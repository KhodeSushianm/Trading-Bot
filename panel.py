#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""پنل کنترل دستیار سیگنال فارکس — نسخهٔ ۰٫۵ (بازطراحی کامل رابط).

زبان بصری:
  • تم تاریکِ مونوکروم (سیاه/سفید) — فقط سبز برای خرید/موفقیت و قرمز برای
    فروش/وتو/خطا. هیچ رنگ سومی در رابط نیست.
  • چیدمان Fluent ویندوز ۱۱: هدر باریک، ریل ناوبری عمودی با آیکون،
    کارت‌های گرد با مرز موئی، تایپوگرافی سه‌سطحی.
  • انیمیشن ظریف: Splash محو‌شونده، ورود پلکانی کارت‌ها، نشانگر ناوبری متحرک،
    نقطهٔ وضعیت تپنده، Toast برای سیگنال جدید.
  • روی ویندوز ۱۱: نوار عنوان تیره + Mica + گوشه گرد (با fallback بی‌خطر).

اجرا:
    python panel.py                پنل + Splash
    python panel.py --selftest     خودآزمون بدون پنجره (CI)
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
                               QPushButton, QSizePolicy, QStackedWidget,
                               QVBoxLayout, QWidget)

from src import app_paths
from src.config import load_config, save_local_config
from src.engine import BotLoop, check_event_alerts, run_briefing, run_cycle
from src.notify import telegram
from src.ui import dwm, effects, icons
from src.ui.splash import WelcomeSplash
from src.ui.theme import DARK, Space, Type, build_qss
from src.ui.widgets import Card, NavRail, StatTile, StatusPill, Toast

# ── ابزارهای کوچک ──────────────────────────────────────────────
_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
T = DARK


def fa(text) -> str:
    """تبدیل ارقام به فارسی."""
    return str(text).translate(_FA_DIGITS)


def load_fonts() -> str:
    """ثبت فونت‌ها و انتخاب خانواده. اولویت: ایران‌سنس کاربر ← وزیرمتن ← پیش‌فرض."""
    families: list[str] = []
    for d in app_paths.fonts_dirs():
        if not d.exists():
            continue
        for f in sorted(list(d.glob("*.ttf")) + list(d.glob("*.otf"))):
            fid = QFontDatabase.addApplicationFont(str(f))
            if fid != -1:
                families += QFontDatabase.applicationFontFamilies(fid)
    for fam in families:
        if "iransans" in fam.lower().replace(" ", ""):
            return fam
    for fam in families:
        if "vazirmatn" in fam.lower():
            return "Vazirmatn"
    return families[0] if families else "Segoe UI"


