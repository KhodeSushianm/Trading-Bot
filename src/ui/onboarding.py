# -*- coding: utf-8 -*-
"""صفحهٔ ورود / فعال‌سازی — «Onboarding» جوهری با شفق (v0.20.0).

طراحی:
  پنجرهٔ بی‌قاب با پس‌زمینهٔ جوهریِ شفق‌دار (همان موتور procedural پس‌زمینهٔ
  برنامه، حالت dark) و دو ستون:
    • ستون برند (راست، RTL): لوگو + واژه‌نشان ODIN + سه «ویژگی» با چیپ آیکون
      + اعتبارنامهٔ سازنده (تلگرام @Khode_Sushian).
    • ستون گام‌ها (چپ): سه گام با انیمیشن محو/ظریف —
        ۱) خوش‌آمد + نام کاربر
        ۲) کد دستگاه (کپی/تلگرام) + کلید لایسنس + دورهٔ آزمایشی
        ۳) موفقیت (تیک سبز) و بستن خودکار
  نقطه‌های گام پایین ستون، دکمهٔ ضربدر بالا، درگ با ماوس (چون بی‌قاب است).

سازگاری:
  یک QDialog است؛ exec()/accept()/reject() مثل قبل کار می‌کند و تست
  رگرسیونِ دیالوگ فعال‌سازی (tests/manual/test_activation_dialog.py)
  با پچ کردن QDialog.exec همان سناریوها را می‌سنجد.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, QSize
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from . import effects, icons
from .backdrop import render_aurora
from .theme import DARK, Space, Theme
from .widgets import IconChip


def _px(t: Theme, hex_color: str, alpha: float) -> str:
    return t.rgba(hex_color, alpha)


class OnboardingDialog(QDialog):
    """درگاه ورود: نام → فعال‌سازی/تریال → موفقیت."""

    W, H = 1040, 680

    def __init__(self, parent=None, t: Theme = DARK, app_version: str = "",
                 app_name: str = "ODIN Assistant"):
        super().__init__(parent)
        self._t = t
        self._app_version = app_version
        self._app_name = app_name
        self.user_name = ""
        self.activation_result = False

        self.setWindowTitle("ورود — " + app_name)
        self.setModal(True)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setFixedSize(self.W, self.H)
        self.setWindowFlags(self.windowFlags()
                            | Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._pm: QPixmap | None = None
        self._phase = 0.0
        self._drag_pos: QPoint | None = None

        # پس‌زمینهٔ شفقِ جوهری — انیمیشن خیلی آرام (فقط اگر انیمیشن روشن است)
        self._bg_timer = QTimer(self)
        self._bg_timer.setInterval(70)
        self._bg_timer.timeout.connect(self._on_bg_tick)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        shell = QFrame(self)
        shell.setObjectName("onb_shell")
        root.addWidget(shell)
        lay = QHBoxLayout(shell)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_brand_column(), 0)
        lay.addWidget(self._build_steps_column(), 1)

        # استایل درون‌برنامه (isolated) — بیرون از QSS سراسری
        t_ = t
        shell.setStyleSheet(f"""
QFrame#onb_shell {{ background: transparent; border: none; }}
QFrame#onb_shell QLabel {{ color: #F4F4F7; background: transparent; }}
QLabel#onb_word {{ font-size: 40px; font-weight: 900; color: #FFFFFF;
                   letter-spacing: 1px; }}
QLabel#onb_word2 {{ font-size: 15px; font-weight: 700; color: {t_.brand};
                    letter-spacing: 6px; }}
QLabel#onb_tag {{ font-size: 13px; color: {_px(t_, '#FFFFFF', 0.62)}; }}
QLabel#onb_feat_t {{ font-size: 13.5px; font-weight: 700; color: #FFFFFF; }}
QLabel#onb_feat_s {{ font-size: 11px; color: {_px(t_, '#FFFFFF', 0.52)}; }}
QLabel#onb_title {{ font-size: 24px; font-weight: 800; color: #FFFFFF; }}
QLabel#onb_sub {{ font-size: 12.5px; color: {_px(t_, '#FFFFFF', 0.60)}; }}
QLabel#onb_credit {{ font-size: 10.5px; color: {_px(t_, '#FFFFFF', 0.45)}; }}
QFrame#onb_glass {{ background: {_px(t_, '#FFFFFF', 0.06)};
                    border: 1px solid {_px(t_, '#FFFFFF', 0.10)};
                    border-radius: 18px; }}
