from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from system_appearance import detect_os_appearance

FOLLOW_SYSTEM = "Follow System"


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
        "LIST_SURFACE_BG",
        "INPUT_BORDER",
        "TEXT_MAIN",
        "BTN_PRIMARY_BG",
        "BTN_PRIMARY_HOVER",
        "BTN_SECONDARY_BG",
        "BTN_SECONDARY_HOVER",
        "BTN_DANGER_BG",
        "BTN_DANGER_HOVER",
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
        "VALIDATION_SUCCESS",
        "VALIDATION_WARN",
        "VALIDATION_ERROR",
        "TAB_BUTTON_BG",
        "TAB_BUTTON_HOVER",
        "GRAPH_NODE_BASE",
        "GRAPH_NODE_ACTIVE",
        "GRAPH_COMM",
        "GRAPH_NODE_SENDER",
        "GRAPH_NODE_RECEIVER",
        "GRAPH_NODE_DROPOUT",
        "GRAPH_NODE_INTERRUPT",
        "GRAPH_NODE_AGGREGATION",
        "GRAPH_EDGE_BASE",
        "GRAPH_EDGE_ACTIVE",
        "GRAPH_EDGE_DROPOUT",
        "GRAPH_EDGE_DELIVERY",
        "LOG_SUCCESS",
        "LOG_ERROR",
        "NOTEBOOK_TAB_SELECTED_FG",
    }
)


def _system_light_preset() -> dict[str, str]:
    """Professional light theme — matches OS light mode / user specification."""
    return {
        "BG_MAIN": "#F5F7FA",
        "PANEL_BLUE": "#FFFFFF",
        "PANEL_GREEN": "#FFFFFF",
        "HEADER_GREEN": "#F5F7FA",
        "HEADER_BLUE": "#F5F7FA",
        "HEADER_FG": "#4A90E2",
        "BORDER": "#C5CDD8",
        "BORDER_INNER": "#D9DEE5",
        "INPUT_BG": "#FFFFFF",
        "LIST_SURFACE_BG": "#F5F7FA",
        "INPUT_BORDER": "#D9DEE5",
        "TEXT_MAIN": "#2C3E50",
        "BTN_PRIMARY_BG": "#4A90E2",
        "BTN_PRIMARY_HOVER": "#357ABD",
        "BTN_SECONDARY_BG": "#EEF2F7",
        "BTN_SECONDARY_HOVER": "#D9E6F5",
        "PROGRESS_BAR": "#4A90E2",
        "PROGRESS_TROUGH": "#E8ECF1",
        "ACCENT": "#4A90E2",
        "GRAPH_AREA_BG": "#FFFFFF",
        "GRAPH_AREA_FG": "#2C3E50",
        "SUMMARY_BG": "#FFFFFF",
        "SCROLLBAR_TRACK": "#EEF2F7",
        "SCROLLBAR_THUMB": "#C5CDD8",
        "TOOLTIP_BG": "#FFFFFF",
        "MUTED_TEXT": "#6B7280",
        "VALIDATION_SUCCESS": "#16A34A",
        "VALIDATION_WARN": "#F97316",
        "VALIDATION_ERROR": "#DC2626",
        "TAB_BUTTON_BG": "#EEF2F7",
        "TAB_BUTTON_HOVER": "#D9E6F5",
        "GRAPH_NODE_BASE": "#4A90E2",
        "GRAPH_NODE_ACTIVE": "#22C55E",
        "GRAPH_COMM": "#8B5CF6",
        "GRAPH_NODE_SENDER": "#F97316",
        "GRAPH_NODE_RECEIVER": "#8B5CF6",
        "GRAPH_NODE_DROPOUT": "#DC2626",
        "GRAPH_NODE_INTERRUPT": "#9CA3AF",
        "GRAPH_NODE_AGGREGATION": "#7C3AED",
        "GRAPH_EDGE_BASE": "#9CA3AF",
        "GRAPH_EDGE_ACTIVE": "#4A90E2",
        "GRAPH_EDGE_DROPOUT": "#DC2626",
        "GRAPH_EDGE_DELIVERY": "#F97316",
        "LOG_SUCCESS": "#16A34A",
        "LOG_ERROR": "#DC2626",
        "NOTEBOOK_TAB_SELECTED_FG": "#FFFFFF",
    }


