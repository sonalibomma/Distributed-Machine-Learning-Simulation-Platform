import copy
import logging
import pprint
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Optional

from experiment_data import (
    GRAPH_TYPES,
    graph_type_canonical,
    graph_type_display_values,
    graph_type_label,
    SEED_GRAPH_TYPES,
    DIRECTED_GRAPH_TYPES,
    SELFLOOPS_GRAPH_TYPES,
    POSITION_GRAPH_TYPES,
    default_experiment_state,
    export_topology_for_save,
    flatten_mapping_for_display,
    default_profile_state,
    default_model_state,
    default_topology_graph_block,
    default_communication_card,
    default_group_policy_card,
    _resolve_path,
    _profiles_list_from_payload,
    _models_list_from_payload,
    _data_assignment_from_payload,
    _communication_cards_from_payload,
    _group_policy_cards_from_payload,
    _file_kind_from_filename,
    _flatten_nested_profile,
    _flatten_nested_model,
    normalize_topology_graph_block,
    normalize_communication_card,
    normalize_group_policy_card,
    extract_param_values_from_topology_block,
    environment_from_configuration,
    COMM_FIELD_ALIASES,
)
from experiment_loader import load_experiment_folder as loader_read_folder, to_gui_experiment_state
from experiment_io import missing_required_files, read_yaml_file, write_experiment_files as io_write_experiment_files
from yaml_stack_sync import YamlStackSnapshot, build_experiment_preview, validate_yaml_stack
from run_config_builder import (
    RunConfiguration,
    RunStackSnapshot,
    build_and_validate_run_configuration,
    build_run_configuration,
    format_run_config_preview,
    validate_run_configuration,
)
from experiment_instance_builder import (
    ExperimentInstance,
    build_experiment_instances,
)
from manifest_export import (
    format_manifest_preview,
    prepare_instances_for_export,
    export_instance_manifests,
)
from orchestrator_adapter import OrchestratorAdapter, format_execution_preview
from command_generation import (
    CommandPreviewResult,
    build_orchestrator_command_from_requests,
    prepare_command_preview,
    prepare_command_preview_legacy,
)
from validation_helpers import (
    PROFILE_FIELD_LABELS,
    profile_field_error,
    model_field_error,
)
from topology_validate import validate_ui_topology
from topology_graph import effective_topology_for_run
from experiment_runtime import validate_run_policies
from theme import (
    BG_MAIN,
    FONT_PT_BASE,
    FONT_FAMILY,
    FONT_MONO,
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
    VALIDATION_SUCCESS,
    VALIDATION_ERROR,
    LIST_SURFACE_BG,
    BORDER,
    BTN_PRIMARY_BG,
    NOTEBOOK_TAB_SELECTED_FG,
    add_tooltip,
)
from theme_manager import (
    AppearanceSession,
    PRESET_ORDER,
    SESSION,
    apply_session,
    ensure_default_applied,
    register_notes_text,
    register_surface,
    start_system_theme_watch,
    subscribe as theme_subscribe,
)
from system_appearance import appearance_label, detect_os_appearance
from app_settings import SETTINGS, apply_simulation_ui_settings, set_execution_mode
from driver_io import (
    DRIVER_FILENAME,
    default_driver_document,
    gui_values_from_document,
    load_driver_yaml,
    merge_gui_into_document,
    print_driver_load_report,
    save_driver_yaml,
    validate_driver_values,
)
from path_resolution import resolve_stack_path_verbose
from permutations_io import (
    PERMUTATIONS_FILENAME,
    PERMUTATION_SECTIONS,
    all_options_for_sections,
    default_permutations_document,
    discover_options_from_reference,
    load_permutations_yaml,
    merge_selections_into_document,
    print_permutations_load_report,
    resolve_permutations_path,
    save_permutations_yaml,
    selections_from_document,
)
from topologies_io import (
    TOPOLOGIES_FILENAME,
    GRAPH_TYPE_PARAM_KEYS,
    block_from_gui,
    canonical_from_yaml_graph_type,
    canonical_to_display,
    default_topology_block,
    default_topologies_document,
    display_to_canonical,
    extra_param_keys,
    format_param_for_display,
    load_topologies_yaml,
    merge_gui_into_document as merge_topologies_gui_into_document,
    print_topologies_load_report,
    resolve_topologies_path,
    save_topologies_yaml,
    topo_page_graph_display_values,
    topology_block,
    topology_names,
    validate_topologies_collection,
)
from assignments_io import (
    ASSIGNMENTS_FILENAME,
    ASSIGNMENT_SECTIONS,
    agent_selection_options,
    default_assignments_document,
    default_new_assignment,
    load_assignments_yaml,
    merge_dropdown_values,
    merge_sections_into_document,
    print_assignments_load_report,
    reference_names_from_definitions,
    resolve_assignments_path,
    save_assignments_yaml,
    section_entries_from_document,
    validate_sections,
)
from definitions_io import (
    DEFINITIONS_FILENAME,
    DEFINITION_SECTIONS,
    block_from_gui_fields,
    default_definitions_document,
    default_new_block,
    format_field_value,
    load_definitions_yaml,
    merge_sections_into_document as merge_definitions_sections_into_document,
    print_definitions_load_report,
    resolve_definitions_path,
    save_definitions_yaml,
    section_entries_from_document as definition_section_entries_from_document,
    section_spec as definition_section_spec,
    split_block_fields,
    validate_sections as validate_definition_sections,
)
from network_io import (
    NETWORK_FILENAME,
    default_network_document,
    default_new_criteria,
    default_new_optimizer,
    format_scalar,
    gui_state_from_document as network_gui_state_from_document,
    load_network_yaml,
    merge_gui_into_document as merge_network_gui_into_document,
    network_document_from_definitions,
    parse_scalar,
    print_network_load_report,
    resolve_network_path,
    save_network_yaml,
    validate_network_state,
)
from execution import ExecutionContext
from run_window import RunWindow
from ui_chrome import (
    BottomActionBar,
    CardGrid,
    PermutationPanel,
    CollapsibleCard,
    card_footer,
    ModernCard,
    NavTabBar,
    PageShell,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
    CARD_GAP,
    mount_card,
    stack_field,
    status_badge,
)

# Extra inner padding for main content panels (center + right)
_MAIN_PANEL_PAD = 10
# Max height for Rounds/Assignment range rows (nested scroll inside panel scroll)
_RANGE_LIST_SCROLL_HEIGHT = 200
_PANEL_BODY_MIN_HEIGHT = 0
_NOTES_PLACEHOLDER = "Write something here..."

# Compact field widths (chars) for short values so they no longer span a full row.
COMPACT_NUM_WIDTH = 10      # numeric / probability fields (lr, p, seed, momentum, …)
COMPACT_NAME_WIDTH = 24     # short names / type strings
COMPACT_COMBO_WIDTH = 22    # dropdowns sized to their expected values

# Definition profile cards — grouped field sections (presentation only).
_DEFN_FIELD_SECTIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "agent_profiles": {
        "General": ("role", "does_train", "is_sync", "checkpoint_enabled"),
        "Training": ("training_time", "epochs", "mini_batches", "neighbor_ratio", "release_agent"),
        "Aggregation": (
            "aggregation",
            "aggregation_minimum",
            "aggregation_maximum",
            "freshness_cap",
            "wait_time",
        ),
        "Advanced": ("metrics",),
    },
    "models": {
        "General": ("model_type", "batch_size"),
        "Network": ("architecture", "optimizer", "criterion"),
    },
}

_LOAD_LOGGER = logging.getLogger("simulation_gui.experiment_load")


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
) -> tuple[tk.Misc, tk.Misc]:
    pad = _MAIN_PANEL_PAD if padding is None else padding
    card = ModernCard(parent, title, padding=pad)
    panel_bg = PANEL_GREEN if green else PANEL_BLUE
    inner_plain_sty = "InnerGreen.TFrame" if green else "Inner.TFrame"

    if scroll_body:
        body_host = ttk.Frame(card.content, style=inner_plain_sty)
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
        inner = card.content
    return card.outer, inner


def _panel_grid(grid: CardGrid, title: str, **kwargs: Any) -> tuple[tk.Misc, tk.Misc]:
    """Create a card and place it in the next grid cell."""
    outer, inner = _make_panel(grid.frame, title, plain_inner=True, **kwargs)
    grid.attach(outer)
    return outer, inner


def _column_card(parent, title: str, **kwargs: Any) -> tuple[tk.Misc, tk.Misc]:
    """Stack a dashboard card vertically inside a 3-column layout cell."""
    return mount_card(parent, title, **kwargs)


def _driver_grid_card(parent: tk.Misc, title: str, row: int) -> tuple[tk.Misc, tk.Misc]:
    """Driver tab: grid-stacked card (natural height, top-aligned column)."""
    card = ModernCard(parent, title)
    card.outer.grid(row=row, column=0, sticky="new", pady=(0, CARD_GAP))
    parent.columnconfigure(0, weight=1)
    return card.outer, card.body


