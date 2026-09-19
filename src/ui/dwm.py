# -*- coding: utf-8 -*-
"""یکپارچه‌سازی با پوستهٔ ویندوز ۱۱ (DWM) — با fallback بی‌خطر.

سه اثر که رابط را «بومیِ ویندوز ۱۱» می‌کند:
  ۱) نوار عنوان تیره   (DWMWA_USE_IMMERSIVE_DARK_MODE)
  ۲) پس‌زمینهٔ Mica     (DWMWA_SYSTEMBACKDROP_TYPE)
  ۳) گوشه‌های گرد پنجره (DWMWA_WINDOW_CORNER_PREFERENCE)

همه داخل try/except هستند: روی ویندوزهای قدیمی‌تر، روی لینوکس/مک،
یا اگر ctypes به هر دلیلی کار نکرد، هیچ اتفاقی نمی‌افتد و رابط با
QSS خودمان درست کار می‌کند. این «تزئینی» است، نه «کارکردی».
"""
from __future__ import annotations

import sys

# مقادیر ثابت DWM (از wingdi.h / dwmapi.h)
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWA_BORDER_COLOR = 34

DWMWCP_ROUND = 2          # گوشهٔ گرد
DWMSBT_MAINWINDOW = 2     # Mica
DWMSBT_TRANSIENT = 3      # Acrylic


def _hwnd(widget) -> int:
    return int(widget.winId())


def apply_win11(widget, dark_title: bool = True, mica: bool = True,
                rounded: bool = True) -> bool:
    """اعمال اثرهای ویندوز ۱۱. برمی‌گرداند آیا حداقل یکی اعمال شد."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        dwm = ctypes.windll.dwmapi          # type: ignore[attr-defined]
    except Exception:
        return False

    hwnd = _hwnd(widget)
    applied = False

    def _set(attr: int, value: int) -> bool:
        try:
            v = wintypes.BOOL(value) if attr == DWMWA_USE_IMMERSIVE_DARK_MODE \
                else ctypes.c_int(value)
            hr = dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v),
                                           ctypes.sizeof(v))
            return hr == 0
        except Exception:
            return False

    if dark_title:
        applied |= _set(DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
    if rounded:
        applied |= _set(DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)
    if mica:
        # Mica ممکن است روی بعضی نسخه‌ها نباشد؛ اگر نشد، بی‌سروصدا رد می‌شویم
        applied |= _set(DWMWA_SYSTEMBACKDROP_TYPE, DWMSBT_MAINWINDOW)
    return applied


def report() -> str:
    """برای لاگ/دیباگ: روی کدام پلتفرم هستیم."""
    return f"platform={sys.platform}"