def _system_dark_preset() -> dict[str, str]:
    """Professional dark theme — used when OS is in dark mode."""
    return {
        "BG_MAIN": "#1A1D23",
        "PANEL_BLUE": "#252830",
        "PANEL_GREEN": "#252830",
        "HEADER_GREEN": "#2A2F3A",
        "HEADER_BLUE": "#2A2F3A",
        "HEADER_FG": "#7CB8FF",
        "BORDER": "#3D4452",
        "BORDER_INNER": "#343A47",
        "INPUT_BG": "#2A2F3A",
        "LIST_SURFACE_BG": "#1E222A",
        "INPUT_BORDER": "#4A5262",
        "TEXT_MAIN": "#E8ECF1",
        "BTN_PRIMARY_BG": "#4A90E2",
        "BTN_PRIMARY_HOVER": "#357ABD",
        "BTN_SECONDARY_BG": "#343A47",
        "BTN_SECONDARY_HOVER": "#4A5262",
        "PROGRESS_BAR": "#4A90E2",
        "PROGRESS_TROUGH": "#2A2F3A",
        "ACCENT": "#7CB8FF",
        "GRAPH_AREA_BG": "#1E222A",
        "GRAPH_AREA_FG": "#E8ECF1",
        "SUMMARY_BG": "#252830",
        "SCROLLBAR_TRACK": "#2A2F3A",
        "SCROLLBAR_THUMB": "#4A5262",
        "TOOLTIP_BG": "#2A2F3A",
        "MUTED_TEXT": "#94A3B8",
        "VALIDATION_SUCCESS": "#4ADE80",
        "VALIDATION_WARN": "#FB923C",
        "VALIDATION_ERROR": "#F87171",
        "TAB_BUTTON_BG": "#343A47",
        "TAB_BUTTON_HOVER": "#4A5262",
        "GRAPH_NODE_BASE": "#60A5FA",
        "GRAPH_NODE_ACTIVE": "#4ADE80",
        "GRAPH_COMM": "#A78BFA",
        "GRAPH_NODE_SENDER": "#FB923C",
        "GRAPH_NODE_RECEIVER": "#A78BFA",
        "GRAPH_NODE_DROPOUT": "#F87171",
        "GRAPH_NODE_INTERRUPT": "#6B7280",
        "GRAPH_NODE_AGGREGATION": "#C084FC",
        "GRAPH_EDGE_BASE": "#6B7280",
        "GRAPH_EDGE_ACTIVE": "#60A5FA",
        "GRAPH_EDGE_DROPOUT": "#F87171",
        "GRAPH_EDGE_DELIVERY": "#FB923C",
        "LOG_SUCCESS": "#4ADE80",
        "LOG_ERROR": "#F87171",
        "NOTEBOOK_TAB_SELECTED_FG": "#FFFFFF",
    }


def _enrich_palette(raw: dict[str, str]) -> dict[str, str]:
    """Fill graph/validation keys for legacy presets missing semantic colors."""
    p = raw.copy()
    is_light = _luminance(p.get("BG_MAIN", "#000000")) > 0.45
    if is_light:
        defaults = {
            "VALIDATION_SUCCESS": "#16A34A",
            "VALIDATION_ERROR": p.get("LOG_ERROR", "#DC2626"),
            "GRAPH_NODE_SENDER": "#F97316",
            "GRAPH_NODE_RECEIVER": "#8B5CF6",
            "GRAPH_NODE_DROPOUT": "#DC2626",
            "GRAPH_NODE_INTERRUPT": "#9CA3AF",
            "GRAPH_NODE_AGGREGATION": p.get("GRAPH_COMM", "#7C3AED"),
            "GRAPH_EDGE_DROPOUT": "#DC2626",
            "GRAPH_EDGE_DELIVERY": "#F97316",
        }
    else:
        defaults = {
            "VALIDATION_SUCCESS": "#4ADE80",
            "VALIDATION_ERROR": p.get("LOG_ERROR", "#F87171"),
            "GRAPH_NODE_SENDER": "#FB923C",
            "GRAPH_NODE_RECEIVER": "#A78BFA",
            "GRAPH_NODE_DROPOUT": "#F87171",
            "GRAPH_NODE_INTERRUPT": "#6B7280",
            "GRAPH_NODE_AGGREGATION": p.get("GRAPH_COMM", "#C084FC"),
            "GRAPH_EDGE_DROPOUT": "#F87171",
            "GRAPH_EDGE_DELIVERY": "#FB923C",
        }
    for k, v in defaults.items():
        p.setdefault(k, v)
    p.setdefault("LIST_SURFACE_BG", p.get("BG_MAIN", "#F5F7FA"))
    if "VALIDATION_WARN" not in p:
        p["VALIDATION_WARN"] = "#F97316" if is_light else "#FB923C"
    return p


