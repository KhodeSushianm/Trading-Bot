# -*- coding: utf-8 -*-
"""مجموعه آیکون برداری (SVG) — سبک خطی نازک، هماهنگ با زبان Fluent.

چرا SVG به‌جای ایموجی؟
  ایموجی‌ها در ویندوز با فونت Segoe UI Emoji رندر می‌شوند که رنگی و سنگین است
  و با یک تم مونوکروم می‌جنگد. آیکون خطی (stroke ~۱.۶px) هم سبک است، هم در هر
  اندازه‌ای شارپ می‌ماند، هم رنگش را می‌توان با توکن تم کنترل کرد.

رندر: QtSvg → QImage → QIcon، با کش بر اساس (نام، اندازه، رنگ).
اگر QtSvg به هر دلیلی در دسترس نبود، به یک گلیف متنی fallback می‌شود تا
رابط هرگز بدون آیکون نماند.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

# ── بدنهٔ آیکون‌ها (viewBox 0 0 24 24) ─────────────────────────
# هر ورودی: (بدنهٔ svg, پر شود؟)
ICONS: dict[str, tuple[str, bool]] = {
    # ناوبری
    "dashboard": ('<rect x="3" y="3" width="7.5" height="9" rx="1.6"/>'
                  '<rect x="13.5" y="3" width="7.5" height="5.2" rx="1.6"/>'
                  '<rect x="13.5" y="11.8" width="7.5" height="9.2" rx="1.6"/>'
                  '<rect x="3" y="15.8" width="7.5" height="5.2" rx="1.6"/>', False),
    "target":    ('<circle cx="12" cy="12" r="8.4"/><circle cx="12" cy="12" r="4.2"/>'
                  '<circle cx="12" cy="12" r="0.9"/>', False),
    "report":    ('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
                  '<path d="M14 3v5h5"/><path d="M9 13.5h6M9 17h4"/>', False),
    "calendar":  ('<rect x="3.2" y="5" width="17.6" height="16" rx="2.2"/>'
                  '<path d="M3.2 10h17.6M8.2 3v4M15.8 3v4"/>', False),
    "sunrise":   ('<path d="M2.5 19h19"/><path d="M7 19a5 5 0 0 1 10 0"/>'
                  '<path d="M12 9.5V4.5"/><path d="M5.1 12.1 3.7 10.7M18.9 12.1l1.4-1.4"/>', False),
    "live":      ('<path d="M21.5 12h-3.6l-2.9 8.5L9 3.5 6.1 12H2.5"/>', False),
    "settings":  ('<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3"/>'
                  '<path d="M1.5 14h5M9.5 8h5M17.5 16h5"/>', False),
    # اقدام‌ها
    "play":      ('<path d="M8 5.2v13.6L19 12z"/>', True),
    "stop":      ('<rect x="6.5" y="6.5" width="11" height="11" rx="2"/>', True),
    "refresh":   ('<path d="M20.5 12a8.5 8.5 0 1 1-2.5-6"/><path d="M20.5 3.5v5h-5"/>', False),
    "send":      ('<path d="M21.5 2.5 11 13"/><path d="M21.5 2.5 14.8 21.5l-3.8-8.5-8.5-3.8z"/>', False),
    # معنا
    "shield":    ('<path d="M12 21.5s7.5-3.6 7.5-9.4V5.4L12 2.5 4.5 5.4v6.7c0 5.8 7.5 9.4 7.5 9.4z"/>', False),
    "bell":      ('<path d="M18 8.5a6 6 0 0 0-12 0c0 6.6-2.8 8.5-2.8 8.5h17.6S18 15.1 18 8.5"/>'
                  '<path d="M13.6 20.5a2 2 0 0 1-3.2 0"/>', False),
    "folder":    ('<path d="M21.5 19a2 2 0 0 1-2 2h-15a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4.6l2 3h6.4a2 2 0 0 1 2 2z"/>', False),
    "chart":     ('<path d="M3.5 3.5v17h17"/><rect x="7" y="12.5" width="2.8" height="5"/>'
                  '<rect x="12" y="8.5" width="2.8" height="9"/><rect x="17" y="5.5" width="2.8" height="12"/>', False),
    "trend_up":  ('<path d="M22 7 13.5 15.5 9 11 2 18"/><path d="M16.5 7H22v5.5"/>', False),
    "trend_down": ('<path d="M22 17 13.5 8.5 9 13 2 6"/><path d="M16.5 17H22v-5.5"/>', False),
    "clock":     ('<circle cx="12" cy="12" r="8.6"/><path d="M12 7.2V12l3.1 2"/>', False),
    "zap":       ('<path d="M13 2.5 3.5 14H12l-1 7.5L20.5 10H12l1-7.5z"/>', False),
    "info":      ('<circle cx="12" cy="12" r="8.6"/><path d="M12 16.2v-4.4"/><path d="M12 8.2h.01"/>', False),
    "check":     ('<path d="M20 6.5 9.4 17.1 4 11.7"/>', False),
    "alert":     ('<path d="M10.3 3.9 1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>'
                  '<path d="M12 9.2v4.2"/><path d="M12 17.2h.01"/>', False),
    "user":      ('<path d="M19.5 20.5v-1.8a4 4 0 0 0-4-4h-7a4 4 0 0 0-4 4v1.8"/>'
                  '<circle cx="12" cy="7.3" r="3.9"/>', False),
    "x":         ('<path d="M17.5 6.5 6.5 17.5M6.5 6.5l11 11"/>', False),
    "file_cfg":  ('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
                  '<path d="M14 3v5h5"/><path d="M10.2 14.6a2 2 0 1 0 3.6 0M12 12.6v-1"/>', False),
    # لوگو — دایره با خط صعودی داخلش (نماد تحلیل)
    "logo":      ('<circle cx="12" cy="12" r="9"/><path d="M7.5 14.5 10.8 10l2.6 2.6L16.8 8"/>', False),
}

_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" '
        'viewBox="0 0 24 24" fill="{fill}" stroke="{stroke}" stroke-width="{w}" '
        'stroke-linecap="round" stroke-linejoin="round">{body}</svg>')

_FALLBACK_GLYPHS = {
    "dashboard": "▦", "target": "◎", "report": "▤", "calendar": "▦", "sunrise": "◔",
    "live": "∿", "settings": "≡", "play": "▶", "stop": "■", "refresh": "↻",
    "send": "➤", "shield": "⛨", "bell": "🔔", "folder": "🗁", "chart": "▮",
    "trend_up": "↗", "trend_down": "↘", "clock": "◷", "zap": "⚡", "info": "ⓘ",
    "check": "✓", "alert": "⚠", "user": "◉", "x": "✕", "file_cfg": "⚙", "logo": "◍",
}


def _svg_bytes(name: str, size: int, color: str, stroke_w: float) -> Optional[bytes]:
    body, filled = ICONS.get(name, ("", False))
    if not body:
        return None
    if filled:
        fill, stroke, w = color, color, 0.0
    else:
        fill, stroke, w = "none", color, stroke_w
    return _SVG.format(s=size * 4, fill=fill, stroke=stroke, w=w, body=body).encode("utf-8")


@lru_cache(maxsize=512)
def icon(name: str, size: int = 18, color: str = "#F4F4F7", stroke_w: float = 1.6):
    """یک QIcon برداری. نتیجه کش می‌شود تا رندر تکراری هزینه نداشته باشد."""
    from PySide6.QtGui import QIcon, QImage, QPixmap

    data = _svg_bytes(name, size, color, stroke_w)
    if data:
        try:
            from PySide6.QtSvg import QSvgRenderer
            from PySide6.QtCore import Qt
            r = QSvgRenderer(data)
            if r.isValid():
                img = QImage(size * 4, size * 4, QImage.Format_ARGB32_Premultiplied)
                img.fill(Qt.transparent)
                from PySide6.QtGui import QPainter
                p = QPainter(img)
                p.setRenderHint(QPainter.Antialiasing, True)
                p.setRenderHint(QPainter.SmoothPixmapTransform, True)
                r.render(p)
                p.end()
                return QIcon(QPixmap.fromImage(img))
        except Exception:
            pass

    # fallback متنی — رابط هرگز بدون آیکون نمی‌ماند
    from PySide6.QtGui import QColor, QFont, QPainter
    from PySide6.QtCore import Qt
    img = QImage(size * 2, size * 2, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(QColor(color))
    f = QFont()
    f.setPixelSize(int(size * 1.3))
    p.setFont(f)
    p.drawText(img.rect(), Qt.AlignCenter, _FALLBACK_GLYPHS.get(name, "•"))
    p.end()
    return QIcon(QPixmap.fromImage(img))



def icon_pixmap(name: str, size: int = 18, color: str = "#F4F4F7",
                stroke_w: float = 1.6):
    """نسخهٔ QPixmap برای استفاده‌های نقاشی‌شده (مثل Splash)."""
    return icon(name, size, color, stroke_w).pixmap(size * 2, size * 2)
