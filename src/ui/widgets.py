# -*- coding: utf-8 -*-
"""ویجت‌های مشترک تم روشن شیشه‌ای.

  SoftCard    کارت با سایهٔ نرمِ نقاشی‌شده (بدون QGraphicsDropShadowEffect)
  Card        کارت سفید با سربرگ اختیاری
  InkCard     کارت مشکی پرکنتراست (لهجهٔ بصری تم)
  StatTile    کاشی خاکستری داخل کارت مشکی (مثل 28/14/11 رفرنس)
  StatusPill  قرص وضعیت با نقطهٔ تپنده
  NavRail     سایدبار شناور سفید با آیتم فعال = پیِل مشکی
  RingGauge   حلقهٔ پیشرفت چندلایه
  LineChart   نمودار خطی نرم با حبابِ نقطهٔ اوج
  DashedCard  جای‌نگهدار خط‌چین (مثل + Add task)
  Toast       اعلان تیره به سبک منوی kontekstی رفرنس
  ToggleSwitch  سوئیچ روشن/خاموش مونوکروم (آینهٔ سوئیچ‌های نسخهٔ اندروید)
  Stepper       قدم‌شمار عددی −/+ با ارقام فارسی (آینهٔ نسخهٔ اندروید)

⚠️ سایه‌ها عمداً با نقاشی لایه‌لایه ساخته می‌شوند، نه با QGraphicsDropShadowEffect:
   اثرهای گرافیکیِ باقی‌مانده قبلاً عامل باگ «صفحه سیاه تا درگ» بودند.
"""
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import (QEasingCurve, QPoint, QPointF, QRect, QRectF, QSize,
                            Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QToolButton,
                               QVBoxLayout, QWidget)

from . import effects, icons
from .theme import DARK, Space, Theme, Type
from ..fa import fa_num


# ══════════════════════════════════════════════════════════════
#  کارت با سایهٔ نرم
# ══════════════════════════════════════════════════════════════
class SoftCard(QWidget):
    """کارت گرد با بدنهٔ تک‌رنگ و هالهٔ سایهٔ نرم.

    `body` رنگ بدنه؛ `ink=True` بدنهٔ مشکی پرکنتراست می‌سازد.
    محتوا از طریق layout داخلی اضافه می‌شود و به‌اندازهٔ هاله از لبه فاصله دارد.
    """

    HALO = 12

    def __init__(self, parent=None, t: Theme = DARK, radius: int = 22,
                 body: Optional[str] = None, ink: bool = False,
                 shadow: bool = True, pad: int = Space.LG, bordered: bool = False,
                 grad: Optional[tuple] = None, interactive: bool = False):
        super().__init__(parent)
        self._t = t
        self._radius = radius
        self._ink = ink
        self._body = QColor(body) if body else QColor(t.ink_card if ink else t.card)
        self._grad = grad            # (رنگ بالا, رنگ پایین) یا None
        self._shadow = shadow
        self._bordered = bordered
        self._interactive = interactive
        self._lift = 0.0
        self._lift_anim = None
        if interactive:
            self.setCursor(Qt.PointingHandCursor)
        self.setAutoFillBackground(False)
        halo = self.HALO if shadow else 0
        self._halo = halo
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(halo + pad, halo + pad, halo + pad, halo + pad)
        self._lay.setSpacing(Space.SM)

    # ── هاور: بلند شدن نرم کارت (v0.20.0) ──────────────────────
    def _animate_lift(self, target: float) -> None:
        if not effects.ANIMATIONS:
            self._lift = target
            self.update()
            return
        if self._lift_anim is None:
            self._lift_anim = QVariantAnimation(self)
            self._lift_anim.setDuration(160)
            self._lift_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._lift_anim.valueChanged.connect(self._on_lift)
        self._lift_anim.stop()
        self._lift_anim.setStartValue(self._lift)
        self._lift_anim.setEndValue(target)
        self._lift_anim.start()

    def _on_lift(self, v) -> None:
        self._lift = float(v)
        self.update()

    def enterEvent(self, ev) -> None:      # noqa: N802
        if self._interactive:
            self._animate_lift(1.0)
        super().enterEvent(ev)

    def leaveEvent(self, ev) -> None:      # noqa: N802
        if self._interactive:
            self._animate_lift(0.0)
        super().leaveEvent(ev)

    # ── API محتوا ────────────────────────────────────────────
    def add_widget(self, w: QWidget, stretch: int = 0) -> None:
        self._lay.addWidget(w, stretch)

    def add_layout(self, lay, stretch: int = 0) -> None:
        self._lay.addLayout(lay, stretch)

    def add_stretch(self, s: int = 1) -> None:
        self._lay.addStretch(s)

    def layout_(self):
        return self._lay

    # ── نقاشی ────────────────────────────────────────────────
    def paintEvent(self, ev) -> None:      # noqa: N802
        from PySide6.QtGui import QLinearGradient
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        h = self._halo
        body = QRectF(self.rect()).adjusted(h, h + 2.0 * self._lift,
                                            -h, -h + 2.0 * self._lift)
        if self._shadow:
            # هاله: لایه‌های نیمه‌شفافِ هرچه نزدیک‌تر به بدنه، تیره‌تر
            boost = 1.0 + 0.9 * self._lift
            for i in range(h, 0, -2):
                a = int(min(40, 16 * boost) * (1 - i / h))
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(24, 24, 32, a))
                p.drawRoundedRect(body.adjusted(-i, -i * 0.55, i, i * 0.9),
                                  self._radius + i, self._radius + i)
        p.setPen(Qt.NoPen)
        if self._grad:
            g = QLinearGradient(0, body.top(), 0, body.bottom())
            g.setColorAt(0.0, QColor(self._grad[0]))
            g.setColorAt(1.0, QColor(self._grad[1]))
            p.setBrush(g)
        else:
            p.setBrush(self._body)
        p.drawRoundedRect(body, self._radius, self._radius)
        if self._bordered:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(self._t.border), 1))
            p.drawRoundedRect(body, self._radius, self._radius)
        if not self._ink:
            # درخششِ هلالی بالای لبه — حس شیشهٔ سفید (v0.20.0)
            hl = QRectF(body)
            hl.setHeight(min(30.0, hl.height() * 0.25))
            g2 = QLinearGradient(0, hl.top(), 0, hl.bottom())
            g2.setColorAt(0.0, QColor(255, 255, 255, 235))
            g2.setColorAt(1.0, QColor(255, 255, 255, 0))
            path = QPainterPath()
            path.addRoundedRect(body, self._radius, self._radius)
            p.save()
            p.setClipPath(path)
            p.setPen(Qt.NoPen)
            p.setBrush(g2)
            p.drawRoundedRect(hl, self._radius, self._radius)
            p.restore()
        p.end()


