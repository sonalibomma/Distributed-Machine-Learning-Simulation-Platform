from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

# --- Session (persists for app lifetime) --------------------------------------

PALETTE_KEYS = frozenset(
    {
        "BG_MAIN",
        "PANEL_BLUE",
        "PANEL_GREEN",
        "HEADER_GREEN",
        "HEADER_BLUE",
        "HEADER_FG",
        "BORDER",
        "BORDER_INNER",
        "INPUT_BG",
        "INPUT_BORDER",
        "TEXT_MAIN",
        "BTN_PRIMARY_BG",
        "BTN_PRIMARY_HOVER",
        "BTN_SECONDARY_BG",
        "BTN_SECONDARY_HOVER",
        "PROGRESS_BAR",
        "PROGRESS_TROUGH",
        "ACCENT",
        "GRAPH_AREA_BG",
        "GRAPH_AREA_FG",
        "SUMMARY_BG",
        "SCROLLBAR_TRACK",
        "SCROLLBAR_THUMB",
        "TOOLTIP_BG",
        "MUTED_TEXT",
        "VALIDATION_WARN",
        "TAB_BUTTON_BG",
        "TAB_BUTTON_HOVER",
        "GRAPH_NODE_BASE",
        "GRAPH_NODE_ACTIVE",
        "GRAPH_COMM",
        "GRAPH_EDGE_BASE",
        "GRAPH_EDGE_ACTIVE",
        "LOG_SUCCESS",
        "LOG_ERROR",
        "NOTEBOOK_TAB_SELECTED_FG",
    }
)


def _classic_preset() -> dict[str, str]:
    """Original application colors (Default Classic)."""
    return {
        "BG_MAIN": "#0B0F14",
        "PANEL_BLUE": "#121821",
        "PANEL_GREEN": "#0F1720",
        "HEADER_GREEN": "#121821",
        "HEADER_BLUE": "#121821",
        "HEADER_FG": "#00E5FF",
        "BORDER": "#3A4F66",
        "BORDER_INNER": "#33475C",
        "INPUT_BG": "#0F1720",
        "INPUT_BORDER": "#3A4F66",
        "TEXT_MAIN": "#E6F1FF",
        "BTN_PRIMARY_BG": "#00FF9C",
        "BTN_PRIMARY_HOVER": "#00E5FF",
        "BTN_SECONDARY_BG": "#1A2330",
        "BTN_SECONDARY_HOVER": "#00E5FF",
        "PROGRESS_BAR": "#00FF9C",
        "PROGRESS_TROUGH": "#0F1720",
        "ACCENT": "#9D4DFF",
        "GRAPH_AREA_BG": "#0B0F14",
        "GRAPH_AREA_FG": "#E6F1FF",
        "SUMMARY_BG": "#0F1720",
        "SCROLLBAR_TRACK": "#0F1720",
        "SCROLLBAR_THUMB": "#1F2A38",
        "TOOLTIP_BG": "#121821",
        "MUTED_TEXT": "#8FA3B0",
        "VALIDATION_WARN": "#FF4D6D",
        "TAB_BUTTON_BG": "#1A2330",
        "TAB_BUTTON_HOVER": "#00E5FF",
        "GRAPH_NODE_BASE": "#00E5FF",
        "GRAPH_NODE_ACTIVE": "#00FF9C",
        "GRAPH_COMM": "#9D4DFF",
        "GRAPH_EDGE_BASE": "#1F2A38",
        "GRAPH_EDGE_ACTIVE": "#00E5FF",
        "LOG_SUCCESS": "#00FF9C",
        "LOG_ERROR": "#FF4D6D",
        "NOTEBOOK_TAB_SELECTED_FG": "#000000",
    }


