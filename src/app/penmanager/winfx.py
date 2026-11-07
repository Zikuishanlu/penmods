"""Best-effort Windows 11 chrome: light title bar, rounded corners.

All calls degrade silently on Windows 10 or when DWM refuses the attribute, so
the custom QML shell still looks right on its own.
"""
from __future__ import annotations

import ctypes
import os

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_SYSTEMBACKDROP_TYPE = 38

DWMWCP_ROUND = 2
DWMSBT_MAINWINDOW = 2        # mica
DWMSBT_TRANSIENTWINDOW = 3   # acrylic
DWMSBT_TABBEDWINDOW = 4


def _set_int(hwnd: int, attribute: int, value: int) -> bool:
    try:
        dwmapi = ctypes.windll.dwmapi
    except (AttributeError, OSError):
        return False
    val = ctypes.c_int(value)
    try:
        result = dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), ctypes.c_uint(attribute), ctypes.byref(val), ctypes.sizeof(val)
        )
    except OSError:
        return False
    return result == 0


def apply(hwnd: int) -> dict:
    """Try to make the frameless window blend into Windows 11. Returns what worked."""
    applied: dict[str, bool] = {}
    if os.name != "nt" or not hwnd:
        return applied
    applied["dark"] = _set_int(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 0)
    applied["round"] = _set_int(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)
    # No backdrop: the QML shell paints its own flat Preline surfaces.
    applied["mica"] = _set_int(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, 1)
    return applied