def _luminance(hex_color: str) -> float:
    try:
        h = hex_color.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    except Exception:
        return 0.0


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
    """White surfaces, gray borders, black text — minimal styling without blue accents."""
    return {
        "BG_MAIN": "#FFFFFF",
        "PANEL_BLUE": "#FFFFFF",
        "PANEL_GREEN": "#FFFFFF",
        "HEADER_GREEN": "#FFFFFF",
        "HEADER_BLUE": "#FFFFFF",
        "HEADER_FG": "#000000",
        "BORDER": "#B0B0B0",
        "BORDER_INNER": "#D0D0D0",
        "INPUT_BG": "#FFFFFF",
        "LIST_SURFACE_BG": "#FFFFFF",
        "INPUT_BORDER": "#B0B0B0",
        "TEXT_MAIN": "#000000",
        "BTN_PRIMARY_BG": "#404040",
        "BTN_PRIMARY_HOVER": "#606060",
        "BTN_SECONDARY_BG": "#F0F0F0",
        "BTN_SECONDARY_HOVER": "#E0E0E0",
        "PROGRESS_BAR": "#606060",
        "PROGRESS_TROUGH": "#E8E8E8",
        "ACCENT": "#404040",
        "GRAPH_AREA_BG": "#FFFFFF",
        "GRAPH_AREA_FG": "#000000",
        "SUMMARY_BG": "#FFFFFF",
        "SCROLLBAR_TRACK": "#F0F0F0",
        "SCROLLBAR_THUMB": "#C0C0C0",
        "TOOLTIP_BG": "#FFFFFF",
        "MUTED_TEXT": "#505050",
        "VALIDATION_SUCCESS": "#2E7D32",
        "VALIDATION_WARN": "#8B0000",
        "VALIDATION_ERROR": "#8B0000",
        "TAB_BUTTON_BG": "#F0F0F0",
        "TAB_BUTTON_HOVER": "#E0E0E0",
        "GRAPH_NODE_BASE": "#606060",
        "GRAPH_NODE_ACTIVE": "#404040",
        "GRAPH_COMM": "#505050",
        "GRAPH_NODE_SENDER": "#707070",
        "GRAPH_NODE_RECEIVER": "#909090",
        "GRAPH_NODE_DROPOUT": "#8B0000",
        "GRAPH_NODE_INTERRUPT": "#505050",
        "GRAPH_NODE_AGGREGATION": "#404040",
        "GRAPH_EDGE_BASE": "#C0C0C0",
        "GRAPH_EDGE_ACTIVE": "#606060",
        "GRAPH_EDGE_DROPOUT": "#8B0000",
        "GRAPH_EDGE_DELIVERY": "#404040",
        "LOG_SUCCESS": "#2E7D32",
        "LOG_ERROR": "#8B0000",
        "NOTEBOOK_TAB_SELECTED_FG": "#000000",
    }