def _mount_panel(outer: tk.Misc, grid: CardGrid | None) -> None:
    if grid is not None:
        grid.attach(outer)
    else:
        outer.pack(fill=tk.X, pady=(0, SPACE_LG))


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
    import theme as _t_range

    sty = "Green.TLabel" if green else "TLabel"
    psty = "InnerGreen.TFrame" if green else "Inner.TFrame"
    panel_bg = _t_range.LIST_SURFACE_BG
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
    setattr(canvas, "_range_list_scroll", True)
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
        theme_subscribe(self._sync_root_theme)
        start_system_theme_watch(self.root)

        self.experiment_name_var = tk.StringVar(value="")
        self._experiments: dict[str, dict[str, Any]] = {}
        self._experiment_order: list[str] = []
        self._current_exp_name: Optional[str] = None
        self._suspend_exp_sync = False
        self._last_exp_file_dir: Optional[Path] = None
        self._load_field_trace: list[str] = []
        self._driver_file_path: Optional[Path] = None
        self._driver_document: dict[str, Any] = default_driver_document()
        self._driver_fields: dict[str, Any] = {}
        self._perm_file_path: Optional[Path] = None
        self._perm_document: dict[str, Any] = default_permutations_document()
        self._perm_all_options: dict[str, list[str]] = {sec["key"]: [] for sec in PERMUTATION_SECTIONS}
        self._perm_checkbox_vars: dict[str, dict[str, tk.BooleanVar]] = {}
        self._perm_section_bodies: dict[str, ttk.Frame] = {}
        self._topo_file_path: Optional[Path] = None
        self._topo_document: dict[str, Any] = default_topologies_document()
        self._topo_cards: list[dict[str, Any]] = []
        self._topo_card_seq = 0
        self._assign_file_path: Optional[Path] = None
        self._assign_document: dict[str, Any] = default_assignments_document()
        self._assign_section_hosts: dict[str, ttk.Frame] = {}
        self._assign_cards: dict[str, list[dict[str, Any]]] = {sec["key"]: [] for sec in ASSIGNMENT_SECTIONS}
        self._assign_card_seq = 0
        self._defn_file_path: Optional[Path] = None
        self._defn_document: dict[str, Any] = default_definitions_document()
        self._defn_section_hosts: dict[str, ttk.Frame] = {}
        self._defn_section_bodies: dict[str, ttk.Frame] = {}
        self._defn_section_collapsed: dict[str, tk.BooleanVar] = {}
        self._defn_cards: dict[str, list[dict[str, Any]]] = {sec["key"]: [] for sec in DEFINITION_SECTIONS}
        self._defn_card_seq = 0
        self._net_file_path: Optional[Path] = None
        self._net_document: dict[str, Any] = default_network_document()
        self._net_optimizers_host: Optional[ttk.Frame] = None
        self._net_criteria_host: Optional[ttk.Frame] = None
        self._net_optimizer_cards: list[dict[str, Any]] = []
        self._net_criteria_cards: list[dict[str, Any]] = []
        self._net_card_seq = 0
        self._yaml_stack_sync_active = False
        self._run_configuration: RunConfiguration | None = None
        self._experiment_instances: list[ExperimentInstance] = []
        self._experiment_instance_index = 0
        self._experiment_instances_active = False
        self._manifest_export_dir: Path | None = None
        self._orchestrator_adapter: OrchestratorAdapter | None = None
        self._generated_command: str = ""
        self._command_preview_result: CommandPreviewResult | None = None
        self._run_window: RunWindow | None = None
        self._main_tab_index = -1
        self._pages_hydrated: set[int] = set()
        self._sync_dashboard_pending = False
        self._batch_stack_refresh = False
        self._perm_rebuild_active = False
        self._run_config_refresh_after_id: str | None = None
        self._assign_dropdown_cache: dict[int, tuple[str, ...]] = {}

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)

        main_container = ttk.Frame(self.root, padding=OUTER_PAD)
        main_container.grid(row=0, column=0, sticky="nsew")
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(1, weight=1)

        nav_row = tk.Frame(main_container, bg=LIST_SURFACE_BG, highlightthickness=0)
        nav_row.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_SM))
        nav_row.columnconfigure(0, weight=1)

        self._page_shell = PageShell(main_container, row=1, column=0)
        driver_page = self._page_shell.add_page()
        permutations_page = self._page_shell.add_page()
        topologies_page = self._page_shell.add_page()
        assignments_page = self._page_shell.add_page()
        definitions_page = self._page_shell.add_page()
        network_page = self._page_shell.add_page()
        experiment_page = self._page_shell.add_page()

        self._pill_tab_bar = NavTabBar(
            nav_row,
            ["Driver", "Permutations", "Topologies", "Assignments", "Definitions", "Network", "Experiment"],
            on_select=self._select_main_tab,
        )
        self._pill_tab_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._nav_actions = ttk.Frame(nav_row, style="TFrame")
        self._nav_actions.pack(side=tk.RIGHT, padx=(SPACE_SM, 0))

        self._nav_driver_upload = ttk.Button(
            self._nav_actions, text="Upload Driver", style="Secondary.TButton", command=self._driver_upload
        )
        self._nav_driver_save = ttk.Button(
            self._nav_actions, text="Save Driver", style="Secondary.TButton", command=self._driver_save
        )
        self._driver_path_lbl = ttk.Label(self._nav_actions, text="", style="Muted.TLabel")

        self._nav_perm_upload = ttk.Button(
            self._nav_actions, text="Upload", style="Secondary.TButton", command=self._perm_upload
        )
        self._nav_perm_save = ttk.Button(
            self._nav_actions, text="Save Permutations", style="Secondary.TButton", command=self._perm_save
        )
        self._perm_path_lbl = ttk.Label(self._nav_actions, text="", style="Muted.TLabel")

        self._nav_topo_save = ttk.Button(
            self._nav_actions, text="Save Topologies", style="Secondary.TButton", command=self._topo_save
        )
        self._nav_topo_add = ttk.Button(
            self._nav_actions, text="Add Topology", style="Secondary.TButton", command=self._topo_add
        )
        self._topo_path_lbl = ttk.Label(
            self._nav_actions, text="No topologies.yaml loaded", style="Muted.TLabel"
        )

        self._nav_assign_save = ttk.Button(
            self._nav_actions, text="Save Assignments", style="Secondary.TButton", command=self._assign_save
        )
        self._assign_path_lbl = ttk.Label(
            self._nav_actions, text="No assignments.yaml loaded", style="Muted.TLabel"
        )

        self._nav_defn_save = ttk.Button(
            self._nav_actions, text="Save Definitions", style="Secondary.TButton", command=self._defn_save
        )
        self._defn_path_lbl = ttk.Label(
            self._nav_actions, text="No definitions.yaml loaded", style="Muted.TLabel"
        )

        self._nav_net_save = ttk.Button(
            self._nav_actions, text="Save Network", style="Secondary.TButton", command=self._net_save
        )
        self._net_path_lbl = ttk.Label(
            self._nav_actions,
            text="Optimizers and criteria are loaded from definitions.yaml",
            style="Muted.TLabel",
        )

        self._nav_tab_widgets: list[list[tk.Misc]] = [
            [self._nav_driver_upload, self._nav_driver_save, self._driver_path_lbl],
            [self._nav_perm_upload, self._nav_perm_save, self._perm_path_lbl],
            [self._nav_topo_save, self._nav_topo_add, self._topo_path_lbl],
            [self._nav_assign_save, self._assign_path_lbl],
            [self._nav_defn_save, self._defn_path_lbl],
            [self._nav_net_save, self._net_path_lbl],
            [],
        ]

        BottomActionBar(
            self.root,
            on_settings=self._open_settings,
            on_save=self._project_save,
            on_run=self._on_run_clicked,
        ).grid(row=1, column=0, sticky="ew")

        self._driver_fields = {}
        self._build_driver_page(driver_page)
        self._build_permutations_page(permutations_page)
        self._build_topologies_page(topologies_page)
        self._build_assignments_page(assignments_page)
        self._build_definitions_page(definitions_page)
        self._build_network_page(network_page)
        self._build_experiment_page(experiment_page)

        self._setup_page_wheel_scroll()
        self._select_main_tab(0)

        self._init_experiment_workspace()
        self._sync_dashboard()

    def _set_execution_preview_text(self, text: str) -> None:
        if not hasattr(self, "_execution_preview"):
            return
        try:
            self._execution_preview.configure(state=tk.NORMAL)
            self._execution_preview.delete("1.0", tk.END)
            self._execution_preview.insert("1.0", text)
            self._execution_preview.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _set_command_preview_text(self, text: str) -> None:
        if not hasattr(self, "_command_preview"):
            return
        try:
            self._command_preview.configure(state=tk.NORMAL)
            self._command_preview.delete("1.0", tk.END)
            self._command_preview.insert("1.0", text)
            self._command_preview.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _copy_generated_command(self) -> None:
        cmd = (self._generated_command or "").strip()
        if not cmd:
            messagebox.showinfo(
                "Copy Command",
                "No command generated yet.\n\nClick Run to validate configuration and generate a command preview.",
            )
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(cmd)
            self.root.update_idletasks()
        except tk.TclError as e:
            messagebox.showerror("Copy Command", f"Could not copy to clipboard:\n\n{e}")
            return
        messagebox.showinfo("Copy Command", "Orchestrator command copied to clipboard.")

    def _refresh_execution_preview(self) -> None:
        if self._manifest_export_dir is None or not self._manifest_export_dir.is_dir():
            self._orchestrator_adapter = None
            self._set_execution_preview_text(
                "Execution Preview\n\n"
                "Export directory: (not set)\n\n"
                "Validation status: No manifests loaded.\n\n"
                "Export instances or click Load Export Directory to preview orchestrator requests."
            )
            return

        driver_root = self._driver_file_path.parent if self._driver_file_path else None
        adapter = OrchestratorAdapter(self._manifest_export_dir, driver_root=driver_root)
        result = adapter.load()
        self._orchestrator_adapter = adapter
        self._set_execution_preview_text(format_execution_preview(result))

    def _load_manifest_export_directory(self) -> None:
        initial = str(self._manifest_export_dir) if self._manifest_export_dir else str(Path.home())
        export_dir = filedialog.askdirectory(
            title="Load Manifest Export Directory",
            initialdir=initial,
        )
        if not export_dir:
            return
        self._manifest_export_dir = Path(export_dir).resolve()
        self._refresh_execution_preview()

    def _collect_run_stack_snapshot(self) -> RunStackSnapshot:
        return RunStackSnapshot(
            driver_path=self._driver_file_path,
            driver_document=self._driver_document,
            topologies_path=self._topo_file_path,
            topologies_document=self._topo_document,
            assignments_path=self._assign_file_path,
            assignments_document=self._assign_document,
            definitions_path=self._defn_file_path,
            definitions_document=self._defn_document,
            network_path=self._net_file_path,
            network_document=self._net_document,
            permutations_path=self._perm_file_path,
            permutations_document=self._perm_document,
            permutation_selections=self._perm_collect_selections(),
        )

    def _set_run_config_preview_text(self, text: str) -> None:
        if not hasattr(self, "_run_config_preview"):
            return
        try:
            self._run_config_preview.configure(state=tk.NORMAL)
            self._run_config_preview.delete("1.0", tk.END)
            self._run_config_preview.insert("1.0", text)
            self._run_config_preview.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _refresh_run_config_preview(self) -> None:
        """Debounced — coalesces rapid checkbox / load callbacks."""
        if self._run_config_refresh_after_id is not None:
            try:
                self.root.after_cancel(self._run_config_refresh_after_id)
            except tk.TclError:
                pass
        self._run_config_refresh_after_id = self.root.after(40, self._refresh_run_config_preview_impl)

    def _refresh_run_config_preview_impl(self) -> None:
        self._run_config_refresh_after_id = None
        if self._driver_file_path is None:
            self._run_configuration = None
            self._clear_experiment_instances()
            self._set_run_config_preview_text(
                "Load driver.yaml to build a run configuration from the YAML stack and permutations."
            )
            self._refresh_driver_summary()
            return

        snapshot = self._collect_run_stack_snapshot()
        config = build_run_configuration(snapshot)
        errors = validate_run_configuration(snapshot, config)
        if errors:
            self._run_configuration = None
            self._clear_experiment_instances()
            body = format_run_config_preview(config)
            err_lines = "\n".join(f"• {e}" for e in errors[:12])
            if len(errors) > 12:
                err_lines += f"\n• … and {len(errors) - 12} more."
            self._set_run_config_preview_text(f"{body}\n\nValidation:\n{err_lines}")
            self._refresh_driver_summary()
            return

        self._run_configuration = config
        self._set_run_config_preview_text(format_run_config_preview(config))
        self._update_experiment_instance_estimate()
        self._refresh_driver_summary()

    def _update_experiment_instance_estimate(self) -> None:
        """Update instance panel labels from run config without building all instances."""
        if not hasattr(self, "_exp_instance_count_lbl"):
            return
        if self._experiment_instances:
            self._refresh_experiment_instance_selector()
            return
        if self._run_configuration is None or self._run_configuration.estimated_run_count <= 0:
            self._refresh_experiment_instance_selector()
            return
        count = self._run_configuration.estimated_run_count
        self._exp_instance_count_lbl.configure(
            text=f"Estimated runs: {count} (click Run or Export to build instances)"
        )
        try:
            self._exp_instance_combo.configure(values=[], state="disabled")
            self._exp_instance_var.set("")
        except tk.TclError:
            pass
        self._set_instance_preview_text(
            "Instance Manifest Preview\n\n"
            f"Estimated runs: {count}\n\n"
            "Instances are built when you click Run or Export Instances.\n"
            "Use Run to generate the orchestrator command preview."
        )
        for btn in (getattr(self, "_exp_instance_prev_btn", None), getattr(self, "_exp_instance_next_btn", None)):
            if btn is not None:
                try:
                    btn.configure(state=tk.DISABLED)
                except tk.TclError:
                    pass

    def _clear_experiment_instances(self) -> None:
        self._experiment_instances = []
        self._experiment_instance_index = 0
        self._experiment_instances_active = False
        self._refresh_experiment_instance_selector()

    def _sync_experiment_instances_from_run_config(self) -> None:
        if self._run_configuration is None or not self._run_configuration.combinations:
            self._clear_experiment_instances()
            return
        self._experiment_instances = build_experiment_instances(self._run_configuration)
        self._experiment_instances_active = True
        self._apply_experiment_instance_index(0)

    def _auto_generate_experiment_instances(self) -> None:
        """Build experiment instances after a driver upload when the YAML stack
        (driver + permutations + topologies + assignments + definitions) is
        loaded and the run configuration validates. No Run click required."""
        if self._run_configuration is None or not self._run_configuration.combinations:
            return
        try:
            self._sync_experiment_instances_from_run_config()
        except Exception as e:  # never let auto-generation break the upload flow
            print(f"Experiment instance auto-generation skipped: {e}")
            self._clear_experiment_instances()

    def _refresh_experiment_instance_selector(self) -> None:
        if not hasattr(self, "_exp_instance_count_lbl"):
            return
        total = len(self._experiment_instances)
        if total == 0:
            self._exp_instance_count_lbl.configure(
                text="No generated instances. Upload driver.yaml with valid permutations to generate them."
            )
            if hasattr(self, "_exp_badge_instances"):
                self._exp_badge_instances.configure(text="● No instances", fg=MUTED_TEXT)
            try:
                self._exp_instance_combo.configure(values=[], state="disabled")
                self._exp_instance_var.set("")
            except tk.TclError:
                pass
            self._set_instance_preview_text(
                "Instance Manifest Preview\n\n"
                "Experiment instances are built from validated permutation combinations.\n"
                "Select an instance to preview its manifest fields, or click Export Instances."
            )
            for btn in (getattr(self, "_exp_instance_prev_btn", None), getattr(self, "_exp_instance_next_btn", None)):
                if btn is not None:
                    try:
                        btn.configure(state=tk.DISABLED)
                    except tk.TclError:
                        pass
            return

        idx = max(0, min(self._experiment_instance_index, total - 1))
        self._experiment_instance_index = idx
        labels = [inst.display_label() for inst in self._experiment_instances]
        self._exp_instance_count_lbl.configure(text=f"Instance {idx + 1} of {total}")
        if hasattr(self, "_exp_badge_instances"):
            self._exp_badge_instances.configure(text=f"● {total} Instances", fg=ACCENT)
        try:
            self._exp_instance_combo.configure(values=labels, state="readonly")
            self._exp_instance_var.set(labels[idx])
        except tk.TclError:
            pass
        prev_state = tk.NORMAL if idx > 0 else tk.DISABLED
        next_state = tk.NORMAL if idx < total - 1 else tk.DISABLED
        for btn, state in (
            (getattr(self, "_exp_instance_prev_btn", None), prev_state),
            (getattr(self, "_exp_instance_next_btn", None), next_state),
        ):
            if btn is not None:
                try:
                    btn.configure(state=state)
                except tk.TclError:
                    pass

    def _set_instance_preview_text(self, text: str) -> None:
        try:
            self._exp_instance_preview.configure(state=tk.NORMAL)
            self._exp_instance_preview.delete("1.0", tk.END)
            self._exp_instance_preview.insert("1.0", text)
            self._exp_instance_preview.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _apply_experiment_instance_index(self, index: int) -> None:
        if not self._experiment_instances:
            self._refresh_experiment_instance_selector()
            return
        index = max(0, min(index, len(self._experiment_instances) - 1))
        self._experiment_instance_index = index
        inst = self._experiment_instances[index]
        self._suspend_exp_sync = True
        try:
            self.populate_ui(copy.deepcopy(inst.experiment_state), validate_topology=True)
            self._set_instance_preview_text(format_manifest_preview(inst))
            if self._yaml_stack_sync_active or self._experiment_instances_active:
                self._set_experiment_yaml_sync_readonly(True)
        except Exception as e:
            messagebox.showerror("Experiment Instance", f"Could not load instance into the UI:\n\n{e}")
        finally:
            self._suspend_exp_sync = False
        self._refresh_experiment_instance_selector()

    def _on_experiment_instance_selected(self, _event=None) -> None:
        if not self._experiment_instances:
            return
        label = self._exp_instance_var.get().strip()
        for i, inst in enumerate(self._experiment_instances):
            if inst.display_label() == label:
                self._apply_experiment_instance_index(i)
                return

    def _exp_instance_prev(self) -> None:
        if self._experiment_instance_index > 0:
            self._apply_experiment_instance_index(self._experiment_instance_index - 1)

    def _exp_instance_next(self) -> None:
        if self._experiment_instance_index < len(self._experiment_instances) - 1:
            self._apply_experiment_instance_index(self._experiment_instance_index + 1)

    def _get_active_experiment_state(self) -> dict[str, Any]:
        if self._experiment_instances and 0 <= self._experiment_instance_index < len(self._experiment_instances):
            return copy.deepcopy(self._experiment_instances[self._experiment_instance_index].experiment_state)
        return self._collect_ui_state()

    def _export_experiment_instances(self) -> None:
        if self._driver_file_path is None:
            messagebox.showerror(
                "Export Instances",
                "Load driver.yaml before exporting experiment instance manifests.",
            )
            return

        snapshot = self._collect_run_stack_snapshot()
        run_config, instances, errors = prepare_instances_for_export(snapshot)
        if errors:
            messagebox.showerror(
                "Export Instances",
                "Fix the following before exporting manifests:\n\n"
                + "\n".join(f"• {e}" for e in errors[:20])
                + (f"\n\n… and {len(errors) - 20} more." if len(errors) > 20 else ""),
            )
            return

        initial = str(self._last_exp_file_dir.parent) if self._last_exp_file_dir else str(Path.home())
        export_dir = filedialog.askdirectory(
            title="Export Experiment Instance Manifests",
            initialdir=initial,
        )
        if not export_dir:
            return

        try:
            result = export_instance_manifests(instances, Path(export_dir))
        except OSError as e:
            messagebox.showerror("Export Instances", f"Could not write manifest files:\n\n{e}")
            return

        self._run_configuration = run_config
        self._experiment_instances = instances
        self._experiment_instances_active = True
        self._manifest_export_dir = result.export_dir
        self._apply_experiment_instance_index(0)
        self._refresh_execution_preview()

        summary = (
            f"{result.total_instances} instance{'s' if result.total_instances != 1 else ''} "
            f"exported successfully.\n\n{result.export_dir}"
        )
        if result.index_file is not None:
            summary += f"\n\nIndex: {result.index_file.name}"
        messagebox.showinfo("Export Instances", summary)

    def _collect_execution_context(self) -> ExecutionContext:
        return ExecutionContext(
            mode=SETTINGS.execution_mode,
            driver_path=self._driver_file_path,
            permutations_path=self._perm_file_path,
            topologies_path=self._topo_file_path,
            assignments_path=self._assign_file_path,
            definitions_path=self._defn_file_path,
            network_path=self._net_file_path,
            experiment_folder=self._last_exp_file_dir,
        )

    def _sync_dashboard(self) -> None:
        if not hasattr(self, "_page_shell"):
            return
        if self._sync_dashboard_pending:
            return
        self._sync_dashboard_pending = True

        def _do() -> None:
            self._sync_dashboard_pending = False
            if hasattr(self, "_page_shell"):
                self._page_shell.sync()

        try:
            self.root.after_idle(_do)
        except tk.TclError:
            self._sync_dashboard_pending = False

    def _setup_page_wheel_scroll(self) -> None:
        """Route mouse wheel to the single main page scroll area."""

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
                if isinstance(p, tk.Canvas) and getattr(p, "_range_list_scroll", False):
                    return
                if isinstance(p, tk.Text) and p.cget("height") != "1":
                    try:
                        h = int(p.cget("height"))
                        if h > 4:
                            return
                    except (TypeError, ValueError, tk.TclError):
                        pass
                p = getattr(p, "master", None)
            delta = int(-1 * (event.delta / 120))
            if hasattr(self, "_page_shell"):
                self._page_shell.scroll_wheel(delta)

        self.root.bind_all("<MouseWheel>", _wheel)

    # --- Driver page ---
    def _driver_labeled_entry(
        self, parent: ttk.Frame, label: str, row: int, *, key: str, tooltip: str = "", width: int = 0
    ) -> ttk.Entry:
        ttk.Label(parent, text=label, style="Muted.TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
            row=row, column=0, sticky="nw", padx=(0, 8), pady=4
        )
        e = ttk.Entry(parent, width=width if width else None)
        e.grid(row=row, column=1, sticky="ew" if not width else "w", pady=4)
        self._driver_fields[key] = e
        if tooltip:
            add_tooltip(e, tooltip)
        return e

    def _driver_grid_fields(
        self,
        parent: ttk.Frame,
        fields: list[tuple[str, str, str, int | None]],
        *,
        cols: int = 4,
    ) -> None:
        """Multi-column compact form: (label, key, tooltip, width). width=None → stretch."""
        for c in range(cols):
            parent.columnconfigure(c, weight=0)

        for i, (label, key, tip, width) in enumerate(fields):
            row, col = divmod(i, cols)
            cell = ttk.Frame(parent, style="CardSurface.TFrame")
            cell.grid(row=row, column=col, sticky="nw", padx=(0, SPACE_SM), pady=(0, SPACE_SM))
            ttk.Label(cell, text=label, style="Muted.TLabel").pack(anchor="w")
            if width is None:
                w = ttk.Entry(cell)
                w.pack(fill=tk.X, anchor="w", pady=(2, 0))
            else:
                w = ttk.Entry(cell, width=width)
                w.pack(anchor="w", pady=(2, 0))
            self._driver_fields[key] = w
            if tip:
                add_tooltip(w, tip)

    def _refresh_nav_actions(self, tab_index: int) -> None:
        for group in self._nav_tab_widgets:
            for widget in group:
                widget.pack_forget()
        widgets = self._nav_tab_widgets[tab_index] if 0 <= tab_index < len(self._nav_tab_widgets) else []
        for i, widget in enumerate(widgets):
            pad = (12, 0) if i == len(widgets) - 1 and widget.winfo_class() == "TLabel" else (0, 6)
            widget.pack(side=tk.LEFT, padx=pad)

    def _select_main_tab(self, tab_index: int) -> None:
        if tab_index < 0 or tab_index > 6:
            return
        if tab_index == self._main_tab_index:
            self._refresh_nav_actions(tab_index)
            return
        self._page_shell.remember_scroll(self._main_tab_index)
        self._main_tab_index = tab_index
        if hasattr(self, "_pill_tab_bar"):
            self._pill_tab_bar.set_active(tab_index)
        self._page_shell.select(tab_index)
        self._refresh_nav_actions(tab_index)
        self._ensure_page_hydrated(tab_index)
        self._sync_dashboard()

    def _ensure_page_hydrated(self, tab_index: int) -> None:
        """Lazy-load heavy card grids the first time a tab is shown."""
        if tab_index in self._pages_hydrated:
            return
        self._pages_hydrated.add(tab_index)
        if tab_index == 1:
            self._perm_rebuild_checkboxes()
        elif tab_index == 2:
            self._topo_rebuild_cards()
        elif tab_index == 3:
            self._assign_rebuild_all()
        elif tab_index == 4:
            self._defn_rebuild_all()
        elif tab_index == 5:
            self._net_rebuild_all()

    def _driver_path_row(self, parent: ttk.Frame, label: str, key: str, tip: str, row: int) -> None:
        ttk.Label(parent, text=label, style="Muted.TLabel").grid(row=row * 2, column=0, columnspan=2, sticky="w", pady=(0, 4))
        row_fr = ttk.Frame(parent, style="CardSurface.TFrame")
        row_fr.grid(row=row * 2 + 1, column=0, columnspan=2, sticky="ew", pady=(0, SPACE_SM))
        row_fr.columnconfigure(0, weight=1)
        e = ttk.Entry(row_fr)
        e.grid(row=0, column=0, sticky="ew", padx=(0, SPACE_XS))
        self._driver_fields[key] = e
        if tip:
            add_tooltip(e, tip)

        def _browse() -> None:
            initial = e.get().strip() or str(Path.home())
            path = (
                filedialog.askdirectory(title=f"Select {label}", initialdir=initial)
                if key in ("paths_save", "environment_virtualenv")
                else filedialog.askopenfilename(
                    title=f"Select {label}",
                    initialdir=str(Path(initial).parent) if initial else None,
                    filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
                )
            )
            if path:
                e.delete(0, tk.END)
                e.insert(0, path)

        ttk.Button(row_fr, text="📁", style="Icon.TButton", command=_browse).grid(row=0, column=1)

    def _build_driver_persistent(self, left: tk.Frame, center: tk.Frame) -> None:
        for col in (left, center):
            col.columnconfigure(0, weight=1)

        _slurm_outer, slurm_body = _driver_grid_card(left, "Slurm Configuration", 0)
        slurm_form = ttk.Frame(slurm_body, style="CardSurface.TFrame")
        slurm_form.pack(fill=tk.X)
        self._driver_grid_fields(
            slurm_form,
            [
                ("Partition", "slurm_partition", "Slurm partition name.", COMPACT_NUM_WIDTH),
                ("CPUs", "slurm_cpus_per_task", "CPUs allocated per task.", COMPACT_NUM_WIDTH),
                ("Memory", "slurm_mem", "Memory limit (e.g. 256G).", COMPACT_NUM_WIDTH),
                ("Time", "slurm_time", "Wall-clock limit (e.g. 4:00:00).", COMPACT_NUM_WIDTH),
                ("GRES", "slurm_gres", "Generic resources (e.g. gpu:1).", COMPACT_NAME_WIDTH),
            ],
            cols=3,
        )
        card_footer(slurm_body, "# SBATCH cluster scheduling parameters")

        _paths_outer, paths_body = _driver_grid_card(left, "Paths", 1)
        paths_body.columnconfigure(0, weight=1)
        paths_body.columnconfigure(1, weight=0)
        for row, (label, key, tip) in enumerate(
            [
                ("Definitions file", "paths_definitions", "Path to definitions.yaml."),
                ("Assignments file", "paths_assignments", "Path to assignments.yaml."),
                ("Topologies file", "paths_topologies", "Path to topologies.yaml."),
                ("Permutations file", "paths_permutations", "Path to permutations.yaml."),
                ("Save path", "paths_save", "Directory for experiment outputs."),
            ]
        ):
            self._driver_path_row(paths_body, label, key, tip, row)
        card_footer(paths_body, "Truncated paths | Click browse to locate directories", row=10)

        _exp_outer, exp_body = _driver_grid_card(center, "Experiment Configuration", 0)
        exp_form = ttk.Frame(exp_body, style="CardSurface.TFrame")
        exp_form.pack(fill=tk.X)
        self._driver_grid_fields(
            exp_form,
            [
                ("Comm rounds", "experiment_communication_rounds", "Number of communication rounds.", COMPACT_NUM_WIDTH),
                ("Seed", "experiment_seed", "Random seed.", COMPACT_NUM_WIDTH),
                ("Agent count", "experiment_agent_count", "Number of agents.", COMPACT_NUM_WIDTH),
            ],
            cols=3,
        )
        self._driver_save_mat_var = tk.BooleanVar(value=False)
        self._driver_fields["experiment_save_raw_data_as_mat"] = self._driver_save_mat_var
        ttk.Checkbutton(
            exp_form,
            text="Save raw data as MAT",
            variable=self._driver_save_mat_var,
            style="Blue.TCheckbutton",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(SPACE_SM, 0))
        card_footer(exp_body, "Experiment metadata & runtime limits")

        _rc_outer, rc_body = _driver_grid_card(center, "Run Configuration", 1)
        rc_body.columnconfigure(0, weight=1)
        self._run_config_preview = tk.Text(
            rc_body,
            height=6,
            wrap=tk.WORD,
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            relief=tk.FLAT,
            highlightthickness=0,
            font=(FONT_MONO, max(8, FONT_PT_BASE - 1)),
            state=tk.DISABLED,
        )
        self._run_config_preview.pack(fill=tk.X)
        card_footer(rc_body, "Generated run matrix from driver + permutation selections")

        _env_outer, env_body = _driver_grid_card(center, "Environment Setup", 2)
        env_body.columnconfigure(0, weight=1)
        for row, (label, key, tip) in enumerate(
            [
                ("Virtual environment", "environment_virtualenv", "Path to Python venv."),
                ("Requirements file", "environment_requirements", "Path to requirements.txt."),
            ]
        ):
            self._driver_path_row(env_body, label, key, tip, row)
        ttk.Label(env_body, text="Modules", style="Muted.TLabel").grid(row=4, column=0, sticky="w", pady=(0, 4))
        modules_fr = tk.Frame(env_body, bg=PANEL_BLUE, highlightthickness=0)
        modules_fr.grid(row=5, column=0, sticky="ew")
        modules_fr.columnconfigure(0, weight=1)
        self._driver_modules_text = tk.Text(
            modules_fr,
            height=3,
            wrap=tk.WORD,
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            relief=tk.FLAT,
            highlightthickness=0,
            font=(FONT_MONO, max(8, FONT_PT_BASE - 1)),
        )
        self._driver_modules_text.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        self._driver_fields["environment_modules"] = self._driver_modules_text
        add_tooltip(self._driver_modules_text, "Environment modules to load (one per line).")
        card_footer(env_body, "Runtime environment dependencies", row=6)

        self._apply_driver_values(gui_values_from_document(self._driver_document))

    def _build_driver_summary(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        _actions_outer, actions_body = _driver_grid_card(parent, "Driver", 0)
        btn_row = ttk.Frame(actions_body, style="CardSurface.TFrame")
        btn_row.pack(fill=tk.X, pady=(0, SPACE_SM))
        ttk.Button(
            btn_row,
            text="Upload Driver",
            style="Secondary.TButton",
            command=self._driver_upload,
        ).pack(side=tk.LEFT, padx=(0, SPACE_SM))
        ttk.Button(
            btn_row,
            text="Save Driver",
            style="Secondary.TButton",
            command=self._driver_save,
        ).pack(side=tk.LEFT)
        self._driver_page_path_lbl = ttk.Label(
            actions_body,
            text="No driver.yaml loaded",
            style="Muted.TLabel",
            wraplength=320,
            justify=tk.LEFT,
        )
        self._driver_page_path_lbl.pack(anchor="w")

        _summary_outer, body = _driver_grid_card(parent, "Driver Summary", 1)
        body.columnconfigure(0, weight=1)
        self._driver_summary_text = tk.Text(
            body,
            height=8,
            wrap=tk.WORD,
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            relief=tk.FLAT,
            highlightthickness=0,
            font=(FONT_MONO, max(8, FONT_PT_BASE - 1)),
            state=tk.DISABLED,
        )
        self._driver_summary_text.pack(fill=tk.X)
        card_footer(body, "Stack status · YAML paths and run estimate")
        self._refresh_driver_summary()

    def _update_driver_path_labels(self) -> None:
        if self._driver_file_path:
            text = f"Loaded: {self._driver_file_path}"
        else:
            text = "No driver.yaml loaded"
        try:
            self._driver_path_lbl.configure(text=text)
        except (tk.TclError, AttributeError):
            pass
        if hasattr(self, "_driver_page_path_lbl"):
            try:
                self._driver_page_path_lbl.configure(text=text)
            except tk.TclError:
                pass

    def _refresh_driver_summary(self) -> None:
        if not hasattr(self, "_driver_summary_text"):
            return
        lines: list[str] = []
        if self._driver_file_path:
            lines.append(f"Driver: {self._driver_file_path}")
        else:
            lines.append("Driver: not loaded")
        stack = (
            ("Permutations", self._perm_file_path),
            ("Topologies", self._topo_file_path),
            ("Assignments", self._assign_file_path),
            ("Definitions", self._defn_file_path),
            ("Network", self._net_file_path),
        )
        for label, path in stack:
            lines.append(f"{label}: {path.name if path else '(not loaded)'}")
        if self._run_configuration is not None and self._run_configuration.estimated_run_count > 0:
            lines.append(f"Estimated runs: {self._run_configuration.estimated_run_count}")
        elif self._driver_file_path:
            lines.append("Run matrix: pending validation")
        try:
            self._driver_summary_text.configure(state=tk.NORMAL)
            self._driver_summary_text.delete("1.0", tk.END)
            self._driver_summary_text.insert("1.0", "\n".join(lines))
            self._driver_summary_text.configure(state=tk.DISABLED)
        except tk.TclError:
            pass
        self._update_driver_path_labels()

    def _build_driver_page(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        grid = tk.Frame(parent, bg=BG_MAIN, highlightthickness=0)
        grid.pack(fill=tk.X, anchor=tk.N)
        for c in range(3):
            grid.columnconfigure(c, weight=1, uniform="driver3")
        grid.rowconfigure(0, weight=0)

        left = tk.Frame(grid, bg=BG_MAIN, highlightthickness=0)
        center = tk.Frame(grid, bg=BG_MAIN, highlightthickness=0)
        right = tk.Frame(grid, bg=BG_MAIN, highlightthickness=0)
        left.grid(row=0, column=0, sticky="new", padx=(0, CARD_GAP))
        center.grid(row=0, column=1, sticky="new", padx=(0, CARD_GAP))
        right.grid(row=0, column=2, sticky="new")

        self._build_driver_persistent(left, center)
        self._build_driver_summary(right)

    def _build_permutation_stack(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        grid = tk.Frame(parent, bg=BG_MAIN, highlightthickness=0)
        grid.pack(fill=tk.X, anchor=tk.N)
        perm_cols = 3
        for c in range(perm_cols):
            grid.columnconfigure(c, weight=1, uniform="permcol")

        self._perm_section_bodies = {}
        _perm_titles = {
            "topology": "Topology permutations",
            "profile": "Profile permutations",
            "grouping": "Grouping permutations",
            "distribution": "Distribution permutations",
            "communication": "Communication permutations",
            "model": "Model permutations",
        }
        for idx, sec in enumerate(PERMUTATION_SECTIONS):
            title = _perm_titles.get(sec["key"], f"{sec['title']} permutations")
            row, col = divmod(idx, perm_cols)
            cell = tk.Frame(grid, bg=BG_MAIN, highlightthickness=0)
            cell.grid(row=row, column=col, sticky="new", padx=(0, CARD_GAP), pady=(0, CARD_GAP))
            card = PermutationPanel(
                cell,
                title,
                start_open=True,
                on_toggle=self._perm_sync_scroll,
            )
            card.outer.pack(fill=tk.X)
            self._perm_section_bodies[sec["key"]] = card.body

    def _build_permutations_page(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        host = tk.Frame(parent, bg=BG_MAIN, highlightthickness=0)
        host.pack(fill=tk.X, anchor=tk.N)
        self._build_permutation_stack(host)

    def _collect_driver_values(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for key, widget in self._driver_fields.items():
            if key == "experiment_save_raw_data_as_mat":
                values[key] = bool(widget.get())
            elif isinstance(widget, tk.Text):
                values[key] = widget.get("1.0", "end-1c")
            else:
                values[key] = widget.get()
        return values

    def _apply_driver_values(self, values: dict[str, Any]) -> None:
        for key, widget in self._driver_fields.items():
            val = values.get(key, "")
            if key == "experiment_save_raw_data_as_mat":
                widget.set(bool(val))
            elif isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
                widget.insert("1.0", str(val or ""))
            else:
                widget.delete(0, tk.END)
                widget.insert(0, str(val if val is not None else ""))

    def _driver_upload(self) -> None:
        initial = str(self._driver_file_path.parent) if self._driver_file_path else None
        path = filedialog.askopenfilename(
            title="Upload Driver YAML",
            initialdir=initial,
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
        )
        if not path:
            return
        file_path = Path(path)
        try:
            doc = load_driver_yaml(file_path)
        except ValueError as e:
            messagebox.showerror("Upload Driver YAML", str(e))
            return
        except Exception as e:
            messagebox.showerror("Upload Driver YAML", f"Could not load driver.yaml:\n\n{e}")
            return

        self._driver_file_path = file_path.resolve()
        self._driver_document = doc
        print_driver_load_report(doc, source=self._driver_file_path)
        self._apply_driver_values(gui_values_from_document(doc))
        self._update_driver_path_labels()
        self._select_main_tab(0)

        loaded: list[str] = []
        issues: list[str] = []
        self._batch_stack_refresh = True
        try:
            for label, auto_load in (
                ("permutations.yaml", self._perm_auto_load_from_driver),
                ("topologies.yaml", self._topo_auto_load_from_driver),
                ("assignments.yaml", self._assign_auto_load_from_driver),
                ("definitions.yaml", self._defn_auto_load_from_driver),
            ):
                err = auto_load(doc, show_warnings=False)
                if err:
                    issues.append(err)
                else:
                    loaded.append(label)
        finally:
            self._batch_stack_refresh = False

        self._assign_refresh_dropdowns()
        self._net_populate_from_definitions()
        self._sync_experiment_from_yaml_stack()
        self._auto_generate_experiment_instances()
        self._refresh_driver_summary()
        self._refresh_run_config_preview()

        if issues:
            parts = [f"Driver configuration loaded:\n{self._driver_file_path}"]
            if loaded:
                parts.append("Auto-loaded:\n" + "\n".join(f"• {name}" for name in loaded))
            parts.append(
                "Issues:\n"
                + "\n".join(f"• {e}" for e in issues)
                + "\n\nFix the paths in driver.yaml and upload it again."
            )
            messagebox.showwarning("Upload Driver YAML", "\n\n".join(parts))
        else:
            messagebox.showinfo(
                "Upload Driver YAML",
                f"Driver configuration loaded.\n\n{self._driver_file_path}\n\n"
                "All referenced YAML files were loaded automatically:\n"
                + "\n".join(f"• {name}" for name in loaded),
            )

    # --- Project (folder) save ---
    @staticmethod
    def _dedup_save_path(folder: Path, filename: str) -> Path:
        """Return folder/filename, or folder/name(N).ext if the file already exists."""
        candidate = folder / filename
        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix
        n = 1
        while True:
            candidate = folder / f"{stem}({n}){suffix}"
            if not candidate.exists():
                return candidate
            n += 1

    def _collect_project_documents(self) -> tuple[list[tuple[str, Any, dict[str, Any]]], list[str]]:
        """
        Build all YAML stack documents from current GUI state.

        Returns ([(filename, writer, document), ...], errors). Documents are only
        included when their page passes validation.
        """
        entries: list[tuple[str, Any, dict[str, Any]]] = []
        errors: list[str] = []

        driver_values = self._collect_driver_values()
        ok, errs = validate_driver_values(driver_values)
        if not ok:
            errors.extend(f"Driver: {e}" for e in errs)
        else:
            entries.append(
                (DRIVER_FILENAME, save_driver_yaml, merge_gui_into_document(self._driver_document, driver_values))
            )

        selections = self._perm_collect_selections()
        entries.append(
            (
                PERMUTATIONS_FILENAME,
                save_permutations_yaml,
                merge_selections_into_document(self._perm_document, self._perm_all_options, selections),
            )
        )

        topo_entries, parse_errors = self._topo_collect_all()
        if parse_errors:
            errors.extend(f"Topologies: {e}" for e in parse_errors)
        else:
            ok, errs = validate_topologies_collection(topo_entries)
            if not ok:
                errors.extend(f"Topologies: {e}" for e in errs)
            else:
                entries.append(
                    (
                        TOPOLOGIES_FILENAME,
                        save_topologies_yaml,
                        merge_topologies_gui_into_document(self._topo_document, topo_entries),
                    )
                )

        self._assign_refresh_dropdowns()
        assign_sections = self._assign_collect_all()
        definition_refs = (
            reference_names_from_definitions(self._defn_document) if self._defn_file_path is not None else None
        )
        ok, errs = validate_sections(assign_sections, definition_refs=definition_refs)
        if not ok:
            errors.extend(f"Assignments: {e}" for e in errs)
        else:
            entries.append(
                (
                    ASSIGNMENTS_FILENAME,
                    save_assignments_yaml,
                    merge_sections_into_document(self._assign_document, assign_sections),
                )
            )

        try:
            defn_sections = self._defn_collect_all()
        except ValueError as e:
            errors.append(f"Definitions: {e}")
        else:
            ok, errs = validate_definition_sections(defn_sections)
            if not ok:
                errors.extend(f"Definitions: {e}" for e in errs)
            else:
                entries.append(
                    (
                        DEFINITIONS_FILENAME,
                        save_definitions_yaml,
                        merge_definitions_sections_into_document(self._defn_document, defn_sections),
                    )
                )

        return entries, errors

    def _project_save(self) -> None:
        """Save the full YAML configuration stack into a user-selected folder."""
        entries, errors = self._collect_project_documents()
        if errors:
            messagebox.showerror(
                "Save Configuration",
                "Fix the following before saving:\n\n"
                + "\n".join(f"• {e}" for e in errors[:20])
                + (f"\n\n… and {len(errors) - 20} more." if len(errors) > 20 else ""),
            )
            return

        if self._driver_file_path is not None:
            initial = str(self._driver_file_path.parent)
        elif self._last_exp_file_dir is not None:
            initial = str(self._last_exp_file_dir.parent)
        else:
            initial = str(Path.home())
        folder = filedialog.askdirectory(title="Save Configuration To Folder", initialdir=initial)
        if not folder:
            return
        target = Path(folder)

        written: list[str] = []
        for filename, writer, document in entries:
            path = self._dedup_save_path(target, filename)
            try:
                writer(path, document)
            except OSError as e:
                messagebox.showerror(
                    "Save Configuration",
                    f"Could not write {path.name}:\n\n{e}\n\n"
                    + ("Already saved: " + ", ".join(written) if written else "No files were saved."),
                )
                return
            written.append(path.name)

        messagebox.showinfo(
            "Save Configuration",
            "Configuration saved successfully.\n\n"
            f"{target}\n\n" + "\n".join(f"• {name}" for name in written),
        )

    def _driver_save(self) -> None:
        values = self._collect_driver_values()
        ok, errors = validate_driver_values(values)
        if not ok:
            messagebox.showerror("Save Driver", "Fix the following before saving:\n\n" + "\n".join(f"• {e}" for e in errors))
            return

        if self._driver_file_path is None:
            initial = str(Path.home())
            path = filedialog.asksaveasfilename(
                title="Save Driver YAML",
                initialdir=initial,
                initialfile=DRIVER_FILENAME,
                defaultextension=".yaml",
                filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
            )
            if not path:
                return
            self._driver_file_path = Path(path).resolve()

        merged = merge_gui_into_document(self._driver_document, values)
        try:
            save_driver_yaml(self._driver_file_path, merged)
        except OSError as e:
            messagebox.showerror("Save Driver", f"Could not write driver.yaml:\n\n{e}")
            return

        self._driver_document = merged
        self._update_driver_path_labels()
        messagebox.showinfo("Save Driver", f"Driver configuration saved.\n\n{self._driver_file_path}")

    # --- Permutations page ---
    def _perm_sync_scroll(self) -> None:
        self._sync_dashboard()

    def _perm_reference_paths_from_driver(self, driver_doc: dict[str, Any] | None = None) -> tuple[str, str, str]:
        doc = driver_doc if driver_doc is not None else self._driver_document
        vals = gui_values_from_document(doc)
        return (
            str(vals.get("paths_permutations", "") or "").strip(),
            str(vals.get("paths_topologies", "") or "").strip(),
            str(vals.get("paths_assignments", "") or "").strip(),
        )

    def _perm_collect_selections(self) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for sec_key, var_map in self._perm_checkbox_vars.items():
            out[sec_key] = {name for name, var in var_map.items() if var.get()}
        return out

    def _on_perm_selection_changed(self, *_args: Any) -> None:
        if self._perm_rebuild_active or self._batch_stack_refresh:
            return
        self._refresh_run_config_preview()

    def _perm_rebuild_checkboxes(self) -> None:
        self._perm_rebuild_active = True
        try:
            self._perm_checkbox_vars = {}
            selections = selections_from_document(self._perm_document)

            for sec in PERMUTATION_SECTIONS:
                key = sec["key"]
                body = self._perm_section_bodies[key]
                for child in body.winfo_children():
                    child.destroy()

                options = self._perm_all_options.get(key, [])
                self._perm_checkbox_vars[key] = {}

                if not options:
                    ttk.Label(
                        body,
                        text="No options available. Upload driver.yaml to load permutations.",
                        style="TLabel",
                        foreground=MUTED_TEXT,
                        wraplength=480,
                        justify=tk.LEFT,
                    ).pack(anchor="w", pady=4)
                    continue

                chosen = selections.get(key, set())
                chk_grid = ttk.Frame(body, style="CardSurface.TFrame")
                chk_grid.pack(fill=tk.X)
                perm_cols = 3
                for c in range(perm_cols):
                    chk_grid.columnconfigure(c, weight=1)
                for idx, name in enumerate(options):
                    row, col = divmod(idx, perm_cols)
                    var = tk.BooleanVar(value=name in chosen)
                    self._perm_checkbox_vars[key][name] = var
                    var.trace_add("write", self._on_perm_selection_changed)
                    cell = ttk.Frame(chk_grid, style="CardSurface.TFrame")
                    cell.grid(row=row, column=col, sticky="w", padx=(0, SPACE_XS), pady=2)
                    ttk.Checkbutton(
                        cell,
                        text=name,
                        variable=var,
                        style="Blue.TCheckbutton",
                    ).pack(anchor="w")
        finally:
            self._perm_rebuild_active = False

        self._perm_sync_scroll()

    def _perm_apply_loaded(
        self,
        *,
        perm_path: Path,
        document: dict[str, Any],
        reference_options: dict[str, list[str]] | None = None,
        show_message: bool = True,
    ) -> None:
        self._perm_file_path = perm_path.resolve()
        self._perm_document = document
        self._perm_all_options = all_options_for_sections(document, reference_options)
        print_permutations_load_report(
            document,
            source=self._perm_file_path,
            all_options=self._perm_all_options,
        )
        self._perm_rebuild_checkboxes()
        self._pages_hydrated.add(1)
        self._perm_path_lbl.configure(text=f"Loaded: {self._perm_file_path}")
        if not self._batch_stack_refresh:
            self._refresh_run_config_preview()
        if show_message:
            messagebox.showinfo("Permutations", f"Permutations loaded.\n\n{self._perm_file_path}")

    def _resolve_stack_file(
        self, kind: str, path_str: str, default_filename: str
    ) -> tuple[Path | None, list[str]]:
        """Resolve a driver-referenced YAML path with shared fallback logic + logging.

        Used identically by the permutations, topologies, assignments, and
        definitions auto-loaders so every tab benefits from the same
        beside-driver fallback. Logs the original path, the resolved local path,
        and whether a fallback (rather than the stored path) was used.
        """
        driver_file = self._driver_file_path
        resolved, attempts = resolve_stack_path_verbose(
            path_str, default_filename, driver_file=driver_file
        )
        fallback_used = resolved is not None and str(Path(path_str)) != str(resolved)
        print(f"[{kind}] driver path resolution:")
        print(f"    original : {path_str or '(empty)'}")
        print(f"    resolved : {resolved if resolved is not None else '(not found)'}")
        print(f"    fallback : {'yes' if fallback_used else 'no'}")
        if resolved is None:
            for line in attempts:
                print(f"      tried {line}")
        return resolved, attempts

    def _perm_auto_load_from_driver(
        self, driver_doc: dict[str, Any] | None = None, *, show_warnings: bool = True
    ) -> str | None:
        """Load permutations.yaml from the driver path. Returns an error string or None."""
        perm_s, topo_s, assign_s = self._perm_reference_paths_from_driver(driver_doc)
        if not perm_s:
            self._perm_path_lbl.configure(text="No permutations path in driver.yaml")
            return "permutations.yaml: paths.permutations is not set in driver.yaml."

        driver_file = self._driver_file_path
        perm_path, attempts = self._resolve_stack_file(
            "permutations", perm_s, PERMUTATIONS_FILENAME
        )
        if perm_path is None:
            hint = Path(perm_s).name if perm_s else PERMUTATIONS_FILENAME
            print(f"[permutations] could not resolve '{perm_s}'. Attempts:")
            for line in attempts:
                print(f"  {line}")
            self._perm_path_lbl.configure(text=f"Permutations file not found: {perm_s}")
            if show_warnings:
                searched = "\n".join(attempts) if attempts else "(no candidates)"
                messagebox.showwarning(
                    "Permutations",
                    f"Could not find permutations.yaml.\n\n"
                    f"driver.yaml path: {perm_s or hint}\n\n"
                    f"Searched:\n{searched}\n\n"
                    "Place permutations.yaml beside driver.yaml and upload it again.",
                )
            return f"permutations.yaml not found: {perm_s or hint}"

        topo_resolved = resolve_topologies_path(topo_s, driver_file=driver_file) if topo_s else None
        assign_resolved = resolve_assignments_path(assign_s, driver_file=driver_file) if assign_s else None
        reference_options = discover_options_from_reference(
            topologies_path=str(topo_resolved) if topo_resolved else None,
            assignments_path=str(assign_resolved) if assign_resolved else None,
        )
        try:
            document = load_permutations_yaml(perm_path)
        except ValueError as e:
            if show_warnings:
                messagebox.showerror("Permutations", str(e))
            return f"permutations.yaml invalid: {e}"
        except Exception as e:
            if show_warnings:
                messagebox.showerror("Permutations", f"Could not load permutations.yaml:\n\n{e}")
            return f"permutations.yaml could not be loaded: {e}"

        self._perm_apply_loaded(
            perm_path=perm_path,
            document=document,
            reference_options=reference_options,
            show_message=False,
        )
        return None

    def _perm_upload(self) -> None:
        initial = str(self._perm_file_path.parent) if self._perm_file_path else None
        path = filedialog.askopenfilename(
            title="Upload Permutations YAML",
            initialdir=initial,
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
        )
        if not path:
            return
        perm_path = Path(path)
        perm_s, topo_s, assign_s = self._perm_reference_paths_from_driver()
        reference_options = discover_options_from_reference(
            topologies_path=topo_s or None,
            assignments_path=assign_s or None,
        )
        try:
            document = load_permutations_yaml(perm_path)
        except ValueError as e:
            messagebox.showerror("Upload Permutations YAML", str(e))
            return
        except Exception as e:
            messagebox.showerror("Upload Permutations YAML", f"Could not load permutations.yaml:\n\n{e}")
            return

        self._perm_apply_loaded(
            perm_path=perm_path,
            document=document,
            reference_options=reference_options,
            show_message=True,
        )

    def _perm_save(self) -> None:
        if self._perm_file_path is None:
            initial = str(Path.home())
            path = filedialog.asksaveasfilename(
                title="Save Permutations YAML",
                initialdir=initial,
                initialfile=PERMUTATIONS_FILENAME,
                defaultextension=".yaml",
                filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
            )
            if not path:
                return
            self._perm_file_path = Path(path).resolve()

        selections = self._perm_collect_selections()
        merged = merge_selections_into_document(self._perm_document, self._perm_all_options, selections)
        try:
            save_permutations_yaml(self._perm_file_path, merged)
        except OSError as e:
            messagebox.showerror("Save Permutations", f"Could not write permutations.yaml:\n\n{e}")
            return

        self._perm_document = merged
        self._perm_path_lbl.configure(text=f"Loaded: {self._perm_file_path}")
        self._refresh_run_config_preview()
        messagebox.showinfo("Save Permutations", f"Permutations saved.\n\n{self._perm_file_path}")

    # --- Topologies page ---
    def _build_topologies_page(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        host = tk.Frame(parent, bg=BG_MAIN, highlightthickness=0)
        host.pack(fill=tk.X, anchor=tk.N)
        host.columnconfigure(0, weight=1)
        self._topo_cards_host = host
        self._topo_card_grid: CardGrid | None = None

    def _topo_path_from_driver(self, driver_doc: dict[str, Any] | None = None) -> str:
        doc = driver_doc if driver_doc is not None else self._driver_document
        return str(gui_values_from_document(doc).get("paths_topologies", "") or "").strip()

    def _topo_sync_scroll(self) -> None:
        self._sync_dashboard()

    def _topo_clear_cards(self) -> None:
        for card in self._topo_cards:
            outer = card.get("outer")
            if outer is not None:
                outer.destroy()
        self._topo_cards = []

    def _topo_rebuild_param_fields(self, card: dict[str, Any], block: dict[str, Any] | None = None) -> None:
        params_frame: ttk.Frame = card["params_frame"]
        for child in params_frame.winfo_children():
            child.destroy()

        graph_display = card["graph_type_var"].get()
        canonical = display_to_canonical(graph_display)
        block = block if isinstance(block, dict) else {}
        primary_keys = GRAPH_TYPE_PARAM_KEYS.get(canonical, ("n",))
        extras = extra_param_keys(block, canonical) if block else []

        card["param_entries"] = {}
        card["extra_entries"] = {}

        # Compact grid: pack several short scalar params per row (label + entry
        # pairs). Multi-line params (p list / sizes dict) get their own full row.
        pairs_per_row = 3
        for c in range(pairs_per_row):
            params_frame.columnconfigure(c * 2, weight=0)
            params_frame.columnconfigure(c * 2 + 1, weight=1)
        grid_state = {"row": 0, "col": 0}

        def _flush_row() -> None:
            if grid_state["col"] != 0:
                grid_state["row"] += 1
                grid_state["col"] = 0

        def _add_field(label: str, key: str, value: Any, *, is_extra: bool) -> None:
            is_text = key in {"p", "sizes"} and isinstance(value, (list, dict))
            if is_text:
                _flush_row()
                r = grid_state["row"]
                ttk.Label(params_frame, text=label, style="Muted.TLabel").grid(
                    row=r, column=0, sticky="w", padx=(0, 8), pady=4
                )
                entry = tk.Text(
                    params_frame,
                    height=3 if key == "p" and isinstance(value, list) else 2,
                    wrap=tk.WORD,
                    bg=INPUT_BG,
                    fg=TEXT_MAIN,
                    relief=tk.FLAT,
                    highlightthickness=1,
                    highlightbackground=INPUT_BORDER,
                    font=(FONT_MONO, max(8, FONT_PT_BASE - 1)),
                )
                entry.grid(row=r, column=1, columnspan=pairs_per_row * 2 - 1, sticky="ew", pady=4)
                entry.insert("1.0", format_param_for_display(key, value))
                grid_state["row"] += 1
                grid_state["col"] = 0
            else:
                r, c = grid_state["row"], grid_state["col"]
                ttk.Label(params_frame, text=label, style="Muted.TLabel").grid(
                    row=r, column=c * 2, sticky="w", padx=(0 if c == 0 else 14, 6), pady=4
                )
                entry = ttk.Entry(params_frame, width=COMPACT_NUM_WIDTH)
                entry.grid(row=r, column=c * 2 + 1, sticky="w", pady=4)
                if value not in (None, ""):
                    entry.insert(0, format_param_for_display(key, value))
                grid_state["col"] += 1
                if grid_state["col"] >= pairs_per_row:
                    grid_state["row"] += 1
                    grid_state["col"] = 0
            if is_extra:
                card["extra_entries"][key] = entry
            else:
                card["param_entries"][key] = entry

        for key in primary_keys:
            val = block.get(key, "")
            _add_field(key, key, val, is_extra=False)

        for key in extras:
            _add_field(key, key, block.get(key, ""), is_extra=True)

    def _topo_on_graph_type_change(self, card: dict[str, Any], _e=None) -> None:
        self._topo_rebuild_param_fields(card)

    def _topo_build_card(self, name: str, block: dict[str, Any]) -> dict[str, Any]:
        self._topo_card_seq += 1
        card_id = f"topo_{self._topo_card_seq}"
        title = f"Topology: {name}" if name else "Topology (new)"
        host = self._topo_card_grid.frame if self._topo_card_grid else self._topo_cards_host
        outer, body = _make_panel(host, title, plain_inner=True)
        if self._topo_card_grid:
            self._topo_card_grid.attach(outer)
        else:
            outer.pack(fill=tk.X, pady=(0, GUTTER))
        body.columnconfigure(0, weight=0, minsize=LABEL_COL_MIN)
        body.columnconfigure(1, weight=1)

        # Name + Graph Type on a single compact row.
        body.columnconfigure(2, weight=0)
        body.columnconfigure(3, weight=1)
        row = 0
        ttk.Label(body, text="Name", style="Muted.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        name_var = tk.StringVar(value=name)
        name_entry = ttk.Entry(body, textvariable=name_var, width=COMPACT_NAME_WIDTH)
        name_entry.grid(row=row, column=1, sticky="w", pady=3)

        ttk.Label(body, text="Graph Type", style="Muted.TLabel").grid(row=row, column=2, sticky="w", padx=(16, 8), pady=3)
        canonical = canonical_from_yaml_graph_type(block.get("graph_type"))
        graph_type_var = tk.StringVar(value=canonical_to_display(canonical))
        graph_combo = ttk.Combobox(
            body,
            textvariable=graph_type_var,
            values=topo_page_graph_display_values(),
            state="readonly",
            width=COMPACT_COMBO_WIDTH,
        )
        graph_combo.grid(row=row, column=3, sticky="w", pady=3)
        row += 1

        ttk.Label(body, text="Parameters:", style="Subsection.TLabel").grid(
            row=row, column=0, columnspan=4, sticky="w", pady=(6, 3)
        )
        row += 1
        params_frame = ttk.Frame(body, style="Inner.TFrame")
        params_frame.grid(row=row, column=0, columnspan=4, sticky="ew")
        row += 1

        card: dict[str, Any] = {
            "id": card_id,
            "outer": outer,
            "name_var": name_var,
            "name_entry": name_entry,
            "graph_type_var": graph_type_var,
            "graph_combo": graph_combo,
            "params_frame": params_frame,
            "param_entries": {},
            "extra_entries": {},
            "loaded_block": copy.deepcopy(block),
        }
        self._topo_rebuild_param_fields(card, block)
        graph_combo.bind("<<ComboboxSelected>>", lambda e, c=card: self._topo_on_graph_type_change(c))

        btn_fr = ttk.Frame(body, style="Inner.TFrame")
        btn_fr.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        ttk.Button(
            btn_fr,
            text="Remove Topology",
            style="Small.TButton",
            command=lambda c=card: self._topo_remove_card(c),
        ).pack(anchor="w")

        self._topo_cards.append(card)
        return card

    def _topo_rebuild_cards(self) -> None:
        self._topo_clear_cards()
        for child in self._topo_cards_host.winfo_children():
            child.destroy()
        names = topology_names(self._topo_document)
        if not names:
            ttk.Label(
                self._topo_cards_host,
                text="No topologies loaded. Upload driver.yaml to populate topologies.",
                style="Muted.TLabel",
                wraplength=520,
                justify=tk.LEFT,
            ).pack(anchor="w", pady=8)
            self._topo_card_grid = None
        else:
            self._topo_card_grid = CardGrid(self._topo_cards_host, columns=3)
            for name in names:
                self._topo_build_card(name, topology_block(self._topo_document, name))
        self._topo_sync_scroll()

    def _topo_read_param_entry(self, widget: Any) -> str:
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end-1c")
        return widget.get()

    def _topo_collect_card(self, card: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
        name = card["name_var"].get().strip()
        param_text: dict[str, str] = {}
        for key, widget in card.get("param_entries", {}).items():
            param_text[key] = self._topo_read_param_entry(widget)
        extra_text: dict[str, str] = {}
        for key, widget in card.get("extra_entries", {}).items():
            extra_text[key] = self._topo_read_param_entry(widget)
        try:
            block = block_from_gui(
                graph_type_display=card["graph_type_var"].get(),
                param_text=param_text,
                extra_param_text=extra_text,
            )
        except ValueError as e:
            return name, {}, str(e)
        return name, block, None

    def _topo_collect_all(self) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        entries: list[tuple[str, dict[str, Any]]] = []
        errors: list[str] = []
        for card in self._topo_cards:
            name, block, parse_err = self._topo_collect_card(card)
            if parse_err:
                errors.append(parse_err)
                continue
            entries.append((name, block))
        return entries, errors

    def _topo_apply_loaded(
        self,
        *,
        topo_path: Path,
        document: dict[str, Any],
        show_message: bool = True,
    ) -> None:
        self._topo_file_path = topo_path.resolve()
        self._topo_document = document
        print_topologies_load_report(document, source=self._topo_file_path)
        self._topo_rebuild_cards()
        self._pages_hydrated.add(2)
        self._topo_path_lbl.configure(text=f"Loaded: {self._topo_file_path}")
        if show_message:
            messagebox.showinfo("Topologies", f"Topologies loaded.\n\n{self._topo_file_path}")
        self._maybe_refresh_experiment_yaml_sync()

    def _topo_auto_load_from_driver(
        self, driver_doc: dict[str, Any] | None = None, *, show_warnings: bool = True
    ) -> str | None:
        """Load topologies.yaml from the driver path. Returns an error string or None."""
        path_str = self._topo_path_from_driver(driver_doc)
        if not path_str:
            self._topo_path_lbl.configure(text="No topologies path in driver.yaml")
            return "topologies.yaml: paths.topologies is not set in driver.yaml."

        resolved, attempts = self._resolve_stack_file(
            "topologies", path_str, TOPOLOGIES_FILENAME
        )
        if resolved is None:
            self._topo_path_lbl.configure(text=f"Topologies file not found: {path_str}")
            if show_warnings:
                searched = "\n".join(attempts) if attempts else "(no candidates)"
                messagebox.showwarning(
                    "Topologies",
                    "Could not find topologies.yaml at the path in driver.yaml.\n\n"
                    f"driver.yaml path: {path_str}\n\n"
                    f"Searched:\n{searched}\n\n"
                    "Place topologies.yaml beside driver.yaml and upload it again.",
                )
            return f"topologies.yaml not found: {path_str}"

        try:
            document = load_topologies_yaml(resolved)
        except ValueError as e:
            if show_warnings:
                messagebox.showerror("Topologies", str(e))
            self._topo_path_lbl.configure(text=f"Invalid topologies.yaml: {resolved.name}")
            return f"topologies.yaml invalid: {e}"
        except Exception as e:
            if show_warnings:
                messagebox.showerror("Topologies", f"Could not load topologies.yaml:\n\n{e}")
            return f"topologies.yaml could not be loaded: {e}"

        self._topo_apply_loaded(topo_path=resolved, document=document, show_message=False)
        return None

    def _topo_upload(self) -> None:
        initial = str(self._topo_file_path.parent) if self._topo_file_path else None
        path = filedialog.askopenfilename(
            title="Upload Topologies YAML",
            initialdir=initial,
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
        )
        if not path:
            return
        topo_path = Path(path)
        try:
            document = load_topologies_yaml(topo_path)
        except ValueError as e:
            messagebox.showerror("Upload Topologies YAML", str(e))
            return
        except Exception as e:
            messagebox.showerror("Upload Topologies YAML", f"Could not load topologies.yaml:\n\n{e}")
            return

        self._topo_apply_loaded(topo_path=topo_path, document=document, show_message=True)

    def _topo_add(self) -> None:
        if not self._topo_cards:
            for child in self._topo_cards_host.winfo_children():
                child.destroy()
            self._topo_card_grid = CardGrid(self._topo_cards_host, columns=3)

        base_name = "topology_new"
        names = {c["name_var"].get().strip() for c in self._topo_cards}
        name = base_name
        n = 1
        while name in names:
            n += 1
            name = f"{base_name}_{n}"

        block = default_topology_block("complete")
        self._topo_build_card(name, block)
        self._topo_sync_scroll()

    def _topo_remove_card(self, card: dict[str, Any]) -> None:
        display_name = card["name_var"].get().strip() or "this topology"
        if not messagebox.askyesno("Remove Topology", f"Remove topology {display_name!r}?"):
            return
        if card in self._topo_cards:
            self._topo_cards.remove(card)
        card["outer"].destroy()
        if not self._topo_cards:
            ttk.Label(
                self._topo_cards_host,
                text="No topologies. Click Add Topology or upload driver.yaml.",
                style="TLabel",
                foreground=MUTED_TEXT,
                wraplength=520,
                justify=tk.LEFT,
            ).pack(anchor="w", pady=8)
        self._topo_sync_scroll()

    def _topo_save(self) -> None:
        entries, parse_errors = self._topo_collect_all()
        if parse_errors:
            messagebox.showerror(
                "Save Topologies",
                "Fix the following before saving:\n\n" + "\n".join(f"• {e}" for e in parse_errors),
            )
            return

        ok, val_errors = validate_topologies_collection(entries)
        if not ok:
            messagebox.showerror(
                "Save Topologies",
                "Fix the following before saving:\n\n" + "\n".join(f"• {e}" for e in val_errors),
            )
            return

        if self._topo_file_path is None:
            initial = str(Path.home())
            path = filedialog.asksaveasfilename(
                title="Save Topologies YAML",
                initialdir=initial,
                initialfile=TOPOLOGIES_FILENAME,
                defaultextension=".yaml",
                filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
            )
            if not path:
                return
            self._topo_file_path = Path(path).resolve()

        merged = merge_topologies_gui_into_document(self._topo_document, entries)
        try:
            save_topologies_yaml(self._topo_file_path, merged)
        except OSError as e:
            messagebox.showerror("Save Topologies", f"Could not write topologies.yaml:\n\n{e}")
            return

        self._topo_document = merged
        self._topo_rebuild_cards()
        self._topo_path_lbl.configure(text=f"Loaded: {self._topo_file_path}")
        messagebox.showinfo("Save Topologies", f"Topologies saved.\n\n{self._topo_file_path}")

    # --- Assignments page ---
    def _assign_section_spec(self, section_key: str) -> dict[str, Any]:
        for sec in ASSIGNMENT_SECTIONS:
            if sec["key"] == section_key:
                return sec
        raise KeyError(section_key)

    def _build_assignments_page(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        host = tk.Frame(parent, bg=BG_MAIN)
        host.pack(fill=tk.X, anchor=tk.N)
        self._assign_section_hosts = {}
        self._assign_card_grids: dict[str, CardGrid] = {}
        for sec in ASSIGNMENT_SECTIONS:
            _outer, body = _column_card(host, sec["title"])
            btn_fr = ttk.Frame(body, style="CardSurface.TFrame")
            btn_fr.pack(fill=tk.X, pady=(0, SPACE_SM))
            ttk.Button(
                btn_fr,
                text=sec["add_label"],
                style="Secondary.TButton",
                command=lambda k=sec["key"]: self._assign_add(k),
            ).pack(anchor="w")
            card_grid = CardGrid(body, columns=2)
            self._assign_card_grids[sec["key"]] = card_grid
            self._assign_section_hosts[sec["key"]] = card_grid.frame

    def _assign_path_from_driver(self, driver_doc: dict[str, Any] | None = None) -> str:
        doc = driver_doc if driver_doc is not None else self._driver_document
        return str(gui_values_from_document(doc).get("paths_assignments", "") or "").strip()

    def _assign_sync_scroll(self) -> None:
        self._sync_dashboard()

    def _assign_clear_section(self, section_key: str) -> None:
        for card in self._assign_cards.get(section_key, []):
            outer = card.get("outer")
            if outer is not None:
                outer.destroy()
        self._assign_cards[section_key] = []

    def _assign_clear_all(self) -> None:
        for sec in ASSIGNMENT_SECTIONS:
            self._assign_clear_section(sec["key"])

    def _assign_agent_count_from_driver(self) -> int | None:
        try:
            raw = gui_values_from_document(self._driver_document).get("experiment_agent_count", "")
            s = str(raw or "").strip()
            if not s:
                return None
            count = int(s)
            return count if count > 0 else None
        except (TypeError, ValueError):
            return None

    def _assign_reference_options(self, section_key: str) -> tuple[str, ...]:
        refs = reference_names_from_definitions(self._defn_document)
        return tuple(sorted(refs.get(section_key, frozenset())))

    def _assign_agent_options(self) -> tuple[str, ...]:
        return agent_selection_options(self._assign_agent_count_from_driver())

    def _assign_configure_row_dropdowns(self, row: dict[str, Any], section_key: str) -> None:
        agent_entry = row["agent_entry"]
        ref_entry = row["ref_entry"]
        agent_vals = merge_dropdown_values(self._assign_agent_options(), agent_entry.get())
        ref_vals = merge_dropdown_values(self._assign_reference_options(section_key), ref_entry.get())
        agent_id = id(agent_entry)
        ref_id = id(ref_entry)
        if self._assign_dropdown_cache.get(agent_id) != agent_vals:
            agent_entry.configure(values=agent_vals)
            self._assign_dropdown_cache[agent_id] = agent_vals
        if self._assign_dropdown_cache.get(ref_id) != ref_vals:
            ref_entry.configure(values=ref_vals)
            self._assign_dropdown_cache[ref_id] = ref_vals

    def _assign_refresh_dropdowns(self) -> None:
        """Refresh agent/reference combobox suggestions from driver + definitions.yaml."""
        if not hasattr(self, "_assign_cards"):
            return
        for sec in ASSIGNMENT_SECTIONS:
            key = sec["key"]
            for card in self._assign_cards.get(key, []):
                for row in card.get("rows", []):
                    self._assign_configure_row_dropdowns(row, key)

    def _assign_build_row(
        self,
        card: dict[str, Any],
        *,
        agent: str = "",
        ref: str = "",
    ) -> dict[str, Any]:
        rows_frame: ttk.Frame = card["rows_frame"]
        row_idx = len(card["rows"]) + 1
        row_fr = ttk.Frame(rows_frame, style="Inner.TFrame")
        row_fr.grid(row=row_idx, column=0, columnspan=3, sticky="ew", pady=2)

        agent_entry = ttk.Combobox(row_fr, values=self._assign_agent_options(), width=COMPACT_COMBO_WIDTH)
        agent_entry.grid(row=0, column=0, sticky="w", padx=(0, 12))
        if agent:
            agent_entry.set(agent)

        ref_entry = ttk.Combobox(
            row_fr,
            values=self._assign_reference_options(card["section_key"]),
            width=COMPACT_COMBO_WIDTH,
        )
        ref_entry.grid(row=0, column=1, sticky="w")
        if ref:
            ref_entry.set(ref)

        row_data: dict[str, Any] = {
            "frame": row_fr,
            "agent_entry": agent_entry,
            "ref_entry": ref_entry,
            "remove_btn": None,
        }
        self._assign_configure_row_dropdowns(row_data, card["section_key"])
        if row_idx > 1:
            remove_btn = ttk.Button(
                row_fr,
                text="×",
                style="Danger.TButton",
                width=3,
                command=lambda r=row_data, c=card: self._assign_remove_row(c, r),
            )
            remove_btn.grid(row=0, column=2, padx=(8, 0))
            row_data["remove_btn"] = remove_btn

        card["rows"].append(row_data)
        return row_data

    def _assign_remove_row(self, card: dict[str, Any], row: dict[str, Any]) -> None:
        if row in card["rows"]:
            card["rows"].remove(row)
        row["frame"].destroy()
        if not card["rows"]:
            self._assign_build_row(card)

    def _assign_build_card(
        self,
        section_key: str,
        name: str,
        rows: list[tuple[str, str]],
        *,
        host: ttk.Frame | None = None,
    ) -> dict[str, Any]:
        self._assign_card_seq += 1
        spec = self._assign_section_spec(section_key)
        cards_host = host if host is not None else self._assign_section_hosts[section_key]
        card_grid = self._assign_card_grids.get(section_key)
        title = name if name else "Assignment (new)"
        outer, body = _make_panel(cards_host, title, plain_inner=True, padding=GUTTER)
        if card_grid is not None:
            card_grid.attach(outer)
        else:
            outer.pack(fill=tk.X, pady=(0, GUTTER))
        body.columnconfigure(0, weight=0, minsize=LABEL_COL_MIN)
        body.columnconfigure(1, weight=1)

        ttk.Label(body, text="Name", style="Muted.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        name_var = tk.StringVar(value=name)
        ttk.Entry(body, textvariable=name_var, width=COMPACT_NAME_WIDTH).grid(
            row=0, column=1, sticky="w", pady=3
        )

        ttk.Label(body, text="Entries:", style="Subsection.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(6, 3)
        )
        rows_frame = ttk.Frame(body, style="Inner.TFrame")
        rows_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        ref_short = spec["ref_label"].rstrip(":").replace(" Reference", "").replace(" reference", "")
        ttk.Label(rows_frame, text="Agent", style="Muted.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(rows_frame, text=ref_short or "Reference", style="Muted.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(rows_frame, text="", width=3).grid(row=0, column=2)

        card: dict[str, Any] = {
            "id": f"assign_{self._assign_card_seq}",
            "section_key": section_key,
            "outer": outer,
            "name_var": name_var,
            "rows_frame": rows_frame,
            "rows": [],
        }

        if rows:
            for agent, ref in rows:
                self._assign_build_row(card, agent=agent, ref=ref)
        else:
            self._assign_build_row(card)

        btn_fr = ttk.Frame(body, style="Inner.TFrame")
        btn_fr.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            btn_fr,
            text="Add entry",
            style="Small.TButton",
            command=lambda c=card: self._assign_build_row(c),
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            btn_fr,
            text=spec["remove_label"],
            style="Small.TButton",
            command=lambda c=card: self._assign_remove_card(c),
        ).pack(side=tk.LEFT)

        self._assign_cards[section_key].append(card)
        return card

    def _assign_rebuild_section(self, section_key: str, entries: list[tuple[str, list[tuple[str, str]]]]) -> None:
        host = self._assign_section_hosts[section_key]
        grid = self._assign_card_grids.get(section_key)
        self._assign_clear_section(section_key)
        for child in host.winfo_children():
            child.destroy()
        if grid is not None:
            grid.reset()
        if not entries:
            ttk.Label(
                host,
                text="No assignments in this section.",
                style="TLabel",
                foreground=MUTED_TEXT,
                wraplength=480,
                justify=tk.LEFT,
            ).pack(anchor="w", pady=4)
            return
        for name, rows in entries:
            self._assign_build_card(section_key, name, rows)

    def _assign_rebuild_all(self) -> None:
        self._assign_clear_all()
        entries = section_entries_from_document(self._assign_document)
        loaded = any(entries.get(sec["key"]) for sec in ASSIGNMENT_SECTIONS)
        for sec in ASSIGNMENT_SECTIONS:
            host = self._assign_section_hosts[sec["key"]]
            grid = self._assign_card_grids.get(sec["key"])
            for child in host.winfo_children():
                child.destroy()
            if grid is not None:
                grid.reset()
            sec_entries = entries.get(sec["key"], [])
            if sec_entries:
                for name, rows in sec_entries:
                    self._assign_build_card(sec["key"], name, rows)
            elif not loaded:
                ttk.Label(
                    host,
                    text="Upload driver.yaml to populate assignments.",
                    style="TLabel",
                    foreground=MUTED_TEXT,
                    wraplength=480,
                    justify=tk.LEFT,
                ).pack(anchor="w", pady=4)
        self._assign_refresh_dropdowns()
        self._assign_sync_scroll()

    def _assign_collect_all(self) -> dict[str, list[tuple[str, list[tuple[str, str]]]]]:
        out: dict[str, list[tuple[str, list[tuple[str, str]]]]] = {}
        for sec in ASSIGNMENT_SECTIONS:
            key = sec["key"]
            collected: list[tuple[str, list[tuple[str, str]]]] = []
            for card in self._assign_cards.get(key, []):
                name = card["name_var"].get().strip()
                rows: list[tuple[str, str]] = []
                for row in card["rows"]:
                    agent = row["agent_entry"].get().strip()
                    ref = row["ref_entry"].get().strip()
                    rows.append((agent, ref))
                collected.append((name, rows))
            out[key] = collected
        return out

    def _assign_apply_loaded(
        self,
        *,
        assign_path: Path,
        document: dict[str, Any],
        show_message: bool = True,
    ) -> None:
        self._assign_file_path = assign_path.resolve()
        self._assign_document = document
        print_assignments_load_report(document, source=self._assign_file_path)
        self._assign_rebuild_all()
        self._pages_hydrated.add(3)
        self._assign_path_lbl.configure(text=f"Loaded: {self._assign_file_path}")
        if show_message:
            messagebox.showinfo("Assignments", f"Assignments loaded.\n\n{self._assign_file_path}")
        self._maybe_refresh_experiment_yaml_sync()

    def _assign_auto_load_from_driver(
        self, driver_doc: dict[str, Any] | None = None, *, show_warnings: bool = True
    ) -> str | None:
        """Load assignments.yaml from the driver path. Returns an error string or None."""
        path_str = self._assign_path_from_driver(driver_doc)
        if not path_str:
            self._assign_path_lbl.configure(text="No assignments path in driver.yaml")
            return "assignments.yaml: paths.assignments is not set in driver.yaml."

        resolved, attempts = self._resolve_stack_file(
            "assignments", path_str, ASSIGNMENTS_FILENAME
        )
        if resolved is None:
            self._assign_path_lbl.configure(text=f"Assignments file not found: {path_str}")
            if show_warnings:
                searched = "\n".join(attempts) if attempts else "(no candidates)"
                messagebox.showwarning(
                    "Assignments",
                    "Could not find assignments.yaml at the path in driver.yaml.\n\n"
                    f"driver.yaml path: {path_str}\n\n"
                    f"Searched:\n{searched}\n\n"
                    "Place assignments.yaml beside driver.yaml and upload it again.",
                )
            return f"assignments.yaml not found: {path_str}"

        try:
            document = load_assignments_yaml(resolved)
        except ValueError as e:
            if show_warnings:
                messagebox.showerror("Assignments", str(e))
            self._assign_path_lbl.configure(text=f"Invalid assignments.yaml: {resolved.name}")
            return f"assignments.yaml invalid: {e}"
        except Exception as e:
            if show_warnings:
                messagebox.showerror("Assignments", f"Could not load assignments.yaml:\n\n{e}")
            return f"assignments.yaml could not be loaded: {e}"

        self._assign_apply_loaded(assign_path=resolved, document=document, show_message=False)
        return None

    def _assign_upload(self) -> None:
        initial = str(self._assign_file_path.parent) if self._assign_file_path else None
        path = filedialog.askopenfilename(
            title="Upload Assignments YAML",
            initialdir=initial,
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
        )
        if not path:
            return
        assign_path = Path(path)
        try:
            document = load_assignments_yaml(assign_path)
        except ValueError as e:
            messagebox.showerror("Upload Assignments YAML", str(e))
            return
        except Exception as e:
            messagebox.showerror("Upload Assignments YAML", f"Could not load assignments.yaml:\n\n{e}")
            return

        self._assign_apply_loaded(assign_path=assign_path, document=document, show_message=True)

    def _assign_add(self, section_key: str) -> None:
        host = self._assign_section_hosts[section_key]
        for child in host.winfo_children():
            if isinstance(child, ttk.Label):
                child.destroy()

        name, rows = default_new_assignment(section_key)
        existing = {c["name_var"].get().strip() for c in self._assign_cards.get(section_key, [])}
        while name in existing:
            self._assign_card_seq += 1
            name = f"{self._assign_section_spec(section_key)['default_new_name']}_{self._assign_card_seq}"
        self._assign_build_card(section_key, name, rows, host=host)
        self._assign_sync_scroll()

    def _assign_remove_card(self, card: dict[str, Any]) -> None:
        spec = self._assign_section_spec(card["section_key"])
        display_name = card["name_var"].get().strip() or "this assignment"
        if not messagebox.askyesno(spec["title"], f"Remove assignment {display_name!r}?"):
            return
        section_key = card["section_key"]
        if card in self._assign_cards.get(section_key, []):
            self._assign_cards[section_key].remove(card)
        card["outer"].destroy()
        self._assign_sync_scroll()

    def _assign_save(self) -> None:
        self._assign_refresh_dropdowns()
        sections = self._assign_collect_all()
        definition_refs = (
            reference_names_from_definitions(self._defn_document) if self._defn_file_path is not None else None
        )
        ok, errors = validate_sections(sections, definition_refs=definition_refs)
        if not ok:
            messagebox.showerror(
                "Save Assignments",
                "Fix the following before saving:\n\n" + "\n".join(f"• {e}" for e in errors),
            )
            return

        if self._assign_file_path is None:
            initial = str(Path.home())
            path = filedialog.asksaveasfilename(
                title="Save Assignments YAML",
                initialdir=initial,
                initialfile=ASSIGNMENTS_FILENAME,
                defaultextension=".yaml",
                filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
            )
            if not path:
                return
            self._assign_file_path = Path(path).resolve()

        merged = merge_sections_into_document(self._assign_document, sections)
        try:
            save_assignments_yaml(self._assign_file_path, merged)
        except OSError as e:
            messagebox.showerror("Save Assignments", f"Could not write assignments.yaml:\n\n{e}")
            return

        self._assign_document = merged
        self._assign_rebuild_all()
        self._assign_path_lbl.configure(text=f"Loaded: {self._assign_file_path}")
        messagebox.showinfo("Save Assignments", f"Assignments saved.\n\n{self._assign_file_path}")

    # --- Definitions page ---
    def _defn_read_widget_text(self, field: dict[str, Any]) -> str:
        widget = field.get("widget")
        if widget is None:
            return ""
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end-1c")
        if field.get("kind") == "bool":
            return "true" if field["var"].get() else "false"
        return widget.get()

    def _defn_build_field_widget(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        kind: str,
        value: Any,
        *,
        col_base: int = 0,
        full_row: bool = False,
    ) -> dict[str, Any]:
        label_col = col_base * 2
        widget_col = col_base * 2 + 1
        lbl_padx = (0 if col_base == 0 else 16, 8)
        ttk.Label(parent, text=label, style="Muted.TLabel").grid(
            row=row, column=label_col, sticky="nw", padx=lbl_padx, pady=2
        )
        field: dict[str, Any] = {"kind": kind}
        if kind == "bool":
            var = tk.BooleanVar(value=bool(value) if value is not None else False)
            cb = ttk.Checkbutton(parent, variable=var, style="Blue.TCheckbutton")
            cb.grid(row=row, column=widget_col, sticky="w", pady=2)
            field["var"] = var
            field["widget"] = cb
        elif kind == "yaml":
            txt = tk.Text(
                parent,
                height=5,
                wrap=tk.WORD,
                bg=INPUT_BG,
                fg=TEXT_MAIN,
                relief=tk.FLAT,
                highlightthickness=1,
                highlightbackground=INPUT_BORDER,
                font=(FONT_MONO, max(8, FONT_PT_BASE - 1)),
            )
            txt.grid(row=row, column=widget_col, columnspan=3, sticky="ew", pady=2)
            if value is not None:
                txt.insert("1.0", format_field_value("yaml", value))
            field["widget"] = txt
        else:
            width = COMPACT_NUM_WIDTH if kind in {"number", "prob"} else COMPACT_NAME_WIDTH
            entry = ttk.Entry(parent, width=width)
            entry.grid(row=row, column=widget_col, sticky="w", pady=2)
            if value is not None and value != "":
                entry.insert(0, format_field_value(kind, value))
            field["widget"] = entry
        return field

    def _defn_build_extra_row(self, card: dict[str, Any], key: str = "", value: Any = "") -> dict[str, Any]:
        extras_frame: ttk.Frame = card["extras_frame"]
        row_fr = ttk.Frame(extras_frame, style="Inner.TFrame")
        row_fr.pack(fill=tk.X, pady=(0, 4))
        row_fr.columnconfigure(1, weight=1)
        row_fr.columnconfigure(3, weight=1)

        ttk.Label(row_fr, text="Field:", style="TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        key_entry = ttk.Entry(row_fr, width=18)
        key_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        if key:
            key_entry.insert(0, key)

        ttk.Label(row_fr, text="Value:", style="TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8))
        if isinstance(value, (dict, list)):
            val_widget: Any = tk.Text(
                row_fr,
                height=3,
                wrap=tk.WORD,
                bg=INPUT_BG,
                fg=TEXT_MAIN,
                relief=tk.FLAT,
                highlightthickness=1,
                highlightbackground=INPUT_BORDER,
                font=(FONT_MONO, max(8, FONT_PT_BASE - 1)),
            )
            val_widget.grid(row=0, column=3, sticky="ew")
            val_widget.insert("1.0", repr(value))
        else:
            val_widget = ttk.Entry(row_fr)
            val_widget.grid(row=0, column=3, sticky="ew")
            if value not in (None, ""):
                val_widget.insert(0, str(value))

        row_data = {"frame": row_fr, "key_entry": key_entry, "value_widget": val_widget}
        card["extra_rows"].append(row_data)
        return row_data

    def _defn_build_card(
        self,
        section_key: str,
        name: str,
        block: dict[str, Any],
        *,
        host: ttk.Frame | None = None,
    ) -> dict[str, Any]:
        self._defn_card_seq += 1
        spec = definition_section_spec(section_key)
        cards_host = host if host is not None else self._defn_section_hosts[section_key]
        card_grid = self._defn_card_grids.get(section_key)
        title = name if name else "Definition (new)"
        use_collapsible = section_key in ("agent_profiles", "models")
        if use_collapsible:
            cc = CollapsibleCard(
                cards_host,
                title,
                start_open=True,
                on_toggle=self._defn_sync_scroll,
            )
            if card_grid is not None:
                card_grid.attach(cc.outer)
            else:
                cc.outer.pack(fill=tk.X, pady=(0, SPACE_LG))
            outer = cc.outer
            body = cc.body
        else:
            outer, body = _make_panel(cards_host, title, plain_inner=True, padding=GUTTER)
            if card_grid is not None:
                card_grid.attach(outer)
            else:
                outer.pack(fill=tk.X, pady=(0, SPACE_LG))
        body.columnconfigure(0, weight=1)

        known_vals, extra_vals = split_block_fields(section_key, block)

        ttk.Label(body, text="Name", style="Muted.TLabel").pack(anchor="w", pady=(0, 4))
        name_var = tk.StringVar(value=name)
        ttk.Entry(body, textvariable=name_var, width=COMPACT_NAME_WIDTH).pack(anchor="w", pady=(0, SPACE_SM))

        fields_frame = ttk.Frame(body, style="Inner.TFrame")
        fields_frame.pack(fill=tk.X)
        for c in (0, 1):
            fields_frame.columnconfigure(c * 2, weight=0)
            fields_frame.columnconfigure(c * 2 + 1, weight=1)

        known_widgets: dict[str, dict[str, Any]] = {}
        field_map = {f[0]: f for f in spec["fields"]}
        section_plan = _DEFN_FIELD_SECTIONS.get(section_key)

        def _layout_fields(parent: ttk.Frame, field_specs: list[tuple[str, str, str]], start_row: int) -> int:
            fg = {"row": start_row, "col": 0}
            for field_key, label, kind in field_specs:
                val = known_vals.get(field_key)
                if val is None and kind != "bool":
                    val = ""
                if kind == "yaml":
                    if fg["col"] != 0:
                        fg["row"] += 1
                        fg["col"] = 0
                    known_widgets[field_key] = self._defn_build_field_widget(
                        parent, fg["row"], label, kind, val, col_base=0, full_row=True
                    )
                    fg["row"] += 1
                else:
                    known_widgets[field_key] = self._defn_build_field_widget(
                        parent, fg["row"], label, kind, val, col_base=fg["col"]
                    )
                    fg["col"] += 1
                    if fg["col"] >= 2:
                        fg["row"] += 1
                        fg["col"] = 0
            if fg["col"] != 0:
                fg["row"] += 1
            return fg["row"]

        if section_plan:
            grid_row = 0
            adv_fields: list[tuple[str, str, str]] = []
            for sec_title, keys in section_plan.items():
                sec_fields = [field_map[k] for k in keys if k in field_map]
                if not sec_fields:
                    continue
                if sec_title == "Advanced":
                    adv_fields = sec_fields
                    continue
                ttk.Label(fields_frame, text=sec_title, style="Subsection.TLabel").grid(
                    row=grid_row, column=0, columnspan=4, sticky="w", pady=(SPACE_SM if grid_row else 0, SPACE_XS)
                )
                grid_row += 1
                grid_row = _layout_fields(fields_frame, sec_fields, grid_row)
            if adv_fields:
                adv_host = ttk.Frame(fields_frame, style="CardSurface.TFrame")
                adv_host.grid(row=grid_row, column=0, columnspan=4, sticky="ew", pady=(SPACE_SM, 0))
                adv_card = CollapsibleCard(
                    adv_host,
                    "Advanced",
                    start_open=False,
                    on_toggle=self._defn_sync_scroll,
                )
                adv_card.outer.pack(fill=tk.X)
                _layout_fields(adv_card.body, adv_fields, 0)
        else:
            _layout_fields(fields_frame, list(spec["fields"]), 0)

        ttk.Label(body, text="Additional fields", style="Subsection.TLabel").pack(anchor="w", pady=(SPACE_SM, SPACE_XS))
        extras_frame = ttk.Frame(body, style="Inner.TFrame")
        extras_frame.pack(fill=tk.X)

        card: dict[str, Any] = {
            "id": f"defn_{self._defn_card_seq}",
            "section_key": section_key,
            "outer": outer,
            "name_var": name_var,
            "known_widgets": known_widgets,
            "extras_frame": extras_frame,
            "extra_rows": [],
        }
        for ek, ev in extra_vals.items():
            self._defn_build_extra_row(card, ek, ev)

        btn_fr = ttk.Frame(body, style="Inner.TFrame")
        btn_fr.pack(fill=tk.X, pady=(SPACE_SM, 0))
        ttk.Button(
            btn_fr,
            text="Add field",
            style="Secondary.TButton",
            command=lambda c=card: self._defn_build_extra_row(c),
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            btn_fr,
            text=spec["remove_label"],
            style="Danger.TButton",
            command=lambda c=card: self._defn_remove_card(c),
        ).pack(side=tk.LEFT)

        self._defn_cards[section_key].append(card)
        return card

    def _build_definitions_page(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        host = tk.Frame(parent, bg=BG_MAIN)
        host.pack(fill=tk.X, anchor=tk.N)
        self._defn_section_hosts = {}
        self._defn_card_grids: dict[str, CardGrid] = {}
        for sec in DEFINITION_SECTIONS:
            _outer, body = _column_card(host, sec["title"])
            btn_fr = ttk.Frame(body, style="CardSurface.TFrame")
            btn_fr.pack(fill=tk.X, pady=(0, SPACE_SM))
            ttk.Button(
                btn_fr,
                text=sec["add_label"],
                style="Secondary.TButton",
                command=lambda k=sec["key"]: self._defn_add(k),
            ).pack(anchor="w")
            card_grid = CardGrid(body, columns=2)
            self._defn_card_grids[sec["key"]] = card_grid
            self._defn_section_hosts[sec["key"]] = card_grid.frame

    def _defn_path_from_driver(self, driver_doc: dict[str, Any] | None = None) -> str:
        doc = driver_doc if driver_doc is not None else self._driver_document
        return str(gui_values_from_document(doc).get("paths_definitions", "") or "").strip()

    def _defn_sync_scroll(self) -> None:
        self._sync_dashboard()

    def _defn_clear_section(self, section_key: str) -> None:
        for card in self._defn_cards.get(section_key, []):
            outer = card.get("outer")
            if outer is not None:
                outer.destroy()
        self._defn_cards[section_key] = []

    def _defn_clear_all(self) -> None:
        for sec in DEFINITION_SECTIONS:
            self._defn_clear_section(sec["key"])

    def _defn_rebuild_all(self) -> None:
        self._defn_clear_all()
        entries = definition_section_entries_from_document(self._defn_document)
        loaded = any(entries.get(sec["key"]) for sec in DEFINITION_SECTIONS)
        for sec in DEFINITION_SECTIONS:
            host = self._defn_section_hosts[sec["key"]]
            grid = self._defn_card_grids.get(sec["key"])
            for child in host.winfo_children():
                child.destroy()
            if grid is not None:
                grid.reset()
            sec_entries = entries.get(sec["key"], [])
            if sec_entries:
                for name, block in sec_entries:
                    self._defn_build_card(sec["key"], name, block)
            elif not loaded:
                ttk.Label(
                    host,
                    text="Upload driver.yaml to populate definitions.",
                    style="TLabel",
                    foreground=MUTED_TEXT,
                    wraplength=480,
                    justify=tk.LEFT,
                ).pack(anchor="w", pady=4)
        self._defn_sync_scroll()

    def _defn_collect_card(self, card: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
        section_key = card["section_key"]
        spec = definition_section_spec(section_key)
        known_values: dict[str, str] = {}
        known_kinds: dict[str, str] = {}
        for field_key, field in card["known_widgets"].items():
            for fk, _label, kind in spec["fields"]:
                if fk == field_key:
                    known_kinds[field_key] = kind
                    break
            known_values[field_key] = self._defn_read_widget_text(field)

        extra_values: dict[str, str] = {}
        for row in card["extra_rows"]:
            ek = row["key_entry"].get().strip()
            vw = row["value_widget"]
            if isinstance(vw, tk.Text):
                ev = vw.get("1.0", "end-1c")
            else:
                ev = vw.get()
            if ek or ev.strip():
                extra_values[ek] = ev

        try:
            block = block_from_gui_fields(section_key, known_values, known_kinds, extra_values)
        except ValueError as e:
            return card["name_var"].get().strip(), {}, str(e)
        return card["name_var"].get().strip(), block, None

    def _defn_collect_all(self) -> dict[str, list[tuple[str, dict[str, Any]]]]:
        out: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for sec in DEFINITION_SECTIONS:
            key = sec["key"]
            collected: list[tuple[str, dict[str, Any]]] = []
            for card in self._defn_cards.get(key, []):
                name, block, parse_err = self._defn_collect_card(card)
                if parse_err:
                    raise ValueError(parse_err)
                collected.append((name, block))
            out[key] = collected
        return out

    def _defn_apply_loaded(
        self,
        *,
        defn_path: Path,
        document: dict[str, Any],
        show_message: bool = True,
    ) -> None:
        self._defn_file_path = defn_path.resolve()
        self._defn_document = document
        print_definitions_load_report(document, source=self._defn_file_path)
        self._defn_rebuild_all()
        self._pages_hydrated.add(4)
        self._defn_path_lbl.configure(text=f"Loaded: {self._defn_file_path}")
        if show_message:
            messagebox.showinfo("Definitions", f"Definitions loaded.\n\n{self._defn_file_path}")
        if not self._batch_stack_refresh:
            self._assign_refresh_dropdowns()
            self._net_populate_from_definitions()
        self._maybe_refresh_experiment_yaml_sync()

    def _defn_auto_load_from_driver(
        self, driver_doc: dict[str, Any] | None = None, *, show_warnings: bool = True
    ) -> str | None:
        """Load definitions.yaml from the driver path. Returns an error string or None."""
        path_str = self._defn_path_from_driver(driver_doc)
        if not path_str:
            self._defn_path_lbl.configure(text="No definitions path in driver.yaml")
            return "definitions.yaml: paths.definitions is not set in driver.yaml."

        resolved, attempts = self._resolve_stack_file(
            "definitions", path_str, DEFINITIONS_FILENAME
        )
        if resolved is None:
            self._defn_path_lbl.configure(text=f"Definitions file not found: {path_str}")
            if show_warnings:
                searched = "\n".join(attempts) if attempts else "(no candidates)"
                messagebox.showwarning(
                    "Definitions",
                    "Could not find definitions.yaml at the path in driver.yaml.\n\n"
                    f"driver.yaml path: {path_str}\n\n"
                    f"Searched:\n{searched}\n\n"
                    "Place definitions.yaml beside driver.yaml and upload it again.",
                )
            return f"definitions.yaml not found: {path_str}"

        try:
            document = load_definitions_yaml(resolved)
        except ValueError as e:
            if show_warnings:
                messagebox.showerror("Definitions", str(e))
            self._defn_path_lbl.configure(text=f"Invalid definitions.yaml: {resolved.name}")
            return f"definitions.yaml invalid: {e}"
        except Exception as e:
            if show_warnings:
                messagebox.showerror("Definitions", f"Could not load definitions.yaml:\n\n{e}")
            return f"definitions.yaml could not be loaded: {e}"

        self._defn_apply_loaded(defn_path=resolved, document=document, show_message=False)
        return None

    def _defn_upload(self) -> None:
        initial = str(self._defn_file_path.parent) if self._defn_file_path else None
        path = filedialog.askopenfilename(
            title="Upload Definitions YAML",
            initialdir=initial,
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
        )
        if not path:
            return
        defn_path = Path(path)
        try:
            document = load_definitions_yaml(defn_path)
        except ValueError as e:
            messagebox.showerror("Upload Definitions YAML", str(e))
            return
        except Exception as e:
            messagebox.showerror("Upload Definitions YAML", f"Could not load definitions.yaml:\n\n{e}")
            return

        self._defn_apply_loaded(defn_path=defn_path, document=document, show_message=True)

    def _defn_add(self, section_key: str) -> None:
        host = self._defn_section_hosts[section_key]
        for child in host.winfo_children():
            if isinstance(child, ttk.Label):
                child.destroy()

        spec = definition_section_spec(section_key)
        name = spec["default_new_name"]
        existing = {c["name_var"].get().strip() for c in self._defn_cards.get(section_key, [])}
        while name in existing:
            self._defn_card_seq += 1
            name = f"{spec['default_new_name']}_{self._defn_card_seq}"
        block = default_new_block(section_key)
        self._defn_build_card(section_key, name, block, host=host)
        self._defn_sync_scroll()

    def _defn_remove_card(self, card: dict[str, Any]) -> None:
        spec = definition_section_spec(card["section_key"])
        display_name = card["name_var"].get().strip() or "this definition"
        if not messagebox.askyesno(spec["title"], f"Remove definition {display_name!r}?"):
            return
        section_key = card["section_key"]
        if card in self._defn_cards.get(section_key, []):
            self._defn_cards[section_key].remove(card)
        card["outer"].destroy()
        self._defn_sync_scroll()

    def _defn_save(self) -> None:
        try:
            sections = self._defn_collect_all()
        except ValueError as e:
            messagebox.showerror("Save Definitions", str(e))
            return

        ok, errors = validate_definition_sections(sections)
        if not ok:
            messagebox.showerror(
                "Save Definitions",
                "Fix the following before saving:\n\n" + "\n".join(f"• {e}" for e in errors),
            )
            return

        if self._defn_file_path is None:
            initial = str(Path.home())
            path = filedialog.asksaveasfilename(
                title="Save Definitions YAML",
                initialdir=initial,
                initialfile=DEFINITIONS_FILENAME,
                defaultextension=".yaml",
                filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
            )
            if not path:
                return
            self._defn_file_path = Path(path).resolve()

        merged = merge_definitions_sections_into_document(self._defn_document, sections)
        try:
            save_definitions_yaml(self._defn_file_path, merged)
        except OSError as e:
            messagebox.showerror("Save Definitions", f"Could not write definitions.yaml:\n\n{e}")
            return

        self._defn_document = merged
        self._defn_rebuild_all()
        self._defn_path_lbl.configure(text=f"Loaded: {self._defn_file_path}")
        self._assign_refresh_dropdowns()
        self._maybe_refresh_experiment_yaml_sync()
        messagebox.showinfo("Save Definitions", f"Definitions saved.\n\n{self._defn_file_path}")

    # --- Network page ---
    def _net_sync_scroll(self) -> None:
        self._sync_dashboard()

    def _net_make_collapsible_section(
        self, parent: tk.Frame, title: str, add_label: str, add_cmd: Callable[[], None]
    ) -> ttk.Frame:
        section_outer = ttk.Frame(parent, style="Panel.TFrame", padding=_MAIN_PANEL_PAD)
        section_outer.pack(fill=tk.X, pady=(0, GUTTER))
        header = ttk.Frame(section_outer, style="Inner.TFrame")
        header.pack(fill=tk.X, pady=(0, GUTTER))
        collapsed = tk.BooleanVar(value=False)
        toggle_btn = ttk.Button(header, text=f"▼ {title}", style="Small.TButton")
        toggle_btn.pack(side=tk.LEFT, anchor="w")
        body = ttk.Frame(section_outer, style="Inner.TFrame")
        body.pack(fill=tk.X)

        def _toggle() -> None:
            if collapsed.get():
                body.pack(fill=tk.X)
                collapsed.set(False)
                toggle_btn.configure(text=f"▼ {title}")
            else:
                body.pack_forget()
                collapsed.set(True)
                toggle_btn.configure(text=f"▶ {title}")
            self._net_sync_scroll()

        toggle_btn.configure(command=_toggle)
        btn_fr = ttk.Frame(body, style="Inner.TFrame")
        btn_fr.pack(fill=tk.X, pady=(0, GUTTER))
        ttk.Button(btn_fr, text=add_label, style="Small.TButton", command=add_cmd).pack(anchor="w")
        cards_host = ttk.Frame(body, style="Inner.TFrame")
        cards_host.pack(fill=tk.X)
        return cards_host

    def _net_build_named_block_card(
        self,
        *,
        kind: str,
        title_prefix: str,
        name: str,
        block: dict[str, Any],
        host: ttk.Frame,
        remove_label: str,
        cards_list: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._net_card_seq += 1
        card_grid = self._net_opt_card_grid if kind == "optimizer" else self._net_crit_card_grid
        title = name if name else title_prefix
        outer, body = _make_panel(host, title, plain_inner=True, padding=GUTTER)
        if card_grid is not None:
            card_grid.attach(outer)
        else:
            outer.pack(fill=tk.X, pady=(0, GUTTER))
        body.columnconfigure(0, weight=0, minsize=LABEL_COL_MIN)
        body.columnconfigure(1, weight=1)

        # Name + Type on one compact row; Learning Rate compact beneath.
        for c in (0, 1):
            body.columnconfigure(c * 2, weight=0)
        body.columnconfigure(1, weight=0)
        body.columnconfigure(3, weight=1)

        row = 0
        ttk.Label(body, text="Name", style="Muted.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        name_var = tk.StringVar(value=name)
        ttk.Entry(body, textvariable=name_var, width=COMPACT_NAME_WIDTH).grid(
            row=row, column=1, sticky="w", pady=3
        )
        known_keys = {"type", "lr", "params"}
        ttk.Label(body, text="Type:", style="TLabel").grid(row=row, column=2, sticky="w", padx=(16, 8), pady=3)
        type_entry = ttk.Entry(body, width=COMPACT_NAME_WIDTH)
        type_entry.grid(row=row, column=3, sticky="w", pady=3)
        type_entry.insert(0, str(block.get("type", "") or ""))
        row += 1

        lr_entry: ttk.Entry | None = None
        if kind == "optimizer":
            ttk.Label(body, text="Learning Rate:", style="TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
            lr_entry = ttk.Entry(body, width=COMPACT_NUM_WIDTH)
            lr_entry.grid(row=row, column=1, sticky="w", pady=3)
            lr_entry.insert(0, format_scalar(block.get("lr", "")))
            row += 1

        ttk.Label(body, text="Parameters:", style="Subsection.TLabel").grid(
            row=row, column=0, columnspan=4, sticky="w", pady=(8, 4)
        )
        row += 1
        extras_frame = ttk.Frame(body, style="Inner.TFrame")
        extras_frame.grid(row=row, column=0, columnspan=4, sticky="ew")
        row += 1

        extra_rows: list[dict[str, Any]] = []
        nested = block.get("params") if isinstance(block.get("params"), dict) else {}
        flat_extras = {k: v for k, v in block.items() if k not in known_keys}
        for k, v in nested.items():
            flat_extras[f"params.{k}"] = v

        def _add_extra(key: str = "", value: Any = "") -> None:
            fr = ttk.Frame(extras_frame, style="Inner.TFrame")
            fr.pack(fill=tk.X, pady=2)
            ttk.Label(fr, text="Parameter:", style="TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
            ke = ttk.Entry(fr, width=COMPACT_NAME_WIDTH)
            ke.grid(row=0, column=1, sticky="w", padx=(0, 16))
            if key:
                ke.insert(0, key)
            ttk.Label(fr, text="Value:", style="TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8))
            ve = ttk.Entry(fr, width=COMPACT_NAME_WIDTH)
            ve.grid(row=0, column=3, sticky="w")
            if value not in (None, ""):
                ve.insert(0, format_scalar(value) if not isinstance(value, (dict, list)) else repr(value))
            extra_rows.append({"frame": fr, "key_entry": ke, "value_entry": ve})

        for ek, ev in flat_extras.items():
            _add_extra(ek, ev)

        btn_fr = ttk.Frame(body, style="Inner.TFrame")
        btn_fr.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        card: dict[str, Any] = {
            "kind": kind,
            "outer": outer,
            "name_var": name_var,
            "type_entry": type_entry,
            "lr_entry": lr_entry,
            "extra_rows": extra_rows,
            "_add_extra": _add_extra,
        }
        ttk.Button(btn_fr, text="Add Parameter", style="Small.TButton", command=lambda: _add_extra()).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(
            btn_fr,
            text=remove_label,
            style="Small.TButton",
            command=lambda c=card, cl=cards_list: self._net_remove_block_card(c, cl),
        ).pack(side=tk.LEFT)
        cards_list.append(card)
        return card

    def _net_remove_block_card(self, card: dict[str, Any], cards_list: list[dict[str, Any]]) -> None:
        label = "optimizer" if card["kind"] == "optimizer" else "criteria"
        if not messagebox.askyesno(f"Remove {label.title()}", f"Remove {label} {card['name_var'].get().strip()!r}?"):
            return
        if card in cards_list:
            cards_list.remove(card)
        card["outer"].destroy()
        self._net_sync_scroll()

    def _build_network_page(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        host = tk.Frame(parent, bg=BG_MAIN)
        host.pack(fill=tk.X, anchor=tk.N)

        _opt_outer, opt_body = _column_card(host, "Optimizers")
        opt_btn = ttk.Frame(opt_body, style="CardSurface.TFrame")
        opt_btn.pack(fill=tk.X, pady=(0, SPACE_SM))
        ttk.Button(opt_btn, text="Add Optimizer", style="Secondary.TButton", command=self._net_add_optimizer).pack(anchor="w")
        self._net_opt_card_grid = CardGrid(opt_body, columns=1)
        self._net_optimizers_host = self._net_opt_card_grid.frame

        _crit_outer, crit_body = _column_card(host, "Criteria")
        crit_btn = ttk.Frame(crit_body, style="CardSurface.TFrame")
        crit_btn.pack(fill=tk.X, pady=(0, SPACE_SM))
        ttk.Button(crit_btn, text="Add Criteria", style="Secondary.TButton", command=self._net_add_criteria).pack(anchor="w")
        self._net_crit_card_grid = CardGrid(crit_body, columns=1)
        self._net_criteria_host = self._net_crit_card_grid.frame

    def _net_path_from_driver(self, driver_doc: dict[str, Any] | None = None) -> str:
        doc = driver_doc if driver_doc is not None else self._driver_document
        return str(gui_values_from_document(doc).get("paths_network", "") or "").strip()

    def _net_populate_from_definitions(self) -> None:
        """Build the Network page (optimizers/criteria) from definitions.yaml.

        network.yaml is no longer used; models and their embedded optimizers and
        criteria live in definitions.yaml, which is the single source of truth.
        """
        self._net_document = network_document_from_definitions(self._defn_document)
        if not hasattr(self, "_net_optimizers_host"):
            return
        self._net_rebuild_all()
        self._pages_hydrated.add(5)
        state = network_gui_state_from_document(self._net_document)
        if state["optimizers"] or state["criteria"]:
            src = self._defn_file_path.name if self._defn_file_path else "definitions.yaml"
            self._net_path_lbl.configure(text=f"From definitions.yaml ({src})")
        else:
            self._net_path_lbl.configure(text="Load definitions.yaml to populate optimizers and criteria")

    def _net_clear_hosts(self) -> None:
        for card in self._net_optimizer_cards + self._net_criteria_cards:
            if card.get("outer"):
                card["outer"].destroy()
        self._net_optimizer_cards = []
        self._net_criteria_cards = []

    def _net_rebuild_all(self) -> None:
        self._net_clear_hosts()
        state = network_gui_state_from_document(self._net_document)
        loaded = bool(state["optimizers"] or state["criteria"])

        for host, grid, items, empty_msg in (
            (self._net_optimizers_host, getattr(self, "_net_opt_card_grid", None), state["optimizers"], "No optimizers defined."),
            (self._net_criteria_host, getattr(self, "_net_crit_card_grid", None), state["criteria"], "No criteria defined."),
        ):
            if host is None:
                continue
            for child in host.winfo_children():
                child.destroy()
            if grid is not None:
                grid.reset()
            if items:
                if host is self._net_optimizers_host:
                    for name, block in items:
                        self._net_build_named_block_card(
                            kind="optimizer",
                            title_prefix="Optimizer",
                            name=name,
                            block=block,
                            host=host,
                            remove_label="Remove Optimizer",
                            cards_list=self._net_optimizer_cards,
                        )
                else:
                    for name, block in items:
                        self._net_build_named_block_card(
                            kind="criteria",
                            title_prefix="Criteria",
                            name=name,
                            block=block,
                            host=host,
                            remove_label="Remove Criteria",
                            cards_list=self._net_criteria_cards,
                        )
            elif not loaded:
                ttk.Label(
                    host,
                    text="Upload driver.yaml to populate optimizers and criteria from definitions.yaml.",
                    style="TLabel",
                    foreground=MUTED_TEXT,
                    wraplength=480,
                    justify=tk.LEFT,
                ).pack(anchor="w", pady=4)
            else:
                ttk.Label(host, text=empty_msg, style="TLabel", foreground=MUTED_TEXT).pack(anchor="w", pady=4)
        self._net_sync_scroll()

    def _net_collect_block(self, card: dict[str, Any]) -> dict[str, Any]:
        block: dict[str, Any] = {"type": card["type_entry"].get().strip()}
        if card.get("lr_entry") is not None:
            lr_text = card["lr_entry"].get().strip()
            if lr_text:
                block["lr"] = parse_scalar(lr_text)
        params: dict[str, Any] = {}
        for row in card.get("extra_rows", []):
            key = row["key_entry"].get().strip()
            val = row["value_entry"].get().strip()
            if not key or not val:
                continue
            if key.startswith("params."):
                pk = key[7:]
                params[pk] = parse_scalar(val)
            else:
                block[key] = parse_scalar(val)
        if params:
            block["params"] = params
        return block

    def _net_collect_all(self) -> tuple[list[tuple[str, dict[str, Any]]], list[tuple[str, dict[str, Any]]]]:
        optimizers: list[tuple[str, dict[str, Any]]] = []
        for card in self._net_optimizer_cards:
            optimizers.append((card["name_var"].get().strip(), self._net_collect_block(card)))

        criteria: list[tuple[str, dict[str, Any]]] = []
        for card in self._net_criteria_cards:
            criteria.append((card["name_var"].get().strip(), self._net_collect_block(card)))

        return optimizers, criteria

    def _net_apply_loaded(self, *, net_path: Path, document: dict[str, Any], show_message: bool = True) -> None:
        self._net_file_path = net_path.resolve()
        self._net_document = document
        print_network_load_report(document, source=self._net_file_path)
        self._net_rebuild_all()
        self._net_path_lbl.configure(text=f"Loaded: {self._net_file_path}")
        if show_message:
            messagebox.showinfo("Network", f"Network configuration loaded.\n\n{self._net_file_path}")
        self._maybe_refresh_experiment_yaml_sync()

    def _net_auto_load_from_driver(
        self, driver_doc: dict[str, Any] | None = None, *, show_warnings: bool = True
    ) -> str | None:
        """Load network.yaml from the driver path. Returns an error string or None."""
        path_str = self._net_path_from_driver(driver_doc)
        resolved = resolve_network_path(path_str, driver_file=self._driver_file_path)
        if resolved is None:
            hint = path_str or "network.yaml beside driver.yaml"
            self._net_path_lbl.configure(text=f"Network file not found: {hint}")
            if show_warnings:
                messagebox.showwarning(
                    "Network",
                    "Could not find network.yaml.\n\n"
                    f"Looked for: {hint}\n\n"
                    "Add paths.network to driver.yaml and upload it again.",
                )
            return f"network.yaml not found: {hint}"

        try:
            document = load_network_yaml(resolved)
        except ValueError as e:
            if show_warnings:
                messagebox.showerror("Network", str(e))
            self._net_path_lbl.configure(text=f"Invalid network.yaml: {resolved.name}")
            return f"network.yaml invalid: {e}"
        except Exception as e:
            if show_warnings:
                messagebox.showerror("Network", f"Could not load network.yaml:\n\n{e}")
            return f"network.yaml could not be loaded: {e}"

        self._net_apply_loaded(net_path=resolved, document=document, show_message=False)
        return None

    def _net_upload(self) -> None:
        initial = str(self._net_file_path.parent) if self._net_file_path else None
        path = filedialog.askopenfilename(
            title="Upload Network YAML",
            initialdir=initial,
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            document = load_network_yaml(Path(path))
        except ValueError as e:
            messagebox.showerror("Upload Network YAML", str(e))
            return
        except Exception as e:
            messagebox.showerror("Upload Network YAML", f"Could not load network.yaml:\n\n{e}")
            return
        self._net_apply_loaded(net_path=Path(path), document=document, show_message=True)

    def _net_add_optimizer(self) -> None:
        if self._net_optimizers_host is None:
            return
        name, block = default_new_optimizer()
        existing = {c["name_var"].get().strip() for c in self._net_optimizer_cards}
        while name in existing:
            self._net_card_seq += 1
            name = f"optimizer_new_{self._net_card_seq}"
        self._net_build_named_block_card(
            kind="optimizer",
            title_prefix="Optimizer",
            name=name,
            block=block,
            host=self._net_optimizers_host,
            remove_label="Remove Optimizer",
            cards_list=self._net_optimizer_cards,
        )
        self._net_sync_scroll()

    def _net_add_criteria(self) -> None:
        if self._net_criteria_host is None:
            return
        name, block = default_new_criteria()
        existing = {c["name_var"].get().strip() for c in self._net_criteria_cards}
        while name in existing:
            self._net_card_seq += 1
            name = f"criteria_new_{self._net_card_seq}"
        self._net_build_named_block_card(
            kind="criteria",
            title_prefix="Criteria",
            name=name,
            block=block,
            host=self._net_criteria_host,
            remove_label="Remove Criteria",
            cards_list=self._net_criteria_cards,
        )
        self._net_sync_scroll()

    def _net_save(self) -> None:
        optimizers, criteria = self._net_collect_all()
        ok, errors = validate_network_state(optimizers=optimizers, criteria=criteria)
        if not ok:
            messagebox.showerror(
                "Save Network",
                "Fix the following before saving:\n\n" + "\n".join(f"• {e}" for e in errors),
            )
            return

        if self._net_file_path is None:
            path = filedialog.asksaveasfilename(
                title="Save Network YAML",
                initialfile=NETWORK_FILENAME,
                defaultextension=".yaml",
                filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
            )
            if not path:
                return
            self._net_file_path = Path(path).resolve()

        # Models are managed on the Definitions page now; any legacy models block
        # in network.yaml is preserved untouched by the merge.
        merged = merge_network_gui_into_document(
            self._net_document,
            optimizers=optimizers,
            criteria=criteria,
        )
        try:
            save_network_yaml(self._net_file_path, merged)
        except OSError as e:
            messagebox.showerror("Save Network", f"Could not write network.yaml:\n\n{e}")
            return

        self._net_document = merged
        self._net_rebuild_all()
        self._net_path_lbl.configure(text=f"Loaded: {self._net_file_path}")
        messagebox.showinfo("Save Network", f"Network configuration saved.\n\n{self._net_file_path}")

    def _build_experiment_page(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        grid = tk.Frame(parent, bg=BG_MAIN, highlightthickness=0)
        grid.pack(fill=tk.X, anchor=tk.N)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        exp_cols = 2
        for c in range(exp_cols):
            grid.columnconfigure(c, weight=1, uniform="expcol")

        left = tk.Frame(grid, bg=BG_MAIN, highlightthickness=0)
        right = tk.Frame(grid, bg=BG_MAIN, highlightthickness=0)
        left.grid(row=0, column=0, sticky="new", padx=(0, CARD_GAP))
        right.grid(row=0, column=1, sticky="new")
        center = left
        self._exp_layout = None

        self._build_experiment_instance_panel(left)
        self._build_environment_panel(left)
        self._build_topology_panel(left)
        self._build_communication_panel(right)
        self._build_group_policy_panel(right)
        self._build_profile_assignment_panel(right)
        self._build_model_assignment_panel(right)
        self._build_data_assignment_panel(right)
        self._build_network_panel(right)
        self._build_notes_panel(right)

        exec_outer, exec_body = _column_card(right, "Execution Preview")
        exec_body.columnconfigure(0, weight=1)
        self._execution_preview = tk.Text(
            exec_body,
            height=8,
            wrap=tk.WORD,
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            relief=tk.FLAT,
            highlightthickness=0,
            font=(FONT_MONO, max(8, FONT_PT_BASE - 1)),
            state=tk.DISABLED,
        )
        self._execution_preview.pack(fill=tk.X)
        self._refresh_execution_preview()

        exec_row = ttk.Frame(right, style="CardSurface.TFrame")
        exec_row.pack(fill=tk.X, pady=(0, CARD_GAP))
        ttk.Button(
            exec_row,
            text="Load Export Directory",
            style="Secondary.TButton",
            command=self._load_manifest_export_directory,
        ).pack(side=tk.LEFT, padx=(0, SPACE_SM))
        ttk.Label(
            exec_row,
            text="Run opens Graph, Summary, Logs & Terminal in the execution window.",
            style="Muted.TLabel",
            wraplength=420,
        ).pack(side=tk.LEFT)

        _cmd_outer, cmd_body = _column_card(right, "Command Preview")
        cmd_body.columnconfigure(0, weight=1)
        self._command_preview = tk.Text(
            cmd_body,
            height=6,
            wrap=tk.WORD,
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            relief=tk.FLAT,
            highlightthickness=0,
            font=(FONT_MONO, max(8, FONT_PT_BASE - 1)),
            state=tk.DISABLED,
        )
        self._command_preview.pack(fill=tk.X)

    def _build_experiment_instance_panel(self, parent, *, grid: CardGrid | None = None) -> None:
        outer, inner = _make_panel(parent, "Manifest Preview", plain_inner=True)
        _mount_panel(outer, grid)

        badge_row = ttk.Frame(inner, style="CardSurface.TFrame")
        badge_row.pack(fill=tk.X, pady=(0, SPACE_SM))
        self._exp_badge_instances = status_badge(badge_row, "No instances", color=MUTED_TEXT)
        self._exp_badge_instances.pack(side=tk.LEFT, padx=(0, SPACE_SM))

        nav = ttk.Frame(inner, style="CardSurface.TFrame")
        nav.pack(fill=tk.X, pady=(0, SPACE_SM))
        self._exp_instance_count_lbl = ttk.Label(
            nav,
            text="No generated instances.",
            style="Muted.TLabel",
        )
        self._exp_instance_count_lbl.pack(side=tk.LEFT)

        self._exp_instance_prev_btn = ttk.Button(nav, text="◀ Prev", command=self._exp_instance_prev)
        self._exp_instance_prev_btn.pack(side=tk.RIGHT, padx=(4, 0))
        self._exp_instance_next_btn = ttk.Button(nav, text="Next ▶", command=self._exp_instance_next)
        self._exp_instance_next_btn.pack(side=tk.RIGHT, padx=(4, 0))

        pick = ttk.Frame(inner, style="Inner.TFrame")
        pick.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(pick, text="Select instance:", style="TLabel").pack(side=tk.LEFT, padx=(0, 8))
        self._exp_instance_var = tk.StringVar(value="")
        self._exp_instance_combo = ttk.Combobox(
            pick,
            textvariable=self._exp_instance_var,
            state="disabled",
            width=48,
        )
        self._exp_instance_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._exp_instance_combo.bind("<<ComboboxSelected>>", self._on_experiment_instance_selected)

        export_row = ttk.Frame(inner, style="Inner.TFrame")
        export_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(export_row, text="Instance Manifest Preview", style="Subsection.TLabel").pack(
            side=tk.LEFT, padx=(0, 12)
        )
        ttk.Button(
            export_row,
            text="Export Instances",
            style="Accent.TButton",
            command=self._export_experiment_instances,
        ).pack(side=tk.RIGHT)

        preview_holder = tk.Frame(
            inner,
            bg=INPUT_BG,
            highlightbackground=INPUT_BORDER,
            highlightthickness=1,
        )
        preview_holder.pack(fill=tk.X)
        preview_holder.columnconfigure(0, weight=1)
        self._exp_instance_preview = tk.Text(
            preview_holder,
            height=4,
            wrap=tk.WORD,
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            font=(FONT_MONO, max(8, FONT_PT_BASE - 1)),
            state=tk.DISABLED,
        )
        self._exp_instance_preview.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        self._refresh_experiment_instance_selector()

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
    def _build_environment_panel(self, parent, *, grid: CardGrid | None = None):
        outer, inner = _make_panel(parent, "Environment", plain_inner=True)
        _mount_panel(outer, grid)

        fields_row = ttk.Frame(inner, style="CardSurface.TFrame")
        fields_row.pack(fill=tk.X)
        for c in range(4):
            fields_row.columnconfigure(c, weight=1)

        def _cell(col: int, label: str, build_widget) -> tk.Misc:
            cell = ttk.Frame(fields_row, style="CardSurface.TFrame")
            cell.grid(row=0, column=col, sticky="ew", padx=(0, SPACE_SM))
            ttk.Label(cell, text=label, style="Muted.TLabel").pack(anchor="w")
            widget = build_widget(cell)
            widget.pack(anchor="w", pady=(2, 0))
            return widget

        self.env_seed = _cell(
            0,
            "Random Seed",
            lambda p: ttk.Spinbox(p, from_=-2**31, to=2**31 - 1, width=COMPACT_NUM_WIDTH),
        )
        add_tooltip(self.env_seed, "Integer seed for reproducible environment initialization.")

        self.env_save_path = _cell(1, "Save Path", lambda p: ttk.Entry(p, width=COMPACT_NAME_WIDTH))
        add_tooltip(self.env_save_path, "Directory where artifacts are written.")

        self.env_save_name = _cell(2, "Save Name", lambda p: ttk.Entry(p, width=COMPACT_NAME_WIDTH))
        add_tooltip(self.env_save_name, "Base file name for outputs.")

        paths_fr = ttk.Frame(inner, style="CardSurface.TFrame")
        paths_fr.pack(fill=tk.X, pady=(SPACE_SM, 0))
        paths_fr.columnconfigure(0, weight=1)
        paths_fr.columnconfigure(1, weight=1)
        ttk.Label(paths_fr, text="Agent Assignment Path", style="Muted.TLabel").grid(row=0, column=0, sticky="w", padx=(0, SPACE_SM))
        ttk.Label(paths_fr, text="Topology Assignment Path", style="Muted.TLabel").grid(row=0, column=1, sticky="w")
        self.env_agent_path = ttk.Entry(paths_fr)
        self.env_agent_path.grid(row=1, column=0, sticky="ew", pady=(2, 0), padx=(0, SPACE_SM))
        add_tooltip(self.env_agent_path, "Path to agent-role assignment configuration.")
        self.env_topology_assign_path = ttk.Entry(paths_fr)
        self.env_topology_assign_path.grid(row=1, column=1, sticky="ew", pady=(2, 0))
        add_tooltip(self.env_topology_assign_path, "Path to topology assignment configuration.")

    # --- Communication ---
    def _fill_communication_tab(self, tab: ttk.Frame, state: dict[str, Any] | None) -> dict[str, Any]:
        for c in (0, 1):
            tab.columnconfigure(c * 2, weight=0)
            tab.columnconfigure(c * 2 + 1, weight=1)
        w: dict[str, Any] = {}
        r = 0
        for i, (lab, tip, key) in enumerate((
            ("Latency probability (0–1):", "Chance a message is delayed.", "latency_prob"),
            ("Dropout probability (0–1):", "Chance a message is dropped.", "dropout_prob"),
        )):
            col = i % 2
            ttk.Label(tab, text=lab, style="TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
                row=r, column=col * 2, sticky="nw", padx=(0 if col == 0 else 16, 8), pady=5
            )
            e = ttk.Entry(tab, width=COMPACT_NUM_WIDTH)
            e.grid(row=r, column=col * 2 + 1, sticky="w", pady=5)
            add_tooltip(e, tip)
            w[key] = e
        r += 1

        lat_row = ttk.Frame(tab, style="Inner.TFrame")
        lat_row.grid(row=r, column=0, columnspan=4, sticky="ew", pady=5)
        ttk.Label(lat_row, text="Latency minimum:", style="TLabel").pack(side=tk.LEFT, padx=(0, 6))
        w["latency_min"] = ttk.Entry(lat_row, width=10)
        w["latency_min"].pack(side=tk.LEFT)
        add_tooltip(w["latency_min"], "Minimum delay (steps or ms).")
        ttk.Label(lat_row, text="Latency maximum:", style="TLabel").pack(side=tk.LEFT, padx=(16, 6))
        w["latency_max"] = ttk.Entry(lat_row, width=10)
        w["latency_max"].pack(side=tk.LEFT)
        add_tooltip(w["latency_max"], "Maximum delay.")
        r += 1
        sub = ttk.Frame(tab, style="Inner.TFrame")
        sub.grid(row=r, column=0, columnspan=4, sticky="ew", pady=(8, 0))
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
        for key in ("latency_prob", "dropout_prob", "latency_min", "latency_max"):
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
            "latency_min": w["latency_min"].get(),
            "latency_max": w["latency_max"].get(),
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

    def _build_communication_panel(self, parent, *, grid: CardGrid | None = None):
        outer, inner = _make_panel(parent, "Communication Assignment", plain_inner=True)
        _mount_panel(outer, grid)

        bar = ttk.Frame(inner, style="Inner.TFrame")
        host = ttk.Frame(inner, style="Inner.TFrame")
        bar.pack(fill=tk.X, pady=(0, GUTTER))
        host.pack(fill=tk.X)

        self.comm_notebook = ttk.Notebook(host)
        self.comm_notebook.pack(fill=tk.X)
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

    def _build_group_policy_panel(self, parent, *, grid: CardGrid | None = None):
        outer, inner = _make_panel(parent, "Group Policy Assignment", green=True, plain_inner=True)
        _mount_panel(outer, grid)

        bar = ttk.Frame(inner, style="InnerGreen.TFrame")
        host = ttk.Frame(inner, style="InnerGreen.TFrame")
        bar.pack(fill=tk.X, pady=(0, GUTTER))
        host.pack(fill=tk.X)

        self.group_policy_notebook = ttk.Notebook(host)
        self.group_policy_notebook.pack(fill=tk.X)
        self._group_policy_tab_states: list[dict[str, Any]] = []

        ttk.Button(bar, text="Add Group Policy Card", command=self._gp_add_tab).pack(side=tk.LEFT)
        ttk.Button(bar, text="Remove group policy tab", style="Small.TButton", command=self._gp_remove_tab).pack(
            side=tk.LEFT, padx=(GUTTER, 0)
        )
        self._gp_add_tab(default_group_policy_card(1))

    # --- Profile Assignment 
    def _build_profile_assignment_panel(self, parent, *, grid: CardGrid | None = None):
        outer, inner = _make_panel(parent, "Profile Assignment", green=True, plain_inner=True)
        _mount_panel(outer, grid)

        self._exp_profile_source_lbl = ttk.Label(
            inner,
            text="",
            style="TLabel",
            foreground=MUTED_TEXT,
            wraplength=520,
            justify=tk.LEFT,
        )
        self._exp_profile_source_lbl.pack(fill=tk.X, anchor="w", pady=(0, 4))
        bar = ttk.Frame(inner, style="InnerGreen.TFrame")
        bar.pack(fill=tk.X, pady=(0, GUTTER))
        self._exp_profile_add_btn = ttk.Button(bar, text="Add Profile", command=self._profile_add_tab)
        self._exp_profile_add_btn.pack(side=tk.LEFT)
        self._exp_profile_remove_btn = ttk.Button(
            bar, text="Remove profile", style="Small.TButton", command=self._profile_remove_tab
        )
        self._exp_profile_remove_btn.pack(side=tk.LEFT, padx=(GUTTER, 0))

        self.profile_stack = ttk.Frame(inner, style="InnerGreen.TFrame")
        self.profile_stack.pack(fill=tk.X)
        self.profile_notebook = ttk.Notebook(self.profile_stack)
        self.profile_notebook.pack(fill=tk.X)
        self.profile_notebook.bind("<<NotebookTabChanged>>", self._on_profile_notebook_tab)
        self._profile_tab_states: list[dict[str, Any]] = []
        self._profile_active_idx = 0

    def _fill_profile_tab(self, lf: ttk.Frame, state: dict[str, Any] | None) -> dict[str, Any]:
        for c in (0, 1):
            lf.columnconfigure(c * 2, weight=0)
            lf.columnconfigure(c * 2 + 1, weight=1)
        roles = ("dfl_server", "dfl_client", "aggregator", "custom")
        aggs = ("average", "sum", "max", "weighted_average")
        w: dict[str, Any] = {}

        # Two label/value pairs per row; cursor advances across 2 pair-columns.
        g = {"row": 0, "col": 0}

        def _flush() -> None:
            if g["col"] != 0:
                g["row"] += 1
                g["col"] = 0

        def _place(label: str, widget: Any, *, tip: str = "", full: bool = False, sticky: str = "w") -> None:
            if full:
                _flush()
            c = g["col"]
            lab = ttk.Label(lf, text=label, style="Green.TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT)
            lab.grid(row=g["row"], column=c * 2, sticky="nw", padx=(0 if c == 0 else 16, 8), pady=2)
            span = 3 if full else 1
            widget.grid(row=g["row"], column=c * 2 + 1, columnspan=span, sticky=sticky, pady=2)
            if tip:
                add_tooltip(lab, tip)
                add_tooltip(widget, tip)
            if full:
                g["row"] += 1
                g["col"] = 0
            else:
                g["col"] += 1
                if g["col"] >= 2:
                    g["row"] += 1
                    g["col"] = 0

        e0 = ttk.Entry(lf, width=COMPACT_NAME_WIDTH)
        _place("Description:", e0, tip="Human-readable label for this agent profile.", full=True)
        w["description"] = e0

        rc = ttk.Combobox(lf, values=roles, width=COMPACT_COMBO_WIDTH, state="readonly")
        _place("Role:", rc, tip="Logical role for this profile (e.g. dfl_server).")
        w["role"] = rc
        ac = ttk.Combobox(lf, values=aggs, width=COMPACT_COMBO_WIDTH, state="readonly")
        _place("Aggregation:", ac, tip="Aggregation rule over neighbor updates (e.g. average).")
        w["aggregation"] = ac

        wt = ttk.Spinbox(lf, from_=0, to=10**9, width=COMPACT_NUM_WIDTH)
        _place("Wait Time:", wt, tip="Steps or seconds to wait before acting.")
        w["wait_time"] = wt

        for lab, key, tip in (
            ("Aggregation Min:", "agg_min", "Minimum value before aggregation triggers."),
            ("Freshness Cap:", "freshness_cap", "Maximum staleness allowed for updates."),
            ("Training Time:", "training_time", "Allocated training duration."),
        ):
            e = ttk.Entry(lf, width=COMPACT_NUM_WIDTH)
            _place(lab, e, tip=tip)
            w[key] = e

        vt = tk.BooleanVar(value=True)
        _place("Does Train:", ttk.Checkbutton(lf, style="Green.TCheckbutton", variable=vt))
        w["does_train"] = vt

        mt = tk.Text(
            lf,
            height=3,
            width=40,
            font=(FONT_FAMILY, FONT_PT_BASE),
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=INPUT_BORDER,
        )
        _place("Metrics (tokens):", mt, tip="Comma- or newline-separated metric names to track.", full=True, sticky="ew")
        register_notes_text(mt)
        w["metrics"] = mt

        for lab, key, tip in (
            ("Neighbor Ratio:", "neighbor_ratio", "Fraction of neighbors sampled each step."),
            ("Epochs:", "epochs", "Training epochs."),
            ("Mini-batches:", "minibatches", "Mini-batch count per epoch."),
            ("Release Agent:", "release_agent", "Index or id when releasing."),
            ("Group ID:", "group_id", "Logical group identifier."),
        ):
            e = ttk.Entry(lf, width=COMPACT_NUM_WIDTH)
            _place(lab, e, tip=tip)
            w[key] = e

        v_sync = tk.BooleanVar(value=False)
        _place("Is Sync:", ttk.Checkbutton(lf, style="Green.TCheckbutton", variable=v_sync))
        w["is_sync"] = v_sync
        v_ck = tk.BooleanVar(value=False)
        _place("Checkpoint Enabled:", ttk.Checkbutton(lf, style="Green.TCheckbutton", variable=v_ck))
        w["checkpoint"] = v_ck
        _flush()

        r = g["row"]
        sub = ttk.Frame(lf, style="InnerGreen.TFrame")
        sub.grid(row=r, column=0, columnspan=4, sticky="ew", pady=(8, 0))
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
    def _build_topology_panel(self, parent, *, grid: CardGrid | None = None):
        outer, inner = _make_panel(parent, "Topology & Graph", plain_inner=True, padding=GUTTER)
        _mount_panel(outer, grid)

        inner.columnconfigure(0, weight=1)
        inner.rowconfigure(0, weight=1)
        inner.rowconfigure(1, weight=0)

        form = ttk.Frame(inner, style="Inner.TFrame", padding=(4, 10, 4, 4))
        form.grid(row=0, column=0, sticky="nsew")
        form.columnconfigure(0, weight=0, minsize=LABEL_COL_MIN)
        form.columnconfigure(1, weight=1)

        self._exp_topo_source_lbl = ttk.Label(
            form,
            text="",
            style="TLabel",
            foreground=MUTED_TEXT,
            wraplength=520,
            justify=tk.LEFT,
        )
        self._exp_topo_source_lbl.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        bf = ttk.Frame(inner, style="Inner.TFrame", padding=(4, 0, 4, 4))
        bf.grid(row=1, column=0, sticky="ew")
        bf.columnconfigure(0, weight=1, uniform="topo_btns")
        bf.columnconfigure(1, weight=1)
        pb = dict(padx=4, pady=4, sticky="nsew")
        self._exp_topo_buttons = [
            ttk.Button(bf, text="Reset to defaults", style="Small.TButton", command=self._topology_reset),
            ttk.Button(bf, text="Validate / Preview", style="Small.TButton", command=self._topology_validate),
            ttk.Button(bf, text="Add graph configuration", style="Small.TButton", command=self._topology_add_graph),
            ttk.Button(
                bf, text="Remove graph configuration", style="Small.TButton", command=self._topology_remove_graph
            ),
        ]
        self._exp_topo_buttons[0].grid(row=0, column=0, **pb)
        self._exp_topo_buttons[1].grid(row=0, column=1, **pb)
        self._exp_topo_buttons[2].grid(row=1, column=0, **pb)
        self._exp_topo_buttons[3].grid(row=1, column=1, **pb)
        self._exp_topo_form = form
        self._exp_topo_btn_frame = bf

        self._topology_graph_idx = 0
        self._suspend_topology_graph_events = False

        py = 5
        ttk.Label(form, text="Active graph:", style="TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=(0, py)
        )
        self.topology_graph_combo = ttk.Combobox(form, state="readonly", width=28)
        self.topology_graph_combo.grid(row=0, column=1, sticky="w", pady=(0, py))
        add_tooltip(self.topology_graph_combo, "Switch between saved graph configurations.")
        self.topology_graph_combo.bind("<<ComboboxSelected>>", self._on_topology_graph_selected)

        ttk.Label(form, text="Graph type:", style="TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(0, py)
        )
        self.graph_type_var = tk.StringVar(value=graph_type_label(GRAPH_TYPES[0]))
        self.graph_type_combo = ttk.Combobox(
            form,
            textvariable=self.graph_type_var,
            values=graph_type_display_values(),
            width=30,
            state="readonly",
        )
        self.graph_type_combo.grid(row=1, column=1, sticky="w", pady=(0, py))
        add_tooltip(self.graph_type_combo, "Generator family for the underlying graph structure.")

        self._seed_label = ttk.Label(form, text="Seed:", style="TLabel")
        self._seed_label.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(0, py))
        self.global_seed_spin = ttk.Spinbox(form, from_=0, to=2**31 - 1, width=COMPACT_NUM_WIDTH)
        self.global_seed_spin.grid(row=2, column=1, sticky="w", pady=(0, py))
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

    def _current_graph_type(self) -> str:
        return graph_type_canonical(self.graph_type_var.get())

    def _topology_repack_optional_in_params_box(self):
        gt = self._current_graph_type()
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
        gt = self._current_graph_type()
        self._clear(self.graph_dyn_inner)
        self._update_topology_visibility()
        self._populate_graph_fields(self.graph_dyn_inner, gt)

    def _update_topology_visibility(self, *_a):
        gt = self._current_graph_type()
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
            e = ttk.Entry(parent, width=COMPACT_NUM_WIDTH)
            e.grid(row=row, column=1, sticky="w", pady=pr)
            if tip:
                add_tooltip(lb, tip)
                add_tooltip(e, tip)
            row += 1
            return e

        def spin(t: str, tip: str, frm=0, to=10**9):
            nonlocal row
            lb = ttk.Label(parent, text=t, style=sty, wraplength=0)
            lb.grid(row=row, column=0, sticky="w", padx=lp, pady=pr)
            s = ttk.Spinbox(parent, from_=frm, to=to, width=COMPACT_NUM_WIDTH)
            s.grid(row=row, column=1, sticky="w", pady=pr)
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
        elif gt == "extended_barabasi":
            spin("n", "Number of nodes.")
            spin("m", "Edges to attach at each step.", 1, 10**6)
            lbl("p (0–1)", "Probability of attachment edge.")
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
                    font=(FONT_MONO, 10),
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
                se = ttk.Entry(parent, width=COMPACT_NUM_WIDTH)
                se.grid(row=row, column=1, sticky="w", pady=pr)
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
            "graph_type": self._current_graph_type(),
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
        return normalize_topology_graph_block(g)

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
            names = [
                str(g.get("graph_label") or f"Graph {i + 1}") for i, g in enumerate(self._topology_graphs)
            ]
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
            self.graph_type_var.set(graph_type_label(g.get("graph_type", GRAPH_TYPES[0])))
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
            try:
                self.root.update_idletasks()
            except tk.TclError:
                pass
            pv = g.get("param_values")
            if not pv or not any(str(x).strip() for x in pv):
                pv = extract_param_values_from_topology_block(g)
            self._apply_topology_param_values(list(pv or []))
            self._trace_field_map("topology.param_values", pv, "graph_dyn_inner (n, p, …)")
            self.validation_lbl.configure(text=g.get("validation_text", "Validation: —"))
            self._topology_refresh_graph_combo()
        finally:
            self._suspend_topology_graph_events = False

    def _topology_graph_index_from_combo(self, sel: str) -> int | None:
        s = str(sel or "").strip()
        if not s:
            return None
        for i, g in enumerate(self._topology_graphs):
            label = str(g.get("graph_label") or f"Graph {i + 1}")
            if label == s:
                return i
        try:
            return int(s.split()[-1]) - 1
        except (ValueError, IndexError):
            return None

    def _on_topology_graph_selected(self, _e=None) -> None:
        if self._suspend_topology_graph_events:
            return
        idx = self._topology_graph_index_from_combo(self.topology_graph_combo.get())
        if idx is None or idx < 0 or idx >= len(self._topology_graphs):
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

    def _sync_root_theme(self) -> None:
        import theme as t

        try:
            self.root.configure(bg=t.BG_MAIN)
        except tk.TclError:
            return
        if hasattr(self, "validation_lbl"):
            txt = str(self.validation_lbl.cget("text") or "")
            low = txt.lower()
            if "ok" in low and "issue" not in low:
                self.validation_lbl.configure(foreground=t.VALIDATION_SUCCESS)
            elif any(w in low for w in ("issue", "error", "invalid", "must", "failed")):
                self.validation_lbl.configure(foreground=t.VALIDATION_ERROR)
            else:
                self.validation_lbl.configure(foreground=t.VALIDATION_WARN)

    def _topology_reset(self):
        self._topology_graphs[self._topology_graph_idx] = default_topology_graph_block()
        self._topology_load_slot(self._topology_graph_idx)
        self.validation_lbl.configure(text="Validation: defaults applied (UI only).", foreground=VALIDATION_WARN)

    def _topology_validate(self):
        self._topology_save_current_to_slot()
        tp = self._topology_slot_from_ui()
        ok, msg = validate_ui_topology(tp)
        self.validation_lbl.configure(
            text=msg,
            foreground=VALIDATION_SUCCESS if ok else VALIDATION_ERROR,
        )
        self._topology_save_current_to_slot()

    # --- Experiment persistence, multi-exp switching, JSON I/O ---
    def _init_experiment_workspace(self) -> None:
        self._experiments.clear()
        self._experiment_order.clear()
        self._current_exp_name = None
        self._suspend_exp_sync = True
        self._apply_ui_state(default_experiment_state(""))
        self._suspend_exp_sync = False

    def _register_experiment_entry(self, key: str, state: dict[str, Any]) -> None:
        self._experiments[key] = state
        if key not in self._experiment_order:
            self._experiment_order.append(key)

    def _refresh_experiment_list(self, *, select_key: Optional[str] = None) -> None:
        """The sidebar experiment list was removed; the registry in
        self._experiments / self._experiment_order is still maintained."""

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
        from experiment_loader import _backend_assignment_to_ranges

        flat = _flatten_nested_profile(r) if isinstance(r, dict) else {}
        b = default_profile_state(1)
        b["title"] = str(flat.get("title", r.get("title", r.get("id", b["title"]))))
        b["description"] = str(r.get("description", flat.get("description", r.get("name", r.get("id", "")))))
        if flat.get("role") is not None:
            b["role"] = str(flat["role"])
        if flat.get("aggregation") is not None:
            b["aggregation"] = str(flat["aggregation"])
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
            if k in flat and flat[k] is not None:
                b[k] = str(flat[k])
        if flat.get("aggregation_minimum") is not None:
            b["agg_min"] = str(flat["aggregation_minimum"])
        if flat.get("group") is not None:
            b["group_id"] = str(flat["group"])
        mb = flat.get("minibatches", flat.get("mini_batches"))
        if mb is not None:
            b["minibatches"] = str(mb)
        metrics = flat.get("metrics")
        if isinstance(metrics, list):
            b["metrics"] = ", ".join(str(x) for x in metrics)
        elif metrics is not None:
            b["metrics"] = str(metrics)
        if "does_train" in flat:
            b["does_train"] = bool(flat["does_train"])
        if "is_sync" in flat:
            b["is_sync"] = bool(flat["is_sync"])
        if "checkpoint" in flat:
            b["checkpoint"] = bool(flat["checkpoint"])
        if isinstance(flat.get("assignment_ranges"), list):
            b["assignment_ranges"] = [
                [str(x) for x in (list(row) + ["", ""])[:2]] for row in flat["assignment_ranges"]
            ]
        elif isinstance(r.get("assignment"), list):
            b["assignment_ranges"] = _backend_assignment_to_ranges(r["assignment"])
        return b

    def _map_model_dict_to_gui(self, r: dict[str, Any]) -> dict[str, Any]:
        from experiment_loader import _backend_assignment_to_ranges

        flat = _flatten_nested_model(r) if isinstance(r, dict) else {}
        b = default_model_state(1)
        b["title"] = str(flat.get("title", r.get("title", r.get("id", b["title"]))))
        b["description"] = str(r.get("description", flat.get("description", "")))
        b["model_type"] = str(flat.get("model_type", flat.get("type", "")))
        b["optimizer"] = str(flat.get("optimizer", ""))
        b["lr"] = str(flat.get("lr", flat.get("learning_rate", "")))
        b["momentum"] = str(flat.get("momentum", ""))
        b["batch_size"] = str(flat.get("batch_size", flat.get("batchsize", "")))
        b["criterion"] = str(flat.get("criterion", ""))
        if isinstance(flat.get("assignment_ranges"), list):
            b["assignment_ranges"] = [
                [str(x) for x in (list(row) + ["", ""])[:2]] for row in flat["assignment_ranges"]
            ]
        elif isinstance(r.get("assignment"), list):
            b["assignment_ranges"] = _backend_assignment_to_ranges(r["assignment"])
        return b

    def _map_communication_card_to_gui(self, r: dict[str, Any], index: int = 1) -> dict[str, Any]:
        return normalize_communication_card(r, index)

    def _map_group_policy_card_to_gui(self, r: dict[str, Any], index: int = 1) -> dict[str, Any]:
        return normalize_group_policy_card(r, index)

    def _trace_field_map(self, json_key: str, json_value: Any, ui_field: str) -> None:
        line = f"JSON KEY: {json_key}\nJSON VALUE: {json_value!r}\nTARGET UI FIELD: {ui_field}\n"
        self._load_field_trace.append(line)
        _LOAD_LOGGER.debug(line)
        print(line)

    def _log_json_debug(self, title: str, data: Any) -> None:
        banner = f"\n{'-' * 34}\n{title}\n{'-' * 34}\n"
        body = pprint.pformat(data, width=120, compact=False, sort_dicts=False)
        block = banner + body + "\n"
        print(block)
        _LOAD_LOGGER.info(block)

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
        cc = _communication_cards_from_payload(raw)
        if cc is not None:
            state["communication_cards"] = [
                self._map_communication_card_to_gui(x, i + 1) for i, x in enumerate(cc) if isinstance(x, dict)
            ]
        gpc = _group_policy_cards_from_payload(raw)
        if gpc is not None:
            state["group_policy_cards"] = [
                self._map_group_policy_card_to_gui(x, i + 1) for i, x in enumerate(gpc) if isinstance(x, dict)
            ]

    def _read_experiment_yaml_file(self, path: Path) -> Any:
        return read_yaml_file(path)

    def read_config(self, path: Path) -> dict[str, Any]:
        raw = self._read_experiment_yaml_file(path)
        if not isinstance(raw, dict):
            raise ValueError(f"{path.name} must be a YAML mapping.")
        return raw

    def read_topology(self, path: Path) -> dict[str, Any]:
        raw = self._read_experiment_yaml_file(path)
        if not isinstance(raw, dict):
            raise ValueError(f"{path.name} must be a YAML mapping.")
        return self._coerce_topology_document(raw)

    def read_agents(self, path: Path) -> dict[str, Any]:
        raw = self._read_experiment_yaml_file(path)
        if not isinstance(raw, dict):
            raise ValueError(f"{path.name} must be a YAML mapping.")
        return raw

    def _coerce_topology_document(self, raw: dict[str, Any]) -> dict[str, Any]:
        doc = copy.deepcopy(raw)
        inner = doc.get("topology")
        if isinstance(inner, dict):
            base = copy.deepcopy(inner)
            if isinstance(doc.get("graphs"), list):
                base["graphs"] = copy.deepcopy(doc["graphs"])
            if "active_graph_index" in doc:
                base["active_graph_index"] = doc["active_graph_index"]
            doc = base
        out: dict[str, Any] = {
            "graphs": [],
            "active_graph_index": 0,
            **default_topology_graph_block(),
        }
        if isinstance(doc.get("graphs"), list) and doc["graphs"]:
            out["graphs"] = [self._topology_normalize_graph_block(g) for g in doc["graphs"] if isinstance(g, dict)]
            try:
                out["active_graph_index"] = int(doc.get("active_graph_index", 0))
            except (TypeError, ValueError):
                out["active_graph_index"] = 0
            ai = max(0, min(out["active_graph_index"], len(out["graphs"]) - 1))
            active = out["graphs"][ai]
            for k, v in active.items():
                out[k] = copy.deepcopy(v)
        else:
            self._merge_topology_file_payload(out, doc)
            if not isinstance(out.get("graphs"), list) or not out["graphs"]:
                block = self._topology_normalize_graph_block(out)
                out["graphs"] = [block]
                for k, v in block.items():
                    out[k] = copy.deepcopy(v)
        return out

    def _normalize_experiment_state(self, st: dict[str, Any]) -> dict[str, Any]:
        out = copy.deepcopy(st)
        tp = out.get("topology")
        if isinstance(tp, dict):
            if isinstance(tp.get("graphs"), list) and tp["graphs"]:
                graphs = [normalize_topology_graph_block(g) for g in tp["graphs"] if isinstance(g, dict)]
                try:
                    ai = int(tp.get("active_graph_index", 0))
                except (TypeError, ValueError):
                    ai = 0
                ai = max(0, min(ai, len(graphs) - 1))
                active = graphs[ai]
                out["topology"] = {**copy.deepcopy(tp), "graphs": graphs, "active_graph_index": ai, **active}
            else:
                out["topology"] = self._coerce_topology_document(tp)

        profs = out.get("profiles")
        if isinstance(profs, list) and profs:
            out["profiles"] = [self._map_profile_dict_to_gui(x) for x in profs if isinstance(x, dict)]
        else:
            out["profiles"] = [default_profile_state(1)]

        mods = out.get("models")
        if isinstance(mods, list) and mods:
            out["models"] = [self._map_model_dict_to_gui(x) for x in mods if isinstance(x, dict)]
        else:
            out["models"] = [default_model_state(1)]

        cc = out.get("communication_cards")
        if isinstance(cc, list) and cc:
            out["communication_cards"] = [
                self._map_communication_card_to_gui(x, i + 1) for i, x in enumerate(cc) if isinstance(x, dict)
            ]
        else:
            out["communication_cards"] = [default_communication_card(1)]

        gpc = out.get("group_policy_cards")
        if isinstance(gpc, list) and gpc:
            out["group_policy_cards"] = [
                self._map_group_policy_card_to_gui(x, i + 1) for i, x in enumerate(gpc) if isinstance(x, dict)
            ]
        else:
            out["group_policy_cards"] = [default_group_policy_card(1)]

        da = out.get("data_assignment")
        if not isinstance(da, dict):
            out["data_assignment"] = {"training": [], "validation": []}

        if isinstance(out.get("environment"), dict):
            base_env = default_experiment_state(str(out.get("name") or ""))["environment"]
            for k in base_env:
                if k in out["environment"] and out["environment"][k] is not None:
                    base_env[k] = str(out["environment"][k])
            out["environment"] = base_env
        else:
            out["environment"] = default_experiment_state(str(out.get("name") or ""))["environment"]

        return out

    def _merge_cards_from_sources(self, merged: dict[str, Any], *sources: dict[str, Any]) -> None:
        if not isinstance(merged.get("communication_cards"), list) or len(merged["communication_cards"]) <= 1:
            for src in sources:
                cc = _communication_cards_from_payload(src)
                if cc:
                    merged["communication_cards"] = cc
                    break
        if not isinstance(merged.get("group_policy_cards"), list) or len(merged["group_policy_cards"]) <= 1:
            for src in sources:
                gpc = _group_policy_cards_from_payload(src)
                if gpc:
                    merged["group_policy_cards"] = gpc
                    break

    def _load_experiment_from_folder(self, folder: Path) -> dict[str, Any]:
        loaded = loader_read_folder(folder)
        return self._normalize_experiment_state(to_gui_experiment_state(loaded))

    def _build_load_report(self, st: dict[str, Any]) -> tuple[list[str], list[str]]:
        ok: list[str] = []
        fail: list[str] = []
        env = st.get("environment") or {}

        env_ok = True
        for key, widget in (
            ("random_seed", self.env_seed),
            ("save_path", self.env_save_path),
            ("save_name", self.env_save_name),
            ("agent_assignment_path", self.env_agent_path),
            ("topology_assignment_path", self.env_topology_assign_path),
        ):
            expected = str(env.get(key, "")).strip()
            actual = widget.get().strip()
            if expected and expected != actual:
                env_ok = False
        if env_ok and (env.get("random_seed") or self.env_seed.get().strip()):
            ok.append("Environment")
        elif not env.get("random_seed") and not self.env_seed.get().strip():
            ok.append("Environment")
        else:
            fail.append("Environment")

        tp = st.get("topology") or {}
        graphs = tp.get("graphs") if isinstance(tp.get("graphs"), list) else []
        active = graphs[0] if graphs else tp
        expected_params = extract_param_values_from_topology_block(active if isinstance(active, dict) else {})
        ui_params = self._collect_topology_param_values()
        topo_ok = bool(str(self.graph_type_var.get()).strip())
        if topo_ok:
            ok.append("Topology")
        else:
            fail.append("Topology")
        if expected_params and any(str(x).strip() for x in expected_params):
            if [str(x) for x in ui_params[: len(expected_params)]] == [str(x) for x in expected_params[: len(ui_params)]]:
                ok.append("Topology Parameters")
            else:
                fail.append("Topology Parameters")
        elif topo_ok:
            ok.append("Topology Parameters")

        has_comm_data = any(
            isinstance(c, dict) and any(str(c.get(k, "")).strip() for k in COMM_FIELD_ALIASES)
            for c in (st.get("communication_cards") or [])
        )
        if has_comm_data:
            w0 = self._comm_tab_states[0]["widgets"] if self._comm_tab_states else {}
            loaded = any(w0.get(k) and str(w0[k].get()).strip() for k in COMM_FIELD_ALIASES if k in w0)
            (ok if loaded else fail).append("Communication Assignment")
        else:
            ok.append("Communication Assignment")

        gp_cards = st.get("group_policy_cards") or []
        has_gp = any(isinstance(c, dict) and (c.get("rounds") or c.get("assignment")) for c in gp_cards)
        if has_gp:
            ok.append("Group Policy Assignment")
        else:
            ok.append("Group Policy Assignment")

        if self._profile_tab_states:
            ok.append("Profiles")
        else:
            fail.append("Profiles")

        if self._model_tab_states:
            ok.append("Models")
        else:
            fail.append("Models")

        return ok, fail

    def _show_load_report(self, ok: list[str], fail: list[str]) -> None:
        lines = ["Experiment load report:", ""]
        if ok:
            lines.append("Successfully Loaded:")
            for item in ok:
                lines.append(f"  ✓ {item}")
        if fail:
            lines.append("")
            lines.append("Failed:")
            for item in fail:
                lines.append(f"  ✗ {item}")
        if self._load_field_trace:
            lines.append("")
            lines.append(f"Field mappings traced: {len(self._load_field_trace)} (see console)")
        messagebox.showinfo("Upload", "\n".join(lines))

    def populate_ui(self, st: dict[str, Any], *, validate_topology: bool = False, show_load_report: bool = False) -> None:
        self._load_field_trace = []
        normalized = self._normalize_experiment_state(st)

        def _finish_load() -> None:
            if validate_topology and hasattr(self, "validation_lbl"):
                self._topology_validate()
            if show_load_report:
                ok, fail = self._build_load_report(normalized)
                self._show_load_report(ok, fail)

        self._apply_ui_state(normalized)
        try:
            self.root.update_idletasks()
        except tk.TclError:
            pass
        if validate_topology or show_load_report:
            self.root.after_idle(_finish_load)

    def load_experiment(self, folder: str | Path) -> None:
        self._load_experiment_folder(Path(folder))

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
        gt = tj.get("graph_type") or tj.get("generator") or tj.get("type")
        if gt:
            topo["graph_type"] = str(gt)
        if "global_seed" in tj or "seed" in tj:
            topo["global_seed"] = str(tj.get("global_seed", tj.get("seed", "0")))
        merged_block = {**topo, **tj}
        extracted = extract_param_values_from_topology_block(merged_block)
        if extracted:
            topo["param_values"] = extracted
        elif isinstance(tj.get("param_values"), list):
            topo["param_values"] = [str(x) for x in tj["param_values"]]
        elif isinstance(tj.get("params"), list):
            topo["param_values"] = [str(x) for x in tj["params"]]
        if not isinstance(topo.get("graphs"), list) or not topo["graphs"]:
            topo["graphs"] = [self._topology_normalize_graph_block({**topo, **tj})]

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

    def _select_and_apply_loaded_experiment(self, key: str, *, show_load_report: bool = False) -> None:
        if key not in self._experiments:
            return
        self._current_exp_name = key
        self._suspend_exp_sync = True
        try:
            self._refresh_experiment_list(select_key=key)
            self.populate_ui(
                copy.deepcopy(self._experiments[key]),
                validate_topology=True,
                show_load_report=show_load_report,
            )
        except Exception as e:
            messagebox.showerror("Experiment", f"Could not load experiment into the UI:\n\n{e}")
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
                        tj = read_yaml_file(rp)
                        if isinstance(tj, dict):
                            if isinstance(tj.get("topology"), dict):
                                merge = copy.deepcopy(tj["topology"])
                                tp.update(merge)
                            self._merge_topology_file_payload(tp, tj)
                    except ValueError as e:
                        errs.append(f"Topology file has invalid YAML ({rp}):\n{e}")
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
                        aj = read_yaml_file(rp)
                        if isinstance(aj, dict):
                            self._apply_payload_normalization(state, aj)
                    except ValueError as e:
                        errs.append(f"Agent assignment file has invalid YAML ({rp}):\n{e}")
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
            "network_config": getattr(self, "_network_config", {}) or {},
        }

    def _collect_yaml_stack_snapshot(self) -> YamlStackSnapshot:
        return YamlStackSnapshot(
            driver_path=self._driver_file_path,
            driver_document=self._driver_document,
            topologies_path=self._topo_file_path,
            topologies_document=self._topo_document,
            assignments_path=self._assign_file_path,
            assignments_document=self._assign_document,
            definitions_path=self._defn_file_path,
            definitions_document=self._defn_document,
            network_path=self._net_file_path,
            network_document=self._net_document,
        )

    def _update_yaml_sync_source_labels(self, sources: dict[str, str]) -> None:
        mapping = (
            ("topology", "_exp_topo_source_lbl"),
            ("profiles", "_exp_profile_source_lbl"),
            ("models", "_exp_model_source_lbl"),
            ("network", "_exp_network_source_lbl"),
        )
        for key, attr in mapping:
            lbl = getattr(self, attr, None)
            if lbl is None:
                continue
            text = str(sources.get(key, "") or "").strip()
            try:
                lbl.configure(text=text)
            except tk.TclError:
                pass

    def _set_sync_widget_tree_readonly(self, parent: tk.Misc | None, readonly: bool) -> None:
        if parent is None:
            return
        skip = {
            getattr(self, "topology_graph_combo", None),
        }
        state = "disabled" if readonly else "normal"

        def _walk(widget: tk.Misc) -> None:
            if widget in skip:
                return
            if isinstance(widget, ttk.Button):
                try:
                    widget.configure(state=state)
                except tk.TclError:
                    pass
            elif isinstance(widget, (ttk.Entry, ttk.Spinbox)):
                try:
                    widget.configure(state=state)
                except tk.TclError:
                    pass
            elif isinstance(widget, ttk.Combobox):
                try:
                    if readonly:
                        widget.configure(state="disabled")
                    elif widget in (
                        getattr(self, "graph_type_combo", None),
                        getattr(self, "topology_graph_combo", None),
                    ):
                        widget.configure(state="readonly")
                    else:
                        widget.configure(state="normal")
                except tk.TclError:
                    pass
            elif isinstance(widget, tk.Text):
                try:
                    widget.configure(state="disabled" if readonly else "normal")
                except tk.TclError:
                    pass
            elif isinstance(widget, ttk.Checkbutton):
                try:
                    widget.configure(state=state)
                except tk.TclError:
                    pass
            for child in widget.winfo_children():
                _walk(child)

        _walk(parent)

    def _set_experiment_yaml_sync_readonly(self, readonly: bool) -> None:
        btn_state = "disabled" if readonly else "normal"
        for btn in getattr(self, "_exp_topo_buttons", []):
            try:
                btn.configure(state=btn_state)
            except tk.TclError:
                pass
        for btn in (
            getattr(self, "_exp_profile_add_btn", None),
            getattr(self, "_exp_profile_remove_btn", None),
            getattr(self, "_exp_model_add_btn", None),
            getattr(self, "_exp_model_remove_btn", None),
        ):
            if btn is not None:
                try:
                    btn.configure(state=btn_state)
                except tk.TclError:
                    pass
        self._set_sync_widget_tree_readonly(getattr(self, "_exp_topo_form", None), readonly)
        self._set_sync_widget_tree_readonly(getattr(self, "profile_stack", None), readonly)
        self._set_sync_widget_tree_readonly(getattr(self, "model_stack", None), readonly)
        if readonly and hasattr(self, "topology_graph_combo"):
            try:
                self.topology_graph_combo.configure(state="readonly")
            except tk.TclError:
                pass

    def _apply_yaml_stack_topology_preview(self, topology: dict[str, Any]) -> None:
        tp = topology if isinstance(topology, dict) else {}
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

    def _apply_yaml_stack_preview(self, preview: dict[str, Any]) -> None:
        self._suspend_exp_sync = True
        try:
            if "topology" in preview:
                self._apply_yaml_stack_topology_preview(preview["topology"])
            if "profiles" in preview:
                profiles = preview["profiles"] or [default_profile_state(1)]
                self._rebuild_profile_tabs(profiles)
            if "models" in preview:
                models = preview["models"] or [default_model_state(1)]
                self._rebuild_model_tabs(models)
            if "network_config" in preview:
                self._rebuild_network_fields(preview.get("network_config"))
            self._update_yaml_sync_source_labels(preview.get("sources") or {})
            self._set_experiment_yaml_sync_readonly(True)
            self._yaml_stack_sync_active = True
        finally:
            self._suspend_exp_sync = False

    def _sync_experiment_from_yaml_stack(self) -> None:
        if self._driver_file_path is None:
            return
        snapshot = self._collect_yaml_stack_snapshot()
        preview = build_experiment_preview(snapshot)
        self._apply_yaml_stack_preview(preview)
        self._refresh_run_config_preview()

    def _maybe_refresh_experiment_yaml_sync(self) -> None:
        if self._batch_stack_refresh:
            return
        if not getattr(self, "_yaml_stack_sync_active", False):
            return
        self._sync_experiment_from_yaml_stack()

    def _set_legacy_experiment_source_labels(self, folder: Path) -> None:
        self._update_yaml_sync_source_labels(
            {
                "topology": f"Source: {folder.name}/topology.yaml",
                "profiles": f"Source: {folder.name}/agent_assignment.yaml",
                "models": f"Source: {folder.name}/agent_assignment.yaml",
                "network": f"Source: {folder.name}/network.yaml",
            }
        )

    def _apply_ui_state(self, st: dict[str, Any]) -> None:
        env = st.get("environment", {})
        self.experiment_name_var.set(st.get("name", ""))
        self._trace_field_map("name", st.get("name"), "experiment_name_var")

        seed_val = str(env.get("random_seed", "0"))
        self.env_seed.delete(0, tk.END)
        self.env_seed.insert(0, seed_val)
        self._trace_field_map("environment.random_seed", seed_val, "env_seed")
        for w, key in (
            (self.env_save_path, "save_path"),
            (self.env_save_name, "save_name"),
            (self.env_agent_path, "agent_assignment_path"),
            (self.env_topology_assign_path, "topology_assignment_path"),
        ):
            val = str(env.get(key, ""))
            w.delete(0, tk.END)
            w.insert(0, val)
            self._trace_field_map(f"environment.{key}", val, key)

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
        active_g = self._topology_graphs[want_idx]
        self._trace_field_map("topology.graph_type", active_g.get("graph_type"), "graph_type_combo")
        self._trace_field_map("topology.global_seed", active_g.get("global_seed"), "global_seed_spin")
        self._trace_field_map("topology.param_values", active_g.get("param_values"), "graph_dyn_inner")
        self._topology_load_slot(want_idx)

        comm_cards = st.get("communication_cards") or [default_communication_card(1)]
        self._rebuild_communication_tabs(comm_cards)
        for i, card in enumerate(comm_cards):
            if not isinstance(card, dict):
                continue
            for fk in COMM_FIELD_ALIASES:
                if fk in card and str(card.get(fk, "")).strip():
                    self._trace_field_map(f"communication[{i}].{fk}", card.get(fk), f"comm_card_{i}.{fk}")

        gp_cards = st.get("group_policy_cards") or [default_group_policy_card(1)]
        self._rebuild_group_policy_tabs(gp_cards)
        for i, card in enumerate(gp_cards):
            if not isinstance(card, dict):
                continue
            if card.get("rounds"):
                self._trace_field_map(f"group_policy[{i}].rounds", card.get("rounds"), f"gp_card_{i}.rounds")
            if card.get("assignment"):
                self._trace_field_map(f"group_policy[{i}].assignment", card.get("assignment"), f"gp_card_{i}.assignment")

        profiles = st.get("profiles") or [default_profile_state(1)]
        self._rebuild_profile_tabs(profiles)
        for i, p in enumerate(profiles):
            if isinstance(p, dict):
                for fk in ("role", "aggregation", "wait_time", "description"):
                    if fk in p:
                        self._trace_field_map(f"profiles[{i}].{fk}", p.get(fk), f"profile_tab_{i}.{fk}")

        models = st.get("models") or [default_model_state(1)]
        self._rebuild_model_tabs(models)
        for i, m in enumerate(models):
            if isinstance(m, dict):
                for fk in ("model_type", "lr", "optimizer", "description"):
                    if fk in m:
                        self._trace_field_map(f"models[{i}].{fk}", m.get(fk), f"model_tab_{i}.{fk}")

        self._rebuild_network_fields(st.get("network_config"))

        self._apply_data_assignment_state(st.get("data_assignment") or {"training": [], "validation": []})

    def _experiment_upload(self) -> None:
        initial = str(self._last_exp_file_dir) if self._last_exp_file_dir else None
        folder = filedialog.askdirectory(title="Load Experiment Folder", initialdir=initial)
        if not folder:
            return
        self._load_experiment_folder(Path(folder))

    def _sanitize_experiment_folder_name(self, name: str) -> str:
        s = re.sub(r'[<>:"/\\|?*]+', "_", name.strip())
        s = re.sub(r"\s+", "_", s).strip("._")
        return s or "Experiment_unnamed"

    def _topology_state_for_export(self, topology: dict[str, Any]) -> dict[str, Any]:
        return export_topology_for_save(topology)

    def _write_experiment_files(self, exp_dir: Path, st: dict[str, Any]) -> None:
        st_name = str(st.get("name") or exp_dir.name)
        st["name"] = st_name
        topo_export = self._topology_state_for_export(st.get("topology") or {})
        io_write_experiment_files(
            exp_dir,
            st,
            topology_export=topo_export,
            default_environment=default_experiment_state(st_name)["environment"],
        )

    def _experiment_save(self) -> None:
        self._snapshot_current_ui_to_store()
        self._open_save_as_dialog()

    def _open_save_as_dialog(self) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title("Save As")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        dlg.grab_set()
        try:
            dlg.configure(bg=BG_MAIN)
        except tk.TclError:
            pass

        st = self._collect_ui_state()
        default_name = (
            self.experiment_name_var.get().strip()
            or str(st.get("name") or "").strip()
            or "Experiment_1"
        )
        initial_parent = self._last_exp_file_dir.parent if self._last_exp_file_dir else Path.home()

        outer = ttk.Frame(dlg, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(1, weight=1)

        ttk.Label(outer, text="Save Experiment As", style="Subsection.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 12)
        )
        ttk.Label(outer, text="Experiment Name:", style="TLabel").grid(row=1, column=0, sticky="w", pady=4)
        v_name = tk.StringVar(value=default_name)
        ttk.Entry(outer, textvariable=v_name, width=40).grid(row=1, column=1, columnspan=2, sticky="ew", pady=4)

        ttk.Label(outer, text="Location:", style="TLabel").grid(row=2, column=0, sticky="w", pady=4)
        v_loc = tk.StringVar(value=str(initial_parent))
        loc_entry = ttk.Entry(outer, textvariable=v_loc, width=34)
        loc_entry.grid(row=2, column=1, sticky="ew", pady=4)

        def _browse() -> None:
            chosen = filedialog.askdirectory(
                title="Choose Save Location",
                initialdir=v_loc.get() or str(initial_parent),
            )
            if chosen:
                v_loc.set(chosen)

        ttk.Button(outer, text="Browse…", command=_browse).grid(row=2, column=2, sticky="w", padx=(8, 0), pady=4)

        bf = ttk.Frame(outer)
        bf.grid(row=3, column=0, columnspan=3, sticky="e", pady=(16, 0))

        def _do_save() -> None:
            parent = Path(v_loc.get().strip()).expanduser()
            folder_name = self._sanitize_experiment_folder_name(v_name.get())
            if not folder_name:
                messagebox.showerror("Save", "Enter a valid experiment name.", parent=dlg)
                return
            if not str(parent):
                messagebox.showerror("Save", "Choose a save location.", parent=dlg)
                return
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                messagebox.showerror("Save", f"Could not create location:\n{parent}\n\n{e}", parent=dlg)
                return
            if not parent.is_dir():
                messagebox.showerror("Save", f"Location is not a folder:\n{parent}", parent=dlg)
                return

            exp_dir = parent / folder_name
            out_st = self._collect_ui_state()
            out_st["name"] = v_name.get().strip() or folder_name

            if exp_dir.exists():
                if not messagebox.askyesno(
                    "Save",
                    f"Folder already exists:\n{exp_dir}\n\nOverwrite its experiment files?",
                    parent=dlg,
                ):
                    return
            else:
                try:
                    exp_dir.mkdir(parents=True, exist_ok=False)
                except OSError as e:
                    messagebox.showerror("Save", f"Could not create folder:\n{exp_dir}\n\n{e}", parent=dlg)
                    return

            try:
                self._write_experiment_files(exp_dir, out_st)
            except OSError as e:
                messagebox.showerror("Save", f"Could not write experiment files:\n{e}", parent=dlg)
                return

            key = str(exp_dir.resolve())
            self._last_exp_file_dir = exp_dir
            self._register_experiment_entry(key, out_st)
            self._select_and_apply_loaded_experiment(key)
            dlg.grab_release()
            dlg.destroy()
            messagebox.showinfo("Save As", f"Experiment saved successfully.\n\n{exp_dir}")

        ttk.Button(bf, text="Save", style="Accent.TButton", command=_do_save).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bf, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT)

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
        folder = folder.resolve()
        missing = missing_required_files(folder)
        if missing:
            if len(missing) == 1:
                messagebox.showerror("Upload", f"Missing required file:\n\n{missing[0]}")
            else:
                messagebox.showerror(
                    "Upload",
                    "Experiment folder is missing required files:\n\n"
                    + "\n".join(missing)
                    + f"\n\nFolder:\n{folder}",
                )
            return
        try:
            self._snapshot_current_ui_to_store()
            merged = self._load_experiment_from_folder(folder)
        except ValueError as e:
            messagebox.showerror("Upload", str(e))
            return
        except Exception as e:
            messagebox.showerror("Upload", f"Unexpected error loading experiment:\n\n{e}")
            return

        key = str(folder)
        self._last_exp_file_dir = folder
        self._experiments[key] = merged
        if key not in self._experiment_order:
            self._experiment_order.append(key)
        self._select_and_apply_loaded_experiment(key, show_load_report=True)
        self._yaml_stack_sync_active = False
        self._experiment_instances_active = False
        self._clear_experiment_instances()
        self._set_experiment_yaml_sync_readonly(False)
        self._set_legacy_experiment_source_labels(folder)

    # --- Model assignment (stacked cards) ---
    def _build_model_assignment_panel(self, parent, *, grid: CardGrid | None = None):
        outer, inner = _make_panel(parent, "Model Assignment", plain_inner=True)
        _mount_panel(outer, grid)

        self._exp_model_source_lbl = ttk.Label(
            inner,
            text="",
            style="TLabel",
            foreground=MUTED_TEXT,
            wraplength=520,
            justify=tk.LEFT,
        )
        self._exp_model_source_lbl.pack(fill=tk.X, anchor="w", pady=(0, 4))
        bar = ttk.Frame(inner, style="Inner.TFrame")
        bar.pack(fill=tk.X, pady=(0, GUTTER))
        self._exp_model_add_btn = ttk.Button(bar, text="Add Model", command=self._model_add_tab)
        self._exp_model_add_btn.pack(side=tk.LEFT)
        self._exp_model_remove_btn = ttk.Button(
            bar, text="Remove model", style="Small.TButton", command=self._model_remove_tab
        )
        self._exp_model_remove_btn.pack(side=tk.LEFT, padx=(GUTTER, 0))

        self.model_stack = ttk.Frame(inner, style="Inner.TFrame")
        self.model_stack.pack(fill=tk.X)
        self.model_notebook = ttk.Notebook(self.model_stack)
        self.model_notebook.pack(fill=tk.X)
        self.model_notebook.bind("<<NotebookTabChanged>>", self._on_model_notebook_tab)
        self._model_tab_states: list[dict[str, Any]] = []
        self._model_active_idx = 0

    def _fill_model_tab(self, lf: ttk.Frame, state: dict[str, Any] | None) -> dict[str, Any]:
        for c in (0, 1):
            lf.columnconfigure(c * 2, weight=0)
            lf.columnconfigure(c * 2 + 1, weight=1)
        w: dict[str, Any] = {}
        g = {"row": 0, "col": 0}

        def _flush() -> None:
            if g["col"] != 0:
                g["row"] += 1
                g["col"] = 0

        def _place(label: str, widget: Any, *, tip: str = "", full: bool = False) -> None:
            if full:
                _flush()
            c = g["col"]
            ttk.Label(lf, text=label, style="TLabel", wraplength=LABEL_WRAP, justify=tk.LEFT).grid(
                row=g["row"], column=c * 2, sticky="nw", padx=(0 if c == 0 else 16, 8), pady=2
            )
            widget.grid(row=g["row"], column=c * 2 + 1, columnspan=3 if full else 1, sticky="w", pady=2)
            if tip:
                add_tooltip(widget, tip)
            if full:
                g["row"] += 1
                g["col"] = 0
            else:
                g["col"] += 1
                if g["col"] >= 2:
                    g["row"] += 1
                    g["col"] = 0

        ed = ttk.Entry(lf, width=COMPACT_NAME_WIDTH)
        _place("Description:", ed, full=True)
        w["description"] = ed
        mt = ttk.Combobox(lf, values=("", "MNISTNN", "CIFAR_CNN", "ResNet18", "custom"), width=COMPACT_COMBO_WIDTH)
        _place("Model type:", mt)
        w["model_type"] = mt
        op = ttk.Combobox(lf, values=("", "sgd", "adam", "adamw", "rmsprop"), width=COMPACT_COMBO_WIDTH, state="readonly")
        _place("Optimizer:", op)
        w["optimizer"] = op
        for lab, key, tip in (
            ("Learning rate (float):", "lr", "Step size for weight updates."),
            ("Momentum (float):", "momentum", "SGD momentum coefficient."),
            ("Batch size (int):", "batch_size", "Samples per mini-batch."),
        ):
            e = ttk.Entry(lf, width=COMPACT_NUM_WIDTH)
            _place(lab, e, tip=tip)
            w[key] = e
        cr = ttk.Combobox(lf, values=("", "cel", "mse", "bce"), width=COMPACT_COMBO_WIDTH, state="readonly")
        _place("Criterion:", cr)
        w["criterion"] = cr
        _flush()
        r = g["row"]
        sub = ttk.Frame(lf, style="Inner.TFrame")
        sub.grid(row=r, column=0, columnspan=4, sticky="ew", pady=(8, 0))
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
        holder.pack(fill=tk.X)
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

    def _build_network_panel(self, parent, *, grid: CardGrid | None = None) -> None:
        outer, inner = _make_panel(parent, "Network Configuration", plain_inner=True)
        _mount_panel(outer, grid)

        self._exp_network_source_lbl = ttk.Label(
            inner,
            text="",
            style="TLabel",
            foreground=MUTED_TEXT,
            wraplength=520,
            justify=tk.LEFT,
        )
        self._exp_network_source_lbl.pack(fill=tk.X, anchor="w", pady=(0, 4))

        self._network_host = ttk.Frame(inner, style="Inner.TFrame")
        self._network_host.pack(fill=tk.X)
        self._network_config: dict[str, Any] = {}
        self._network_empty_lbl = ttk.Label(
            self._network_host,
            text="No network.yaml loaded. Upload an experiment folder that includes network.yaml.",
            style="TLabel",
            foreground=MUTED_TEXT,
            wraplength=520,
            justify=tk.LEFT,
        )
        self._network_empty_lbl.pack(anchor="w")

    def _rebuild_network_fields(self, network: dict[str, Any] | None) -> None:
        if not hasattr(self, "_network_host"):
            return
        for w in self._network_host.winfo_children():
            w.destroy()
        self._network_config = network if isinstance(network, dict) else {}
        rows = flatten_mapping_for_display(self._network_config)
        if not rows:
            ttk.Label(
                self._network_host,
                text="No network.yaml loaded. Upload an experiment folder that includes network.yaml.",
                style="TLabel",
                foreground=MUTED_TEXT,
                wraplength=520,
                justify=tk.LEFT,
            ).pack(anchor="w")
            return
        grid = ttk.Frame(self._network_host, style="Inner.TFrame")
        grid.pack(fill=tk.X)
        grid.columnconfigure(1, weight=1)
        for r, (path, value) in enumerate(rows):
            ttk.Label(grid, text=f"{path}:", style="TLabel", wraplength=220, justify=tk.LEFT).grid(
                row=r, column=0, sticky="nw", padx=(0, 10), pady=3
            )
            e = ttk.Entry(grid, width=42)
            e.insert(0, value)
            e.configure(state="readonly")
            e.grid(row=r, column=1, sticky="ew", pady=3)

    def _build_data_assignment_panel(self, parent, *, grid: CardGrid | None = None):
        outer, inner = _make_panel(parent, "Data Assignment", green=True, plain_inner=True)
        _mount_panel(outer, grid)

        host = ttk.Frame(inner, style="InnerGreen.TFrame")
        host.pack(fill=tk.X)

        self._data_training_entries: list[dict[str, Any]] = []
        self._data_validation_entries: list[dict[str, Any]] = []

        def make_section(title: str, bucket: list[dict[str, Any]], nb_attr: str) -> None:
            sec = ttk.Frame(host, style="InnerGreen.TFrame")
            sec.pack(fill=tk.X, pady=(0, GUTTER))
            ttk.Label(sec, text=title, style="SubsectionGreen.TLabel").pack(anchor="w", pady=(0, 6))
            nb = ttk.Notebook(sec)
            nb.pack(fill=tk.X)
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

    def _build_notes_panel(self, parent, *, grid: CardGrid | None = None):
        outer, inner = _make_panel(parent, "Notes", green=True, plain_inner=True)
        _mount_panel(outer, grid)

        self.notes_text = tk.Text(
            inner,
            height=14,
            wrap=tk.WORD,
            bg=INPUT_BG,
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=INPUT_BORDER,
            font=(FONT_FAMILY, FONT_PT_BASE),
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
        try:
            win.configure(bg=BG_MAIN)
        except tk.TclError:
            pass

        outer = ttk.Frame(win, padding=(16, 14))
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(outer, text="Settings", style="HeaderBlue.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        row += 1

        ttk.Label(outer, text="Theme", style="Subsection.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )
        row += 1

        v_preset = tk.StringVar(value=SESSION.preset)
        ttk.Label(outer, text="Color theme:", style="TLabel").grid(row=row, column=0, sticky="nw", pady=2)
        ttk.Combobox(
            outer,
            textvariable=v_preset,
            values=list(PRESET_ORDER),
            state="readonly",
            width=28,
        ).grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        os_mode = appearance_label(detect_os_appearance())
        theme_hint = ttk.Label(
            outer,
            text=f"OS appearance: {os_mode}. “Follow System” updates when your OS theme changes.",
            style="TLabel",
            wraplength=360,
        )
        theme_hint.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
        row += 1

        ttk.Label(outer, text="Visualization", style="Subsection.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )
        row += 1

        v_viz = tk.BooleanVar(value=SETTINGS.visualization_enabled)
        ttk.Checkbutton(outer, text="Enable Visualization Effects", variable=v_viz).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )
        row += 1

        ttk.Label(
            outer,
            text="Enable or disable node/edge highlighting and graph animation during simulation execution.",
            style="TLabel",
            foreground=MUTED_TEXT,
            wraplength=360,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
        row += 1

        bf = ttk.Frame(outer)
        bf.grid(row=row, column=0, columnspan=2, sticky="w", pady=(4, 0))

        def _apply() -> None:
            apply_simulation_ui_settings(visualization_enabled=bool(v_viz.get()))
            ps = v_preset.get()
            if ps not in PRESET_ORDER:
                ps = SESSION.preset
            apply_session(AppearanceSession(preset=ps))
            start_system_theme_watch(self.root)
            try:
                self.root.configure(bg=BG_MAIN)
            except tk.TclError:
                pass
            theme_hint.configure(
                text=f"OS appearance: {appearance_label(detect_os_appearance())}. Active preset: {ps}."
            )

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
                raise ValueError(f"{label} must be an integer (got {_s(x)!r}).")
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
                    for key in ("latency_prob", "dropout_prob"):
                        v = _s(c.get(key, ""))
                        if not v:
                            continue
                        try:
                            p = float(v)
                        except Exception:
                            return False, f"Communication {i+1}: {key} must be numeric."
                        if not (0.0 <= p <= 1.0):
                            return False, f"Communication {i+1}: {key} must be between 0 and 1."
                    for key in ("latency_min", "latency_max"):
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
                profile_numeric_fields = set(PROFILE_FIELD_LABELS.keys())
                for i, p in enumerate(profiles):
                    if not isinstance(p, dict):
                        continue
                    for key in profile_numeric_fields:
                        err = profile_field_error(i, key, p.get(key, ""))
                        if err:
                            return False, err
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
                for i, m in enumerate(models):
                    if not isinstance(m, dict):
                        continue
                    for key in ("lr", "momentum"):
                        err = model_field_error(i, key, m.get(key, ""))
                        if err:
                            return False, err
                    err = model_field_error(i, "batch_size", m.get("batch_size", ""), min_positive=True)
                    if err:
                        return False, err

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

    def _validate_experiment_state_for_run(self, state: dict[str, Any]) -> tuple[bool, str]:
        """Validate legacy Page 2 numeric/policy fields on the state that will run."""
        ok, msg = self._validate_page1_inputs(state)
        if not ok:
            return False, msg

        topo_eff = effective_topology_for_run(state)
        ok_top, vmsg = validate_ui_topology(topo_eff)
        if not ok_top:
            return False, f"Topology validation failed:\n{vmsg}"

        ok_pol, pol_warns = validate_run_policies(state)
        if not ok_pol:
            return False, "Policy validation failed:\n\n" + "\n".join(f"• {w}" for w in pol_warns[:20])

        return True, ""

    def _open_run_window(
        self,
        *,
        experiment_state: dict[str, Any],
        experiment_name: str,
        run_configuration: RunConfiguration | None = None,
        experiment_instance: ExperimentInstance | None = None,
        experiment_instances: list[ExperimentInstance] | None = None,
    ) -> None:
        """Open Page 2 (RunWindow) after validation succeeds."""
        win = self._run_window
        if win is not None:
            try:
                if win.winfo_exists():
                    win.lift()
                    win.focus_force()
                    return
            except tk.TclError:
                pass
            self._run_window = None

        self._run_window = RunWindow(
            self.root,
            experiment_name=experiment_name,
            experiment_state=copy.deepcopy(experiment_state),
            execution_context=self._collect_execution_context(),
            get_execution_context=self._collect_execution_context,
            run_configuration=run_configuration,
            experiment_instance=experiment_instance,
            experiment_instances=list(experiment_instances or []),
        )

    def _ask_execution_mode(self, command_for_mode: Callable[[str], str]) -> str | None:
        """
        Modal Run dialog: choose execution mode and preview the orchestrator command.

        Returns the selected mode key ('local' / 'remote') on Continue, or None on Cancel.
        Display only — nothing is executed.
        """
        dlg = tk.Toplevel(self.root)
        dlg.title("Run")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        dlg.grab_set()
        try:
            dlg.configure(bg=BG_MAIN)
        except tk.TclError:
            pass

        outer = ttk.Frame(dlg, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)

        ttk.Label(outer, text="Execution Mode", style="Subsection.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        initial = SETTINGS.execution_mode if SETTINGS.execution_mode in ("local", "remote") else "local"
        mode_var = tk.StringVar(value=initial)

        ttk.Label(outer, text="Command:", style="TLabel").grid(row=3, column=0, sticky="w", pady=(10, 4))
        cmd_holder = tk.Frame(outer, bg=INPUT_BG, highlightbackground=INPUT_BORDER, highlightthickness=1)
        cmd_holder.grid(row=4, column=0, sticky="ew")
        cmd_holder.columnconfigure(0, weight=1)
        cmd_text = tk.Text(
            cmd_holder,
            height=3,
            width=78,
            wrap=tk.WORD,
            bg=INPUT_BG,
            fg=TEXT_MAIN,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            font=(FONT_MONO, max(8, FONT_PT_BASE - 1)),
            state=tk.DISABLED,
        )
        cmd_text.grid(row=0, column=0, sticky="ew", padx=6, pady=6)

        def _update_command() -> None:
            cmd = command_for_mode(mode_var.get()).strip() or "(no command available)"
            try:
                cmd_text.configure(state=tk.NORMAL)
                cmd_text.delete("1.0", tk.END)
                cmd_text.insert("1.0", cmd)
                cmd_text.configure(state=tk.DISABLED)
            except tk.TclError:
                pass

        ttk.Radiobutton(outer, text="Local", value="local", variable=mode_var, command=_update_command).grid(
            row=1, column=0, sticky="w"
        )
        ttk.Radiobutton(outer, text="Remote", value="remote", variable=mode_var, command=_update_command).grid(
            row=2, column=0, sticky="w", pady=(2, 0)
        )

        result: dict[str, str | None] = {"mode": None}

        def _continue() -> None:
            result["mode"] = mode_var.get()
            dlg.destroy()

        def _cancel() -> None:
            dlg.destroy()

        btns = ttk.Frame(outer)
        btns.grid(row=5, column=0, sticky="e", pady=(14, 0))
        ttk.Button(btns, text="Continue", style="Accent.TButton", command=_continue).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btns, text="Cancel", command=_cancel).pack(side=tk.LEFT)

        dlg.protocol("WM_DELETE_WINDOW", _cancel)
        _update_command()
        dlg.wait_window()
        return result["mode"]

    def _on_run_clicked(self) -> None:
        """Validate configuration, ask for execution mode, then open the run window."""
        if self._driver_file_path is None:
            try:
                state = self._get_active_experiment_state()
            except (tk.TclError, OSError, ValueError, TypeError) as e:
                messagebox.showerror("Run", f"Could not read current experiment state:\n{e}")
                return

            ok, msg = self._validate_experiment_state_for_run(state)
            if not ok:
                messagebox.showerror("Run", msg)
                return

            def _legacy_command_for_mode(mode: str) -> str:
                ctx = self._collect_execution_context()
                ctx.mode = mode
                return prepare_command_preview_legacy(ctx).command

            mode = self._ask_execution_mode(_legacy_command_for_mode)
            if mode is None:
                return
            set_execution_mode(mode)

            legacy = prepare_command_preview_legacy(self._collect_execution_context())
            if legacy.valid:
                self._generated_command = legacy.command
                self._command_preview_result = legacy
                self._set_command_preview_text(legacy.command)
            else:
                self._generated_command = ""
                self._command_preview_result = None
                self._set_command_preview_text("")
            name = str(state.get("name") or self.experiment_name_var.get().strip() or "Experiment")
            self._open_run_window(experiment_state=state, experiment_name=name)
            return

        stack_errors = validate_yaml_stack(self._collect_yaml_stack_snapshot())
        if stack_errors:
            messagebox.showerror(
                "Run",
                "Fix YAML configuration issues before running:\n\n"
                + "\n".join(f"• {e}" for e in stack_errors[:20])
                + (f"\n\n… and {len(stack_errors) - 20} more." if len(stack_errors) > 20 else ""),
            )
            return

        active_instance_id: int | None = None
        if self._experiment_instances and 0 <= self._experiment_instance_index < len(self._experiment_instances):
            active_instance_id = self._experiment_instances[self._experiment_instance_index].instance_number

        preview = prepare_command_preview(
            self._collect_run_stack_snapshot(),
            mode=SETTINGS.execution_mode,
            export_dir=self._manifest_export_dir if self._manifest_export_dir and self._manifest_export_dir.is_dir() else None,
            driver_root=self._driver_file_path.parent,
            active_instance_id=active_instance_id,
        )

        if not preview.valid:
            self._generated_command = ""
            self._command_preview_result = None
            self._set_command_preview_text("")
            messagebox.showerror(
                "Run",
                "Fix the following before running:\n\n"
                + "\n".join(f"• {e}" for e in preview.errors[:20])
                + (f"\n\n… and {len(preview.errors) - 20} more." if len(preview.errors) > 20 else ""),
            )
            self._refresh_run_config_preview()
            return

        def _command_for_mode(mode: str) -> str:
            if preview.export_dir is not None and preview.execution_requests:
                return build_orchestrator_command_from_requests(
                    driver_path=self._driver_file_path,
                    export_dir=preview.export_dir,
                    execution_requests=preview.execution_requests,
                    mode=mode,
                    active_instance_id=active_instance_id,
                )
            return preview.command

        mode = self._ask_execution_mode(_command_for_mode)
        if mode is None:
            return
        set_execution_mode(mode)
        final_command = _command_for_mode(mode)

        self._command_preview_result = preview
        self._generated_command = final_command
        self._run_configuration = preview.run_configuration
        if preview.run_configuration is not None:
            self._experiment_instances = build_experiment_instances(preview.run_configuration)
            self._experiment_instances_active = True
            if self._experiment_instances:
                idx = max(0, min(self._experiment_instance_index, len(self._experiment_instances) - 1))
                self._apply_experiment_instance_index(idx)
        if preview.export_dir is not None:
            self._manifest_export_dir = preview.export_dir
        self._set_command_preview_text(final_command)
        self._refresh_run_config_preview()
        self._refresh_execution_preview()

        try:
            state = self._get_active_experiment_state()
        except (tk.TclError, OSError, ValueError, TypeError) as e:
            messagebox.showerror("Run", f"Could not read current experiment state:\n{e}")
            return

        ok, msg = self._validate_experiment_state_for_run(state)
        if not ok:
            messagebox.showerror("Run", msg)
            return

        name = str(state.get("name") or self.experiment_name_var.get().strip() or "Experiment")
        active_instance: ExperimentInstance | None = None
        if self._experiment_instances and 0 <= self._experiment_instance_index < len(self._experiment_instances):
            active_instance = self._experiment_instances[self._experiment_instance_index]

        self._open_run_window(
            experiment_state=state,
            experiment_name=name,
            run_configuration=self._run_configuration,
            experiment_instance=active_instance,
            experiment_instances=self._experiment_instances,
        )

    def run(self):
        self.root.mainloop()


def main():
    desktop = MainWindow()
    desktop.run()


if __name__ == "__main__":
    main()