def _dark_professional_preset() -> dict[str, str]:
    return {
        "BG_MAIN": "#121212",
        "PANEL_BLUE": "#1A1A1A",
        "PANEL_GREEN": "#161616",
        "HEADER_GREEN": "#1E1E1E",
        "HEADER_BLUE": "#1E1E1E",
        "HEADER_FG": "#F0F0F0",
        "BORDER": "#3D3D3D",
        "BORDER_INNER": "#343434",
        "INPUT_BG": "#1C1C1C",
        "INPUT_BORDER": "#404040",
        "TEXT_MAIN": "#E8E8E8",
        "BTN_PRIMARY_BG": "#5B8FC7",
        "BTN_PRIMARY_HOVER": "#7AA8E0",
        "BTN_SECONDARY_BG": "#2A2A2A",
        "BTN_SECONDARY_HOVER": "#4A6785",
        "PROGRESS_BAR": "#5B8FC7",
        "PROGRESS_TROUGH": "#1C1C1C",
        "ACCENT": "#7AA8E0",
        "GRAPH_AREA_BG": "#121212",
        "GRAPH_AREA_FG": "#E8E8E8",
        "SUMMARY_BG": "#1A1A1A",
        "SCROLLBAR_TRACK": "#1C1C1C",
        "SCROLLBAR_THUMB": "#3A3A3A",
        "TOOLTIP_BG": "#252525",
        "MUTED_TEXT": "#A8A8A8",
        "VALIDATION_WARN": "#E57373",
        "TAB_BUTTON_BG": "#2A2A2A",
        "TAB_BUTTON_HOVER": "#4A6785",
        "GRAPH_NODE_BASE": "#90CAF9",
        "GRAPH_NODE_ACTIVE": "#A5D6A7",
        "GRAPH_COMM": "#CE93D8",
        "GRAPH_EDGE_BASE": "#424242",
        "GRAPH_EDGE_ACTIVE": "#90CAF9",
        "LOG_SUCCESS": "#A5D6A7",
        "LOG_ERROR": "#E57373",
        "NOTEBOOK_TAB_SELECTED_FG": "#121212",
    }


def _neon_tech_preset() -> dict[str, str]:
    return {
        "BG_MAIN": "#050810",
        "PANEL_BLUE": "#0A1220",
        "PANEL_GREEN": "#081018",
        "HEADER_GREEN": "#0A1220",
        "HEADER_BLUE": "#0A1220",
        "HEADER_FG": "#00F0FF",
        "BORDER": "#00E5FF",
        "BORDER_INNER": "#1E90FF",
        "INPUT_BG": "#080D16",
        "INPUT_BORDER": "#00D4AA",
        "TEXT_MAIN": "#E0FFFF",
        "BTN_PRIMARY_BG": "#00FF88",
        "BTN_PRIMARY_HOVER": "#00FFCC",
        "BTN_SECONDARY_BG": "#121E30",
        "BTN_SECONDARY_HOVER": "#00F0FF",
        "PROGRESS_BAR": "#00FF88",
        "PROGRESS_TROUGH": "#080D16",
        "ACCENT": "#00F0FF",
        "GRAPH_AREA_BG": "#050810",
        "GRAPH_AREA_FG": "#E0FFFF",
        "SUMMARY_BG": "#0A1220",
        "SCROLLBAR_TRACK": "#080D16",
        "SCROLLBAR_THUMB": "#1A3048",
        "TOOLTIP_BG": "#0A1220",
        "MUTED_TEXT": "#88C8D8",
        "VALIDATION_WARN": "#FF6B9D",
        "TAB_BUTTON_BG": "#121E30",
        "TAB_BUTTON_HOVER": "#00F0FF",
        "GRAPH_NODE_BASE": "#00F0FF",
        "GRAPH_NODE_ACTIVE": "#00FF88",
        "GRAPH_COMM": "#D946FF",
        "GRAPH_EDGE_BASE": "#1A3048",
        "GRAPH_EDGE_ACTIVE": "#00F0FF",
        "LOG_SUCCESS": "#00FF88",
        "LOG_ERROR": "#FF6B9D",
        "NOTEBOOK_TAB_SELECTED_FG": "#000000",
    }