def _pure_black_professional_preset() -> dict[str, str]:
    """Black surfaces, gray borders, white text — minimal styling without blue accents."""
    return {
        "BG_MAIN": "#000000",
        "PANEL_BLUE": "#0A0A0A",
        "PANEL_GREEN": "#0A0A0A",
        "HEADER_GREEN": "#0A0A0A",
        "HEADER_BLUE": "#0A0A0A",
        "HEADER_FG": "#FFFFFF",
        "BORDER": "#606060",
        "BORDER_INNER": "#404040",
        "INPUT_BG": "#121212",
        "LIST_SURFACE_BG": "#000000",
        "INPUT_BORDER": "#606060",
        "TEXT_MAIN": "#FFFFFF",
        "BTN_PRIMARY_BG": "#B0B0B0",
        "BTN_PRIMARY_HOVER": "#D0D0D0",
        "BTN_SECONDARY_BG": "#1A1A1A",
        "BTN_SECONDARY_HOVER": "#2A2A2A",
        "PROGRESS_BAR": "#B0B0B0",
        "PROGRESS_TROUGH": "#1A1A1A",
        "ACCENT": "#B0B0B0",
        "GRAPH_AREA_BG": "#000000",
        "GRAPH_AREA_FG": "#FFFFFF",
        "SUMMARY_BG": "#0A0A0A",
        "SCROLLBAR_TRACK": "#1A1A1A",
        "SCROLLBAR_THUMB": "#505050",
        "TOOLTIP_BG": "#121212",
        "MUTED_TEXT": "#B0B0B0",
        "VALIDATION_SUCCESS": "#90EE90",
        "VALIDATION_WARN": "#FFB0B0",
        "VALIDATION_ERROR": "#FFB0B0",
        "TAB_BUTTON_BG": "#1A1A1A",
        "TAB_BUTTON_HOVER": "#2A2A2A",
        "GRAPH_NODE_BASE": "#B0B0B0",
        "GRAPH_NODE_ACTIVE": "#FFFFFF",
        "GRAPH_COMM": "#909090",
        "GRAPH_NODE_SENDER": "#D0D0D0",
        "GRAPH_NODE_RECEIVER": "#A0A0A0",
        "GRAPH_NODE_DROPOUT": "#FFB0B0",
        "GRAPH_NODE_INTERRUPT": "#909090",
        "GRAPH_NODE_AGGREGATION": "#E0E0E0",
        "GRAPH_EDGE_BASE": "#505050",
        "GRAPH_EDGE_ACTIVE": "#B0B0B0",
        "GRAPH_EDGE_DROPOUT": "#FFB0B0",
        "GRAPH_EDGE_DELIVERY": "#E0E0E0",
        "LOG_SUCCESS": "#90EE90",
        "LOG_ERROR": "#FFB0B0",
        "NOTEBOOK_TAB_SELECTED_FG": "#FFFFFF",
    }


def _ml_platform_preset() -> dict[str, str]:
    """Premium ML research platform — Cursor / Docker Desktop aesthetic."""
    return {
        "BG_MAIN": "#0F172A",
        "PANEL_BLUE": "#1E293B",
        "PANEL_GREEN": "#1E293B",
        "HEADER_GREEN": "#1E293B",
        "HEADER_BLUE": "#1E293B",
        "HEADER_FG": "#3B82F6",
        "BORDER": "#334155",
        "BORDER_INNER": "#293548",
        "INPUT_BG": "#0F172A",
        "LIST_SURFACE_BG": "#0F172A",
        "INPUT_BORDER": "#475569",
        "TEXT_MAIN": "#F8FAFC",
        "BTN_PRIMARY_BG": "#2563EB",
        "BTN_PRIMARY_HOVER": "#1D4ED8",
        "BTN_SECONDARY_BG": "#334155",
        "BTN_SECONDARY_HOVER": "#475569",
        "BTN_DANGER_BG": "#EF4444",
        "BTN_DANGER_HOVER": "#DC2626",
        "PROGRESS_BAR": "#3B82F6",
        "PROGRESS_TROUGH": "#1E293B",
        "ACCENT": "#3B82F6",
        "GRAPH_AREA_BG": "#0F172A",
        "GRAPH_AREA_FG": "#F8FAFC",
        "SUMMARY_BG": "#1E293B",
        "SCROLLBAR_TRACK": "#1E293B",
        "SCROLLBAR_THUMB": "#475569",
        "TOOLTIP_BG": "#1E293B",
        "MUTED_TEXT": "#94A3B8",
        "VALIDATION_SUCCESS": "#22C55E",
        "VALIDATION_WARN": "#F59E0B",
        "VALIDATION_ERROR": "#EF4444",
        "TAB_BUTTON_BG": "#252B36",
        "TAB_BUTTON_HOVER": "#353D4D",
        "GRAPH_NODE_BASE": "#3B82F6",
        "GRAPH_NODE_ACTIVE": "#22C55E",
        "GRAPH_COMM": "#A78BFA",
        "GRAPH_NODE_SENDER": "#F59E0B",
        "GRAPH_NODE_RECEIVER": "#A78BFA",
        "GRAPH_NODE_DROPOUT": "#EF4444",
        "GRAPH_NODE_INTERRUPT": "#64748B",
        "GRAPH_NODE_AGGREGATION": "#8B5CF6",
        "GRAPH_EDGE_BASE": "#454B58",
        "GRAPH_EDGE_ACTIVE": "#3B82F6",
        "GRAPH_EDGE_DROPOUT": "#EF4444",
        "GRAPH_EDGE_DELIVERY": "#F59E0B",
        "LOG_SUCCESS": "#22C55E",
        "LOG_ERROR": "#EF4444",
        "NOTEBOOK_TAB_SELECTED_FG": "#F8FAFC",
    }