# ══════════════════════════════════════════════════════════════
#  ویجت‌های اختصاصی داشبورد
# ══════════════════════════════════════════════════════════════
class StrengthBars(QWidget):
    """نوارهای افقی قدرت ارزها حول صفر — سفید برای مثبت، خاکستری برای منفی."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[tuple[str, float]] = []
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def set_data(self, ranking: list[tuple[str, float]]) -> None:
        self._data = list(ranking)
        self.update()

    def paintEvent(self, ev) -> None:      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        if not self._data:
            p.setPen(QColor(T.text_3))
            p.drawText(self.rect(), Qt.AlignCenter, "هنوز داده‌ای نیست — یک چرخه تحلیل اجرا کن")
            p.end()
            return

        vals = [v for _, v in self._data]
        vmax = max(abs(min(vals)), abs(max(vals)), 0.0001)
        n = len(self._data)
        row_h = max(14, min(24, self.height() // max(n, 1)))
        bar_h = max(5, row_h - 9)
        label_w = 34
        val_w = 62
        area = self.width() - label_w - val_w
        mid = val_w + area / 2.0
        half = area / 2.0 - 4

        f = QFont()
        f.setPixelSize(Type.CAPTION + 1)
        p.setFont(f)
        # محور صفر
        p.setPen(QPen(QColor(T.border_strong), 1, Qt.DashLine))
        p.drawLine(QPoint(int(mid), 2), QPoint(int(mid), n * row_h - 2))

        for i, (ccy, v) in enumerate(self._data):
            y = i * row_h + (row_h - bar_h) // 2
            frac = max(-1.0, min(1.0, v / vmax))
            w = int(abs(frac) * half)
            color = QColor(T.accent_ink) if v >= 0 else QColor(T.text_3)
            # برچسب ارز — سمت راست (ابتدای خط در RTL)، چسبیده به نوار
            p.setPen(QColor(T.text_2))
            p.drawText(QRect(self.width() - label_w, y, label_w - 6, bar_h + 4),
                       Qt.AlignLeft | Qt.AlignVCenter, ccy)
            # نوار
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            if v >= 0:
                p.drawRoundedRect(QRect(int(mid), y, max(w, 2), bar_h), 2, 2)
            else:
                p.drawRoundedRect(QRect(int(mid) - max(w, 2), y, max(w, 2), bar_h), 2, 2)
            # مقدار — سمت چپ، چسبیده به نوار
            p.setPen(QColor(T.text_3))
            p.drawText(QRect(6, y, val_w - 8, bar_h + 4),
                       Qt.AlignRight | Qt.AlignVCenter,
                       "\u200E" + f"{v:+.2f}%")
        p.end()


def _plain(max_blocks: int | None = None, placeholder: str = "") -> QPlainTextEdit:
    v = QPlainTextEdit()
    v.setObjectName("plain")
    v.setReadOnly(True)
    # متن‌ها فارسی‌محورند؛ جهت سند باید RTL باشد وگرنه چپ‌چین می‌افتند
    v.setLayoutDirection(Qt.RightToLeft)
    if max_blocks:
        v.setMaximumBlockCount(max_blocks)
    if placeholder:
        v.setPlaceholderText(placeholder)
    return v


def _btn(text: str, obj: str, icon_name: str = "", tip: str = "") -> QPushButton:
    b = QPushButton(text)
    b.setObjectName(obj)
    if icon_name:
        b.setIcon(icons.icon(icon_name, 16,
                             "#0A0A0B" if obj == "primary" else T.text))
        b.setIconSize(QSize(16, 16))
    if tip:
        b.setToolTip(tip)
    b.setMinimumHeight(38)
    b.setCursor(Qt.PointingHandCursor)
    return b


# ══════════════════════════════════════════════════════════════
#  پنجرهٔ اصلی
# ══════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    # ایندکس صفحات (همان ترتیب ریل ناوبری)
    TAB_DASH, TAB_SIGNAL, TAB_REPORT, TAB_FUND, TAB_BRIEF, TAB_LOG, TAB_SETTINGS = range(7)

    def __init__(self, show_splash: bool = True):
        super().__init__()
        self.q: queue.Queue = queue.Queue()
        self.cfg = load_config()
        uicfg = self.cfg.get("ui") or {}
        self.user_name = str(uicfg.get("user_name") or "سوشیان")
        effects.set_animations(bool(uicfg.get("animations", True)))
        self.loop = BotLoop(on_log=lambda m: self.q.put(("log", m)),
                            on_report=lambda r: self.q.put(("report", r)),
                            on_briefing=lambda r: self.q.put(("briefing", r)),
                            on_fundamental=lambda r: self.q.put(("fundamental", r)),
                            on_signal=lambda r: self.q.put(("signal", r)),
                            cfg_provider=load_config)
        self._build_ui()
        self._load_tg_fields()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_queue)
        self.timer.start(300)
        self.tick = QTimer(self)
        self.tick.timeout.connect(self._tick)
        self.tick.start(1000)

        self._splash = None
        if show_splash and bool(uicfg.get("splash", True)):
            self._show_splash()
        else:
            self._after_splash()

    # ── Splash ────────────────────────────────────────────────
    def _show_splash(self) -> None:
        try:
            self._splash = WelcomeSplash(
                user_name=self.user_name,
                version=app_paths.APP_VERSION,
                tagline="دستیار تحلیل و سیگنال فارکس",
                t=T, hold_ms=1500)
            self._splash.show_and_run(self._after_splash)
        except Exception:
            # Splash تزئینی است؛ اگر شکست خورد برنامه باید بالا بیاید
            self._splash = None
            self._after_splash()

    def _after_splash(self) -> None:
        self.show()
        self.raise_()
        effects.fade(self.centralWidget(), 0.0, 1.0, effects.DUR_SLOW)
        self._log(f"👋 خوش اومدی {self.user_name}! دکمهٔ «شروع» را بزن تا تحلیل خودکار فعال شود.")
        self._log("💡 برای دریافت گزارش‌ها روی گوشی، از منوی «تنظیمات» تلگرام را وصل کن.")

    # ── ساخت رابط ─────────────────────────────────────────────
    def _build_ui(self) -> None:
        self.setWindowTitle(f"دستیار سیگنال فارکس — {app_paths.APP_VERSION}")
        self.resize(1180, 860)
        self.setMinimumSize(940, 640)
        ico = app_paths.bundled_dir() / "assets" / "icon.ico"
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))
        dwm.apply_win11(self)

        central = QWidget()
        central.setObjectName("app")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_nav())
        body.addWidget(self._build_pages(), 1)
        root.addLayout(body, 1)

        self.setCentralWidget(central)
        self.toast = Toast(central, t=T)
        self.toast.setParent(central)
        self.toast.hide()

    def _build_header(self) -> QFrame:
        h = QFrame()
        h.setObjectName("header")
        h.setFixedHeight(62)
        lay = QHBoxLayout(h)
        lay.setContentsMargins(Space.XL, 0, Space.XL, 0)
        lay.setSpacing(Space.MD)

        logo = QLabel()
        logo.setFixedSize(30, 30)
        logo.setPixmap(icons.icon("logo", 30, T.accent_ink, 1.5).pixmap(30, 30))
        lay.addWidget(logo)

        tcol = QVBoxLayout()
        tcol.setSpacing(1)
        name = QLabel("دستیار سیگنال فارکس")
        name.setObjectName("appname")
        sub = QLabel("تحلیل · فاندامنتال · اخبار → داور امتیازدهی")
        sub.setObjectName("appsub")
        tcol.addWidget(name)
        tcol.addWidget(sub)
        lay.addLayout(tcol)
        lay.addStretch(1)

        # چیپ خوش‌آمد
        chip = QFrame()
        chip.setObjectName("greetchip")
        cl = QHBoxLayout(chip)
        cl.setContentsMargins(12, 4, 12, 4)
        cl.setSpacing(Space.SM)
        uic = QLabel()
        uic.setFixedSize(14, 14)
        uic.setPixmap(icons.icon("user", 14, T.text_2).pixmap(14, 14))
        cl.addWidget(uic)
        self.greet_lbl = QLabel(f"خوش اومدی {self.user_name}")
        self.greet_lbl.setObjectName("greetchip_txt")
        cl.addWidget(self.greet_lbl)
        lay.addWidget(chip)

        self.clock_lbl = QLabel("")
        self.clock_lbl.setObjectName("clock")
        lay.addWidget(self.clock_lbl)
        return h

    def _build_nav(self) -> NavRail:
        self.nav = NavRail(self, t=T)
        self.nav.setFixedWidth(196)
        self.nav.add_item("dash", "داشبورد", "dashboard")
        self.nav.add_item("signals", "سیگنال‌ها", "target")
        self.nav.add_item("report", "گزارش کامل", "report")
        self.nav.add_item("fund", "تقویم و اخبار", "calendar")
        self.nav.add_item("brief", "بریفینگ", "sunrise")
        self.nav.add_item("live", "گزارش زنده", "live")
        self.nav.add_item("settings", "تنظیمات", "settings")
        self.nav.finish()
        self.nav.activated.connect(self._on_nav)
        return self.nav

    # ── صفحات ─────────────────────────────────────────────────
    def _build_pages(self) -> QStackedWidget:
        self.pages = QStackedWidget()
        self.pages.addWidget(self._page_dash())
        self.pages.addWidget(self._page_signals())
        self.pages.addWidget(self._page_report())
        self.pages.addWidget(self._page_fund())
        self.pages.addWidget(self._page_brief())
        self.pages.addWidget(self._page_live())
        self.pages.addWidget(self._page_settings())
        return self.pages

    def _page_frame(self, title: str, sub: str, build) -> tuple:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(Space.XL, Space.LG, Space.XL, Space.LG)
        lay.setSpacing(Space.LG)
        head = QHBoxLayout()
        ttl = QLabel(title)
        ttl.setObjectName("pagetitle")
        sb = QLabel(sub)
        sb.setObjectName("pagesub")
        v = QVBoxLayout()
        v.setSpacing(2)
        v.addWidget(ttl)
        v.addWidget(sb)
        head.addLayout(v)
        head.addStretch(1)
        build(head)                      # هر صفحه می‌تواند اقدام سمت چپ اضافه کند
        lay.addLayout(head)
        return w, lay

    # ── داشبورد ───────────────────────────────────────────────
    def _page_dash(self) -> QWidget:
        w, lay = self._page_frame(
            "داشبورد", "نمای کلی وضعیت ربات، سیگنال‌ها و رویدادهای پیش‌رو",
            self._dash_actions)

        # کارت وضعیت (hero)
        hero = Card(t=T)
        hl = QHBoxLayout()
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(Space.MD)
        self.status_pill = StatusPill(t=T)
        hl.addWidget(self.status_pill)
        hl.addSpacing(Space.MD)
        self.last_run_lbl = QLabel("آخرین تحلیل: —")
        self.last_run_lbl.setObjectName("label")
        hl.addWidget(self.last_run_lbl)
        hl.addStretch(1)
        self.next_run_lbl = QLabel("")
        self.next_run_lbl.setObjectName("mono")
        hl.addWidget(self.next_run_lbl)
        self.veto_lbl = QLabel("")
        self.veto_lbl.setObjectName("label")
        self.veto_lbl.setWordWrap(True)
        hl.addSpacing(Space.LG)
        hl.addWidget(self.veto_lbl)
        hero.add_layout(hl)
        lay.addWidget(hero)

        # کارت‌های آمار
        row = QHBoxLayout()
        row.setSpacing(Space.MD)
        self.st_signals = StatTile("سیگنال این چرخه", "—", "target", "", t=T)
        self.st_score = StatTile("بیشترین امتیاز", "—", "chart", "", t=T)
        self.st_news = StatTile("خبرهای رصدشده", "—", "live", "", t=T)
        self.st_veto = StatTile("نمادهای وتوشده", "—", "shield", "", t=T)
        for s in (self.st_signals, self.st_score, self.st_news, self.st_veto):
            row.addWidget(s, 1)
        lay.addLayout(row)

        # دو ستون: سیگنال‌ها + رویدادها
        mid = QHBoxLayout()
        mid.setSpacing(Space.MD)
        c1 = Card("آخرین سیگنال‌ها", "", "target", t=T)
        self.dash_signals = _plain(None, "هنوز سیگنالی صادر نشده — و این طبیعی است.")
        c1.add_widget(self.dash_signals, 1)
        c2 = Card("رویدادهای پیش‌رو", "تقویم اقتصادی — ۴۸ ساعت آینده", "calendar", t=T)
        self.dash_events = _plain(None, "رویدادی در این بازه نیست.")
        c2.add_widget(self.dash_events, 1)
        c1.setFixedHeight(210)
        c2.setFixedHeight(210)
        mid.addWidget(c1, 1)
        mid.addWidget(c2, 1)
        lay.addLayout(mid)

        # جریان قدرت ارزها
        c3 = Card("جریان قدرت ارزها",
                  "تغییر درصد ۲۴ ساعت اخیر — سفید = قوی‌تر، خاکستری = ضعیف‌تر",
                  "chart", t=T)
        self.strength = StrengthBars()
        self.strength.setMinimumHeight(120)
        c3.add_widget(self.strength, 1)
        lay.addWidget(c3, 1)
        return w

    def _dash_actions(self, head: QHBoxLayout) -> None:
        self.btn_once = _btn("تحلیل یک‌بار", "ghost", "refresh", "همین حالا یک چرخه تحلیل اجرا کن")
        self.btn_once.clicked.connect(self._on_once)
        self.btn_brief = _btn("بریفینگ", "ghost", "sunrise", "ساخت و ارسال بریفینگ صبحگاهی")
        self.btn_brief.clicked.connect(self._on_briefing)
        self.btn_stop = _btn("توقف", "red", "stop", "توقف حلقهٔ تحلیل خودکار")
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_start = _btn("شروع ربات", "primary", "play", "شروع تحلیل خودکار (هر ۱۵ دقیقه)")
        self.btn_start.clicked.connect(self._on_start)
        head.addWidget(self.btn_once)
        head.addWidget(self.btn_brief)
        head.addWidget(self.btn_stop)
        head.addWidget(self.btn_start)

    # ── سایر صفحات ────────────────────────────────────────────
    def _page_signals(self) -> QWidget:
        w, lay = self._page_frame("سیگنال‌ها", "سیگنال‌های صادرشده با دلایل کامل",
                                  lambda h: None)
        self.sig_view = _plain(None,
                               "هنوز سیگنالی صادر نشده.\n"
                               "داور فقط وقتی سیگنال می‌دهد که هیچ وتویی فعال نباشد "
                               "و امتیاز ≥ ۷ از ۱۱ شود.")
        lay.addWidget(self.sig_view, 1)
        return w

    def _page_report(self) -> QWidget:
        w, lay = self._page_frame("گزارش کامل", "تحلیل تکنیکال + تاییدیه + تقویم + اخبار + داور",
                                  lambda h: None)
        self.report_view = _plain(None, "هنوز گزارشی نیست — «تحلیل یک‌بار» را بزن.")
        lay.addWidget(self.report_view, 1)
        return w

    def _page_fund(self) -> QWidget:
        w, lay = self._page_frame("تقویم و اخبار", "موتور فاندامنتال و رصد اخبار",
                                  lambda h: None)
        self.fund_view = _plain(None, "هنوز داده‌ای نیست.")
        lay.addWidget(self.fund_view, 1)
        return w

    def _page_brief(self) -> QWidget:
        w, lay = self._page_frame("بریفینگ صبحگاهی", "خلاصهٔ روز قبل از باز شدن لندن",
                                  lambda h: None)
        self.brief_view = _plain(None,
                                 "بریفینگ هنوز ساخته نشده — دکمهٔ «بریفینگ» را بزن "
                                 "یا منتظر ساعت تنظیم‌شده بمان.")
        lay.addWidget(self.brief_view, 1)
        return w

    def _page_live(self) -> QWidget:
        w, lay = self._page_frame("گزارش زنده", "رویدادها لحظه‌به‌لحظه", lambda h: None)
        self.log_view = _plain(4000, "رویدادی ثبت نشده.")
        lay.addWidget(self.log_view, 1)
        return w

    def _page_settings(self) -> QWidget:
        w, lay = self._page_frame("تنظیمات", "تلگرام، فایل‌ها و دربارهٔ برنامه",
                                  lambda h: None)

        tg = Card("تلگرام — دریافت گزارش‌ها روی گوشی", "", "send", t=T)
        self.tg_token = QLineEdit()
        self.tg_token.setPlaceholderText("توکن بات از BotFather (مثلاً 123456:ABC-DEF…)")
        self.tg_token.setEchoMode(QLineEdit.Password)
        self.tg_token.editingFinished.connect(self._save_tg_fields)
        self.tg_chat = QLineEdit()
        self.tg_chat.setPlaceholderText("شناسه چت (عدد) — یا دکمهٔ «گرفتن خودکار شناسه»")
        self.tg_chat.editingFinished.connect(self._save_tg_fields)
        self.btn_getid = _btn("گرفتن خودکار شناسه", "ghost", "user")
        self.btn_getid.clicked.connect(self._on_get_chat_id)
        self.btn_test = _btn("ارسال پیام تست", "ghost", "send")
        self.btn_test.clicked.connect(self._on_test_send)
        self.chk_send = QCheckBox("گزارش‌ها به تلگرام ارسال شود")
        self.chk_send.toggled.connect(self._save_tg_fields)
        self.tg_status = QLabel("")
        self.tg_status.setObjectName("hint")
        self.tg_status.setWordWrap(True)

        r1 = QHBoxLayout(); r1.setSpacing(Space.SM)
        l1 = QLabel("توکن بات:"); l1.setObjectName("label"); l1.setFixedWidth(70)
        r1.addWidget(l1); r1.addWidget(self.tg_token, 1)
        r2 = QHBoxLayout(); r2.setSpacing(Space.SM)
        l2 = QLabel("شناسه چت:"); l2.setObjectName("label"); l2.setFixedWidth(70)
        r2.addWidget(l2); r2.addWidget(self.tg_chat, 1); r2.addWidget(self.btn_getid)
        r3 = QHBoxLayout(); r3.setSpacing(Space.SM)
        r3.addWidget(self.chk_send); r3.addStretch(1); r3.addWidget(self.btn_test)
        tg.add_layout(r1); tg.add_layout(r2); tg.add_layout(r3)
        tg.add_widget(self.tg_status)
        hint = QLabel("راهنما: در تلگرام به @BotFather پیام بده و /newbot را بزن، توکن را اینجا بگذار؛ "
                      "سپس یک بار به بات خودت /start بفرست و «گرفتن خودکار شناسه» را بزن.")
        hint.setObjectName("hint"); hint.setWordWrap(True)
        tg.add_widget(hint)
        lay.addWidget(tg)

        files = Card("فایل‌ها", "", "folder", t=T)
        fl = QHBoxLayout(); fl.setSpacing(Space.SM)
        self.btn_cfg = _btn("بازکردن config.yaml", "ghost", "file_cfg")
        self.btn_cfg.clicked.connect(lambda: self._open_path(app_paths.config_path()))
        self.btn_logs = _btn("پوشهٔ لاگ‌ها", "ghost", "folder")
        self.btn_logs.clicked.connect(lambda: self._open_path(app_paths.logs_dir()))
        fl.addWidget(self.btn_cfg); fl.addWidget(self.btn_logs); fl.addStretch(1)
        files.add_layout(fl)
        note = QLabel("توکن و شناسهٔ تلگرام در config.local.yaml کنار برنامه ذخیره می‌شوند "
                      "و هرگز به گیت‌هاب نمی‌روند.")
        note.setObjectName("hint"); note.setWordWrap(True)
        files.add_widget(note)
        lay.addWidget(files)

        about = Card("درباره", "", "info", t=T)
        av = QLabel(f"نسخه {fa(app_paths.APP_VERSION)}  ·  تم مونوکروم تاریک  ·  "
                    f"طراحی Fluent ویندوز ۱۱\n"
                    "این ابزار فقط تحلیل و سیگنال می‌دهد و هیچ معامله‌ای انجام نمی‌دهد؛ "
                    "تصمیم نهایی با شماست.")
        av.setObjectName("label"); av.setWordWrap(True)
        about.add_widget(av)
        lay.addWidget(about)
        lay.addStretch(1)
        return w

    # ── ناوبری ────────────────────────────────────────────────
    def _on_nav(self, i: int) -> None:
        self.pages.setCurrentIndex(i)
        page = self.pages.currentWidget()
        effects.fade(page, 0.0, 1.0, effects.DUR_MED)

    # ── صف پیام‌ها ────────────────────────────────────────────
    def _fill(self, view: QPlainTextEdit, text: str, page_idx: int, label: str) -> None:
        stamp = fa(time.strftime("%H:%M:%S"))
        view.setPlainText(f"⟵ {label} — {stamp}\n\n{text}")
        self._flash_nav(page_idx)

    def _flash_nav(self, page_idx: int) -> None:
        if page_idx >= len(self.nav._items):      # noqa: SLF001
            return
        b = self.nav._items[page_idx]             # noqa: SLF001
        b.setProperty("badge", "true")
        b.style().unpolish(b); b.style().polish(b)

        def clear():
            b.setProperty("badge", "false")
            b.style().unpolish(b); b.style().polish(b)
        QTimer.singleShot(6000, clear)

    def _poll_queue(self) -> None:
        for _ in range(200):
            try:
                kind, payload = self.q.get_nowait()
            except queue.Empty:
                return
            if kind == "log":
                self._log(payload)
            elif kind == "report":
                self._fill(self.report_view, payload, self.TAB_REPORT, "گزارش")
            elif kind == "fundamental":
                self._fill(self.fund_view, payload, self.TAB_FUND, "تقویم و اخبار")
            elif kind == "briefing":
                self._fill(self.brief_view, payload, self.TAB_BRIEF, "بریفینگ")
                self.pages.setCurrentIndex(self.TAB_BRIEF)
            elif kind == "signal":
                self._fill(self.sig_view, payload, self.TAB_SIGNAL, "سیگنال‌ها")
                self.pages.setCurrentIndex(self.TAB_SIGNAL)
                self._toast_signal(payload)

    def _toast_signal(self, text: str) -> None:
        first = next((l for l in text.splitlines() if "سیگنال" in l), "سیگنال جدید")
        self.toast.show_message(first.strip(), "برای جزئیات و دلایل، تب «سیگنال‌ها» را ببین",
                                "target", T.accent_ink)

    def _log(self, msg: str) -> None:
        self.log_view.appendPlainText(msg)

    # ── تیک هر ثانیه ──────────────────────────────────────────
    def _tick(self) -> None:
        now = time.time()
        self.clock_lbl.setText(fa(time.strftime("%H:%M:%S")))
        st = self.loop.state
        running = self.loop.running
        once_busy = self.loop._once_running      # noqa: SLF001

        if running:
            self.status_pill.set_state("ok")
        elif once_busy:
            self.status_pill.set_state("busy")
        else:
            self.status_pill.set_state("err" if st.get("last_error") else "idle")

        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.btn_once.setEnabled(not once_busy)
        self.btn_brief.setEnabled(not once_busy)

        last = st.get("last_run")
        self.last_run_lbl.setText("آخرین تحلیل: " + (
            fa(time.strftime("%H:%M", time.localtime(last))) if last else "—"))
        nxt = st.get("next_run")
        self.next_run_lbl.setText(
            fa(f"تحلیل بعدی تا {int(nxt - now) // 60:02d}:{int(nxt - now) % 60:02d}")
            if running and nxt and nxt > now else "")

        vetoes = st.get("last_vetoes") or []
        self.veto_lbl.setText(
            f"🚫 وتو: {'، '.join(vetoes)}" if vetoes
            else ("وتوی فعالی نیست" if last else ""))

        self._refresh_dash(st)

    def _refresh_dash(self, st) -> None:
        sigs = st.get("last_signals") or []
        self.st_signals.set_value(fa(len(sigs)),
                                  "green" if sigs else "")
        best = max((x["score"] for x in sigs), default=None)
        self.st_score.set_value(fa(f"{best}/{sigs[0]['max_score']}") if best is not None else "—",
                                "green" if best is not None and best >= 7 else "")
        self.st_news.set_value(fa(st.get("news_count") or 0))
        nv = len(st.get("last_vetoes") or [])
        self.st_veto.set_value(fa(nv), "red" if nv else "")

        if sigs:
            lines = []
            for x in sigs:
                d = "خرید 🟢" if x["direction"] == "BUY" else "فروش 🔴"
                lines.append(f"{x['symbol']}  {d}  امتیاز {fa(x['score'])} از {fa(x['max_score'])}"
                             + ("" if x.get("sent") else "  (ارسال نشد)"))
            self.dash_signals.setPlainText("\n".join(lines))
        else:
            self.dash_signals.setPlainText("سیگنالی در این چرخه صادر نشد.")

        ups = st.get("upcoming") or []
        if ups:
            self.dash_events.setPlainText("\n".join(
                f"{'🔴' if u['impact'] == 'HIGH' else '🟠'} {u['title_fa']} ({u['country_fa']})"
                f" — {fa(abs(u['minutes']))} دقیقهٔ دیگر" for u in ups))
        else:
            self.dash_events.setPlainText("رویداد پراثر یا متوسطی در ۴۸ ساعت آینده نیست.")

        self.strength.set_data(st.get("ranking") or [])

    # ── اقدام‌ها ──────────────────────────────────────────────
    def _on_start(self) -> None:
        self.loop.start()

    def _on_stop(self) -> None:
        self.loop.stop()

    def _on_once(self) -> None:
        if not self.loop.run_once_async():
            self._log("[i] یک تحلیل دیگر در جریان است — کمی صبر کن")

    def _on_briefing(self) -> None:
        if not self.loop.run_briefing_async():
            self._log("[i] یک کار دیگر در جریان است — کمی صبر کن")
        else:
            self._log("🌅 ساخت بریفینگ صبحگاهی آغاز شد…")

    def _save_tg_fields(self) -> None:
        save_local_config({"telegram": {
            "bot_token": self.tg_token.text().strip(),
            "chat_id": self.tg_chat.text().strip(),
            "send_reports": self.chk_send.isChecked(),
        }})
        self.tg_status.setText("✔ تنظیمات تلگرام ذخیره شد (در فایل امن config.local.yaml)")

    def _load_tg_fields(self) -> None:
        tg = self.cfg.get("telegram") or {}
        self.tg_token.setText(str(tg.get("bot_token") or ""))
        self.tg_chat.setText(str(tg.get("chat_id") or ""))
        self.chk_send.setChecked(bool(tg.get("send_reports", True)))

    def _on_get_chat_id(self) -> None:
        token = self.tg_token.text().strip()
        if not token:
            self.tg_status.setText("⚠️ اول توکن بات را وارد کن (از @BotFather)")
            return
        self.tg_status.setText("⏳ در حال دریافت شناسه چت…")

        def work():
            ok, who = telegram.validate_token(token)
            if not ok:
                self.q.put(("log", f"[!] توکن نامعتبر: {who}"))
                return
            cid, msg = telegram.get_chat_id(token)
            if cid:
                self.tg_chat.setText(cid)
                self._save_tg_fields()
            else:
                self.tg_status.setText(f"⚠️ {msg}")
        threading.Thread(target=work, daemon=True).start()

    def _on_test_send(self) -> None:
        token = self.tg_token.text().strip()
        chat = self.tg_chat.text().strip()
        if not token or not chat:
            self.tg_status.setText("⚠️ توکن و شناسه چت را وارد کن")
            return
        self.tg_status.setText("⏳ در حال ارسال پیام تست…")

        def work():
            text = (f"✅ پیام تست دستیار سیگنال فارکس\n"
                    f"اگر این پیام را می‌بینی، تلگرام درست تنظیم شده است.\n"
                    f"نسخه {app_paths.APP_VERSION}")
            ok, msg = telegram.send_message(token, chat, text)
            self.tg_status.setText(("✅ ارسال شد! " if ok else "❌ ") + msg)
        threading.Thread(target=work, daemon=True).start()

    def _open_path(self, path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(path))     # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            self._log(f"[!] بازکردن مسیر ناموفق: {e}")

    def resizeEvent(self, ev) -> None:      # noqa: N802
        super().resizeEvent(ev)
        if getattr(self, "toast", None) is not None:
            self.toast._place()             # noqa: SLF001

    def closeEvent(self, event) -> None:    # noqa: N802
        try:
            self.loop.stop()
        except Exception:
            pass
        super().closeEvent(event)


# ══════════════════════════════════════════════════════════════
#  خودآزمون و ورودی
# ══════════════════════════════════════════════════════════════
def _selftest() -> int:
    """خودآزمون بدون پنجره (برای CI): GUI + موتور + داور را بارگذاری و بررسی می‌کند."""
    app_paths.fix_console_encoding()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    fam = load_fonts()
    app.setFont(QFont(fam, 11))
    app.setStyleSheet(build_qss(fam))

    win = MainWindow(show_splash=False)
    win.show()
    app.processEvents()

    # منطق غیرگرافیکی
    from src.notify.telegram import _chunks
    assert len(_chunks("x" * 9000)) >= 3, "تقسیم پیام تلگرام درست کار نمی‌کند"
    assert callable(run_cycle) and callable(run_briefing) and callable(check_event_alerts)

    # ساختار رابط
    assert win.pages.count() == 7, f"انتظار ۷ صفحه، {win.pages.count()} پیدا شد"
    assert (win.TAB_DASH, win.TAB_SIGNAL, win.TAB_REPORT, win.TAB_FUND,
            win.TAB_BRIEF, win.TAB_LOG, win.TAB_SETTINGS) == tuple(range(7))
    assert len(win.nav._items) == 7, "ریل ناوبری باید ۷ آیتم داشته باشد"   # noqa: SLF001
    assert win.user_name, "نام کاربر برای Splash باید مقدار داشته باشد"

    # آیکون‌ها باید رندر شوند (نه fallback خالی)
    for nm in ("dashboard", "target", "play", "stop", "logo"):
        pm = icons.icon(nm, 24, "#FFFFFF").pixmap(24, 24)
        assert not pm.isNull(), f"آیکون {nm} رندر نشد"

    # داور + فاندامنتال بدون اینترنت
    from src.fundamental import calendar as cal
    from src.fundamental import news as nw
    from src.judge.scoring import compute_levels, judge_config

    evs = cal.parse_events([{"country": "USD", "date": "2026-09-16T14:00:00-04:00",
                             "title": "Federal Funds Rate", "impact": "High",
                             "forecast": "4.00%", "previous": "3.75%"}])
    assert len(evs) == 1 and evs[0].when.hour == 18
    sc, direction, _k, _b, _r = nw.score_text("USDJPY surges as the BOJ hike disappoints")
    assert direction == {"USD": 1, "JPY": -1}, f"جهت‌دهی اخبار: {direction}"
    jc = judge_config({})
    sl, tp, risk, capped = compute_levels("BUY", 1.149, 0.001, 1.1486, 1.156, jc["risk"])
    assert sl < 1.1486 < 1.149 < tp and not capped, "ریاضی SL/TP"

    win.close()
    print(f"SELFTEST OK — فونت: {fam} | صفحات: {win.pages.count()} | "
          f"آیکون‌ها و داور سالم | نسخه {app_paths.APP_VERSION}")
    return 0


def main() -> None:
    app_paths.fix_console_encoding()

    if "--selftest" in sys.argv:
        sys.exit(_selftest())

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setLayoutDirection(Qt.RightToLeft)

    # تک‌نمونه
    from PySide6.QtCore import QSharedMemory
    guard = QSharedMemory("ForexAssistant_SingleInstance_Guard_v2")
    if not guard.create(1):
        if guard.attach():
            guard.detach()
        if not guard.create(1):
            QMessageBox.warning(None, "دستیار سیگنال فارکس",
                                "برنامه از قبل در حال اجراست! (یک پنجرهٔ دیگر باز است)")
            sys.exit(0)
    app._single_instance_guard = guard    # noqa: SLF001

    fam = load_fonts()
    app.setFont(QFont(fam, 11))
    app.setStyleSheet(build_qss(fam))

    win = MainWindow(show_splash="--no-splash" not in sys.argv)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
