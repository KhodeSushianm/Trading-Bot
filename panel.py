#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""پنل کنترل ODIN Assistant — دستیار تحلیل و سیگنال فارکس (تم روشن شیشه‌ای).

زبان بصری (الگو: داشبوردهای مدرن ۲۰۲۶ / رفرنس iDraft):
  • پس‌زمینهٔ خاکستری محو + پنل شیشه‌ای نیمه‌شفاف (بدون blur effect — procedural)
  • سایدبار = کارت شناور سفید با آیتم فعال = پیِل مشکی
  • کارت مشکی پرکنتراست برای «نمای کلی» و رویدادها؛ کارت سفید با سایهٔ نرم برای بقیه
  • هدر با سلام بزرگ «سلام {نام}!» + دکمه‌های دایره‌ای + پیِل مشکی اقدام اصلی
  • نمودار خطی نرم + حلقهٔ پیشرفت + کارت خط‌چین جای‌نگهدار
  • فقط سبز/قرمز به‌عنوان رنگ معنایی؛ بقیه کاملاً مونوکروم

اجرا:
    python panel.py                پنل + Splash
    python panel.py --selftest     خودآزمون بدون پنجره (CI)
"""
from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu,
                               QMainWindow, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QStackedWidget,
                               QSystemTrayIcon, QVBoxLayout, QWidget, QDialog,
                               QDialogButtonBox, QFormLayout, QComboBox)

from src import app_paths
from src.config import load_config, prune_local_config, save_local_config
from src.engine import BotLoop, check_event_alerts, run_briefing, run_cycle
from src.fa import fa_countdown
from src.notify import telegram
from src.ui import dwm, effects, icons
from src.ui.backdrop import paint_glass, render_backdrop
from src.ui.splash import WelcomeSplash
from src.ui.theme import DARK, Space, build_qss
from src.ui.widgets import (CandleChart, Card, DashedCard, InkCard, LineChart, NavRail,
                            RingGauge, StatTile, StatusPill, Stepper, Toast, ToggleSwitch)
from src.license import (check_and_enforce_license, activate_program,
                         get_device_id, get_device_code, is_activated,
                         deactivate_program, start_trial, trial_status)

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
T = DARK
# رنگ متن کارت مشکی در کد ست می‌شود؛ QSS روی برخی پلتفرم‌ها (ویندوز)
# به برچسب‌های فرزند القا نمی‌شود و متن سیاه روی سیاه نامرئی می‌ماند.
_INK_TITLE = f"color: {T.on_ink};"
_INK_CAP = f"color: {T.rgba('#FFFFFF', 0.55)};"

# ── تنظیمات مدیریت‌شدهٔ پنل (آینهٔ نسخهٔ اندروید) ────────────────
# این کلیدها از صفحهٔ تنظیماتِ پنل در config.local.yaml ذخیره می‌شوند
# (بیرون از گیت و با اولویت بر config.yaml) و «بازنشانی تنظیمات» فقط
# همین‌ها را از فایل محلی حذف می‌کند — تلگرام/ژورنال دست‌نخورده می‌مانند.
VETO_KEYS = ("weekend", "high_impact_event", "timeframe_conflict",
             "range_market", "volatility_spike", "breaking_news")
MANAGED_SETTINGS: dict[str, tuple[str, ...]] = {
    "ui": ("user_name", "splash", "animations"),
    "judge": ("enabled", "min_score", "max_signals_per_cycle", "veto"),
    "fundamental": ("enabled", "alerts_enabled"),
    "news": ("enabled",),
    "tradingview": ("enabled",),
    "loop": ("interval_minutes",),
    "briefing": ("enabled",),
    "journal": ("enabled", "conservative_both_touch"),
}


def fa(text) -> str:
    return str(text).translate(_FA_DIGITS)


def _dot_pixmap(color: str, size: int = 10) -> QPixmap:
    """نقطهٔ رنگی به‌جای ایموجی — پالت تک‌رنگ/معنایی و رندر یکسان روی همهٔ پلتفرم‌ها."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return pm


def load_fonts() -> str:
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


def _check_img() -> str:
    return (app_paths.bundled_dir() / "assets" / "checkbox_check.png").as_posix()


def _set_text(lbl: QLabel, txt: str) -> None:
    if lbl.text() != txt:
        lbl.setText(txt)


def _set_plain(view: QPlainTextEdit, txt: str) -> None:
    if view.toPlainText() != txt:
        view.setPlainText(txt)


def _plain(max_blocks: int | None = None, placeholder: str = "") -> QPlainTextEdit:
    v = QPlainTextEdit()
    v.setObjectName("plain")
    v.setReadOnly(True)
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
        col = T.on_ink if obj == "primary" else T.text_2
        b.setIcon(icons.icon(icon_name, 16, col))
        b.setIconSize(QSize(16, 16))
    if tip:
        b.setToolTip(tip)
    b.setMinimumHeight(40)
    b.setCursor(Qt.PointingHandCursor)
    return b


def _circle(icon_name: str, tip: str) -> QPushButton:
    b = QPushButton()
    b.setObjectName("circle")
    b.setFixedSize(40, 40)
    b.setIcon(icons.icon(icon_name, 18, T.text_2))
    b.setIconSize(QSize(18, 18))
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    return b


def _set_row(label: str, sub: str, widget: QWidget | None = None) -> QWidget:
    """یک ردیف تنظیمات: عنوان+توضیح در یک سو، کنترل در سوی دیگر.

    آینهٔ `.set-row` نسخهٔ اندروید — در چیدمان RTL، متن سمت راست و
    سوئیچ/قدم‌شمار سمت چپ می‌نشیند (دقیقاً مثل موبایل).
    """
    row = QWidget()
    row.setObjectName("setrow")
    h = QHBoxLayout(row)
    h.setContentsMargins(2, 10, 2, 10)
    h.setSpacing(Space.MD)
    col = QVBoxLayout()
    col.setSpacing(2)
    lbl = QLabel(label)
    lbl.setObjectName("setlabel")
    sb = QLabel(sub)
    sb.setObjectName("setsub")
    sb.setWordWrap(True)
    col.addWidget(lbl)
    col.addWidget(sb)
    h.addLayout(col, 1)
    if widget is not None:
        h.addWidget(widget, 0, Qt.AlignVCenter)
    return row


def _set_divider() -> QFrame:
    """خط جداکنندهٔ ظریف بین ردیف‌های تنظیمات (مثل border-bottom اندروید)."""
    d = QFrame()
    d.setObjectName("setdivider")
    d.setFixedHeight(1)
    return d


def _clear_layout(lay) -> None:
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if w is not None:
            w.deleteLater()
        elif it.layout() is not None:
            _clear_layout(it.layout())


# ══════════════════════════════════════════════════════════════
#  ریشهٔ شیشه‌ای
# ══════════════════════════════════════════════════════════════
class GlassRoot(QWidget):
    """پس‌زمینهٔ محو + لایهٔ شیشه را خودش می‌کشد (بدون هیچ اثر گرافیکی)."""

    def __init__(self, t=T, parent=None):
        super().__init__(parent)
        self.setObjectName("app")
        self._t = t
        self._pm: QPixmap | None = None
        self._pm_size = QSize()

    def paintEvent(self, ev) -> None:      # noqa: N802
        p = QPainter(self)
        if self._pm is None or self._pm_size != self.size():
            self._pm = render_backdrop(self.size(), self._t)
            self._pm_size = self.size()
        p.drawPixmap(0, 0, self._pm)
        paint_glass(p, self.rect().adjusted(10, 10, -10, -10), self._t, radius=30)
        p.end()