class Card(SoftCard):
    """کارت سفید با سربرگ اختیاری (آیکون + عنوان + زیرعنوان)."""

    def __init__(self, title: str = "", sub: str = "", icon_name: str = "",
                 parent=None, t: Theme = DARK, bordered: bool = True):
        super().__init__(parent, t=t, bordered=bordered)
        self._t = t
        if title:
            head = QHBoxLayout()
            head.setSpacing(Space.SM + 2)
            if icon_name:
                head.addWidget(IconChip(icon_name, 28, tint=t.raised,
                                        color=t.text))
            ttl = QLabel(title)
            ttl.setObjectName("cardtitle")
            head.addWidget(ttl)
            head.addStretch(1)
            self._head_extra = QHBoxLayout()
            self._head_extra.setSpacing(Space.XS)
            head.addLayout(self._head_extra)
            self._lay.addLayout(head)
            if sub:
                sb = QLabel(sub)
                sb.setObjectName("cardsub")
                sb.setWordWrap(True)
                self._lay.addWidget(sb)
            self._lay.addSpacing(Space.XS)

    def header_extra(self):
        return getattr(self, "_head_extra", None)


class InkCard(SoftCard):
    """کارت مشکی پرکنتراست — لهجهٔ بصری تم روشن."""

    def __init__(self, title: str = "", sub: str = "", parent=None, t: Theme = DARK):
        super().__init__(parent, t=t, ink=True, grad=("#1C1C25", "#0A0A0E"))
        self._t = t
        if title:
            ttl = QLabel(title)
            ttl.setObjectName("ink_title")
            # رنگ در کد: روی برخی پلتفرم‌ها QSS برای برچسب‌های داخل کارت
            # مشکی قابل اتکا نیست (متن سیاه روی سیاه = نامرئی)
            ttl.setStyleSheet(f"color: {t.on_ink};")
            self._lay.addWidget(ttl)
        if sub:
            sb = QLabel(sub)
            sb.setObjectName("ink_sub")
            sb.setWordWrap(True)
            sb.setStyleSheet(f"color: {t.rgba('#FFFFFF', 0.55)};")
            self._lay.addWidget(sb)


class StatTile(QFrame):
    """کاشی خاکستری داخل کارت مشکی (عدد + برچسب)."""

    def __init__(self, label: str, value: str = "—", icon_name: str = "",
                 tone: str = "", parent=None, t: Theme = DARK):
        super().__init__(parent)
        self.setObjectName("inktile")
        self._t = t
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(2)
        self._num = QLabel(value)
        self._num.setObjectName("tile_num")
        self._num.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._num.setStyleSheet(f"color: {t.on_ink};")
        cap = QLabel(label)
        cap.setObjectName("tile_cap")
        cap.setWordWrap(True)
        cap.setStyleSheet(f"color: {t.rgba('#FFFFFF', 0.5)};")
        lay.addWidget(self._num)
        lay.addWidget(cap)
        self._tone = tone

    def set_value(self, v: str, tone: str = "") -> None:
        if self._num.text() == v and self._tone == tone:
            return
        self._num.setText(v)
        self._tone = tone
        # در کاشی مشکی، لهجهٔ رنگی با سفید/سبز/قرمز روشن بیان می‌شود
        col = {"green": self._t.green_text, "red": self._t.red_text}.get(tone, "#FFFFFF")
        self._num.setStyleSheet(f"color: {col if tone else self._t.on_ink};")


# ══════════════════════════════════════════════════════════════
#  وضعیت
# ══════════════════════════════════════════════════════════════
class StatusPill(QFrame):
    COLORS = {"idle": None, "ok": "#1F9D66", "busy": "#FFFFFF", "err": "#D64545"}
    TEXT = {"idle": "متوقف", "ok": "در حال اجرا", "busy": "در حال تحلیل…", "err": "خطا"}
    # رنگ متن برچسب — QSS رنگ را به فرزند القا نمی‌کند، پس در کد ست می‌شود
    TXT_ONINK = {"ok": "#7BE0B0", "err": "#FF9A9A"}

    def __init__(self, parent=None, t: Theme = DARK, onink: bool = False):
        super().__init__(parent)
        self.setObjectName("statuspill")
        self._t = t
        self._onink = onink
        if onink:
            self.setProperty("onink", "true")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 7, 16, 7)
        lay.setSpacing(Space.SM)
        self._dot = effects.PulseDot("#94949C", 8)
        self._dot.setFixedSize(20, 20)
        lay.addWidget(self._dot)
        self._txt = QLabel(self.TEXT["idle"])
        self._txt.setObjectName("statuspill_txt")
        f = QFont()
        f.setBold(True)
        self._txt.setFont(f)
        lay.addWidget(self._txt)
        self._state = ""
        self.set_state("idle")

    def _text_color(self, state: str) -> str:
        t = self._t
        if self._onink:
            if state == "ok":
                return self.TXT_ONINK["ok"]
            if state == "err":
                return self.TXT_ONINK["err"]
            if state == "busy":
                return t.on_ink
            return t.rgba("#FFFFFF", 0.72)
        if state == "ok":
            return t.green_text
        if state == "err":
            return t.red_text
        if state == "busy":
            return t.text
        return t.text_2

    def set_state(self, state: str, custom_text: str = "") -> None:
        text = custom_text or self.TEXT.get(state, state)
        if state == self._state and text == self._txt.text():
            return
        self._state = state
        self.setProperty("state", state)
        st = self.style()
        st.unpolish(self)
        st.polish(self)
        color = self.COLORS.get(state, "#94949C") or self._t.text_3
        self._dot.set_color(color)
        self._dot.set_pulsing(state in ("ok", "busy"))
        self._txt.setText(text)
        self._txt.setStyleSheet(f"color: {self._text_color(state)};")


# ══════════════════════════════════════════════════════════════
#  سایدبار شناور
# ══════════════════════════════════════════════════════════════
class NavRail(SoftCard):
    """سایدبار کارت شناور سفید؛ آیتم فعال = پیِل مشکی (مثل رفرنس)."""

    activated = Signal(int)

    def __init__(self, parent=None, t: Theme = DARK):
        super().__init__(parent, t=t, radius=26, pad=Space.MD, shadow=True)
        self._t = t
        self._items: list[QToolButton] = []
        self._keys: list[str] = []
        self._index = 0
        self._lay.setSpacing(2)

    def add_section(self, label: str) -> None:
        lb = QLabel(label)
        lb.setObjectName("navsection")
        wrap = QHBoxLayout()
        wrap.setContentsMargins(Space.MD, Space.MD, 0, Space.XS)
        wrap.addWidget(lb)
        wrap.addStretch(1)
        self._lay.addLayout(wrap)

    def add_item(self, key: str, label: str, icon_name: str) -> int:
        btn = QToolButton()
        btn.setObjectName("navitem")
        btn.setText(label)
        btn.setIcon(icons.icon(icon_name, 18, self._t.text_2))
        btn.setIconSize(QSize(18, 18))
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setMinimumHeight(40)
        btn._icon_name = icon_name                 # noqa: SLF001
        idx = len(self._items)
        btn.clicked.connect(lambda _=False, i=idx: self._select(i))
        self._items.append(btn)
        self._keys.append(key)
        row = QHBoxLayout()
        row.setContentsMargins(Space.XS, 0, Space.XS, 0)
        row.addWidget(btn)
        self._lay.addLayout(row)
        return idx

    def finish(self) -> None:
        self._lay.addStretch(1)

    def _select(self, i: int, animate: bool = True) -> None:
        for j, b in enumerate(self._items):
            active = (j == i)
            b.setProperty("active", "true" if active else "false")
            st = b.style()
            st.unpolish(b)
            st.polish(b)
            col = self._t.on_ink if active else self._t.text_2
            b.setIcon(icons.icon(getattr(b, "_icon_name", ""), 18, col))
        self._index = i
        self.activated.emit(i)

    def set_current(self, i: int) -> None:
        self._select(i)

    def key_at(self, i: int) -> str:
        return self._keys[i] if i < len(self._keys) else ""


