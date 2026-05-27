import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.animation as mpl_animation
import networkx as nx
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import queue
import threading

from theme import (
    BG_MAIN,
    BORDER,
    FONT_PT_BASE,
    HEADER_FG,
    INPUT_BG,
    INPUT_BORDER,
    LOG_ERROR,
    LOG_SUCCESS,
    MUTED_TEXT,
    PANEL_BLUE,
    PROGRESS_TROUGH,
    SUMMARY_BG,
    TEXT_MAIN,
)
from theme_manager import subscribe as theme_subscribe, unsubscribe as theme_unsubscribe
from distributed_simulator import DistributedSimulator, total_simulation_frames
from experiment_runtime import (
    summarize_policies_for_run,
    suggested_comm_log_interval_ms,
    validate_run_policies,
)
from topology_graph import build_graph_for_run, effective_topology_for_run
from topology_validate import validate_ui_topology


class RunWindow(tk.Toplevel):
    """Secondary desktop window shown when starting a run."""

    def __init__(self, parent, *, experiment_name: str, experiment_state: dict[str, Any]):
        super().__init__(parent)
        self._experiment_state = experiment_state
        self._graph_anim = None
        self._canvas = None
        self._worker_thread: threading.Thread | None = None
        self._frame_queue: "queue.Queue[tuple[int, Any]]" = queue.Queue()
        self._stop_requested = False
        self._drain_after_id: str | None = None
        self._sim_id = 0
        self.title("Run — Simulation")
        self.geometry("1100x820")
        self.configure(bg=BG_MAIN)
        self.transient(parent)

        import theme as _tinit

        main = ttk.Frame(self, padding=12)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=3)
        main.rowconfigure(3, weight=1)

        hdr_bar = ttk.Frame(main)
        hdr_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self._hdr_title = tk.Label(
            hdr_bar,
            text=f"Experiment Name - {experiment_name}",
            font=("Segoe UI", FONT_PT_BASE + 2, "bold"),
            bg=BG_MAIN,
            fg=HEADER_FG,
        )
        self._hdr_title.pack(anchor="w")

        toolbar = ttk.Frame(main)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        def _tb(txt: str, cmd=None) -> ttk.Button:
            b = ttk.Button(toolbar, text=txt, style="TButton", command=cmd if cmd is not None else (lambda: None))
            b.pack(side=tk.LEFT, padx=(0, 8))
            return b

        _tb("Graph", self._focus_graph_area)
        _tb("Settings")
        _tb("Save As")
        _tb("Delete")
        self._run_btn = _tb("Run", self._restart_simulation)
        self._stop_btn = _tb("Stop", self._stop_animation)

        graph_outer = ttk.Frame(main, style="Panel.TFrame", padding=4)
        graph_outer.grid(row=2, column=0, sticky="nsew")
        graph_outer.columnconfigure(0, weight=1)
        graph_outer.rowconfigure(0, weight=1)

        self.graph_placeholder = tk.Frame(
            graph_outer,
            bg=_tinit.GRAPH_AREA_BG,
            highlightbackground=_tinit.BORDER,
            highlightthickness=2,
        )
        self.graph_placeholder.grid(row=0, column=0, sticky="nsew")

        bottom_nb = ttk.Notebook(main)
        bottom_nb.grid(row=3, column=0, sticky="nsew")

        summary_tab = ttk.Frame(bottom_nb, style="Panel.TFrame", padding=12)
        bottom_nb.add(summary_tab, text="Summary")
        summary_tab.columnconfigure(0, weight=1)
        summary_tab.rowconfigure(0, weight=1)

        sum_box = tk.Frame(
            summary_tab,
            bg=SUMMARY_BG,
            highlightbackground=BORDER,
            highlightthickness=2,
            padx=12,
            pady=12,
        )
        sum_box.grid(row=0, column=0, sticky="nsew")
        self._sum_box = sum_box

        prog_fr = tk.Frame(sum_box, bg=SUMMARY_BG)
        prog_fr.pack(fill=tk.X, pady=(0, 10))
        tk.Label(prog_fr, text="Progress:", bg=SUMMARY_BG, fg=TEXT_MAIN, font=("Segoe UI", FONT_PT_BASE)).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        prog_holder = tk.Frame(prog_fr, bg=SUMMARY_BG, highlightbackground=BORDER, highlightthickness=1)
        prog_holder.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.run_progress = ttk.Progressbar(
            prog_holder, style="Horizontal.TProgressbar", mode="determinate", maximum=100, value=0
        )
        self.run_progress.pack(fill=tk.X, expand=True)
        self.progress_pct = tk.Label(
            prog_holder,
            text="0%",
            bg=PROGRESS_TROUGH,
            font=("Segoe UI", FONT_PT_BASE - 1, "bold"),
            fg=TEXT_MAIN,
        )
        self.progress_pct.place(in_=self.run_progress, relx=0.5, rely=0.5, anchor="center")
        self.progress_pct.lift()

        self.summary_eta_lbl = tk.Label(
            sum_box, text="ETA: —", bg=SUMMARY_BG, fg=MUTED_TEXT, font=("Segoe UI", FONT_PT_BASE), anchor="w"
        )
        self.summary_eta_lbl.pack(fill=tk.X, pady=(0, 6))
        self.summary_active_lbl = tk.Label(
            sum_box,
            text="Active Agents: —",
            bg=SUMMARY_BG,
            fg=LOG_SUCCESS,
            font=("Segoe UI", FONT_PT_BASE),
            anchor="w",
        )
        self.summary_active_lbl.pack(fill=tk.X, pady=(0, 6))
        self.summary_round_lbl = tk.Label(
            sum_box,
            text="Round: —",
            bg=SUMMARY_BG,
            fg=LOG_SUCCESS,
            font=("Segoe UI", FONT_PT_BASE),
            anchor="w",
        )
        self.summary_round_lbl.pack(fill=tk.X, pady=(0, 0))

        logs_tab = ttk.Frame(bottom_nb, style="Panel.TFrame", padding=6)
        bottom_nb.add(logs_tab, text="Logs")
        logs_tab.columnconfigure(0, weight=1)
        logs_tab.rowconfigure(0, weight=1)

        log_frame = tk.Frame(logs_tab, bg=PANEL_BLUE, highlightbackground=BORDER, highlightthickness=2)
        log_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            height=12,
            wrap=tk.WORD,
            bg=INPUT_BG,
            fg=MUTED_TEXT,
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=INPUT_BORDER,
            font=("Consolas", max(8, FONT_PT_BASE - 1)),
            state=tk.DISABLED,
        )
        self.log_text.tag_configure("error", foreground=LOG_ERROR)
        self.log_text.tag_configure("success", foreground=LOG_SUCCESS)
        self.log_text.tag_configure("info", foreground=MUTED_TEXT)
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")

        self._log_frame = log_frame

        self._bottom_nb = bottom_nb
        self._mpl_fig = None
        self._mpl_ax = None
        self._mpl_node_artist = None
        self._mpl_edge_artist = None
        self._graph_theme = self._make_graph_theme_dict()
        theme_subscribe(self._sync_theme)
        self._append_log("Run window opened.")
        self._append_log(summarize_policies_for_run(experiment_state))
        _ok_pol, pol_warns = validate_run_policies(experiment_state)
        for w in pol_warns:
            self._append_log(f"Policy: {w}")
        topo_eff = effective_topology_for_run(experiment_state)
        ok_top, vmsg = validate_ui_topology(topo_eff)
        self._append_log(f"Topology: {vmsg}" if ok_top else f"Topology issue: {vmsg}")
        self._setup_graph_and_summary(experiment_state)
        bottom_nb.select(0)
        self._sync_theme()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _make_graph_theme_dict(self) -> dict[str, str]:
        import theme as t

        return {
            "base_node": t.GRAPH_NODE_BASE,
            "active_node": t.GRAPH_NODE_ACTIVE,
            "comm": t.GRAPH_COMM,
            "edge_base": t.GRAPH_EDGE_BASE,
            "edge_active": t.GRAPH_EDGE_ACTIVE,
        }

    def _sync_theme(self) -> None:
        import theme as t

        try:
            self.configure(bg=t.BG_MAIN)
        except tk.TclError:
            return
        self._hdr_title.configure(bg=t.BG_MAIN, fg=t.HEADER_FG, font=("Segoe UI", t.FONT_PT_BASE + 2, "bold"))
        self.graph_placeholder.configure(bg=t.GRAPH_AREA_BG, highlightbackground=t.BORDER, highlightthickness=2)
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
        self.summary_eta_lbl.configure(fg=t.MUTED_TEXT, font=("Segoe UI", t.FONT_PT_BASE))
        self.summary_active_lbl.configure(fg=t.LOG_SUCCESS, font=("Segoe UI", t.FONT_PT_BASE))
        self.summary_round_lbl.configure(fg=t.LOG_SUCCESS, font=("Segoe UI", t.FONT_PT_BASE))
        self.progress_pct.configure(bg=t.PROGRESS_TROUGH, fg=t.TEXT_MAIN, font=("Segoe UI", t.FONT_PT_BASE - 1, "bold"))
        try:
            self._log_frame.configure(bg=t.PANEL_BLUE, highlightbackground=t.BORDER)
        except tk.TclError:
            pass
        self.log_text.configure(
            bg=t.INPUT_BG,
            fg=t.MUTED_TEXT,
            highlightbackground=t.INPUT_BORDER,
            font=("Consolas", max(8, t.FONT_PT_BASE - 1)),
        )
        self.log_text.tag_configure("error", foreground=t.LOG_ERROR)
        self.log_text.tag_configure("success", foreground=t.LOG_SUCCESS)
        self.log_text.tag_configure("info", foreground=t.MUTED_TEXT)
        self._refresh_mpl_graph_theme(t)

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
                    na.set_facecolor([gt["base_node"]] * n)
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
        except tk.TclError:
            pass

    def _restart_simulation(self) -> None:
        """Restart the graph animation in-place (supports Run → Stop → Run)."""
        self._sim_id += 1
        self._stop_animation()
        # Clear UI first to avoid stale visuals during rebuild.
        self._clear_run_ui()
        try:
            for w in self.graph_placeholder.winfo_children():
                w.destroy()
        except tk.TclError:
            pass
        # Rebuild graph + animation.
        try:
            self._setup_graph_and_summary(self._experiment_state)
            bottom_nb = getattr(self, "_bottom_nb", None)
            if bottom_nb is not None:
                bottom_nb.select(0)
        except Exception as e:
            messagebox.showerror("Run", f"Could not restart simulation:\n{e}")

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        lower = text.lower()
        tag = "info"
        if "error" in lower or "failed" in lower or "missing" in lower:
            tag = "error"
        elif "completed" in lower or "started" in lower or "updated" in lower:
            tag = "success"
        self.log_text.insert(tk.END, text + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _on_close(self) -> None:
        theme_unsubscribe(self._sync_theme)
        # Stop worker thread + drain callback (if any).
        try:
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

        node_list = list(G.nodes())
        node_to_idx = {n: i for i, n in enumerate(node_list)}
        nn = max(len(node_list), 1)
        edge_list = list(G.edges())
        self._graph_edge_count = len(edge_list)
        edge_to_idx = {tuple(sorted((u, v))): i for i, (u, v) in enumerate(edge_list)}

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
        gt = self._graph_theme
        base_node_color = gt["base_node"]
        active_node_color = gt["active_node"]
        comm_node_color = gt["comm"]
        base_edge_color = gt["edge_base"]
        active_edge_color = gt["edge_active"]

        # Draw static artists once; then only mutate attributes per frame.
        edge_artist = nx.draw_networkx_edges(
            G,
            pos,
            ax=ax,
            edge_color=[base_edge_color] * max(1, len(edge_list)),
            width=1.2,
        )
        node_artist = nx.draw_networkx_nodes(
            G,
            pos,
            ax=ax,
            node_color=[base_node_color] * nn,
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

            processed = 0
            import theme as _tm

            while processed < 2:
                try:
                    frame_idx, sr, n_train = self._frame_queue.get_nowait()
                except queue.Empty:
                    break

                # Completion sentinel.
                if frame_idx == -1:
                    try:
                        if isinstance(sr, tuple) and sr and sr[0] == "error":
                            self._append_log(f"Animation worker error: {sr[1]}")
                    except Exception:
                        pass
                    self._drain_after_id = None
                    return

                if frame_idx != expected_frame:
                    # Should not happen (queue preserves order), but be tolerant.
                    expected_frame = frame_idx

                st["frame"] = frame_idx

                gt = self._graph_theme
                base_node_color = gt["base_node"]
                active_node_color = gt["active_node"]
                comm_node_color = gt["comm"]
                base_edge_color = gt["edge_base"]
                active_edge_color = gt["edge_active"]

                # Nodes
                node_colors = [base_node_color] * nn
                node_sizes = [base_node_size] * nn
                if sr.sender_idx is not None and sr.receiver_idx is not None:
                    for idx in (sr.sender_idx, sr.receiver_idx):
                        if 0 <= idx < nn:
                            node_colors[idx] = comm_node_color
                            node_sizes[idx] = int(base_node_size * 1.35)
                    if sr.sender_idx is not None and 0 <= sr.sender_idx < nn:
                        node_colors[sr.sender_idx] = active_node_color
                        node_sizes[sr.sender_idx] = int(base_node_size * 1.55)
                node_artist.set_facecolor(node_colors)
                node_artist.set_sizes(node_sizes)

                # Edges
                if edge_artist is not None and len(edge_list) > 0:
                    edge_colors = [base_edge_color] * len(edge_list)
                    edge_widths = [1.2] * len(edge_list)
                    if sr.edge_highlight is not None:
                        a, b = sr.edge_highlight
                        key = tuple(sorted((node_list[a], node_list[b])))
                        ei = edge_to_idx.get(key)
                        if ei is not None:
                            edge_colors[ei] = active_edge_color
                            edge_widths[ei] = 2.8 if sr.delivered else 2.2
                    edge_artist.set_color(edge_colors)
                    edge_artist.set_linewidth(edge_widths)

                total_frames_local = st["total_frames"]
                pct = int(max(0, min(100, (frame_idx + 1) * 100 / max(1, total_frames_local))))
                self.run_progress.configure(value=pct)
                self.progress_pct.configure(text=f"{pct}%")

                remaining_frames = max(0, total_frames_local - (frame_idx + 1))
                eta_seconds = int(remaining_frames * (anim_ms / 1000.0))
                minutes = eta_seconds // 60
                seconds = eta_seconds % 60

                active_node = (
                    node_list[sr.sender_idx] if sr.sender_idx is not None and sr.sender_idx < nn else None
                )
                ax.set_title(
                    f"Distributed sim — Round {sr.round}  Step {sr.step_in_round}/{sr.round_length}  Initiator: {active_node}",
                    color=_tm.GRAPH_AREA_FG,
                    fontsize=max(9, _tm.FONT_PT_BASE),
                )

                self.summary_eta_lbl.configure(text=f"ETA: {minutes:02d}:{seconds:02d}")
                self.summary_active_lbl.configure(text=f"Active Agents: {n_train}")
                self.summary_round_lbl.configure(text=f"Round: {sr.round}")

                if frame_idx == 0:
                    self._append_log(
                        "Distributed simulator started (async messages, comm policy, federated round aggregation)."
                    )
                    if not str((experiment_state.get("environment") or {}).get("topology_assignment_path", "")).strip():
                        self._append_log(
                            "No topology file path found; generated network from current UI graph settings."
                        )
                if frame_idx - st["last_log_frame"] >= 4:
                    self._append_log(sr.line)
                    st["last_log_frame"] = frame_idx

                expected_frame = frame_idx + 1
                processed += 1

            # Continue draining while the window is still active.
            if expected_frame < total_frames and run_id == self._sim_id and not self._stop_requested:
                self._drain_after_id = self.after(16, _drain)
            else:
                self._drain_after_id = None

        # Kick off UI draining loop.
        self._drain_after_id = self.after(0, _drain)
        canvas.draw()
