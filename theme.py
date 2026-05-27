import tkinter as tk
from tkinter import ttk
from typing import Any

# --- Mutable runtime palette (defaults match Dark Mode Professional + session defaults) ---
BG_MAIN = "#121212"
PANEL_BLUE = "#1A1A1A"
PANEL_GREEN = "#161616"
HEADER_GREEN = "#1E1E1E"
HEADER_BLUE = "#1E1E1E"
HEADER_FG = "#F0F0F0"
BORDER = "#3D3D3D"
BORDER_INNER = "#343434"
INPUT_BG = "#1C1C1C"
INPUT_BORDER = "#404040"
TEXT_MAIN = "#E8E8E8"
BTN_PRIMARY_BG = "#5B8FC7"
BTN_PRIMARY_HOVER = "#7AA8E0"
BTN_SECONDARY_BG = "#2A2A2A"
BTN_SECONDARY_HOVER = "#4A6785"
PROGRESS_BAR = "#5B8FC7"
PROGRESS_TROUGH = "#1C1C1C"
ACCENT = "#7AA8E0"
GRAPH_AREA_BG = "#121212"
GRAPH_AREA_FG = "#E8E8E8"
SUMMARY_BG = "#1A1A1A"
SCROLLBAR_TRACK = "#1C1C1C"
SCROLLBAR_THUMB = "#3A3A3A"
TOOLTIP_BG = "#252525"
MUTED_TEXT = "#A8A8A8"
VALIDATION_WARN = "#E57373"
TAB_BUTTON_BG = "#2A2A2A"
TAB_BUTTON_HOVER = "#4A6785"
GRAPH_NODE_BASE = "#90CAF9"
GRAPH_NODE_ACTIVE = "#A5D6A7"
GRAPH_COMM = "#CE93D8"
GRAPH_EDGE_BASE = "#424242"
GRAPH_EDGE_ACTIVE = "#90CAF9"
LOG_SUCCESS = "#A5D6A7"
LOG_ERROR = "#E57373"
NOTEBOOK_TAB_SELECTED_FG = "#121212"

FONT_PT_BASE = 10
FONT_PT_HEADER = 11
FONT_PT_TOOLTIP = 9
PANEL_BORDER_W = 2
INNER_BORDER_W = 1
BUTTON_RELIEF = "solid"
BUTTON_BORDER_W = 1

GUTTER = 12
PANEL_GAP = (0, GUTTER)
OUTER_PAD = (GUTTER, GUTTER, GUTTER, 8)
LABEL_COL_MIN = 260
LABEL_WRAP = 300


def apply_runtime(palette: dict[str, Any]) -> None:
    """Update palette colors only; fonts and chrome dimensions stay fixed."""
    import sys

    mod = sys.modules[__name__]
    for k, v in palette.items():
        setattr(mod, k, v)
    _configure_styles()


def _configure_styles() -> None:
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    fb, fh, fts = FONT_PT_BASE, FONT_PT_HEADER, FONT_PT_TOOLTIP
    pb, ib = PANEL_BORDER_W, INNER_BORDER_W
    br, bbw = BUTTON_RELIEF, BUTTON_BORDER_W

    style.configure(".", background=BG_MAIN, foreground=TEXT_MAIN, font=("Segoe UI", fb))
    style.configure("TFrame", background=BG_MAIN)
    style.configure(
        "Panel.TFrame",
        background=PANEL_BLUE,
        borderwidth=pb,
        relief=br,
        bordercolor=BORDER,
    )
    style.configure(
        "PanelGreen.TFrame",
        background=PANEL_GREEN,
        borderwidth=pb,
        relief=br,
        bordercolor=BORDER,
    )
    style.configure(
        "Inner.TFrame",
        background=PANEL_BLUE,
        borderwidth=ib,
        relief=br,
        bordercolor=BORDER_INNER,
    )
    style.configure(
        "InnerGreen.TFrame",
        background=PANEL_GREEN,
        borderwidth=ib,
        relief=br,
        bordercolor=BORDER_INNER,
    )
    style.configure(
        "HeaderGreen.TLabel",
        background=HEADER_GREEN,
        foreground=HEADER_FG,
        font=("Segoe UI", fh, "bold"),
        padding=(8, 6),
    )
    style.configure(
        "HeaderBlue.TLabel",
        background=HEADER_BLUE,
        foreground=HEADER_FG,
        font=("Segoe UI", fh, "bold"),
        padding=(8, 6),
    )
    style.configure("TLabel", background=PANEL_BLUE, foreground=TEXT_MAIN, font=("Segoe UI", fb))
    style.configure("Green.TLabel", background=PANEL_GREEN, foreground=TEXT_MAIN, font=("Segoe UI", fb))
    style.configure("Subsection.TLabel", background=PANEL_BLUE, foreground=TEXT_MAIN, font=("Segoe UI", fb, "bold"))
    style.configure(
        "SubsectionGreen.TLabel", background=PANEL_GREEN, foreground=TEXT_MAIN, font=("Segoe UI", fb, "bold")
    )

    style.configure(
        "TButton",
        background=BTN_SECONDARY_BG,
        foreground=TEXT_MAIN,
        padding=(12, 8),
        borderwidth=bbw,
        relief=br,
        bordercolor=BORDER,
        focusthickness=1,
        focuscolor=ACCENT,
        font=("Segoe UI", fb),
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
        padding=(12, 8),
        bordercolor=VALIDATION_WARN,
        relief=br,
        borderwidth=max(1, bbw),
        font=("Segoe UI", fb),
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
        padding=(12, 8),
        bordercolor=BTN_PRIMARY_BG,
        relief=br,
        borderwidth=max(1, bbw),
        font=("Segoe UI", fb),
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
        padding=4,
        font=("Segoe UI", fb),
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
        font=("Segoe UI", fb),
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
        font=("Segoe UI", fb),
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
        font=("Segoe UI", fb, "bold"),
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
        font=("Segoe UI", fb, "bold"),
    )

    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=PROGRESS_TROUGH,
        background=PROGRESS_BAR,
        borderwidth=max(1, bbw),
        lightcolor=PROGRESS_BAR,
        darkcolor=PROGRESS_BAR,
    )

    style.configure("Green.TCheckbutton", background=PANEL_GREEN, foreground=TEXT_MAIN, font=("Segoe UI", fb))
    style.map("Green.TCheckbutton", background=[("active", PANEL_GREEN)])
    style.configure("Blue.TCheckbutton", background=PANEL_BLUE, foreground=TEXT_MAIN, font=("Segoe UI", fb))
    style.map("Blue.TCheckbutton", background=[("active", PANEL_BLUE)])

    style.configure("Tab.TButton", padding=(12, 8), background=TAB_BUTTON_BG, foreground=TEXT_MAIN, font=("Segoe UI", fb))
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

    style.configure("TNotebook", background=BG_MAIN, borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=TAB_BUTTON_BG,
        foreground=TEXT_MAIN,
        padding=[12, 6],
        font=("Segoe UI", fb, "bold"),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", BTN_PRIMARY_BG), ("active", TAB_BUTTON_HOVER)],
        foreground=[("selected", NOTEBOOK_TAB_SELECTED_FG), ("active", NOTEBOOK_TAB_SELECTED_FG)],
    )


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
            font=("Segoe UI", _t.FONT_PT_TOOLTIP),
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
