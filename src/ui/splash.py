# -*- coding: utf-8 -*-
"""صفحهٔ خوش‌آمدگویی (Splash) — «خوش اومدی سوشیان».

طراحی: تمام‌صفحهٔ شفاف با یک کارت سیاه در مرکز؛
  لوگو → نام کاربر (بزرگ) → زیرعنوان → خط پیشرفت نازک
سپس کل پنجره محو می‌شود و پنجرهٔ اصلی با fade وارد می‌شود.

نکته‌ها:
  • Frameless + Translucent تا لبه‌ها کاملاً خودمان باشند
  • AlwaysOnTop تا روی پنجره‌های دیگر نیفتد
  • نام کاربر از config می‌آید (`ui.user_name`) — هاردکد نیست
  • اگر به هر دلیلی Splash شکست خورد، برنامه باید بدون آن بالا بیاید
"""
from __future__ import annotations

from PySide6.QtCore import (Property, QEasingCurve, QPropertyAnimation, Qt,
                            QTimer, QRect)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QLabel,
                               QVBoxLayout, QWidget)

from . import effects, icons
from .theme import DARK, Space, Theme


class _ProgressLine(QWidget):
    """خط پیشرفت نازک (۲px) که از راست به چپ پر می‌شود (RTL)."""

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._value = 0.0
        self.setFixedHeight(3)

    # باید Property خودِ Qt باشد تا QPropertyAnimation بتواند انیمیتش کند؛
    # property معمولی پایتون از دید متاصدلبخشی نامرئی است و خط ساکن می‌ماند.
    def _get(self) -> float:
        return self._value

    def _set(self, v: float) -> None:
        self._value = max(0.0, min(1.0, v))
        self.update()

    value = Property(float, _get, _set)

    def paintEvent(self, ev) -> None:      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # ریل پس‌زمینه
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 26))
        p.drawRoundedRect(self.rect(), 2, 2)
        # بخش پرشده — از راست (RTL)
        w = int(self.width() * self._value)
        if w > 0:
            p.setBrush(self._color)
            p.drawRoundedRect(QRect(self.width() - w, 0, w, self.height()), 2, 2)
        p.end()


class WelcomeSplash(QWidget):
    """پنجرهٔ خوش‌آمد. `finished` وقتی صدا زده می‌شود که محو شدن تمام شد."""

    def __init__(self, user_name: str = "", version: str = "",
                 app_name: str = "", tagline: str = "",
                 t: Theme = DARK, hold_ms: int = 1500):
        super().__init__(None)
        self.setObjectName("splash")
        self._t = t
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)

        # کارت مرکزی — مشکیِ برند روی شیشه (مستقل از توکن‌های تم)
        card = QFrame(self)
        card.setObjectName("splash_card")
        card.setFixedSize(440, 260)
        # انتخابگر محدوده‌دار (scoped): شکل سادهٔ «QFrame {...» به QLabelهای
        # فرزند هم می‌افتاد (QLabel زیرکلاس QFrame است) و دور هر برچسب حاشیه می‌کشید!
        card.setStyleSheet(
            "QFrame#splash_card { background:#101013; border-radius:28px; "
            "border:1px solid rgba(255,255,255,0.10); }")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(Space.XL, Space.XL, Space.XL, Space.XL)
        lay.setSpacing(Space.MD)
        lay.setAlignment(Qt.AlignCenter)

        logo = QLabel()
        logo.setFixedSize(44, 44)
        logo.setPixmap(icons.icon("logo", 44, t.accent_ink, 1.5).pixmap(44, 44))
        logo.setAlignment(Qt.AlignCenter)

        name = QLabel(f"خوش اومدی {user_name}" if user_name else "خوش اومدی")
        name.setObjectName("splash_name")
        name.setAlignment(Qt.AlignCenter)

        sub = QLabel(tagline or "دستیار تحلیل و سیگنال فارکس")
        sub.setObjectName("splash_sub")
        sub.setAlignment(Qt.AlignCenter)

        self._bar = _ProgressLine(t.accent_ink)
        self._bar.setFixedWidth(180)

        if app_name and version:
            ver_txt = f"{app_name}  ·  v{version}"
        elif version:
            ver_txt = f"v{version}"
        else:
            ver_txt = app_name
        ver = QLabel(ver_txt)
        ver.setObjectName("splash_ver")
        ver.setAlignment(Qt.AlignCenter)

        lay.addWidget(logo, 0, Qt.AlignCenter)
        lay.addSpacing(Space.SM)
        lay.addWidget(name)
        lay.addWidget(sub)
        lay.addSpacing(Space.SM)
        lay.addWidget(self._bar, 0, Qt.AlignCenter)
        lay.addWidget(ver)

        self._card = card
        self._parts = [logo, name, sub, self._bar, ver]

        self._hold = hold_ms
        self.finished = False

    # ── چیدمان و اجرا ────────────────────────────────────────
    def _center(self) -> None:
        from PySide6.QtGui import QGuiApplication
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.setFixedSize(geo.size())
        self.move(geo.topLeft())
        self._card.move(geo.width() // 2 - self._card.width() // 2,
                        geo.height() // 2 - self._card.height() // 2)

    def show_and_run(self, on_done) -> None:
        """نمایش + انیمیشن ورود پلکانی + پرشدن خط + محو شدن + on_done."""
        self._center()
        self.show()
        self.raise_()

        # ورود پلکانی اجزا
        st = effects.Stagger(step_ms=70, dy=14, ms=effects.DUR_SLOW)
        for w in self._parts:
            st.add(w)

        # پر شدن خط پیشرفت
        anim = QPropertyAnimation(self._bar, b"value", self._bar)
        anim.setDuration(self._hold)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        effects._keep(self._bar, anim)     # noqa: SLF001
        anim.start()

        # بعد از hold، محو شو
        QTimer.singleShot(self._hold + 120, lambda: self._fade_out(on_done))

    def _fade_out(self, on_done) -> None:
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(effects.DUR_SLOW)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)

        def _done():
            self.finished = True
            self.hide()
            self.setGraphicsEffect(None)
            on_done()

        anim.finished.connect(_done)
        effects._keep(self, anim)     # noqa: SLF001
        anim.start()

    def resizeEvent(self, ev) -> None:      # noqa: N802
        super().resizeEvent(ev)
        self._card.move(self.width() // 2 - self._card.width() // 2,
                        self.height() // 2 - self._card.height() // 2)
