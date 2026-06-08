from __future__ import annotations

import os
import subprocess
import sys
from typing import Literal

AppearanceMode = Literal["light", "dark"]


def detect_os_appearance() -> AppearanceMode:
    """
    Best-effort OS appearance detection.

    macOS: ``defaults read -g AppleInterfaceStyle``
    Windows: ``AppsUseLightTheme`` registry value
    Linux: GNOME ``color-scheme`` gsettings, then ``GTK_THEME`` env hint
    """
    if sys.platform == "darwin":
        return _detect_macos()
    if sys.platform == "win32":
        return _detect_windows()
    return _detect_linux()


def appearance_label(mode: AppearanceMode) -> str:
    return "Dark" if mode == "dark" else "Light"


def _detect_macos() -> AppearanceMode:
    try:
        out = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if out.returncode == 0 and "dark" in out.stdout.strip().lower():
            return "dark"
    except Exception:
        pass
    return "light"


def _detect_windows() -> AppearanceMode:
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        try:
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if int(val) == 1 else "dark"
        finally:
            winreg.CloseKey(key)
    except Exception:
        pass
    return "light"


def _detect_linux() -> AppearanceMode:
    try:
        out = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if out.returncode == 0:
            txt = out.stdout.strip().lower()
            if "dark" in txt:
                return "dark"
            if "light" in txt:
                return "light"
    except Exception:
        pass

    try:
        out = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if out.returncode == 0 and "dark" in out.stdout.strip().lower():
            return "dark"
    except Exception:
        pass

    gtk = os.environ.get("GTK_THEME", "")
    if gtk and "dark" in gtk.lower():
        return "dark"
    return "light"
