"""Premium 3-column dashboard chrome (presentation only)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

import theme as t
from theme_manager import register_surface

# Spacing tokens (reference spec)
SPACE_XS = 6
SPACE_SM = 12
SPACE_MD = 16
SPACE_LG = 24
CARD_PAD = 18
CARD_GAP = 22
CARD_RADIUS = 12
CARD_SHADOW = 4
NAV_HEIGHT = 48


def _round_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, r: int, **kw: Any) -> int:
    r = max(0, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, splinesteps=36, **kw)


class DashboardCard:
    """Rounded card with soft shadow; sizes to content."""

    def __init__(self, parent: tk.Misc, title: str = "", *, padding: int = CARD_PAD) -> None:
        self._pad = padding
        self.shell = tk.Frame(parent, bg=t.BG_MAIN, highlightthickness=0)
        self.canvas = tk.Canvas(self.shell, bg=t.BG_MAIN, highlightthickness=0, borderwidth=0, height=48)
        self.canvas.pack(fill=tk.X)

        self._host = tk.Frame(self.canvas, bg=t.PANEL_BLUE, highlightthickness=0)
        self._win = self.canvas.create_window(padding, padding, window=self._host, anchor="nw")
        register_surface(self._host, "PANEL_BLUE")

        inner = ttk.Frame(self._host, style="CardSurface.TFrame", padding=0)
        inner.pack(fill=tk.X)

        if title:
            ttk.Label(inner, text=title, style="CardTitle.TLabel").pack(anchor="w", fill=tk.X)
            rule_row = tk.Frame(inner, bg=t.PANEL_BLUE, highlightthickness=0)
            rule_row.pack(fill=tk.X, pady=(SPACE_SM, SPACE_MD))
            tk.Frame(rule_row, bg=t.ACCENT, height=2, width=52).pack(anchor="w")
            self.content = ttk.Frame(inner, style="CardSurface.TFrame")
            self.content.pack(fill=tk.X)
        else:
            self.content = inner

        self.body = self.content
        self.canvas.bind("<Configure>", self._redraw, add=True)
        self._host.bind("<Configure>", self._schedule_redraw, add=True)
        self._redraw()

    @property
    def outer(self) -> tk.Misc:
        return self.shell

    def _schedule_redraw(self, _e: tk.Event | None = None) -> None:
        self.shell.after_idle(self._redraw)

    def _redraw(self, _e: tk.Event | None = None) -> None:
        self._host.update_idletasks()
        cw = max(self.shell.winfo_width(), 120)
        ch = self._host.winfo_reqheight() + self._pad * 2
        self.canvas.configure(height=ch + CARD_SHADOW)
        self.canvas.delete("chrome")
        _round_rect(
            self.canvas, CARD_SHADOW, CARD_SHADOW + 2, cw - 1, ch + CARD_SHADOW,
            CARD_RADIUS, fill="#0B0F17", outline="", tags="chrome",
        )
        _round_rect(
            self.canvas, 0, 0, cw - CARD_SHADOW - 1, ch,
            CARD_RADIUS, fill=t.PANEL_BLUE, outline=t.BORDER, width=1, tags="chrome",
        )
        self.canvas.tag_lower("chrome")
        self.canvas.itemconfig(self._win, width=max(1, cw - self._pad * 2 - CARD_SHADOW))


ModernCard = DashboardCard


class _ColumnShim:
    """Maps legacy column-scroll API onto the single-scroll dashboard."""

    def __init__(self, inner: tk.Frame, scroll_canvas: tk.Canvas) -> None:
        self.inner = inner
        self.wrap = inner
        self.canvas = scroll_canvas

    def _sync(self, _e: tk.Event | None = None) -> None:
        pass

    def scroll_wheel(self, delta: int) -> None:
        pass


class SingleScrollDashboard:
    """3-column dashboard with ONE vertical scrollbar for the whole page."""

    def __init__(self, parent: tk.Misc, *, row: int = 0, column: int = 0) -> None:
        self.shell = tk.Frame(parent, bg=t.BG_MAIN, highlightthickness=0)
        self.shell.grid(row=row, column=column, sticky="nsew")
        parent.rowconfigure(row, weight=1)
        parent.columnconfigure(column, weight=1)
        self.shell.columnconfigure(0, weight=1)
        self.shell.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self.shell, bg=t.BG_MAIN, highlightthickness=0, borderwidth=0)
        self.vsb = ttk.Scrollbar(self.shell, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")

        self.inner = tk.Frame(self.canvas, bg=t.BG_MAIN, highlightthickness=0)
        register_surface(self.inner, "BG_MAIN")
        register_surface(self.canvas, "BG_MAIN")
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        for c in range(3):
            self.inner.columnconfigure(c, weight=1, uniform="dash3")
        self.inner.rowconfigure(0, weight=0)

        self.left_col = tk.Frame(self.inner, bg=t.BG_MAIN, highlightthickness=0)
        self.center_col = tk.Frame(self.inner, bg=t.BG_MAIN, highlightthickness=0)
        self.right_col = tk.Frame(self.inner, bg=t.BG_MAIN, highlightthickness=0)
        self.left_col.grid(row=0, column=0, sticky="new", padx=(0, CARD_GAP))
        self.center_col.grid(row=0, column=1, sticky="new", padx=(0, CARD_GAP))
        self.right_col.grid(row=0, column=2, sticky="new")

        self.left = _ColumnShim(self.left_col, self.canvas)
        self.center = _ColumnShim(self.center_col, self.canvas)
        self.right = _ColumnShim(self.right_col, self.canvas)
        self._columns = (self.left, self.center, self.right)

        self.inner.bind("<Configure>", self._sync, add=True)
        self.canvas.bind("<Configure>", self._on_canvas, add=True)
        self.canvas.configure(yscrollcommand=self.vsb.set)

    def _sync(self, _e: tk.Event | None = None) -> None:
        self.canvas.update_idletasks()
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=bbox)

    def _on_canvas(self, e: tk.Event) -> None:
        if e.width > 1:
            self.canvas.itemconfig(self._win, width=e.width)
        self._sync()

    def sync(self) -> None:
        self._sync()

    def scroll_wheel(self, delta: int) -> None:
        self.canvas.yview_scroll(delta, "units")


ThreeColumnLayout = SingleScrollDashboard
DashboardPage = SingleScrollDashboard


class DashboardGrid:
    """Multi-column wrapping grid inside a column."""

    def __init__(self, parent: tk.Misc, columns: int = 2) -> None:
        self._columns = max(1, columns)
        self._next = 0
        self.frame = tk.Frame(parent, bg=t.BG_MAIN, highlightthickness=0)
        self.frame.pack(fill=tk.X, anchor="n")
        for c in range(self._columns):
            self.frame.columnconfigure(c, weight=1, uniform="dashcol")

    def attach(self, widget: tk.Misc) -> tuple[int, int]:
        row, col = divmod(self._next, self._columns)
        widget.grid(
            row=row, column=col, sticky="new",
            padx=(0, SPACE_LG), pady=(0, SPACE_LG),
        )
        self._next += 1
        return row, col

    def reset(self) -> None:
        self._next = 0

    def clear(self) -> None:
        for child in self.frame.winfo_children():
            child.destroy()
        self.reset()


CardGrid = DashboardGrid


def mount_card(parent: tk.Misc, title: str, **kwargs: Any) -> tuple[tk.Misc, tk.Misc]:
    """Create a card and stack it vertically in a column."""
    card = DashboardCard(parent, title, padding=kwargs.pop("padding", CARD_PAD))
    card.outer.pack(fill=tk.X, pady=(0, CARD_GAP))
    return card.outer, card.body


def card_footer(parent: tk.Misc, text: str, *, row: int | None = None, columnspan: int = 2) -> None:
    lbl = ttk.Label(parent, text=text, style="CardHint.TLabel")
    if row is not None:
        lbl.grid(row=row, column=0, columnspan=columnspan, sticky="w", pady=(SPACE_SM, 0))
    else:
        lbl.pack(anchor="w", pady=(SPACE_SM, 0))


class PermutationPanel:
    """Reference-style collapsible permutation panel — title left, chevron right, horizontal checkboxes."""

    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        *,
        start_open: bool = True,
        on_toggle: Callable[[], None] | None = None,
    ) -> None:
        self._title = title
        self._open = start_open
        self._on_toggle = on_toggle

        card = DashboardCard(parent, padding=SPACE_MD)
        self.outer = card.outer

        hdr = tk.Frame(card.content, bg=t.PANEL_BLUE, highlightthickness=0, cursor="hand2")
        hdr.pack(fill=tk.X)
        self._title_lbl = tk.Label(
            hdr,
            text=title,
            bg=t.PANEL_BLUE,
            fg=t.TEXT_MAIN,
            font=(t.FONT_FAMILY, t.FONT_PT_BASE, "bold"),
            anchor="w",
        )
        self._title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._chevron = tk.Label(
            hdr,
            text="▾" if start_open else "▸",
            bg=t.PANEL_BLUE,
            fg=t.MUTED_TEXT,
            font=(t.FONT_FAMILY, t.FONT_PT_BASE),
            padx=4,
        )
        self._chevron.pack(side=tk.RIGHT)
        for w in (hdr, self._title_lbl, self._chevron):
            w.bind("<Button-1>", lambda _e: self._toggle())

        rule_row = tk.Frame(card.content, bg=t.PANEL_BLUE, highlightthickness=0)
        rule_row.pack(fill=tk.X, pady=(SPACE_XS, SPACE_SM))
        tk.Frame(rule_row, bg=t.ACCENT, height=2, width=52).pack(anchor="w")

        self.body = ttk.Frame(card.content, style="CardSurface.TFrame")
        if start_open:
            self.body.pack(fill=tk.X)

    def _toggle(self) -> None:
        self._open = not self._open
        self._chevron.configure(text="▾" if self._open else "▸")
        if self._open:
            self.body.pack(fill=tk.X)
        else:
            self.body.pack_forget()
        if self._on_toggle:
            self._on_toggle()


class CollapsibleCard(PermutationPanel):
    """Back-compat alias — definitions use the same panel chrome."""


class NavTabBar(tk.Frame):
    """Compact top nav — dark strip, blue underline on active tab."""

    def __init__(self, parent: tk.Misc, notebook: ttk.Notebook, labels: list[str]) -> None:
        super().__init__(parent, bg=t.LIST_SURFACE_BG, height=NAV_HEIGHT, highlightthickness=0)
        self.pack_propagate(False)
        self._notebook = notebook
        self._active = 0
        self._items: list[tuple[tk.Frame, tk.Label, tk.Frame]] = []

        row = tk.Frame(self, bg=t.LIST_SURFACE_BG, highlightthickness=0)
        row.pack(fill=tk.BOTH, expand=True, padx=SPACE_MD)

        for i, label in enumerate(labels):
            cell = tk.Frame(row, bg=t.LIST_SURFACE_BG, highlightthickness=0, cursor="hand2")
            cell.pack(side=tk.LEFT)
            lbl = tk.Label(
                cell,
                text=label,
                bg=t.LIST_SURFACE_BG,
                fg=t.MUTED_TEXT,
                font=(t.FONT_FAMILY, t.FONT_PT_BASE),
                padx=14,
                pady=10,
            )
            lbl.pack()
            underline = tk.Frame(cell, bg=t.ACCENT, height=2, highlightthickness=0)
            underline.pack(fill=tk.X, padx=8)
            underline.pack_forget()
            for w in (cell, lbl):
                w.bind("<Button-1>", lambda _e, idx=i: self.select(idx))
            self._items.append((cell, lbl, underline))

        notebook.bind("<<NotebookTabChanged>>", self._sync, add=True)
        self.select(0)

    def select(self, index: int) -> None:
        tabs = self._notebook.tabs()
        if not tabs or index < 0 or index >= len(tabs):
            return
        self._active = index
        self._notebook.select(tabs[index])
        for i, (_cell, lbl, ul) in enumerate(self._items):
            if i == index:
                lbl.configure(fg=t.TEXT_MAIN, font=(t.FONT_FAMILY, t.FONT_PT_BASE, "bold"))
                ul.pack(fill=tk.X, padx=8)
            else:
                lbl.configure(fg=t.MUTED_TEXT, font=(t.FONT_FAMILY, t.FONT_PT_BASE))
                ul.pack_forget()

    def _sync(self, _e: tk.Event | None = None) -> None:
        try:
            idx = self._notebook.index(self._notebook.select())
        except tk.TclError:
            return
        if idx != self._active:
            self.select(idx)


# Back-compat alias
PillTabBar = NavTabBar


class BottomActionBar(tk.Frame):
    """Persistent footer: Settings (left) · Save As (center) · Run (right, prominent)."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_settings: Callable[[], None],
        on_save: Callable[[], None],
        on_run: Callable[[], None],
    ) -> None:
        super().__init__(parent, bg=t.LIST_SURFACE_BG, highlightthickness=0)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.columnconfigure(2, weight=1)
        left = ttk.Frame(self, style="TFrame")
        left.grid(row=0, column=0, sticky="w", padx=SPACE_LG, pady=8)
        ttk.Button(left, text="Settings", style="Secondary.TButton", command=on_settings).pack(side=tk.LEFT)
        mid = ttk.Frame(self, style="TFrame")
        mid.grid(row=0, column=1, pady=8)
        ttk.Button(mid, text="Save As", style="Primary.TButton", command=on_save).pack(ipadx=8, ipady=2)
        right = ttk.Frame(self, style="TFrame")
        right.grid(row=0, column=2, sticky="e", padx=SPACE_LG, pady=8)
        ttk.Button(right, text="Run", style="PrimaryPill.TButton", command=on_run).pack(side=tk.RIGHT, ipadx=24, ipady=6)


