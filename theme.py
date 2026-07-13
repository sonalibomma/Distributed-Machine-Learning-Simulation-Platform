import tkinter as tk
from tkinter import ttk
from typing import Any


BG_MAIN = "#0F172A"
PANEL_BLUE = "#1E293B"
PANEL_GREEN = "#1E293B"
HEADER_GREEN = "#1E293B"
HEADER_BLUE = "#1E293B"
HEADER_FG = "#3B82F6"
BORDER = "#334155"
BORDER_INNER = "#293548"
INPUT_BG = "#0F172A"
LIST_SURFACE_BG = "#0F172A"
INPUT_BORDER = "#475569"
TEXT_MAIN = "#F8FAFC"
BTN_PRIMARY_BG = "#2563EB"
BTN_PRIMARY_HOVER = "#1D4ED8"
BTN_SECONDARY_BG = "#334155"
BTN_SECONDARY_HOVER = "#475569"
BTN_DANGER_BG = "#EF4444"
BTN_DANGER_HOVER = "#DC2626"
PROGRESS_BAR = "#3B82F6"
PROGRESS_TROUGH = "#252B36"
ACCENT = "#3B82F6"
GRAPH_AREA_BG = "#0F172A"
GRAPH_AREA_FG = "#F8FAFC"
SUMMARY_BG = "#1E293B"
SCROLLBAR_TRACK = "#1E293B"
SCROLLBAR_THUMB = "#475569"
TOOLTIP_BG = "#1E293B"
MUTED_TEXT = "#94A3B8"
VALIDATION_SUCCESS = "#16A34A"
VALIDATION_WARN = "#F97316"
VALIDATION_ERROR = "#DC2626"
TAB_BUTTON_BG = "#252830"
TAB_BUTTON_HOVER = "#353945"
GRAPH_NODE_BASE = "#4A90E2"
GRAPH_NODE_ACTIVE = "#22C55E"
GRAPH_COMM = "#8B5CF6"
GRAPH_NODE_SENDER = "#F97316"
GRAPH_NODE_RECEIVER = "#8B5CF6"
GRAPH_NODE_DROPOUT = "#DC2626"
GRAPH_NODE_INTERRUPT = "#9CA3AF"
GRAPH_NODE_AGGREGATION = "#7C3AED"
GRAPH_EDGE_BASE = "#9CA3AF"
GRAPH_EDGE_ACTIVE = "#4A90E2"
GRAPH_EDGE_DROPOUT = "#DC2626"
GRAPH_EDGE_DELIVERY = "#F97316"
LOG_SUCCESS = "#16A34A"
LOG_ERROR = "#DC2626"
NOTEBOOK_TAB_SELECTED_FG = "#F8FAFC"

FONT_PT_BASE = 12
FONT_PT_HEADER = 16
FONT_PT_TOOLTIP = 10
PANEL_BORDER_W = 0
INNER_BORDER_W = 0
BUTTON_RELIEF = "flat"
BUTTON_BORDER_W = 0

# Modern font stack. Defaults are clean macOS system faces; _resolve_fonts()
# upgrades to SF Pro / SF Mono when Tk reports them available.
FONT_FAMILY = "Helvetica Neue"
FONT_MONO = "Menlo"

_UI_FONT_PREFS = (
    "SF Pro Text",
    "SF Pro Display",
    ".AppleSystemUIFont",
    "Helvetica Neue",
    "Inter",
    "Segoe UI",
    "Roboto",
    "DejaVu Sans",
)
_MONO_FONT_PREFS = (
    "SF Mono",
    "JetBrains Mono",
    "Menlo",
    "Cascadia Mono",
    "Consolas",
    "DejaVu Sans Mono",
    "Courier New",
)


def _resolve_fonts() -> None:
    """Pick the best available UI and monospace families for this machine."""
    global FONT_FAMILY, FONT_MONO
    try:
        import tkinter.font as tkfont

        available = set(tkfont.families())
    except Exception:
        return
    for fam in _UI_FONT_PREFS:
        if fam in available:
            FONT_FAMILY = fam
            break
    for fam in _MONO_FONT_PREFS:
        if fam in available:
            FONT_MONO = fam
            break

GUTTER = 12
PANEL_GAP = (0, GUTTER)
OUTER_PAD = (18, 18, 18, 18)
LABEL_COL_MIN = 130
LABEL_WRAP = 170


