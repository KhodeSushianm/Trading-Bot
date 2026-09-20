# -*- coding: utf-8 -*-
"""تولید اسکرین‌شات‌های رسمی پروژه برای README و docs (آفلاین، بدون شبکه).

خروجی‌ها در ``docs/images/``:
    splash.png            — اسپلش خوش‌آمدگویی (برند ODIN)
    panel-dashboard.png   — داشبورد با دادهٔ نمونه
    panel-signals.png     — صفحهٔ سیگنال‌ها با یک سیگنال نمونه + خلاصهٔ داور
    panel-settings.png    — صفحهٔ تنظیمات

داده‌ها نمونهٔ نمایشی‌اند (نه سیگنال واقعی) و فقط برای بازبینی چشمی رابط‌کاربری
ساخته می‌شوند. اعداد با قالب واقعی گزارش‌ها از طریق همان توکن render در
``src/report/signal.py`` تولید می‌شوند تا اسکرین‌شات با خروجی واقعی یکی باشد.

کاربرد:
    QT_QPA_PLATFORM=offscreen python3 tests/manual/render_shots.py
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
IMG = ROOT / "docs" / "images"

from PySide6.QtCore import QPoint, QRect, Qt  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import panel as P  # noqa: E402
from src import app_paths  # noqa: E402
from src.judge.scoring import Evidence, Judgment, Signal, Veto  # noqa: E402
from src.report.signal import render_judge_summary, render_signal  # noqa: E402
from src.ui.splash import WelcomeSplash  # noqa: E402

W, H = 1280, 900


def _pump(app: QApplication, seconds: float) -> None:
    """چرخاندن حلقهٔ رویداد تا انیمیشن‌های محو کامل شوند."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        app.thread().msleep(16)


# ══════════════════════════════════════════════════════════════
#  دادهٔ نمونه (نمایشی)
# ══════════════════════════════════════════════════════════════
def mock_signal() -> Signal:
    now = datetime.now(timezone.utc)
    evs = [
        Evidence("trend", "هم‌راستایی روند ۴ ساعته و ۱ ساعته", 2, 2,
                 "روند صعودی و تایم‌فریم ۱ ساعته هم تایید می‌کند؛ ADX=28 → روند قوی", ok=True),
        Evidence("level", "واکنش به سطح کلیدی (حمایت)", 2, 2,
                 "قیمت روی حمایت 180.90؛ سایهٔ کندل H4 آن را لمس کرد و بالای آن بست", ok=True),
        Evidence("fundamental", "پنجرهٔ فاندامنتال پاک", 2, 2,
                 "هیچ رویداد مهم CHF/JPY در ۶ ساعت آینده (تقویم اقتصادی)", ok=True),
        Evidence("momentum", "تایید مومنتوم (RSI)", 1, 1,
                 "RSI(H1)=42 — در منطقهٔ پولبک و رو به بالا", ok=True),
        Evidence("strength", "هم‌جهتی جریان قدرت ارزها", 1, 1,
                 "CHF قوی‌ترین (+0.56) و JPY ضعیف‌ترین (−0.72) — جهت با جریان قدرت یکی است", ok=True),
        Evidence("news", "تایید خبری", 0, 1,
                 "خبر هم‌جهت با معامله در ۲ ساعت اخیر پیدا نشد (امتیازی نگرفت، وتو هم نکرد)"),
        Evidence("tv", "هم‌جهتی با تریدینگ‌ویو", 1, 1,
                 "خلاصهٔ تکنیکال تریدینگ‌ویو در H1: خرید", ok=True),
        Evidence("session", "زمان‌بندی مناسب (سشن)", 1, 1,
                 "سشن لندن/نیویورک — بیشترین نقدینگی و کمترین اسپرد هفته", ok=True),
    ]
    return Signal(
        symbol="CHFJPY", fa_name="فرانک سوئیس / ین ژاپن", direction="BUY",
        score=sum(e.points for e in evs), max_score=sum(e.max_points for e in evs),
        stars=5, entry=181.420, sl=180.980, tp=182.520, pip=0.01,
        atr=0.185, risk_pips=44.0, reward_pips=110.0, rr=2.5,
        is_gold=False, session_fa="لندن/نیویورک", now=now,
        evidences=evs,
        warnings=["جفت‌ارز متقاطع CHF — اسپرد کمی بزرگ‌تر از جفت‌ارزهای اصلی است"],
        sid="demo-0001",
    )