def stack_field(parent: tk.Misc, label: str, widget: tk.Misc, *, pady: int = SPACE_SM) -> None:
    """Label above input (reference layout)."""
    cell = ttk.Frame(parent, style="CardSurface.TFrame")
    cell.pack(fill=tk.X, pady=(0, pady))
    ttk.Label(cell, text=label, style="Muted.TLabel").pack(anchor="w", pady=(0, 4))
    widget.pack(anchor="w")


def compact_label(parent: tk.Misc, text: str) -> ttk.Label:
    return ttk.Label(parent, text=text, style="Muted.TLabel")


def field_row(parent: tk.Misc, label: str, widget: tk.Misc, *, pady: int = SPACE_XS) -> None:
    stack_field(parent, label, widget, pady=pady)


def grid_fields(
    parent: ttk.Frame,
    specs: list[tuple[str, Callable[[ttk.Frame], tk.Misc]]],
    *,
    cols: int = 2,
) -> dict[str, tk.Misc]:
    widgets: dict[str, tk.Misc] = {}
    for c in range(cols):
        parent.columnconfigure(c, weight=1)
    for i, (key, builder) in enumerate(specs):
        r, c = divmod(i, cols)
        cell = ttk.Frame(parent, style="CardSurface.TFrame")
        cell.grid(row=r, column=c, sticky="nw", padx=(0, SPACE_SM), pady=(0, SPACE_SM))
        ttk.Label(cell, text=key, style="Muted.TLabel").pack(anchor="w", pady=(0, 4))
        w = builder(cell)
        w.pack(anchor="w")
        widgets[key] = w
    return widgets


