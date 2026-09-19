#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""پنل کنترل گرافیکی دستیار سیگنال فارکس — PySide6، تاریک، راست‌به‌چپ، فونت وزیرمتن.

اجرای مستقیم      :  python panel.py
خودآزمون (بدون GUI):  python panel.py --selftest     (برای CI / ساخت EXE)

اگر فونت ایران‌سنس را در پوشه «fonts» کنار برنامه بگذارید، خودکار جای وزیرمتن
استفاده می‌شود.
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QSharedMemory, Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy,
    QTabWidget, QVBoxLayout, QWidget,
)

from src import app_paths
from src.config import load_config, save_local_config
from src.engine import BotLoop, check_event_alerts, run_briefing, run_cycle
from src.notify import telegram

# ── ابزارهای کوچک ──────────────────────────────────────────────
_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(text) -> str:
    """تبدیل ارقام به فارسی (برای ساعت و شمارنده‌ها)."""
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


def build_qss(fam: str) -> str:
    return f"""
* {{ font-family: "{fam}"; }}
QMainWindow, QWidget {{ background-color: #0e1116; color: #e8eaf0; font-size: 14px; }}
QFrame#card {{ background-color: #161a22; border: 1px solid #232936; border-radius: 14px; }}
QLabel#title {{ font-size: 20px; font-weight: 800; color: #ffffff; }}
QLabel#subtitle {{ color: #8b93a5; font-size: 12px; }}
QLabel#bigemoji {{ font-size: 30px; }}
QLabel#chip {{ background: #1c2230; border: 1px solid #2a3242; border-radius: 10px;
              padding: 4px 10px; color: #9aa4b8; font-size: 11px; }}
QLabel#pill {{ border-radius: 11px; padding: 5px 14px; font-weight: 700; font-size: 13px; }}
QLabel#pill[state=idle] {{ background: #262b36; color: #9aa4b8; border: 1px solid #313849; }}
QLabel#pill[state=ok]   {{ background: #052e16; color: #4ade80; border: 1px solid #14532d; }}
QLabel#pill[state=busy] {{ background: #172554; color: #60a5fa; border: 1px solid #1e3a8a; }}
QLabel#pill[state=err]  {{ background: #450a0a; color: #f87171; border: 1px solid #7f1d1d; }}
QLabel#section {{ font-size: 15px; font-weight: 700; color: #f3f4f8; }}
QLabel#sub {{ color: #8b93a5; font-size: 12px; }}
QLabel#hint {{ color: #6b7280; font-size: 11px; }}
QLabel#tgstatus {{ color: #9aa4b8; font-size: 12px; }}
QPushButton {{ border-radius: 10px; padding: 10px 18px; font-weight: 700; font-size: 14px; }}
QPushButton:disabled {{ color: #5b6270; background: #1a1f29; border: 1px solid #232936; }}
QPushButton#primary {{ background-color: #16a34a; color: white; border: none; }}
QPushButton#primary:hover:!disabled {{ background-color: #15803d; }}
QPushButton#primary:pressed {{ background-color: #166534; }}
QPushButton#danger {{ background-color: #dc2626; color: white; border: none; }}
QPushButton#danger:hover:!disabled {{ background-color: #b91c1c; }}
QPushButton#accent {{ background-color: #2563eb; color: white; border: none; }}
QPushButton#accent:hover:!disabled {{ background-color: #1d4ed8; }}
QPushButton#ghost {{ background: transparent; color: #c7cdd9; border: 1px solid #2c3444; }}
QPushButton#ghost:hover:!disabled {{ border-color: #3b82f6; color: #ffffff; }}
QLineEdit {{ background: #0b0e13; border: 1px solid #262d3b; border-radius: 9px;
            padding: 9px 12px; color: #e8eaf0; font-size: 13px; }}
QLineEdit:focus {{ border-color: #22c55e; }}
QCheckBox {{ spacing: 8px; color: #c7cdd9; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px;
                       border: 1px solid #2c3444; background: #0b0e13; }}
QCheckBox::indicator:checked {{ background: #16a34a; border-color: #16a34a; }}
QTabWidget::pane {{ border: 1px solid #232936; border-radius: 12px; background: #0b0e13; top: -1px; }}
QTabBar::tab {{ background: transparent; color: #8b93a5; padding: 9px 20px;
               border-radius: 9px; font-weight: 600; }}
QTabBar::tab:selected {{ background: #1c2230; color: #ffffff; }}
QPlainTextEdit {{ background: #0b0e13; border: none; border-radius: 10px;
                 padding: 10px; color: #d5dae4; font-size: 13px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2a3242; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def _card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(18, 14, 18, 14)
    lay.setSpacing(10)
    if title:
        lbl = QLabel(title)
        lbl.setObjectName("section")
        lay.addWidget(lbl)
    return frame, lay


# ── پنجره اصلی ─────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.q: queue.Queue = queue.Queue()
        self.cfg = load_config()
        self.loop = BotLoop(on_log=lambda m: self.q.put(("log", m)),
                            on_report=lambda r: self.q.put(("report", r)),
                            on_briefing=lambda r: self.q.put(("briefing", r)),
                            on_fundamental=lambda r: self.q.put(("fundamental", r)),
                            cfg_provider=load_config)
        self._build_ui()
        self._load_tg_fields()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_queue)
        self.timer.start(300)
        self.tick = QTimer(self)
        self.tick.timeout.connect(self._tick)
        self.tick.start(1000)

        self._log("👋 سلام! دکمه «▶ شروع ربات» را بزن تا تحلیل خودکار فعال شود.")
        self._log("🆕 جدید در نسخهٔ ۰٫۳: تقویم اقتصادی + رصد اخبار + بریفینگ صبحگاهی "
                  "+ هشدار رویداد پراثر + وتوی خودکار سیگنال نزدیک اخبار مهم")
        self._log("💡 برای دریافت گزارش‌ها روی گوشی، بخش تلگرام را تنظیم کن (راهنما: docs/panel-guide-fa.md)")

    # ── ساخت رابط ─────────────────────────────────────────────
    def _build_ui(self) -> None:
        self.setWindowTitle(f"🤖 دستیار سیگنال فارکس — نسخه {fa(app_paths.APP_VERSION)}")
        self.resize(900, 880)
        icon = app_paths.bundled_dir() / "assets" / "icon.ico"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # سربرگ
        head = QHBoxLayout()
        emoji = QLabel("🤖")
        emoji.setObjectName("bigemoji")
        texts = QVBoxLayout()
        texts.setSpacing(2)
        title = QLabel("دستیار سیگنال فارکس")
        title.setObjectName("title")
        subtitle = QLabel("تکنیکال + تقویم اقتصادی + اخبار + تاییدیه تریدینگ‌ویو — "
                          "گزارش به زبان ساده، مستقیم به تلگرام تو")
        subtitle.setObjectName("subtitle")
        texts.addWidget(title)
        texts.addWidget(subtitle)
        chip = QLabel(f"نسخه {fa(app_paths.APP_VERSION)}")
        chip.setObjectName("chip")
        head.addWidget(emoji)
        head.addLayout(texts)
        head.addStretch(1)
        head.addWidget(chip)
        root.addLayout(head)

        # کارت وضعیت
        card, lay = _card()
        row = QHBoxLayout()
        self.pill = QLabel("⏹ متوقف")
        self.pill.setObjectName("pill")
        self._set_pill_state("idle")
        self.last_run_lbl = QLabel("آخرین تحلیل: —")
        self.last_run_lbl.setObjectName("sub")
        self.next_run_lbl = QLabel("")
        self.next_run_lbl.setObjectName("sub")
        self.clock_lbl = QLabel("")
        self.clock_lbl.setObjectName("sub")
        row.addWidget(self.pill)
        row.addWidget(self.last_run_lbl)
        row.addStretch(1)
        row.addWidget(self.next_run_lbl)
        row.addWidget(self.clock_lbl)
        lay.addLayout(row)

        # ردیف دوم: وتوی خبری + وضعیت فاندامنتال/بریفینگ
        row2 = QHBoxLayout()
        self.veto_lbl = QLabel("")
        self.veto_lbl.setObjectName("sub")
        self.veto_lbl.setWordWrap(True)
        self.fund_lbl = QLabel("")
        self.fund_lbl.setObjectName("sub")
        self.brief_lbl = QLabel("")
        self.brief_lbl.setObjectName("sub")
        row2.addWidget(self.veto_lbl, 2)
        row2.addWidget(self.fund_lbl, 2)
        row2.addStretch(1)
        row2.addWidget(self.brief_lbl)
        lay.addLayout(row2)
        root.addWidget(card)

        # دکمه‌های کنترل
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)
        self.btn_start = QPushButton("▶ شروع ربات")
        self.btn_start.setObjectName("primary")
        self.btn_start.setMinimumHeight(44)
        self.btn_stop = QPushButton("⏹ توقف")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.setMinimumHeight(44)
        self.btn_once = QPushButton("🔄 اجرای یک‌بار تحلیل")
        self.btn_once.setObjectName("accent")
        self.btn_once.setMinimumHeight(44)
        self.btn_brief = QPushButton("🌅 بریفینگ صبحگاهی")
        self.btn_brief.setObjectName("ghost")
        self.btn_brief.setMinimumHeight(44)
        self.btn_brief.setToolTip("ساخت و ارسال بریفینگ صبحگاهی: تقویم امروز، پنجره‌های ممنوعه، "
                                  "تیترهای بازار و جهت مورد انتظار هر نماد")
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_once.clicked.connect(self._on_once)
        self.btn_brief.clicked.connect(self._on_briefing)
        ctrl.addWidget(self.btn_start)
        ctrl.addWidget(self.btn_stop)
        ctrl.addWidget(self.btn_once)
        ctrl.addWidget(self.btn_brief)
        ctrl.addStretch(1)
        root.addLayout(ctrl)

        # کارت تلگرام
        tg_card, tg_lay = _card("📱 تلگرام — دریافت گزارش‌ها روی گوشی")
        self.tg_token = QLineEdit()
        self.tg_token.setPlaceholderText("توکن بات از BotFather (مثلاً 123456:ABC-DEF...)")
        self.tg_token.setEchoMode(QLineEdit.Password)
        self.tg_token.editingFinished.connect(self._save_tg_fields)
        self.tg_chat = QLineEdit()
        self.tg_chat.setPlaceholderText("شناسه چت (عدد) — یا دکمه «گرفتن خودکار» را بزن")
        self.tg_chat.editingFinished.connect(self._save_tg_fields)
        self.btn_getid = QPushButton("📥 گرفتن خودکار شناسه")
        self.btn_getid.setObjectName("ghost")
        self.btn_getid.clicked.connect(self._on_get_chat_id)
        self.btn_test = QPushButton("✅ ارسال پیام تست")
        self.btn_test.setObjectName("ghost")
        self.btn_test.clicked.connect(self._on_test_send)
        self.chk_send = QCheckBox("گزارش‌ها به تلگرام ارسال شود")
        self.chk_send.toggled.connect(self._save_tg_fields)
        self.tg_status = QLabel("")
        self.tg_status.setObjectName("tgstatus")
        self.tg_status.setWordWrap(True)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("توکن بات:"))
        r1.addWidget(self.tg_token, 1)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("شناسه چت:"))
        r2.addWidget(self.tg_chat, 1)
        r2.addWidget(self.btn_getid)
        r3 = QHBoxLayout()
        r3.addWidget(self.chk_send)
        r3.addStretch(1)
        r3.addWidget(self.btn_test)
        hint = QLabel("راهنما: در تلگرام به @BotFather پیام بده، newbot/ را بزن و توکن را اینجا وارد کن — "
                      "سپس یک بار به بات خودت /start بفرست و «گرفتن خودکار شناسه» را بزن.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        tg_lay.addLayout(r1)
        tg_lay.addLayout(r2)
        tg_lay.addLayout(r3)
        tg_lay.addWidget(self.tg_status)
        tg_lay.addWidget(hint)
        root.addWidget(tg_card)

        # تب‌های گزارش
        self.tabs = QTabWidget()

        def _view(max_blocks: int | None = None) -> QPlainTextEdit:
            v = QPlainTextEdit()
            v.setReadOnly(True)
            if max_blocks:
                v.setMaximumBlockCount(max_blocks)
            else:
                v.setPlaceholderText("هنوز چیزی اینجا نیست — «▶ شروع ربات» یا «🔄 اجرای یک‌بار تحلیل» را بزن")
            return v

        self.log_view = _view(4000)
        self.report_view = _view()
        self.fund_view = _view()
        self.brief_view = _view()
        self.brief_view.setPlaceholderText("بریفینگ صبحگاهی هنوز ساخته نشده — دکمه «🌅 بریفینگ صبحگاهی» "
                                           "را بزن یا منتظر ساعت تنظیم‌شده در config.yaml بمان")
        self.TAB_LOG, self.TAB_REPORT, self.TAB_FUND, self.TAB_BRIEF = 0, 1, 2, 3
        self.tabs.addTab(self.log_view, "🟢 گزارش زنده")
        self.tabs.addTab(self.report_view, "📄 آخرین گزارش کامل")
        self.tabs.addTab(self.fund_view, "🏦 تقویم و اخبار")
        self.tabs.addTab(self.brief_view, "🌅 بریفینگ صبحگاهی")
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.tabs, 1)

        # پابرگ
        foot = QHBoxLayout()
        self.btn_cfg = QPushButton("⚙️ بازکردن فایل تنظیمات")
        self.btn_cfg.setObjectName("ghost")
        self.btn_cfg.clicked.connect(lambda: self._open_path(app_paths.config_path()))
        self.btn_logs = QPushButton("📂 پوشه لاگ‌ها")
        self.btn_logs.setObjectName("ghost")
        self.btn_logs.clicked.connect(lambda: self._open_path(app_paths.logs_dir()))
        foot.addWidget(self.btn_cfg)
        foot.addWidget(self.btn_logs)
        foot.addStretch(1)
        self.interval_lbl = QLabel("")
        self.interval_lbl.setObjectName("hint")
        foot.addWidget(self.interval_lbl)
        root.addLayout(foot)

        self.setCentralWidget(central)

    # ── وضعیت و رویدادها ──────────────────────────────────────
    def _set_pill_state(self, state: str) -> None:
        self.pill.setProperty("state", state)
        st = self.pill.style()
        st.unpolish(self.pill)
        st.polish(self.pill)

    def _log(self, msg: str) -> None:
        self.log_view.appendPlainText(msg)

    def _tick(self) -> None:
        now = time.time()
        self.clock_lbl.setText(f"🕒 {fa(time.strftime('%H:%M:%S'))}")
        running = self.loop.running
        once_busy = self.loop._once_running

        if running:
            self.pill.setText("🟢 در حال اجرا")
            self._set_pill_state("ok")
        elif once_busy:
            self.pill.setText("🔄 تحلیل یک‌باره...")
            self._set_pill_state("busy")
        else:
            self.pill.setText("⏹ متوقف")
            self._set_pill_state("idle" if not self.loop.state.get("last_error") else "err")

        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.btn_once.setEnabled(not once_busy)
        self.btn_brief.setEnabled(not once_busy)

        last = self.loop.state.get("last_run")
        self.last_run_lbl.setText(
            "آخرین تحلیل: " + (fa(time.strftime("%H:%M", time.localtime(last))) if last else "—"))
        nxt = self.loop.state.get("next_run")
        if running and nxt and nxt > now:
            rem = int(nxt - now)
            self.next_run_lbl.setText(f"تحلیل بعدی تا: {fa(f'{rem // 60:02d}:{rem % 60:02d}')}")
        else:
            self.next_run_lbl.setText("")
        self.interval_lbl.setText(
            f"⏱ فاصله تحلیل‌های خودکار: {fa(int(self.loop.interval_min))} دقیقه (قابل تغییر در config.yaml)")

        # ── وتوی خبری ────────────────────────────────────────
        vetoes = self.loop.state.get("last_vetoes") or []
        if vetoes:
            self.veto_lbl.setText("🚫 وتوی خبری فعال: " + "، ".join(vetoes)
                                  + " — تا ۳۰ دقیقه بعد از رویداد پراثر سیگنال صادر نمی‌شود")
        elif self.loop.state.get("last_run"):
            self.veto_lbl.setText("✅ وتوی خبری فعال نیست — پنجرهٔ صدور سیگنال باز است")
        else:
            self.veto_lbl.setText("")

        # ── وضعیت موتور فاندامنتال ───────────────────────────
        if self.loop.state.get("last_run"):
            cal_ok = self.loop.state.get("calendar_ok")
            n_news = int(self.loop.state.get("news_count") or 0)
            cal_txt = "تقویم ✅" if cal_ok else ("تقویم ⚠️" if cal_ok is False else "تقویم —")
            alerts = int(self.loop.state.get("alerts_sent") or 0)
            self.fund_lbl.setText(f"🏦 {cal_txt} | 📰 {fa(n_news)} خبر"
                                  + (f" | 🚨 {fa(alerts)} هشدار ارسال شد" if alerts else ""))
        else:
            self.fund_lbl.setText("")

        # ── بریفینگ بعدی ─────────────────────────────────────
        nb = self.loop.state.get("next_briefing")
        lb = self.loop.state.get("last_briefing")
        bits = []
        if lb:
            bits.append(f"آخرین: {fa(time.strftime('%H:%M', time.localtime(lb)))}")
        if nb and nb > now:
            b = time.localtime(nb)
            bits.append(f"بعدی: {fa(time.strftime('%H:%M', b))} UTC")
        self.brief_lbl.setText(("🌅 بریفینگ — " + " | ".join(bits)) if bits else "")

    def _fill(self, view: QPlainTextEdit, text: str, label: str,
              tab_idx: int, tab_text: str) -> None:
        """پر کردن یک تب و چشمک‌زدن کوتاه آن برای جلب توجه."""
        stamp = fa(time.strftime("%Y-%m-%d %H:%M:%S"))
        view.setPlainText(f"⟵ {label} — {stamp}\n\n{text}")
        self.tabs.setTabText(tab_idx, "🔔 جدید!")
        QTimer.singleShot(6000, lambda i=tab_idx, t=tab_text: self.tabs.setTabText(i, t))

    def _poll_queue(self) -> None:
        for _ in range(200):
            try:
                kind, payload = self.q.get_nowait()
            except queue.Empty:
                return
            if kind == "log":
                self._log(payload)
            elif kind == "report":
                self._fill(self.report_view, payload, "گزارش", self.TAB_REPORT, "📄 آخرین گزارش کامل")
            elif kind == "fundamental":
                self._fill(self.fund_view, payload, "تقویم اقتصادی و اخبار",
                           self.TAB_FUND, "🏦 تقویم و اخبار")
            elif kind == "briefing":
                self._fill(self.brief_view, payload, "بریفینگ صبحگاهی 🌅",
                           self.TAB_BRIEF, "🌅 بریفینگ صبحگاهی")
                self.tabs.setCurrentIndex(self.TAB_BRIEF)
            elif kind == "tg_msg":
                self.tg_status.setText(payload)
            elif kind == "tg_chatid":
                self.tg_chat.setText(payload)
                self._save_tg_fields()

    # ── دکمه‌ها ────────────────────────────────────────────────
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
            self._log("🌅 ساخت بریفینگ صبحگاهی آغاز شد (۱۰ تا ۳۰ ثانیه)...")

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
        self.tg_status.setText("⏳ در حال دریافت شناسه چت...")

        def work():
            ok, who = telegram.validate_token(token)
            if not ok:
                self.q.put(("tg_msg", f"❌ توکن نامعتبر است: {who}"))
                return
            cid, msg = telegram.get_chat_id(token)
            if cid:
                self.q.put(("tg_msg", f"✅ {msg} — شناسه وارد شد"))
                self.q.put(("tg_chatid", cid))
            else:
                self.q.put(("tg_msg", f"⚠️ {msg}"))
        threading.Thread(target=work, daemon=True).start()

    def _on_test_send(self) -> None:
        token = self.tg_token.text().strip()
        chat = self.tg_chat.text().strip()
        if not token or not chat:
            self.tg_status.setText("⚠️ توکن و شناسه چت را وارد کن (شناسه با دکمه «گرفتن خودکار»)")
            return
        self.tg_status.setText("⏳ در حال ارسال پیام تست...")

        def work():
            text = ("✅ پیام تست دستیار سیگنال فارکس\n"
                    "اگر این پیام را می‌بینی، تلگرام درست تنظیم شده است. 🎉\n"
                    f"نسخه {app_paths.APP_VERSION}")
            ok, msg = telegram.send_message(token, chat, text)
            self.q.put(("tg_msg", ("✅ پیام تست به تلگرامت ارسال شد! " if ok else "❌ ") + msg))
        threading.Thread(target=work, daemon=True).start()

    def _open_path(self, path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            self._log(f"[!] بازکردن مسیر ناموفق: {e}")

    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            self.loop.stop()
        except Exception:
            pass
        super().closeEvent(event)


# ── ورود و راه‌اندازی ──────────────────────────────────────────
def _selftest() -> int:
    """خودآزمون بدون پنجره (برای ماشین ساخت گیت‌هاب): GUI + موتور را بارگذاری می‌کند."""
    app_paths.fix_console_encoding()      # کنسول CI ویندوز cp1252 است — وگرنه print فارسی می‌شکند
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    fam = load_fonts()
    app.setFont(QFont(fam, 11))
    app.setStyleSheet(build_qss(fam))
    win = MainWindow()
    win.show()
    app.processEvents()
    # بررسی منطق غیرگرافیکی
    from src.notify.telegram import _chunks
    assert len(_chunks("x" * 9000)) >= 3, "تقسیم پیام تلگرام درست کار نمی‌کند"
    assert callable(run_cycle) and callable(run_briefing) and callable(check_event_alerts)

    # تب‌های پنل باید سر جایشان باشند (ایندکس‌ها در کد استفاده می‌شوند)
    assert win.tabs.count() == 4, f"انتظار ۴ تب، {win.tabs.count()} پیدا شد"
    assert (win.TAB_LOG, win.TAB_REPORT, win.TAB_FUND, win.TAB_BRIEF) == (0, 1, 2, 3)

    # موتور فاندامنتال باید بدون اینترنت هم پارس/رندر کند
    from src.fundamental import calendar as cal
    from src.fundamental import news as nw
    from src.report.fundamental import render_calendar, render_news

    evs = cal.parse_events([{"country": "USD", "date": "2026-09-16T14:00:00-04:00",
                             "title": "Federal Funds Rate", "impact": "High",
                             "forecast": "4.00%", "previous": "3.75%"}])
    assert len(evs) == 1 and evs[0].when.hour == 18, "پارس/تبدیل زمانی تقویم اشتباه است"
    sc, direction, _kw, _b, _r = nw.score_text("USDJPY surges as the BOJ hike disappoints")
    assert direction == {"USD": 1, "JPY": -1}, f"جهت‌دهی اخبار اشتباه: {direction}"
    assert sc >= 3, f"امتیاز خبر خیلی کم است: {sc}"
    assert "تقویم اقتصادی" in render_calendar(cal.CalendarSnapshot(events=evs, fetched=True),
                                              [{"name": "USDJPY", "base": "USD", "quote": "JPY"}])
    assert "اخبار بازار" in render_news(nw.NewsSnapshot(error="offline"))

    win.close()
    print(f"SELFTEST OK — فونت: {fam} | تب‌ها: {win.tabs.count()} | پنجره: {win.windowTitle()}")
    return 0


def main() -> None:
    # پیش از هر print فارسی — بدون این، روی کنسول ویندوز (cp1252) اولین
    # print لایهٔ داده UnicodeEncodeError می‌دهد و بی‌صدا کل داده از کار می‌افتد
    app_paths.fix_console_encoding()

    if "--selftest" in sys.argv:
        sys.exit(_selftest())

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setLayoutDirection(Qt.RightToLeft)

    # تک‌نمونه: جلوگیری از اجرای همزمان دو پنل
    guard = QSharedMemory("ForexAssistant_SingleInstance_Guard_v1")
    if not guard.create(1):
        if guard.attach():
            guard.detach()
        if not guard.create(1):
            QMessageBox.warning(None, "دستیار سیگنال فارکس",
                                "برنامه از قبل در حال اجراست! (یک پنجره دیگر باز است)")
            sys.exit(0)
    app._single_instance_guard = guard  # نگه داشتن مرجع تا آزاد نشود  # noqa: SLF001

    fam = load_fonts()
    app.setFont(QFont(fam, 11))
    app.setStyleSheet(build_qss(fam))

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