QFrame#onb_err {{ background: rgba(214, 69, 69, 0.16);
                  border: 1px solid rgba(255, 120, 120, 0.35);
                  border-radius: 14px; }}
QLabel#onb_err_txt {{ color: #FF9A9A; font-size: 11.5px; }}
QLineEdit#onb_input {{
    background: {_px(t_, '#FFFFFF', 0.07)};
    border: 1.5px solid {_px(t_, '#FFFFFF', 0.14)};
    border-radius: 14px; padding: 12px 16px;
    color: #FFFFFF; font-size: 14px;
    selection-background-color: {t_.brand};
}}
QLineEdit#onb_input:hover {{ border-color: {_px(t_, '#FFFFFF', 0.26)}; }}
QLineEdit#onb_input:focus {{ border-color: {t_.brand};
                             background: {_px(t_, '#FFFFFF', 0.09)}; }}
QLineEdit#onb_code {{
    background: {_px(t_, '#FFFFFF', 0.05)};
    border: 1.5px dashed {_px(t_, '#FFFFFF', 0.22)};
    border-radius: 14px; padding: 12px 16px;
    color: #FFFFFF; font-size: 20px; font-weight: 800;
    letter-spacing: 4px; font-family: "Cascadia Mono", "Consolas", monospace;
}}
QLineEdit#onb_license {{
    background: {_px(t_, '#FFFFFF', 0.07)};
    border: 1.5px solid {_px(t_, '#FFFFFF', 0.14)};
    border-radius: 14px; padding: 13px 16px;
    color: #FFFFFF; font-size: 16px; font-weight: 700; letter-spacing: 2px;
    font-family: "Cascadia Mono", "Consolas", monospace;
}}
QLineEdit#onb_license:focus {{ border-color: {t_.brand}; }}
QPushButton#onb_primary {{
    background-color: {t_.on_ink}; color: {t_.accent_ink};
    border: none; border-radius: 999px; padding: 13px 26px;
    font-size: 14px; font-weight: 800;
}}
QPushButton#onb_primary:hover {{ background-color: #EAEAF0; }}
QPushButton#onb_primary:pressed {{ background-color: #D8D8E0; }}
QPushButton#onb_ghost {{
    background: {_px(t_, '#FFFFFF', 0.08)}; color: #FFFFFF;
    border: 1px solid {_px(t_, '#FFFFFF', 0.16)};
    border-radius: 999px; padding: 12px 22px; font-size: 12.5px; font-weight: 700;
}}
QPushButton#onb_ghost:hover {{ background: {_px(t_, '#FFFFFF', 0.15)}; }}
QPushButton#onb_icon {{
    background: {_px(t_, '#FFFFFF', 0.08)}; color: #FFFFFF;
    border: 1px solid {_px(t_, '#FFFFFF', 0.12)}; border-radius: 999px;
}}
QPushButton#onb_icon:hover {{ background: {_px(t_, '#FFFFFF', 0.16)}; }}
QLabel#onb_chip {{
    background: {_px(t_, '#FFFFFF', 0.08)}; color: {_px(t_, '#FFFFFF', 0.72)};
    border-radius: 999px; padding: 5px 14px; font-size: 11px; font-weight: 700;
}}
""")

        self._step = 0
        self._go_step(0, animate=False)

        # انیمیشن شفق فقط وقتی کاربر انیمیشن را خاموش نکرده باشد
        if effects.animations_enabled():
            self._bg_timer.start()

    # ── ستون برند ─────────────────────────────────────────────
    def _build_brand_column(self) -> QWidget:
        t = self._t
        w = QWidget()
        w.setFixedWidth(400)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(Space.XXL, Space.XXL, Space.XL, Space.XXL)
        lay.setSpacing(Space.MD)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(Space.MD)
        logo = IconChip("logo", 56, tint=_px(t, "#FFFFFF", 0.08), color="#FFFFFF",
                        radius=18)
        logo_row.addWidget(logo)
        word = QVBoxLayout()
        word.setSpacing(0)
        w1 = QLabel("ODIN")
        w1.setObjectName("onb_word")
        w2 = QLabel("ASSISTANT")
        w2.setObjectName("onb_word2")
        word.addWidget(w1)
        word.addWidget(w2)
        logo_row.addLayout(word)
        logo_row.addStretch(1)
        lay.addLayout(logo_row)

        tag = QLabel("دستیار تحلیل و سیگنال فارکس — تحلیل، فاندامنتال و اخبار "
                     "با داورِ بدون استثنا")
        tag.setObjectName("onb_tag")
        tag.setWordWrap(True)
        lay.addWidget(tag)
        lay.addSpacing(Space.LG)

        for iconn, ft, fs in (
                ("layers", "تحلیل چندلایه",
                 "تکنیکال + فاندامنتال + اخبار + تأییدیهٔ تریدینگ‌ویو"),
                ("shield", "داور و دروازه‌های وتو",
                 "سیگنال فقط با پشتوانهٔ امتیاز — بدون استثنا"),
                ("bell", "هشدارها و نمودار زنده",
                 "حتی وقتی پنجره بسته است، در پس‌زمینه فعال است")):
            row = QHBoxLayout()
            row.setSpacing(Space.MD)
            row.addWidget(IconChip(iconn, 38, tint=_px(t, "#FFFFFF", 0.07),
                                   color="#FFFFFF", radius=12))
            col = QVBoxLayout()
            col.setSpacing(1)
            ftl = QLabel(ft)
            ftl.setObjectName("onb_feat_t")
            fsl = QLabel(fs)
            fsl.setObjectName("onb_feat_s")
            fsl.setWordWrap(True)
            col.addWidget(ftl)
            col.addWidget(fsl)
            row.addLayout(col, 1)
            lay.addLayout(row)

        lay.addStretch(1)

        ver = ""
        if self._app_version:
            ver = QLabel(f"نسخه {self._app_version}")
            ver.setObjectName("onb_credit")
            lay.addWidget(ver)
        cr_row = QHBoxLayout()
        cr_row.setSpacing(Space.SM)
        cr_row.addWidget(IconChip("telegram", 26, tint=_px(t, "#FFFFFF", 0.07),
                                  color="#FFFFFF", radius=9))
        cr = QLabel("Sushian Khoshkhani  ·  @Khode_Sushian")
        cr.setObjectName("onb_credit")
        cr_row.addWidget(cr)
        cr_row.addStretch(1)
        lay.addLayout(cr_row)
        return w

    # ── ستون گام‌ها ────────────────────────────────────────────
    def _build_steps_column(self) -> QWidget:
        t = self._t
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(Space.XL, Space.LG, Space.XXL, Space.XL)
        outer.setSpacing(Space.MD)

        top = QHBoxLayout()
        top.addStretch(1)
        self.btn_close = QPushButton()
        self.btn_close.setObjectName("onb_icon")
        self.btn_close.setFixedSize(36, 36)
        self.btn_close.setIcon(icons.icon("x", 16, "#FFFFFF"))
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("بستن")
        self.btn_close.clicked.connect(self.reject)
        top.addWidget(self.btn_close)
        outer.addLayout(top)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._step_welcome())
        self.stack.addWidget(self._step_activate())
        self.stack.addWidget(self._step_done())
        outer.addWidget(self.stack, 1)

        # نقطه‌های گام
        dots_row = QHBoxLayout()
        dots_row.addStretch(1)
        self._dots = []
        for i in range(3):
            d = QWidget()
            d.setFixedSize(8, 8)
            d.setAttribute(Qt.WA_StyledBackground, True)
            d.setStyleSheet("border-radius: 4px; background: rgba(255,255,255,0.18);")
            dots_row.addWidget(d)
            self._dots.append(d)
        dots_row.addStretch(1)
        outer.addLayout(dots_row)
        return w

    def _step_welcome(self) -> QWidget:
        t = self._t
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, Space.MD, 0, 0)
        lay.setSpacing(Space.MD)
        lay.addWidget(IconChip("sparkle", 48, tint=_px(t, "#FFFFFF", 0.08),
                               color="#FFFFFF", radius=16))
        ttl = QLabel("به ODIN خوش اومدی")
        ttl.setObjectName("onb_title")
        lay.addWidget(ttl)
        sub = QLabel("اول نامت را بنویس تا کل برنامه — از خوش‌آمدگویی تا "
                     "کارت‌های سیگنال — به نام خودت شخصی‌سازی شود.")
        sub.setObjectName("onb_sub")
        sub.setWordWrap(True)
        lay.addWidget(sub)
        lay.addSpacing(Space.SM)
        self.name_input = QLineEdit()
        self.name_input.setObjectName("onb_input")
        self.name_input.setPlaceholderText("نام تو — مثلاً سوشیان")
        self.name_input.setMaxLength(24)
        lay.addWidget(self.name_input)
        lay.addSpacing(Space.SM)
        b = QPushButton("شروع — قدم بعد")
        b.setObjectName("onb_primary")
        b.setCursor(Qt.PointingHandCursor)
        b.setIcon(icons.icon("chevron_left", 16, t.accent_ink))
        b.clicked.connect(self._on_next_from_welcome)
        lay.addWidget(b, 0, Qt.AlignLeft)
        self.name_input.returnPressed.connect(self._on_next_from_welcome)
        lay.addStretch(1)
        return w

    def _step_activate(self) -> QWidget:
        t = self._t
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(Space.MD)

        head = QHBoxLayout()
        head.setSpacing(Space.SM)
        back = QPushButton()
        back.setObjectName("onb_icon")
        back.setFixedSize(34, 34)
        back.setIcon(icons.icon("chevron_right", 15, "#FFFFFF"))
        back.setCursor(Qt.PointingHandCursor)
        back.setToolTip("قدم قبل")
        back.clicked.connect(lambda: self._go_step(0))
        head.addWidget(back)
        ttl = QLabel("فعال‌سازی برنامه")
        ttl.setObjectName("onb_title")
        head.addWidget(ttl)
        head.addStretch(1)
        lay.addLayout(head)

        # کارت کد دستگاه
        dev = QFrame()
        dev.setObjectName("onb_glass")
        dl = QVBoxLayout(dev)
        dl.setContentsMargins(Space.LG, Space.LG, Space.LG, Space.LG)
        dl.setSpacing(Space.SM)
        r1 = QHBoxLayout()
        r1.setSpacing(Space.SM)
        r1.addWidget(IconChip("monitor", 30, tint=_px(t, "#FFFFFF", 0.08),
                              color="#FFFFFF", radius=10))
        cap = QLabel("کد دستگاه تو")
        cap.setObjectName("onb_feat_t")
        r1.addWidget(cap)
        r1.addStretch(1)
        self.btn_copy = QPushButton("کپی")
        self.btn_copy.setObjectName("onb_ghost")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setIcon(icons.icon("copy", 14, "#FFFFFF"))
        self.btn_copy.clicked.connect(self._copy_code)
        r1.addWidget(self.btn_copy)
        dl.addLayout(r1)

        from src.license import get_device_code
        self._device_code = ""
        try:
            self._device_code = get_device_code()
        except Exception:
            self._device_code = "----"
        self.device_view = QLineEdit(self._device_code)
        self.device_view.setObjectName("onb_code")
        self.device_view.setReadOnly(True)
        self.device_view.setAlignment(Qt.AlignCenter)
        self.device_view.setLayoutDirection(Qt.LeftToRight)
        dl.addWidget(self.device_view)

        tg_row = QHBoxLayout()
        tg_row.setSpacing(Space.SM)
        tg_row.addWidget(IconChip("telegram", 24, tint=_px(t, "#FFFFFF", 0.08),
                                  color="#FFFFFF", radius=8))
        tg = QLabel("این کد را برای سازنده بفرست:  @Khode_Sushian")
        tg.setObjectName("onb_feat_s")
        tg_row.addWidget(tg)
        tg_row.addStretch(1)
        dl.addLayout(tg_row)
        lay.addWidget(dev)

        # کلید لایسنس
        lic_row = QHBoxLayout()
        lic_row.setSpacing(Space.SM)
        lic_row.addWidget(IconChip("key", 30, tint=_px(t, "#FFFFFF", 0.08),
                                   color="#FFFFFF", radius=10))
        lcap = QLabel("کلید لایسنس")
        lcap.setObjectName("onb_feat_t")
        lic_row.addWidget(lcap)
        lic_row.addStretch(1)
        lhint = QLabel("کلیدهای زمان‌دار یک بخش تاریخ هم دارند — همه را وارد کن")
        lhint.setObjectName("onb_credit")
        lic_row.addWidget(lhint)
        lay.addLayout(lic_row)

        self.license_input = QLineEdit()
        self.license_input.setObjectName("onb_license")
        self.license_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX[-YYMMDD]")
        self.license_input.setLayoutDirection(Qt.LeftToRight)
        self.license_input.setAlignment(Qt.AlignCenter)
        self.license_input.textChanged.connect(self._fmt_license)
        lay.addWidget(self.license_input)

        # بنر خطا
        self.err_box = QFrame()
        self.err_box.setObjectName("onb_err")
        self.err_box.setVisible(False)
        el = QHBoxLayout(self.err_box)
        el.setContentsMargins(Space.MD, 10, Space.MD, 10)
        el.setSpacing(Space.SM)
        el.addWidget(icons_label := QLabel())
        icons_label.setFixedSize(18, 18)
        icons_label.setPixmap(icons.icon("alert", 16, "#FF9A9A").pixmap(16, 16))
        self.err_lbl = QLabel("")
        self.err_lbl.setObjectName("onb_err_txt")
        self.err_lbl.setWordWrap(True)
        el.addWidget(self.err_lbl, 1)
        lay.addWidget(self.err_box)

        lay.addStretch(1)

        btns = QHBoxLayout()
        btns.setSpacing(Space.SM)
        self.btn_trial = QPushButton("شروع دورهٔ آزمایشی ۷ روزه")
        self.btn_trial.setObjectName("onb_ghost")
        self.btn_trial.setCursor(Qt.PointingHandCursor)
        self.btn_trial.setIcon(icons.icon("clock", 14, "#FFFFFF"))
        self.btn_trial.clicked.connect(self._on_trial)
        btns.addWidget(self.btn_trial)
        btns.addStretch(1)
        self.btn_activate = QPushButton("فعال‌سازی")
        self.btn_activate.setObjectName("onb_primary")
        # استایل درون‌خطی با توکن‌های تم: هم تست رگرسیون رنگ‌ها را resolve‌شده
        # می‌بیند، هم اگر QSS پوسته به هر دلیلی نرسد دکمه درست می‌ماند.
        self.btn_activate.setStyleSheet(
            f"background-color: {t.on_ink}; color: {t.accent_ink};"
            "border: none; border-radius: 999px; padding: 13px 26px;"
            "font-size: 14px; font-weight: 800;")
        self.btn_activate.setCursor(Qt.PointingHandCursor)
        self.btn_activate.setIcon(icons.icon("check", 16, t.accent_ink))
        self.btn_activate.clicked.connect(self._on_activate)
        btns.addWidget(self.btn_activate)
        lay.addLayout(btns)
        return w

    def _step_done(self) -> QWidget:
        t = self._t
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, Space.XL, 0, 0)
        lay.setSpacing(Space.MD)
        lay.setAlignment(Qt.AlignCenter)
        self.done_icon = IconChip("check_circle", 84, tint=_px(t, "#FFFFFF", 0.08),
                                  color=t.console_green, radius=42)
        lay.addWidget(self.done_icon, 0, Qt.AlignHCenter)
        ttl = QLabel("همه‌چیز آماده است!")
        ttl.setObjectName("onb_title")
        ttl.setAlignment(Qt.AlignCenter)
        lay.addWidget(ttl)
        self.done_sub = QLabel("")
        self.done_sub.setObjectName("onb_sub")
        self.done_sub.setWordWrap(True)
        self.done_sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.done_sub)
        lay.addStretch(1)
        return w

    # ── رفتار ──────────────────────────────────────────────────
    def _go_step(self, i: int, animate: bool = True) -> None:
        self._step = i
        self.stack.setCurrentIndex(i)
        page = self.stack.currentWidget()
        if animate:
            effects.fade(page, 0.0, 1.0, effects.DUR_MED)
            effects.rise(page, dy=10, ms=effects.DUR_MED)
        for k, d in enumerate(self._dots):
            d.setStyleSheet("border-radius: 4px; background: "
                            + ("#FFFFFF;" if k == i
                               else "rgba(255,255,255,0.18);"))

    def _show_error(self, msg: str, shake_target=None) -> None:
        self.err_lbl.setText(msg)
        self.err_box.setVisible(True)
        effects.shake(shake_target or self.err_box)

    def _hide_error(self) -> None:
        self.err_box.setVisible(False)

    def _on_next_from_welcome(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            self._go_step(0, animate=False)
            self.name_input.setFocus()
            effects.shake(self.name_input)
            return
        self.user_name = name
        self._hide_error()
        self._go_step(1)

    def _fmt_license(self, raw: str) -> None:
        """بزرگ‌سازی + خط‌تیره‌گذاری خودکار XXXX-XXXX-XXXX-XXXX[-YYMMDD]."""
        clean = "".join(ch for ch in raw.upper()
                        if ch.isalnum() and ch.isascii())
        parts = [clean[i:i + 4] for i in range(0, min(len(clean), 16), 4)]
        rest = clean[16:16 + 6]
        out = "-".join(parts)
        if rest:
            out += "-" + rest
        if out != raw:
            self.license_input.blockSignals(True)
            self.license_input.setText(out)
            self.license_input.blockSignals(False)

    def _copy_code(self) -> None:
        try:
            QApplication.clipboard().setText(self._device_code)
            self.btn_copy.setText("کپی شد ✔")
            QTimer.singleShot(1600, lambda: self.btn_copy.setText("کپی"))
        except Exception:
            pass

    def _on_activate(self) -> None:
        from src.license import activate_program
        key = self.license_input.text().strip()
        if not key:
            self._show_error("کلید لایسنس را وارد کن — یا دورهٔ آزمایشی را شروع کن.",
                             self.license_input)
            return
        ok, msg = activate_program(key, self.user_name)
        if ok:
            self._finish(msg or "لایسنس با موفقیت فعال شد")
        else:
            self._show_error(msg or "فعال‌سازی ناموفق بود", self.license_input)

    def _on_trial(self) -> None:
        from src.license import start_trial
        ok, msg = start_trial()
        if ok:
            self._finish((msg or "") + " — همهٔ امکانات فعال است")
        else:
            self._show_error(msg or "شروع دورهٔ آزمایشی ناموفق بود")

    def _finish(self, msg: str) -> None:
        self.activation_result = True
        self.done_sub.setText(msg)
        self._go_step(2)
        try:
            effects.fade(self.done_icon, 0.0, 1.0, effects.DUR_SLOW)
        except Exception:
            pass
        QTimer.singleShot(1200, self.accept)

    # ── پس‌زمینهٔ شفقِ جوهری (متحرک، کم‌قطع) ─────────────────
    def paintEvent(self, ev) -> None:      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if self._pm is None:
            self._pm = render_aurora(QSize(512, int(512 * self.H / self.W)),
                                     self._t, phase=self._phase, dark=True)
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 28, 28)
        p.setClipPath(path)
        p.drawPixmap(self.rect(), self._pm)
        # لبهٔ نورانی ظریف
        p.setClipping(False)
        from PySide6.QtGui import QPen
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 34), 1.4))
        p.drawPath(path)
        p.end()

    def _on_bg_tick(self) -> None:
        if not self.isVisible():
            return
        self._phase += 0.05
        self._pm = render_aurora(QSize(512, int(512 * self.H / self.W)),
                                 self._t, phase=self._phase, dark=True)
        self.update()

    def showEvent(self, ev) -> None:       # noqa: N802
        super().showEvent(ev)
        try:
            self.name_input.setFocus()
        except Exception:
            pass

    def closeEvent(self, ev) -> None:      # noqa: N802
        try:
            self._bg_timer.stop()
        except Exception:
            pass
        super().closeEvent(ev)

    def reject(self) -> None:
        try:
            self._bg_timer.stop()
        except Exception:
            pass
        super().reject()

    def accept(self) -> None:
        try:
            self._bg_timer.stop()
        except Exception:
            pass
        super().accept()

    # ── درگ پنجرهٔ بی‌قاب ─────────────────────────────────────
    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev) -> None:   # noqa: N802
        if self._drag_pos is not None and ev.buttons() & Qt.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
            ev.accept()

    def mouseReleaseEvent(self, ev) -> None:  # noqa: N802
        self._drag_pos = None
        ev.accept()