def _midnight_blue_preset() -> dict[str, str]:
    return {
        "BG_MAIN": "#0B1426",
        "PANEL_BLUE": "#111C33",
        "PANEL_GREEN": "#0E182E",
        "HEADER_GREEN": "#132542",
        "HEADER_BLUE": "#132542",
        "HEADER_FG": "#B8E0FF",
        "BORDER": "#2D4A7C",
        "BORDER_INNER": "#243D66",
        "INPUT_BG": "#0F1A30",
        "INPUT_BORDER": "#3D5A8A",
        "TEXT_MAIN": "#E8F4FF",
        "BTN_PRIMARY_BG": "#4DA3FF",
        "BTN_PRIMARY_HOVER": "#7BC0FF",
        "BTN_SECONDARY_BG": "#1A2844",
        "BTN_SECONDARY_HOVER": "#4DA3FF",
        "PROGRESS_BAR": "#4DA3FF",
        "PROGRESS_TROUGH": "#0F1A30",
        "ACCENT": "#7BC0FF",
        "GRAPH_AREA_BG": "#0B1426",
        "GRAPH_AREA_FG": "#E8F4FF",
        "SUMMARY_BG": "#111C33",
        "SCROLLBAR_TRACK": "#0F1A30",
        "SCROLLBAR_THUMB": "#2A4570",
        "TOOLTIP_BG": "#152542",
        "MUTED_TEXT": "#9BB8D9",
        "VALIDATION_WARN": "#FF8A80",
        "TAB_BUTTON_BG": "#1A2844",
        "TAB_BUTTON_HOVER": "#4DA3FF",
        "GRAPH_NODE_BASE": "#7BC0FF",
        "GRAPH_NODE_ACTIVE": "#B8E0FF",
        "GRAPH_COMM": "#CE93D8",
        "GRAPH_EDGE_BASE": "#243D66",
        "GRAPH_EDGE_ACTIVE": "#4DA3FF",
        "LOG_SUCCESS": "#B8E0FF",
        "LOG_ERROR": "#FF8A80",
        "NOTEBOOK_TAB_SELECTED_FG": "#0B1426",
    }


def _forest_tech_preset() -> dict[str, str]:
    return {
        "BG_MAIN": "#0D1512",
        "PANEL_BLUE": "#14221C",
        "PANEL_GREEN": "#101C18",
        "HEADER_GREEN": "#162820",
        "HEADER_BLUE": "#162820",
        "HEADER_FG": "#5EEAD4",
        "BORDER": "#2D6B5C",
        "BORDER_INNER": "#245548",
        "INPUT_BG": "#111E1A",
        "INPUT_BORDER": "#34796A",
        "TEXT_MAIN": "#E8F5F0",
        "BTN_PRIMARY_BG": "#34D399",
        "BTN_PRIMARY_HOVER": "#5EEAD4",
        "BTN_SECONDARY_BG": "#1A2E28",
        "BTN_SECONDARY_HOVER": "#34D399",
        "PROGRESS_BAR": "#34D399",
        "PROGRESS_TROUGH": "#111E1A",
        "ACCENT": "#5EEAD4",
        "GRAPH_AREA_BG": "#0D1512",
        "GRAPH_AREA_FG": "#E8F5F0",
        "SUMMARY_BG": "#14221C",
        "SCROLLBAR_TRACK": "#111E1A",
        "SCROLLBAR_THUMB": "#2A4D44",
        "TOOLTIP_BG": "#162820",
        "MUTED_TEXT": "#9BC9BC",
        "VALIDATION_WARN": "#FCA5A5",
        "TAB_BUTTON_BG": "#1A2E28",
        "TAB_BUTTON_HOVER": "#34D399",
        "GRAPH_NODE_BASE": "#5EEAD4",
        "GRAPH_NODE_ACTIVE": "#34D399",
        "GRAPH_COMM": "#A78BFA",
        "GRAPH_EDGE_BASE": "#2A4D44",
        "GRAPH_EDGE_ACTIVE": "#5EEAD4",
        "LOG_SUCCESS": "#34D399",
        "LOG_ERROR": "#FCA5A5",
        "NOTEBOOK_TAB_SELECTED_FG": "#0D1512",
    }