def mock_judgments(sig: Signal) -> list[Judgment]:
    j_sig = Judgment(symbol=sig.symbol, fa_name=sig.fa_name, direction="BUY",
                     score=sig.score, max_score=sig.max_score, signal=sig,
                     price=sig.entry, pip=sig.pip)
    j_veto = Judgment(
        symbol="XAUUSD", fa_name="طلا / دلار آمریکا", direction="BUY",
        price=2612.40, pip=0.01,
        vetoes=[Veto("high_impact_event", "رویداد پراهمیت پیش رو",
                     "CPI آمریکا در ۴۵ دقیقه آینده (اهمیت بالا) — معاملهٔ طلا در این "
                     "پنجره قمار است، نه تحلیل")],
        reject_reason="VETO")
    j_low = Judgment(
        symbol="EURUSD", fa_name="یورو / دلار آمریکا", direction="SELL",
        score=5, max_score=11, price=1.0842, pip=0.0001,
        evidences=[
            Evidence("trend", "هم‌راستایی روند ۴ ساعته و ۱ ساعته", 2, 2,
                     "روند نزولی و H1 هم تایید می‌کند؛ ADX=23 → روند متوسط", ok=True),
            Evidence("level", "واکنش به سطح کلیدی (مقاومت)", 2, 2,
                     "قیمت زیر مقاومت 1.0880 پس‌زده شد", ok=True),
            Evidence("fundamental", "پنجرهٔ فاندامنتال پاک", 1, 2,
                     "یک رویداد اهمیت متوسط EUR در ۲ ساعت آینده — نیمهٔ امتیاز", ok=True),
            Evidence("momentum", "تایید مومنتوم (RSI)", 0, 1,
                     "RSI(H1)=54 — هنوز در منطقهٔ اصلاح رو به بالا نیست"),
            Evidence("strength", "هم‌جهتی جریان قدرت ارزها", 0, 1,
                     "EUR ضعیف‌تر از USD نیست — جریان قدرت، فروش را تایید نمی‌کند"),
        ],
        reject_reason="LOW_SCORE",
        reject_detail="امتیاز ۵ از ۱۱ — زیر آستانهٔ ۷")
    j_no = Judgment(
        symbol="GBPUSD", fa_name="پوند / دلار آمریکا", direction=None,
        price=1.2918, pip=0.0001, reject_reason="NO_SETUP",
        reject_detail="روند نزولی است ولی RSI=51 در منطقهٔ اصلاح رو به بالا نیست")
    return [j_sig, j_veto, j_low, j_no]


def mock_dash_state() -> dict:
    now = time.time()
    return {
        "last_run": now - 180,
        "last_error": None,
        "last_vetoes": ["رویداد پراهمیت پیش رو"],
        "calendar_ok": True,
        "news_count": 4,
        "signals_total": 2,
        "last_signals": [
            {"symbol": "CHFJPY", "direction": "BUY", "score": 10,
             "max_score": 11, "sent": True},
            {"symbol": "EURUSD", "direction": "SELL", "score": 7,
             "max_score": 11, "sent": True},
        ],
        "ranking": [("CHF", 0.56), ("EUR", 0.21), ("GBP", 0.05), ("AUD", -0.08),
                    ("NZD", -0.22), ("CAD", -0.41), ("USD", -0.55), ("JPY", -0.72)],
        "upcoming": [
            {"title_fa": "سخنرانی لاگارد (رئیس بانک مرکزی اروپا)",
             "country_fa": "منطقه یورو", "minutes": 1889, "impact": "MEDIUM"},
            {"title_fa": "BOC Gov Macklem Speaks",
             "country_fa": "کانادا", "minutes": 1794, "impact": "MEDIUM"},
            {"title_fa": "RBA Gov Bullock Speaks",
             "country_fa": "استرالیا", "minutes": 2515, "impact": "HIGH"},
        ],
    }


# ══════════════════════════════════════════════════════════════
#  رندر
# ══════════════════════════════════════════════════════════════
def main() -> int:
    P.app_paths.fix_console_encoding()
    IMG.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setLayoutDirection(Qt.RightToLeft)
    fam = P.load_fonts()
    app.setFont(QFont(fam, 11))
    app.setStyleSheet(P.build_qss(fam, check_img=P._check_img()))

    # ── اسپلش ─────────────────────────────────────────────────
    sp = WelcomeSplash(user_name="سوشیان", version=app_paths.APP_VERSION,
                       app_name=app_paths.APP_NAME,
                       tagline="دستیار تحلیل و سیگنال فارکس", t=P.T)
    sp._center()                                             # noqa: SLF001
    sp.show()
    _pump(app, 1.6)
    shot = sp.grab()
    cg = sp._card.frameGeometry()                            # noqa: SLF001
    cx, cy = cg.center().x(), cg.center().y()
    cw, ch = 760, 500
    r = QRect(cx - cw // 2, cy - ch // 2, cw, ch)
    r = r.intersected(QRect(0, 0, shot.width(), shot.height()))
    ok = shot.copy(r).save(str(IMG / "splash.png"))
    print("splash.png", ok, r.width(), "x", r.height())

    # ── پنجرهٔ اصلی ───────────────────────────────────────────
    win = P.MainWindow(show_splash=False)
    win.resize(W, H)
    win.loop.state.update(mock_dash_state())
    type(win.loop).running = property(lambda self: True)     # noqa: ARG005
    win._tick()                                              # noqa: SLF001
    win.show()
    _pump(app, 0.9)
    win._tick()                                              # noqa: SLF001
    app.processEvents()
    ok = win.grab().save(str(IMG / "panel-dashboard.png"))
    print("panel-dashboard.png", ok)

    # ── صفحه سیگنال‌ها ─────────────────────────────────────────
    sig = mock_signal()
    text = render_signal(sig) + "\n\n" + render_judge_summary(mock_judgments(sig),
                                                              min_score=7)
    win._fill(win.sig_view, text, win.TAB_SIGNAL, "سیگنال‌ها")  # noqa: SLF001
    win.nav._select(win.TAB_SIGNAL)                           # noqa: SLF001
    _pump(app, 0.9)
    ok = win.grab().save(str(IMG / "panel-signals.png"))
    print("panel-signals.png", ok)

    # ── صفحهٔ تنظیمات ──────────────────────────────────────────
    win.nav._select(win.TAB_SETTINGS)                         # noqa: SLF001
    _pump(app, 0.9)
    ok = win.grab().save(str(IMG / "panel-settings.png"))
    print("panel-settings.png", ok)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
