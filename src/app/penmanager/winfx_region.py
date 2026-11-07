"""Windows 10 compatible rounded window corners via SetWindowRgn."""
from __future__ import annotations

import ctypes
import os


def apply_round_region(hwnd: int, width: int, height: int, radius: int) -> bool:
    """Clip the window to a rounded rectangle (works on Windows 10)."""
    if os.name != "nt" or not hwnd or width <= 0 or height <= 0 or radius <= 0:
        return False
    try:
        gdi32 = ctypes.windll.gdi32
        user32 = ctypes.windll.user32
    except (AttributeError, OSError):
        return False
    dialog_units = max(2, radius * 2)
    try:
        region = gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, dialog_units, dialog_units)
        if not region:
            return False
        if not user32.SetWindowRgn(ctypes.c_void_p(hwnd), ctypes.c_void_p(region), True):
            gdi32.DeleteObject(ctypes.c_void_p(region))
            return False
    except OSError:
        return False
    return True