def _light_minimal_preset() -> dict[str, str]:
    return {
        "BG_MAIN": "#F4F6F8",
        "PANEL_BLUE": "#FFFFFF",
        "PANEL_GREEN": "#FAFBFC",
        "HEADER_GREEN": "#F0F4F8",
        "HEADER_BLUE": "#F0F4F8",
        "HEADER_FG": "#1565C0",
        "BORDER": "#CFD8DC",
        "BORDER_INNER": "#E0E6EB",
        "INPUT_BG": "#FFFFFF",
        "INPUT_BORDER": "#B0BEC5",
        "TEXT_MAIN": "#263238",
        "BTN_PRIMARY_BG": "#1976D2",
        "BTN_PRIMARY_HOVER": "#42A5F5",
        "BTN_SECONDARY_BG": "#ECEFF1",
        "BTN_SECONDARY_HOVER": "#1976D2",
        "PROGRESS_BAR": "#1976D2",
        "PROGRESS_TROUGH": "#ECEFF1",
        "ACCENT": "#1976D2",
        "GRAPH_AREA_BG": "#FFFFFF",
        "GRAPH_AREA_FG": "#263238",
        "SUMMARY_BG": "#FAFBFC",
        "SCROLLBAR_TRACK": "#ECEFF1",
        "SCROLLBAR_THUMB": "#B0BEC5",
        "TOOLTIP_BG": "#FFFFFF",
        "MUTED_TEXT": "#546E7A",
        "VALIDATION_WARN": "#D32F2F",
        "TAB_BUTTON_BG": "#ECEFF1",
        "TAB_BUTTON_HOVER": "#42A5F5",
        "GRAPH_NODE_BASE": "#1976D2",
        "GRAPH_NODE_ACTIVE": "#42A5F5",
        "GRAPH_COMM": "#7E57C2",
        "GRAPH_EDGE_BASE": "#CFD8DC",
        "GRAPH_EDGE_ACTIVE": "#1976D2",
        "LOG_SUCCESS": "#2E7D32",
        "LOG_ERROR": "#D32F2F",
        "NOTEBOOK_TAB_SELECTED_FG": "#FFFFFF",
    }


def _pure_white_professional_preset() -> dict[str, str]:
    """Clean white surfaces, soft gray borders, charcoal text, blue corporate accents."""
    return {
        "BG_MAIN": "#FFFFFF",
        "PANEL_BLUE": "#F8FAFC",
        "PANEL_GREEN": "#F3F6F9",
        "HEADER_GREEN": "#F1F5F9",
        "HEADER_BLUE": "#F1F5F9",
        "HEADER_FG": "#1E40AF",
        "BORDER": "#CBD5E1",
        "BORDER_INNER": "#E2E8F0",
        "INPUT_BG": "#FFFFFF",
        "INPUT_BORDER": "#94A3B8",
        "TEXT_MAIN": "#1E293B",
        "BTN_PRIMARY_BG": "#2563EB",
        "BTN_PRIMARY_HOVER": "#3B82F6",
        "BTN_SECONDARY_BG": "#F1F5F9",
        "BTN_SECONDARY_HOVER": "#DBEAFE",
        "PROGRESS_BAR": "#2563EB",
        "PROGRESS_TROUGH": "#E2E8F0",
        "ACCENT": "#2563EB",
        "GRAPH_AREA_BG": "#FFFFFF",
        "GRAPH_AREA_FG": "#1E293B",
        "SUMMARY_BG": "#F8FAFC",
        "SCROLLBAR_TRACK": "#F1F5F9",
        "SCROLLBAR_THUMB": "#CBD5E1",
        "TOOLTIP_BG": "#FFFFFF",
        "MUTED_TEXT": "#64748B",
        "VALIDATION_WARN": "#DC2626",
        "TAB_BUTTON_BG": "#E8EEF4",
        "TAB_BUTTON_HOVER": "#BFDBFE",
        "GRAPH_NODE_BASE": "#2563EB",
        "GRAPH_NODE_ACTIVE": "#10B981",
        "GRAPH_COMM": "#7C3AED",
        "GRAPH_EDGE_BASE": "#CBD5E1",
        "GRAPH_EDGE_ACTIVE": "#2563EB",
        "LOG_SUCCESS": "#059669",
        "LOG_ERROR": "#DC2626",
        "NOTEBOOK_TAB_SELECTED_FG": "#FFFFFF",
    }


