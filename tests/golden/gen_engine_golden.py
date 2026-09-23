# -*- coding: utf-8 -*-
"""تولیدکنندهٔ فایل طلایی `run_cycle` — فاز ۳ (سوییچ engine به registry).

ایده (انضباط «اول میخ، بعد چکش»):
  ۱) این اسکریپت یک چرخهٔ کامل `run_cycle` را با دادهٔ **ساختگیِ قطعی** و
     **بدون شبکه** روی engine *فعلی* اجرا می‌کند و نتیجهٔ نرمال‌شده را در
     tests/golden/run_cycle_golden.json ضبط می‌کند (قبل از سوییچ).
  ۲) tests/test_engine_switch.py همان اجرا را تکرار و با فایل طلایی مقایسه
     می‌کند. بعد از سوییچِ فاز ۳، تست باید **بدون هیچ تغییری** سبز بماند —
     یعنی خروجی سیستم عوض نشده است.

اجرا (برای ضبط/بازتولید عمدیِ طلایی — فقط با دلیل موجه):
    python tests/golden/gen_engine_golden.py

⚠️ seamهای پچ عمداً «مستقل از نسخه» انتخاب شده‌اند تا همین هارنس قبل و بعد
   از سوییچ معتبر باشد:
     • YahooSource.connect/fetch/disconnect (پچ سطح کلاس — هر دو نسخه از
       همان کلاس استفاده می‌کنند)
     • src.notify.telegram.send_message (engine از attribute ماژول در زمان
       فراخوانی می‌خواند)
     • src.app_paths.* (همهٔ مصرف‌کنندگان یک ماژول را share دارند)
     • توابع شبکه‌ای TV/تقویم/خبر در **دو** seam پچ می‌شوند: نامِ bound در
       engine (نسخهٔ فعلی) و تابع ماژول (نسخهٔ پلاگین‌محور، import تنبل) —
       هرکدام وجود داشته باشد.
"""
from __future__ import annotations

import contextlib
import copy
import dataclasses
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

GOLDEN_PATH = HERE / "run_cycle_golden.json"
NOW = datetime(2026, 9, 16, 14, 30, tzinfo=timezone.utc)   # چهارشنبه — هم‌پوشانی لندن/NY

# قیمت پایهٔ قطعی به‌ازای هر نماد (بدون تصادف)
BASES = {"EURUSD": 1.1000, "GBPUSD": 1.3000, "USDJPY": 150.00, "USDCAD": 1.3600,
         "AUDUSD": 0.6600, "USDCHF": 0.8800, "XAUUSD": 2400.0}


# ══════════════════════════════════════════════════════════════
#  دادهٔ ساختگیِ قطعی
# ══════════════════════════════════════════════════════════════
def _mk_frame(n: int, base: float, freq: str, drift: float = 0.0):
    import pandas as pd
    idx = pd.date_range("2026-08-01", periods=n, freq=freq)
    close = [base + drift * i + 0.00012 * base * ((i * 7) % 11 - 5) for i in range(n)]
    return pd.DataFrame({"Open": [c - 0.0001 * base for c in close],
                         "High": [c + 0.0004 * base for c in close],
                         "Low": [c - 0.0004 * base for c in close],
                         "Close": close}, index=idx)


def _mk_frame_pullback(n: int, base: float, freq: str):
    """الگوی «روند صعودی + پولبک + برگشت» — برای اینکه ستاپ خریدِ EURUSD
    دروازه‌های داور (RSI<45 و رو به بالا در روند صعودی) را با دادهٔ قطعی پاس
    کند. سه فاز: صعود بلند ← اصلاح کوتاه ← برگشت ملایم."""
    import pandas as pd
    idx = pd.date_range("2026-08-01", periods=n, freq=freq)
    cut1, cut2 = int(n * 0.84), int(n * 0.94)
    close, last = [], base
    for i in range(n):
        if i < cut1:
            step = 0.00055 * base                       # صعود پایدار
        elif i < cut2:
            step = -0.0016 * base                        # پولبک (RSI ≈ ۴۰ — منطقهٔ ستاپ خرید)
        else:
            step = 0.00035 * base                        # برگشت ملایم (rsi_rising=True)
        last = last + step + 0.00008 * base * ((i * 7) % 9 - 4)
        close.append(last)
    return pd.DataFrame({"Open": [c - 0.0001 * base for c in close],
                         "High": [c + 0.0004 * base for c in close],
                         "Low": [c - 0.0004 * base for c in close],
                         "Close": close}, index=idx)


