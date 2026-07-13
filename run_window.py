import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.animation as mpl_animation
import networkx as nx
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import queue
import threading

from execution import (
    EXECUTION_STATUSES,
    ExecutionContext,
    LocalProcessRunner,
    build_orchestrator_command,
    normalize_execution_mode,
    resolve_run_command,
)
from run_config_builder import RunConfiguration, format_run_config_preview
from experiment_instance_builder import ExperimentInstance, format_instance_preview
from theme import (
    BG_MAIN,
    BORDER,
    FONT_PT_BASE,
    FONT_FAMILY,
    FONT_MONO,
    HEADER_FG,
    INPUT_BG,
    INPUT_BORDER,
    LOG_ERROR,
    LOG_SUCCESS,
    MUTED_TEXT,
    VALIDATION_WARN,
    PANEL_BLUE,
    PROGRESS_TROUGH,
    SUMMARY_BG,
    TEXT_MAIN,
)
from theme_manager import subscribe as theme_subscribe, unsubscribe as theme_unsubscribe
from ui_chrome import SPACE_MD, SPACE_SM, status_badge
from distributed_simulator import DistributedSimulator, total_simulation_frames
from experiment_runtime import (
    summarize_policies_for_run,
    suggested_comm_log_interval_ms,
    validate_run_policies,
)
from topology_graph import build_graph_for_run, effective_topology_for_run
from topology_validate import validate_ui_topology
import app_settings
from experiment_data import default_experiment_state, export_topology_for_save
from experiment_io import write_run_results

# Console-style terminal placeholder (UI only; not theme-driven).
_TERMINAL_BG = "#1E1E1E"
_TERMINAL_FG = "#CCCCCC"
_TERMINAL_BORDER = "#3C3C3C"

# Graph ~72% / bottom dock ~28% of the resizable visualization area.
_VIZ_GRAPH_WEIGHT = 3
_VIZ_DOCK_WEIGHT = 1


def _configure_run_dock_notebook() -> None:
    """Hide native notebook tabs — dock uses custom pill tab bar."""
    style = ttk.Style()
    style.layout("RunDock.TNotebook.Tab", [])
    style.configure("RunDock.TNotebook", tabmargins=(0, 0, 0, 0))


class RunDockTabBar(tk.Frame):
    """Rounded pill tabs for the run-window bottom dock (Summary · Logs · Terminal)."""

    def __init__(self, parent: tk.Misc, notebook: ttk.Notebook, labels: list[str]) -> None:
        super().__init__(parent, bg=PANEL_BLUE, highlightthickness=0)
        self._notebook = notebook
        self._labels = labels
        self._buttons: list[ttk.Button] = []
        self._disabled: set[int] = set()
        self._active = 0

        strip = tk.Frame(self, bg=PANEL_BLUE, highlightthickness=0)
        strip.pack(anchor="w")
        inner = ttk.Frame(strip, style="TabStrip.TFrame", padding=(4, 4))
        inner.pack(anchor="w")

        for i, label in enumerate(labels):
            btn = ttk.Button(
                inner,
                text=label,
                style="TabPill.TButton",
                command=lambda idx=i: self.select(idx),
            )
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self._buttons.append(btn)

        notebook.bind("<<NotebookTabChanged>>", self._sync, add=True)
        self.select(0)

    def set_tab_enabled(self, index: int, enabled: bool) -> None:
        if enabled:
            self._disabled.discard(index)
        else:
            self._disabled.add(index)
        if 0 <= index < len(self._buttons):
            state = "normal" if enabled else "disabled"
            self._buttons[index].configure(state=state)

    def select(self, index: int) -> None:
        if index in self._disabled:
            return
        tabs = self._notebook.tabs()
        if not tabs or index < 0 or index >= len(tabs):
            return
        self._active = index
        self._notebook.select(tabs[index])
        for i, btn in enumerate(self._buttons):
            btn.configure(style="TabPillActive.TButton" if i == index else "TabPill.TButton")

    def _sync(self, _e: tk.Event | None = None) -> None:
        try:
            idx = self._notebook.index(self._notebook.select())
        except tk.TclError:
            return
        if idx != self._active and idx not in self._disabled:
            self.select(idx)


