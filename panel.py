#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""پنل کنترل دستیار سیگنال فارکس — نسخهٔ ۰٫۶ (تم روشن شیشه‌ای).

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
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

from src import app_paths
from src.config import load_config, save_local_config
from src.engine import BotLoop, check_event_alerts, run_briefing, run_cycle
from src.fa import fa_countdown
from src.notify import telegram
from src.ui import dwm, effects, icons
from src.ui.backdrop import paint_glass, render_backdrop
from src.ui.splash import WelcomeSplash
from src.ui.theme import DARK, Space, build_qss
from src.ui.widgets import (Card, DashedCard, InkCard, LineChart, NavRail, RingGauge,
                            StatTile, StatusPill, Toast)

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
T = DARK
# رنگ متن کارت مشکی در کد ست می‌شود؛ QSS روی برخی پلتفرم‌ها (ویندوز)
# به برچسب‌های فرزند القا نمی‌شود و متن سیاه روی سیاه نامرئی می‌ماند.
_INK_TITLE = f"color: {T.on_ink};"
_INK_CAP = f"color: {T.rgba('#FFFFFF', 0.55)};"


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
                            cfg_provider=load_config)
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
        self.setWindowTitle(f"دستیار سیگنال فارکس — {app_paths.APP_VERSION}")
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
        w, lay = self._page_frame("تنظیمات", "تلگرام، فایل‌ها و دربارهٔ برنامه")

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
        av = QLabel(f"نسخه {fa(app_paths.APP_VERSION)}  ·  تم روشن شیشه‌ای مونوکروم  ·  "
                    f"طراحی Fluent/2026\n"
                    "این ابزار فقط تحلیل و سیگنال می‌دهد و هیچ معامله‌ای انجام نمی‌دهد؛ "
                    "تصمیم نهایی با شماست.")
        av.setObjectName("label"); av.setWordWrap(True)
        about.add_widget(av)
        lay.addWidget(about)
        lay.addStretch(1)
        return w

    # ── ناوبری ────────────────────────────────────────────────
    def _on_nav(self, i: int) -> None:
        if i == self.TAB_SETTINGS:
            # config ممکن است بیرون برنامه ویرایش شده باشد؛ هنگام بازکردن
            # صفحهٔ تنظیمات دوباره خوانده می‌شود تا مقادیر کهنه نمایش داده نشود.
            try:
                self.cfg = load_config()
                self._load_tg_fields()
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
            text = (f"✅ پیام تست دستیار سیگنال فارکس\n"
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


# ══════════════════════════════════════════════════════════════
#  خودآزمون و ورودی
# ══════════════════════════════════════════════════════════════
def _selftest() -> int:
    app_paths.fix_console_encoding()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
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
    assert f"سلام {win.user_name}" in win.greet_lbl.text(), "سلام بزرگ در هدر"

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

    win.close()
    print(f"SELFTEST OK — فونت: {fam} | صفحات: {win.pages.count()} | "
          f"آیکون‌ها/داور/رندر سالم | نسخه {app_paths.APP_VERSION}")
    return 0


def main() -> None:
    app_paths.fix_console_encoding()

    if "--selftest" in sys.argv:
        sys.exit(_selftest())

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setLayoutDirection(Qt.RightToLeft)

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
    app.setStyleSheet(build_qss(fam, check_img=_check_img()))

    win = MainWindow(show_splash="--no-splash" not in sys.argv)
    app._main_window = win
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