# ══════════════════════════════════════════════════════════════
#  حلقهٔ پیشرفت
# ══════════════════════════════════════════════════════════════
class RingGauge(QWidget):
    """حلقهٔ پیشرفت چندلایه با متن مرکز (مثل Month progress رفرنس)."""

    def __init__(self, parent=None, t: Theme = DARK, value: float = 0.0,
                 caption: str = ""):
        super().__init__(parent)
        self._t = t
        self._value = max(0.0, min(1.0, value))
        self._caption = caption
        # اندازهٔ منعطف: در پنجره‌های کوچک جمع می‌شود تا از کارت بیرون نزند
        self.setMinimumSize(84, 84)
        self.setMaximumSize(220, 220)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

    def sizeHint(self) -> QSize:     # noqa: N802
        return QSize(132, 132)

    def set_value(self, v: float, caption: str = "") -> None:
        v = max(0.0, min(1.0, v))
        if abs(v - self._value) < 1e-6 and caption == self._caption:
            return
        self._value = v
        self._caption = caption
        self.update()

    def paintEvent(self, ev) -> None:      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        t = self._t
        side = min(self.width(), self.height())
        rect = QRect(0, 0, side, side)
        rect.moveCenter(self.rect().center())

        rings = [(0.0, t.border_strong, 5), (0.14, t.border, 5), (0.28, t.divider, 5)]
        for inset_frac, col, thick in rings:
            inset = int(side * inset_frac)
            r = QRectF(rect).adjusted(inset, inset, -inset, -inset)
            p.setPen(QPen(QColor(col), thick, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawArc(r, 0, 360 * 16)
        # کمان مقدار (لایهٔ بیرونی، مشکی)
        inset = 0
        r = QRectF(rect).adjusted(inset, inset, -inset, -inset)
        p.setPen(QPen(QColor(t.ink_card), 6, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(r, 90 * 16, -int(self._value * 360 * 16))

        # متن مرکز (ارقام فارسی طبق قانون ارقام)
        p.setPen(QColor(t.text))
        f = QFont()
        f.setPixelSize(int(side * 0.20))
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(rect).adjusted(0, side * 0.30, 0, -side * 0.34).toRect(),
                   Qt.AlignCenter, f"{fa_num(int(round(self._value * 100)))}٪")
        if self._caption:
            p.setPen(QColor(t.text_3))
            f2 = QFont()
            f2.setPixelSize(Type.CAPTION)
            p.setFont(f2)
            p.drawText(QRectF(rect).adjusted(0, side * 0.52, 0, 0).toRect(),
                       Qt.AlignHCenter | Qt.AlignTop, self._caption)
        p.end()


# ══════════════════════════════════════════════════════════════
#  نمودار خطی نرم
# ══════════════════════════════════════════════════════════════
class LineChart(QWidget):
    """خط نرم تک‌رنگ + سطح زیرین + حباب نقطهٔ اوج + برچسب محور."""

    def __init__(self, parent=None, t: Theme = DARK):
        super().__init__(parent)
        self._t = t
        self._vals: list[float] = []
        self._labels: list[str] = []
        # حداقل ارتفاع کوچک: در پنجره‌های کوتاه، کارت را مجبور به سرریز نکند
        self.setMinimumHeight(92)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self, vals: list[float], labels: list[str]) -> None:
        if vals == self._vals and labels == self._labels:
            return
        self._vals = list(vals)
        self._labels = list(labels)
        self.update()

    def paintEvent(self, ev) -> None:      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        t = self._t
        if len(self._vals) < 2:
            p.setPen(QColor(t.text_3))
            p.drawText(self.rect(), Qt.AlignCenter, "داده‌ای برای نمودار نیست")
            p.end()
            return

        pad_l, pad_r, pad_t, pad_b = 8, 8, 26, 22
        w = self.width() - pad_l - pad_r
        h = self.height() - pad_t - pad_b
        vmin, vmax = min(self._vals), max(self._vals)
        span = (vmax - vmin) or 1.0

        pts = []
        n = len(self._vals)
        for i, v in enumerate(self._vals):
            x = pad_l + w * (i / (n - 1))
            y = pad_t + h * (1 - (v - vmin) / span)
            pts.append(QPointF(x, y))

        # سطح زیر خط
        path = QPainterPath()
        path.moveTo(pts[0])
        for i in range(1, n):
            mid = QPointF((pts[i - 1].x() + pts[i].x()) / 2, (pts[i - 1].y() + pts[i].y()) / 2)
            path.quadTo(pts[i - 1], mid)
        path.lineTo(pts[-1])
        area = QPainterPath(path)
        area.lineTo(pts[-1].x(), pad_t + h)
        area.lineTo(pts[0].x(), pad_t + h)
        area.closeSubpath()
        fill = QColor(t.ink_card)
        fill.setAlpha(16)
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawPath(area)

        # خط
        p.setPen(QPen(QColor(t.ink_card), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        # نقطهٔ اوج + حباب
        imax = max(range(n), key=lambda i: self._vals[i])
        px, py = pts[imax].x(), pts[imax].y()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t.ink_card))
        p.drawEllipse(px, py - 3.2, 6.4, 6.4)
        bubble = "\u200E" + f"{self._vals[imax]:+.2f}%"
        f = QFont()
        f.setPixelSize(Type.CAPTION)
        f.setBold(True)
        p.setFont(f)
        tw = p.fontMetrics().horizontalAdvance(bubble) + 14
        bx = min(max(px - tw / 2, pad_l), self.width() - pad_r - tw)
        by = max(py - 26, 2)
        p.drawRoundedRect(QRectF(bx, by, tw, 18), 9, 9)
        p.setPen(QColor(t.on_ink))
        p.drawText(QRectF(bx, by, tw, 18).toRect(), Qt.AlignCenter, bubble)

        # برچسب محور — در عرض کم یکی‌درمیان تا هرگز همپوشانی نکنند
        p.setPen(QColor(t.text_3))
        f2 = QFont()
        f2.setPixelSize(Type.CAPTION)
        p.setFont(f2)
        slot = w / (n - 1) if n > 1 else float(w)
        k = max(1, math.ceil(40 / slot)) if slot > 0 else 1
        for i, lb in enumerate(self._labels[:n]):
            if i % k:
                continue
            x = pad_l + w * (i / (n - 1))
            bx = min(max(x - 20, 0), max(0, self.width() - 40))
            p.drawText(QRectF(bx, pad_t + h + 4, 40, 16).toRect(), Qt.AlignCenter, lb)
        p.end()


# ══════════════════════════════════════════════════════════════
#  کارت خط‌چین
# ══════════════════════════════════════════════════════════════
class DashedCard(QWidget):
    """جای‌نگهدار خط‌چین با برچسب مرکزی (مثل + Add task)."""

    def __init__(self, label: str, parent=None, t: Theme = DARK, radius: int = 20):
        super().__init__(parent)
        self._t = t
        self._label = label
        self._radius = radius
        self.setMinimumHeight(120)
        self.setAutoFillBackground(False)

    def paintEvent(self, ev) -> None:      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(QColor(self._t.border_strong), 1.6, Qt.DashLine, Qt.RoundCap))
        p.setBrush(QColor(255, 255, 255, 90))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1),
                          self._radius, self._radius)
        p.setPen(QColor(self._t.text_3))
        f = QFont()
        f.setPixelSize(Type.BODY)
        f.setBold(True)
        p.setFont(f)
        # علامت «+» با نشانهٔ RTL تا در چیدمان راست‌به‌چپ اولِ عبارت بماند
        p.drawText(self.rect(), Qt.AlignCenter, "\u200F+  " + self._label)
        p.end()