def page_scroll(parent: tk.Misc) -> tuple[ttk.Frame, tk.Canvas, tk.Frame]:
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(1, weight=1)
    shell = ttk.Frame(parent)
    shell.grid(row=1, column=0, sticky="nsew")
    shell.columnconfigure(0, weight=1)
    shell.rowconfigure(0, weight=1)
    canvas = tk.Canvas(shell, bg=t.BG_MAIN, highlightthickness=0, borderwidth=0)
    vsb = ttk.Scrollbar(shell, orient=tk.VERTICAL, command=canvas.yview)
    canvas.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    inner = tk.Frame(canvas, bg=t.BG_MAIN, highlightthickness=0)
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
    return shell, canvas, inner


def make_column_scroll(parent: tk.Misc, bg: str | None = None) -> tuple[ttk.Frame, tk.Canvas, ttk.Scrollbar, tk.Frame]:
    surface = bg or t.BG_MAIN
    shell = ttk.Frame(parent)
    shell.columnconfigure(0, weight=1)
    shell.rowconfigure(0, weight=1)
    canvas = tk.Canvas(shell, bg=surface, highlightthickness=0)
    vsb = ttk.Scrollbar(shell, orient=tk.VERTICAL, command=canvas.yview)
    canvas.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    inner = tk.Frame(canvas, bg=surface, highlightthickness=0)
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


def status_badge(parent: tk.Misc, text: str, *, color: str | None = None) -> tk.Label:
    fg = color or t.ACCENT
    return tk.Label(
        parent, text=f"● {text}", bg=t.LIST_SURFACE_BG, fg=fg,
        font=(t.FONT_FAMILY, t.FONT_PT_BASE - 1),
        padx=12, pady=5, highlightthickness=0,
    )


def hide_notebook_tabs() -> None:
    ttk.Style().layout("TNotebook.Tab", [])