def apply_runtime(palette: dict[str, Any]) -> None:
    """Update palette colors only; fonts and chrome dimensions stay fixed."""
    import sys

    mod = sys.modules[__name__]
    for k, v in palette.items():
        setattr(mod, k, v)
    _configure_styles()


# PhotoImages backing the standard checkbox indicator. Kept at module level so
# they are not garbage-collected and can be redrawn in place on theme changes.
_CHECKBOX_IMAGES: dict[str, tk.PhotoImage] = {}
_CHECKBOX_SIZE = 16


def _draw_checkbox_images() -> None:
    """Draw (or redraw with the current palette) the checkbox indicator images.

    The clam theme renders the checked indicator as an X-like cross; these
    images replace it with a standard checkbox: an empty box when off and an
    accent-filled box with a white checkmark when on.
    """
    size = _CHECKBOX_SIZE
    if not _CHECKBOX_IMAGES:
        _CHECKBOX_IMAGES["off"] = tk.PhotoImage(width=size, height=size)
        _CHECKBOX_IMAGES["on"] = tk.PhotoImage(width=size, height=size)
    off, on = _CHECKBOX_IMAGES["off"], _CHECKBOX_IMAGES["on"]

    def _box(img: tk.PhotoImage, fill: str, border: str) -> None:
        img.put(border, to=(0, 0, size, size))
        img.put(fill, to=(1, 1, size - 1, size - 1))

    _box(off, INPUT_BG, INPUT_BORDER)
    _box(on, ACCENT, ACCENT)

    # White checkmark: short down-right stroke meeting a longer up-right stroke.
    check = "#FFFFFF"
    for i in range(4):
        on.put(check, to=(3 + i, 8 + i, 5 + i, 10 + i))
    for i in range(1, 7):
        on.put(check, to=(6 + i, 11 - i, 8 + i, 13 - i))


