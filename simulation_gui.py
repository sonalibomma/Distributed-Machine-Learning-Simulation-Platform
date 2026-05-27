import copy
import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Optional

from experiment_data import (
    GRAPH_TYPES,
    SEED_GRAPH_TYPES,
    DIRECTED_GRAPH_TYPES,
    SELFLOOPS_GRAPH_TYPES,
    POSITION_GRAPH_TYPES,
    default_experiment_state,
    default_profile_state,
    default_model_state,
    default_topology_graph_block,
    default_communication_card,
    default_group_policy_card,
    _resolve_path,
    _profiles_list_from_payload,
    _models_list_from_payload,
    _data_assignment_from_payload,
    _file_kind_from_filename,
)
from run_window import RunWindow
from topology_validate import validate_ui_topology
from topology_graph import effective_topology_for_run
from experiment_runtime import validate_run_policies
from theme import (
    BG_MAIN,
    FONT_PT_BASE,
    PANEL_BLUE,
    PANEL_GREEN,
    GUTTER,
    PANEL_GAP,
    OUTER_PAD,
    LABEL_COL_MIN,
    LABEL_WRAP,
    INPUT_BG,
    INPUT_BORDER,
    TEXT_MAIN,
    MUTED_TEXT,
    ACCENT,
    HEADER_FG,
    VALIDATION_WARN,
    add_tooltip,
)
from theme_manager import (
    AppearanceSession,
    PRESET_ORDER,
    SESSION,
    apply_session,
    ensure_default_applied,
    register_listbox,
    register_notes_text,
    register_surface,
)

# Left sidebar: narrow; center/right get most horizontal space
_SIDEBAR_COL_MINSIZE = 168
_MAIN_COL_WEIGHT = 5
_SIDEBAR_COL_WEIGHT = 1
# Extra inner padding for main content panels (center + right)
_MAIN_PANEL_PAD = GUTTER + 6
# Max height for Rounds/Assignment range rows (nested scroll inside panel scroll)
_RANGE_LIST_SCROLL_HEIGHT = 200
# Minimum viewport height for each panel body canvas (readable; column scroll handles overflow)
_PANEL_BODY_MIN_HEIGHT = 280
_NOTES_PLACEHOLDER = "Write something here..."


def _make_column_scroll(parent, bg: str) -> tuple[ttk.Frame, tk.Canvas, ttk.Scrollbar, tk.Frame]:
    """One vertical scrollbar for an entire main column; inner holds stacked panels."""
    shell = ttk.Frame(parent)
    shell.columnconfigure(0, weight=1)
    shell.rowconfigure(0, weight=1)
    canvas = tk.Canvas(shell, bg=bg, highlightthickness=0)
    vsb = ttk.Scrollbar(shell, orient=tk.VERTICAL, command=canvas.yview)
    canvas.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    inner = tk.Frame(canvas, bg=bg, highlightthickness=0)
    register_surface(inner, "BG_MAIN")
    register_surface(canvas, "BG_MAIN")
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _sync(_e=None):
        canvas.update_idletasks()
        bbox = canvas.bbox("all")
        if bbox:
            canvas.configure(scrollregion=bbox)

    inner.bind("<Configure>", _sync)

    def _on_cv(e):
        if e.width > 1:
            canvas.itemconfig(win_id, width=e.width)
        _sync()

    canvas.bind("<Configure>", _on_cv)
    canvas.configure(yscrollcommand=vsb.set)
    return shell, canvas, vsb, inner


def _make_panel(
    parent,
    title: str,
    *,
    green: bool = False,
    title_wrap: int = 520,
    padding: int | None = None,
    scroll_body: bool = False,
    body_min_height: int | None = None,
    plain_inner: bool = False,
) -> tuple[ttk.Frame, tk.Misc]:
    pad = _MAIN_PANEL_PAD if padding is None else padding
    psty = "PanelGreen.TFrame" if green else "Panel.TFrame"
    outer = ttk.Frame(parent, style=psty, padding=pad)
    hdr_style = "HeaderGreen.TLabel" if green else "HeaderBlue.TLabel"
    hdr = ttk.Label(outer, text=title, style=hdr_style, wraplength=title_wrap, justify=tk.LEFT, anchor="w")
    hdr.pack(fill=tk.X, pady=(0, pad))
    panel_bg = PANEL_GREEN if green else PANEL_BLUE
    inner_plain_sty = "InnerGreen.TFrame" if green else "Inner.TFrame"

    if scroll_body:
        body_host = ttk.Frame(outer, style=inner_plain_sty)
        body_host.pack(fill=tk.BOTH, expand=True)
        if body_min_height is None:
            bmin = _PANEL_BODY_MIN_HEIGHT
        else:
            bmin = body_min_height
        canvas_kw: dict[str, Any] = {"bg": panel_bg, "highlightthickness": 0}
        if bmin > 0:
            canvas_kw["height"] = bmin
        canvas = tk.Canvas(body_host, **canvas_kw)
        setattr(canvas, "_panel_body_scroll", True)
        vsb = ttk.Scrollbar(body_host, orient=tk.VERTICAL, command=canvas.yview)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        body_host.columnconfigure(0, weight=1)
        body_host.rowconfigure(0, weight=1)
        inner = tk.Frame(canvas, bg=panel_bg, highlightthickness=0)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_cfg(_e=None):
            canvas.update_idletasks()
            bbox = canvas.bbox("all")
            if bbox:
                canvas.configure(scrollregion=bbox)

        inner.bind("<Configure>", _on_inner_cfg)

        def _on_canvas_cfg(e):
            if e.width > 1:
                canvas.itemconfig(win_id, width=e.width)
            _on_inner_cfg()

        canvas.bind("<Configure>", _on_canvas_cfg)
        canvas.configure(yscrollcommand=vsb.set)
        pk = "PANEL_GREEN" if green else "PANEL_BLUE"
        register_surface(inner, pk)
        register_surface(canvas, pk)

        def _wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _wheel)
    else:
        content_sty = inner_plain_sty if plain_inner else psty
        inner = ttk.Frame(outer, style=content_sty)
        inner.pack(fill=tk.BOTH, expand=True)
    return outer, inner


def _serialize_range_refs(refs: list[dict[str, Any]]) -> list[list[str]]:
    return [[r["start"].get(), r["end"].get()] for r in refs]


def _range_list_block(
    parent: ttk.Frame,
    title: str,
    *,
    green: bool,
    columns: tuple[str, ...] = ("start", "end"),
    extra_middle: Callable[[ttk.Frame, int], None] | None = None,
    initial_rows: list[list[str]] | None = None,
) -> tuple[ttk.Frame, list[dict[str, Any]], Callable[[list[list[str]]], None]]:
    """Rows of range controls with Add; each row has Remove on its own line (avoids clipping).

    Returns ``holder`` frame, mutable ``row_refs`` (each ref has ``start`` / ``end`` entries and ``_block``),
    and ``set_rows`` to replace all rows from serialized data.
    """
    sty = "Green.TLabel" if green else "TLabel"
    psty = "InnerGreen.TFrame" if green else "Inner.TFrame"
    panel_bg = PANEL_GREEN if green else PANEL_BLUE
    sub_sty = "SubsectionGreen.TLabel" if green else "Subsection.TLabel"
    ttk.Label(parent, text=title, style=sub_sty).pack(anchor="w", pady=(0, 6))

    shell = ttk.Frame(parent, style=psty)
    shell.pack(fill=tk.X)
    canvas = tk.Canvas(
        shell,
        height=_RANGE_LIST_SCROLL_HEIGHT,
        bg=panel_bg,
        highlightthickness=0,
    )
    vsb = ttk.Scrollbar(shell, orient=tk.VERTICAL, command=canvas.yview)
    canvas.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    shell.columnconfigure(0, weight=1)
    shell.rowconfigure(0, weight=1)

    inner = tk.Frame(canvas, bg=panel_bg, highlightthickness=0)
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    holder = ttk.Frame(inner, style=psty)
    holder.pack(fill=tk.X)

    row_refs: list[dict[str, Any]] = []

    def _sync_scroll() -> None:
        canvas.update_idletasks()
        bbox = canvas.bbox("all")
        if bbox:
            canvas.configure(scrollregion=bbox)

    def _on_inner_cfg(_e=None) -> None:
        _sync_scroll()

    inner.bind("<Configure>", _on_inner_cfg)

    def _on_canvas_cfg(e) -> None:
        if e.width > 1:
            canvas.itemconfig(win_id, width=e.width)
        _sync_scroll()

    canvas.bind("<Configure>", _on_canvas_cfg)
    canvas.configure(yscrollcommand=vsb.set)

    def _wheel(e):
        canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        return "break"

    canvas.bind("<MouseWheel>", _wheel)
    inner.bind("<MouseWheel>", _wheel)

    def _bind_tree_wheel(w: tk.Misc) -> None:
        w.bind("<MouseWheel>", _wheel)
        for child in w.winfo_children():
            _bind_tree_wheel(child)

    def _add_row(initial: tuple[str, str] = ("", "")) -> None:
        block = ttk.Frame(holder, style=psty)
        block.pack(fill=tk.X, pady=4)
        fields = ttk.Frame(block, style=psty)
        fields.pack(fill=tk.X)
        ttk.Label(fields, text="Start:", style=sty).grid(row=0, column=0, sticky="w", padx=(0, 4))
        e1 = ttk.Entry(fields, width=9)
        e1.grid(row=0, column=1, sticky="w", padx=(0, 6))
        e1.insert(0, initial[0])
        ttk.Label(fields, text="End:", style=sty).grid(row=0, column=2, sticky="w", padx=(0, 4))
        e2 = ttk.Entry(fields, width=9)
        e2.grid(row=0, column=3, sticky="w", padx=(0, 6))
        e2.insert(0, initial[1])
        col = 4
        if "sampling" in columns and extra_middle is None:
            ttk.Label(fields, text="Sampling:", style=sty).grid(row=0, column=col, sticky="w", padx=(0, 4))
            ttk.Entry(fields, width=11).grid(row=0, column=col + 1, sticky="ew", padx=(0, 0))
            fields.columnconfigure(col + 1, weight=1)
        elif extra_middle:
            extra_middle(fields, len(row_refs))

        btn_row = ttk.Frame(block, style=psty)
        btn_row.pack(fill=tk.X, pady=(4, 0))
        ref: dict[str, Any] = {"start": e1, "end": e2, "_block": block}

        def _drop() -> None:
            block.destroy()
            if ref in row_refs:
                row_refs.remove(ref)
            _sync_scroll()

        ttk.Button(btn_row, text="Remove", style="Small.TButton", command=_drop).pack(side=tk.RIGHT, padx=(8, 0))
        _bind_tree_wheel(block)
        row_refs.append(ref)
        _sync_scroll()

    def set_rows(rows: list[list[str]]) -> None:
        for ref in list(row_refs):
            ref["_block"].destroy()
        row_refs.clear()
        data = rows if rows else [["", ""]]
        for row in data:
            a, b = (list(row) + ["", ""])[:2]
            _add_row((str(a), str(b)))

    rows_seed = initial_rows if initial_rows is not None else [["", ""]]
    if not rows_seed:
        rows_seed = [["", ""]]
    for row in rows_seed:
        a, b = (list(row) + ["", ""])[:2]
        _add_row((str(a), str(b)))

    bf = ttk.Frame(parent, style=psty)
    bf.pack(fill=tk.X, pady=(6, 0))
    ttk.Button(bf, text="Add", style="Small.TButton", command=lambda: _add_row(("", ""))).pack(side=tk.LEFT)
    return holder, row_refs, set_rows


