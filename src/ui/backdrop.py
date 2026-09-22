# -*- coding: utf-8 -*-
"""پس‌زمینهٔ «شفق» (Aurora) — procedural، متحرک، بدون QGraphicsBlurEffect.

چرا procedural و نه بلور زنده؟
  بلور زنده روی کانتینر (QGraphicsBlurEffect) همان خانوادهٔ باگی است که
  «صفحه سیاه تا درگ» را ساخت. اینجا پس‌زمینه از **گرادیان‌های شعاعیِ ذاتاً
  نرم** ساخته می‌شود؛ یک لایهٔ سفید نیمه‌شفاف نقش «شیشه» را بازی می‌کند.
  صفر اثر گرافیکی، صفر ریسک repaint.

ترفد کارایی (v0.20.0):
  شفق در یک پیکس‌مپ **کم‌قطع** (پیش‌فرض عرض ۵۱۲) رندر و هنگام کشیدن با
  SmoothPixmapTransform بزرگ می‌شود. گرادیان‌ها ذاتاً نرم‌اند، پس بزرگ‌سازی
  هیچ اثر پیکلی ندارد — ولی هزینهٔ هر فریم ~۵۰ برابر کمتر می‌شود و
  انیمیشنِ موج‌های شفق حتی روی ماشین‌های ضعیف روان می‌ماند.

حرکت: `phase` یک عدد پیوسته است؛ هر توده با سینوس/کسینوسِ آرامِ خودش
around جای پایه‌اش شناور می‌شود. phase=None یعنی نسخهٔ ایستا (سازگار با قبل).
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QRadialGradient)

from .theme import DARK, Theme

# توده‌های شفق: (mx, my, شعاع نسبی, رنگ, آلفا, دامنهٔ موج, سرعت, فاز)
# موج‌ها خیلی کندند (ضریب ۰.۲۵–۰.۶) تا حرکت «تنفسی» باشد نه بازیگوش.
_BLOBS = [
    (0.18, 0.10, 0.55, "#FFFFFF", 0.90, 0.010, 0.31, 0.0),
    (0.85, 0.16, 0.50, "#FFFFFF", 0.72, 0.014, 0.26, 1.7),
    (0.50, 0.55, 0.75, "#FFFFFF", 0.55, 0.010, 0.21, 3.1),
    (0.08, 0.80, 0.45, "#BEBECA", 0.70, 0.016, 0.24, 4.4),
    (0.92, 0.78, 0.50, "#B4B4C0", 0.65, 0.014, 0.28, 5.9),
    (0.42, 0.05, 0.35, "#CFCFD8", 0.70, 0.012, 0.33, 0.8),
    (0.68, 0.95, 0.40, "#CDCDD6", 0.45, 0.015, 0.30, 2.2),
    (0.30, 0.40, 0.30, "#FFFFFF", 0.65, 0.010, 0.35, 3.9),
]

# توده‌های رنگیِ شفق — آلفای خیلی پایین؛ فقط «حس» رنگ، نه رنگِ جیغ
_AURORA = [
    (0.24, 0.22, 0.46, "aurora_indigo", 0.10, 0.020, 0.25, 0.4),
    (0.78, 0.16, 0.42, "aurora_cyan", 0.09, 0.022, 0.31, 2.4),
    (0.62, 0.82, 0.40, "aurora_pink", 0.07, 0.018, 0.27, 4.2),
    (0.10, 0.62, 0.34, "aurora_cyan", 0.05, 0.020, 0.22, 5.5),
]

_LOW_W = 512      # عرض رندر کم‌قطع (بزرگ‌سازی نرم، هزینهٔ ناچیز)


def _blob_positions(phase):
    """جای توده‌ها در phase داده‌شده (None = ایستا)."""
    out = []
    for mx, my, rad, hexc, alpha, amp, spd, off in _BLOBS:
        if phase is None:
            dx = dy = 0.0
        else:
            dx = amp * math.sin(phase * spd + off)
            dy = amp * 0.6 * math.cos(phase * spd * 0.8 + off * 1.7)
        out.append((mx + dx, my + dy, rad, hexc, alpha))
    return out


def _aurora_positions(phase, t: Theme):
    out = []
    for mx, my, rad, token, alpha, amp, spd, off in _AURORA:
        if phase is None:
            dx = dy = 0.0
        else:
            dx = amp * math.cos(phase * spd + off)
            dy = amp * 0.7 * math.sin(phase * spd * 0.9 + off * 1.3)
        out.append((mx + dx, my + dy, rad, getattr(t, token), alpha))
    return out


def render_aurora(size, t: Theme = DARK, phase: float | None = None,
                  dark: bool = False) -> QPixmap:
    """پیکس‌مپ کم‌قطعِ شفق — برای کشیدن با بزرگ‌سازی نرم.

    `dark=True` نسخهٔ جوهری (پس‌زمینهٔ صفحهٔ ورود/Splash) می‌سازد:
    پایهٔ تقریباً سیاه + توده‌های سفیدِ محو + شفق پررنگ‌تر.
    """
    w, h = max(1, int(size.width())), max(1, int(size.height()))
    scale = _LOW_W / max(w, 1)
    lw, lh = _LOW_W, max(1, int(h * scale))
    pm = QPixmap(lw, lh)
    base = QColor(t.onb_bg if dark else t.bg)
    pm.fill(base)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)

    # شفق رنگی زیر لایهٔ سفید (در حالت تیره پررنگ‌تر)
    for mx, my, rad, hexc, alpha in _aurora_positions(phase, t):
        a = alpha * (3.4 if dark else 1.5)
        _blob(p, mx * lw, my * lh, rad * max(lw, lh), hexc, a)

    if dark:
        # در حالت تیره، توده‌های «سفید» به توده‌های جوهریِ کمی روشن‌تر تبدیل می‌شوند
        for mx, my, rad, hexc, alpha in _blob_positions(phase):
            col = "#232330" if hexc == "#FFFFFF" else "#191922"
            _blob(p, mx * lw, my * lh, rad * max(lw, lh), col, alpha * 0.8)
    else:
        for mx, my, rad, hexc, alpha in _blob_positions(phase):
            _blob(p, mx * lw, my * lh, rad * max(lw, lh), hexc, alpha)

    # وینیت ملایمِ پایین (سنگینیِ پریمیوم)
    g = QLinearGradient(0, lh * 0.55, 0, lh)
    vg = QColor(10, 10, 16)
    vg.setAlpha(0 if not dark else 90)
    g.setColorAt(0.0, QColor(0, 0, 0, 0))
    g.setColorAt(1.0, vg if dark else QColor(24, 24, 34, 26))
    p.setBrush(QBrush(g))
    p.drawRect(0, 0, lw, lh)
    p.end()
    return pm


def _blob(p: QPainter, cx: float, cy: float, r: float, hexc: str,
          alpha: float) -> None:
    g = QRadialGradient(QPointF(cx, cy), r)
    c = QColor(hexc)
    c0 = QColor(c)
    c0.setAlpha(int(255 * min(1.0, alpha)))
    mid = QColor(c)
    mid.setAlpha(int(255 * min(1.0, alpha) * 0.45))
    g.setColorAt(0.0, c0)
    g.setColorAt(0.55, mid)
    g.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(cx, cy), r, r)


def render_backdrop(size, t: Theme = DARK, phase: float | None = None) -> QPixmap:
    """پس‌زمینهٔ کامل به اندازهٔ داده‌شده (سازگار با امضای قبلی).

    برای حالت ایستا/کش‌شده: شفق کم‌قطع رندر و هم‌اندازه بزرگ می‌شود.
    """
    pm = render_aurora(size, t, phase)
    w, h = max(1, int(size.width())), max(1, int(size.height()))
    if pm.width() == w and pm.height() == h:
        return pm
    return pm.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def paint_glass(p: QPainter, rect: QRect, t: Theme = DARK, radius: int = 30) -> None:
    """لایهٔ شیشه: مستطیل گردِ سفیدِ نیمه‌شفاف + حلقهٔ نورانی لبه.

    v0.20.0: یک درخششِ هلالی بالای لبه هم اضافه شد — حس شیشهٔ ضخیم.
    """
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
    # هلالِ درخشش در بالای شیشه
    hl = QRectF(rect)
    hl.setHeight(min(64.0, hl.height() * 0.18))
    g = QLinearGradient(0, hl.top(), 0, hl.bottom())
    g.setColorAt(0.0, QColor(255, 255, 255, 150))
    g.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.save()
    p.setClipPath(path)
    p.drawRoundedRect(hl, radius, radius)
    p.restore()
