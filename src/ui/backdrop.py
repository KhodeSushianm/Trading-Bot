# -*- coding: utf-8 -*-
"""پس‌زمینهٔ محوِ procedural + لایهٔ شیشه — بدون QGraphicsBlurEffect.

چرا procedural و نه بلور زنده؟
  بلور زنده روی کانتینر (QGraphicsBlurEffect) همان خانوادهٔ باگی است که
  «صفحه سیاه تا درگ» را ساخت. اینجا پس‌زمینه از **گرادیان‌های شعاعیِ ذاتاً
  نرم** ساخته می‌شود و یک‌بار در یک QPixmap کش می‌شود؛ سپس یک لایهٔ سفید
  نیمه‌شفافِ ساده نقش «شیشه» را بازی می‌کند. صفر اثر گرافیکی، صفر ریسک repaint.

نگاه بصری (الگو از رفرنس):
  خاکستری روشن پایه + چند تودهٔ سفید/خاکستریِ بسیار نرم که یادآور
  یک تصویر محوِ سیاه‌وسفیدند، بدون هیچ جزئیات تیز.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QPainter, QPainterPath, QPen,
                           QPixmap, QRadialGradient)

from .theme import DARK, Theme

# توده‌های نور/سایه: (mx, my, شعاع نسبی, رنگ, آلفا)
_BLOBS = [
    (0.18, 0.10, 0.55, "#FFFFFF", 0.90),
    (0.85, 0.16, 0.50, "#FFFFFF", 0.75),
    (0.50, 0.55, 0.75, "#FFFFFF", 0.55),
    (0.08, 0.80, 0.45, "#BEBECA", 0.70),
    (0.92, 0.78, 0.50, "#B4B4C0", 0.65),
    (0.42, 0.05, 0.35, "#CFcFD8", 0.70),
    (0.68, 0.95, 0.40, "#CDCDD6", 0.45),
    (0.30, 0.40, 0.30, "#FFFFFF", 0.65),
]


def render_backdrop(size, t: Theme = DARK) -> QPixmap:
    """یک QPixmap پس‌زمینهٔ محو به اندازهٔ داده می‌سازد (کش‌پذیر)."""
    w, h = max(1, int(size.width())), max(1, int(size.height()))
    pm = QPixmap(w, h)
    pm.fill(QColor(t.bg))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    for mx, my, rad, hexc, alpha in _BLOBS:
        cx, cy = mx * w, my * h
        r = rad * max(w, h)
        g = QRadialGradient(QPointF(cx, cy), r)
        c = QColor(hexc)
        c0 = QColor(c)
        c0.setAlpha(int(255 * alpha))
        c1 = QColor(c)
        c1.setAlpha(0)
        g.setColorAt(0.0, c0)
        g.setColorAt(0.55, QColor(c.red(), c.green(), c.blue(), int(255 * alpha * 0.45)))
        g.setColorAt(1.0, c1)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), r, r)
    p.end()
    return pm


def paint_glass(p: QPainter, rect: QRect, t: Theme = DARK, radius: int = 30) -> None:
    """لایهٔ شیشه: مستطیل گردِ سفیدِ نیمه‌شفاف + حلقهٔ نورانی لبه."""
    p.setRenderHint(QPainter.Antialiasing, True)
    path = QPainterPath()
    path.addRoundedRect(QRectF(rect), radius, radius)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, int(255 * t.glass_alpha)))
    p.drawPath(path)
    # لبهٔ نورانی نازک (حس شیشه)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(255, 255, 255, 170), 1.2))
    p.drawPath(path)