class RunWindow(tk.Toplevel):
    """Secondary desktop window shown when starting a run."""

    def __init__(
        self,
        parent,
        *,
        experiment_name: str,
        experiment_state: dict[str, Any],
        execution_context: ExecutionContext | None = None,
        get_execution_context: Callable[[], ExecutionContext] | None = None,
        run_configuration: RunConfiguration | None = None,
        experiment_instance: ExperimentInstance | None = None,
        experiment_instances: list[ExperimentInstance] | None = None,
    ):
        super().__init__(parent)
        self._experiment_name = experiment_name
        self._experiment_state = experiment_state
        self._run_configuration = run_configuration
        self._experiment_instance = experiment_instance
        self._experiment_instances = list(experiment_instances or [])
        self._execution_context = execution_context or ExecutionContext()
        self._get_execution_context = get_execution_context
        self._process_runner: LocalProcessRunner | None = None
        self._execution_status = "Idle"
        self._graph_anim = None
        self._canvas = None
        self._worker_thread: threading.Thread | None = None
        self._frame_queue: "queue.Queue[tuple[int, Any]]" = queue.Queue()
        self._stop_requested = False
        self._drain_after_id: str | None = None
        self._sim_id = 0
        self.title("Run — Simulation")
        self.geometry("1280x900")
        self.configure(bg=BG_MAIN)
        self.transient(parent)

        import theme as _tinit

        _configure_run_dock_notebook()

        main = ttk.Frame(self, padding=12)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)

        hdr_bar = ttk.Frame(main)
        hdr_bar.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_SM))
        self._hdr_title = tk.Label(
            hdr_bar,
            text=self._run_window_title(experiment_name),
            font=(FONT_FAMILY, FONT_PT_BASE + 2, "bold"),
            bg=BG_MAIN,
            fg=HEADER_FG,
        )
        self._hdr_title.pack(side=tk.LEFT, anchor="w")

        badge_row = ttk.Frame(main, style="TFrame")
        badge_row.grid(row=1, column=0, sticky="ew", pady=(0, SPACE_SM))
        mode_label = "Local" if normalize_execution_mode(self._execution_context.mode) == "local" else "Remote"
        self._badge_mode = status_badge(badge_row, mode_label)
        self._badge_mode.pack(side=tk.LEFT, padx=(0, SPACE_SM))
        self._badge_status = status_badge(badge_row, "Idle", color=MUTED_TEXT)
        self._badge_status.pack(side=tk.LEFT, padx=(0, SPACE_SM))
        agent_count = ""
        try:
            agent_count = str(experiment_state.get("environment", {}).get("agent_count", "") or "")
        except Exception:
            pass
        if agent_count:
            self._badge_agents = status_badge(badge_row, f"{agent_count} Agents")
            self._badge_agents.pack(side=tk.LEFT, padx=(0, SPACE_SM))
        self._badge_round = status_badge(badge_row, "Round: —", color=MUTED_TEXT)
        self._badge_round.pack(side=tk.LEFT, padx=(0, SPACE_SM))

        toolbar = ttk.Frame(main, style="TabStrip.TFrame", padding=(4, 4))
        toolbar.grid(row=2, column=0, sticky="ew", pady=(0, SPACE_SM))

        def _tb(txt: str, cmd=None, *, style: str = "Secondary.TButton") -> ttk.Button:
            b = ttk.Button(toolbar, text=txt, style=style, command=cmd if cmd is not None else (lambda: None))
            b.pack(side=tk.LEFT, padx=(0, 6))
            return b

        _tb("Graph", self._focus_graph_area)
        _tb("Settings", self._show_settings_tab)
        _tb("Save As", self._save_as_results)
        self._run_btn = _tb("Run", self._restart_simulation, style="PrimaryPill.TButton")
        self._stop_btn = _tb("Stop", self._stop_run, style="Danger.TButton")

        exec_panel = ttk.Frame(main, style="Panel.TFrame", padding=(SPACE_MD, SPACE_SM))
        exec_panel.grid(row=3, column=0, sticky="ew", pady=(0, SPACE_SM))
        exec_panel.columnconfigure(0, weight=1)

        meta_row = ttk.Frame(exec_panel, style="CardSurface.TFrame")
        meta_row.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_SM))
        ttk.Label(meta_row, text="Execution Mode", style="Muted.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        self._execution_mode_lbl = tk.Label(
            meta_row,
            text=mode_label,
            bg=PANEL_BLUE,
            fg=TEXT_MAIN,
            font=(FONT_FAMILY, FONT_PT_BASE, "bold"),
            padx=8,
            pady=2,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        self._execution_mode_lbl.pack(side=tk.LEFT, padx=(0, SPACE_MD))
        ttk.Label(meta_row, text="Execution Status", style="Muted.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        self._execution_status_lbl = tk.Label(
            meta_row,
            text="Idle",
            bg=PANEL_BLUE,
            fg=MUTED_TEXT,
            font=(FONT_FAMILY, FONT_PT_BASE, "bold"),
            padx=8,
            pady=2,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        self._execution_status_lbl.pack(side=tk.LEFT)

        ttk.Label(exec_panel, text="Command Preview", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 4))
        cmd_holder = tk.Frame(exec_panel, bg=INPUT_BG, highlightbackground=INPUT_BORDER, highlightthickness=1)
        cmd_holder.grid(row=2, column=0, sticky="ew")
        cmd_holder.columnconfigure(0, weight=1)
        self._command_preview = tk.Text(
            cmd_holder,
            height=2,
            wrap=tk.WORD,
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            font=(FONT_MONO, max(8, FONT_PT_BASE - 1)),
            state=tk.DISABLED,
        )
        self._command_preview.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        self._exec_panel = exec_panel
        self._cmd_holder = cmd_holder

        # Resizable graph (top) + execution dock (bottom): ~72% / ~28%.
        self._viz_pane = ttk.Panedwindow(main, orient=tk.VERTICAL)
        self._viz_pane.grid(row=4, column=0, sticky="nsew")

        graph_outer = ttk.Frame(self._viz_pane, style="Panel.TFrame", padding=4)
        graph_outer.columnconfigure(0, weight=1)
        graph_outer.rowconfigure(0, weight=1)

        dock_shell = tk.Frame(self._viz_pane, bg=PANEL_BLUE, highlightthickness=0)
        dock_shell.columnconfigure(0, weight=1)
        dock_shell.rowconfigure(1, weight=1)

        self._viz_pane.add(graph_outer, weight=_VIZ_GRAPH_WEIGHT)
        self._viz_pane.add(dock_shell, weight=_VIZ_DOCK_WEIGHT)

        def _set_viz_sash() -> None:
            try:
                self._viz_pane.update_idletasks()
                h = self._viz_pane.winfo_height()
                if h > 120:
                    self._viz_pane.sashpos(0, int(h * 0.72))
            except tk.TclError:
                pass

        self.after_idle(_set_viz_sash)

        dock_pad = tk.Frame(dock_shell, bg=PANEL_BLUE, highlightthickness=0)
        dock_pad.pack(fill=tk.BOTH, expand=True, padx=SPACE_MD, pady=SPACE_MD)
        dock_pad.columnconfigure(0, weight=1)
        dock_pad.rowconfigure(1, weight=1)

        bottom_nb = ttk.Notebook(dock_pad, style="RunDock.TNotebook")
        bottom_nb.grid(row=1, column=0, sticky="nsew")
        self._run_dock_tabs = RunDockTabBar(dock_pad, bottom_nb, ["Summary", "Logs", "Terminal"])
        self._run_dock_tabs.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_SM))

        self.graph_placeholder = tk.Frame(
            graph_outer,
            bg=_tinit.GRAPH_AREA_BG,
            highlightbackground=_tinit.BORDER,
            highlightthickness=1,
        )
        self.graph_placeholder.grid(row=0, column=0, sticky="nsew")

        summary_tab = ttk.Frame(bottom_nb, style="Panel.TFrame", padding=SPACE_MD)
        bottom_nb.add(summary_tab, text="Summary")
        summary_tab.columnconfigure(0, weight=1)
        summary_tab.rowconfigure(0, weight=1)

        sum_box = tk.Frame(
            summary_tab,
            bg=SUMMARY_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=SPACE_MD,
            pady=SPACE_MD,
        )
        sum_box.grid(row=0, column=0, sticky="nsew")
        self._sum_box = sum_box

        prog_fr = tk.Frame(sum_box, bg=SUMMARY_BG)
        prog_fr.pack(fill=tk.X, pady=(0, SPACE_SM))
        tk.Label(prog_fr, text="Progress", bg=SUMMARY_BG, fg=MUTED_TEXT, font=(FONT_FAMILY, FONT_PT_BASE - 1)).pack(
            anchor="w", pady=(0, 4)
        )
        prog_holder = tk.Frame(prog_fr, bg=SUMMARY_BG, highlightbackground=BORDER, highlightthickness=1)
        prog_holder.pack(fill=tk.X)
        self.run_progress = ttk.Progressbar(
            prog_holder, style="Horizontal.TProgressbar", mode="determinate", maximum=100, value=0
        )
        self.run_progress.pack(fill=tk.X, expand=True)
        self.progress_pct = tk.Label(
            prog_holder,
            text="0%",
            bg=PROGRESS_TROUGH,
            font=(FONT_FAMILY, FONT_PT_BASE - 1, "bold"),
            fg=TEXT_MAIN,
        )
        self.progress_pct.place(in_=self.run_progress, relx=0.5, rely=0.5, anchor="center")
        self.progress_pct.lift()

        self.summary_eta_lbl = tk.Label(
            sum_box, text="ETA: —", bg=SUMMARY_BG, fg=MUTED_TEXT, font=(FONT_FAMILY, FONT_PT_BASE), anchor="w"
        )
        self.summary_eta_lbl.pack(fill=tk.X, pady=(0, 6))
        self.summary_active_lbl = tk.Label(
            sum_box,
            text="Active Agents: —",
            bg=SUMMARY_BG,
            fg=LOG_SUCCESS,
            font=(FONT_FAMILY, FONT_PT_BASE),
            anchor="w",
        )
        self.summary_active_lbl.pack(fill=tk.X, pady=(0, 6))
        self.summary_round_lbl = tk.Label(
            sum_box,
            text="Round: —",
            bg=SUMMARY_BG,
            fg=LOG_SUCCESS,
            font=(FONT_FAMILY, FONT_PT_BASE),
            anchor="w",
        )
        self.summary_round_lbl.pack(fill=tk.X, pady=(0, SPACE_SM))
        self.summary_status_lbl = tk.Label(
            sum_box,
            text="Simulation Status: Idle",
            bg=SUMMARY_BG,
            fg=MUTED_TEXT,
            font=(FONT_FAMILY, FONT_PT_BASE),
            anchor="w",
        )
        self.summary_status_lbl.pack(fill=tk.X)

        logs_tab = ttk.Frame(bottom_nb, style="Panel.TFrame", padding=SPACE_SM)
        bottom_nb.add(logs_tab, text="Logs")
        logs_tab.columnconfigure(0, weight=1)
        logs_tab.rowconfigure(0, weight=1)

        log_frame = tk.Frame(logs_tab, bg=PANEL_BLUE, highlightbackground=BORDER, highlightthickness=1)
        log_frame.grid(row=0, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            height=8,
            wrap=tk.WORD,
            bg=INPUT_BG,
            fg=MUTED_TEXT,
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=INPUT_BORDER,
            font=(FONT_MONO, max(8, FONT_PT_BASE - 1)),
            state=tk.DISABLED,
        )
        self.log_text.tag_configure("error", foreground=LOG_ERROR)
        self.log_text.tag_configure("success", foreground=LOG_SUCCESS)
        self.log_text.tag_configure("info", foreground=MUTED_TEXT)
        self.log_text.tag_configure("warn", foreground=VALIDATION_WARN)
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")

        self._log_frame = log_frame

        terminal_tab = ttk.Frame(bottom_nb, style="Panel.TFrame", padding=SPACE_SM)
        bottom_nb.add(terminal_tab, text="Terminal")
        terminal_tab.columnconfigure(0, weight=1)
        terminal_tab.rowconfigure(0, weight=1)

        term_frame = tk.Frame(
            terminal_tab,
            bg=_TERMINAL_BG,
            highlightbackground=_TERMINAL_BORDER,
            highlightthickness=1,
        )
        term_frame.grid(row=0, column=0, sticky="nsew")
        term_frame.columnconfigure(0, weight=1)
        term_frame.rowconfigure(0, weight=1)

        self._terminal_text = tk.Text(
            term_frame,
            height=8,
            wrap=tk.WORD,
            bg=_TERMINAL_BG,
            fg=_TERMINAL_FG,
            insertbackground=_TERMINAL_FG,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            font=(FONT_MONO, max(8, FONT_PT_BASE - 1)),
            state=tk.NORMAL,
            cursor="arrow",
        )
        self._terminal_text.insert("1.0", "")
        self._terminal_text.configure(state=tk.DISABLED)
        term_scroll = ttk.Scrollbar(term_frame, command=self._terminal_text.yview)
        self._terminal_text.configure(yscrollcommand=term_scroll.set)
        self._terminal_text.grid(row=0, column=0, sticky="nsew")
        term_scroll.grid(row=0, column=1, sticky="ns")
        self._term_frame = term_frame
        self._terminal_tab = terminal_tab
        self._terminal_placeholder = True

        self._bottom_nb = bottom_nb
        self._mpl_fig = None
        self._mpl_ax = None
        self._mpl_node_artist = None
        self._mpl_edge_artist = None
        self.graph_positions: dict[Any, tuple[float, float]] | None = None
        self._graph_node_list: list[Any] = []
        self._graph_edge_list: list[tuple[Any, Any]] = []
        self._graph_edge_to_idx: dict[tuple[Any, Any], int] = {}
        self._graph_base_node_size = 120
        self._sim_debug = True
        self._graph_theme = self._make_graph_theme_dict()
        theme_subscribe(self._sync_theme)
        self._append_log("Run window opened.")
        if self._experiment_instances:
            total = len(self._experiment_instances)
            current = (self._experiment_instance.instance_number if self._experiment_instance else 1)
            self._append_log(f"Experiment instances: {current} of {total}")
        if self._experiment_instance is not None:
            self._append_log("Active experiment instance:")
            for line in format_instance_preview(self._experiment_instance).splitlines():
                self._append_log(line)
        if self._run_configuration is not None:
            self._append_log("Run configuration prepared (build only — not executed):")
            for line in format_run_config_preview(self._run_configuration).splitlines():
                self._append_log(line)
        self._append_log(summarize_policies_for_run(experiment_state))
        _ok_pol, pol_warns = validate_run_policies(experiment_state)
        for w in pol_warns:
            self._append_log(f"Policy: {w}")
        topo_eff = effective_topology_for_run(experiment_state)
        ok_top, vmsg = validate_ui_topology(topo_eff)
        self._append_log(f"Topology: {vmsg}" if ok_top else f"Topology issue: {vmsg}")
        self._setup_graph_and_summary(experiment_state)
        self._refresh_command_preview()
        self._populate_terminal_info()
        self._apply_execution_mode()
        bottom_nb.select(0)
        self._run_dock_tabs.select(0)
        self._sync_theme()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _run_window_title(self, experiment_name: str) -> str:
        base = f"Experiment Name - {experiment_name}"
        if self._experiment_instances and self._experiment_instance is not None:
            return (
                f"{base}  (Instance {self._experiment_instance.instance_number} "
                f"of {len(self._experiment_instances)})"
            )
        return base

    def _execution_mode(self) -> str:
        return normalize_execution_mode(self._execution_context.mode)

    def _terminal_experiment_label(self) -> str:
        if self._experiment_instance is not None:
            label = self._experiment_instance.display_label()
            if ": " in label:
                return label.split(": ", 1)[1]
            return label
        name = str(self._experiment_state.get("name") or self._experiment_name or "").strip()
        return name or "—"

    def _build_terminal_info_text(self) -> str:
        mode_label = "Local" if self._execution_mode() == "local" else "Remote (Slurm)"
        total = len(self._experiment_instances)
        if self._experiment_instance is not None and total > 0:
            inst_line = f"Instance: {self._experiment_instance.instance_number} of {total}"
        elif total > 0:
            inst_line = f"Instance: 1 of {total}"
        else:
            inst_line = "Instance: —"

        cmd = build_orchestrator_command(self._execution_context).strip()
        if not cmd:
            cmd = "(no command generated — load driver.yaml and the YAML stack on Page 1)"

        return "\n".join(
            [
                f"Execution Mode: {mode_label}",
                "",
                inst_line,
                "",
                f"Experiment: {self._terminal_experiment_label()}",
                "",
                "Command Preview:",
                cmd,
                "",
                "Status:",
                "Ready. Terminal execution is not connected yet.",
            ]
        )

    def _populate_terminal_info(self) -> None:
        """Fill the Terminal tab with static execution metadata (no subprocess)."""
        text = self._build_terminal_info_text()
        try:
            self._terminal_text.configure(state=tk.NORMAL)
            self._terminal_text.delete("1.0", tk.END)
            self._terminal_text.insert("1.0", text)
            self._terminal_text.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _set_execution_status(self, status: str) -> None:
        if status not in EXECUTION_STATUSES:
            status = "Idle"
        self._execution_status = status
        color = MUTED_TEXT
        if status == "Running":
            color = LOG_SUCCESS
        elif status == "Completed":
            color = LOG_SUCCESS
        elif status in ("Failed", "Stopped"):
            color = LOG_ERROR

        def _apply() -> None:
            try:
                self._badge_status.configure(text=f"● {status}", fg=color)
                self._execution_status_lbl.configure(text=status, fg=color)
                self.summary_status_lbl.configure(text=f"Simulation Status: {status}", fg=color)
            except tk.TclError:
                pass

        try:
            self.after(0, _apply)
        except tk.TclError:
            pass

    def _refresh_command_preview(self) -> None:
        cmd = build_orchestrator_command(self._execution_context)
        try:
            self._command_preview.configure(state=tk.NORMAL)
            self._command_preview.delete("1.0", tk.END)
            self._command_preview.insert("1.0", cmd)
            self._command_preview.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _apply_execution_mode(self) -> None:
        mode = self._execution_mode()
        nb = self._bottom_nb
        terminal_idx = 2
        logs_idx = 1
        mode_label = "Local" if mode == "local" else "Remote (Slurm)"
        try:
            self._execution_mode_lbl.configure(text=mode_label)
            self._badge_mode.configure(text=mode_label)
            self._run_dock_tabs.set_tab_enabled(terminal_idx, mode == "local")
            for tab_id in nb.tabs():
                label = nb.tab(tab_id, "text")
                if label == "Terminal":
                    nb.tab(tab_id, state="normal" if mode == "local" else "disabled")
            if mode != "local":
                try:
                    if nb.index(nb.select()) == terminal_idx:
                        self._run_dock_tabs.select(logs_idx)
                except tk.TclError:
                    pass
        except tk.TclError:
            pass

    def _append_terminal(self, text: str, *, stream: str = "stdout") -> None:
        if getattr(self, "_terminal_placeholder", False):
            return

        def _do() -> None:
            try:
                self._terminal_text.configure(state=tk.NORMAL)
                self._terminal_text.insert(tk.END, text + "\n")
                self._terminal_text.see(tk.END)
                self._terminal_text.configure(state=tk.DISABLED)
            except tk.TclError:
                pass

        try:
            self.after(0, _do)
        except tk.TclError:
            pass

    def _clear_terminal(self) -> None:
        if getattr(self, "_terminal_placeholder", False):
            return
        try:
            self._terminal_text.configure(state=tk.NORMAL)
            self._terminal_text.delete("1.0", tk.END)
            self._terminal_text.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _stop_process_runner(self) -> None:
        runner = self._process_runner
        if runner is not None and runner.running:
            runner.stop()
        self._process_runner = None

    def _refresh_execution_context(self) -> None:
        if self._get_execution_context is not None:
            try:
                self._execution_context = self._get_execution_context()
            except Exception:
                pass
        mode_label = "Local" if self._execution_mode() == "local" else "Remote (Slurm)"
        try:
            self._execution_mode_lbl.configure(text=mode_label)
            self._badge_mode.configure(text=mode_label)
        except tk.TclError:
            pass
        self._apply_execution_mode()

    def _start_execution(self) -> None:
        """Refresh command preview only; terminal tab is a placeholder (no subprocess)."""
        self._refresh_execution_context()
        self._stop_process_runner()
        self._refresh_command_preview()
        self._set_execution_status("Idle")

    def _stop_run(self) -> None:
        was_running = self._process_runner is not None and self._process_runner.running
        if was_running:
            self._set_execution_status("Stopped")
            self._append_log("Execution stopped.")
        self._stop_process_runner()
        self._stop_animation()

    def _make_graph_theme_dict(self) -> dict[str, str]:
        import theme as t

        return {
            "idle": t.GRAPH_NODE_BASE,
            "initiator": t.GRAPH_NODE_ACTIVE,
            "sender": t.GRAPH_NODE_SENDER,
            "receiver": t.GRAPH_NODE_RECEIVER,
            "dropout": t.GRAPH_NODE_DROPOUT,
            "interrupted": t.GRAPH_NODE_INTERRUPT,
            "aggregation": t.GRAPH_NODE_AGGREGATION,
            "edge_base": t.GRAPH_EDGE_BASE,
            "edge_active": t.GRAPH_EDGE_ACTIVE,
            "edge_dropout": t.GRAPH_EDGE_DROPOUT,
            "edge_delivery": t.GRAPH_EDGE_DELIVERY,
        }

    def _node_id(self, idx: int | None) -> str:
        if idx is None:
            return "—"
        nl = self._graph_node_list
        if 0 <= idx < len(nl):
            return str(nl[idx])
        return str(idx)

    def _format_step_log(self, sr) -> str | None:
        """Structured log block for meaningful simulation events."""
        ev = sr.event
        if ev in ("idle", "cooldown", "no_neighbor"):
            return None
        lines = [f"Round {sr.round}  Step {sr.step_in_round}/{sr.round_length}"]
        if ev == "transmission_started" and sr.sender_idx is not None and sr.receiver_idx is not None:
            lines.append(f"Agent {self._node_id(sr.sender_idx)} → Agent {self._node_id(sr.receiver_idx)}")
            lines.append("Model transmitted")
            if sr.latency_steps is not None:
                lines.append(f"Latency {sr.latency_steps} step(s)")
        elif ev == "delivery" and sr.delivery_src is not None and sr.delivery_dst is not None:
            lines.append(f"Agent {self._node_id(sr.delivery_src)} → Agent {self._node_id(sr.delivery_dst)}")
            lines.append("Model update delivered")
        elif ev == "dropout" and sr.sender_idx is not None and sr.receiver_idx is not None:
            lines.append(f"Agent {self._node_id(sr.sender_idx)} → Agent {self._node_id(sr.receiver_idx)}")
            lines.append("Communication failure (dropout)")
        elif ev == "interruption":
            lines.append(f"{sr.interrupted} in-flight message(s) interrupted")
        elif ev == "aggregation":
            lines.append("Aggregation complete (federated mean)")
        else:
            lines.append(sr.line)
        return "\n".join(lines)

    def _apply_frame_visuals(self, sr, *, node_artist, edge_artist, ax, nn: int) -> None:
        """Paint node/edge colors from the current simulation event."""
        gt = self._graph_theme
        base_sz = self._graph_base_node_size
        node_colors = [gt["idle"]] * nn
        node_sizes = [base_sz] * nn

        sim = getattr(self, "_distributed_sim", None)
        can_train = sim.can_train if sim is not None else [True] * nn

        def _paint(idx: int | None, color: str, scale: float = 1.0) -> None:
            if idx is not None and 0 <= idx < nn:
                node_colors[idx] = color
                node_sizes[idx] = max(base_sz, int(base_sz * scale))

        initiator = sr.initiator_idx
        if initiator is not None and 0 <= initiator < nn:
            _paint(initiator, gt["initiator"], 1.25)

        ev = sr.event
        if ev == "transmission_started":
            _paint(sr.sender_idx, gt["sender"], 1.55)
            _paint(sr.receiver_idx, gt["receiver"], 1.45)
        elif ev == "delivery":
            _paint(sr.delivery_src, gt["sender"], 1.55)
            _paint(sr.delivery_dst, gt["receiver"], 1.45)
        elif ev == "dropout":
            _paint(sr.sender_idx, gt["dropout"], 1.5)
            _paint(sr.receiver_idx, gt["dropout"], 1.4)
        elif ev == "interruption":
            if initiator is not None:
                _paint(initiator, gt["interrupted"], 1.3)
        elif ev == "aggregation":
            for i in range(nn):
                if i < len(can_train) and can_train[i]:
                    node_colors[i] = gt["aggregation"]
                    node_sizes[i] = int(base_sz * 1.2)

        node_artist.set_facecolor(node_colors)
        node_artist.set_sizes(node_sizes)

        edge_list = self._graph_edge_list
        edge_to_idx = self._graph_edge_to_idx
        node_list = self._graph_node_list
        if edge_artist is not None and edge_list:
            edge_colors = [gt["edge_base"]] * len(edge_list)
            edge_widths = [1.2] * len(edge_list)
            edge_alphas = [0.55] * len(edge_list)
            if sr.edge_highlight is not None:
                a, b = sr.edge_highlight
                key = tuple(sorted((node_list[a], node_list[b])))
                ei = edge_to_idx.get(key)
                if ei is not None:
                    if ev == "dropout":
                        edge_colors[ei] = gt["edge_dropout"]
                        edge_widths[ei] = 3.2
                        edge_alphas[ei] = 1.0
                    elif ev == "delivery":
                        edge_colors[ei] = gt["edge_delivery"]
                        edge_widths[ei] = 3.0
                        edge_alphas[ei] = 1.0
                    else:
                        edge_colors[ei] = gt["edge_active"]
                        edge_widths[ei] = 2.8
                        edge_alphas[ei] = 1.0
            edge_artist.set_color(edge_colors)
            edge_artist.set_linewidth(edge_widths)
            try:
                edge_artist.set_alpha(edge_alphas)
            except Exception:
                pass

    def _visualization_enabled(self) -> bool:
        """Whether graph highlighting and animation redraws run during simulation."""
        return app_settings.SETTINGS.visualization_enabled

    def _debug_sim_frame(self, sr, frame_idx: int) -> None:
        if not self._visualization_enabled() or not self._sim_debug:
            return
        edge = "—"
        if sr.edge_highlight is not None:
            a, b = sr.edge_highlight
            edge = f"{self._node_id(a)} → {self._node_id(b)}"
        print(
            f"[sim] frame={frame_idx} round={sr.round} step={sr.step_in_round}/{sr.round_length} "
            f"event={sr.event} initiator={self._node_id(sr.initiator_idx)} "
            f"sender={self._node_id(sr.sender_idx)} receiver={self._node_id(sr.receiver_idx)} "
            f"edge={edge}",
            flush=True,
        )

    def _sync_theme(self) -> None:
        import theme as t

        try:
            self.configure(bg=t.BG_MAIN)
        except tk.TclError:
            return
        self._hdr_title.configure(bg=t.BG_MAIN, fg=t.HEADER_FG, font=(FONT_FAMILY, t.FONT_PT_BASE + 2, "bold"))
        self.graph_placeholder.configure(bg=t.GRAPH_AREA_BG, highlightbackground=t.BORDER, highlightthickness=1)
        self._sum_box.configure(bg=t.SUMMARY_BG, highlightbackground=t.BORDER)
        for w in self._sum_box.winfo_children():
            if isinstance(w, tk.Frame):
                try:
                    w.configure(bg=t.SUMMARY_BG)
                except tk.TclError:
                    pass
                for c in w.winfo_children():
                    if isinstance(c, tk.Frame):
                        try:
                            c.configure(bg=t.SUMMARY_BG, highlightbackground=t.BORDER)
                        except tk.TclError:
                            pass
                    elif isinstance(c, tk.Label):
                        try:
                            c.configure(bg=t.SUMMARY_BG)
                        except tk.TclError:
                            pass
            elif isinstance(w, tk.Label):
                try:
                    w.configure(bg=t.SUMMARY_BG)
                except tk.TclError:
                    pass
        self.summary_eta_lbl.configure(fg=t.MUTED_TEXT, font=(FONT_FAMILY, t.FONT_PT_BASE))
        self.summary_active_lbl.configure(fg=t.LOG_SUCCESS, font=(FONT_FAMILY, t.FONT_PT_BASE))
        self.summary_round_lbl.configure(fg=t.LOG_SUCCESS, font=(FONT_FAMILY, t.FONT_PT_BASE))
        self.summary_status_lbl.configure(fg=t.MUTED_TEXT, font=(FONT_FAMILY, t.FONT_PT_BASE))
        try:
            self._execution_mode_lbl.configure(bg=t.PANEL_BLUE, fg=t.TEXT_MAIN, highlightbackground=t.BORDER)
            status = self._execution_status
            status_color = t.MUTED_TEXT
            if status in ("Running", "Completed"):
                status_color = t.LOG_SUCCESS
            elif status in ("Failed", "Stopped"):
                status_color = t.LOG_ERROR
            self._execution_status_lbl.configure(bg=t.PANEL_BLUE, fg=status_color, highlightbackground=t.BORDER)
        except tk.TclError:
            pass
        try:
            self._run_dock_tabs.configure(bg=t.PANEL_BLUE)
        except tk.TclError:
            pass
        try:
            self._viz_pane.configure(style="TPanedwindow")
        except tk.TclError:
            pass
        self.progress_pct.configure(bg=t.PROGRESS_TROUGH, fg=t.TEXT_MAIN, font=(FONT_FAMILY, t.FONT_PT_BASE - 1, "bold"))
        try:
            self._log_frame.configure(bg=t.PANEL_BLUE, highlightbackground=t.BORDER)
        except tk.TclError:
            pass
        self.log_text.configure(
            bg=t.INPUT_BG,
            fg=t.MUTED_TEXT,
            highlightbackground=t.INPUT_BORDER,
            font=(FONT_MONO, max(8, t.FONT_PT_BASE - 1)),
        )
        self.log_text.tag_configure("error", foreground=t.LOG_ERROR)
        self.log_text.tag_configure("success", foreground=t.LOG_SUCCESS)
        self.log_text.tag_configure("info", foreground=t.MUTED_TEXT)
        self.log_text.tag_configure("warn", foreground=t.VALIDATION_WARN)
        try:
            self._term_frame.configure(bg=_TERMINAL_BG, highlightbackground=_TERMINAL_BORDER)
        except tk.TclError:
            pass
        self._terminal_text.configure(
            bg=_TERMINAL_BG,
            fg=_TERMINAL_FG,
            insertbackground=_TERMINAL_FG,
            font=(FONT_MONO, max(8, t.FONT_PT_BASE - 1)),
        )
        try:
            self._cmd_holder.configure(bg=t.INPUT_BG, highlightbackground=t.INPUT_BORDER)
            self._command_preview.configure(bg=t.INPUT_BG, fg=t.TEXT_MAIN)
        except tk.TclError:
            pass
        status = self._execution_status
        status_color = t.MUTED_TEXT
        if status == "Running" or status == "Completed":
            status_color = t.LOG_SUCCESS
        elif status in ("Failed", "Stopped"):
            status_color = t.LOG_ERROR
        try:
            self._badge_status.configure(
                text=f"● {status}",
                fg=status_color,
                bg=t.LIST_SURFACE_BG,
                highlightbackground=t.BORDER_INNER,
            )
            self._badge_mode.configure(bg=t.LIST_SURFACE_BG, highlightbackground=t.BORDER_INNER)
            self._badge_round.configure(bg=t.LIST_SURFACE_BG, highlightbackground=t.BORDER_INNER)
        except tk.TclError:
            pass
        self._refresh_mpl_graph_theme(t)

    def _settings_yaml_text(self) -> str:
        from experiment_io import _yaml_dump

        return _yaml_dump(self._experiment_state)

    def _show_settings_tab(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("Settings — Experiment YAML")
        dlg.transient(self)
        dlg.geometry("720x520")
        try:
            dlg.configure(bg=BG_MAIN)
        except tk.TclError:
            pass

        outer = ttk.Frame(dlg, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        settings_frame = tk.Frame(outer, bg=PANEL_BLUE, highlightbackground=BORDER, highlightthickness=2)
        settings_frame.grid(row=0, column=0, sticky="nsew")
        settings_frame.columnconfigure(0, weight=1)
        settings_frame.rowconfigure(0, weight=1)

        settings_scroll = ttk.Scrollbar(settings_frame, orient=tk.VERTICAL)
        settings_text = tk.Text(
            settings_frame,
            wrap=tk.NONE,
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=INPUT_BORDER,
            font=(FONT_MONO, max(8, FONT_PT_BASE - 1)),
            state=tk.DISABLED,
            yscrollcommand=settings_scroll.set,
        )
        settings_scroll.configure(command=settings_text.yview)
        settings_text.grid(row=0, column=0, sticky="nsew")
        settings_scroll.grid(row=0, column=1, sticky="ns")

        body = self._settings_yaml_text()
        settings_text.configure(state=tk.NORMAL)
        settings_text.insert("1.0", body)
        settings_text.configure(state=tk.DISABLED)

        ttk.Button(outer, text="Close", command=dlg.destroy).grid(row=1, column=0, sticky="e", pady=(8, 0))

    def _sanitize_save_folder_name(self, name: str) -> str:
        s = re.sub(r'[<>:"/\\|?*]+', "_", name.strip())
        s = re.sub(r"\s+", "_", s).strip("._")
        return s or "Experiment_unnamed"

    def _collect_log_text(self) -> str:
        try:
            return self.log_text.get("1.0", "end-1c")
        except tk.TclError:
            return ""

    def _collect_run_summary(self) -> dict[str, Any]:
        sim = getattr(self, "_sim_state", None) or {}
        return {
            "experiment_name": self._experiment_name,
            "progress_percent": self.progress_pct.cget("text"),
            "eta": self.summary_eta_lbl.cget("text"),
            "active_agents": self.summary_active_lbl.cget("text"),
            "round": self.summary_round_lbl.cget("text"),
            "frame": sim.get("frame"),
            "total_frames": sim.get("total_frames"),
            "visualization_enabled": app_settings.SETTINGS.visualization_enabled,
        }

    def _save_as_results(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("Save As")
        dlg.transient(self)
        dlg.resizable(False, False)
        dlg.grab_set()
        try:
            dlg.configure(bg=BG_MAIN)
        except tk.TclError:
            pass

        default_name = self._experiment_name.strip() or str(self._experiment_state.get("name") or "Experiment_1")
        initial_parent = Path.home()

        outer = ttk.Frame(dlg, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(1, weight=1)

        ttk.Label(outer, text="Save Experiment Results", style="Subsection.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 12)
        )
        ttk.Label(outer, text="Experiment Name:", style="TLabel").grid(row=1, column=0, sticky="w", pady=4)
        v_name = tk.StringVar(value=default_name)
        ttk.Entry(outer, textvariable=v_name, width=40).grid(row=1, column=1, columnspan=2, sticky="ew", pady=4)

        ttk.Label(outer, text="Location:", style="TLabel").grid(row=2, column=0, sticky="w", pady=4)
        v_loc = tk.StringVar(value=str(initial_parent))
        ttk.Entry(outer, textvariable=v_loc, width=34).grid(row=2, column=1, sticky="ew", pady=4)

        def _browse() -> None:
            chosen = filedialog.askdirectory(title="Choose Save Location", initialdir=v_loc.get() or str(initial_parent))
            if chosen:
                v_loc.set(chosen)

        ttk.Button(outer, text="Browse…", command=_browse).grid(row=2, column=2, sticky="w", padx=(8, 0), pady=4)

        bf = ttk.Frame(outer)
        bf.grid(row=3, column=0, columnspan=3, sticky="e", pady=(16, 0))

        def _do_save() -> None:
            parent = Path(v_loc.get().strip()).expanduser()
            folder_name = self._sanitize_save_folder_name(v_name.get())
            if not folder_name:
                messagebox.showerror("Save As", "Enter a valid experiment name.", parent=dlg)
                return
            if not str(parent):
                messagebox.showerror("Save As", "Choose a save location.", parent=dlg)
                return
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                messagebox.showerror("Save As", f"Could not create location:\n{parent}\n\n{e}", parent=dlg)
                return
            if not parent.is_dir():
                messagebox.showerror("Save As", f"Location is not a folder:\n{parent}", parent=dlg)
                return

            exp_dir = parent / folder_name
            out_st = dict(self._experiment_state)
            out_st["name"] = v_name.get().strip() or folder_name

            if exp_dir.exists():
                if not messagebox.askyesno(
                    "Save As",
                    f"Folder already exists:\n{exp_dir}\n\nOverwrite its experiment files?",
                    parent=dlg,
                ):
                    return
            else:
                try:
                    exp_dir.mkdir(parents=True, exist_ok=False)
                except OSError as e:
                    messagebox.showerror("Save As", f"Could not create folder:\n{exp_dir}\n\n{e}", parent=dlg)
                    return

            try:
                write_run_results(
                    exp_dir,
                    st=out_st,
                    topology_export=export_topology_for_save(out_st.get("topology") or {}),
                    default_environment=default_experiment_state(out_st["name"])["environment"],
                    log_text=self._collect_log_text(),
                    summary=self._collect_run_summary(),
                )
            except OSError as e:
                messagebox.showerror("Save As", f"Could not write experiment files:\n{e}", parent=dlg)
                return

            dlg.grab_release()
            dlg.destroy()
            messagebox.showinfo("Save As", f"Experiment results saved successfully.\n\n{exp_dir}")

        ttk.Button(bf, text="Save", style="Accent.TButton", command=_do_save).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bf, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT)

    def _refresh_mpl_graph_theme(self, t) -> None:
        """Apply current theme colors to matplotlib figure, axes, artists, and canvas (Run window graph)."""
        if self._canvas is None:
            return
        fig = self._mpl_fig
        ax = self._mpl_ax
        if fig is not None:
            fig.patch.set_facecolor(t.GRAPH_AREA_BG)
        if ax is not None:
            ax.set_facecolor(t.GRAPH_AREA_BG)
            try:
                ttl = ax.get_title()
                ax.set_title(ttl, color=t.GRAPH_AREA_FG, fontsize=max(9, t.FONT_PT_BASE))
            except Exception:
                pass
        try:
            self._canvas.get_tk_widget().configure(bg=t.GRAPH_AREA_BG)
        except tk.TclError:
            pass

        gt = self._make_graph_theme_dict()
        self._graph_theme = gt

        na = self._mpl_node_artist
        if na is not None:
            try:
                offs = na.get_offsets()
                n = len(offs)
                if n > 0:
                    na.set_facecolor([gt["idle"]] * n)
            except Exception:
                pass

        ea = self._mpl_edge_artist
        nec = getattr(self, "_graph_edge_count", 0)
        if ea is not None and nec > 0:
            try:
                ea.set_color([gt["edge_base"]] * nec)
                ea.set_linewidth([1.2] * nec)
            except Exception:
                pass

        for _node, txt in getattr(self, "_mpl_label_artists", {}).items():
            try:
                txt.set_color(t.GRAPH_AREA_FG)
            except Exception:
                pass

        try:
            self._canvas.draw()
        except Exception:
            try:
                self._canvas.draw_idle()
            except Exception:
                pass

    def _focus_graph_area(self) -> None:
        try:
            w = self.graph_placeholder.winfo_children()
            if w:
                w[0].focus_set()
        except tk.TclError:
            self.graph_placeholder.focus_set()

    def _stop_animation(self) -> None:
        self._stop_requested = True
        if self._drain_after_id is not None:
            try:
                self.after_cancel(self._drain_after_id)
            except Exception:
                pass
            self._drain_after_id = None
        try:
            while True:
                self._frame_queue.get_nowait()
        except Exception:
            pass
        # Best-effort join (do not block UI).
        if self._worker_thread is not None:
            try:
                self._worker_thread.join(timeout=0.1)
            except Exception:
                pass
            self._worker_thread = None
        self._graph_anim = None

    def _update_round_badge(self, text: str) -> None:
        try:
            self._badge_round.configure(text=text)
        except tk.TclError:
            pass

    def _clear_run_ui(self) -> None:
        """Reset visible execution widgets before starting/restarting animation."""
        try:
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.delete("1.0", tk.END)
            self.log_text.configure(state=tk.DISABLED)
        except tk.TclError:
            pass
        try:
            self.run_progress.configure(value=0)
            self.progress_pct.configure(text="0%")
        except tk.TclError:
            pass
        try:
            self.summary_eta_lbl.configure(text="ETA: —")
            self.summary_active_lbl.configure(text="Active Agents: —")
            self.summary_round_lbl.configure(text="Round: —")
            self.summary_status_lbl.configure(text="Simulation Status: Idle", fg=MUTED_TEXT)
            self._update_round_badge("Round: —")
        except tk.TclError:
            pass

    def _restart_simulation(self) -> None:
        """Restart execution + graph animation in-place (supports Run → Stop → Run)."""
        self._sim_id += 1
        self._stop_run()
        self._clear_run_ui()
        try:
            for w in self.graph_placeholder.winfo_children():
                w.destroy()
        except tk.TclError:
            pass
        try:
            self._start_execution()
            self._setup_graph_and_summary(self._experiment_state)
            bottom_nb = getattr(self, "_bottom_nb", None)
            if bottom_nb is not None:
                bottom_nb.select(0)
                if hasattr(self, "_run_dock_tabs"):
                    self._run_dock_tabs.select(0)
        except Exception as e:
            messagebox.showerror("Run", f"Could not restart simulation:\n{e}")

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        lower = text.lower()
        tag = "info"
        if "error" in lower or "failed" in lower or "missing" in lower:
            tag = "error"
        elif "completed" in lower or "started" in lower or "updated" in lower or "delivered" in lower:
            tag = "success"
        elif "warn" in lower or "policy:" in lower:
            tag = "warn"
        self.log_text.insert(tk.END, text + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _on_close(self) -> None:
        theme_unsubscribe(self._sync_theme)
        try:
            self._stop_process_runner()
            self._stop_animation()
        except Exception:
            pass
        self.destroy()

    def _setup_graph_and_summary(self, experiment_state: dict[str, Any]) -> None:
        for w in self.graph_placeholder.winfo_children():
            w.destroy()

        try:
            G, src_msg = build_graph_for_run(experiment_state)
        except Exception as e:
            messagebox.showerror("Graph", f"Could not build graph:\n{e}")
            G = nx.path_graph(3)
            src_msg = f"error ({e}); fallback path_graph(3)"

        if G.number_of_nodes() == 0:
            G = nx.Graph()
            G.add_node(0)

        self._append_log(f"Network source: {src_msg}")
        self._append_log(f"Vertices/Nodes: {G.number_of_nodes()}  Links/Edges: {G.number_of_edges()}")

        topo = effective_topology_for_run(experiment_state)
        try:
            seed = int(float(str(topo.get("global_seed", 0))))
        except Exception:
            seed = 0

        try:
            pos = nx.spring_layout(G, seed=seed, k=max(0.15, 1.2 / max(1, G.number_of_nodes() ** 0.5)))
        except Exception:
            pos = nx.spring_layout(G, seed=42)
        self.graph_positions = pos

        node_list = list(G.nodes())
        node_to_idx = {n: i for i, n in enumerate(node_list)}
        nn = max(len(node_list), 1)
        edge_list = list(G.edges())
        self._graph_edge_count = len(edge_list)
        edge_to_idx = {tuple(sorted((u, v))): i for i, (u, v) in enumerate(edge_list)}
        self._graph_node_list = node_list
        self._graph_edge_list = edge_list
        self._graph_edge_to_idx = edge_to_idx

        import theme as _t0

        fig = Figure(figsize=(6.8, 5.4), dpi=100)
        fig.patch.set_facecolor(_t0.GRAPH_AREA_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(_t0.GRAPH_AREA_BG)

        canvas = FigureCanvasTkAgg(fig, master=self.graph_placeholder)
        self._canvas = canvas
        w = canvas.get_tk_widget()
        w.configure(bg=_t0.GRAPH_AREA_BG)
        w.pack(fill=tk.BOTH, expand=True)

        self._graph_theme = self._make_graph_theme_dict()
        show_labels = len(node_list) <= 40
        base_node_size = max(80, min(320, 8000 // max(1, len(node_list))))
        self._graph_base_node_size = base_node_size
        gt = self._graph_theme
        idle_color = gt["idle"]
        base_edge_color = gt["edge_base"]

        # Draw static artists once; positions fixed in self.graph_positions for all frames.
        edge_artist = nx.draw_networkx_edges(
            G,
            pos,
            ax=ax,
            edge_color=[base_edge_color] * max(1, len(edge_list)),
            width=1.2,
            alpha=0.55,
        )
        node_artist = nx.draw_networkx_nodes(
            G,
            pos,
            ax=ax,
            node_color=[idle_color] * nn,
            node_size=[base_node_size] * nn,
        )
        self._mpl_label_artists = {}
        if show_labels:
            import theme as _tlab

            self._mpl_label_artists = nx.draw_networkx_labels(
                G, pos, ax=ax, font_size=7, font_color=_tlab.GRAPH_AREA_FG
            )
        ax.set_axis_off()

        self._mpl_fig = fig
        self._mpl_ax = ax
        self._mpl_node_artist = node_artist
        self._mpl_edge_artist = edge_artist

        sim = DistributedSimulator.from_experiment(G, experiment_state, node_list, node_to_idx)
        total_frames = total_simulation_frames(experiment_state, nn)
        self._distributed_sim = sim
        _ntr = sum(1 for i in range(nn) if sim.can_train[i])
        self._append_log(
            f"Assignments: {len(sim.profiles)} profile(s), {len(sim.models)} model(s); "
            f"data split train nodes={_ntr}, val nodes={nn - _ntr} (per assignment_ranges)."
        )
        if nn > 0:
            sw = sim.shard_w
            self._append_log(
                f"Sampling shard weights: min={min(sw):.4g} max={max(sw):.4g} "
                f"(used in gossip payload + weighted FedAvg)."
            )
        self._append_log(
            "Profile wait_time: nodes skip sends until that many steps elapse since their last scheduled message."
        )
        self._sim_state = {
            "frame": 0,
            "total_frames": total_frames,
            "last_log_frame": -100,
        }

        anim_ms = suggested_comm_log_interval_ms(experiment_state, base_ms=200)
        run_id = self._sim_id
        self._stop_requested = False

        # Clear any queued frames from a prior run/restart.
        try:
            while True:
                self._frame_queue.get_nowait()
        except Exception:
            pass

        def _worker() -> None:
            """Compute sim.step() off the UI thread; push StepResult to the UI queue."""
            try:
                for frame_idx in range(total_frames):
                    if self._stop_requested:
                        break
                    if run_id != self._sim_id:
                        break
                    sr = sim.step()
                    n_train = sum(1 for i in range(nn) if sim.can_train[i])
                    self._frame_queue.put((frame_idx, sr, n_train))
                # Sentinel to mark completion.
                if run_id == self._sim_id:
                    self._frame_queue.put((-1, None, 0))
            except Exception as e:
                # Best-effort: log via UI thread.
                try:
                    self._frame_queue.put((-1, ("error", str(e)), 0))
                except Exception:
                    pass

        self._worker_thread = threading.Thread(target=_worker, daemon=True)
        self._worker_thread.start()

        st = self._sim_state
        expected_frame = 0

        def _drain() -> None:
            nonlocal expected_frame
            if run_id != self._sim_id or self._stop_requested:
                return

            viz_on = self._visualization_enabled()
            max_per_tick = 1 if viz_on else 32
            processed = 0
            import theme as _tm

            while processed < max_per_tick:
                try:
                    frame_idx, sr, n_train = self._frame_queue.get_nowait()
                except queue.Empty:
                    break

                # Completion sentinel.
                if frame_idx == -1:
                    try:
                        if isinstance(sr, tuple) and sr and sr[0] == "error":
                            self._append_log(f"Animation worker error: {sr[1]}")
                        else:
                            self._append_log("Simulation completed.")
                    except Exception:
                        pass
                    self._drain_after_id = None
                    return

                if frame_idx != expected_frame:
                    expected_frame = frame_idx

                st["frame"] = frame_idx
                if viz_on:
                    self._apply_frame_visuals(sr, node_artist=node_artist, edge_artist=edge_artist, ax=ax, nn=nn)
                    self._debug_sim_frame(sr, frame_idx)

                total_frames_local = st["total_frames"]
                completed = frame_idx + 1
                pct = int(max(0, min(100, completed * 100 / max(1, total_frames_local))))
                self.run_progress.configure(value=pct)
                self.progress_pct.configure(text=f"{pct}%")

                remaining_frames = max(0, total_frames_local - completed)
                eta_seconds = int(remaining_frames * (anim_ms / 1000.0))
                minutes = eta_seconds // 60
                seconds = eta_seconds % 60

                if viz_on:
                    initiator_lbl = self._node_id(sr.initiator_idx)
                    ax.set_title(
                        f"Distributed sim — Round {sr.round}  Step {sr.step_in_round}/{sr.round_length}  "
                        f"Event: {sr.event}  Initiator: {initiator_lbl}",
                        color=_tm.GRAPH_AREA_FG,
                        fontsize=max(9, _tm.FONT_PT_BASE),
                    )

                self.summary_eta_lbl.configure(text=f"ETA: {minutes:02d}:{seconds:02d}")
                self.summary_active_lbl.configure(text=f"Active Agents: {n_train}")
                self.summary_round_lbl.configure(text=f"Round: {sr.round}  Step: {sr.step_in_round}/{sr.round_length}")
                self._update_round_badge(f"Round: {sr.round}")

                if frame_idx == 0:
                    self._append_log(
                        "Distributed simulator started (async messages, comm policy, federated round aggregation)."
                    )
                    if viz_on:
                        self._append_log(
                            "Legend: blue=idle, green=initiator, yellow=sender, orange=receiver, "
                            "red=dropout, gray=interrupted, purple=aggregation."
                        )
                    else:
                        self._append_log("Visualization effects disabled — graph highlighting and redraws skipped.")
                    if not str((experiment_state.get("environment") or {}).get("topology_assignment_path", "")).strip():
                        self._append_log(
                            "No topology file path found; generated network from current UI graph settings."
                        )

                log_block = self._format_step_log(sr)
                if log_block:
                    self._append_log(log_block)
                elif frame_idx - st["last_log_frame"] >= 8:
                    self._append_log(sr.line)
                    st["last_log_frame"] = frame_idx

                if viz_on:
                    try:
                        canvas.draw_idle()
                    except Exception:
                        try:
                            canvas.draw()
                        except Exception:
                            pass
                try:
                    self.update_idletasks()
                except Exception:
                    pass

                expected_frame = frame_idx + 1
                processed += 1

            # Continue draining while the window is still active.
            if expected_frame < total_frames and run_id == self._sim_id and not self._stop_requested:
                drain_delay = anim_ms if viz_on else 1
                self._drain_after_id = self.after(drain_delay, _drain)
            else:
                self._drain_after_id = None

        # Kick off UI draining loop.
        self._drain_after_id = self.after(0, _drain)
        canvas.draw()