PRESET_FACTORIES: dict[str, Callable[[], dict[str, str]]] = {
    "Default Classic": _classic_preset,
    "Dark Mode Professional": _dark_professional_preset,
    "Neon Tech": _neon_tech_preset,
    "Midnight Blue": _midnight_blue_preset,
    "Forest Tech": _forest_tech_preset,
    "Light Minimal": _light_minimal_preset,
    "Pure White Professional": _pure_white_professional_preset,
}

PRESET_ORDER: tuple[str, ...] = tuple(PRESET_FACTORIES.keys())


@dataclass
class AppearanceSession:
    """Persisted theme choice; updated only when the user clicks Apply."""

    preset: str = "Dark Mode Professional"


SESSION = AppearanceSession()

_surface_registry: list[tuple[Any, str]] = []
_text_registry: list[Any] = []
_listbox_registry: list[Any] = []
_listeners: list[Callable[[], None]] = []


def register_surface(widget: Any, color_key: str) -> None:
    if color_key not in PALETTE_KEYS:
        raise ValueError(f"Unknown color key: {color_key}")
    _surface_registry.append((widget, color_key))


def register_notes_text(widget: Any) -> None:
    _text_registry.append(widget)


def register_listbox(widget: Any) -> None:
    _listbox_registry.append(widget)


def subscribe(callback: Callable[[], None]) -> Callable[[], None]:
    _listeners.append(callback)
    return callback


def unsubscribe(callback: Callable[[], None]) -> None:
    try:
        _listeners.remove(callback)
    except ValueError:
        pass


def notify_theme_changed() -> None:
    refresh_surfaces()
    refresh_text_widgets()
    refresh_listboxes()
    for cb in list(_listeners):
        try:
            cb()
        except Exception:
            pass


def refresh_surfaces() -> None:
    import theme as t

    for pair in list(_surface_registry):
        w, key = pair
        try:
            if not w.winfo_exists():
                continue
            col = getattr(t, key, None)
            if col is not None:
                w.configure(bg=col)
        except Exception:
            pass


def refresh_text_widgets() -> None:
    import theme as t

    for w in list(_text_registry):
        try:
            if not w.winfo_exists():
                continue
            w.configure(
                bg=t.INPUT_BG,
                fg=t.TEXT_MAIN,
                highlightbackground=t.INPUT_BORDER,
                insertbackground=t.TEXT_MAIN,
                font=("Segoe UI", 10),
            )
        except Exception:
            pass


def refresh_listboxes() -> None:
    import theme as t

    for w in list(_listbox_registry):
        try:
            if not w.winfo_exists():
                continue
            w.configure(
                bg=t.INPUT_BG,
                fg=t.TEXT_MAIN,
                highlightbackground=t.INPUT_BORDER,
                selectbackground=t.ACCENT,
                selectforeground=t.HEADER_FG,
            )
        except Exception:
            pass


def palette_for_preset(name: str) -> dict[str, str]:
    fac = PRESET_FACTORIES.get(name) or PRESET_FACTORIES["Dark Mode Professional"]
    return fac().copy()


def build_merged_palette(session: AppearanceSession | None = None) -> dict[str, str]:
    s = session or SESSION
    return palette_for_preset(s.preset)


def apply_session(session: AppearanceSession | None = None) -> None:
    import theme

    global SESSION
    if session is not None:
        SESSION = session
    theme.apply_runtime(build_merged_palette(SESSION))
    notify_theme_changed()


def ensure_default_applied() -> None:
    """Call once after Tk root exists so ttk.Style can run."""
    apply_session(SESSION)