def make_market_data(symbol: str):
    """MarketData ساختگی و قطعی. EURUSD الگوی پولبک دارد (ستاپ خرید)؛
    بقیهٔ نمادها زیگزاگ ملایم (داور صادقانه ردشان می‌کند — همان چیزی که
    طلایی ثبت می‌کند)."""
    from src.data.base import MarketData
    base = BASES.get(symbol, 1.0)
    if symbol == "EURUSD":
        return MarketData(symbol=symbol,
                          m15=_mk_frame_pullback(260, base, "15min"),
                          h1=_mk_frame_pullback(260, base, "1h"),
                          h4=_mk_frame_pullback(260, base, "4h"))
    return MarketData(symbol=symbol,
                      m15=_mk_frame(260, base, "15min", drift=0.00002 * base),
                      h1=_mk_frame(260, base, "1h", drift=0.00008 * base),
                      h4=_mk_frame(260, base, "4h", drift=0.0003 * base))


def make_calendar_snapshot():
    from src.fundamental.calendar import CalendarEvent, CalendarSnapshot
    evs = [
        # رویداد USD عمداً +۷ ساعت: بیرون از پنجرهٔ وتو (۳۰ دقیقه) *و* بیرون
        # از پنجرهٔ «تمیز» فاندامنتال (۶ ساعت) — تا ستاپِ دادهٔ ساختگی با
        # دروازه‌های واقعی داور سنجیده شود، نه با تقویم خالی.
        CalendarEvent(when=NOW + timedelta(hours=7), country="USD",
                      title="Federal Funds Rate", title_fa="نرخ بهرهٔ فدرال",
                      impact="HIGH", forecast="4.00%", previous="4.00%",
                      category="نرخ بهره و بانک مرکزی", polarity=1, source="golden"),
        CalendarEvent(when=NOW + timedelta(hours=20), country="EUR",
                      title="CPI y/y", title_fa="تورم سالانه (CPI)",
                      impact="HIGH", forecast="2.1%", previous="2.0%",
                      category="تورم و قیمت‌ها", polarity=1, source="golden"),
    ]
    return CalendarSnapshot(events=evs, fetched_at=NOW, source="golden", fetched=True)


def make_news_snapshot():
    from src.fundamental.news import NewsItem, NewsSnapshot
    item1 = NewsItem(title="ECB officials signal further rate hike ahead",
                     link="https://example.com/ecb", source="TestFeed",
                     published=NOW - timedelta(hours=1), score=6,
                     direction={"EUR": 1}, keywords=["ecb", "rate"],
                     breaking=False, roundup=False, summary="", age_minutes=60.0)
    item2 = NewsItem(title="Euro zone manufacturing beats estimates",
                     link="https://example.com/eur-pmi", source="TestFeed2",
                     published=NOW - timedelta(hours=3), score=5,
                     direction={"EUR": 1}, keywords=["eur", "pmi"],
                     breaking=False, roundup=False, summary="", age_minutes=180.0)
    return NewsSnapshot(items=[item1, item2], fetched_at=NOW, feeds_ok=3,
                        feeds_failed=0, raw_count=2)


def make_tv_map(symbol_names):
    from src.data.tradingview import TVSnapshot
    return {s: TVSnapshot(symbol=s, close=BASES.get(s, 1.0), rsi=55.0, adx=24.0,
                          recommendation="BUY", buy=12, sell=3, neutral=5,
                          timeframe="4h") for s in symbol_names}


def make_cfg():
    from src.config import load_config
    cfg = copy.deepcopy(load_config())
    cfg["data_source"] = "yahoo"                  # seam مستقیم YahooSource (هر دو نسخه)
    cfg["telegram"] = {"send_reports": True, "bot_token": "123:fake-token",
                       "chat_id": "42"}
    return cfg


