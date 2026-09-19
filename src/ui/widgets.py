# -*- coding: utf-8 -*-
"""ویجت‌های قابل استفادهٔ مجدد — زبان بصری مشترک کل برنامه.

  Card          کارت با عنوان/زیرعنوان و خط جداکنندهٔ موئی
  SectionTitle  عنوان بخش کوچک
  StatTile      کارت عدد بزرگ (داشبورد)
  StatusPill    قرص وضعیت با نقطهٔ تپنده
  NavRail       ریل ناوبری عمودی با آیکون + نشانگر متحرک
  Toast         اعلان شناور که از بالا می‌آید و خودکار می‌رود
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (QPoint, QPropertyAnimation, QSize, Qt, QTimer,
                            Signal)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSizePolicy,
                               QToolButton, QVBoxLayout, QWidget)

from . import effects, icons
from .theme import DARK, Space, Theme


# ══════════════════════════════════════════════════════════════
#  کارت
# ══════════════════════════════════════════════════════════════
class Card(QFrame):
    """کارت استاندارد: عنوان اختیاری + خط موئی + محتوا."""

    def __init__(self, title: str = "", sub: str = "", icon_name: str = "",
                 parent=None, t: Theme = DARK):
        super().__init__(parent)
        self.setObjectName("card")
        self._t = t
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(Space.LG, Space.MD + 2, Space.LG, Space.LG)
        self._lay.setSpacing(Space.SM)
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
            line = QFrame()
            line.setObjectName("cardline")
            line.setFixedHeight(1)
            self._lay.addWidget(line)
            self._lay.addSpacing(Space.XS)

    def add_widget(self, w: QWidget, stretch: int = 0) -> None:
        self._lay.addWidget(w, stretch)

    def add_layout(self, lay) -> None:
        self._lay.addLayout(lay)

    def add_stretch(self, s: int = 1) -> None:
        self._lay.addStretch(s)

    def header_extra(self):
        return getattr(self, "_head_extra", None)


class StatTile(QFrame):
    """کارت عدد بزرگ برای داشبورد. tone: '' | 'green' | 'red'."""

    def __init__(self, label: str, value: str = "—", icon_name: str = "",
                 tone: str = "", parent=None, t: Theme = DARK):
        super().__init__(parent)
        self.setObjectName("stat")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(Space.MD, Space.MD, Space.MD, Space.MD)
        lay.setSpacing(Space.XS)

        top = QHBoxLayout()
        top.setSpacing(Space.SM)
        if icon_name:
            ic = QLabel()
            ic.setFixedSize(15, 15)
            color = {"green": t.green, "red": t.red}.get(tone, t.text_3)
            ic.setPixmap(icons.icon(icon_name, 15, color).pixmap(15, 15))
            top.addWidget(ic)
        lb = QLabel(label)
        lb.setObjectName("statlabel")
        top.addWidget(lb)
        top.addStretch(1)
        lay.addLayout(top)

        self._num = QLabel(value)
        self._num.setObjectName("statnum")
        self._num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if tone:
            self._num.setProperty("tone", tone)
        lay.addWidget(self._num)

    def set_value(self, v: str, tone: str = "") -> None:
        if self._num.text() == v and (self._num.property("tone") or "") == tone:
            return
        self._num.setText(v)
        if tone != self._num.property("tone"):
            self._num.setProperty("tone", tone)
            self._num.style().unpolish(self._num)
            self._num.style().polish(self._num)


# ══════════════════════════════════════════════════════════════
#  وضعیت
# ══════════════════════════════════════════════════════════════
class StatusPill(QFrame):
    """قرص وضعیت: نقطهٔ تپنده + متن. state: idle|ok|busy|err."""

    COLORS = {"idle": None, "ok": "#3ECF8E", "busy": "#FFFFFF", "err": "#FF5D5D"}
    TEXT = {"idle": "متوقف", "ok": "در حال اجرا", "busy": "در حال تحلیل…", "err": "خطا"}

    def __init__(self, parent=None, t: Theme = DARK):
        super().__init__(parent)
        self.setObjectName("statuspill")
        self._t = t
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 14, 6)
        lay.setSpacing(Space.SM)
        self._dot = effects.PulseDot("#9E9EA8", 8)
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
            return                            # تیک هر ثانیه نباید restyle بی‌مورد بزند
        self._state = state
        self.setProperty("state", state)
        st = self.style()
        st.unpolish(self)
        st.polish(self)
        color = self.COLORS.get(state, "#9E9EA8") or self._t.text_3
        self._dot.set_color(color)
        self._dot.set_pulsing(state in ("ok", "busy"))
        self._txt.setText(text)


# ══════════════════════════════════════════════════════════════
#  ریل ناوبری
# ══════════════════════════════════════════════════════════════
class NavRail(QFrame):
    """ریل ناوبری عمودی (در RTL سمت راست) با آیکون + برچسب + نشانگر متحرک."""

    activated = Signal(int)

    IND_W = 3          # ضخامت نشانگر سفید
    IND_H = 22         # ارتفاع نشانگر

    def __init__(self, parent=None, t: Theme = DARK):
        super().__init__(parent)
        self.setObjectName("navrail")
        self._t = t
        self._items: list[QToolButton] = []
        self._index = 0
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(Space.SM, Space.MD, Space.SM + 4, Space.MD)
        self._lay.setSpacing(Space.XS)

        # نشانگر سفید کنار آیتم فعال — پشت آیتم‌ها تا فقط لبه‌اش دیده شود
        self._indicator = QFrame(self)
        self._indicator.setObjectName("navindicator")
        self._indicator.setFixedWidth(self.IND_W)
        self._indicator.setFixedHeight(self.IND_H)
        self._keys: list[str] = []

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
        self._lay.addWidget(btn)
        return idx

    def finish(self) -> None:
        self._lay.addStretch(1)
        # نشانگر باید زیر آیتم‌ها باشد تا خط سفید کنارشان دیده شود
        self._indicator.lower()

    def _select(self, i: int, animate: bool = True) -> None:
        for j, b in enumerate(self._items):
            b.setProperty("active", "true" if j == i else "false")
            st = b.style()
            st.unpolish(b)
            st.polish(b)
            col = self._t.accent_ink if j == i else self._t.text_2
            b.setIcon(icons.icon(getattr(b, "_icon_name", ""), 18, col))
        self._index = i
        if animate:
            self._move_indicator()
        self.activated.emit(i)

    def _move_indicator(self) -> None:
        if not self._items:
            return
        btn = self._items[self._index]
        y = btn.mapTo(self, QPoint(0, 0)).y() + (btn.height() - self.IND_H) // 2
        effects.slide_indicator(self._indicator, y, self.IND_H)

    def set_current(self, i: int) -> None:
        self._select(i)

    def key_at(self, i: int) -> str:
        return self._keys[i] if i < len(self._keys) else ""

    def resizeEvent(self, ev) -> None:      # noqa: N802
        super().resizeEvent(ev)
        # نشانگر در لبهٔ بیرونی ریل (در RTL = سمت راستِ خودِ ریل)
        self._indicator.move(self.width() - self.IND_W - 2, self._indicator.y())
        if self._items:
            btn = self._items[self._index]
            y = btn.mapTo(self, QPoint(0, 0)).y() + (btn.height() - self.IND_H) // 2
            effects.slide_indicator(self._indicator, y, self.IND_H, instant=True)


# ══════════════════════════════════════════════════════════════
#  Toast
# ══════════════════════════════════════════════════════════════
class Toast(QFrame):
    """اعلان شناور بالای محتوا؛ خودکار بعد از چند ثانیه جمع می‌شود."""

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
        c = color or self._t.text_2
        self._icon.setPixmap(icons.icon(icon_name, 18, c).pixmap(18, 18))
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()
        effects.fade(self, 0.0, 1.0, effects.DUR_MED)
        # اسلاید از بالا
        target = self.pos()
        self.move(target.x(), target.y() - 14)
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
        # fade خودش اثر را پس از پایان حذف می‌کند (و برای end=0 اول hide می‌کند)
        effects.fade(self, 1.0, 0.0, effects.DUR_FAST, on_finished=self.hide)