def _configure_styles() -> None:
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    _draw_checkbox_images()
    try:
        style.element_create(
            "Std.Checkbutton.indicator",
            "image",
            _CHECKBOX_IMAGES["off"],
            ("selected", _CHECKBOX_IMAGES["on"]),
            width=_CHECKBOX_SIZE + 6,
            sticky="w",
        )
    except tk.TclError:
        # Element already exists (theme re-applied); the images above were
        # redrawn in place, so the indicator picks up the new palette.
        pass
    style.layout(
        "TCheckbutton",
        [
            (
                "Checkbutton.padding",
                {
                    "sticky": "nswe",
                    "children": [
                        ("Std.Checkbutton.indicator", {"side": "left", "sticky": ""}),
                        (
                            "Checkbutton.focus",
                            {
                                "side": "left",
                                "sticky": "w",
                                "children": [("Checkbutton.label", {"sticky": "nswe"})],
                            },
                        ),
                    ],
                },
            )
        ],
    )

    _resolve_fonts()
    fb, fh, fts = FONT_PT_BASE, FONT_PT_HEADER, FONT_PT_TOOLTIP
    fl = max(8, fb - 1)  # smaller, cleaner field-label size
    pb, ib = PANEL_BORDER_W, INNER_BORDER_W
    br, bbw = BUTTON_RELIEF, BUTTON_BORDER_W

    style.configure(".", background=BG_MAIN, foreground=TEXT_MAIN, font=(FONT_FAMILY, fb))
    style.configure("TFrame", background=BG_MAIN)
    style.configure(
        "Panel.TFrame",
        background=PANEL_BLUE,
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "PanelGreen.TFrame",
        background=PANEL_GREEN,
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "Inner.TFrame",
        background=PANEL_BLUE,
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "InnerGreen.TFrame",
        background=PANEL_GREEN,
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "HeaderGreen.TLabel",
        background=PANEL_GREEN,
        foreground=HEADER_FG,
        font=(FONT_FAMILY, fh, "bold"),
        padding=(0, 2),
    )
    style.configure(
        "HeaderBlue.TLabel",
        background=PANEL_BLUE,
        foreground=HEADER_FG,
        font=(FONT_FAMILY, fh, "bold"),
        padding=(0, 2),
    )
    style.configure("TLabel", background=PANEL_BLUE, foreground=TEXT_MAIN, font=(FONT_FAMILY, fl))
    style.configure("Green.TLabel", background=PANEL_GREEN, foreground=TEXT_MAIN, font=(FONT_FAMILY, fl))
    style.configure("Subsection.TLabel", background=PANEL_BLUE, foreground=TEXT_MAIN, font=(FONT_FAMILY, fb, "bold"))
    style.configure(
        "SubsectionGreen.TLabel", background=PANEL_GREEN, foreground=TEXT_MAIN, font=(FONT_FAMILY, fb, "bold")
    )
    style.configure("CardSurface.TFrame", background=PANEL_BLUE, borderwidth=0)
    style.configure(
        "CardTitle.TLabel",
        background=PANEL_BLUE,
        foreground=TEXT_MAIN,
        font=(FONT_FAMILY, fh, "bold"),
        padding=(0, 0),
    )
    style.configure("CardRule.TFrame", background=BORDER_INNER)
    style.configure("Muted.TLabel", background=PANEL_BLUE, foreground=MUTED_TEXT, font=(FONT_FAMILY, fl))
    style.configure(
        "CardHint.TLabel",
        background=PANEL_BLUE,
        foreground=MUTED_TEXT,
        font=(FONT_FAMILY, max(9, fl - 1)),
    )
    style.configure("TabStrip.TFrame", background=LIST_SURFACE_BG, borderwidth=0)

    style.configure(
        "Primary.TButton",
        background=BTN_PRIMARY_BG,
        foreground=NOTEBOOK_TAB_SELECTED_FG,
        padding=(16, 8),
        borderwidth=0,
        relief="flat",
        font=(FONT_FAMILY, fb, "bold"),
    )
    style.map(
        "Primary.TButton",
        background=[("active", BTN_PRIMARY_HOVER), ("pressed", BTN_PRIMARY_HOVER)],
    )
    style.configure(
        "PrimaryPill.TButton",
        background=BTN_PRIMARY_BG,
        foreground=NOTEBOOK_TAB_SELECTED_FG,
        padding=(24, 10),
        borderwidth=0,
        relief="flat",
        font=(FONT_FAMILY, fb + 1, "bold"),
    )
    style.map(
        "PrimaryPill.TButton",
        background=[("active", BTN_PRIMARY_HOVER), ("pressed", BTN_PRIMARY_HOVER)],
    )
    style.configure(
        "Icon.TButton",
        background=BTN_SECONDARY_BG,
        foreground=TEXT_MAIN,
        padding=(6, 4),
        borderwidth=0,
        relief="flat",
        font=(FONT_FAMILY, fb),
        width=3,
    )
    style.map(
        "Icon.TButton",
        background=[("active", BTN_SECONDARY_HOVER), ("pressed", BTN_SECONDARY_HOVER)],
    )
    style.configure(
        "Secondary.TButton",
        background=BTN_SECONDARY_BG,
        foreground=TEXT_MAIN,
        padding=(14, 7),
        borderwidth=0,
        relief="flat",
        font=(FONT_FAMILY, fb),
    )
    style.map(
        "Secondary.TButton",
        background=[("active", BTN_SECONDARY_HOVER), ("pressed", BTN_SECONDARY_HOVER)],
    )
    style.configure(
        "Danger.TButton",
        background=BTN_DANGER_BG,
        foreground=NOTEBOOK_TAB_SELECTED_FG,
        padding=(10, 5),
        borderwidth=0,
        relief="flat",
        font=(FONT_FAMILY, fb),
    )
    style.map(
        "Danger.TButton",
        background=[("active", BTN_DANGER_HOVER), ("pressed", BTN_DANGER_HOVER)],
    )

    style.configure(
        "TabPill.TButton",
        background=LIST_SURFACE_BG,
        foreground=MUTED_TEXT,
        padding=(14, 7),
        borderwidth=0,
        relief="flat",
        font=(FONT_FAMILY, fb),
    )
    style.map(
        "TabPill.TButton",
        background=[("active", TAB_BUTTON_HOVER), ("pressed", TAB_BUTTON_HOVER)],
        foreground=[("active", TEXT_MAIN), ("pressed", TEXT_MAIN)],
    )
    style.configure(
        "TabPillActive.TButton",
        background=ACCENT,
        foreground=NOTEBOOK_TAB_SELECTED_FG,
        padding=(14, 7),
        borderwidth=0,
        relief="flat",
        font=(FONT_FAMILY, fb, "bold"),
    )
    style.map(
        "TabPillActive.TButton",
        background=[("active", BTN_PRIMARY_HOVER), ("pressed", BTN_PRIMARY_HOVER)],
        foreground=[("active", NOTEBOOK_TAB_SELECTED_FG), ("pressed", NOTEBOOK_TAB_SELECTED_FG)],
    )
    style.configure(
        "Ghost.TButton",
        background=PANEL_BLUE,
        foreground=ACCENT,
        padding=(4, 2),
        borderwidth=0,
        relief="flat",
        font=(FONT_FAMILY, fb, "bold"),
    )
    style.map(
        "Ghost.TButton",
        background=[("active", PANEL_BLUE), ("pressed", PANEL_BLUE)],
        foreground=[("active", TEXT_MAIN), ("pressed", TEXT_MAIN)],
    )

    style.configure(
        "TButton",
        background=BTN_SECONDARY_BG,
        foreground=TEXT_MAIN,
        padding=(10, 5),
        borderwidth=bbw,
        relief=br,
        bordercolor=BORDER,
        focusthickness=1,
        focuscolor=ACCENT,
        font=(FONT_FAMILY, fb),
    )
    style.map(
        "TButton",
        background=[("active", BTN_SECONDARY_HOVER), ("pressed", BTN_SECONDARY_HOVER)],
        foreground=[("active", NOTEBOOK_TAB_SELECTED_FG), ("pressed", NOTEBOOK_TAB_SELECTED_FG)],
    )
    style.configure(
        "Small.TButton",
        background=BTN_SECONDARY_BG,
        foreground=TEXT_MAIN,
        padding=(8, 4),
        bordercolor=BORDER,
        relief=br,
        borderwidth=max(1, bbw),
        font=(FONT_FAMILY, fb),
    )
    style.map(
        "Small.TButton",
        background=[("active", BTN_SECONDARY_HOVER), ("pressed", BTN_SECONDARY_HOVER)],
        foreground=[("active", NOTEBOOK_TAB_SELECTED_FG), ("pressed", NOTEBOOK_TAB_SELECTED_FG)],
    )
    style.configure(
        "Accent.TButton",
        background=BTN_PRIMARY_BG,
        foreground=NOTEBOOK_TAB_SELECTED_FG,
        padding=(12, 6),
        bordercolor=BTN_PRIMARY_BG,
        relief=br,
        borderwidth=max(1, bbw),
        font=(FONT_FAMILY, fb),
    )
    style.map(
        "Accent.TButton",
        background=[("active", BTN_PRIMARY_HOVER), ("pressed", BTN_PRIMARY_HOVER)],
        foreground=[("active", NOTEBOOK_TAB_SELECTED_FG), ("pressed", NOTEBOOK_TAB_SELECTED_FG)],
    )

    style.configure(
        "TEntry",
        fieldbackground=INPUT_BG,
        foreground=TEXT_MAIN,
        bordercolor=INPUT_BORDER,
        borderwidth=max(1, bbw),
        relief=br,
        padding=(6, 3),
        font=(FONT_FAMILY, fb),
    )
    style.map("TEntry", bordercolor=[("focus", ACCENT)])
    style.configure(
        "TSpinbox",
        fieldbackground=INPUT_BG,
        foreground=TEXT_MAIN,
        bordercolor=INPUT_BORDER,
        borderwidth=max(1, bbw),
        padding=2,
        arrowcolor=TEXT_MAIN,
        relief=br,
        font=(FONT_FAMILY, fb),
    )
    style.map("TSpinbox", fieldbackground=[("readonly", INPUT_BG)])
    style.map("TSpinbox", bordercolor=[("focus", ACCENT)])
    style.configure(
        "TCombobox",
        fieldbackground=INPUT_BG,
        background=INPUT_BG,
        foreground=TEXT_MAIN,
        bordercolor=INPUT_BORDER,
        borderwidth=max(1, bbw),
        padding=2,
        arrowcolor=TEXT_MAIN,
        relief=br,
        font=(FONT_FAMILY, fb),
    )
    style.map("TCombobox", fieldbackground=[("readonly", INPUT_BG), ("disabled", INPUT_BG)])
    style.map("TCombobox", bordercolor=[("focus", ACCENT)])

    style.configure(
        "Card.TLabelframe",
        background=PANEL_BLUE,
        borderwidth=max(1, ib),
        relief=br,
        bordercolor=BORDER,
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=PANEL_BLUE,
        foreground=HEADER_FG,
        font=(FONT_FAMILY, fb, "bold"),
    )
    style.configure(
        "GreenCard.TLabelframe",
        background=PANEL_GREEN,
        borderwidth=max(1, ib),
        relief=br,
        bordercolor=BORDER,
    )
    style.configure(
        "GreenCard.TLabelframe.Label",
        background=PANEL_GREEN,
        foreground=HEADER_FG,
        font=(FONT_FAMILY, fb, "bold"),
    )

    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=PROGRESS_TROUGH,
        background=PROGRESS_BAR,
        borderwidth=max(1, bbw),
        lightcolor=PROGRESS_BAR,
        darkcolor=PROGRESS_BAR,
    )

    style.configure("Green.TCheckbutton", background=PANEL_GREEN, foreground=TEXT_MAIN, font=(FONT_FAMILY, fb))
    style.map("Green.TCheckbutton", background=[("active", PANEL_GREEN)])
    style.configure("Blue.TCheckbutton", background=PANEL_BLUE, foreground=TEXT_MAIN, font=(FONT_FAMILY, fb))
    style.map("Blue.TCheckbutton", background=[("active", PANEL_BLUE)])

    style.configure("Tab.TButton", padding=(12, 8), background=TAB_BUTTON_BG, foreground=TEXT_MAIN, font=(FONT_FAMILY, fb))
    style.map(
        "Tab.TButton",
        background=[("active", TAB_BUTTON_HOVER), ("pressed", TAB_BUTTON_HOVER)],
        foreground=[("active", NOTEBOOK_TAB_SELECTED_FG), ("pressed", NOTEBOOK_TAB_SELECTED_FG)],
    )

    style.configure(
        "Vertical.TScrollbar",
        background=SCROLLBAR_THUMB,
        troughcolor=SCROLLBAR_TRACK,
        borderwidth=0,
        arrowcolor=TEXT_MAIN,
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("active", ACCENT), ("pressed", ACCENT)],
    )
    style.configure(
        "Horizontal.TScrollbar",
        background=SCROLLBAR_THUMB,
        troughcolor=SCROLLBAR_TRACK,
        borderwidth=0,
        arrowcolor=TEXT_MAIN,
    )
    style.map(
        "Horizontal.TScrollbar",
        background=[("active", ACCENT), ("pressed", ACCENT)],
    )

    style.configure("TSeparator", background=BORDER_INNER)

    # Flat, developer-tool navigation: tabs sit on the window background; the
    # selected tab adopts the content surface + accent text (no heavy fill).
    style.configure("TNotebook", background=BG_MAIN, borderwidth=0, tabmargins=(2, 4, 2, 0))
    style.configure(
        "TNotebook.Tab",
        background=BG_MAIN,
        foreground=MUTED_TEXT,
        padding=[16, 8],
        borderwidth=0,
        font=(FONT_FAMILY, fb),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", PANEL_BLUE), ("active", TAB_BUTTON_BG)],
        foreground=[("selected", ACCENT), ("active", TEXT_MAIN)],
        font=[("selected", (FONT_FAMILY, fb, "bold"))],
    )

    try:
        style.layout("TNotebook.Tab", [])
    except tk.TclError:
        pass


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str):
        self._widget = widget
        self._text = text
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add=True)
        widget.bind("<Leave>", self._hide, add=True)

    def _show(self, _e=None):
        if self._tip or not self._text:
            return
        import theme as _t

        x = self._widget.winfo_rootx() + 20
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        lb = tk.Label(
            self._tip,
            text=self._text,
            background=_t.TOOLTIP_BG,
            foreground=_t.TEXT_MAIN,
            relief=tk.SOLID,
            borderwidth=1,
            highlightbackground=_t.BORDER,
            highlightthickness=1,
            font=(_t.FONT_FAMILY, _t.FONT_PT_TOOLTIP),
            justify=tk.LEFT,
            padx=6,
            pady=4,
            wraplength=320,
        )
        lb.pack()

    def _hide(self, _e=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None


def add_tooltip(w: tk.Widget, text: str) -> None:
    ToolTip(w, text)