# ══════════════════════════════════════════════════════════════
#  پنجرهٔ اصلی
# ══════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    (TAB_DASH, TAB_SIGNAL, TAB_REPORT, TAB_FUND, TAB_BRIEF,
     TAB_LOG, TAB_JOURNAL, TAB_SETTINGS) = range(8)

    def __init__(self, show_splash: bool = True):
        super().__init__()

        # دروازهٔ لایسنس (v0.14.0) — عمداً «بعد از» super().__init__():
        # در v0.14.0 اولیه اینجا قبل از ساخت آبجکت پایه بود و دیالوگ فعال‌سازی
        # با والدِ ساخته‌نشده، روی هر ماشین بدون لایسنس کرش می‌کرد
        # (RuntimeError: libshiboken). در حالت تست/توسعه خودِ
        # check_and_enforce_license بی‌اثر می‌شود (ODIN_SKIP_LICENSE=1 یا offscreen).
        license_ok, _license_msg = check_and_enforce_license()
        if not license_ok:
            if not self._show_activation_dialog():
                sys.exit(1)

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
                            on_journal=lambda r: self.q.put(("journal", r)),
                            cfg_provider=load_config,
                            on_alert=lambda lst: self.q.put(("alert", lst)),
                            on_signal_card=lambda lst: self.q.put(("signal_card", lst)))
        self._last_signals: list = []
        self._sig_popup = None
        self._chart_dialog = None
        self._alerts_dialog = None
        self._sig_signature = ""
        self._ev_signature = ""
        self._last_ranking = None
        self._build_ui()
        self._load_tg_fields()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_queue)
        self.timer.start(300)
        self.tick = QTimer(self)
        self.tick.timeout.connect(self._tick)
        self.tick.start(1000)

        # v0.19.0 — tray: بستن پنجره = رفتن به پس‌زمینه (حلقه/هشدارها زنده می‌مانند)
        self._force_quit = False
        self._tray_hint_shown = False
        self._init_tray()

        # v0.15.0 — وضعیت دسترسی در لاگ پنل شفاف باشد (لایسنس یا تریال)
        try:
            if not is_activated():
                _t = trial_status()
                if _t.get("active"):
                    self.q.put(("log", f"دورهٔ آزمایشی — {_t['days_left']} روز باقی است؛ پس از پایان، کلید لایسنس وارد کنید"))
                elif _t.get("exists") and not _t.get("tampered"):
                    self.q.put(("log", "دورهٔ آزمایشی تمام شده — برای ادامه، کلید لایسنس وارد کنید"))
        except Exception:
            pass

        self._splash = None
        if show_splash and bool(uicfg.get("splash", True)):
            self._show_splash()
        else:
            self._after_splash()

    # ── Splash ────────────────────────────────────────────────
    def _show_splash(self) -> None:
        try:
            self._splash = WelcomeSplash(user_name=self.user_name,
                                         version=app_paths.APP_VERSION,
                                         app_name=app_paths.APP_NAME,
                                         tagline="دستیار تحلیل و سیگنال فارکس",
                                         t=T, hold_ms=1500)
            self._splash.show_and_run(self._after_splash)
        except Exception:
            self._splash = None
            self._after_splash()

    def _after_splash(self) -> None:
        self.show()
        self.raise_()
        effects.fade(self.centralWidget(), 0.0, 1.0, effects.DUR_SLOW)
        self._log(f"👋 خوش اومدی {self.user_name}! دکمهٔ «شروع ربات» را بزن.")
        self._log("💡 برای دریافت گزارش‌ها روی گوشی، از «تنظیمات» تلگرام را وصل کن.")

    # ── ساخت ──────────────────────────────────────────────────
    def _build_ui(self) -> None:
        self.setWindowTitle(f"{app_paths.APP_NAME} — {app_paths.APP_VERSION}")
        self.resize(1280, 900)
        self.setMinimumSize(1020, 700)
        ico = app_paths.bundled_dir() / "assets" / "icon.ico"
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))
        dwm.apply_win11(self)

        root_widget = GlassRoot(T)
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(Space.XL + 8, Space.LG + 6, Space.XL + 8, Space.LG + 6)
        root.setSpacing(Space.LG)

        root.addLayout(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(Space.LG)
        body.addWidget(self._build_nav())
        body.addWidget(self._build_pages(), 1)
        root.addLayout(body, 1)

        self.setCentralWidget(root_widget)
        self.toast = Toast(root_widget, t=T)
        self.toast.hide()

    def _build_header(self) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(Space.MD)

        txt = QVBoxLayout()
        txt.setSpacing(2)
        self.greet_lbl = QLabel(f"سلام {self.user_name}!")
        self.greet_lbl.setObjectName("greet")
        sub = QLabel("دستیار تحلیل و سیگنال فارکس — تحلیل، فاندامنتال، اخبار → داور")
        sub.setObjectName("appsub")
        txt.addWidget(self.greet_lbl)
        txt.addWidget(sub)
        h.addLayout(txt)
        h.addStretch(1)

        # اقدام اصلی = پیِل مشکی
        self.btn_start = _btn("شروع ربات", "primary", "play", "شروع تحلیل خودکار")
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop = _circle("stop", "توقف حلقهٔ خودکار")
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_once = _circle("refresh", "همین حالا یک چرخه تحلیل")
        self.btn_once.clicked.connect(self._on_once)
        self.btn_brief = _circle("sunrise", "بریفینگ صبحگاهی")
        self.btn_brief.clicked.connect(self._on_briefing)
        self.btn_live = _circle("live", "گزارش زنده")
        self.btn_live.clicked.connect(lambda: self.nav._select(self.TAB_LOG))   # noqa: SLF001
        self.btn_alerts = _circle("bell", "هشدارهای قیمت")
        self.btn_alerts.clicked.connect(self._open_alerts)
        self.btn_chart = _circle("chart", "نمودار کندل‌استیک")
        self.btn_chart.clicked.connect(lambda: self._open_chart())
        self.avatar = QLabel()
        self.avatar.setFixedSize(40, 40)
        self.avatar.setStyleSheet(
            f"background:{T.ink_card}; border-radius:20px; color:{T.on_ink}; "
            f"font-weight:800; font-size:15px;")
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setText(self.user_name[:1] if self.user_name else "•")
        self.clock_lbl = QLabel("")
        self.clock_lbl.setObjectName("clock")

        h.addWidget(self.btn_start)
        h.addWidget(self.btn_stop)
        h.addWidget(self.btn_once)
        h.addWidget(self.btn_brief)
        h.addWidget(self.btn_live)
        h.addWidget(self.btn_alerts)
        h.addWidget(self.btn_chart)
        h.addWidget(self.clock_lbl)
        h.addWidget(self.avatar)
        return h

    def _build_nav(self) -> NavRail:
        self.nav = NavRail(self, t=T)
        self.nav.setFixedWidth(212)
        self.nav.add_section("منو")
        self.nav.add_item("dash", "داشبورد", "dashboard")
        self.nav.add_item("signals", "سیگنال‌ها", "target")
        self.nav.add_item("report", "گزارش کامل", "report")
        self.nav.add_item("fund", "تقویم و اخبار", "calendar")
        self.nav.add_item("brief", "بریفینگ", "sunrise")
        self.nav.add_stretch(1)
        self.nav.add_section("سیستم")
        self.nav.add_item("live", "گزارش زنده", "live")
        self.nav.add_item("journal", "کارنامه", "chart")
        self.nav.add_item("settings", "تنظیمات", "settings")
        self.nav.activated.connect(self._on_nav)
        return self.nav

    def _build_pages(self) -> QStackedWidget:
        self.pages = QStackedWidget()
        self.pages.setObjectName("pages")
        for w in (self._page_dash(), self._page_signals(), self._page_report(),
                  self._page_fund(), self._page_brief(), self._page_live(),
                  self._page_journal(), self._page_settings()):
            if w.objectName() != "pagescroll":      # داشبورد خودش نام دارد
                w.setObjectName("page")
            self.pages.addWidget(w)
        return self.pages

    def _page_frame(self, title: str, sub: str) -> tuple:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(Space.XS, 0, Space.XS, Space.XS)
        lay.setSpacing(Space.LG)
        head = QVBoxLayout()
        head.setSpacing(2)
        ttl = QLabel(title)
        ttl.setObjectName("pagetitle")
        sb = QLabel(sub)
        sb.setObjectName("pagesub")
        head.addWidget(ttl)
        head.addWidget(sb)
        lay.addLayout(head)
        return w, lay

    # ── داشبورد ───────────────────────────────────────────────
    def _page_dash(self) -> QWidget:
        w, lay = self._page_frame("داشبورد", "نمای کلی ربات، سیگنال‌ها و رویدادهای پیش‌رو")

        # ردیف ۱: کارت مشکی نمای کلی | نمودار خطی | حلقه
        row1 = QHBoxLayout()
        row1.setSpacing(Space.LG)

        hero = InkCard("نمای کلی", "", t=T)
        htop = QHBoxLayout()
        self.status_pill = StatusPill(t=T, onink=True)
        htop.addWidget(self.status_pill)
        htop.addStretch(1)
        self.last_run_lbl = QLabel("—")
        self.last_run_lbl.setObjectName("ink_cap")
        self.last_run_lbl.setStyleSheet(_INK_CAP)
        htop.addWidget(self.last_run_lbl)
        hero.add_layout(htop)
        nums = QHBoxLayout()
        nums.setSpacing(Space.XL)
        n1 = QVBoxLayout()
        self.hero_signals = QLabel("۰")
        self.hero_signals.setObjectName("ink_num")
        self.hero_signals.setStyleSheet(_INK_TITLE)
        c1 = QLabel("سیگنال کل")
        c1.setObjectName("ink_cap")
        c1.setStyleSheet(_INK_CAP)
        n1.addWidget(self.hero_signals)
        n1.addWidget(c1)
        n2 = QVBoxLayout()
        self.hero_veto = QLabel("۰")
        self.hero_veto.setObjectName("ink_num")
        self.hero_veto.setStyleSheet(_INK_TITLE)
        c2 = QLabel("وتوی فعال")
        c2.setObjectName("ink_cap")
        c2.setStyleSheet(_INK_CAP)
        n2.addWidget(self.hero_veto)
        n2.addWidget(c2)
        nums.addLayout(n1)
        nums.addLayout(n2)
        nums.addStretch(1)
        hero.add_layout(nums)
        self.veto_lbl = QLabel("")
        self.veto_lbl.setObjectName("ink_sub")
        self.veto_lbl.setStyleSheet(_INK_CAP)
        self.veto_lbl.setWordWrap(True)
        hero.add_widget(self.veto_lbl)
        tiles = QHBoxLayout()
        tiles.setSpacing(Space.SM)
        self.st_signals = StatTile("سیگنال این چرخه", "—", "", "", t=T)
        self.st_score = StatTile("بیشترین امتیاز", "—", "", "", t=T)
        self.st_news = StatTile("خبرهای رصدشده", "—", "", "", t=T)
        for s in (self.st_signals, self.st_score, self.st_news):
            tiles.addWidget(s, 1)
        hero.add_layout(tiles)
        row1.addWidget(hero, 5)

        chart_card = Card("جریان قدرت ارزها", "تغییر ۲۴ ساعت اخیر — قوی‌تر به ضعیف‌تر",
                          "chart", t=T)
        self.chart = LineChart(t=T)
        chart_card.add_widget(self.chart, 1)
        row1.addWidget(chart_card, 4)

        ring_card = Card("آمادگی سیگنال", "بهترین امتیاز این چرخه از ۱۱", "target", t=T)
        rlay = QVBoxLayout()
        rlay.setSpacing(Space.MD)
        self.ring = RingGauge(t=T, value=0.0)
        rlay.addWidget(self.ring, 0, Qt.AlignHCenter)
        self.ring_note = QLabel("هنوز سیگنالی نیست")
        self.ring_note.setObjectName("cardsub")
        self.ring_note.setWordWrap(True)
        self.ring_note.setAlignment(Qt.AlignCenter)
        rlay.addWidget(self.ring_note)
        rlay.addStretch(1)
        ring_card.add_layout(rlay, 1)
        row1.addWidget(ring_card, 3)
        lay.addLayout(row1)

        # ردیف ۲: سیگنال‌های اخیر (کارت‌های سفید + خط‌چین) | چک‌لیست موتورها
        row2 = QHBoxLayout()
        row2.setSpacing(Space.LG)
        sig_wrap = Card("سیگنال‌های اخیر", "", "target", t=T)
        sig_row = QHBoxLayout()
        sig_row.setSpacing(Space.MD)
        self.sig_cards_lay = QHBoxLayout()      # فقط کارت‌ها؛ با refresh پاک می‌شود
        self.sig_cards_lay.setSpacing(Space.MD)
        sig_row.addLayout(self.sig_cards_lay, 3)
        self.dashed = DashedCard("منتظر سیگنال بعدی", t=T)
        sig_row.addWidget(self.dashed, 2)       # بیرون از layoutِ پاک‌شونده
        sig_wrap.add_layout(sig_row, 1)
        row2.addWidget(sig_wrap, 7)

        goals = Card("وضعیت موتورها", "", "check", t=T)
        self.goals_lay = QVBoxLayout()
        self.goals_lay.setSpacing(Space.SM)
        self.goal_checks: dict[str, QCheckBox] = {}
        for key, label in (("cal", "تقویم اقتصادی"), ("news", "موتور اخبار"),
                           ("judge", "داور امتیازدهی"), ("tg", "اتصال تلگرام")):
            cb = QCheckBox(label)
            cb.setEnabled(False)
            self.goal_checks[key] = cb
            self.goals_lay.addWidget(cb)
        goals.add_layout(self.goals_lay, 1)
        row2.addWidget(goals, 3)
        lay.addLayout(row2)

        # ردیف ۳: رویدادهای پیش‌رو به‌شکل کارت‌های مشکی
        ev_title = QLabel("رویدادهای پیش‌رو")
        ev_title.setObjectName("sectiontitle")
        lay.addWidget(ev_title)
        self.ev_cards_lay = QHBoxLayout()
        self.ev_cards_lay.setSpacing(Space.LG)
        self.ev_cards_lay.addStretch(1)
        lay.addLayout(self.ev_cards_lay)
        lay.addStretch(1)

        # ظرف اسکرول: در پنجره‌های کوچک‌تر یا مقیاس‌دهی DPI ویندوز، محتوا به‌جای
        # فشرده‌شدن/سرریز از کارت‌ها، عمودی اسکرول می‌شود (افقی هرگز).
        w.setObjectName("page")
        scroll = QScrollArea()
        scroll.setObjectName("pagescroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(w)
        return scroll

    # ── سایر صفحه‌ها ──────────────────────────────────────────
    def _page_signals(self) -> QWidget:
        w, lay = self._page_frame("سیگنال‌ها", "سیگنال‌های صادرشده با دلایل کامل")
        bar = QHBoxLayout()
        self.btn_share_sig = _btn("اشتراک تصویر آخرین سیگنال", "", "send",
                                  "کارت تصویری برند (۱۰۸۰×۱۳۵۰) — ذخیره در گالری + کلیپ‌بورد")
        self.btn_share_sig.clicked.connect(self._share_last_signal)
        bar.addWidget(self.btn_share_sig)
        bar.addStretch(1)
        lay.addLayout(bar)
        self.sig_view = _plain(None, "هنوز سیگنالی صادر نشده.\n"
                               "داور فقط وقتی سیگنال می‌دهد که هیچ وتویی فعال نباشد "
                               "و امتیاز ≥ ۷ از ۱۱ شود.")
        lay.addWidget(self.sig_view, 1)
        return w

    def _page_report(self) -> QWidget:
        w, lay = self._page_frame("گزارش کامل", "تحلیل تکنیکال + تاییدیه + تقویم + اخبار + داور")
        self.report_view = _plain(None, "هنوز گزارشی نیست — «تحلیل یک‌بار» را بزن.")
        lay.addWidget(self.report_view, 1)
        return w

    def _page_fund(self) -> QWidget:
        w, lay = self._page_frame("تقویم و اخبار", "موتور فاندامنتال و رصد اخبار")
        self.fund_view = _plain(None, "هنوز داده‌ای نیست.")
        lay.addWidget(self.fund_view, 1)
        return w

    def _page_brief(self) -> QWidget:
        w, lay = self._page_frame("بریفینگ صبحگاهی", "خلاصهٔ روز قبل از باز شدن لندن")
        self.brief_view = _plain(None, "بریفینگ هنوز ساخته نشده.")
        lay.addWidget(self.brief_view, 1)
        return w

    def _page_live(self) -> QWidget:
        w, lay = self._page_frame("گزارش زنده", "رویدادها لحظه‌به‌لحظه")
        self.log_view = _plain(4000, "رویدادی ثبت نشده.")
        lay.addWidget(self.log_view, 1)
        return w

    def _page_journal(self) -> QWidget:
        w, lay = self._page_frame("کارنامه", "دقت واقعی سیستم — حلقهٔ صداقت")

        bar = QHBoxLayout()
        bar.addStretch(1)
        self.btn_journal = _btn("به‌روزرسانی کارنامه", "ghost", "refresh",
                                "همین حالا کارنامه را بازسازی کن")
        self.btn_journal.clicked.connect(self._on_journal)
        bar.addWidget(self.btn_journal)
        lay.addLayout(bar)

        self.journal_view = _plain(None,
                                   "هنوز کارنامه‌ای نیست.\n"
                                   "با اولین سیگنالِ بسته‌شده، آمار دقت اینجا ساخته می‌شود.")
        lay.addWidget(self.journal_view, 1)
        return w

    def _page_settings(self) -> QWidget:
        w, lay = self._page_frame(
            "تنظیمات",
            "نام نمایشی، داور، وتوها، موتورها، حلقه و ظاهر — تغییرها فوری ذخیره "
            "می‌شوند و در تحلیل بعدی اثر می‌کنند")

        self._set_guard = False
        self.set_switches: dict[str, ToggleSwitch] = {}
        self.set_steppers: dict[str, Stepper] = {}

        def sw(key: str) -> ToggleSwitch:
            s = ToggleSwitch(t=T)
            s.toggled.connect(self._on_setting_changed)
            self.set_switches[key] = s
            return s

        def step(key: str, lo: int, hi: int, st: int = 1, unit: str = "") -> Stepper:
            sp = Stepper(lo, hi, step=st, unit=unit, t=T)
            sp.valueChanged.connect(self._on_setting_changed)
            self.set_steppers[key] = sp
            return sp

        def rows_into(card: Card, rows: list) -> None:
            for i, r in enumerate(rows):
                if i:
                    card.add_widget(_set_divider())
                card.add_widget(r)

        # ── شخصی‌سازی (آینهٔ «👤 شخصی» اندروید) ─────────────────
        prof = Card("شخصی‌سازی", "", "user", t=T)
        rows_into(prof, [
            _set_row("نام نمایشی",
                     "در خوش‌آمدگویی، هدر و Splash استفاده می‌شود — فوری اعمال می‌شود"),
        ])
        self.set_name = QLineEdit()
        self.set_name.setMaxLength(24)
        self.set_name.setPlaceholderText("مثلاً سوشیان")
        self.set_name.editingFinished.connect(self._on_name_edited)
        prof.add_widget(self.set_name)
        lay.addWidget(prof)

        # ── داور امتیازدهی (آینهٔ اندروید + سقف سیگنال) ─────────
        judge = Card("داور امتیازدهی", "", "target", t=T)
        rows_into(judge, [
            _set_row("داور فعال است",
                     "خاموش = هیچ سیگنالی داوری/صادر نمی‌شود",
                     sw("judge_enabled")),
            _set_row("آستانهٔ صدور سیگنال",
                     "حداکثر ممکن ۱۱ امتیاز است — پیش‌فرض ۷",
                     step("min_score", 4, 10)),
            _set_row("حداکثر سیگنال در هر چرخه",
                     "جلوگیری از رگبار سیگنال — پیش‌فرض ۳",
                     step("max_signals_per_cycle", 1, 5)),
        ])
        lay.addWidget(judge)

        # ── دروازه‌های وتو (آینهٔ اندروید) ───────────────────────
        veto = Card("دروازه‌های وتو",
                    "وتوها بدون استثنا هستند: حتی با امتیاز کامل، سیگنال صادر نمی‌شود.",
                    "shield", t=T)
        rows_into(veto, [
            _set_row("بازار بسته", "شنبه/یکشنبه و جمعه بعد از ۲۱ UTC",
                     sw("veto.weekend")),
            _set_row("رویداد پراثر تقویم", "رویداد پراثر تا ۳۰ دقیقهٔ آینده",
                     sw("veto.high_impact_event")),
            _set_row("تضاد تایم‌فریم", "H4 و H1 هم‌جهت نباشند",
                     sw("veto.timeframe_conflict")),
            _set_row("بازار بی‌روند", "ADX زیر آستانهٔ ۲۰",
                     sw("veto.range_market")),
            _set_row("جهش غیرعادی نوسان", "ATR فعلی بیش از ۲ برابر میانگین",
                     sw("veto.volatility_spike")),
            _set_row("خبر فوری", "خبر فوریِ مرتبط با نماد",
                     sw("veto.breaking_news")),
        ])
        lay.addWidget(veto)

        # ── موتورها (آینهٔ اندروید + هشدار رویداد) ───────────────
        eng = Card("موتورها", "", "zap", t=T)
        rows_into(eng, [
            _set_row("تقویم اقتصادی", "ForexFactory — کش ۳۰ دقیقه‌ای",
                     sw("fund_enabled")),
            _set_row("هشدار رویداد نزدیک",
                     "اعلان تلگرامی کمی قبل از رویدادهای پراثر (بدون تکرار)",
                     sw("alerts_enabled")),
            _set_row("موتور اخبار", "RSS فارکس — دریافت زنده در هر تحلیل",
                     sw("news_enabled")),
            _set_row("تأییدیهٔ تریدینگ‌ویو",
                     "API غیررسمی — اگر قطع باشد، آن مدرک «ناموجود» می‌گیرد",
                     sw("tv_enabled")),
        ])
        lay.addWidget(eng)

        # ── حلقهٔ خودکار و گزارش‌ها (بیشتر از اندروید) ────────────
        loopc = Card("حلقهٔ خودکار و گزارش‌ها", "", "clock", t=T)
        rows_into(loopc, [
            _set_row("فاصلهٔ تحلیل خودکار",
                     "بین ۵ تا ۱۲۰ دقیقه — از چرخهٔ بعد اعمال می‌شود",
                     step("interval_minutes", 5, 120, 5, "دقیقه")),
            _set_row("بریفینگ صبحگاهی",
                     "گزارش روزانه در ساعت مقرر (بر پایهٔ UTC) ساخته و ارسال شود",
                     sw("briefing_enabled")),
            _set_row("کارنامه (ژورنال)",
                     "ثبت سیگنال‌ها و پیگیری خودکار نتایج روی کندل‌های M15",
                     sw("journal_enabled")),
            _set_row("قانون محافظه‌کارانهٔ «هر دو لمس»",
                     "در یک کندل هم TP و هم SL لمس شود → شکست حساب می‌شود",
                     sw("both_touch")),
        ])
        lay.addWidget(loopc)

        # ── ظاهر ─────────────────────────────────────────────────
        appear = Card("ظاهر", "", "eye", t=T)
        rows_into(appear, [
            _set_row("صفحهٔ خوش‌آمدگویی",
                     "هنگام شروع برنامه — از اجرای بعدی اعمال می‌شود",
                     sw("splash")),
            _set_row("انیمیشن‌ها", "محو شدن صفحه‌ها و حرکت ظریف اجزا",
                     sw("animations")),
        ])
        lay.addWidget(appear)

        # ── تلگرام ───────────────────────────────────────────────
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

        # ── داده‌ها (آینهٔ «🗄️ داده‌ها» اندروید) ──────────────────
        data = Card("داده‌ها", "", "refresh", t=T)
        self.btn_clear_cache = _btn("پاک‌کردن", "ghost", "refresh",
                                    "کش تقویم اقتصادی را پاک کن")
        self.btn_clear_cache.clicked.connect(self._on_clear_cache)
        self.btn_reset_settings = _btn("بازنشانی", "ghost", "alert",
                                       "همهٔ تنظیمات پنل به حالت پیش‌فرض")
        self.btn_reset_settings.clicked.connect(self._on_reset_settings)
        rows_into(data, [
            _set_row("پاک‌کردن کش تقویم اقتصادی",
                     "دادهٔ بازار و اخبار همیشه تازه دریافت می‌شوند؛ کش فقط برای تقویم است",
                     self.btn_clear_cache),
            _set_row("بازنشانی همهٔ تنظیمات",
                     "به حالت پیش‌فرض برمی‌گردند — تلگرام، ژورنال و سیگنال‌ها پاک نمی‌شوند",
                     self.btn_reset_settings),
        ])
        dnote = QLabel("این تنظیمات در config.local.yaml داخل پوشهٔ داده‌ها ذخیره می‌شوند "
                       "(بیرون از گیت) و بر config.yaml اولویت دارند — آینهٔ رفتار نسخهٔ اندروید.")
        dnote.setObjectName("hint"); dnote.setWordWrap(True)
        data.add_widget(dnote)
        lay.addWidget(data)

        # ── فایل‌ها ──────────────────────────────────────────────
        files = Card("فایل‌ها", "", "folder", t=T)
        fl = QHBoxLayout(); fl.setSpacing(Space.SM)
        self.btn_cfg = _btn("بازکردن config.yaml", "ghost", "file_cfg")
        self.btn_cfg.clicked.connect(lambda: self._open_path(app_paths.config_path()))
        self.btn_logs = _btn("پوشهٔ لاگ‌ها", "ghost", "folder")
        self.btn_logs.clicked.connect(lambda: self._open_path(app_paths.logs_dir()))
        self.btn_data = _btn("پوشهٔ داده‌ها", "ghost", "folder")
        self.btn_data.clicked.connect(lambda: self._open_path(app_paths.data_dir()))
        fl.addWidget(self.btn_cfg); fl.addWidget(self.btn_logs)
        fl.addWidget(self.btn_data); fl.addStretch(1)
        files.add_layout(fl)
        note = QLabel("توکن و شناسهٔ تلگرام در config.local.yaml داخل پوشهٔ داده‌ها "
                      "ذخیره می‌شوند و هرگز به گیت‌هاب نمی‌روند.")
        note.setObjectName("hint"); note.setWordWrap(True)
        files.add_widget(note)
        dpath = QLabel(str(app_paths.data_dir()))
        dpath.setObjectName("hint"); dpath.setWordWrap(True)
        dpath.setTextInteractionFlags(Qt.TextSelectableByMouse)
        files.add_widget(dpath)
        lay.addWidget(files)

        # ── درباره ───────────────────────────────────────────────
        about = Card("درباره", "", "info", t=T)
        av = QLabel(f"{app_paths.APP_NAME} — نسخه {fa(app_paths.APP_VERSION)}  ·  "
                    f"تم روشن شیشه‌ای مونوکروم  ·  طراحی Fluent/2026\n"
                    "این ابزار فقط تحلیل و سیگنال می‌دهد و هیچ معامله‌ای انجام نمی‌دهد؛ "
                    "تصمیم نهایی با شماست.")
        av.setObjectName("label"); av.setWordWrap(True)
        about.add_widget(av)
        lay.addWidget(about)

        self._load_settings_fields()
        lay.addStretch(1)

        # ظرف اسکرول: صفحهٔ تنظیمات حالا بلند است؛ در پنجره‌های کوچک/مقیاس
        # DPI مثل داشبورد عمودی اسکرول می‌شود (افقی هرگز).
        w.setObjectName("page")
        scroll = QScrollArea()
        scroll.setObjectName("pagescroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(w)
        return scroll

    # ── ناوبری ────────────────────────────────────────────────
    def _on_nav(self, i: int) -> None:
        if i == self.TAB_SETTINGS:
            # config ممکن است بیرون برنامه ویرایش شده باشد؛ هنگام بازکردن
            # صفحهٔ تنظیمات دوباره خوانده می‌شود تا مقادیر کهنه نمایش داده نشود.
            try:
                self.cfg = load_config()
                self._load_tg_fields()
                self._load_settings_fields()
            except Exception as e:
                self._log(f"[!] بازخوانی تنظیمات ناموفق: {e}")
        self.pages.setCurrentIndex(i)
        page = self.pages.currentWidget()
        page.update()
        effects.fade(page, 0.0, 1.0, effects.DUR_MED)

    # ── صف ────────────────────────────────────────────────────
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
            try:
                b.setProperty("badge", "false")
                b.style().unpolish(b); b.style().polish(b)
            except RuntimeError:
                pass
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
            elif kind == "journal":
                self._fill(self.journal_view, payload, self.TAB_JOURNAL, "کارنامه")
            elif kind == "alert":
                self._on_price_alerts(payload)
            elif kind == "signal_card":
                self._last_signals = payload or []
                self._show_signal_popup(self._last_signals)
            elif kind == "tg_msg":
                # از thread ورکر تلگرام فقط به صف می‌آید؛ دست‌زدن به ویجت از
                # thread غیر-GUI در Qt تعریف‌نشده/کرش‌خیز است.
                self.tg_status.setText(payload)
            elif kind == "tg_chat":
                self.tg_chat.setText(payload)
                self._save_tg_fields()

    def _toast_signal(self, text: str) -> None:
        first = next((l for l in text.splitlines() if "سیگنال" in l), "سیگنال جدید")
        self.toast.show_message(first.strip(), "برای جزئیات و دلایل، تب «سیگنال‌ها» را ببین",
                                "target")

    def _log(self, msg: str) -> None:
        self.log_view.appendPlainText(msg)

    # ── tray + پس‌زمینه (v0.19.0) ─────────────────────────────
    def _init_tray(self) -> None:
        self.tray = None
        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
            ico = Path(__file__).resolve().parent / "assets" / "icon.png"
            icon = QIcon(str(ico)) if ico.exists() else self.windowIcon()
            self.tray = QSystemTrayIcon(icon, self)
            menu = QMenu()
            a = menu.addAction("بازکردن ODIN ASSISTANT")
            a.triggered.connect(self._tray_show)
            a2 = menu.addAction("تحلیل همین حالا")
            a2.triggered.connect(self._on_once)
            menu.addSeparator()
            a3 = menu.addAction("هشدارهای قیمت…")
            a3.triggered.connect(self._open_alerts)
            a4 = menu.addAction("نمودار کندل‌استیک…")
            a4.triggered.connect(lambda: self._open_chart())
            menu.addSeparator()
            a5 = menu.addAction("خروج")
            a5.triggered.connect(self._quit_force)
            self.tray.setContextMenu(menu)
            self.tray.setToolTip("ODIN ASSISTANT — دستیار تحلیل و سیگنال")
            self.tray.activated.connect(self._tray_activated)
            self.tray.show()
        except Exception:
            self.tray = None

    def _tray_activated(self, reason) -> None:
        try:
            if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
                self._tray_show()
        except Exception:
            pass

    def _tray_show(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_force(self) -> None:
        self._force_quit = True
        try:
            if self.tray is not None:
                self.tray.hide()
        except Exception:
            pass
        QApplication.quit()

    def closeEvent(self, event) -> None:
        close_to_tray = True
        try:
            close_to_tray = bool((self.cfg.get("ui") or {}).get("close_to_tray", True))
        except Exception:
            pass
        if self.tray is not None and close_to_tray and not self._force_quit:
            event.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                try:
                    self.tray.showMessage(
                        "ODIN ASSISTANT در پس‌زمینه فعال است",
                        "حلقهٔ تحلیل، سیگنال‌ها و هشدارهای قیمت با اعلان ادامه دارند. "
                        "خروج کامل: منوی tray ← خروج",
                        QSystemTrayIcon.Information, 6000)
                except Exception:
                    pass
            return
        super().closeEvent(event)

    # ── اعلان‌های زیبا به‌جای خروجی ترمینالی (v0.19.0) ─────────
    def _on_price_alerts(self, fired: list) -> None:
        try:
            lines = []
            for f in (fired or [])[:3]:
                d = "بالاتر از" if f.get("dir") == "above" else "پایین‌تر از"
                lines.append(f"{f['symbol']} به {f.get('_price')} رسید ({d} {f['price']})")
            title = f"هشدار قیمت — {len(fired or [])} مورد فعال شد"
            body = "\n".join(lines)
            self.toast.show_message(title, body, "bell")
            if self.tray is not None:
                try:
                    self.tray.showMessage(title, body, QSystemTrayIcon.Information, 8000)
                except Exception:
                    pass
        except Exception:
            pass

    def _show_signal_popup(self, sigs: list) -> None:
        """کارت سیگنال متحرک روی پنجره (همزاد کارت اندروید) — نه متن ترمینالی."""
        try:
            if not sigs:
                return
            from src.report.signal import fmt_price
            from src.fa import fa_num, jalali_fa, hhmm_teh

            sent = [x for x in sigs if x.get("sent")] or sigs
            sig = sent[0]
            extra = len(sigs) - 1
            if self._sig_popup is not None:
                try:
                    self._close_popup(self._sig_popup)
                except Exception:
                    pass

            buy = str(sig.get("direction", "")).upper().startswith("B")
            acc = T.green_text if buy else T.red_text
            acc_bg = T.green_tint if buy else T.red_tint
            pair = str(sig["symbol"])
            if len(pair) == 6:
                pair = pair[:3] + "/" + pair[3:]
            stars_n = max(0, min(5, int(sig.get("stars") or 0)))
            pip = float(sig.get("pip") or 0.0001)

            card = QFrame(self)
            card.setObjectName("sig_popup")
            card.setFixedSize(396, 272)
            card.setStyleSheet(
                "QFrame#sig_popup { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
                f" stop:0 #1A1A1F, stop:0.55 {T.ink_card}, stop:1 #0A0A0D);"
                " border-radius: 22px; }"
                " QFrame#sig_popup QLabel { color: #FFFFFF; background: transparent; }"
                f" QFrame#sig_popup QLabel#sp_dir {{ color: {acc}; background: {acc_bg};"
                " border-radius: 13px; padding: 4px 14px; font-weight: 800; font-size: 12px; }"
                f" QFrame#sig_popup QLabel#sp_tile {{ background: {T.ink_tile}; border-radius: 12px; }}"
                " QFrame#sig_popup QPushButton { background: rgba(255,255,255,.12); color:#fff;"
                " border:none; border-radius:11px; padding:7px 12px; font-weight:700; font-size:11px; }"
                " QFrame#sig_popup QPushButton:hover { background: rgba(255,255,255,.24); }")

            v = QVBoxLayout(card)
            v.setContentsMargins(18, 16, 18, 14)
            v.setSpacing(7)

            row1 = QHBoxLayout()
            dir_lbl = QLabel("سیگنال خرید" if buy else "سیگنال فروش")
            dir_lbl.setObjectName("sp_dir")
            row1.addWidget(dir_lbl)
            row1.addStretch(1)
            if extra > 0:
                cap = QLabel("+" + fa_num(extra) + " سیگنال دیگر")
                cap.setStyleSheet("color:rgba(255,255,255,.5);font-size:10px")
                row1.addWidget(cap)
            close_b = QPushButton("✕")
            close_b.setFixedSize(26, 26)
            close_b.clicked.connect(lambda: self._close_popup(card))
            row1.addWidget(close_b)
            v.addLayout(row1)

            pair_lbl = QLabel(pair)
            pair_lbl.setStyleSheet("font-size:23px;font-weight:800;direction:ltr")
            v.addWidget(pair_lbl)

            meta = QLabel(f"{sig.get('fa_name', '')}  ·  امتیاز {fa_num(sig.get('score', 0))}"
                          f" از {fa_num(sig.get('max_score', 11))}  ·  "
                          + "★" * stars_n + "☆" * (5 - stars_n))
            meta.setStyleSheet("color:rgba(255,255,255,.62);font-size:11px")
            v.addWidget(meta)

            tiles = QHBoxLayout()
            tiles.setSpacing(8)
            for cap_t, val, col in (("ورود", fmt_price(float(sig["entry"]), pip), "#FFFFFF"),
                                    ("حد ضرر", fmt_price(float(sig["sl"]), pip), "#FF9A9A"),
                                    ("هدف", fmt_price(float(sig["tp"]), pip), "#7BE0B0")):
                tl = QLabel("<div style='font-size:9px;color:rgba(255,255,255,.5)'>" + cap_t + "</div>"
                            "<div style='font-size:14px;font-weight:800;color:" + col +
                            ";direction:ltr'>" + val + "</div>")
                tl.setObjectName("sp_tile")
                tl.setAlignment(Qt.AlignCenter)
                tiles.addWidget(tl)
            v.addLayout(tiles)

            when = QLabel("")
            try:
                _now = sig.get("now")
                if isinstance(_now, str):
                    _now = datetime.fromisoformat(_now)
                if _now is not None:
                    if _now.tzinfo is None:
                        from datetime import timezone as _tz
                        _now = _now.replace(tzinfo=_tz.utc)
                    when.setText(jalali_fa(_now) + "  ·  ساعت " + fa_num(hhmm_teh(_now)) + " تهران")
            except Exception:
                pass
            when.setStyleSheet("color:rgba(255,255,255,.5);font-size:10px")
            v.addWidget(when)
            v.addStretch(1)

            btns = QHBoxLayout()
            btns.setSpacing(8)
            b_chart = QPushButton("نمودار")
            b_share = QPushButton("اشتراک تصویر")
            b_det = QPushButton("جزئیات")
            b_chart.clicked.connect(lambda _s=sig: self._open_chart_for_signal(_s))
            b_share.clicked.connect(lambda _s=sig: self._share_signal(_s))
            b_det.clicked.connect(lambda c=card: (self._close_popup(c),
                                                  self.nav._select(self.TAB_SIGNAL)))  # noqa: SLF001
            btns.addWidget(b_chart)
            btns.addWidget(b_share)
            btns.addWidget(b_det)
            v.addLayout(btns)

            x = max(12, self.width() - card.width() - 18)
            y = max(60, self.height() - card.height() - 66)
            card.move(x, y)
            card.show()
            card.raise_()
            try:
                effects.fade(card, 0.0, 1.0, effects.DUR_MED)
                effects.rise(card, dy=18, ms=getattr(effects, "DUR_MED", 260))
            except Exception:
                pass
            self._sig_popup = card
            QTimer.singleShot(24000, lambda c=card: self._close_popup(c))
            if self.tray is not None:
                try:
                    self.tray.showMessage(
                        ("سیگنال خرید — " if buy else "سیگنال فروش — ") + pair,
                        "ورود " + fmt_price(float(sig["entry"]), pip) +
                        " · حد ضرر " + fmt_price(float(sig["sl"]), pip) +
                        " · هدف " + fmt_price(float(sig["tp"]), pip),
                        QSystemTrayIcon.Information, 8000)
                except Exception:
                    pass
        except Exception as e:
            self.q.put(("log", f"[!] کارت سیگنال ناموفق: {str(e)[:110]}"))

    def _close_popup(self, card) -> None:
        try:
            if self._sig_popup is card:
                self._sig_popup = None
            card.deleteLater()
        except Exception:
            pass

    def _sr_for(self, symbol: str):
        try:
            for row in (self.loop.state.get("symbols_summary") or []):
                if row.get("symbol") == symbol:
                    return row.get("support"), row.get("resistance")
        except Exception:
            pass
        return None, None

    def _open_chart_for_signal(self, sig: dict) -> None:
        lv = []
        try:
            lv = [(float(sig["entry"]), QColor(T.text), "ورود", False),
                  (float(sig["sl"]), QColor(T.red), "حد ضرر", True),
                  (float(sig["tp"]), QColor(T.green), "هدف", True)]
        except Exception:
            lv = []
        self._open_chart(symbol=sig.get("symbol"), levels=lv,
                         sr=self._sr_for(sig.get("symbol", "")))

    # ── اشتراک کارت تصویری سیگنال ────────────────────────────
    def _share_signal(self, sig: dict) -> None:
        try:
            from src.report.sharecard import build_share_spec, render_card_pixmap
            spec = build_share_spec(sig, version=app_paths.APP_VERSION)
            pm = render_card_pixmap(spec)
            pics = Path.home() / "Pictures" / "ODIN"
            try:
                pics.mkdir(parents=True, exist_ok=True)
            except Exception:
                pics = Path.home()
            fname = ("odin-signal-" + spec["pair"].replace("/", "") +
                     "-" + time.strftime("%Y%m%d-%H%M%S") + ".png")
            fpath = pics / fname
            pm.save(str(fpath), "PNG")
            try:
                QApplication.clipboard().setPixmap(pm)
            except Exception:
                pass
            self.toast.show_message(
                "کارت سیگنال ساخته شد",
                "در Pictures/ODIN ذخیره و در کلیپ‌بورد کپی شد — آمادهٔ اشتراک",
                "send")
            try:
                from PySide6.QtGui import QDesktopServices
                from PySide6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(pics)))
            except Exception:
                pass
        except Exception as e:
            self.toast.show_message("ساخت کارت ناموفق بود", str(e)[:120], "shield")

    def _share_last_signal(self) -> None:
        sigs = ([x for x in (self._last_signals or []) if x.get("sent")]
                or (self._last_signals or []))
        if not sigs:
            self.toast.show_message("سیگنالی برای اشتراک نیست",
                                    "پس از اولین سیگنالِ چرخه، این دکمه فعال می‌شود",
                                    "bell")
            return
        self._share_signal(sigs[0])

    # ── دیالوگ‌های هشدار قیمت و نمودار ────────────────────────
    def _open_alerts(self) -> None:
        try:
            if self._alerts_dialog is None:
                self._alerts_dialog = AlertsDialog(self)
            self._alerts_dialog.refresh()
            self._alerts_dialog.show()
            self._alerts_dialog.raise_()
            self._alerts_dialog.activateWindow()
        except Exception as e:
            self.toast.show_message("هشدارها باز نشد", str(e)[:100], "shield")

    def _open_chart(self, symbol: str = None, levels=None, sr=(None, None)) -> None:
        try:
            dlg = ChartDialog(self, symbol=symbol, levels=levels, sr=sr)
            self._chart_dialog = dlg
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
        except Exception as e:
            self.toast.show_message("نمودار باز نشد", str(e)[:100], "shield")

    # ── تیک ───────────────────────────────────────────────────
    def _tick(self) -> None:
        _set_text(self.clock_lbl, fa(time.strftime("%H:%M:%S")))
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
        _set_text(self.last_run_lbl, "آخرین تحلیل: " + (
            fa(time.strftime("%H:%M", time.localtime(last))) if last else "—"))
        vetoes = st.get("last_vetoes") or []
        _set_text(self.veto_lbl,
                  f"وتوی فعال: {'، '.join(vetoes)}" if vetoes
                  else ("وتوی فعالی نیست — پنجرهٔ صدور سیگنال باز است" if last else ""))
        _set_text(self.hero_signals, fa(int(st.get("signals_total") or 0)))
        _set_text(self.hero_veto, fa(len(vetoes)))

        self._refresh_dash(st)

    def _refresh_dash(self, st) -> None:
        sigs = st.get("last_signals") or []
        self.st_signals.set_value(fa(len(sigs)))
        best = max((x["score"] for x in sigs), default=None)
        self.st_score.set_value(fa(f"{best}/{sigs[0]['max_score']}") if best is not None else "—",
                                "green" if best is not None and best >= 7 else "")
        self.st_news.set_value(fa(st.get("news_count") or 0))

        # حلقه: بهترین امتیاز نسبت به ۱۱
        self.ring.set_value((best / 11.0) if best is not None else 0.0)
        _set_text(self.ring_note,
                  f"بهترین سیگنال این چرخه: {fa(best)} از ۱۱" if best is not None
                  else "هنوز سیگنالی در این چرخه صادر نشده")

        # نمودار خطی قدرت ارزها
        ranking = st.get("ranking") or []
        if ranking != self._last_ranking:
            self._last_ranking = ranking
            self.chart.set_data([v for _, v in ranking], [c for c, _ in ranking])

        # چک‌لیست موتورها
        tg = self.cfg.get("telegram") or {}
        states = {"cal": bool(st.get("calendar_ok")),
                  "news": bool(st.get("news_count")),
                  "judge": bool((self.cfg.get("judge") or {}).get("enabled", True)),
                  "tg": bool(str(tg.get("bot_token") or "").strip()
                             and str(tg.get("chat_id") or "").strip())}
        for k, cb in self.goal_checks.items():
            cb.setChecked(states[k])

        # کارت‌های سیگنال (بازسازی فقط با تغییر داده)
        sig_sig = "|".join(f"{x['symbol']}{x['direction']}{x['score']}{int(x.get('sent', 0))}"
                           for x in sigs)
        if sig_sig != self._sig_signature:
            self._sig_signature = sig_sig
            _clear_layout(self.sig_cards_lay)
            for x in sigs[:3]:
                c = Card(t=T, bordered=True)
                tl = QLabel(f"{x['symbol']}  " + ("خرید" if x["direction"] == "BUY" else "فروش"))
                tl.setObjectName("cardtitle")
                sc = QLabel(f"امتیاز {fa(x['score'])} از {fa(x['max_score'])}"
                            + ("" if x.get("sent") else "  ·  ارسال نشد"))
                sc.setObjectName("cardsub")
                dot = QLabel()
                dot.setFixedSize(34, 34)
                col = T.green_text if x["direction"] == "BUY" else T.red_text
                dot.setPixmap(icons.icon("trend_up" if x["direction"] == "BUY" else "trend_down",
                                         18, col).pixmap(34, 34))
                row = QHBoxLayout()
                row.addWidget(tl); row.addStretch(1); row.addWidget(dot)
                c.add_layout(row)
                c.add_widget(sc)
                self.sig_cards_lay.addWidget(c, 1)

        # کارت‌های رویداد پیش‌رو (مشکی)
        ups = st.get("upcoming") or []
        ev_sig = "|".join(f"{u['title_fa']}{u['minutes']}" for u in ups)
        if ev_sig != self._ev_signature:
            self._ev_signature = ev_sig
            _clear_layout(self.ev_cards_lay)
            if not ups:
                empty = QLabel("رویداد پراثر یا متوسطی در ۴۸ ساعت آینده نیست.")
                empty.setObjectName("sectionsub")
                self.ev_cards_lay.addWidget(empty)
            for u in ups[:3]:
                ic = InkCard(t=T)
                tl = QLabel(u["title_fa"])
                tl.setObjectName("ink_title")
                tl.setWordWrap(True)
                tl.setStyleSheet(_INK_TITLE)
                sb = QLabel(f"{u['country_fa']}  ·  {fa_countdown(u['minutes'])}")
                sb.setObjectName("ink_sub")
                sb.setWordWrap(True)
                sb.setStyleSheet(_INK_CAP)
                # نشانگر اثر: نقطهٔ نقاشی‌شده در کد به‌جای ایموجی (پالت + کراس‌پلتفرم)
                high = u["impact"] == "HIGH"
                imp_row = QHBoxLayout()
                imp_row.setSpacing(6)
                dot = QLabel()
                dot.setFixedSize(10, 10)
                dot.setPixmap(_dot_pixmap("#FF5D5D" if high
                                          else T.rgba("#FFFFFF", 0.45), 10))
                imp_row.addWidget(dot, 0, Qt.AlignVCenter)
                imp = QLabel("پراثر" if high else "متوسط")
                imp.setObjectName("ink_cap")
                imp.setStyleSheet("color: #FF9A9A;" if high
                                  else f"color: {T.rgba('#FFFFFF', 0.60)};")
                imp_row.addWidget(imp, 0, Qt.AlignVCenter)
                imp_row.addStretch(1)
                ic.add_widget(tl)
                ic.add_widget(sb)
                ic.add_layout(imp_row)
                self.ev_cards_lay.addWidget(ic, 1)

    # ── اقدام‌ها ──────────────────────────────────────────────
    def _on_start(self) -> None:
        self.loop.start()

    def _on_stop(self) -> None:
        self.loop.stop()

    def _on_once(self) -> None:
        if not self.loop.run_once_async():
            self._log("[i] یک تحلیل دیگر در جریان است — کمی صبر کن")

    def _on_journal(self) -> None:
        if not self.loop.run_journal_async():
            self._log("[i] یک کار دیگر در جریان است — کمی صبر کن")

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

    # ── تنظیمات پنل (آینهٔ نسخهٔ اندروید) ────────────────────────
    def _load_settings_fields(self) -> None:
        """ویجت‌های تنظیمات را از cfg پر کن — بدون برانگیختن ذخیره (guard)."""
        self._set_guard = True
        try:
            cfg = self.cfg
            u = cfg.get("ui") or {}
            j = cfg.get("judge") or {}
            v = j.get("veto") or {}
            f = cfg.get("fundamental") or {}
            n = cfg.get("news") or {}
            tv = cfg.get("tradingview") or {}
            lp = cfg.get("loop") or {}
            br = cfg.get("briefing") or {}
            jn = cfg.get("journal") or {}
            self.set_name.setText(str(u.get("user_name") or "سوشیان"))
            vals = {
                "judge_enabled": bool(j.get("enabled", True)),
                "fund_enabled": bool(f.get("enabled", True)),
                "alerts_enabled": bool(f.get("alerts_enabled", True)),
                "news_enabled": bool(n.get("enabled", True)),
                "tv_enabled": bool(tv.get("enabled", True)),
                "briefing_enabled": bool(br.get("enabled", True)),
                "journal_enabled": bool(jn.get("enabled", True)),
                "both_touch": bool(jn.get("conservative_both_touch", True)),
                "splash": bool(u.get("splash", True)),
                "animations": bool(u.get("animations", True)),
            }
            for k in VETO_KEYS:
                vals[f"veto.{k}"] = bool(v.get(k, True))
            for key, on in vals.items():
                s = self.set_switches.get(key)
                if s is not None:
                    s.setChecked(on)
            self.set_steppers["min_score"].setValue(
                int(j.get("min_score", 7)), silent=True)
            self.set_steppers["max_signals_per_cycle"].setValue(
                int(j.get("max_signals_per_cycle", 3)), silent=True)
            self.set_steppers["interval_minutes"].setValue(
                int(lp.get("interval_minutes", 15)), silent=True)
        finally:
            self._set_guard = False

    def _collect_settings_block(self) -> dict:
        """بلوک کاملِ تنظیماتِ مدیریت‌شده را از ویجت‌ها بگیر."""
        s = self.set_switches
        st = self.set_steppers
        return {
            "ui": {"user_name": self.set_name.text().strip() or "سوشیان",
                   "splash": s["splash"].isChecked(),
                   "animations": s["animations"].isChecked()},
            "judge": {"enabled": s["judge_enabled"].isChecked(),
                      "min_score": int(st["min_score"].value()),
                      "max_signals_per_cycle": int(st["max_signals_per_cycle"].value()),
                      "veto": {k: s[f"veto.{k}"].isChecked() for k in VETO_KEYS}},
            "fundamental": {"enabled": s["fund_enabled"].isChecked(),
                            "alerts_enabled": s["alerts_enabled"].isChecked()},
            "news": {"enabled": s["news_enabled"].isChecked()},
            "tradingview": {"enabled": s["tv_enabled"].isChecked()},
            "loop": {"interval_minutes": int(st["interval_minutes"].value())},
            "briefing": {"enabled": s["briefing_enabled"].isChecked()},
            "journal": {"enabled": s["journal_enabled"].isChecked(),
                        "conservative_both_touch": s["both_touch"].isChecked()},
        }

    def _on_setting_changed(self, *_a) -> None:
        """هر تغییر = ذخیرهٔ فوری (دقیقاً رفتار نسخهٔ اندروید).

        مسیر اثر: config.local.yaml ← load_config ← BotLoop که هر چرخه
        cfg_provider() را صدا می‌زند → تغییرها بدون ری‌استارت اعمال می‌شوند.
        """
        if getattr(self, "_set_guard", False):
            return
        try:
            save_local_config(self._collect_settings_block())
            self.cfg = load_config()
        except Exception as e:
            self._log(f"[!] ذخیرهٔ تنظیمات ناموفق: {e}")
            return
        uicfg = self.cfg.get("ui") or {}
        self.user_name = str(uicfg.get("user_name") or "سوشیان")
        self._apply_user_name()
        effects.set_animations(bool(uicfg.get("animations", True)))
        self.toast.show_message("ذخیره شد ✓", "", "check")

    def _apply_user_name(self) -> None:
        """نام نمایشی تازه را آنی در هدر بنشان (سلام + آواتار)."""
        _set_text(self.greet_lbl, f"سلام {self.user_name}!")
        self.avatar.setText(self.user_name[:1] if self.user_name else "•")

    def _on_name_edited(self) -> None:
        if getattr(self, "_set_guard", False):
            return
        txt = self.set_name.text().strip() or "سوشیان"
        if txt != self.set_name.text():
            self.set_name.setText(txt)
        self._on_setting_changed()

    def _on_clear_cache(self) -> None:
        from src.fundamental.calendar import CACHE_FILE
        p = app_paths.cache_dir() / CACHE_FILE
        try:
            if p.exists():
                p.unlink()
                self._log("🧹 کش تقویم اقتصادی پاک شد — دریافت بعدی تازه است")
                self.toast.show_message("کش پاک شد", "تحلیل بعدی کاملاً تازه است",
                                        "refresh")
            else:
                self.toast.show_message("کشی وجود نداشت",
                                        "دادهٔ بازار و اخبار هر چرخه تازه دریافت می‌شوند",
                                        "info")
        except OSError as e:
            self._log(f"[!] پاک‌کردن کش ناموفق: {e}")

    def _on_reset_settings(self) -> None:
        r = QMessageBox.question(
            self, "بازنشانی تنظیمات",
            "همهٔ تنظیمات پنل (نام، داور، وتوها، موتورها، حلقه و ظاهر) به حالت\n"
            "پیش‌فرض برمی‌گردند.\n\n"
            "تلگرام، ژورنال و سیگنال‌های ثبت‌شده پاک نمی‌شوند.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r == QMessageBox.Yes:
            self._reset_settings_now()

    def _reset_settings_now(self) -> None:
        """بازنشانی بدون پرسش (selftest هم همین را صدا می‌زند)."""
        try:
            prune_local_config(MANAGED_SETTINGS)
            self.cfg = load_config()
        except Exception as e:
            self._log(f"[!] بازنشانی تنظیمات ناموفق: {e}")
            return
        self._load_settings_fields()
        uicfg = self.cfg.get("ui") or {}
        self.user_name = str(uicfg.get("user_name") or "سوشیان")
        self._apply_user_name()
        effects.set_animations(bool(uicfg.get("animations", True)))
        self._log("♻️ تنظیمات به حالت پیش‌فرض بازنشانی شد")
        self.toast.show_message("تنظیمات بازنشانی شد", "", "refresh")

    def _on_get_chat_id(self) -> None:
        token = self.tg_token.text().strip()
        if not token:
            self.tg_status.setText("⚠️ اول توکن بات را وارد کن (از @BotFather)")
            return
        self.tg_status.setText("⏳ در حال دریافت شناسه چت…")

        def work():
            ok, who = telegram.validate_token(token)
            if not ok:
                self.q.put(("tg_msg", f"❌ توکن نامعتبر: {who}"))
                return
            cid, msg = telegram.get_chat_id(token)
            if cid:
                self.q.put(("tg_msg", f"✅ {msg} — شناسه وارد شد"))
                self.q.put(("tg_chat", cid))
            else:
                self.q.put(("tg_msg", f"⚠️ {msg}"))
        threading.Thread(target=work, daemon=True).start()

    def _on_test_send(self) -> None:
        token = self.tg_token.text().strip()
        chat = self.tg_chat.text().strip()
        if not token or not chat:
            self.tg_status.setText("⚠️ توکن و شناسه چت را وارد کن")
            return
        self.tg_status.setText("⏳ در حال ارسال پیام تست…")

        def work():
            text = (f"✅ پیام تست {app_paths.APP_NAME}\n"
                    f"اگر این پیام را می‌بینی، تلگرام درست تنظیم شده است.\n"
                    f"نسخه {app_paths.APP_VERSION}")
            ok, msg = telegram.send_message(token, chat, text)
            self.q.put(("tg_msg", ("✅ ارسال شد! " if ok else "❌ ") + msg))
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

    # ── دیالوگ فعال‌سازی لایسنس ───────────────────────────────
    def _show_activation_dialog(self) -> bool:
        """نمایش دیالوگ فعال‌سازی برنامه.
        
        Returns:
            True اگر کاربر با موفقیت فعال‌سازی کرد، False اگر انصراف داد یا شکست خورد
        """
        # والدِ None: دیالوگ مستقل و مدال است — وابسته به ساخت‌ویندوز نیست
        dialog = QDialog()
        dialog.setWindowTitle("فعال‌سازی ODIN Assistant")
        dialog.setModal(True)
        dialog.setFixedSize(520, 430)
        dialog.setLayoutDirection(Qt.RightToLeft)
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # عنوان
        title_lbl = QLabel("فعال‌سازی برنامه")
        title_lbl.setObjectName("ink_title")
        title_lbl.setStyleSheet(f"color: {T.on_ink}; font-size: 18px; font-weight: bold;")
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)
        
        # توضیحات
        desc_lbl = QLabel(
            "۱) «کد دستگاه» زیر را کپی کرده و برای سازنده (Sushian Khoshkhani — تلگرام @Khode_Sushian) بفرستید.\n"
            "۲) کلید لایسنس مخصوص همین دستگاه را دریافت و اینجا وارد کنید.\n"
            "   کلیدهای زمان‌دار یک بخش تاریخ هم دارند — کل رشتهٔ دریافتی را وارد کنید.\n\n"
            "یا «شروع دورهٔ آزمایشی» را بزنید: ۷ روز استفادهٔ کامل و رایگان."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"color: {T.text_2}; font-size: 13px;")
        layout.addWidget(desc_lbl)
        
        # فرم ورودی
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        
        # فیلد نام کاربر
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("نام خود را وارد کنید")
        self.name_input.setMinimumHeight(40)
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                font-size: 13px;
                font-family: inherit;
            }
            QLineEdit:focus {
                border-color: #1976D2;
                outline: none;
            }
        """)
        form_layout.addRow("نام:", self.name_input)
        
        # فیلد کلید لایسنس
        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX[-YYMMDD]")
        self.license_input.setMinimumHeight(40)
        self.license_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                font-size: 13px;
                font-family: inherit;
                letter-spacing: 1px;
            }
            QLineEdit:focus {
                border-color: #1976D2;
                outline: none;
            }
        """)
        form_layout.addRow("کلید لایسنس:", self.license_input)
        
        # نمایش کد دستگاه (کامل، انتخاب‌پذیر، با دکمهٔ کپی) — v0.14.0
        device_code = get_device_code()
        dev_row = QHBoxLayout()
        dev_row.setSpacing(8)
        self.device_code_input = QLineEdit(device_code)
        self.device_code_input.setReadOnly(True)
        self.device_code_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px; border: 1px solid {T.divider}; border-radius: 8px;
                font-size: 14px; font-weight: bold; letter-spacing: 2px;
                color: {T.text}; background: {T.raised};
                font-family: Consolas, monospace;
            }}
        """)
        copy_btn = QPushButton("کپی")
        copy_btn.setMinimumHeight(38)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {T.text_2};
                border: 1px solid {T.divider}; border-radius: 8px;
                font-size: 12px; padding: 0 14px;
            }}
            QPushButton:hover {{ background-color: {T.rgba('#000000', 0.05)}; }}
        """)

        def _copy_code():
            QApplication.clipboard().setText(device_code)
            copy_btn.setText("کپی شد")

        copy_btn.clicked.connect(_copy_code)
        dev_row.addWidget(self.device_code_input, 1)
        dev_row.addWidget(copy_btn)
        form_layout.addRow("کد دستگاه:", dev_row)
        
        layout.addLayout(form_layout)
        
        # پیام وضعیت
        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet("font-size: 12px; color: #FF5D5D;")
        layout.addWidget(self.status_lbl)
        
        layout.addStretch(1)
        
        # دکمه‌ها
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        cancel_btn = QPushButton("انصراف")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.setMinimumWidth(120)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {T.text_2};
                border: 1px solid {T.divider};
                border-radius: 8px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {T.rgba('#000000', 0.05)};
            }}
        """)
        
        activate_btn = QPushButton("فعال‌سازی")
        activate_btn.setMinimumHeight(40)
        activate_btn.setMinimumWidth(120)
        activate_btn.setCursor(Qt.PointingHandCursor)
        activate_btn.setObjectName("primary")
        activate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T.accent_ink};
                color: {T.on_ink};
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {T.rgba(T.accent_ink, 0.9)};
            }}
            QPushButton:pressed {{
                background-color: {T.rgba(T.accent_ink, 0.8)};
            }}
        """)
        
        trial_btn = QPushButton("شروع دورهٔ آزمایشی ۷ روزه")
        trial_btn.setMinimumHeight(40)
        trial_btn.setCursor(Qt.PointingHandCursor)
        trial_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T.raised};
                color: {T.text};
                border: none;
                border-radius: 8px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {T.rgba('#000000', 0.08)}; }}
        """)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(trial_btn)
        btn_layout.addWidget(activate_btn)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        
        # اتصال دکمه‌ها
        self.activation_result = False
        
        def on_activate():
            name = self.name_input.text().strip()
            license_key = self.license_input.text().strip()
            
            if not name:
                self.status_lbl.setText("لطفاً نام خود را وارد کنید")
                self.status_lbl.setStyleSheet("font-size: 12px; color: #FF9A9A;")
                return
            
            if not license_key:
                self.status_lbl.setText("لطفاً کلید لایسنس را وارد کنید")
                self.status_lbl.setStyleSheet("font-size: 12px; color: #FF9A9A;")
                return
            
            # تلاش برای فعال‌سازی
            success, message = activate_program(license_key, name)
            
            if success:
                self.status_lbl.setText(message)
                self.status_lbl.setStyleSheet("font-size: 12px; color: #4CAF50;")
                self.activation_result = True
                dialog.accept()
            else:
                self.status_lbl.setText(message)
                self.status_lbl.setStyleSheet("font-size: 12px; color: #FF5D5D;")
        
        def on_trial():
            ok, msg = start_trial()
            if ok:
                self.status_lbl.setText(msg + " — همهٔ امکانات فعال است")
                self.status_lbl.setStyleSheet("font-size: 12px; color: #4CAF50;")
                self.activation_result = True
                dialog.accept()
            else:
                self.status_lbl.setText(msg)
                self.status_lbl.setStyleSheet("font-size: 12px; color: #FF5D5D;")

        activate_btn.clicked.connect(on_activate)
        trial_btn.clicked.connect(on_trial)
        cancel_btn.clicked.connect(dialog.reject)
        
        # اجرای دیالوگ
        result = dialog.exec()
        
        return self.activation_result if hasattr(self, 'activation_result') else (result == QDialog.Accepted)


# ══════════════════════════════════════════════════════════════
#  دیالوگ هشدارهای قیمت (v0.19.0)
# ══════════════════════════════════════════════════════════════
class AlertsDialog(QDialog):
    """مدیریت هشدارهای سطح قیمت — همان مدل js/alerts.js (src/alerts.py)."""

    def __init__(self, parent=None, t=DARK):
        super().__init__(parent)
        self._t = t
        self.setWindowTitle("هشدارهای قیمت — ODIN ASSISTANT")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumSize(540, 580)
        self._pips = {}
        try:
            cfg = load_config()
            for sym in cfg.get("symbols", []):
                self._pips[sym["name"]] = float(sym.get("pip", 0.0001))
        except Exception:
            pass
        if not self._pips:
            self._pips = {k: 0.0001 for k in
                          ("EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF")}
            self._pips["XAUUSD"] = 1.0
            self._pips["USDJPY"] = 0.01

        from src.fa import fa_num  # noqa: F401  (برای سازگاری بصری)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)

        desc = QLabel("وقتی قیمت از سطح تعیین‌شده عبور کرد، اعلان می‌گیری — "
                      "در پنل، در tray (حتی وقتی پنجره بسته است) و در تلگرامِ وصل. "
                      "هشدار یک‌بارمصرف پس از فعال‌شدن حذف می‌شود.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{t.text_2};font-size:12px")
        root.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(10)
        self.cmb_sym = QComboBox()
        self.cmb_sym.addItems(list(self._pips.keys()))
        self.cmb_dir = QComboBox()
        self.cmb_dir.addItem("عبور به بالا", "above")
        self.cmb_dir.addItem("عبور به پایین", "below")
        self.txt_price = QLineEdit()
        self.txt_price.setPlaceholderText("مثلاً 1.1800")
        self.txt_price.setStyleSheet("text-align:center;font-weight:700;letter-spacing:1px")
        self.chk_sticky = QCheckBox("تکرارشونده (حداکثر ساعتی یک‌بار یادآوری شود)")
        form.addRow("نماد:", self.cmb_sym)
        form.addRow("جهت:", self.cmb_dir)
        form.addRow("قیمت:", self.txt_price)
        form.addRow("", self.chk_sticky)
        root.addLayout(form)

        self.btn_add = _btn("افزودن هشدار", "primary", "bell", "")
        self.btn_add.clicked.connect(self._on_add)
        root.addWidget(self.btn_add)

        self.status = QLabel("")
        self.status.setStyleSheet("font-size:11px")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.list = QListWidget()
        self.list.setStyleSheet(f"background:{t.card};border:1px solid {t.border};"
                                f"border-radius:12px;font-size:12px")
        root.addWidget(self.list, 1)

        self.btn_del = _btn("حذف هشدار انتخاب‌شده", "", "stop", "")
        self.btn_del.clicked.connect(self._on_del)
        root.addWidget(self.btn_del)
        self.refresh()

    def refresh(self) -> None:
        from src import alerts as alert_store
        self.list.clear()
        for a in alert_store.load_alerts():
            d = "بالاتر از" if a.get("dir") == "above" else "پایین‌تر از"
            kind = "تکرارشونده" if a.get("sticky") else "یک‌بارمصرف"
            it = QListWidgetItem(f"{a['symbol']} — {d} {a['price']}   ({kind})")
            it.setData(Qt.UserRole, a.get("id"))
            self.list.addItem(it)

    def _on_add(self) -> None:
        from src import alerts as alert_store
        raw = self.txt_price.text().strip().replace("٫", ".")
        try:
            price = float(raw)
        except ValueError:
            self.status.setText("قیمت نامعتبر — عدد لاتین وارد کن")
            self.status.setStyleSheet(f"color:{self._t.red_text};font-size:11px")
            return
        sym = self.cmb_sym.currentText()
        ok, why = alert_store.add_alert(
            sym, self.cmb_dir.currentData(), price,
            sticky=self.chk_sticky.isChecked(),
            pip=self._pips.get(sym, 0.0001))
        if ok:
            self.status.setText(f"هشدار {sym} ثبت شد — در چرخهٔ تحلیل بعدی بررسی می‌شود")
            self.status.setStyleSheet(f"color:{self._t.green_text};font-size:11px")
            self.txt_price.setText("")
            self.refresh()
        else:
            msg = {"duplicate": "این هشدار قبلاً ثبت شده",
                   "max": f"حداکثر {alert_store.MAX_ALERTS} هشدار فعال — یکی را حذف کن",
                   }.get(why, "نامعتبر")
            self.status.setText(msg)
            self.status.setStyleSheet(f"color:{self._t.red_text};font-size:11px")

    def _on_del(self) -> None:
        from src import alerts as alert_store
        it = self.list.currentItem()
        if it is None:
            return
        alert_store.remove_alert(it.data(Qt.UserRole))
        self.refresh()


# ══════════════════════════════════════════════════════════════
#  دیالوگ نمودار کندل‌استیک (v0.19.0)
# ══════════════════════════════════════════════════════════════
class ChartDialog(QDialog):
    """نمودار H1/H4 از کش چرخه‌ها (chart_<SYM>.json) + سطوح سیگنال."""

    def __init__(self, parent=None, symbol: str = None, levels=None,
                 sr=(None, None), t=DARK):
        super().__init__(parent)
        self._t = t
        self._levels_ext = list(levels or [])
        self._sr = sr or (None, None)
        self._pips = {}
        try:
            cfg = load_config()
            for sym in cfg.get("symbols", []):
                self._pips[sym["name"]] = float(sym.get("pip", 0.0001))
        except Exception:
            pass
        if not self._pips:
            self._pips = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01,
                          "USDCAD": 0.0001, "AUDUSD": 0.0001, "USDCHF": 0.0001,
                          "XAUUSD": 1.0}
        syms = list(self._pips.keys())
        self._sym = symbol if symbol in self._pips else (syms[0] if syms else "EURUSD")
        self._tf = "h1"

        self.setWindowTitle(f"نمودار کندل‌استیک — {self._sym} · ODIN ASSISTANT")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(920, 600)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        bar = QHBoxLayout()
        self.cmb_sym = QComboBox()
        self.cmb_sym.addItems(syms)
        self.cmb_sym.setCurrentText(self._sym)
        self.cmb_sym.currentTextChanged.connect(self._on_sym)
        self.btn_h1 = _btn("H1", "", "", "کندل‌های یک‌ساعته")
        self.btn_h4 = _btn("H4", "", "", "کندل‌های چهارساعته")
        self.btn_h1.setCheckable(True)
        self.btn_h4.setCheckable(True)
        self.btn_h1.setChecked(True)
        self.btn_h1.clicked.connect(lambda: self._on_tf("h1"))
        self.btn_h4.clicked.connect(lambda: self._on_tf("h4"))
        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet(f"color:{t.text_3};font-size:11px")
        bar.addWidget(QLabel("نماد:"))
        bar.addWidget(self.cmb_sym)
        bar.addSpacing(10)
        bar.addWidget(self.btn_h1)
        bar.addWidget(self.btn_h4)
        bar.addStretch(1)
        bar.addWidget(self.lbl_info)
        root.addLayout(bar)

        self.chart = CandleChart(t=t)
        root.addWidget(self.chart, 1)
        self.load()

    def _on_sym(self, sym: str) -> None:
        self._sym = sym
        self.setWindowTitle(f"نمودار کندل‌استیک — {sym} · ODIN ASSISTANT")
        self.load()

    def _on_tf(self, tf: str) -> None:
        self._tf = tf
        self.btn_h1.setChecked(tf == "h1")
        self.btn_h4.setChecked(tf == "h4")
        self.load()

    def load(self) -> None:
        import json as _json
        try:
            f = app_paths.data_dir() / f"chart_{self._sym}.json"
            if not f.exists():
                self.chart.set_data([])
                self.lbl_info.setText("کش نمودار نیست — یک چرخهٔ تحلیل اجرا کن")
                return
            data = _json.loads(f.read_text(encoding="utf-8"))
            candles = data.get(self._tf) or []
            pip = self._pips.get(self._sym, 0.0001)
            levels = list(self._levels_ext)
            sup, res = self._sr
            from src.report.signal import fmt_price
            if sup:
                levels.append((float(sup), QColor(self._t.text_3),
                               "حمایت " + fmt_price(float(sup), pip), True))
            if res:
                levels.append((float(res), QColor(self._t.text_3),
                               "مقاومت " + fmt_price(float(res), pip), True))
            self.chart.set_data(candles[-240:], pip, levels)
            if candles:
                from datetime import datetime as _dt, timezone as _tz
                from src.fa import jalali_fa
                last_t = _dt.fromtimestamp(candles[-1]["t"] / 1000, tz=_tz.utc)
                self.lbl_info.setText(f"{len(candles)} کندل · آخرین: {jalali_fa(last_t)}")
            else:
                self.lbl_info.setText("کندلی در کش نیست")
        except Exception as e:
            self.chart.set_data([])
            self.lbl_info.setText(f"خطا در بارگذاری نمودار: {str(e)[:60]}")


# ══════════════════════════════════════════════════════════════
#  خودآزمون و ورودی
# ══════════════════════════════════════════════════════════════
def _selftest() -> int:
    """ورودی خودآزمون — پوشهٔ داده‌ها را موقت می‌کند.

    آزمون‌های تازهٔ «تنظیمات» در config.local.yaml می‌نویسند؛ فایل واقعیِ
    کاربر (که توکن تلگرام دارد) هرگز نباید لمس شود. پس داده‌ها به پوشهٔ
    temp می‌روند و config.yaml پروژه داخلش کپی می‌شود.
    """
    app_paths.fix_console_encoding()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    # خودآزمون هرگز پشت دروازهٔ لایسنس نمی‌ماند (CI و توسعه)
    os.environ["ODIN_SKIP_LICENSE"] = "1"
    tmp_data = tempfile.mkdtemp(prefix="odin-selftest-")
    repo_cfg = Path(app_paths.app_dir()) / "config.yaml"
    if repo_cfg.exists():
        shutil.copyfile(repo_cfg, str(Path(tmp_data) / "config.yaml"))
    os.environ[app_paths.DATA_DIR_ENV] = tmp_data
    app_paths.clear_data_dir_cache()
    try:
        return _selftest_body()
    finally:
        shutil.rmtree(tmp_data, ignore_errors=True)
        os.environ.pop(app_paths.DATA_DIR_ENV, None)
        app_paths.clear_data_dir_cache()


def _selftest_body() -> int:
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    fam = load_fonts()
    app.setFont(QFont(fam, 11))
    app.setStyleSheet(build_qss(fam, check_img=_check_img()))

    win = MainWindow(show_splash=False)
    win.show()
    app.processEvents()

    from src.notify.telegram import _chunks
    assert len(_chunks("x" * 9000)) >= 3, "تقسیم پیام تلگرام درست کار نمی‌کند"
    assert callable(run_cycle) and callable(run_briefing) and callable(check_event_alerts)

    assert win.pages.count() == 8, f"انتظار ۸ صفحه، {win.pages.count()}"
    assert (win.TAB_DASH, win.TAB_SIGNAL, win.TAB_REPORT, win.TAB_FUND,
            win.TAB_BRIEF, win.TAB_LOG, win.TAB_JOURNAL,
            win.TAB_SETTINGS) == tuple(range(8))
    assert len(win.nav._items) == 8, "ریل ناوبری باید ۸ آیتم داشته باشد"   # noqa: SLF001
    assert win.user_name, "نام کاربر برای Splash باید مقدار داشته باشد"
    assert win.windowTitle().startswith("ODIN Assistant"), \
        f"عنوان پنجره باید با برند شروع شود: {win.windowTitle()!r}"
    assert f"سلام {win.user_name}" in win.greet_lbl.text(), "سلام بزرگ در هدر"

    # v0.19.0 — اجزای تازه: دیالوگ هشدارها، دیالوگ نمودار، کارت سیگنال، اشتراک
    ad = AlertsDialog(win)
    ad.refresh()
    ad.close()
    cd = ChartDialog(win)
    cd.load()
    cd.close()
    fake_sig = {"symbol": "EURUSD", "direction": "BUY", "score": 10, "max_score": 11,
                "sent": True, "text": "", "entry": 1.17, "sl": 1.165, "tp": 1.18,
                "pip": 0.0001, "is_gold": False, "rr": 2.0, "stars": 5,
                "session_fa": "لندن", "fa_name": "یورو به دلار آمریکا",
                "now": datetime.now(timezone.utc).isoformat()}
    win._last_signals = [fake_sig]
    win._show_signal_popup([fake_sig])
    app.processEvents()
    assert win._sig_popup is not None, "کارت سیگنال متحرک ساخته نشد"
    from src.report.sharecard import build_share_spec, render_card_pixmap
    _spec = build_share_spec(fake_sig, version=app_paths.APP_VERSION)
    assert _spec["pair"] == "EUR/USD" and _spec["footerTg"] == "@Khode_Sushian"
    _pm = render_card_pixmap(_spec)
    assert not _pm.isNull() and _pm.width() == 1080 and _pm.height() == 1350, \
        "کارت تصویری ۱۰۸۰×۱۳۵۰ رندر نشد"
    from src import alerts as _al
    _al.add_alert("EURUSD", "above", 9.9999, pip=0.0001)
    _fired = _al.check_alerts([{"symbol": "EURUSD", "price": 10.5, "pip": 0.0001}])
    assert len(_fired) == 1, "هشدار قیمت در موتور فعال نشد"
    assert _al.check_alerts([{"symbol": "EURUSD", "price": 10.5, "pip": 0.0001}]) == [], \
        "هشدار یک‌بارمصرف باید پس از فعال‌شدن حذف شود"

    # رگرسیون باگ «صفحه سیاه تا درگ»
    from PySide6.QtWidgets import QGraphicsOpacityEffect
    probe = QWidget()
    effects.fade(probe, 0.0, 1.0, 60)
    assert isinstance(probe.graphicsEffect(), QGraphicsOpacityEffect)
    import time as _time
    deadline = _time.time() + 2.0
    while _time.time() < deadline and probe.graphicsEffect() is not None:
        app.processEvents()
        app.thread().msleep(10)
    assert probe.graphicsEffect() is None, "اثر opacity باقی ماند → باگ صفحه سیاه"

    win.report_view.setPlainText("متن نمونه برای بررسی رندر ✅\nسطر دوم")
    win.nav._select(win.TAB_REPORT)      # noqa: SLF001
    deadline = _time.time() + 2.0
    while (_time.time() < deadline
           and win.pages.widget(win.TAB_REPORT).graphicsEffect() is not None):
        app.processEvents()
        app.thread().msleep(10)
    app.processEvents()
    img = win.pages.currentWidget().grab().toImage()
    bg = img.pixelColor(4, 4)
    diff = sum(1 for y in range(0, img.height(), 6) for x in range(0, img.width(), 6)
               if img.pixelColor(x, y) != bg)
    assert diff > 30, f"صفحه فقط پس‌زمینهٔ خالی رندر کرد ({diff}) — باگ صفحه سیاه/خالی"
    win.nav._select(win.TAB_DASH)        # noqa: SLF001
    app.processEvents()

    # آیکون‌ها
    for nm in ("dashboard", "target", "play", "stop", "logo", "chart"):
        pm = icons.icon(nm, 24, "#111111").pixmap(24, 24)
        assert not pm.isNull(), f"آیکون {nm} رندر نشد"

    # داور آفلاین
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
    assert sl < 1.1486 < 1.149 < tp and not capped

    # ── صفحهٔ تنظیمات — آینهٔ نسخهٔ اندروید (v0.8.1) ──────────────
    assert win.pages.widget(win.TAB_SETTINGS).objectName() == "pagescroll", \
        "صفحهٔ تنظیمات باید ظرف اسکرول داشته باشد (محتوای بلند)"
    base_cfg = load_config()
    expect_sw = {"judge_enabled", "fund_enabled", "alerts_enabled", "news_enabled",
                 "tv_enabled", "briefing_enabled", "journal_enabled", "both_touch",
                 "splash", "animations",
                 *(f"veto.{k}" for k in VETO_KEYS)}
    assert expect_sw <= set(win.set_switches), "سوئیچ‌های تنظیمات ناقص‌اند"
    assert {"min_score", "max_signals_per_cycle",
            "interval_minutes"} <= set(win.set_steppers), "قدم‌شمارها ناقص‌اند"

    # صفحهٔ تنظیمات واقعاً رندر می‌شود (رگرسیون صفحهٔ خالی)
    win.nav._select(win.TAB_SETTINGS)       # noqa: SLF001
    deadline = _time.time() + 2.0
    while (_time.time() < deadline
           and win.pages.currentWidget().graphicsEffect() is not None):
        app.processEvents()
        app.thread().msleep(10)
    img = win.pages.currentWidget().grab().toImage()
    bg = img.pixelColor(4, 4)
    diff = sum(1 for y in range(0, img.height(), 6) for x in range(0, img.width(), 6)
               if img.pixelColor(x, y) != bg)
    assert diff > 30, f"صفحهٔ تنظیمات خالی رندر کرد ({diff})"

    # نام نمایشی → اثر آنی در هدر + ماندگاری در config.local.yaml
    win.set_name.setText("نام‌تست")
    win._on_name_edited()                   # noqa: SLF001
    assert win.user_name == "نام‌تست"
    assert "سلام نام‌تست" in win.greet_lbl.text(), "نام تازه باید آنی در هدر بنشیند"
    assert win.avatar.text() == "ن", "حرف اول نام در آواتار"
    assert load_config()["ui"]["user_name"] == "نام‌تست", "نام باید ذخیره شود"

    # سوئیچ داور → خاموش؛ بارگذاری تازهٔ config همان را ببیند
    win.set_switches["judge_enabled"].setChecked(False)
    app.processEvents()
    cfg2 = load_config()
    assert cfg2["judge"]["enabled"] is False, "خاموش‌کردن داور باید ذخیره شود"
    assert cfg2["judge"]["min_score"] == base_cfg["judge"]["min_score"], \
        "بقیهٔ تنظیمات داور نباید دست بخورد"

    # قدم‌شمار: clamp در بازه + ذخیره
    win.set_steppers["min_score"].setValue(99)
    assert win.set_steppers["min_score"].value() == 10, "clamp در سقف ۱۰"
    win.set_steppers["min_score"].setValue(9)
    app.processEvents()
    assert load_config()["judge"]["min_score"] == 9

    # وتوها هم ذخیره می‌شوند
    win.set_switches["veto.weekend"].setChecked(False)
    app.processEvents()
    assert load_config()["judge"]["veto"]["weekend"] is False
    assert load_config()["judge"]["veto"]["breaking_news"] is True

    # پاک‌کردن کش تقویم
    cache_f = app_paths.cache_dir() / "calendar.json"
    cache_f.write_text("[]", encoding="utf-8")
    win._on_clear_cache()                   # noqa: SLF001
    assert not cache_f.exists(), "کش تقویم باید پاک شود"

    # بازنشانی: تنظیمات مدیریت‌شده → پیش‌فرض؛ تلگرام دست‌نخورده
    save_local_config({"telegram": {"bot_token": "TOKEN-BAYAD-BEMUNAD"}})
    win._reset_settings_now()               # noqa: SLF001
    cfg3 = load_config()
    assert cfg3["judge"]["enabled"] is True and cfg3["judge"]["min_score"] == 7
    assert cfg3["judge"]["veto"]["weekend"] is True
    assert cfg3["ui"]["user_name"] == base_cfg["ui"]["user_name"]
    assert win.user_name == base_cfg["ui"]["user_name"], "هدر باید به نام پیش‌فرض برگردد"
    assert cfg3["telegram"]["bot_token"] == "TOKEN-BAYAD-BEMUNAD", \
        "بازنشانی نباید تلگرام را پاک کند"

    win.close()
    print(f"SELFTEST OK — فونت: {fam} | صفحات: {win.pages.count()} | "
          f"آیکون‌ها/داور/رندر/تنظیمات سالم | نسخه {app_paths.APP_VERSION}")
    return 0


def main() -> None:
    app_paths.fix_console_encoding()

    if "--selftest" in sys.argv:
        sys.exit(_selftest())

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setLayoutDirection(Qt.RightToLeft)

    from PySide6.QtCore import QSharedMemory
    guard = QSharedMemory("ODINAssistant_SingleInstance_Guard_v3")
    if not guard.create(1):
        if guard.attach():
            guard.detach()
        if not guard.create(1):
            QMessageBox.warning(None, app_paths.APP_NAME,
                                "برنامه از قبل در حال اجراست! (یک پنجرهٔ دیگر باز است)")
            sys.exit(0)
    app._single_instance_guard = guard    # noqa: SLF001

    fam = load_fonts()
    app.setFont(QFont(fam, 11))
    app.setStyleSheet(build_qss(fam, check_img=_check_img()))

    win = MainWindow(show_splash="--no-splash" not in sys.argv)
    app._main_window = win
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