# ══════════════════════════════════════════════════════════════
#  Toast تیره
# ══════════════════════════════════════════════════════════════
class Toast(QFrame):
    def __init__(self, parent=None, t: Theme = DARK, ms: int = 4200):
        super().__init__(parent)
        self.setObjectName("toast")
        self._t = t
        self._ms = ms
        self.setFixedWidth(360)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(Space.MD, Space.MD, Space.MD, Space.MD)
        lay.setSpacing(Space.SM)
        self._icon = QLabel()
        self._icon.setFixedSize(18, 18)
        lay.addWidget(self._icon)
        col = QVBoxLayout()
        col.setSpacing(2)
        self._title = QLabel()
        self._title.setObjectName("toast_title")
        self._body = QLabel()
        self._body.setObjectName("toast_body")
        self._body.setWordWrap(True)
        col.addWidget(self._title)
        col.addWidget(self._body)
        lay.addLayout(col, 1)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)

    def show_message(self, title: str, body: str = "", icon_name: str = "info",
                     color: Optional[str] = None) -> None:
        self._title.setText(title)
        self._body.setText(body)
        self._body.setVisible(bool(body))
        c = color or self._t.on_ink
        self._icon.setPixmap(icons.icon(icon_name, 18, c).pixmap(18, 18))
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()
        effects.fade(self, 0.0, 1.0, effects.DUR_MED)
        if not effects.ANIMATIONS:
            self._timer.start(self._ms)
            return
        target = self.pos()
        self.move(target.x(), target.y() - 14)
        from PySide6.QtCore import QPropertyAnimation
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(effects.DUR_MED)
        anim.setStartValue(QPoint(target.x(), target.y() - 14))
        anim.setEndValue(target)
        anim.setEasingCurve(effects.EASE)
        effects._keep(self, anim)     # noqa: SLF001
        anim.start()
        self._timer.start(self._ms)

    def _place(self) -> None:
        p = self.parentWidget()
        if p is None:
            return
        self.move(p.width() // 2 - self.width() // 2, Space.LG)

    def dismiss(self) -> None:
        effects.fade(self, 1.0, 0.0, effects.DUR_FAST, on_finished=self.hide)


# ══════════════════════════════════════════════════════════════
#  کنترل‌های تنظیمات (آینهٔ نسخهٔ اندروید)
# ══════════════════════════════════════════════════════════════
def _mix(a: QColor, b: QColor, t: float) -> QColor:
    """مخلوط خطی دو رنگ (t=0 → a، t=1 → b) — برای انیمیشن سوئیچ."""
    t = max(0.0, min(1.0, t))
    return QColor(int(a.red() + (b.red() - a.red()) * t),
                  int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


class ToggleSwitch(QAbstractButton):
    """سوئیچ روشن/خاموش مونوکروم — آینهٔ دقیق سوئیچ CSS نسخهٔ اندروید.

    خاموش = ریل خاکستری با دستگیره در سمت راست؛ روشن = ریل مشکی با دستگیره‌ای
    که به سمت چپ سر می‌خورد (همان جهت فیزیکی در RTL). حرکت دستگیره انیمیشن
    کوتاه ۱۸۰ms است و با `ui.animations=false` آنی می‌شود.

    مثل QCheckBox با `setChecked`/`isChecked`/سیگنال `toggled` کار می‌کند، پس
    کد پنل هیچ تفاوتی با یک چک‌باکس معمولی نمی‌بیند.
    """

    W, H = 46, 27          # هم‌اندازهٔ .switch در style.css اندروید
    KNOB = 21
    PAD = 3

    def __init__(self, parent=None, t: Theme = DARK, checked: bool = False):
        super().__init__(parent)
        self._t = t
        self.setCheckable(True)
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0
        self.setChecked(checked)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(180)                       # مانند transition .18s
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self.toggled.connect(self._animate)

    # ── انیمیشن ──────────────────────────────────────────────
    def _on_anim(self, v) -> None:
        self._pos = float(v)
        self.update()

    def _animate(self, _checked: bool) -> None:
        target = 1.0 if self.isChecked() else 0.0
        self._anim.stop()
        if not effects.ANIMATIONS:
            self._pos = target
            self.update()
            return
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(target)
        self._anim.start()

    # ── نقاشی ────────────────────────────────────────────────
    def paintEvent(self, ev) -> None:      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        t = self._pos
        # ریل: خاکستری (خاموش) → مشکی جوهری (روشن)
        track = _mix(QColor(self._t.border_strong), QColor(self._t.ink_card), t)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(track, 1))
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        # دستگیره: دایرهٔ سفید با سایهٔ ظریف؛ از راست (خاموش) به چپ (روشن)
        d = float(self.KNOB)
        x0 = self.W - self.PAD - d                        # جای خاموش (سمت راست)
        x1 = float(self.PAD)                              # جای روشن (سمت چپ)
        x = x0 + (x1 - x0) * t
        y = (self.H - d) / 2.0
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 45))
        p.drawEllipse(QRectF(x, y + 1.0, d, d))
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(x, y, d, d))
        p.end()


