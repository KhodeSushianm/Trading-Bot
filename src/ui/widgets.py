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

⚠️ سایه‌ها عمداً با نقاشی لایه‌لایه ساخته می‌شوند، نه با QGraphicsDropShadowEffect:
   اثرهای گرافیکیِ باقی‌مانده قبلاً عامل باگ «صفحه سیاه تا درگ» بودند.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer,
                            Signal)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSizePolicy, QToolButton,
                               QVBoxLayout, QWidget)

from . import effects, icons
from .theme import DARK, Space, Theme, Type


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
                 shadow: bool = True, pad: int = Space.LG, bordered: bool = False):
        super().__init__(parent)
        self._t = t
        self._radius = radius
        self._ink = ink
        self._body = QColor(body) if body else QColor(t.ink_card if ink else t.card)
        self._shadow = shadow
        self._bordered = bordered
        self.setAutoFillBackground(False)
        halo = self.HALO if shadow else 0
        self._halo = halo
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(halo + pad, halo + pad, halo + pad, halo + pad)
        self._lay.setSpacing(Space.SM)

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
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        h = self._halo
        body = QRectF(self.rect()).adjusted(h, h, -h, -h)
        if self._shadow:
            # هاله: لایه‌های نیمه‌شفافِ هرچه نزدیک‌تر به بدنه، تیره‌تر
            for i in range(h, 0, -2):
                a = int(16 * (1 - i / h))
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(24, 24, 32, a))
                p.drawRoundedRect(body.adjusted(-i, -i * 0.55, i, i * 0.9),
                                  self._radius + i, self._radius + i)
        p.setPen(Qt.NoPen)
        p.setBrush(self._body)
        p.drawRoundedRect(body, self._radius, self._radius)
        if self._bordered:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(self._t.border), 1))
            p.drawRoundedRect(body, self._radius, self._radius)
        p.end()


class Card(SoftCard):
    """کارت سفید با سربرگ اختیاری (آیکون + عنوان + زیرعنوان)."""

    def __init__(self, title: str = "", sub: str = "", icon_name: str = "",
                 parent=None, t: Theme = DARK, bordered: bool = True):
        super().__init__(parent, t=t, bordered=bordered)
        self._t = t
        if title:
            head = QHBoxLayout()
            head.setSpacing(Space.SM)
            if icon_name:
                ic = QLabel()
                ic.setFixedSize(18, 18)
                ic.setPixmap(icons.icon(icon_name, 18, t.text_2).pixmap(18, 18))
                head.addWidget(ic)
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
        super().__init__(parent, t=t, ink=True)
        self._t = t
        if title:
            ttl = QLabel(title)
            ttl.setObjectName("ink_title")
            self._lay.addWidget(ttl)
        if sub:
            sb = QLabel(sub)
            sb.setObjectName("ink_sub")
            sb.setWordWrap(True)
            self._lay.addWidget(sb)


class StatTile(QFrame):
    """کاشی خاکستری داخل کارت مشکی (عدد + برچسب)."""

    def __init__(self, label: str, value: str = "—", icon_name: str = "",
                 tone: str = "", parent=None, t: Theme = DARK):
        super().__init__(parent)
        self.setObjectName("inktile")
        self._t = t
        lay = QVBoxLayout(self)
        lay.setContentsMargins(Space.MD, Space.MD, Space.MD, Space.MD)
        lay.setSpacing(2)
        self._num = QLabel(value)
        self._num.setObjectName("tile_num")
        self._num.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        cap = QLabel(label)
        cap.setObjectName("tile_cap")
        cap.setWordWrap(True)
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

    def __init__(self, parent=None, t: Theme = DARK):
        super().__init__(parent)
        self.setObjectName("statuspill")
        self._t = t
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
        self.setMinimumSize(120, 120)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

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

        # متن مرکز
        p.setPen(QColor(t.text))
        f = QFont()
        f.setPixelSize(int(side * 0.20))
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(rect).adjusted(0, side * 0.30, 0, -side * 0.34).toRect(),
                   Qt.AlignCenter, f"{int(round(self._value * 100))}٪")
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
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

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

        # برچسب محور
        p.setPen(QColor(t.text_3))
        f2 = QFont()
        f2.setPixelSize(Type.CAPTION)
        p.setFont(f2)
        for i, lb in enumerate(self._labels[:n]):
            x = pad_l + w * (i / (n - 1))
            p.drawText(QRectF(x - 20, pad_t + h + 4, 40, 16).toRect(), Qt.AlignCenter, lb)
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
        p.drawText(self.rect(), Qt.AlignCenter, "+  " + self._label)
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