class MainWindow:
    """Primary desktop window (simulation setup and controls)."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Simulation Platform")
        self.root.geometry("1720x980")
        self.root.minsize(1400, 780)
        self.root.configure(bg=BG_MAIN)
        ensure_default_applied()

        self.experiment_name_var = tk.StringVar(value="")
        self._experiments: dict[str, dict[str, Any]] = {}
        self._experiment_order: list[str] = []
        self._current_exp_name: Optional[str] = None
        self._suspend_exp_sync = False
        self._last_exp_file_dir: Optional[Path] = None

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main_container = ttk.Frame(self.root, padding=OUTER_PAD)
        main_container.grid(row=0, column=0, sticky="nsew")
        main_container.columnconfigure(0, weight=_SIDEBAR_COL_WEIGHT, minsize=_SIDEBAR_COL_MINSIZE)
        main_container.columnconfigure(1, weight=_MAIN_COL_WEIGHT, uniform="main_cols")
        main_container.columnconfigure(2, weight=_MAIN_COL_WEIGHT, uniform="main_cols")
        main_container.rowconfigure(0, weight=1)

        bottom = ttk.Frame(self.root, padding=(GUTTER, 8, GUTTER, GUTTER))
        bottom.grid(row=1, column=0, sticky="ew")

        left = ttk.Frame(main_container)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, GUTTER))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        self._col2_shell, self._col2_canvas, self._col2_vsb, self._col2_col_inner = _make_column_scroll(
            main_container, BG_MAIN
        )
        self._col2_shell.grid(row=0, column=1, sticky="nsew", padx=(0, GUTTER))

        self._col3_shell, self._col3_canvas, self._col3_vsb, self._col3_col_inner = _make_column_scroll(
            main_container, BG_MAIN
        )
        self._col3_shell.grid(row=0, column=2, sticky="nsew")

        self._build_experiment_panel(left)

        self._build_environment_panel(self._col2_col_inner)
        self._build_communication_panel(self._col2_col_inner)
        self._build_group_policy_panel(self._col2_col_inner)

        self._build_topology_panel(self._col3_col_inner)
        self._build_profile_assignment_panel(self._col3_col_inner)
        self._build_model_assignment_panel(self._col3_col_inner)
        self._build_data_assignment_panel(self._col3_col_inner)
        self._build_notes_panel(self._col3_col_inner)

        self._setup_column_wheel_scroll()

        for c in range(3):
            bottom.columnconfigure(c, weight=1, uniform="bottom_btns")
        pad_b = 5
        ttk.Button(bottom, text="Settings", command=self._open_settings).grid(row=0, column=0, padx=pad_b, pady=2, sticky="nsew")
        ttk.Button(bottom, text="Save", style="Accent.TButton", command=self._experiment_save_json).grid(
            row=0, column=1, padx=pad_b, pady=2, sticky="nsew"
        )
        ttk.Button(bottom, text="Run", style="Accent.TButton", command=self._open_run_window).grid(
            row=0, column=2, padx=pad_b, pady=2, sticky="nsew"
        )

        self._init_experiment_workspace()

    def _setup_column_wheel_scroll(self) -> None:
        """Scroll column 2/3 when wheel is used outside panel body canvases (headers, gaps, etc.)."""

        def _wheel(event):
            try:
                w = event.widget
                top = w.winfo_toplevel()
            except tk.TclError:
                return
            if top is not self.root:
                return
            p = w
            while p:
                if isinstance(p, tk.Canvas) and getattr(p, "_panel_body_scroll", False):
                    return
                p = getattr(p, "master", None)
            p = w
            while p:
                if p is self._col2_col_inner or p is self._col2_canvas:
                    self._col2_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    return
                if p is self._col3_col_inner or p is self._col3_canvas:
                    self._col3_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    return
                p = getattr(p, "master", None)

        self.root.bind_all("<MouseWheel>", _wheel)

    # --- Left column ---
    def _build_experiment_panel(self, parent):
        outer, inner = _make_panel(
            parent, "Experiment", title_wrap=200, padding=GUTTER, scroll_body=False, plain_inner=True
        )
        outer.grid(row=0, column=0, sticky="nsew")

        search_fr = ttk.Frame(inner, style="Inner.TFrame")
        search_fr.pack(fill=tk.X, pady=(0, GUTTER))
        ttk.Label(search_fr, text="Search:", style="TLabel").pack(anchor="w", pady=(0, 4))
        self.exp_search = ttk.Entry(search_fr)
        self.exp_search.pack(fill=tk.X, expand=True)
        add_tooltip(self.exp_search, "Filter experiments by name or tag.")

        btn_fr = ttk.Frame(inner, style="Inner.TFrame")
        btn_fr.pack(fill=tk.X, pady=(0, GUTTER))
        for i, txt in enumerate(("Upload", "Save")):
            cmd = (self._experiment_upload_json, self._experiment_save_json)[i]
            ttk.Button(btn_fr, text=txt, command=cmd).pack(fill=tk.X, pady=(0, 4 if i < 2 else 0))

        self.exp_listbox = tk.Listbox(
            inner,
            height=10,
            width=20,
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=INPUT_BORDER,
            selectbackground=ACCENT,
            selectforeground=HEADER_FG,
        )
        self.exp_listbox.pack(fill=tk.BOTH, expand=True)
        self.exp_listbox.bind("<<ListboxSelect>>", self._on_experiment_list_select)
        register_listbox(self.exp_listbox)

    def _labeled_entry(self, parent, label: str, row: int, *, green: bool = False, tooltip: str = "") -> ttk.Entry:
        sty = "Green.TLabel" if green else "TLabel"
        parent.columnconfigure(0, weight=0, minsize=LABEL_COL_MIN)
        parent.columnconfigure(1, weight=1)
        lb = ttk.Label(parent, text=label, style=sty, wraplength=LABEL_WRAP, justify=tk.LEFT)
        lb.grid(row=row, column=0, sticky="nw", padx=(0, 12), pady=6)
        e = ttk.Entry(parent)
        e.grid(row=row, column=1, sticky="ew", pady=6)
        if tooltip:
            add_tooltip(lb, tooltip)
            add_tooltip(e, tooltip)
        return e

    # --- Environment ---
    def _build_environment_panel(self, parent):
        outer, inner = _make_panel(
            parent,
            "Environment",
            title_wrap=480,
            scroll_body=True,
            plain_inner=True,
            body_min_height=140,
        )
        outer.pack(fill=tk.X, pady=(0, GUTTER))

        inner.grid_columnconfigure(0, weight=0, minsize=LABEL_COL_MIN)
        inner.grid_columnconfigure(1, weight=1)
        # Do not stretch vertically; scroll area should match content height.
        # (No inner.rowconfigure with weight=1 here.)

        padx = 10
        pady = 5

        ttk.Label(inner, text="Random Seed:", style="TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
            row=0, column=0, sticky="w", padx=(padx, 0), pady=pady
        )
        self.env_seed = ttk.Spinbox(inner, from_=-2**31, to=2**31 - 1, width=14)
        self.env_seed.grid(row=0, column=1, sticky="ew", padx=(0, padx), pady=pady)
        add_tooltip(self.env_seed, "Integer seed for reproducible environment initialization.")

        def labeled_entry(label: str, row: int, tooltip: str) -> ttk.Entry:
            ttk.Label(inner, text=label, style="TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
                row=row, column=0, sticky="w", padx=(padx, 0), pady=pady
            )
            e = ttk.Entry(inner)
            e.grid(row=row, column=1, sticky="ew", padx=(0, padx), pady=pady)
            if tooltip:
                add_tooltip(e, tooltip)
            return e

        self.env_save_path = labeled_entry("Save Path:", 1, "Directory where artifacts are written.")
        self.env_save_name = labeled_entry("Save Name:", 2, "Base file name for outputs.")
        self.env_agent_path = labeled_entry(
            "Agent Assignment Path:", 3, "Path to agent-role assignment configuration."
        )
        self.env_topology_assign_path = labeled_entry(
            "Topology Assignment Path:", 4, "Path to topology assignment configuration."
        )

    # --- Communication ---
    def _fill_communication_tab(self, tab: ttk.Frame, state: dict[str, Any] | None) -> dict[str, Any]:
        tab.columnconfigure(0, weight=0, minsize=LABEL_COL_MIN)
        tab.columnconfigure(1, weight=1)
        w: dict[str, Any] = {}
        r = 0
        keys = (
            "latency_prob",
            "dropout_prob",
            "interruption_prob",
            "latency_min",
            "latency_max",
            "earliest_interruption",
            "latest_interruption",
        )
        for lab, tip, key in (
            ("Latency probability (0–1):", "Chance a message is delayed.", keys[0]),
            ("Dropout probability (0–1):", "Chance a message is dropped.", keys[1]),
            ("Interruption probability (0–1):", "Chance an in-flight message is interrupted.", keys[2]),
            ("Latency minimum:", "Minimum delay (steps or ms).", keys[3]),
            ("Latency maximum:", "Maximum delay.", keys[4]),
            ("Earliest interruption:", "Earliest step an interruption may occur.", keys[5]),
            ("Latest interruption:", "Latest step an interruption may occur.", keys[6]),
        ):
            ttk.Label(tab, text=lab, style="TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
                row=r, column=0, sticky="nw", padx=(0, 10), pady=5
            )
            e = ttk.Entry(tab, width=18)
            e.grid(row=r, column=1, sticky="ew", pady=5)
            add_tooltip(e, tip)
            w[key] = e
            r += 1
        sub = ttk.Frame(tab, style="Inner.TFrame")
        sub.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ar_init = None
        if state is not None and isinstance(state.get("assignment_ranges"), list):
            ar_init = [[str(x) for x in (list(row) + ["", ""])[:2]] for row in state["assignment_ranges"]]
        _h, ar_refs, ar_set = _range_list_block(
            sub,
            "Assignment",
            green=False,
            columns=("start", "end"),
            initial_rows=ar_init,
        )
        w["assignment_range_refs"] = ar_refs
        w["assignment_range_set_rows"] = ar_set
        if state is not None:
            self._apply_communication_widgets(w, state)
        return w

    def _apply_communication_widgets(self, w: dict[str, Any], st: dict[str, Any]) -> None:
        for key in (
            "latency_prob",
            "dropout_prob",
            "interruption_prob",
            "latency_min",
            "latency_max",
            "earliest_interruption",
            "latest_interruption",
        ):
            w[key].delete(0, tk.END)
            w[key].insert(0, str(st.get(key, "")))
        ar = st.get("assignment_ranges")
        if isinstance(ar, list) and w.get("assignment_range_set_rows"):
            rows = [[str(x) for x in (list(row) + ["", ""])[:2]] for row in ar]
            w["assignment_range_set_rows"](rows if rows else [["", ""]])

    def _collect_communication_tab(self, w: dict[str, Any]) -> dict[str, Any]:
        d = {
            "latency_prob": w["latency_prob"].get(),
            "dropout_prob": w["dropout_prob"].get(),
            "interruption_prob": w["interruption_prob"].get(),
            "latency_min": w["latency_min"].get(),
            "latency_max": w["latency_max"].get(),
            "earliest_interruption": w["earliest_interruption"].get(),
            "latest_interruption": w["latest_interruption"].get(),
        }
        if w.get("assignment_range_refs") is not None:
            d["assignment_ranges"] = _serialize_range_refs(w["assignment_range_refs"])
        return d

    def _comm_add_tab(self, state: dict[str, Any] | None = None) -> None:
        n = len(self._comm_tab_states) + 1
        st = state if state is not None else default_communication_card(n)
        title = str(st.get("title", f"Communication {n}"))
        tab = ttk.Frame(self.comm_notebook, style="Inner.TFrame", padding=8)
        self.comm_notebook.add(tab, text=title[:32])
        widgets = self._fill_communication_tab(tab, st)
        self._comm_tab_states.append({"frame": tab, "widgets": widgets, "title": title})
        self.comm_notebook.select(tab)

    def _comm_remove_tab(self) -> None:
        if len(self._comm_tab_states) <= 1:
            messagebox.showinfo("Communication", "At least one communication card is required.")
            return
        try:
            idx = self.comm_notebook.index(self.comm_notebook.select())
        except tk.TclError:
            return
        if 0 <= idx < len(self._comm_tab_states):
            meta = self._comm_tab_states.pop(idx)
            try:
                meta["frame"].destroy()
            except tk.TclError:
                pass
        self.comm_notebook.forget(idx)

    def _rebuild_communication_tabs(self, cards: list[dict[str, Any]]) -> None:
        for meta in list(self._comm_tab_states):
            try:
                meta["frame"].destroy()
            except tk.TclError:
                pass
        self._comm_tab_states.clear()
        while self.comm_notebook.tabs():
            self.comm_notebook.forget(0)
        if not cards:
            self._comm_add_tab(default_communication_card(1))
            return
        for c in cards:
            self._comm_add_tab(c)

    def _build_communication_panel(self, parent):
        outer, inner = _make_panel(
            parent,
            "Communication Assignment",
            title_wrap=480,
            scroll_body=True,
            body_min_height=220,
        )
        outer.pack(fill=tk.X, pady=PANEL_GAP)

        bar = ttk.Frame(inner, style="Inner.TFrame")
        host = ttk.Frame(inner, style="Inner.TFrame")
        bar.pack(fill=tk.X, pady=(0, GUTTER))
        host.pack(fill=tk.BOTH, expand=True)

        self.comm_notebook = ttk.Notebook(host)
        self.comm_notebook.pack(fill=tk.BOTH, expand=True)
        self._comm_tab_states: list[dict[str, Any]] = []

        ttk.Button(bar, text="Add Communication Card", command=self._comm_add_tab).pack(side=tk.LEFT)
        ttk.Button(bar, text="Remove communication tab", style="Small.TButton", command=self._comm_remove_tab).pack(
            side=tk.LEFT, padx=(GUTTER, 0)
        )
        self._comm_add_tab(default_communication_card(1))

    # --- Group Policy Assignment ---
    def _fill_group_policy_tab(self, tab: ttk.Frame, state: dict[str, Any] | None) -> dict[str, Any]:
        w: dict[str, Any] = {}
        r1 = ttk.Frame(tab, style="InnerGreen.TFrame")
        r1.pack(fill=tk.X)
        rounds_init = None
        assign_init = None
        if state is not None:
            if isinstance(state.get("rounds"), list):
                rounds_init = [[str(x) for x in (list(row) + ["", ""])[:2]] for row in state["rounds"]]
            if isinstance(state.get("assignment"), list):
                assign_init = [[str(x) for x in (list(row) + ["", ""])[:2]] for row in state["assignment"]]
        _h1, rr_refs, rr_set = _range_list_block(
            r1,
            "Rounds",
            green=True,
            columns=("start", "end"),
            initial_rows=rounds_init,
        )
        w["rounds_range_refs"] = rr_refs
        w["rounds_set_rows"] = rr_set
        r2 = ttk.Frame(tab, style="InnerGreen.TFrame")
        r2.pack(fill=tk.X, pady=(10, 0))
        _h2, ar_refs, ar_set = _range_list_block(
            r2,
            "Assignment",
            green=True,
            columns=("start", "end"),
            initial_rows=assign_init,
        )
        w["assignment_range_refs"] = ar_refs
        w["assignment_range_set_rows"] = ar_set
        if state is not None:
            self._apply_group_policy_widgets(w, state)
        return w

    def _apply_group_policy_widgets(self, w: dict[str, Any], st: dict[str, Any]) -> None:
        ro = st.get("rounds")
        if isinstance(ro, list) and w.get("rounds_set_rows"):
            rows = [[str(x) for x in (list(row) + ["", ""])[:2]] for row in ro]
            w["rounds_set_rows"](rows if rows else [["", ""]])
        ao = st.get("assignment")
        if isinstance(ao, list) and w.get("assignment_range_set_rows"):
            rows = [[str(x) for x in (list(row) + ["", ""])[:2]] for row in ao]
            w["assignment_range_set_rows"](rows if rows else [["", ""]])

    def _collect_group_policy_tab(self, w: dict[str, Any]) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if w.get("rounds_range_refs") is not None:
            d["rounds"] = _serialize_range_refs(w["rounds_range_refs"])
        if w.get("assignment_range_refs") is not None:
            d["assignment"] = _serialize_range_refs(w["assignment_range_refs"])
        return d

    def _gp_add_tab(self, state: dict[str, Any] | None = None) -> None:
        n = len(self._group_policy_tab_states) + 1
        st = state if state is not None else default_group_policy_card(n)
        title = str(st.get("title", f"Group Policy {n}"))
        tab = ttk.Frame(self.group_policy_notebook, style="InnerGreen.TFrame", padding=8)
        self.group_policy_notebook.add(tab, text=title[:32])
        widgets = self._fill_group_policy_tab(tab, st)
        self._group_policy_tab_states.append({"frame": tab, "widgets": widgets, "title": title})
        self.group_policy_notebook.select(tab)

    def _gp_remove_tab(self) -> None:
        if len(self._group_policy_tab_states) <= 1:
            messagebox.showinfo("Group Policy", "At least one group policy card is required.")
            return
        try:
            idx = self.group_policy_notebook.index(self.group_policy_notebook.select())
        except tk.TclError:
            return
        if 0 <= idx < len(self._group_policy_tab_states):
            meta = self._group_policy_tab_states.pop(idx)
            try:
                meta["frame"].destroy()
            except tk.TclError:
                pass
        self.group_policy_notebook.forget(idx)

    def _rebuild_group_policy_tabs(self, cards: list[dict[str, Any]]) -> None:
        for meta in list(self._group_policy_tab_states):
            try:
                meta["frame"].destroy()
            except tk.TclError:
                pass
        self._group_policy_tab_states.clear()
        while self.group_policy_notebook.tabs():
            self.group_policy_notebook.forget(0)
        if not cards:
            self._gp_add_tab(default_group_policy_card(1))
            return
        for c in cards:
            self._gp_add_tab(c)

    def _build_group_policy_panel(self, parent):
        outer, inner = _make_panel(
            parent,
            "Group Policy Assignment",
            green=True,
            title_wrap=480,
            scroll_body=True,
            body_min_height=220,
        )
        outer.pack(fill=tk.X, pady=PANEL_GAP)

        bar = ttk.Frame(inner, style="InnerGreen.TFrame")
        host = ttk.Frame(inner, style="InnerGreen.TFrame")
        bar.pack(fill=tk.X, pady=(0, GUTTER))
        host.pack(fill=tk.BOTH, expand=True)

        self.group_policy_notebook = ttk.Notebook(host)
        self.group_policy_notebook.pack(fill=tk.BOTH, expand=True)
        self._group_policy_tab_states: list[dict[str, Any]] = []

        ttk.Button(bar, text="Add Group Policy Card", command=self._gp_add_tab).pack(side=tk.LEFT)
        ttk.Button(bar, text="Remove group policy tab", style="Small.TButton", command=self._gp_remove_tab).pack(
            side=tk.LEFT, padx=(GUTTER, 0)
        )
        self._gp_add_tab(default_group_policy_card(1))

    # --- Profile Assignment (stacked cards) ---
    def _build_profile_assignment_panel(self, parent):
        outer, inner = _make_panel(
            parent,
            "Profile Assignment",
            green=True,
            title_wrap=480,
            scroll_body=True,
            body_min_height=220,
        )
        outer.pack(fill=tk.X, pady=PANEL_GAP)

        bar = ttk.Frame(inner, style="InnerGreen.TFrame")
        bar.pack(fill=tk.X, pady=(0, GUTTER))
        ttk.Button(bar, text="Add Profile", command=self._profile_add_tab).pack(side=tk.LEFT)
        ttk.Button(bar, text="Remove profile", style="Small.TButton", command=self._profile_remove_tab).pack(
            side=tk.LEFT, padx=(GUTTER, 0)
        )

        self.profile_stack = ttk.Frame(inner, style="InnerGreen.TFrame")
        self.profile_stack.pack(fill=tk.BOTH, expand=True)
        self.profile_notebook = ttk.Notebook(self.profile_stack)
        self.profile_notebook.pack(fill=tk.BOTH, expand=True)
        self.profile_notebook.bind("<<NotebookTabChanged>>", self._on_profile_notebook_tab)
        self._profile_tab_states: list[dict[str, Any]] = []
        self._profile_active_idx = 0

    def _fill_profile_tab(self, lf: ttk.Frame, state: dict[str, Any] | None) -> dict[str, Any]:
        lf.columnconfigure(0, weight=0, minsize=LABEL_COL_MIN)
        lf.columnconfigure(1, weight=1)
        roles = ("dfl_server", "dfl_client", "aggregator", "custom")
        aggs = ("average", "sum", "max", "weighted_average")
        w: dict[str, Any] = {}

        d0 = ttk.Label(lf, text="Description:", style="Green.TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT)
        d0.grid(row=0, column=0, sticky="nw", padx=(0, 8), pady=2)
        e0 = ttk.Entry(lf, width=36)
        e0.grid(row=0, column=1, sticky="ew", pady=2)
        add_tooltip(d0, "Human-readable label for this agent profile.")
        w["description"] = e0

        r = 1
        lr = ttk.Label(lf, text="Role:", style="Green.TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT)
        lr.grid(row=r, column=0, sticky="nw")
        rc = ttk.Combobox(lf, values=roles, width=32, state="readonly")
        rc.grid(row=r, column=1, sticky="ew", pady=2)
        add_tooltip(rc, "Logical role for this profile (e.g. dfl_server).")
        w["role"] = rc
        r += 1
        la = ttk.Label(lf, text="Aggregation:", style="Green.TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT)
        la.grid(row=r, column=0, sticky="nw")
        ac = ttk.Combobox(lf, values=aggs, width=32, state="readonly")
        ac.grid(row=r, column=1, sticky="ew", pady=2)
        add_tooltip(ac, "Aggregation rule over neighbor updates (e.g. average).")
        w["aggregation"] = ac
        r += 1

        ttk.Label(lf, text="Wait Time:", style="Green.TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
            row=r, column=0, sticky="nw"
        )
        wt = ttk.Spinbox(lf, from_=0, to=10**9, width=16)
        wt.grid(row=r, column=1, sticky="ew", pady=2)
        add_tooltip(wt, "Steps or seconds to wait before acting.")
        w["wait_time"] = wt
        r += 1

        for lab, key, tip in (
            ("Aggregation Min:", "agg_min", "Minimum value before aggregation triggers."),
            ("Freshness Cap:", "freshness_cap", "Maximum staleness allowed for updates."),
            ("Training Time:", "training_time", "Allocated training duration."),
        ):
            ttk.Label(lf, text=lab, style="Green.TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
                row=r, column=0, sticky="nw", pady=2
            )
            e = ttk.Entry(lf, width=16)
            e.grid(row=r, column=1, sticky="ew", pady=2)
            add_tooltip(e, tip)
            w[key] = e
            r += 1

        vt = tk.BooleanVar(value=True)
        ttk.Label(lf, text="Does Train:", style="Green.TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
            row=r, column=0, sticky="nw"
        )
        ttk.Checkbutton(lf, style="Green.TCheckbutton", variable=vt).grid(row=r, column=1, sticky="w")
        w["does_train"] = vt
        r += 1

        ttk.Label(lf, text="Metrics (tokens):", style="Green.TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
            row=r, column=0, sticky="nw"
        )
        mt = tk.Text(
            lf,
            height=3,
            width=40,
            font=("Segoe UI", FONT_PT_BASE),
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=INPUT_BORDER,
        )
        mt.grid(row=r, column=1, sticky="ew", pady=2)
        register_notes_text(mt)
        add_tooltip(mt, "Comma- or newline-separated metric names to track.")
        w["metrics"] = mt
        r += 1

        for lab, key, tip in (
            ("Neighbor Ratio:", "neighbor_ratio", "Fraction of neighbors sampled each step."),
            ("Epochs:", "epochs", "Training epochs."),
            ("Mini-batches:", "minibatches", "Mini-batch count per epoch."),
            ("Release Agent:", "release_agent", "Index or id when releasing."),
            ("Group ID:", "group_id", "Logical group identifier."),
        ):
            ttk.Label(lf, text=lab, style="Green.TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
                row=r, column=0, sticky="nw", pady=2
            )
            e = ttk.Entry(lf, width=16)
            e.grid(row=r, column=1, sticky="ew", pady=2)
            add_tooltip(e, tip)
            w[key] = e
            r += 1

        v_sync = tk.BooleanVar(value=False)
        ttk.Label(lf, text="Is Sync:", style="Green.TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
            row=r, column=0, sticky="nw"
        )
        ttk.Checkbutton(lf, style="Green.TCheckbutton", variable=v_sync).grid(row=r, column=1, sticky="w")
        w["is_sync"] = v_sync
        r += 1
        v_ck = tk.BooleanVar(value=False)
        ttk.Label(lf, text="Checkpoint Enabled:", style="Green.TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
            row=r, column=0, sticky="nw"
        )
        ttk.Checkbutton(lf, style="Green.TCheckbutton", variable=v_ck).grid(row=r, column=1, sticky="w")
        w["checkpoint"] = v_ck
        r += 1

        sub = ttk.Frame(lf, style="InnerGreen.TFrame")
        sub.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ar_init = None
        if state is not None and isinstance(state.get("assignment_ranges"), list):
            ar_init = [[str(x) for x in (list(row) + ["", ""])[:2]] for row in state["assignment_ranges"]]
        _h, ar_refs, ar_set = _range_list_block(
            sub,
            "Assignments (ranges)",
            green=True,
            columns=("start", "end"),
            initial_rows=ar_init,
        )
        w["assignment_range_refs"] = ar_refs
        w["assignment_range_set_rows"] = ar_set

        if state is not None:
            self._apply_profile_widgets(w, state)
        return w

    def _apply_profile_widgets(self, w: dict[str, Any], st: dict[str, Any]) -> None:
        w["description"].delete(0, tk.END)
        w["description"].insert(0, st.get("description", ""))
        w["role"].set(st.get("role", "dfl_server"))
        w["aggregation"].set(st.get("aggregation", "average"))
        w["wait_time"].delete(0, tk.END)
        w["wait_time"].insert(0, str(st.get("wait_time", "0")))
        for k in ("agg_min", "freshness_cap", "training_time", "neighbor_ratio", "epochs", "minibatches", "release_agent", "group_id"):
            w[k].delete(0, tk.END)
            w[k].insert(0, str(st.get(k, "")))
        w["does_train"].set(bool(st.get("does_train", True)))
        w["metrics"].delete("1.0", tk.END)
        w["metrics"].insert("1.0", st.get("metrics", ""))
        w["is_sync"].set(bool(st.get("is_sync", False)))
        w["checkpoint"].set(bool(st.get("checkpoint", False)))
        ar = st.get("assignment_ranges")
        if isinstance(ar, list) and w.get("assignment_range_set_rows"):
            rows = [[str(x) for x in (list(row) + ["", ""])[:2]] for row in ar]
            w["assignment_range_set_rows"](rows if rows else [["", ""]])

    def _collect_profile_tab(self, w: dict[str, Any]) -> dict[str, Any]:
        d = {
            "description": w["description"].get(),
            "role": w["role"].get(),
            "aggregation": w["aggregation"].get(),
            "wait_time": w["wait_time"].get(),
            "agg_min": w["agg_min"].get(),
            "freshness_cap": w["freshness_cap"].get(),
            "training_time": w["training_time"].get(),
            "does_train": w["does_train"].get(),
            "metrics": w["metrics"].get("1.0", "end-1c"),
            "neighbor_ratio": w["neighbor_ratio"].get(),
            "epochs": w["epochs"].get(),
            "minibatches": w["minibatches"].get(),
            "release_agent": w["release_agent"].get(),
            "group_id": w["group_id"].get(),
            "is_sync": w["is_sync"].get(),
            "checkpoint": w["checkpoint"].get(),
        }
        if w.get("assignment_range_refs") is not None:
            d["assignment_ranges"] = _serialize_range_refs(w["assignment_range_refs"])
        return d

    def _on_profile_notebook_tab(self, _event=None) -> None:
        try:
            self._profile_active_idx = self.profile_notebook.index(self.profile_notebook.select())
        except tk.TclError:
            pass

    def _profile_set_active(self, idx: int) -> None:
        if not self._profile_tab_states:
            return
        self._profile_active_idx = max(0, min(idx, len(self._profile_tab_states) - 1))
        try:
            self.profile_notebook.select(self._profile_active_idx)
        except tk.TclError:
            pass

    def _profile_add_tab(self, state: dict[str, Any] | None = None) -> None:
        n = len(self._profile_tab_states) + 1
        st = state if state is not None else default_profile_state(n)
        title = str(st.get("title", f"Profile {n}"))
        tab = ttk.Frame(self.profile_notebook, style="InnerGreen.TFrame", padding=8)
        self.profile_notebook.add(tab, text=title[:32])
        widgets = self._fill_profile_tab(tab, st)
        idx = len(self._profile_tab_states)
        self._profile_tab_states.append({"frame": tab, "widgets": widgets, "title": title})
        self.profile_notebook.select(tab)

    def _profile_remove_tab(self) -> None:
        if len(self._profile_tab_states) <= 1:
            messagebox.showinfo("Profile", "At least one profile is required.")
            return
        try:
            idx = self.profile_notebook.index(self.profile_notebook.select())
        except tk.TclError:
            return
        if 0 <= idx < len(self._profile_tab_states):
            meta = self._profile_tab_states.pop(idx)
            try:
                meta["frame"].destroy()
            except tk.TclError:
                pass
        self.profile_notebook.forget(idx)
        new_len = len(self._profile_tab_states)
        self._profile_active_idx = min(idx, new_len - 1)
        self._profile_set_active(self._profile_active_idx)

    def _rebuild_profile_tabs(self, profiles: list[dict[str, Any]]) -> None:
        for meta in list(self._profile_tab_states):
            try:
                meta["frame"].destroy()
            except tk.TclError:
                pass
        self._profile_tab_states.clear()
        while self.profile_notebook.tabs():
            self.profile_notebook.forget(0)
        if not profiles:
            self._profile_add_tab(default_profile_state(1))
            return
        for p in profiles:
            self._profile_add_tab(p)

    # --- Topology & graph params ---
    def _build_topology_panel(self, parent):
        outer, inner = _make_panel(
            parent, "Topology & Graph", title_wrap=200, padding=GUTTER, scroll_body=True, body_min_height=220
        )
        outer.pack(fill=tk.X, pady=(0, GUTTER))

        inner.columnconfigure(0, weight=1)
        inner.rowconfigure(0, weight=1)
        inner.rowconfigure(1, weight=0)

        form = ttk.Frame(inner, style="Inner.TFrame", padding=(4, 10, 4, 4))
        form.grid(row=0, column=0, sticky="nsew")
        form.columnconfigure(0, weight=0, minsize=LABEL_COL_MIN)
        form.columnconfigure(1, weight=1)

        bf = ttk.Frame(inner, style="Inner.TFrame", padding=(4, 0, 4, 4))
        bf.grid(row=1, column=0, sticky="ew")
        bf.columnconfigure(0, weight=1, uniform="topo_btns")
        bf.columnconfigure(1, weight=1)
        pb = dict(padx=4, pady=4, sticky="nsew")
        ttk.Button(bf, text="Reset to defaults", style="Small.TButton", command=self._topology_reset).grid(
            row=0, column=0, **pb
        )
        ttk.Button(bf, text="Validate / Preview", style="Small.TButton", command=self._topology_validate).grid(
            row=0, column=1, **pb
        )
        ttk.Button(bf, text="Add graph configuration", style="Small.TButton", command=self._topology_add_graph).grid(
            row=1, column=0, **pb
        )
        ttk.Button(bf, text="Remove graph configuration", style="Small.TButton", command=self._topology_remove_graph).grid(
            row=1, column=1, **pb
        )

        self._topology_graph_idx = 0
        self._suspend_topology_graph_events = False

        py = 5
        ttk.Label(form, text="Active graph:", style="TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=(0, py)
        )
        self.topology_graph_combo = ttk.Combobox(form, state="readonly", width=28)
        self.topology_graph_combo.grid(row=0, column=1, sticky="ew", pady=(0, py))
        add_tooltip(self.topology_graph_combo, "Switch between saved graph configurations.")
        self.topology_graph_combo.bind("<<ComboboxSelected>>", self._on_topology_graph_selected)

        ttk.Label(form, text="Graph type:", style="TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(0, py)
        )
        self.graph_type_var = tk.StringVar(value=GRAPH_TYPES[0])
        self.graph_type_combo = ttk.Combobox(
            form,
            textvariable=self.graph_type_var,
            values=GRAPH_TYPES,
            width=30,
            state="readonly",
        )
        self.graph_type_combo.grid(row=1, column=1, sticky="ew", pady=(0, py))
        add_tooltip(self.graph_type_combo, "Generator family for the underlying graph structure.")

        self._seed_label = ttk.Label(form, text="Seed:", style="TLabel")
        self._seed_label.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(0, py))
        self.global_seed_spin = ttk.Spinbox(form, from_=0, to=2**31 - 1, width=16)
        self.global_seed_spin.grid(row=2, column=1, sticky="ew", pady=(0, py))
        add_tooltip(self.global_seed_spin, "Random seed used when this graph type consumes a seed field.")

        ttk.Label(form, text="Graph parameters", style="Subsection.TLabel").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 4)
        )

        self.params_box = ttk.Frame(form, style="Inner.TFrame", padding=(6, 4, 6, 4))
        self.params_box.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        self.params_box.columnconfigure(0, weight=1)

        self.graph_params_container = ttk.Frame(self.params_box, style="Inner.TFrame")
        self.graph_params_container.pack(fill=tk.X)

        self.sbm_fr = ttk.Frame(self.graph_params_container, style="Inner.TFrame")
        ttk.Label(self.sbm_fr, text="SBM p input mode:", style="TLabel").pack(side=tk.LEFT, padx=(0, 8))
        self.sbm_p_mode = tk.StringVar(value="single")
        ttk.Combobox(
            self.sbm_fr,
            textvariable=self.sbm_p_mode,
            values=("single", "matrix"),
            width=10,
            state="readonly",
        ).pack(side=tk.LEFT)
        add_tooltip(self.sbm_fr, "Use scalar p or a full probability matrix for stochastic_block_model.")

        self.dir_fr = ttk.Frame(self.graph_params_container, style="Inner.TFrame")
        self.var_directed = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.dir_fr, text="Directed", variable=self.var_directed, style="Blue.TCheckbutton").pack(
            side=tk.LEFT
        )
        add_tooltip(self.dir_fr, "Whether edges are directed (only for supported generators).")

        self.self_fr = ttk.Frame(self.graph_params_container, style="Inner.TFrame")
        self.var_selfloops = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.self_fr, text="Self-loops", variable=self.var_selfloops, style="Blue.TCheckbutton"
        ).pack(side=tk.LEFT)
        add_tooltip(self.self_fr, "Allow self-loops (stochastic block model).")

        self.pos_fr = ttk.Frame(self.graph_params_container, style="Inner.TFrame")
        self.var_supply_pos = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.pos_fr,
            text="Supply vertex positions (pos)",
            variable=self.var_supply_pos,
            style="Blue.TCheckbutton",
        ).pack(anchor="w")
        self.pos_fields_fr = ttk.Frame(self.pos_fr, style="Inner.TFrame")
        ttk.Label(self.pos_fields_fr, text="pos (file path or CSV text):", style="TLabel").pack(anchor="w")
        ttk.Entry(self.pos_fields_fr).pack(fill=tk.X, pady=(2, 0))
        add_tooltip(self.pos_fields_fr, "Optional explicit coordinates for geometric graphs.")

        self.graph_dyn_inner = ttk.Frame(self.graph_params_container, style="Inner.TFrame")

        self.validation_lbl = ttk.Label(
            form,
            text="Validation: —",
            style="TLabel",
            foreground=VALIDATION_WARN,
            wraplength=520,
            justify=tk.LEFT,
        )
        self.validation_lbl.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(2, 0))

        self.graph_type_combo.bind("<<ComboboxSelected>>", self._on_graph_type_change)
        self.var_supply_pos.trace_add("write", lambda *_a: self._update_topology_visibility())
        self.sbm_p_mode.trace_add("write", lambda *_a: self._on_graph_type_change())
        self._topology_graphs = [default_topology_graph_block()]
        self._topology_graph_idx = 0
        self._topology_load_slot(0)

    def _topology_repack_optional_in_params_box(self):
        """Keep optional controls above dynamic fields; parameter box height follows content only."""
        gt = self.graph_type_var.get()
        for w in (self.sbm_fr, self.dir_fr, self.self_fr, self.pos_fr, self.graph_dyn_inner):
            w.pack_forget()
        if gt == "stochastic_block_model":
            self.sbm_fr.pack(fill=tk.X, pady=(0, 4))
        if gt in DIRECTED_GRAPH_TYPES:
            self.dir_fr.pack(fill=tk.X, pady=(0, 4))
        if gt in SELFLOOPS_GRAPH_TYPES:
            self.self_fr.pack(fill=tk.X, pady=(0, 4))
        if gt in POSITION_GRAPH_TYPES:
            self.pos_fr.pack(fill=tk.X, pady=(0, 4))
        self.graph_dyn_inner.pack(fill=tk.X)

    def _clear(self, frame: ttk.Frame):
        for w in frame.winfo_children():
            w.destroy()

    def _on_graph_type_change(self, _e=None):
        gt = self.graph_type_var.get()
        self._clear(self.graph_dyn_inner)
        self._update_topology_visibility()
        self._populate_graph_fields(self.graph_dyn_inner, gt)

    def _update_topology_visibility(self, *_a):
        gt = self.graph_type_var.get()
        show_seed = gt in SEED_GRAPH_TYPES
        py = 5
        if show_seed:
            self._seed_label.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(0, py))
            self.global_seed_spin.grid(row=2, column=1, sticky="ew", pady=(0, py))
        else:
            self._seed_label.grid_remove()
            self.global_seed_spin.grid_remove()

        show_pos_panel = gt in POSITION_GRAPH_TYPES
        if show_pos_panel and self.var_supply_pos.get():
            self.pos_fields_fr.pack(fill=tk.X, pady=(2, 0))
        else:
            self.pos_fields_fr.pack_forget()

        self._topology_repack_optional_in_params_box()

    def _populate_graph_fields(self, parent: ttk.Frame, gt: str):
        parent.columnconfigure(0, weight=0, minsize=LABEL_COL_MIN)
        parent.columnconfigure(1, weight=1)
        row = 0
        sty = "TLabel"
        lp = (0, 8)
        pr = 4

        def lbl(t: str, tip: str = ""):
            nonlocal row
            lb = ttk.Label(parent, text=t, style=sty, wraplength=0)
            lb.grid(row=row, column=0, sticky="w", padx=lp, pady=pr)
            e = ttk.Entry(parent, width=18)
            e.grid(row=row, column=1, sticky="ew", pady=pr)
            if tip:
                add_tooltip(lb, tip)
                add_tooltip(e, tip)
            row += 1
            return e

        def spin(t: str, tip: str, frm=0, to=10**9):
            nonlocal row
            lb = ttk.Label(parent, text=t, style=sty, wraplength=0)
            lb.grid(row=row, column=0, sticky="w", padx=lp, pady=pr)
            s = ttk.Spinbox(parent, from_=frm, to=to, width=16)
            s.grid(row=row, column=1, sticky="ew", pady=pr)
            add_tooltip(lb, tip)
            add_tooltip(s, tip)
            row += 1
            return s

        defaults_help = "Override default if empty."

        if gt == "er":
            spin("n (int)", "Number of nodes.")
            lbl("p (0–1)", "Edge probability between each pair.")
        elif gt == "ba":
            spin("n", "Number of nodes.")
            spin("m", "Edges to attach at each step.", 1, 10**6)
        elif gt == "ws":
            spin("n", "Number of nodes.")
            spin("k", "Each node joined to k nearest neighbors.")
            lbl("p (0–1)", "Rewiring probability.")
        elif gt in {"complete", "cycle", "path", "star", "wheel", "ladder", "circular_ladder"}:
            spin("n", "Size parameter for this classic graph.")
        elif gt == "hypercube":
            spin("dimension", "Hypercube dimension (preview capped at 6).", 1, 6)
        elif gt == "complete_bipartite":
            spin("m", "Size of first partition.")
            spin("n", "Size of second partition.")
        elif gt == "lollipop":
            spin("m", "Complete graph order.")
            spin("n", "Path length attached.")
        elif gt == "barbell":
            spin("m1", "Clique size (first bell).")
            spin("m2", "Clique size (second bell).")
        elif gt == "grid_2d":
            spin("m", "Rows.")
            spin("n", "Columns.")
        elif gt == "grid":
            e = lbl("dim_sizes (comma-separated)", "Dimensions of the grid, e.g. 3,4,5.")
            e.insert(0, "3,3,3")
        elif gt == "trivial":
            ttk.Label(parent, text="(no parameters)", style=sty, wraplength=0).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=pr
            )
        elif gt == "empty":
            spin("n", "Number of isolated vertices.")
        elif gt == "gnp_random":
            spin("n", "Number of nodes.")
            lbl("p (0–1)", "Edge probability.")
        elif gt in {"dense_gnm_random", "gnm_random"}:
            spin("n", "Number of nodes.")
            spin("m", "Number of edges.")
        elif gt == "random_regular":
            spin("d", "Degree.")
            spin("n", "Number of nodes.")
        elif gt == "random_shell":
            e = lbl("constructor", "Shell sizes / constructor string, e.g. [10,20,10].")
            e.insert(0, "[10,10,10]")
        elif gt in {"random_powerlaw_tree", "random_powerlaw_tree_sequence"}:
            spin("n", "Number of nodes.")
            e = lbl(f"exponent (default 2)", defaults_help)
            e.insert(0, "2")
            e2 = lbl(f"tries (default 100)", defaults_help)
            e2.insert(0, "100")
        elif gt in {"random_geometric", "soft_random_geometric"}:
            spin("n", "Number of nodes.")
            lbl("radius (float)", "Connection radius.")
            e = lbl("dim (default 2)", defaults_help)
            e.insert(0, "2")
            if gt == "soft_random_geometric":
                e3 = lbl("p (default 0.5)", defaults_help)
                e3.insert(0, "0.5")
        elif gt == "random_lobster":
            spin("n", "Number of nodes.")
            lbl("p1 (0–1)", "Probability of attachment edge.")
            lbl("p2 (0–1)", "Probability of leaf edge.")
        elif gt in {"random_interval_graph", "random_tree"}:
            spin("n", "Number of nodes.")
        elif gt == "stochastic_block_model":
            e = lbl("sizes (comma-separated blocks)", "Block sizes as integers.")
            e.insert(0, "10,10,10")
            mode = self.sbm_p_mode.get()
            ttk.Label(parent, text="p (single value or matrix)", style=sty, wraplength=0).grid(
                row=row, column=0, sticky="w", padx=lp, pady=pr
            )
            if mode == "matrix":
                tm = tk.Text(
                    parent,
                    height=4,
                    width=32,
                    font=("Consolas", 10),
                    bg=INPUT_BG,
                    fg=TEXT_MAIN,
                    relief=tk.SOLID,
                    borderwidth=1,
                    highlightthickness=1,
                    highlightbackground=INPUT_BORDER,
                )
                tm.grid(row=row, column=1, sticky="ew", pady=pr)
                tm.insert("1.0", "0.3 0.05\n0.05 0.3")
                add_tooltip(tm, "Row/column aligned probability matrix.")
                register_notes_text(tm)
            else:
                se = ttk.Entry(parent)
                se.grid(row=row, column=1, sticky="ew", pady=pr)
                se.insert(0, "0.1")
                add_tooltip(se, "Scalar probability (if appropriate for block structure).")
            row += 1
        elif gt == "powerlaw_cluster":
            spin("n", "Number of nodes.")
            spin("m", "Edges to attach.")
            lbl("p (0–1)", "Triangle-closing probability.")
        elif gt in {"connected_watts_strogatz", "newman_watts_strogatz"}:
            spin("n", "Number of nodes.")
            spin("k", "Nearest-neighbor ring degree.")
            lbl("p (0–1)", "Rewiring/add-edge probability.")
            e = lbl("tries (default 100)", defaults_help)
            e.insert(0, "100")
        else:
            ttk.Label(parent, text=f"(specialized fields for {gt})", style=sty, wraplength=0).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=pr
            )

    def _topology_slot_from_ui(self) -> dict[str, Any]:
        pe = self._pos_entry_widget()
        return {
            "graph_type": self.graph_type_var.get(),
            "global_seed": self.global_seed_spin.get(),
            "directed": bool(self.var_directed.get()),
            "selfloops": bool(self.var_selfloops.get()),
            "supply_pos": bool(self.var_supply_pos.get()),
            "sbm_mode": self.sbm_p_mode.get(),
            "pos_path": pe.get() if pe else "",
            "param_values": self._collect_topology_param_values(),
            "validation_text": self.validation_lbl.cget("text"),
        }

    def _topology_normalize_graph_block(self, g: dict[str, Any]) -> dict[str, Any]:
        b = default_topology_graph_block()
        for k in b:
            if k not in g:
                continue
            val = g[k]
            if k in ("directed", "selfloops", "supply_pos"):
                b[k] = bool(val)
            elif k == "param_values" and isinstance(val, list):
                b[k] = [str(x) for x in val]
            else:
                b[k] = str(val) if val is not None else ""
        return b

    def _topology_save_current_to_slot(self) -> None:
        if not self._topology_graphs:
            self._topology_graphs = [default_topology_graph_block()]
        idx = max(0, min(self._topology_graph_idx, len(self._topology_graphs) - 1))
        self._topology_graphs[idx] = self._topology_slot_from_ui()

    def _topology_export_state(self) -> dict[str, Any]:
        self._topology_save_current_to_slot()
        graphs = copy.deepcopy(self._topology_graphs)
        idx = max(0, min(self._topology_graph_idx, len(graphs) - 1)) if graphs else 0
        g_active = graphs[idx] if graphs else default_topology_graph_block()
        return {
            "graphs": graphs,
            "active_graph_index": int(self._topology_graph_idx),
            **copy.deepcopy(g_active),
        }

    def _topology_refresh_graph_combo(self) -> None:
        if not hasattr(self, "topology_graph_combo"):
            return
        self._suspend_topology_graph_events = True
        try:
            names = [f"Graph {i + 1}" for i in range(len(self._topology_graphs))]
            self.topology_graph_combo.configure(values=names)
            if self._topology_graph_idx < len(names):
                self.topology_graph_combo.set(names[self._topology_graph_idx])
        finally:
            self._suspend_topology_graph_events = False

    def _topology_load_slot(self, idx: int) -> None:
        if not self._topology_graphs:
            self._topology_graphs = [default_topology_graph_block()]
        idx = max(0, min(idx, len(self._topology_graphs) - 1))
        self._topology_graph_idx = idx
        g = self._topology_graphs[idx]
        self._suspend_topology_graph_events = True
        try:
            self.sbm_p_mode.set(g.get("sbm_mode", "single"))
            self.graph_type_var.set(g.get("graph_type", GRAPH_TYPES[0]))
            self._on_graph_type_change()
            self.global_seed_spin.delete(0, tk.END)
            self.global_seed_spin.insert(0, str(g.get("global_seed", "0")))
            self.var_directed.set(bool(g.get("directed", False)))
            self.var_selfloops.set(bool(g.get("selfloops", False)))
            self.var_supply_pos.set(bool(g.get("supply_pos", False)))
            pe = self._pos_entry_widget()
            if pe:
                pe.delete(0, tk.END)
                pe.insert(0, str(g.get("pos_path", "")))
            self._update_topology_visibility()
            pv = g.get("param_values") or []
            if pv:
                self._apply_topology_param_values(list(pv))
            self.validation_lbl.configure(text=g.get("validation_text", "Validation: —"))
            self._topology_refresh_graph_combo()
        finally:
            self._suspend_topology_graph_events = False

    def _on_topology_graph_selected(self, _e=None) -> None:
        if self._suspend_topology_graph_events:
            return
        sel = self.topology_graph_combo.get()
        try:
            idx = int(sel.split()[-1]) - 1
        except (ValueError, IndexError):
            return
        if idx < 0 or idx >= len(self._topology_graphs):
            return
        if idx == self._topology_graph_idx:
            return
        self._topology_save_current_to_slot()
        self._topology_load_slot(idx)

    def _topology_add_graph(self) -> None:
        self._topology_save_current_to_slot()
        self._topology_graphs.append(default_topology_graph_block())
        self._topology_load_slot(len(self._topology_graphs) - 1)

    def _topology_remove_graph(self) -> None:
        if len(self._topology_graphs) <= 1:
            messagebox.showinfo("Topology", "At least one graph configuration is required.")
            return
        self._topology_save_current_to_slot()
        del self._topology_graphs[self._topology_graph_idx]
        self._topology_graph_idx = min(self._topology_graph_idx, len(self._topology_graphs) - 1)
        self._topology_load_slot(self._topology_graph_idx)

    def _topology_reset(self):
        self._topology_graphs[self._topology_graph_idx] = default_topology_graph_block()
        self._topology_load_slot(self._topology_graph_idx)
        self.validation_lbl.configure(text="Validation: defaults applied (UI only).")

    def _topology_validate(self):
        self._topology_save_current_to_slot()
        tp = self._topology_slot_from_ui()
        _ok, msg = validate_ui_topology(tp)
        self.validation_lbl.configure(text=msg)
        self._topology_save_current_to_slot()

    # --- Experiment persistence, multi-exp switching, JSON I/O ---
    def _init_experiment_workspace(self) -> None:
        self._experiments.clear()
        self._experiment_order.clear()
        self._current_exp_name = None
        self.exp_listbox.delete(0, tk.END)
        self._suspend_exp_sync = True
        self._apply_ui_state(default_experiment_state(""))
        self._suspend_exp_sync = False

    def _display_label_for_key(self, key: str) -> str:
        p = Path(key)
        same_name = sum(1 for k in self._experiments if Path(k).name == p.name)
        if same_name > 1:
            return f"{p.name}  ({p.parent})"
        return p.name

    def _register_experiment_entry(self, key: str, state: dict[str, Any]) -> None:
        self._experiments[key] = state
        if key not in self._experiment_order:
            self._experiment_order.append(key)

    def _refresh_experiment_list(self, *, select_key: Optional[str] = None) -> None:
        self.exp_listbox.delete(0, tk.END)
        for k in self._experiment_order:
            if k in self._experiments:
                self.exp_listbox.insert(tk.END, self._display_label_for_key(k))
        if select_key and select_key in self._experiments:
            try:
                idx = self._experiment_order.index(select_key)
            except ValueError:
                idx = 0
            self.exp_listbox.selection_clear(0, tk.END)
            if self.exp_listbox.size() > 0:
                self.exp_listbox.selection_set(idx)
                self.exp_listbox.see(idx)

    def _on_experiment_list_select(self, _evt=None) -> None:
        if self._suspend_exp_sync:
            return
        sel = self.exp_listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < 0 or idx >= len(self._experiment_order):
            return
        key = self._experiment_order[idx]
        if key not in self._experiments:
            return
        if self._current_exp_name and self._current_exp_name != key:
            self._experiments[self._current_exp_name] = self._collect_ui_state()
        self._current_exp_name = key
        self._suspend_exp_sync = True
        try:
            self._apply_ui_state(copy.deepcopy(self._experiments[key]))
        finally:
            self._suspend_exp_sync = False

    def _merge_payload_into_state(self, dst: dict[str, Any], src: dict[str, Any]) -> None:
        for k, v in src.items():
            if k in ("profiles", "models", "communication_cards", "group_policy_cards") and isinstance(v, list):
                dst[k] = copy.deepcopy(v)
            elif k == "environment" and isinstance(v, dict) and isinstance(dst.get("environment"), dict):
                dst["environment"].update(copy.deepcopy(v))
            elif k == "topology" and isinstance(v, dict) and isinstance(dst.get("topology"), dict):
                dst["topology"].update(copy.deepcopy(v))
            elif k == "data_assignment" and isinstance(v, dict) and isinstance(dst.get("data_assignment"), dict):
                dst["data_assignment"] = copy.deepcopy(v)
            elif k in dst:
                dst[k] = copy.deepcopy(v)
            elif k in ("topology_path", "agent_assignment_path", "topology_file", "agent_file"):
                dst[k] = copy.deepcopy(v)

    def _map_profile_dict_to_gui(self, r: dict[str, Any]) -> dict[str, Any]:
        b = default_profile_state(1)
        b["title"] = str(r.get("title", r.get("id", b["title"])))
        b["description"] = str(r.get("description", r.get("name", r.get("id", ""))))
        if r.get("role") is not None:
            b["role"] = str(r["role"])
        if r.get("aggregation") is not None:
            b["aggregation"] = str(r["aggregation"])
        for k in (
            "wait_time",
            "agg_min",
            "freshness_cap",
            "training_time",
            "neighbor_ratio",
            "epochs",
            "release_agent",
            "group_id",
        ):
            if k in r and r[k] is not None:
                b[k] = str(r[k])
        mb = r.get("minibatches", r.get("mini_batches"))
        if mb is not None:
            b["minibatches"] = str(mb)
        if r.get("metrics") is not None:
            b["metrics"] = str(r["metrics"])
        if "does_train" in r:
            b["does_train"] = bool(r["does_train"])
        if "is_sync" in r:
            b["is_sync"] = bool(r["is_sync"])
        if "checkpoint" in r:
            b["checkpoint"] = bool(r["checkpoint"])
        if isinstance(r.get("assignment_ranges"), list):
            b["assignment_ranges"] = [
                [str(x) for x in (list(row) + ["", ""])[:2]] for row in r["assignment_ranges"]
            ]
        return b

    def _map_model_dict_to_gui(self, r: dict[str, Any]) -> dict[str, Any]:
        b = default_model_state(1)
        b["title"] = str(r.get("title", r.get("id", b["title"])))
        b["description"] = str(r.get("description", ""))
        b["model_type"] = str(r.get("model_type", r.get("type", "")))
        b["optimizer"] = str(r.get("optimizer", ""))
        b["lr"] = str(r.get("lr", r.get("learning_rate", "")))
        b["momentum"] = str(r.get("momentum", ""))
        b["batch_size"] = str(r.get("batch_size", r.get("batchsize", "")))
        b["criterion"] = str(r.get("criterion", ""))
        if isinstance(r.get("assignment_ranges"), list):
            b["assignment_ranges"] = [
                [str(x) for x in (list(row) + ["", ""])[:2]] for row in r["assignment_ranges"]
            ]
        return b

    def _apply_payload_normalization(self, state: dict[str, Any], raw: dict[str, Any]) -> None:
        pl = _profiles_list_from_payload(raw)
        if pl:
            state["profiles"] = [self._map_profile_dict_to_gui(x) for x in pl]
        ml = _models_list_from_payload(raw)
        if ml:
            state["models"] = [self._map_model_dict_to_gui(x) for x in ml]
        da = _data_assignment_from_payload(raw)
        if da is not None:
            state["data_assignment"] = da

    def _resolve_effective_kind(self, path: Path, raw: dict[str, Any]) -> str:
        by_name = _file_kind_from_filename(path.name)
        by_content = self._classify_json_kind(raw)
        if by_name == "experiment":
            return "experiment"
        if by_name == "topology":
            return "topology"
        if by_name == "agent":
            return "agent"
        return by_content

    def _pos_entry_widget(self) -> Optional[ttk.Entry]:
        for w in self.pos_fields_fr.winfo_children():
            if isinstance(w, ttk.Entry):
                return w
        return None

    def _collect_topology_param_values(self) -> list[str]:
        rows: set[int] = set()
        for c in self.graph_dyn_inner.grid_slaves():
            info = c.grid_info()
            if int(info.get("column", -1)) == 1:
                rows.add(int(info.get("row", 0)))
        out: list[str] = []
        for r in sorted(rows):
            w = None
            for c in self.graph_dyn_inner.grid_slaves():
                inf = c.grid_info()
                if int(inf.get("row", -99)) == r and int(inf.get("column", -99)) == 1:
                    w = c
                    break
            if w is None:
                continue
            if isinstance(w, (ttk.Entry, ttk.Spinbox)):
                out.append(w.get())
            elif isinstance(w, tk.Text):
                out.append(w.get("1.0", "end-1c"))
        return out

    def _apply_topology_param_values(self, values: list[str]) -> None:
        idx = 0
        rows = sorted(
            {
                int(c.grid_info().get("row", 0))
                for c in self.graph_dyn_inner.grid_slaves()
                if int(c.grid_info().get("column", -1)) == 1
            }
        )
        for r in rows:
            if idx >= len(values):
                break
            w = None
            for c in self.graph_dyn_inner.grid_slaves():
                inf = c.grid_info()
                if int(inf.get("row", -99)) == r and int(inf.get("column", -99)) == 1:
                    w = c
                    break
            if w is None:
                continue
            val = values[idx]
            idx += 1
            if isinstance(w, (ttk.Entry, ttk.Spinbox)):
                w.delete(0, tk.END)
                w.insert(0, val)
            elif isinstance(w, tk.Text):
                w.delete("1.0", tk.END)
                w.insert("1.0", val)

    def _merge_topology_file_payload(self, topo: dict[str, Any], tj: dict[str, Any]) -> None:
        gt = tj.get("graph_type") or tj.get("generator")
        if gt:
            topo["graph_type"] = str(gt)
        if "global_seed" in tj or "seed" in tj:
            topo["global_seed"] = str(tj.get("global_seed", tj.get("seed", "0")))
        if isinstance(tj.get("param_values"), list):
            topo["param_values"] = [str(x) for x in tj["param_values"]]
        elif isinstance(tj.get("params"), list):
            topo["param_values"] = [str(x) for x in tj["params"]]
        if not isinstance(topo.get("graphs"), list) or not topo["graphs"]:
            topo["graphs"] = [self._topology_normalize_graph_block(topo)]

    def _classify_json_kind(self, data: dict[str, Any]) -> str:
        if isinstance(data.get("environment"), dict):
            return "experiment"
        if any(
            k in data
            for k in (
                "topology_path",
                "topology_file",
                "topology_assignment_path",
                "agent_assignment_path",
                "agent_path",
                "agent_file",
            )
        ):
            return "experiment"
        has_prof = isinstance(data.get("profiles"), list)
        has_models = isinstance(data.get("models"), list)
        topo_inline = isinstance(data.get("topology"), dict)
        topo_top = any(k in data for k in ("graph_type", "generator", "param_values")) or (
            isinstance(data.get("params"), list)
        )
        if topo_inline and (has_prof or has_models):
            return "experiment"
        if topo_top and (has_prof or has_models):
            return "experiment"
        if topo_inline or topo_top:
            return "topology"
        if has_prof or has_models:
            return "agent"
        return "experiment"

    def _snapshot_current_ui_to_store(self) -> None:
        if self._current_exp_name:
            self._experiments[self._current_exp_name] = self._collect_ui_state()

    def _select_and_apply_loaded_experiment(self, key: str) -> None:
        self._current_exp_name = key
        self._refresh_experiment_list(select_key=key)
        self._suspend_exp_sync = True
        try:
            self._apply_ui_state(copy.deepcopy(self._experiments[key]))
        finally:
            self._suspend_exp_sync = False

    def _resolve_linked_files(
        self, state: dict[str, Any], raw: dict[str, Any], base: Path, errs: list[str]
    ) -> None:
        env = state["environment"]
        tp = state["topology"]
        tpath = raw.get("topology_path") or raw.get("topology_file") or raw.get("topology_assignment_path")
        if tpath is None and isinstance(raw.get("environment"), dict):
            tpath = raw["environment"].get("topology_assignment_path")
        apath = raw.get("agent_assignment_path") or raw.get("agent_path") or raw.get("agent_file")
        if apath is None and isinstance(raw.get("environment"), dict):
            apath = raw["environment"].get("agent_assignment_path")
        if tpath:
            s = str(tpath).strip()
            if s:
                rp = _resolve_path(s, base)
                env["topology_assignment_path"] = str(rp)
                if rp.is_file():
                    try:
                        tj = json.loads(rp.read_text(encoding="utf-8"))
                        if isinstance(tj, dict):
                            if isinstance(tj.get("topology"), dict):
                                merge = copy.deepcopy(tj["topology"])
                                tp.update(merge)
                            self._merge_topology_file_payload(tp, tj)
                    except json.JSONDecodeError as e:
                        errs.append(f"Topology file has invalid JSON ({rp}):\n{e}")
                    except OSError as e:
                        errs.append(f"Topology file could not be read ({rp}):\n{e}")
                else:
                    errs.append(f"Topology file not found:\n{rp}")
        if apath:
            s = str(apath).strip()
            if s:
                rp = _resolve_path(s, base)
                env["agent_assignment_path"] = str(rp)
                if rp.is_file():
                    try:
                        aj = json.loads(rp.read_text(encoding="utf-8"))
                        if isinstance(aj, dict):
                            self._apply_payload_normalization(state, aj)
                    except json.JSONDecodeError as e:
                        errs.append(f"Agent assignment file has invalid JSON ({rp}):\n{e}")
                    except OSError as e:
                        errs.append(f"Agent assignment file could not be read ({rp}):\n{e}")
                else:
                    errs.append(f"Agent assignment file not found:\n{rp}")

    def _collect_ui_state(self) -> dict[str, Any]:
        notes_raw = self.notes_text.get("1.0", "end-1c")
        if getattr(self, "_notes_placeholder_active", False) or notes_raw.strip() == _NOTES_PLACEHOLDER:
            notes_raw = ""
        profs: list[dict[str, Any]] = []
        for meta in self._profile_tab_states:
            d = self._collect_profile_tab(meta["widgets"])
            d["title"] = str(meta.get("title", "Profile"))
            profs.append(d)
        mods: list[dict[str, Any]] = []
        for meta in self._model_tab_states:
            d = self._collect_model_tab(meta["widgets"])
            d["title"] = str(meta.get("title", "Model"))
            mods.append(d)
        pe = self._pos_entry_widget()
        label = self.experiment_name_var.get().strip()
        if not label and self._current_exp_name:
            label = Path(self._current_exp_name).name
        comm_cards: list[dict[str, Any]] = []
        for meta in self._comm_tab_states:
            d = self._collect_communication_tab(meta["widgets"])
            d["title"] = str(meta.get("title", "Communication"))
            comm_cards.append(d)
        gp_cards: list[dict[str, Any]] = []
        for meta in self._group_policy_tab_states:
            d = self._collect_group_policy_tab(meta["widgets"])
            d["title"] = str(meta.get("title", "Group Policy"))
            gp_cards.append(d)
        return {
            "name": label,
            "environment": {
                "random_seed": self.env_seed.get(),
                "save_path": self.env_save_path.get(),
                "save_name": self.env_save_name.get(),
                "agent_assignment_path": self.env_agent_path.get(),
                "topology_assignment_path": self.env_topology_assign_path.get(),
            },
            "topology": self._topology_export_state(),
            "notes": notes_raw,
            "profiles": profs,
            "models": mods,
            "data_assignment": self._collect_data_assignment_state(),
            "communication_cards": comm_cards,
            "group_policy_cards": gp_cards,
        }

    def _apply_ui_state(self, st: dict[str, Any]) -> None:
        env = st.get("environment", {})
        self.experiment_name_var.set(st.get("name", ""))

        self.env_seed.delete(0, tk.END)
        self.env_seed.insert(0, str(env.get("random_seed", "0")))
        for w, key in (
            (self.env_save_path, "save_path"),
            (self.env_save_name, "save_name"),
            (self.env_agent_path, "agent_assignment_path"),
            (self.env_topology_assign_path, "topology_assignment_path"),
        ):
            w.delete(0, tk.END)
            w.insert(0, str(env.get(key, "")))

        note = st.get("notes", "")
        self.notes_text.delete("1.0", tk.END)
        if str(note).strip():
            self.notes_text.insert("1.0", note)
            self.notes_text.config(fg=TEXT_MAIN)
            self._notes_placeholder_active = False
        else:
            self.notes_text.insert("1.0", _NOTES_PLACEHOLDER)
            self.notes_text.config(fg=MUTED_TEXT)
            self._notes_placeholder_active = True

        tp = st.get("topology", {})
        if isinstance(tp.get("graphs"), list):
            raw_g = tp["graphs"]
            self._topology_graphs = [self._topology_normalize_graph_block(g) for g in raw_g if isinstance(g, dict)]
        else:
            self._topology_graphs = []
        if not self._topology_graphs:
            self._topology_graphs = [self._topology_normalize_graph_block(tp)]
        ai = tp.get("active_graph_index", 0)
        try:
            want_idx = int(ai)
        except (TypeError, ValueError):
            want_idx = 0
        want_idx = max(0, min(want_idx, len(self._topology_graphs) - 1))
        self._topology_load_slot(want_idx)

        self._apply_data_assignment_state(st.get("data_assignment") or {"training": [], "validation": []})

        self._rebuild_profile_tabs(st.get("profiles") or [default_profile_state(1)])
        self._rebuild_model_tabs(st.get("models") or [default_model_state(1)])
        self._rebuild_communication_tabs(st.get("communication_cards") or [default_communication_card(1)])
        self._rebuild_group_policy_tabs(st.get("group_policy_cards") or [default_group_policy_card(1)])

    def _experiment_upload_json(self) -> None:
        initial = str(self._last_exp_file_dir) if self._last_exp_file_dir else None
        folder = filedialog.askdirectory(title="Load Experiment Folder", initialdir=initial)
        if not folder:
            return
        self._load_experiment_folder(Path(folder))

    def _experiment_save_json(self) -> None:
        self._snapshot_current_ui_to_store()
        base_dir_str = filedialog.askdirectory(
            title="Choose Parent Folder to Save Experiment",
            initialdir=str(self._last_exp_file_dir) if self._last_exp_file_dir else None,
        )
        if not base_dir_str:
            return
        base_dir = Path(base_dir_str)
        try:
            exp_dir = self._next_experiment_dir(base_dir)
        except ValueError as e:
            messagebox.showerror("Save", str(e))
            return

        st = self._collect_ui_state()
        # Keep a stable experiment display name; the folder is the unique storage key.
        st_name = str(st.get("name") or self.experiment_name_var.get().strip() or exp_dir.name)
        st["name"] = st_name

        try:
            exp_dir.mkdir(parents=True, exist_ok=False)
        except OSError as e:
            messagebox.showerror("Save", f"Could not create folder:\n{exp_dir}\n\n{e}")
            return

        # Required structure: topology.json, agent_assignment.json, configuration.json
        try:
            (exp_dir / "topology.json").write_text(json.dumps(st.get("topology") or {}, indent=2, default=str), encoding="utf-8")
            agent_payload = {
                "profiles": st.get("profiles") or [],
                "models": st.get("models") or [],
                "data_assignment": st.get("data_assignment") or {"training": [], "validation": []},
            }
            (exp_dir / "agent_assignment.json").write_text(json.dumps(agent_payload, indent=2, default=str), encoding="utf-8")
            config_payload = {
                "name": st_name,
                "environment": st.get("environment") or default_experiment_state(st_name)["environment"],
                "notes": st.get("notes") or "",
                "communication_cards": st.get("communication_cards") or [],
                "group_policy_cards": st.get("group_policy_cards") or [],
            }
            (exp_dir / "configuration.json").write_text(json.dumps(config_payload, indent=2, default=str), encoding="utf-8")
        except OSError as e:
            messagebox.showerror("Save", f"Could not write experiment files:\n{e}")
            try:
                # Best-effort cleanup; safe if folder empty or partially written.
                for f in exp_dir.glob("*.json"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
                exp_dir.rmdir()
            except Exception:
                pass
            return

        key = str(exp_dir.resolve())
        self._last_exp_file_dir = exp_dir.parent
        self._register_experiment_entry(key, st)
        self._select_and_apply_loaded_experiment(key)
        messagebox.showinfo("Save", f"Saved experiment to\n{exp_dir}")

    def _next_experiment_dir(self, base_dir: Path, prefix: str = "Experiment_") -> Path:
        if not base_dir.exists() or not base_dir.is_dir():
            raise ValueError(f"Base folder does not exist: {base_dir}")
        existing = []
        for p in base_dir.iterdir():
            if not p.is_dir():
                continue
            name = p.name
            if name.startswith(prefix):
                tail = name[len(prefix) :]
                if tail.isdigit():
                    existing.append(int(tail))
        nxt = (max(existing) + 1) if existing else 1
        return base_dir / f"{prefix}{nxt}"

    def _load_experiment_folder(self, folder: Path) -> None:
        self._snapshot_current_ui_to_store()
        if not folder.exists() or not folder.is_dir():
            messagebox.showerror("Upload", f"Experiment folder not found:\n{folder}")
            return

        req = ["topology.json", "agent_assignment.json", "configuration.json"]
        missing = [x for x in req if not (folder / x).is_file()]
        if missing:
            messagebox.showerror(
                "Upload",
                "Missing required files in experiment folder:\n\n"
                + "\n".join(missing)
                + f"\n\nFolder: {folder}",
            )
            return

        def _read_json(p: Path) -> Any:
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in {p.name}:\n{e}") from e
            except OSError as e:
                raise ValueError(f"Could not read {p.name}:\n{e}") from e

        try:
            topo = _read_json(folder / "topology.json")
            agent = _read_json(folder / "agent_assignment.json")
            config = _read_json(folder / "configuration.json")
        except ValueError as e:
            messagebox.showerror("Upload", str(e))
            return

        if not isinstance(config, dict):
            messagebox.showerror("Upload", "configuration.json must be an object.")
            return
        if not isinstance(topo, dict):
            messagebox.showerror("Upload", "topology.json must be an object.")
            return
        if not isinstance(agent, dict):
            messagebox.showerror("Upload", "agent_assignment.json must be an object.")
            return

        name = str(config.get("name") or folder.name)
        merged = default_experiment_state(name)
        merged["name"] = name
        merged["topology"] = topo
        merged["notes"] = str(config.get("notes") or "")

        env = config.get("environment")
        if isinstance(env, dict):
            merged["environment"].update(env)
        merged["communication_cards"] = config.get("communication_cards") or merged["communication_cards"]
        merged["group_policy_cards"] = config.get("group_policy_cards") or merged["group_policy_cards"]

        profs = agent.get("profiles")
        mods = agent.get("models")
        da = agent.get("data_assignment")
        if isinstance(profs, list):
            merged["profiles"] = profs
        if isinstance(mods, list):
            merged["models"] = mods
        if isinstance(da, dict):
            merged["data_assignment"] = da

        # Run-time simulation uses inline topology/profiles/models; clear assignment-path indirections.
        if isinstance(merged.get("environment"), dict):
            merged["environment"]["topology_assignment_path"] = str(merged["environment"].get("topology_assignment_path") or "")
            merged["environment"]["agent_assignment_path"] = str(merged["environment"].get("agent_assignment_path") or "")

        key = str(folder.resolve())
        self._last_exp_file_dir = folder.parent
        self._register_experiment_entry(key, merged)
        self._select_and_apply_loaded_experiment(key)

    def _load_experiment_json_file(self, path: Path) -> None:
        self._snapshot_current_ui_to_store()
        key = str(path.resolve())
        self._last_exp_file_dir = path.parent
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            messagebox.showerror("Open", f"Could not read file:\n{e}")
            return
        try:
            raw_any = json.loads(text)
        except json.JSONDecodeError as e:
            messagebox.showerror("Open", f"Invalid JSON:\n{e}")
            return
        if not isinstance(raw_any, dict):
            messagebox.showerror("Open", "JSON root must be an object.")
            return
        raw: dict[str, Any] = raw_any
        kind = self._resolve_effective_kind(path, raw)
        name = str(raw.get("name", path.stem))
        errs: list[str] = []
        merged = default_experiment_state(name)
        merged["name"] = name

        if kind == "topology":
            if isinstance(raw.get("topology"), dict):
                merged["topology"].update(copy.deepcopy(raw["topology"]))
            else:
                self._merge_topology_file_payload(merged["topology"], raw)
            if isinstance(raw.get("notes"), str):
                merged["notes"] = raw["notes"]
            merged["environment"]["topology_assignment_path"] = key
            self._apply_payload_normalization(merged, raw)
            self._register_experiment_entry(key, merged)
            self._select_and_apply_loaded_experiment(key)
        elif kind == "agent":
            self._merge_payload_into_state(merged, raw)
            self._apply_payload_normalization(merged, raw)
            merged["environment"]["agent_assignment_path"] = key
            self._register_experiment_entry(key, merged)
            self._select_and_apply_loaded_experiment(key)
        else:
            self._merge_payload_into_state(merged, raw)
            self._apply_payload_normalization(merged, raw)
            self._resolve_linked_files(merged, raw, path.parent, errs)
            self._register_experiment_entry(key, merged)
            self._select_and_apply_loaded_experiment(key)

        if errs:
            messagebox.showwarning("Linked files", "\n\n".join(errs))

    # --- Model assignment (stacked cards) ---
    def _build_model_assignment_panel(self, parent):
        outer, inner = _make_panel(
            parent, "Model Assignment", title_wrap=480, scroll_body=True, body_min_height=220
        )
        outer.pack(fill=tk.X, pady=PANEL_GAP)

        bar = ttk.Frame(inner, style="Inner.TFrame")
        bar.pack(fill=tk.X, pady=(0, GUTTER))
        ttk.Button(bar, text="Add Model", command=self._model_add_tab).pack(side=tk.LEFT)
        ttk.Button(bar, text="Remove model", style="Small.TButton", command=self._model_remove_tab).pack(
            side=tk.LEFT, padx=(GUTTER, 0)
        )

        self.model_stack = ttk.Frame(inner, style="Inner.TFrame")
        self.model_stack.pack(fill=tk.BOTH, expand=True)
        self.model_notebook = ttk.Notebook(self.model_stack)
        self.model_notebook.pack(fill=tk.BOTH, expand=True)
        self.model_notebook.bind("<<NotebookTabChanged>>", self._on_model_notebook_tab)
        self._model_tab_states: list[dict[str, Any]] = []
        self._model_active_idx = 0

    def _fill_model_tab(self, lf: ttk.Frame, state: dict[str, Any] | None) -> dict[str, Any]:
        lf.columnconfigure(0, weight=0, minsize=LABEL_COL_MIN)
        lf.columnconfigure(1, weight=1)
        w: dict[str, Any] = {}
        r = 0
        ttk.Label(lf, text="Description:", style="TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
            row=r, column=0, sticky="nw"
        )
        ed = ttk.Entry(lf, width=36)
        ed.grid(row=r, column=1, sticky="ew", pady=2)
        w["description"] = ed
        r += 1
        ttk.Label(lf, text="Model type:", style="TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
            row=r, column=0, sticky="nw"
        )
        mt = ttk.Combobox(lf, values=("", "MNISTNN", "CIFAR_CNN", "ResNet18", "custom"), width=34)
        mt.grid(row=r, column=1, sticky="ew", pady=2)
        w["model_type"] = mt
        r += 1
        ttk.Label(lf, text="Optimizer:", style="TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
            row=r, column=0, sticky="nw"
        )
        op = ttk.Combobox(lf, values=("", "sgd", "adam", "adamw", "rmsprop"), width=34, state="readonly")
        op.grid(row=r, column=1, sticky="ew", pady=2)
        w["optimizer"] = op
        r += 1
        for lab, key, tip in (
            ("Learning rate (float):", "lr", "Step size for weight updates."),
            ("Momentum (float):", "momentum", "SGD momentum coefficient."),
            ("Batch size (int):", "batch_size", "Samples per mini-batch."),
        ):
            ttk.Label(lf, text=lab, style="TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
                row=r, column=0, sticky="nw", pady=2
            )
            e = ttk.Entry(lf, width=18)
            e.grid(row=r, column=1, sticky="ew", pady=2)
            add_tooltip(e, tip)
            w[key] = e
            r += 1
        ttk.Label(lf, text="Criterion:", style="TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
            row=r, column=0, sticky="nw"
        )
        cr = ttk.Combobox(lf, values=("", "cel", "mse", "bce"), width=34, state="readonly")
        cr.grid(row=r, column=1, sticky="ew", pady=2)
        w["criterion"] = cr
        r += 1
        sub = ttk.Frame(lf, style="Inner.TFrame")
        sub.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        mar_init = None
        if state is not None and isinstance(state.get("assignment_ranges"), list):
            mar_init = [[str(x) for x in (list(row) + ["", ""])[:2]] for row in state["assignment_ranges"]]
        _h, mar_refs, mar_set = _range_list_block(
            sub,
            "Assignment",
            green=False,
            columns=("start", "end"),
            initial_rows=mar_init,
        )
        w["assignment_range_refs"] = mar_refs
        w["assignment_range_set_rows"] = mar_set

        if state is not None:
            self._apply_model_widgets(w, state)
        return w

    def _apply_model_widgets(self, w: dict[str, Any], st: dict[str, Any]) -> None:
        w["description"].delete(0, tk.END)
        w["description"].insert(0, st.get("description", ""))
        w["model_type"].set(st.get("model_type", ""))
        w["optimizer"].set(st.get("optimizer", ""))
        for k in ("lr", "momentum", "batch_size"):
            w[k].delete(0, tk.END)
            w[k].insert(0, str(st.get(k, "")))
        w["criterion"].set(st.get("criterion", ""))
        ar = st.get("assignment_ranges")
        if isinstance(ar, list) and w.get("assignment_range_set_rows"):
            rows = [[str(x) for x in (list(row) + ["", ""])[:2]] for row in ar]
            w["assignment_range_set_rows"](rows if rows else [["", ""]])

    def _collect_model_tab(self, w: dict[str, Any]) -> dict[str, Any]:
        d = {
            "description": w["description"].get(),
            "model_type": w["model_type"].get(),
            "optimizer": w["optimizer"].get(),
            "lr": w["lr"].get(),
            "momentum": w["momentum"].get(),
            "batch_size": w["batch_size"].get(),
            "criterion": w["criterion"].get(),
        }
        if w.get("assignment_range_refs") is not None:
            d["assignment_ranges"] = _serialize_range_refs(w["assignment_range_refs"])
        return d

    def _on_model_notebook_tab(self, _event=None) -> None:
        try:
            self._model_active_idx = self.model_notebook.index(self.model_notebook.select())
        except tk.TclError:
            pass

    def _model_set_active(self, idx: int) -> None:
        if not self._model_tab_states:
            return
        self._model_active_idx = max(0, min(idx, len(self._model_tab_states) - 1))
        try:
            self.model_notebook.select(self._model_active_idx)
        except tk.TclError:
            pass

    def _model_add_tab(self, state: dict[str, Any] | None = None) -> None:
        n = len(self._model_tab_states) + 1
        st = state if state is not None else default_model_state(n)
        title = str(st.get("title", f"Model {n}"))
        tab = ttk.Frame(self.model_notebook, style="Inner.TFrame", padding=8)
        self.model_notebook.add(tab, text=title[:32])
        widgets = self._fill_model_tab(tab, st)
        self._model_tab_states.append({"frame": tab, "widgets": widgets, "title": title})
        self.model_notebook.select(tab)

    def _model_remove_tab(self) -> None:
        if len(self._model_tab_states) <= 1:
            messagebox.showinfo("Model", "At least one model configuration is required.")
            return
        try:
            idx = self.model_notebook.index(self.model_notebook.select())
        except tk.TclError:
            return
        if 0 <= idx < len(self._model_tab_states):
            meta = self._model_tab_states.pop(idx)
            try:
                meta["frame"].destroy()
            except tk.TclError:
                pass
        self.model_notebook.forget(idx)
        new_len = len(self._model_tab_states)
        self._model_active_idx = min(idx, new_len - 1)
        self._model_set_active(self._model_active_idx)

    def _rebuild_model_tabs(self, models: list[dict[str, Any]]) -> None:
        for meta in list(self._model_tab_states):
            try:
                meta["frame"].destroy()
            except tk.TclError:
                pass
        self._model_tab_states.clear()
        while self.model_notebook.tabs():
            self.model_notebook.forget(0)
        if not models:
            self._model_add_tab(default_model_state(1))
            return
        for m in models:
            self._model_add_tab(m)

    # --- Data assignment (repeatable entries) ---
    def _data_assignment_range_block(
        self, parent: ttk.Frame, initial_rows: list[list[str]]
    ) -> tuple[list[list[ttk.Entry]], ttk.Frame]:
        sty = "Green.TLabel"
        psty = "InnerGreen.TFrame"
        ttk.Label(parent, text="Assignment", style="SubsectionGreen.TLabel").pack(anchor="w", pady=(0, 6))
        holder = ttk.Frame(parent, style=psty)
        holder.pack(fill=tk.BOTH, expand=True)
        row_entries: list[list[ttk.Entry]] = []

        def _add_row(a: str = "", b: str = "") -> None:
            block = ttk.Frame(holder, style=psty)
            block.pack(fill=tk.X, pady=4)
            fields = ttk.Frame(block, style=psty)
            fields.pack(fill=tk.X)
            ttk.Label(fields, text="Start:", style=sty).grid(row=0, column=0, sticky="w", padx=(0, 4))
            e1 = ttk.Entry(fields, width=9)
            e1.grid(row=0, column=1, sticky="w", padx=(0, 6))
            e1.insert(0, a)
            ttk.Label(fields, text="End:", style=sty).grid(row=0, column=2, sticky="w", padx=(0, 4))
            e2 = ttk.Entry(fields, width=9)
            e2.grid(row=0, column=3, sticky="w", padx=(0, 6))
            e2.insert(0, b)
            pair = [e1, e2]
            row_entries.append(pair)
            btn_row = ttk.Frame(block, style=psty)
            btn_row.pack(fill=tk.X, pady=(4, 0))

            def _drop() -> None:
                block.destroy()
                if pair in row_entries:
                    row_entries.remove(pair)

            ttk.Button(btn_row, text="Remove", style="Small.TButton", command=_drop).pack(side=tk.RIGHT, padx=(8, 0))

        rows = initial_rows if initial_rows else [["", ""]]
        for row in rows:
            a, b = (list(row) + ["", ""])[:2]
            _add_row(str(a), str(b))
        bf = ttk.Frame(holder, style=psty)
        bf.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(bf, text="Add", style="Small.TButton", command=lambda: _add_row()).pack(side=tk.LEFT)
        return row_entries, holder

    def _data_remove_current_entry(self, notebook: ttk.Notebook, bucket: list[dict[str, Any]], label: str) -> None:
        if len(notebook.tabs()) <= 1:
            messagebox.showinfo("Data", f"At least one {label} entry is required.")
            return
        try:
            idx = notebook.index(notebook.select())
        except tk.TclError:
            return
        if 0 <= idx < len(bucket):
            meta = bucket.pop(idx)
            try:
                meta["frame"].destroy()
            except tk.TclError:
                pass
        notebook.forget(idx)

    def _data_create_assignment_entry(
        self, notebook: ttk.Notebook, bucket: list[dict[str, Any]], initial: Optional[dict[str, Any]]
    ) -> None:
        ini = initial or {}
        desc_val = str(ini.get("description", ""))
        samp_raw = ini.get("sampling")
        samp_data: list[list[str]] = []
        if isinstance(samp_raw, list) and samp_raw:
            for row in samp_raw:
                if isinstance(row, (list, tuple)):
                    samp_data.append([str(x) for x in (list(row) + ["", "", ""])[:3]])
                elif isinstance(row, dict):
                    samp_data.append(
                        [
                            str(row.get("start", "")),
                            str(row.get("end", "")),
                            str(row.get("sampling", row.get("sample", ""))),
                        ]
                    )
        if not samp_data:
            samp_data = [["", "", ""]]

        arng = ini.get("assignment_ranges", ini.get("ranges"))
        ar_list: list[list[str]] = []
        if isinstance(arng, list) and arng:
            for row in arng:
                if isinstance(row, (list, tuple)):
                    ar_list.append([str(x) for x in (list(row) + ["", ""])[:2]])
                elif isinstance(row, dict):
                    ar_list.append([str(row.get("start", "")), str(row.get("end", ""))])
        if not ar_list:
            ar_list = [["", ""]]

        tab = ttk.Frame(notebook, style="InnerGreen.TFrame", padding=6)
        ntab = len(notebook.tabs()) + 1
        notebook.add(tab, text=f"Entry {ntab}")
        tab.columnconfigure(0, weight=0, minsize=LABEL_COL_MIN)
        tab.columnconfigure(1, weight=1)
        ttk.Label(tab, text="Description:", style="Green.TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
            row=0, column=0, sticky="nw", padx=(0, 8), pady=2
        )
        desc_e = ttk.Entry(tab, width=40)
        desc_e.grid(row=0, column=1, sticky="ew", pady=2)
        desc_e.insert(0, desc_val)

        r2 = ttk.Frame(tab, style="InnerGreen.TFrame")
        r2.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        slf = ttk.Frame(r2, style="InnerGreen.TFrame")
        slf.pack(fill=tk.X)
        ttk.Label(slf, text="Sampling:", style="SubsectionGreen.TLabel").pack(anchor="w", pady=(0, 4))
        samp_rows = ttk.Frame(slf, style="InnerGreen.TFrame")
        samp_rows.pack(fill=tk.X)
        samp_refs: list[dict[str, Any]] = []

        def _add_samp(a: str = "", b: str = "", c: str = "") -> None:
            rr = ttk.Frame(samp_rows, style="InnerGreen.TFrame")
            rr.pack(fill=tk.X, pady=3)
            top = ttk.Frame(rr, style="InnerGreen.TFrame")
            top.pack(fill=tk.X)
            ttk.Label(top, text="Start:", style="Green.TLabel").pack(side=tk.LEFT)
            e_a = ttk.Entry(top, width=8)
            e_a.pack(side=tk.LEFT, padx=4)
            e_a.insert(0, a)
            ttk.Label(top, text="End:", style="Green.TLabel").pack(side=tk.LEFT, padx=(8, 0))
            e_b = ttk.Entry(top, width=8)
            e_b.pack(side=tk.LEFT, padx=4)
            e_b.insert(0, b)
            ttk.Label(top, text="Sampling:", style="Green.TLabel").pack(side=tk.LEFT, padx=(8, 0))
            e_c = ttk.Entry(top, width=14)
            e_c.pack(side=tk.LEFT, padx=4)
            e_c.insert(0, c)
            brm = ttk.Frame(rr, style="InnerGreen.TFrame")
            brm.pack(fill=tk.X, pady=(4, 0))
            ref = {"start": e_a, "end": e_b, "sampling": e_c, "frame": rr}
            samp_refs.append(ref)

            def _rm() -> None:
                rr.destroy()
                if ref in samp_refs:
                    samp_refs.remove(ref)

            ttk.Button(brm, text="Remove", style="Small.TButton", command=_rm).pack(side=tk.RIGHT)

        bb = ttk.Frame(slf, style="InnerGreen.TFrame")
        bb.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(bb, text="Add sampling row", style="Small.TButton", command=lambda: _add_samp()).pack(
            side=tk.LEFT
        )
        for triplet in samp_data:
            a, b, c = (triplet + ["", "", ""])[:3]
            _add_samp(a, b, c)

        al = ttk.Frame(tab, style="InnerGreen.TFrame")
        al.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        assign_rows, _holder = self._data_assignment_range_block(al, ar_list)

        meta = {
            "frame": tab,
            "description": desc_e,
            "sampling": samp_refs,
            "assign_rows": assign_rows,
        }
        bucket.append(meta)

    def _data_clear_bucket(self, bucket: list[dict[str, Any]]) -> None:
        for m in list(bucket):
            try:
                m["frame"].destroy()
            except tk.TclError:
                pass
        bucket.clear()

    def _data_apply_section_list(self, notebook: ttk.Notebook, bucket: list[dict[str, Any]], rows: Any) -> None:
        self._data_clear_bucket(bucket)
        if isinstance(rows, list) and rows:
            for ini in rows:
                if isinstance(ini, dict):
                    self._data_create_assignment_entry(notebook, bucket, ini)
        if not bucket:
            self._data_create_assignment_entry(notebook, bucket, None)

    def _data_serialize_bucket(self, bucket: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in bucket:
            samp_out: list[list[str]] = []
            for s in m["sampling"]:
                samp_out.append(
                    [
                        s["start"].get(),
                        s["end"].get(),
                        s["sampling"].get(),
                    ]
                )
            ar_out: list[list[str]] = []
            for pair in m["assign_rows"]:
                ar_out.append([pair[0].get(), pair[1].get()])
            out.append(
                {
                    "description": m["description"].get(),
                    "sampling": samp_out,
                    "assignment_ranges": ar_out,
                }
            )
        return out

    def _collect_data_assignment_state(self) -> dict[str, Any]:
        tr = self._data_serialize_bucket(self._data_training_entries)
        va = self._data_serialize_bucket(self._data_validation_entries)
        return {"training": tr, "validation": va}

    def _apply_data_assignment_state(self, da: dict[str, Any]) -> None:
        if not hasattr(self, "_data_train_nb"):
            return
        tr = da.get("training")
        va = da.get("validation")
        if not isinstance(tr, list):
            tr = []
        if not isinstance(va, list):
            va = []
        self._data_apply_section_list(self._data_train_nb, self._data_training_entries, tr)
        self._data_apply_section_list(self._data_val_nb, self._data_validation_entries, va)

    def _build_data_assignment_panel(self, parent):
        outer, inner = _make_panel(parent, "Data Assignment", green=True, title_wrap=480, scroll_body=True)
        outer.pack(fill=tk.X, pady=PANEL_GAP)

        host = ttk.Frame(inner, style="InnerGreen.TFrame")
        host.pack(fill=tk.X)

        self._data_training_entries: list[dict[str, Any]] = []
        self._data_validation_entries: list[dict[str, Any]] = []

        def make_section(title: str, bucket: list[dict[str, Any]], nb_attr: str) -> None:
            sec = ttk.Frame(host, style="InnerGreen.TFrame")
            sec.pack(fill=tk.X, pady=(0, GUTTER))
            ttk.Label(sec, text=title, style="SubsectionGreen.TLabel").pack(anchor="w", pady=(0, 6))
            nb = ttk.Notebook(sec)
            nb.pack(fill=tk.BOTH, expand=True)
            setattr(self, nb_attr, nb)

            def add_entry() -> None:
                self._data_create_assignment_entry(nb, bucket, None)

            def remove_entry() -> None:
                self._data_remove_current_entry(nb, bucket, title)

            bar = ttk.Frame(sec, style="InnerGreen.TFrame")
            bar.pack(fill=tk.X, pady=(0, 6))
            ttk.Button(bar, text=f"Add {title} entry", style="Small.TButton", command=add_entry).pack(side=tk.LEFT)
            ttk.Button(bar, text=f"Remove {title} entry", style="Small.TButton", command=remove_entry).pack(
                side=tk.LEFT, padx=(GUTTER, 0)
            )
            self._data_create_assignment_entry(nb, bucket, None)

        make_section("Training", self._data_training_entries, "_data_train_nb")
        make_section("Validation", self._data_validation_entries, "_data_val_nb")

    def _notes_on_focus_in(self, _event=None) -> None:
        if getattr(self, "_notes_placeholder_active", False):
            self.notes_text.delete("1.0", tk.END)
            self.notes_text.config(fg=TEXT_MAIN)
            self._notes_placeholder_active = False

    def _notes_on_focus_out(self, _event=None) -> None:
        if not self.notes_text.get("1.0", "end-1c").strip():
            self._notes_placeholder_active = True
            self.notes_text.delete("1.0", tk.END)
            self.notes_text.insert("1.0", _NOTES_PLACEHOLDER)
            self.notes_text.config(fg=MUTED_TEXT)

    def _build_notes_panel(self, parent):
        outer, inner = _make_panel(parent, "Notes", green=True, title_wrap=480, scroll_body=True)
        outer.pack(fill=tk.X, pady=PANEL_GAP)

        self.notes_text = tk.Text(
            inner,
            height=14,
            wrap=tk.WORD,
            bg=INPUT_BG,
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=INPUT_BORDER,
            font=("Segoe UI", FONT_PT_BASE),
            fg=MUTED_TEXT,
        )
        self._notes_placeholder_active = True
        self.notes_text.insert("1.0", _NOTES_PLACEHOLDER)
        self.notes_text.bind("<FocusIn>", self._notes_on_focus_in)
        self.notes_text.bind("<FocusOut>", self._notes_on_focus_out)
        self.notes_text.pack(fill=tk.X)
        register_notes_text(self.notes_text)

    def _open_settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.transient(self.root)
        win.resizable(False, False)

        outer = ttk.Frame(win, padding=16)
        outer.pack(fill=tk.BOTH)

        ttk.Label(outer, text="Appearance / Theme", style="Subsection.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        v_preset = tk.StringVar(value=SESSION.preset)

        ttk.Label(outer, text="Theme:", style="TLabel").grid(row=1, column=0, sticky="nw", pady=2)
        ttk.Combobox(
            outer,
            textvariable=v_preset,
            values=list(PRESET_ORDER),
            state="readonly",
            width=32,
        ).grid(row=1, column=1, sticky="ew", pady=2)

        outer.columnconfigure(1, weight=1)

        bf = ttk.Frame(outer)
        bf.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))

        def _apply() -> None:
            ps = v_preset.get()
            if ps not in PRESET_ORDER:
                ps = SESSION.preset
            apply_session(AppearanceSession(preset=ps))
            try:
                self.root.configure(bg=BG_MAIN)
            except tk.TclError:
                pass

        ttk.Button(bf, text="Apply", style="Accent.TButton", command=_apply).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bf, text="Close", command=win.destroy).pack(side=tk.LEFT)

    def _validate_page1_inputs(self, state: dict[str, Any]) -> tuple[bool, str]:
        """
        Strict-but-safe validation for user-provided numeric/probability inputs.
        Returns (ok, message). Empty optional fields are allowed.
        """

        def _s(x: Any) -> str:
            return "" if x is None else str(x).strip()

        def _parse_float(x: Any, label: str) -> float:
            txt = _s(x)
            if not txt:
                raise ValueError(f"{label} must be a number.")
            try:
                return float(txt)
            except Exception:
                raise ValueError(f"{label} must be numeric (got {txt!r}).")

        def _parse_int_like(x: Any, label: str) -> int:
            v = _parse_float(x, label)
            # Allow "3.0" but reject fractional "3.14".
            if abs(v - int(v)) > 1e-9:
                raise ValueError(f"{label} must be an integer (got {txt!r}).")
            return int(v)

        def _parse_range_pair(row: Any, label: str) -> tuple[float | None, float | None]:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                return None, None
            a, b = row[0], row[1]
            sa, sb = _s(a), _s(b)
            if not sa and not sb:
                return None, None
            # If either side is present, both must be valid numbers.
            if not sa or not sb:
                raise ValueError(f"{label} range rows must have both start and end.")
            try:
                fa = float(sa)
                fb = float(sb)
            except Exception:
                raise ValueError(f"{label} range rows must be numeric ({sa!r}, {sb!r}).")
            return fa, fb

        try:
            env = state.get("environment") or {}
            if _s(env.get("random_seed", "") ) == "":
                return False, "Random Seed is required."
            try:
                int(float(_s(env.get("random_seed"))))
            except Exception:
                return False, f"Random Seed must be an integer (got {env.get('random_seed')!r})."

            # --- Communication cards ---
            comm_cards = state.get("communication_cards") or []
            if isinstance(comm_cards, list):
                for i, c in enumerate(comm_cards):
                    if not isinstance(c, dict):
                        continue
                    for key in ("latency_prob", "dropout_prob", "interruption_prob"):
                        v = _s(c.get(key, ""))
                        if not v:
                            continue
                        try:
                            p = float(v)
                        except Exception:
                            return False, f"Communication {i+1}: {key} must be numeric."
                        if not (0.0 <= p <= 1.0):
                            return False, f"Communication {i+1}: {key} must be between 0 and 1."
                    for key in ("latency_min", "latency_max", "earliest_interruption", "latest_interruption"):
                        v = _s(c.get(key, ""))
                        if not v:
                            continue
                        try:
                            float(v)
                        except Exception:
                            return False, f"Communication {i+1}: {key} must be numeric."

                    # assignment_ranges (min/max membership intervals)
                    ar = c.get("assignment_ranges")
                    if isinstance(ar, list):
                        for ri, row in enumerate(ar):
                            try:
                                a, b = _parse_range_pair(row, f"Communication {i+1} assignment")
                            except ValueError as e:
                                return False, str(e)
                            if a is not None and b is not None and a > b:
                                return False, f"Communication {i+1}: assignment range start must be <= end."

            # --- Group policy cards ---
            gp_cards = state.get("group_policy_cards") or []
            if isinstance(gp_cards, list):
                for i, g in enumerate(gp_cards):
                    if not isinstance(g, dict):
                        continue
                    for key in ("rounds", "assignment"):
                        rows = g.get(key)
                        if not isinstance(rows, list):
                            continue
                        for ri, row in enumerate(rows):
                            try:
                                a, b = _parse_range_pair(
                                    row, f"Group Policy {i+1} {key}"
                                )
                            except ValueError as e:
                                return False, str(e)
                            if a is not None and b is not None and a > b:
                                return False, f"Group Policy {i+1}: {key} start must be <= end."

            # --- Profiles ---
            profiles = state.get("profiles") or []
            if isinstance(profiles, list):
                numeric_nonneg = {"wait_time", "agg_min", "freshness_cap", "training_time", "neighbor_ratio", "epochs"}
                int_fields = {"minibatches", "epochs"}
                for i, p in enumerate(profiles):
                    if not isinstance(p, dict):
                        continue
                    for key in numeric_nonneg:
                        v = _s(p.get(key, ""))
                        if not v:
                            continue
                        try:
                            fv = float(v)
                        except Exception:
                            return False, f"Profile {i+1}: {key} must be numeric."
                        if fv < 0:
                            return False, f"Profile {i+1}: {key} must be >= 0."
                    # assignment_ranges start/end
                    ar = p.get("assignment_ranges")
                    if isinstance(ar, list):
                        for row in ar:
                            try:
                                a, b = _parse_range_pair(row, f"Profile {i+1} assignment")
                            except ValueError as e:
                                return False, str(e)
                            if a is not None and b is not None and a > b:
                                return False, f"Profile {i+1}: assignment start must be <= end."

            # --- Models ---
            models = state.get("models") or []
            if isinstance(models, list):
                numeric_nonneg_models = {"lr", "momentum"}
                int_fields_models = {"batch_size"}
                for i, m in enumerate(models):
                    if not isinstance(m, dict):
                        continue
                    for key in numeric_nonneg_models:
                        v = _s(m.get(key, ""))
                        if not v:
                            continue
                        try:
                            fv = float(v)
                        except Exception:
                            return False, f"Model {i+1}: {key} must be numeric."
                        if fv < 0:
                            return False, f"Model {i+1}: {key} must be >= 0."
                    for key in int_fields_models:
                        v = _s(m.get(key, ""))
                        if not v:
                            continue
                        try:
                            fv = float(v)
                        except Exception:
                            return False, f"Model {i+1}: {key} must be numeric."
                        iv = int(fv)
                        if abs(fv - iv) > 1e-9:
                            return False, f"Model {i+1}: {key} must be an integer."
                        if iv < 1:
                            return False, f"Model {i+1}: {key} must be >= 1."

                    ar = m.get("assignment_ranges")
                    if isinstance(ar, list):
                        for row in ar:
                            try:
                                a, b = _parse_range_pair(row, f"Model {i+1} assignment")
                            except ValueError as e:
                                return False, str(e)
                            if a is not None and b is not None and a > b:
                                return False, f"Model {i+1}: assignment start must be <= end."

            return True, ""
        except Exception as e:
            return False, f"Validation error: {e}"

    def _open_run_window(self):
        try:
            state = self._collect_ui_state()
        except (tk.TclError, OSError, ValueError, TypeError) as e:
            messagebox.showerror("Run", f"Could not read current experiment state:\n{e}")
            return
        # Prevent duplicate concurrent runs.
        if getattr(self, "_run_window", None) is not None:
            try:
                if self._run_window.winfo_exists():
                    self._run_window.lift()
                    self._run_window.focus_force()
                    return
            except tk.TclError:
                pass

        # Preflight validation to avoid starting a run with invalid settings.
        topo_eff = effective_topology_for_run(state)
        ok_top, vmsg = validate_ui_topology(topo_eff)
        if not ok_top:
            messagebox.showerror("Run", vmsg)
            return
        ok_pol, pol_warns = validate_run_policies(state)
        if not ok_pol:
            messagebox.showerror("Run", "Policy validation failed:\n" + "\n".join(pol_warns[:12]))
            return
        ok_inp, inp_msg = self._validate_page1_inputs(state)
        if not ok_inp:
            messagebox.showerror("Run", inp_msg)
            return

        name = str(state.get("name") or self.experiment_name_var.get().strip() or "")
        self._run_window = RunWindow(self.root, experiment_name=name, experiment_state=copy.deepcopy(state))

    def run(self):
        self.root.mainloop()


def main():
    desktop = MainWindow()
    desktop.run()


if __name__ == "__main__":
    main()