class Stepper(QWidget):
    """قدم‌شمار عددی −/+ — آینهٔ `.stepper` نسخهٔ اندروید.

    مقدار همیشه در بازهٔ [lo, hi] clamp می‌شود و نمایش با ارقام فارسی است.
    هر تغییر واقعی، سیگنال `valueChanged(int)` را منتشر می‌کند. `unit`
    برچسب کوچک واحد (مثل «دقیقه») کنار دکمه‌ها اضافه می‌کند.
    """

    valueChanged = Signal(int)

    _BTN_QSS = ("QPushButton {{ background:{bg}; border:1px solid {bd};"
                " border-radius:{r}px; color:{fg}; font-size:17px;"
                " font-weight:700; padding:0; }}"
                " QPushButton:hover {{ color:{hov}; background:{hbg}; }}"
                " QPushButton:pressed {{ background:{pbg}; }}")

    def __init__(self, lo: int, hi: int, value: Optional[int] = None, step: int = 1,
                 unit: str = "", parent=None, t: Theme = DARK):
        super().__init__(parent)
        self._t = t
        self._lo, self._hi = int(lo), int(hi)
        self._step = max(1, int(step))
        self._value = self._lo if value is None else self._clamp(value)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self._minus = self._mk_btn("−")
        self._plus = self._mk_btn("+")
        self._label = QLabel(fa_num(self._value))
        self._label.setMinimumWidth(34)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet(
            f"color:{t.text}; font-size:15px; font-weight:700; background:transparent;")
        h.addWidget(self._minus)
        h.addWidget(self._label)
        h.addWidget(self._plus)
        if unit:
            u = QLabel(unit)
            u.setStyleSheet(f"color:{t.text_3}; font-size:{Type.CAPTION}px;"
                            " background:transparent;")
            h.addWidget(u)
        self._minus.clicked.connect(lambda: self.setValue(self._value - self._step))
        self._plus.clicked.connect(lambda: self.setValue(self._value + self._step))

    def _mk_btn(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setFixedSize(34, 34)
        b.setCursor(Qt.PointingHandCursor)
        t = self._t
        b.setStyleSheet(self._BTN_QSS.format(
            bg=t.card, bd=t.border_strong, r=17, fg=t.text_2,
            hov=t.text, hbg=t.card_hover, pbg=t.raised))
        return b

    def _clamp(self, v) -> int:
        return max(self._lo, min(self._hi, int(v)))

    # ── API ──────────────────────────────────────────────────
    def value(self) -> int:
        return self._value

    def setValue(self, v, silent: bool = False) -> None:
        v = self._clamp(v)
        changed = v != self._value
        self._value = v
        self._label.setText(fa_num(v))
        if changed and not silent:
            self.valueChanged.emit(v)
#  نمودار کندل‌استیک (v0.19.0) — QPainter، بدون کتابخانهٔ خارجی؛
#  همزاد بصری js/chart.js اندروید (همان حاشیه‌ها/رنگ‌ها/برچسب‌ها)
# ══════════════════════════════════════════════════════════════
class CandleChart(QWidget):
    """candles: [{'t':ms,'o','h','l','c'}] · levels: [(price, QColor, label, dashed)]"""

    PAD_L, PAD_R, PAD_T, PAD_B = 6, 78, 10, 26

    def __init__(self, parent=None, t: Theme = DARK):
        super().__init__(parent)
        self._t = t
        self._candles: list = []
        self._pip = 0.0001
        self._levels: list = []
        self.setMinimumHeight(240)

    def set_data(self, candles, pip: float = 0.0001, levels=None) -> None:
        self._candles = list(candles or [])
        self._pip = pip if pip and pip > 0 else 0.0001
        self._levels = list(levels or [])
        self.update()

    def _fmt(self, v: float) -> str:
        from src.report.signal import fmt_price
        return fmt_price(v, self._pip)

    def paintEvent(self, ev) -> None:          # noqa: N802
        from datetime import datetime, timezone
        from PySide6.QtCore import QPointF, QRectF, Qt
        from PySide6.QtGui import QColor, QFont, QPainter, QPen

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        w, h = self.width(), self.height()
        t = self._t
        cs = self._candles[-240:]
        if len(cs) < 2:
            p.setPen(QColor(t.text_3))
            p.setFont(QFont("Vazirmatn", 11))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "دادهٔ نمودار کافی نیست — اول یک چرخهٔ تحلیل اجرا کن")
            p.end()
            return

        lo = min(c["l"] for c in cs)
        hi = max(c["h"] for c in cs)
        for lv in self._levels:
            lo = min(lo, lv[0]); hi = max(hi, lv[0])
        rng = (hi - lo) or hi * 0.001 or 1
        lo -= rng * 0.04; hi += rng * 0.04; rng = hi - lo

        plot_w = w - self.PAD_L - self.PAD_R
        plot_h = h - self.PAD_T - self.PAD_B

        def y_of(price):
            return self.PAD_T + (hi - price) / rng * plot_h

        # شبکه + برچسب قیمت (راست)
        mono = QFont("Consolas", 8)
        for g in range(5):
            pv = hi - rng * g / 4
            gy = y_of(pv)
            p.setPen(QPen(QColor(t.divider), 1))
            p.drawLine(int(self.PAD_L), int(gy), int(w - self.PAD_R), int(gy))
            p.setPen(QColor(t.text_3))
            p.setFont(mono)
            p.drawText(QRectF(w - self.PAD_R + 6, gy - 8, self.PAD_R - 8, 16),
                       Qt.AlignLeft | Qt.AlignVCenter, self._fmt(pv))

        # سطوح (خط‌چین + برچسب)
        for price, color, label, dashed in self._levels:
            ly = y_of(price)
            if ly < self.PAD_T - 2 or ly > h - self.PAD_B + 2:
                continue
            pen = QPen(color, 1.4)
            if dashed:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.drawLine(self.PAD_L, int(ly), int(w - self.PAD_R), int(ly))
            if label:
                p.setPen(color)
                p.setFont(QFont("Vazirmatn", 8, QFont.Bold))
                p.drawText(QRectF(self.PAD_L + 4, ly - 17, plot_w - 8, 15),
                           Qt.AlignLeft | Qt.AlignVCenter, label)

        # کندل‌ها
        n = len(cs)
        step = plot_w / n
        bw = max(1.6, min(12.0, step * 0.62))
        up_c, dn_c = QColor(t.green), QColor(t.red)
        for i, c in enumerate(cs):
            x = self.PAD_L + i * step + step / 2
            col = up_c if c["c"] >= c["o"] else dn_c
            y_h, y_l = y_of(c["h"]), y_of(c["l"])
            y_o, y_c = y_of(c["o"]), y_of(c["c"])
            p.setPen(QPen(col, 1))
            p.drawLine(QPointF(x, y_h), QPointF(x, y_l))
            top, bh = min(y_o, y_c), max(1.0, abs(y_c - y_o))
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(x - bw / 2, top, bw, bh), 1, 1)

        # برچسب زمان (تهران) — ۴ نقطه
        from src.fa import hhmm, tehran
        p.setFont(mono)
        p.setPen(QColor(t.text_3))
        for ti in range(4):
            idx = min(n - 1, round((n - 1) * ti / 3))
            d = tehran(datetime.fromtimestamp(cs[idx]["t"] / 1000, tz=timezone.utc))
            lbl = f"{d.month:02d}/{d.day:02d} {hhmm(d)}"
            tx = self.PAD_L + idx * step + step / 2
            p.drawText(QRectF(tx - 44, h - 20, 88, 16), Qt.AlignCenter, lbl)

        # قرص قیمت آخرین کندل
        last = cs[-1]
        ly2 = max(self.PAD_T + 8, min(h - self.PAD_B - 8, y_of(last["c"])))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t.ink_card))
        p.drawRoundedRect(QRectF(w - self.PAD_R + 3, ly2 - 9, 70, 18), 9, 9)
        p.setPen(QColor(t.on_ink))
        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.drawText(QRectF(w - self.PAD_R + 3, ly2 - 9, 70, 18), Qt.AlignCenter, self._fmt(last["c"]))
        p.end()