PRESET_FACTORIES: dict[str, Callable[[], dict[str, str]]] = {
    FOLLOW_SYSTEM: _system_light_preset,
    "System Light": _system_light_preset,
    "System Dark": _system_dark_preset,
    "ML Platform": _ml_platform_preset,
    "Default Classic": _classic_preset,
    "Dark Mode Professional": _dark_professional_preset,
    "Neon Tech": _neon_tech_preset,
    "Midnight Blue": _midnight_blue_preset,
    "Forest Tech": _forest_tech_preset,
    "Light Minimal": _light_minimal_preset,
    "Pure White Professional": _pure_white_professional_preset,
    "Pure Black Professional": _pure_black_professional_preset,
}

PRESET_ORDER: tuple[str, ...] = (FOLLOW_SYSTEM,) + tuple(
    k for k in PRESET_FACTORIES if k not in (FOLLOW_SYSTEM, "System Light", "System Dark")
)


@dataclass
class AppearanceSession:
    """Persisted theme choice; default is the ML Platform dashboard theme."""

    preset: str = "ML Platform"


SESSION = AppearanceSession()

_last_detected_appearance: str | None = None
_theme_watch_after_id: str | None = None

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
                font=(t.FONT_FAMILY, 10),
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
                bg=t.LIST_SURFACE_BG,
                fg=t.TEXT_MAIN,
                highlightbackground=t.BORDER,
                highlightthickness=1,
                selectbackground=t.BTN_PRIMARY_BG,
                selectforeground=t.NOTEBOOK_TAB_SELECTED_FG,
            )
        except Exception:
            pass


def resolve_preset_name(session: AppearanceSession | None = None) -> str:
    """Map session preset to an concrete palette factory name."""
    s = session or SESSION
    if s.preset == FOLLOW_SYSTEM:
        return "System Dark" if detect_os_appearance() == "dark" else "System Light"
    return s.preset


def palette_for_preset(name: str) -> dict[str, str]:
    if name == FOLLOW_SYSTEM:
        name = resolve_preset_name(AppearanceSession(preset=FOLLOW_SYSTEM))
    fac = PRESET_FACTORIES.get(name) or PRESET_FACTORIES["System Light"]
    return _enrich_palette(fac())


def build_merged_palette(session: AppearanceSession | None = None) -> dict[str, str]:
    s = session or SESSION
    return palette_for_preset(resolve_preset_name(s))


def apply_session(session: AppearanceSession | None = None) -> None:
    import theme

    global SESSION, _last_detected_appearance
    if session is not None:
        SESSION = session
    _last_detected_appearance = detect_os_appearance()
    theme.apply_runtime(build_merged_palette(SESSION))
    notify_theme_changed()


def ensure_default_applied() -> None:
    """Call once after Tk root exists so ttk.Style can run."""
    apply_session(SESSION)


def start_system_theme_watch(root: Any, *, interval_ms: int = 8000) -> None:
    """
    Poll OS appearance while preset is Follow System; re-apply when mode changes.
    Safe to call once at startup.
    """
    global _theme_watch_after_id, _last_detected_appearance

    def _poll() -> None:
        global _theme_watch_after_id, _last_detected_appearance
        _theme_watch_after_id = None
        try:
            if not root.winfo_exists():
                return
        except Exception:
            return
        if SESSION.preset != FOLLOW_SYSTEM:
            return
        current = detect_os_appearance()
        if _last_detected_appearance is not None and current != _last_detected_appearance:
            apply_session(SESSION)
        _last_detected_appearance = current
        try:
            _theme_watch_after_id = root.after(interval_ms, _poll)
        except Exception:
            pass

    _last_detected_appearance = detect_os_appearance()
    if SESSION.preset == FOLLOW_SYSTEM:
        try:
            _theme_watch_after_id = root.after(interval_ms, _poll)
        except Exception:
            pass


def stop_system_theme_watch(root: Any) -> None:
    global _theme_watch_after_id
    if _theme_watch_after_id is not None:
        try:
            root.after_cancel(_theme_watch_after_id)
        except Exception:
            pass
        _theme_watch_after_id = None
