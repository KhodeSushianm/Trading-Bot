# -*- coding: utf-8 -*-
"""انیمیشن‌های ظریف (Motion) — مطابق انتخاب کاربر: «ظریف و حرفه‌ای».

چیزهایی که اینجا ساخته می‌شود:
  • محو/پررنگ شدن (fade) برای ورود صفحات و Splash
  • جابه‌جایی نرم نشانگرِ ریل ناوبری (nav indicator)
  • نقطهٔ وضعیتِ تپنده (pulse) برای حالت «در حال اجرا»
  • ورود کارت‌ها با کمی جابه‌جایی عمودی (stagger)

قاعدهٔ طراحی: هیچ انیمیشنی بیشتر از ~۳۰۰ms طول نمی‌کشد و هیچ‌کدام
«بلوکه‌کننده» نیست. هدف این است که رابط «زنده» به نظر برسد، نه «شلوغ».
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import (Property, QEasingCurve, QPoint,
                            QPropertyAnimation, Qt, QTimer)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

# منحنی استاندارد Fluent — شروع سریع، فرود نرم
EASE = QEasingCurve.Type.OutCubic
EASE_INOUT = QEasingCurve.Type.InOutCubic
DUR_FAST = 140
DUR_MED = 220
DUR_SLOW = 320

# کلید سراسری: با ui.animations=false در config، همهٔ انیمیشن‌ها آنی می‌شوند
# (برای کاربران حساس به حرکت یا سیستم‌های کند). بدون آن ویجت‌ها همان ظاهر
# نهایی را بدون گذار می‌گیرند.
ANIMATIONS = True


def set_animations(on: bool) -> None:
    global ANIMATIONS
    ANIMATIONS = bool(on)


def _keep(widget: QWidget, anim) -> None:
    """نگه‌داشتن مرجع انیمیشن تا GC نشود."""
    running = getattr(widget, "_fx_running", None)
    if running is None:
        running = []
        widget._fx_running = running      # noqa: SLF001
    running.append(anim)
    anim.destroyed.connect(lambda *_: running.remove(anim) if anim in running else None)


def fade(widget: QWidget, start: float = 0.0, end: float = 1.0,
         ms: int = DUR_MED, easing=EASE, on_finished: Optional[Callable] = None,
         delete_effect: bool = False) -> QPropertyAnimation:
    """محو/پررنگ شدن یک ویجت با QGraphicsOpacityEffect."""
    eff = widget.graphicsEffect()
    if not isinstance(eff, QGraphicsOpacityEffect):
        eff = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(eff)
    eff.setOpacity(start)
    if not ANIMATIONS:
        eff.setOpacity(end)
        if on_finished:
            on_finished()
        return None
    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(easing)

    def _done():
        if delete_effect:
            widget.setGraphicsEffect(None)
        if on_finished:
            on_finished()

    anim.finished.connect(_done)
    _keep(widget, anim)
    anim.start()
    return anim


def rise(widget: QWidget, dy: int = 10, ms: int = DUR_MED, delay: int = 0) -> None:
    """ورود کارت از کمی پایین‌تر + محو شدن هم‌زمان (حس «نشستن» در جا)."""
    base = widget.pos()
    if not ANIMATIONS:
        return
    widget.move(base.x(), base.y() + dy)
    fade(widget, 0.0, 1.0, ms)

    anim = QPropertyAnimation(widget, b"pos", widget)
    anim.setDuration(ms)
    anim.setStartValue(QPoint(base.x(), base.y() + dy))
    anim.setEndValue(base)
    anim.setEasingCurve(EASE)
    if delay:
        anim.setStartDelay(delay)
    _keep(widget, anim)
    anim.start()


def slide_indicator(indicator: QWidget, target_y: int, height: int,
                    ms: int = DUR_MED) -> None:
    """نشانگر ریل ناوبری را نرم به آیتم فعال می‌برد."""
    geo = indicator.geometry()
    if not ANIMATIONS:
        from PySide6.QtCore import QRect
        indicator.setGeometry(QRect(geo.x(), target_y, geo.width(), height))
        return
    anim = QPropertyAnimation(indicator, b"geometry", indicator)
    anim.setDuration(ms)
    anim.setStartValue(geo)
    anim.setEndValue(indicator.parentWidget().rect().adjusted(0, 0, 0, 0)
                     .adjusted(0, target_y, 0, target_y + height - geo.height())
                     .adjusted(0, 0, 0, 0))
    from PySide6.QtCore import QRect
    x = geo.x()
    w = geo.width()
    anim.setEndValue(QRect(x, target_y, w, height))
    anim.setEasingCurve(EASE_INOUT)
    _keep(indicator, anim)
    anim.start()


class PulseDot(QWidget):
    """نقطهٔ وضعیت با تپش ملایم — فقط وقتی «در حال اجرا» است می‌تپد."""

    def __init__(self, color: str = "#3ECF8E", size: int = 9, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._phase = 0.0
        self._size = size
        self.setFixedSize(size * 3, size * 3)
        self._anim = QPropertyAnimation(self, b"phase", self)
        self._anim.setDuration(1600)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setLoopCount(-1)                     # بی‌نهایت
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulsing = False

    @Property(float)
    def phase(self) -> float:
        return self._phase

    @phase.setter
    def phase(self, v: float) -> None:
        self._phase = v
        self.update()

    def set_color(self, hex_color: str) -> None:
        self._color = QColor(hex_color)
        self.update()

    def set_pulsing(self, on: bool) -> None:
        on = on and ANIMATIONS
        if on == self._pulsing:
            return
        self._pulsing = on
        if on:
            self._anim.start()
        else:
            self._anim.stop()
            self._phase = 0.0
            self.update()

    def paintEvent(self, ev) -> None:      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        cx = self.width() / 2
        cy = self.height() / 2
        r = self._size / 2

        if self._pulsing:
            # هالهٔ بیرونی که با phase بزرگ و کم‌رنگ می‌شود
            halo_r = r + self._size * 1.1 * self._phase
            halo_alpha = int(90 * (1.0 - self._phase))
            c = QColor(self._color)
            c.setAlpha(max(0, halo_alpha))
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPoint(int(cx), int(cy)), int(halo_r), int(halo_r))

        p.setPen(Qt.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(QPoint(int(cx), int(cy)), int(r), int(r))
        p.end()


class Stagger:
    """ورود پلکانی چند ویجت (برای کارت‌های داشبورد)."""

    def __init__(self, step_ms: int = 45, dy: int = 12, ms: int = DUR_MED):
        self.step = step_ms
        self.dy = dy
        self.ms = ms
        self._i = 0

    def add(self, widget: QWidget) -> None:
        if not ANIMATIONS:
            self._i += 1
            return
        QTimer.singleShot(self._i * self.step,
                          lambda w=widget: rise(w, self.dy, self.ms))
        self._i += 1