# ══════════════════════════════════════════════════════════════
#  v0.20.0 — Aurora Glass 2.0: اجزای تازهٔ طراحی
# ══════════════════════════════════════════════════════════════
class IconChip(QFrame):
    """نشانِ آیکون: مربع گردِ رنگی با آیکون SVG در مرکز.

    پایهٔ زبان بصری جدید — هیچ آیکون برهنه‌ای در رابط نمی‌ماند.
    """

    def __init__(self, icon_name: str, size: int = 36, tint: str = "",
                 color: str = "", radius: int = -1, parent=None,
                 t: Theme = DARK):
        super().__init__(parent)
        self._t = t
        self._icon = icon_name
        self._tint = QColor(tint or t.ink_card)
        self._color = color or t.on_ink
        self._size = size
        self._radius = radius if radius >= 0 else max(8, int(size * 0.32))
        self.setFixedSize(size, size)

    def set_icon(self, name: str, color: str = "") -> None:
        self._icon = name
        if color:
            self._color = color
        self.update()

    def paintEvent(self, ev) -> None:      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(self._tint)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
                          self._radius, self._radius)
        inner = max(10, int(self._size * 0.56))
        if inner % 2:
            inner -= 1
        pm = icons.icon(self._icon, inner, self._color).pixmap(inner, inner)
        x = (self.width() - inner) // 2
        y = (self.height() - inner) // 2
        p.drawPixmap(x, y, pm)
        p.end()