# ══════════════════════════════════════════════════════════════
#  نرمال‌سازی (برای مقایسهٔ قطعی و JSON)
# ══════════════════════════════════════════════════════════════
def normalize(obj):
    """dataclass→dict، datetime→iso، tuple→list؛ بازگوشی و قطعی."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return normalize(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {str(k): normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [normalize(x) for x in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


_TS_PREFIX = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]\s?")
_ELAPSED = re.compile(r"\(\d+ ثانیه")


def normalize_logs(logs):
    """پیشوند زمانی و عددِ «N ثانیه» (elapsed واقعی) حذف/یکسان می‌شوند."""
    out = []
    for ln in logs:
        ln = _TS_PREFIX.sub("", ln)
        ln = _ELAPSED.sub("(N ثانیه", ln)
        out.append(ln)
    return out


def normalize_result(result):
    r = normalize(result)
    r.pop("elapsed", None)          # تنها فیلد ذاتاً فرار
    return r


# ══════════════════════════════════════════════════════════════
#  هارنس اجرای چرخه با mock (بدون شبکه)
# ══════════════════════════════════════════════════════════════
def _has_attr(dotted: str) -> bool:
    mod_name, _, attr = dotted.rpartition(".")
    try:
        import importlib
        mod = importlib.import_module(mod_name)
    except Exception:
        return False
    return hasattr(mod, attr)


def run_mock_cycle(tmpdir, cfg=None):
    """run_cycle با دادهٔ ساختگی روی هر نسخهٔ engine → (result, logs).

    tmpdir: مسیر دیتادایر/لاگ/کش ایزوله (tmp).
    """
    from unittest import mock

    import src.app_paths as app_paths
    from src import engine
    from src.data import yahoo_source

    tmp = Path(tmpdir)
    data_dir, logs_dir, cache_dir = tmp / "data", tmp / "logs", tmp / "cache"
    for d in (data_dir, logs_dir, cache_dir):
        d.mkdir(parents=True, exist_ok=True)

    cfg = cfg or make_cfg()
    symbols = [s["name"] for s in cfg["symbols"]]
    tv_map = make_tv_map(symbols)
    cal_snap = make_calendar_snapshot()
    news_snap = make_news_snapshot()
    logs: list = []

    sent_messages: list = []

    def fake_send_message(token, chat_id, text, timeout=15):
        sent_messages.append({"token": token, "chat_id": chat_id, "len": len(text)})
        return True, "OK-mock"

    def fake_fetch(self, sym_cfg):
        return make_market_data(sym_cfg["name"])

    with contextlib.ExitStack() as st:
        # ── seamهای مستقل از نسخه ──
        st.enter_context(mock.patch.object(yahoo_source.YahooSource, "connect",
                                           lambda self: None))
        st.enter_context(mock.patch.object(yahoo_source.YahooSource, "disconnect",
                                           lambda self: None))
        st.enter_context(mock.patch.object(yahoo_source.YahooSource, "fetch", fake_fetch))
        st.enter_context(mock.patch("src.notify.telegram.send_message", fake_send_message))
        st.enter_context(mock.patch.object(app_paths, "data_dir", return_value=data_dir))
        st.enter_context(mock.patch.object(app_paths, "logs_dir", return_value=logs_dir))
        st.enter_context(mock.patch.object(app_paths, "cache_dir", return_value=cache_dir))
        st.enter_context(mock.patch.object(app_paths, "sent_alerts_path",
                                           return_value=cache_dir / "sent_alerts.json"))
        # ── seamهای دوتایی: نام bound در engine فعلی + تابع ماژول (نسخهٔ پلاگینی) ──
        for target, ret in (("fetch_tv_snapshot", tv_map),
                            ("fetch_calendar", cal_snap),
                            ("fetch_news", news_snap)):
            mod_target = {"fetch_tv_snapshot": "src.data.tradingview.fetch_tv_snapshot",
                          "fetch_calendar": "src.fundamental.calendar.fetch_calendar",
                          "fetch_news": "src.fundamental.news.fetch_news"}[target]
            st.enter_context(mock.patch(mod_target, return_value=ret))
            if _has_attr(f"src.engine.{target}"):
                st.enter_context(mock.patch(f"src.engine.{target}", return_value=ret))

        result = engine.run_cycle(cfg, on_log=logs.append, now_override=NOW)

    return result, logs, sent_messages


# ══════════════════════════════════════════════════════════════
def build_golden() -> dict:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        result, logs, sent = run_mock_cycle(td)
    return {"result": normalize_result(result),
            "logs": normalize_logs(logs),
            "sent_messages": sent}


def main() -> int:
    g1 = build_golden()
    g2 = build_golden()          # اجرای دوم: اثبات قطعیتِ خودِ هارنس
    if g1 != g2:
        print("❌ خروجی چرخهٔ mock قطعی نیست — قبل از ضبط، ناپایداری را پیدا کنید")
        return 1
    n_sig = len(g1["result"].get("signals") or [])
    GOLDEN_PATH.write_text(json.dumps(g1, ensure_ascii=False, sort_keys=True, indent=1),
                           encoding="utf-8")
    print(f"✅ طلایی ضبط شد: {GOLDEN_PATH.name} — ok={g1['result']['ok']}, "
          f"signals={n_sig}, judgments={g1['result']['judgments']}, "
          f"{len(g1['logs'])} خط لاگ، {len(g1['sent_messages'])} ارسال تلگرام(mock)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
