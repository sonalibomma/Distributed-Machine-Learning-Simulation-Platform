"""App-wide UI preferences (session lifetime). Extensible for simulation visualization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SimulationUiSettings:
    """
    Simulation visualization and related UI toggles.

    When ``visualization_enabled`` is False, the run window skips graph highlighting,
    animation redraws, and per-frame title updates while still running the simulator
    and updating progress, summary, and logs.

    Future granular options (e.g. show_communication_paths, animate_graph_updates)
    can be added here and gated behind ``visualization_enabled``.
    """

    visualization_enabled: bool = True
    execution_mode: str = "local"


SETTINGS = SimulationUiSettings()


def apply_simulation_ui_settings(**kwargs: bool) -> None:
    """Update session settings in place (safe for ``from app_settings import SETTINGS``)."""
    for key, value in kwargs.items():
        if not hasattr(SETTINGS, key):
            raise AttributeError(f"Unknown simulation UI setting: {key!r}")
        setattr(SETTINGS, key, value)


def set_execution_mode(mode: str) -> None:
    SETTINGS.execution_mode = "remote" if str(mode).strip().lower().startswith("remote") else "local"