class Chip(QLabel):
    """برچسب قرصی کوچک با تُن معنایی (neutral/ink/green/red/amber/brand)."""

    def __init__(self, text: str = "", tone: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("chip")
        self.setAlignment(Qt.AlignCenter)
        self._tone = tone
        if tone:
            self.setProperty("tone", tone)

    def set_tone(self, tone: str) -> None:
        self._tone = tone
        self.setProperty("tone", tone)
        st = self.style()
        st.unpolish(self)
        st.polish(self)


class Stars(QWidget):
    """رتبهٔ ستاره‌ای نقاشی‌شده (به‌جای گلیف متنی ★)."""

    def __init__(self, value: int = 0, total: int = 5, size: int = 14,
                 parent=None, t: Theme = DARK):
        super().__init__(parent)
        self._t = t
        self._value = max(0, min(total, int(value)))
        self._total = total
        self._size = size
        self.setFixedHeight(size + 4)
        self.setMinimumWidth(total * (size + 3))

    def set_value(self, v: int) -> None:
        v = max(0, min(self._total, int(v)))
        if v != self._value:
            self._value = v
            self.update()

    def paintEvent(self, ev) -> None:      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        s = self._size
        y = (self.height() - s) // 2
        # RTL: از راست بچین
        x = self.width() - s
        for i in range(self._total):
            filled = i < self._value
            pm = icons.icon("star_filled" if filled else "star", s,
                            self._t.amber if filled else self._t.border_strong,
                            1.5).pixmap(s, s)
            p.drawPixmap(x, y, pm)
            x -= s + 3
        p.end()


class SectionHeader(QWidget):
    """سربرگ صفحه/بخش: چیپ آیکون + عنوان بزرگ + زیرعنوان + دنبالهٔ اختیاری."""

    def __init__(self, icon_name: str, title: str, sub: str = "",
                 parent=None, t: Theme = DARK, trailing: QWidget = None):
        super().__init__(parent)
        self._t = t
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(Space.MD)
        self.chip = IconChip(icon_name, 42, tint=t.ink_card, color=t.on_ink)
        lay.addWidget(self.chip, 0, Qt.AlignVCenter)
        col = QVBoxLayout()
        col.setSpacing(1)
        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("pagetitle")
        self.sub_lbl = QLabel(sub)
        self.sub_lbl.setObjectName("pagesub")
        self.sub_lbl.setWordWrap(True)
        col.addWidget(self.title_lbl)
        col.addWidget(self.sub_lbl)
        lay.addLayout(col, 1)
        if trailing is not None:
            lay.addWidget(trailing, 0, Qt.AlignVCenter)


class SegmentedControl(QFrame):
    """کلید چندحالتهٔ قرصی (مثل H1/H4) — انتخاب = پیِل مشکی."""

    changed = Signal(object)

    def __init__(self, options: list, parent=None, t: Theme = DARK):
        """options: [(key, label), ...]"""
        super().__init__(parent)
        self.setObjectName("seg")
        self._t = t
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        self._btns = {}
        self._current = options[0][0] if options else None
        for key, label in options:
            b = QToolButton()
            b.setObjectName("segbtn")
            b.setText(label)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(key == self._current)
            b.clicked.connect(lambda _=False, k=key: self.set_current(k, emit=True))
            lay.addWidget(b)
            self._btns[key] = b

    def set_current(self, key, emit: bool = False) -> None:
        if key not in self._btns:
            return
        self._current = key
        for k, b in self._btns.items():
            b.setChecked(k == key)
        if emit:
            self.changed.emit(key)

    def current(self):
        return self._current


class ConsoleCard(SoftCard):
    """کارتِ کنسول: سربرگ (چیپ آیکون + عنوان + قرص زمان + کپی) روی بدنهٔ تیره.

    بدنه یک QTextEdit فقط‌خواندنی با استایل «ترمینال پریمیوم» است؛ متن خام
    همیشه *داخل کارت* و با رنگ‌بندی ساختاری نمایش داده می‌شود.
    `view` برای سازگاری با تست‌ها همان setPlainText/toPlainText را دارد.
    """

    def __init__(self, title: str = "", sub: str = "", icon_name: str = "report",
                 parent=None, t: Theme = DARK, placeholder: str = "",
                 with_copy: bool = True):
        super().__init__(parent, t=t, pad=Space.MD)
        self._t = t
        head = QHBoxLayout()
        head.setSpacing(Space.SM + 2)
        head.addWidget(IconChip(icon_name, 34, tint=t.ink_card, color=t.on_ink))
        col = QVBoxLayout()
        col.setSpacing(1)
        if title:
            ttl = QLabel(title)
            ttl.setObjectName("cardtitle")
            col.addWidget(ttl)
        self.sub_lbl = QLabel(sub or "")
        self.sub_lbl.setObjectName("cardsub")
        col.addWidget(self.sub_lbl)
        head.addLayout(col, 1)
        self.time_chip = Chip("", "")
        self.time_chip.setVisible(False)
        head.addWidget(self.time_chip)
        if with_copy:
            self.copy_btn = QPushButton()
            self.copy_btn.setObjectName("circle")
            self.copy_btn.setFixedSize(34, 34)
            self.copy_btn.setIcon(icons.icon("copy", 16, t.text_2))
            self.copy_btn.setCursor(Qt.PointingHandCursor)
            self.copy_btn.setToolTip("کپی متن کامل")
            self.copy_btn.clicked.connect(self._copy)
            head.addWidget(self.copy_btn)
        self.add_layout(head)

        from PySide6.QtWidgets import QTextEdit
        self.view = QTextEdit()
        self.view.setObjectName("console")
        self.view.setReadOnly(True)
        self.view.setPlaceholderText(placeholder)
        self.view.setMinimumHeight(120)
        self.add_widget(self.view, 1)

    def _copy(self) -> None:
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(self.view.toPlainText())
            if getattr(self, "copy_btn", None) is not None:
                self.copy_btn.setIcon(icons.icon("check", 16, self._t.green_text))
                QTimer.singleShot(1400, lambda: self.copy_btn.setIcon(
                    icons.icon("copy", 16, self._t.text_2)))
        except Exception:
            pass

    # ── محتوا ────────────────────────────────────────────────
    def set_stamp(self, stamp: str) -> None:
        if stamp:
            self.time_chip.setText(stamp)
            self.time_chip.setVisible(True)
        else:
            self.time_chip.setVisible(False)

    def set_text(self, text: str, stamp: str = "", colorize: bool = True) -> None:
        """متن کامل را می‌گذارد؛ با colorize سرتیترها/جداکننده‌ها رنگ می‌گیرند."""
        self.set_stamp(stamp)
        if colorize:
            self.view.setHtml(self.colorize(text))
        else:
            self.view.setPlainText(text)

    def colorize(self, text: str) -> str:
        """HTML ساده: جداکننده‌ها و سرتیترهای گزارش را برجسته می‌کند."""
        import html as _html
        t = self._t
        out = []
        for line in str(text).splitlines():
            esc = _html.escape(line)
            s = line.strip()
            if not s:
                out.append("&nbsp;")
            elif s.startswith("═") or set(s) <= {"━", "─", "═"} and len(s) > 3:
                out.append(f"<span style='color:{t.console_dim}'>{esc}</span>")
            elif s.startswith("───"):
                out.append(f"<span style='color:{t.brand};font-weight:700'>{esc}</span>")
            elif s[:1] in "🔎⚖️📊🕒📅💹🛑🎯⚠️📍🌊💰🧭📈📉✅❌🟢🔴🟡" or \
                    (len(s) > 1 and s[1] in "️⃣" ):
                out.append(f"<span style='color:{t.console_text};font-weight:600'>{esc}</span>")
            elif "سیگنال" in s and ("—" in s or "✅" in s):
                out.append(f"<span style='color:{t.console_green};font-weight:700'>{esc}</span>")
            elif s.startswith("❌") or "خطا" in s[:6]:
                out.append(f"<span style='color:{t.console_red};font-weight:600'>{esc}</span>")
            else:
                out.append(f"<span style='color:{t.console_text}'>{esc}</span>")
        return ("<div style='font-family:Vazirmatn,Consolas,monospace;"
                f"font-size:12.5px;line-height:1.7;direction:rtl'>"
                + "<br>".join(out) + "</div>")

    def append_line(self, html_line: str) -> None:
        self.view.append(html_line)


class KpiCard(SoftCard):
    """کارت شاخص: چیپ آیکون + عدد بزرگ + برچسب."""

    def __init__(self, label: str, value: str = "—", icon_name: str = "gauge",
                 tone: str = "", parent=None, t: Theme = DARK):
        super().__init__(parent, t=t, radius=18, pad=Space.MD, bordered=True)
        self._t = t
        row = QHBoxLayout()
        row.setSpacing(Space.SM)
        tint = {"green": t.green_tint, "red": t.red_tint,
                "amber": t.amber_tint, "brand": t.brand_tint}.get(tone, t.raised)
        colr = {"green": t.green_text, "red": t.red_text,
                "amber": "#9A7220", "brand": t.brand}.get(tone, t.text)
        self.chip = IconChip(icon_name, 30, tint=tint, color=colr)
        row.addWidget(self.chip, 0, Qt.AlignVCenter)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.value_lbl = QLabel(value)
        self.value_lbl.setObjectName("kpi_val")
        if tone in ("green", "red"):
            self.value_lbl.setProperty("tone", tone)
        self.label_lbl = QLabel(label)
        self.label_lbl.setObjectName("kpi_lab")
        col.addWidget(self.value_lbl)
        col.addWidget(self.label_lbl)
        row.addLayout(col, 1)
        self.add_layout(row)

    def set_value(self, value: str, tone: str = "") -> None:
        self.value_lbl.setText(value)
        if tone:
            self.value_lbl.setProperty("tone", tone)
            st = self.value_lbl.style()
            st.unpolish(self.value_lbl)
            st.polish(self.value_lbl)


_EN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _en_num(s: str) -> str:
    return str(s).translate(_EN_DIGITS)


class SignalCard(SoftCard):
    """کارت سیگنال ساختاریافته — همان زبان بصری کارت اندروید/اشتراک.

    از dict سیگنال موتور ساخته می‌شود (symbol, direction, score, entry, sl,
    tp, rr, stars, session_fa, fa_name, now, text, sent, pip, is_gold).
    دلایل از `text` سیگنال با پارسر محافظه‌کار بیرون کشیده می‌شوند؛ اگر
    پارس نشد، بخش دلایل پنهان می‌ماند و «متن کامل» همیشه در دسترس است.
    """

    def __init__(self, sig: dict, parent=None, t: Theme = DARK,
                 on_chart=None, on_share=None):
        super().__init__(parent, t=t, radius=20, pad=Space.LG, bordered=True,
                         interactive=True)
        self._t = t
        self.sig = dict(sig or {})
        buy = str(self.sig.get("direction", "")).upper().startswith("B")
        self._buy = buy
        acc = t.green_text if buy else t.red_text
        pip = float(self.sig.get("pip") or (1.0 if self.sig.get("is_gold") else 0.0001))

        from src.report.signal import fmt_price

        # ── ردیف ۱: جهت + ستاره‌ها + وضعیت ارسال ──────────────
        row1 = QHBoxLayout()
        row1.setSpacing(Space.SM)
        dir_chip = Chip(("سیگنال خرید" if buy else "سیگنال فروش"),
                        "green" if buy else "red")
        row1.addWidget(dir_chip)
        sent = bool(self.sig.get("sent", True))
        row1.addWidget(Chip("ارسال شد" if sent else "ارسال نشد",
                            "ink" if sent else "amber"))
        row1.addStretch(1)
        self.stars = Stars(int(self.sig.get("stars") or 0), 5, 15, t=t)
        row1.addWidget(self.stars, 0, Qt.AlignVCenter)
        self.add_layout(row1)

        # ── ردیف ۲: جفت‌ارز + نام فارسی ──────────────────────
        pair = str(self.sig.get("symbol", ""))
        if len(pair) == 6:
            pair = pair[:3] + "/" + pair[3:]
        row2 = QHBoxLayout()
        row2.setSpacing(Space.SM)
        pl = QLabel("\u200E" + pair)
        pl.setObjectName("sigpair")
        row2.addWidget(pl)
        fa_name = str(self.sig.get("fa_name") or "")
        if fa_name:
            fn = QLabel(fa_name)
            fn.setObjectName("sigmeta")
            row2.addWidget(fn, 0, Qt.AlignBottom)
        row2.addStretch(1)
        score = self.sig.get("score")
        max_score = self.sig.get("max_score")
        if score is not None:
            from ..fa import fa_num
            row2.addWidget(Chip(f"امتیاز {fa_num(score)} از {fa_num(max_score or 11)}",
                                "ink"))
        self.add_layout(row2)

        # ── ردیف ۳: زمان + سشن ───────────────────────────────
        row3 = QHBoxLayout()
        row3.setSpacing(Space.SM)
        try:
            nowv = self.sig.get("now")
            if isinstance(nowv, str):
                from datetime import datetime as _dt
                nowv = _dt.fromisoformat(nowv)
            if nowv is not None:
                from ..fa import fa_num, jalali_fa, hhmm_teh
                if nowv.tzinfo is None:
                    from datetime import timezone as _tz
                    nowv = nowv.replace(tzinfo=_tz.utc)
                row3.addWidget(Chip(jalali_fa(nowv) + " · ساعت " +
                                    fa_num(hhmm_teh(nowv)) + " تهران", ""))
        except Exception:
            pass
        if self.sig.get("session_fa"):
            row3.addWidget(Chip("سشن " + str(self.sig["session_fa"]), "brand"))
        rr = self.sig.get("rr")
        if rr:
            from ..fa import fa_num
            row3.addWidget(Chip("ریسک به ریوارد ۱:" + fa_num(f"{float(rr):.1f}"), "green"))
        row3.addStretch(1)
        self.add_layout(row3)

        # ── ردیف ۴: کاشی‌های ورود/حد ضرر/هدف ──────────────────
        tiles = QHBoxLayout()
        tiles.setSpacing(Space.SM)
        for cap_t, key, tone in (("ورود", "entry", ""), ("حد ضرر", "sl", "red"),
                                 ("هدف", "tp", "green")):
            tl = QFrame()
            tl.setObjectName("sigtile")
            vl = QVBoxLayout(tl)
            vl.setContentsMargins(Space.MD, 10, Space.MD, 10)
            vl.setSpacing(2)
            c = QLabel(cap_t)
            c.setObjectName("sigtile_cap")
            v = QLabel("")
            v.setObjectName("sigtile_val")
            v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if tone:
                v.setProperty("tone", tone)
            try:
                v.setText("\u200E" + fmt_price(float(self.sig[key]), pip))
            except Exception:
                v.setText("—")
            vl.addWidget(c)
            vl.addWidget(v)
            tiles.addWidget(tl, 1)
        self.add_layout(tiles)

        # ── ردیف ۵: دلایل (پارس‌شده از متن سیگنال) ────────────
        reasons, warns = self._parse_reasons(str(self.sig.get("text") or ""))
        if reasons:
            cap = QLabel("چرا این سیگنال صادر شد؟")
            cap.setObjectName("cardtitle")
            self.add_widget(cap)
            for iconn, label, pts, detail in reasons:
                r = QFrame()
                r.setObjectName("sigreason")
                rl = QHBoxLayout(r)
                rl.setContentsMargins(Space.MD, 8, Space.MD, 8)
                rl.setSpacing(Space.SM)
                rl.addWidget(IconChip(iconn, 24, tint=t.green_tint,
                                      color=t.green_text))
                txt = QLabel(f"{label} — {detail}" if detail else label)
                txt.setObjectName("sigreason_txt")
                txt.setWordWrap(True)
                rl.addWidget(txt, 1)
                if pts:
                    from ..fa import fa_num
                    rl.addWidget(Chip("+" + fa_num(pts), "green"))
                self.add_widget(r)
        if warns:
            for wmsg in warns[:3]:
                r = QFrame()
                r.setObjectName("sigreason")
                rl = QHBoxLayout(r)
                rl.setContentsMargins(Space.MD, 8, Space.MD, 8)
                rl.setSpacing(Space.SM)
                rl.addWidget(IconChip("alert", 24, tint=t.amber_tint, color="#9A7220"))
                txt = QLabel(wmsg)
                txt.setObjectName("sigreason_txt")
                txt.setWordWrap(True)
                rl.addWidget(txt, 1)
                self.add_widget(r)

        # ── ردیف ۶: اقدام‌ها ──────────────────────────────────
        acts = QHBoxLayout()
        acts.setSpacing(Space.SM)
        from PySide6.QtWidgets import QPushButton
        b_chart = QPushButton("نمودار")
        b_chart.setObjectName("ghost")
        b_chart.setIcon(icons.icon("chart", 15, t.text_2))
        b_chart.setCursor(Qt.PointingHandCursor)
        b_share = QPushButton("اشتراک تصویر")
        b_share.setObjectName("ghost")
        b_share.setIcon(icons.icon("send", 15, t.text_2))
        b_share.setCursor(Qt.PointingHandCursor)
        b_text = QPushButton("متن کامل")
        b_text.setObjectName("subtle")
        b_text.setCheckable(True)
        b_text.setIcon(icons.icon("eye", 15, t.text_3))
        b_text.setCursor(Qt.PointingHandCursor)
        acts.addWidget(b_chart)
        acts.addWidget(b_share)
        acts.addStretch(1)
        acts.addWidget(b_text)
        self.add_layout(acts)

        self._text_card = ConsoleCard("متن کامل سیگنال", "", "report", t=t,
                                      with_copy=True)
        self._text_card.set_text(str(self.sig.get("text") or "متنی نیست."))
        self._text_card.setVisible(False)
        self.add_widget(self._text_card)
        b_text.toggled.connect(self._text_card.setVisible)

        if on_chart is not None:
            b_chart.clicked.connect(lambda _=False, s=self.sig: on_chart(s))
        if on_share is not None:
            b_share.clicked.connect(lambda _=False, s=self.sig: on_share(s))

    # ── پارسر محافظه‌کارِ دلایل از متن رندرشده ────────────────
    _ICON_HINTS = (("روند", "trend_up"), ("H4", "trend_up"), ("H1", "trend_up"),
                   ("تقویم", "calendar"), ("رویداد", "calendar"), ("خبر", "report"),
                   ("اخبار", "report"), ("تریدینگ", "eye"), ("TradingView", "eye"),
                   ("نوسان", "zap"), ("ATR", "zap"), ("حمایت", "layers"),
                   ("مقاومت", "layers"), ("سشن", "clock"), ("زمان", "clock"),
                   ("فاصله", "gauge"), ("مومنتوم", "zap"), ("حجم", "chart"))

    def _parse_reasons(self, text: str):
        import re
        reasons, warns = [], []
        if not text:
            return reasons, warns
        try:
            negative = False
            for raw in text.splitlines():
                line = raw.strip()
                if "امتیاز نگرفتند" in line:
                    negative = True
                    continue
                if line.startswith("•"):
                    warns.append(line.lstrip("• ").strip())
                    continue
                m = re.match(r"^(?:[^\w\s]+\s*)?(.+?)\s*\(\+([۰-۹0-9]+)\)\s*(?:—|-)\s*(.*)$",
                             line)
                if not m or negative:
                    continue
                label, pts, detail = m.group(1).strip(), int(_en_num(m.group(2))), \
                    m.group(3).strip()
                iconn = "check"
                for hint, ic in self._ICON_HINTS:
                    if hint in label or hint in detail:
                        iconn = ic
                        break
                reasons.append((iconn, label, pts, detail))
        except Exception:
            return [], []
        return reasons[:8], warns
