# -*- coding: utf-8 -*-
"""باتری سناریوهای قطعیِ tracker — منبعِ مشترکِ طلایی و تست.

چرا این فایل جدا است؟ پیش‌تر تنها پوششِ ``resolve_open_signals`` در
``tests/manual/test_journal.py`` بود که **در CI اجرا نمی‌شد**. همین باعث شد
باگِ «ورودِ کهنه / پنجرهٔ کور» (v0.29) ناشناخته بماند. این باتری:

  • کاملاً آفلاین و قطعی (کندل‌ها مصنوعی، زمان تزریق‌شده)
  • به‌صورت JSON سریال‌شدنی → همان سناریوها در موتور JS هم قابل اجراست
    (پاریتی بایت‌به‌بایت، مطابق قراردادِ دو موتور)
  • توسط ``tests/golden/gen_tracker_golden.py`` ضبط می‌شود و توسط
    ``tests/test_tracker.py`` بازپخش و مقایسه می‌شود

قاعدهٔ ریپو: این فایل «میخ» است. افزودن سناریو آزاد است؛ تغییرِ سناریوی
موجود فقط با دلیلِ مکتوب و بازضبطِ عمدیِ طلایی.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from src.data.base import MarketData
from src.journal.store import Journal
from src.journal.tracker import resolve_open_signals

# ── زمان‌های پایه (ثابت و قطعی) ─────────────────────────────────
T0 = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
# «now» نزدیک به T0 — برای سناریوهایی که باید *باز* بمانند و ناخواسته
# از پنجرهٔ انقضای ۴۸ ساعته نگذرند.
NOW_NEAR = T0 + timedelta(hours=2)

STEP_MIN = 15

CFG_STD = {"journal": {"enabled": True, "expiry_hours": 48,
                       "conservative_both_touch": True}}
CFG_OPTIMISTIC = {"journal": {"enabled": True, "expiry_hours": 48,
                              "conservative_both_touch": False}}
CFG_DISABLED = {"journal": {"enabled": False}}


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def signal(sid: str, symbol: str, direction: str, entry: float, sl: float,
           tp: float, ts: datetime, *, rr: float = 2.0, risk_pips: float = 20.0,
           pip: float = 0.0001, score: int = 8, entry_ts=None,
           rules_version=None) -> dict:
    """یک رکورد ``kind=signal`` — همان قالبی که ``Signal.to_journal`` می‌نویسد."""
    rec = {
        "kind": "signal", "id": sid, "ts": _iso(ts), "symbol": symbol,
        "direction": direction, "entry": entry, "sl": sl, "tp": tp, "pip": pip,
        "atr": round(abs(entry - sl) / 1.5, 6),
        "risk_pips": risk_pips, "reward_pips": risk_pips * rr, "rr": rr,
        "score": score, "max_score": 11, "session": "لندن",
        "evidences": ["trend:2/2", "level:2/2", "fundamental:2/2", "news:0/1"],
        "strategies": ["trend_pullback"], "sent": True,
    }
    # فیلدهای اختیاری: رکوردهای قدیمی اینها را ندارند و باید دقیقاً مثل قبل
    # رفتار کنند (سازگاریِ backward — پینِ صریح)
    if entry_ts is not None:
        rec["entry_ts"] = _iso(entry_ts) if isinstance(entry_ts, datetime) else entry_ts
    if rules_version is not None:
        rec["rules_version"] = rules_version
    return rec


def dataset(symbol: str, start: datetime, bars: list) -> dict:
    """bars: فهرست [high, low, close] با گامِ ۱۵ دقیقه از start."""
    return {"symbol": symbol, "start": _iso(start), "step_min": STEP_MIN,
            "bars": [[float(b[0]), float(b[1]), float(b[2])] for b in bars]}


def _build_md(spec: dict) -> MarketData:
    idx = pd.date_range(datetime.fromisoformat(spec["start"]),
                        periods=len(spec["bars"]),
                        freq=f"{spec['step_min']}min", tz="UTC")
    df = pd.DataFrame(spec["bars"], columns=["High", "Low", "Close"], index=idx)
    df["Open"] = df["Close"]
    return MarketData(symbol=spec["symbol"], m15=df, h1=df, h4=df)


def run_scenario(sc: dict) -> dict:
    """یک سناریو را اجرا و نتیجه را **سریال‌شدنی** برمی‌گرداند.

    خروجی فقط شامل فیلدهایی است که در فایل طلایی پایدارند (بدون اشیاء زنده).
    """
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        jr = Journal(Path(tmp) / "signals.jsonl")
        for rec in sc.get("signals", []):
            jr.append(rec)

        datasets = {d["symbol"]: _build_md(d) for d in sc.get("datasets", [])}
        now = datetime.fromisoformat(sc["now"])
        cfg = sc.get("cfg", CFG_STD)

        logs: list = []
        resolved = resolve_open_signals(jr, datasets, now=now, cfg=cfg,
                                        on_log=logs.append)
        # فراخوانی دوم: idempotency — هیچ‌چیز نباید دوباره بسته شود
        resolved2 = resolve_open_signals(jr, datasets, now=now, cfg=cfg,
                                         on_log=lambda _m: None)

        out = {"resolved_first_call": [e.id for e in resolved],
               "resolved_second_call": [e.id for e in resolved2],
               "logs": logs, "entries": {}}
        for e in jr.load():
            row = {"is_open": e.is_open, "outcome": e.outcome,
                   "close_price": e.close_price, "r": e.r, "note": e.note}
            # فیلدهای v0.29 — فقط اگر موجود باشند (رکوردهای قدیمی: غایب)
            for extra in ("net_r", "mfe_r", "mae_r", "rules_version", "entry_ts"):
                v = getattr(e, extra, None)
                if v is not None:
                    row[extra] = v.isoformat() if isinstance(v, datetime) else v
            out["entries"][e.id] = row
        return out


# ══════════════════════════════════════════════════════════════
#  باتری سناریوها
# ══════════════════════════════════════════════════════════════
def scenarios() -> list:
    S = []
    bar0 = T0 + timedelta(minutes=15)

    # ── ۱) پایه: هدف / حد ضرر / برخورد دوگانه / انقضا / باز ──────
    S.append({
        "name": "base_outcomes",
        "now": _iso(NOW), "cfg": CFG_STD,
        "signals": [
            signal("buy_tp", "EURUSD", "BUY", 1.1000, 1.0980, 1.1040, T0),
            signal("sell_tp", "GBPUSD", "SELL", 1.3000, 1.3020, 1.2960, T0),
            signal("buy_sl", "USDJPY", "BUY", 150.00, 149.80, 150.40, T0, pip=0.01),
            signal("both_touch", "USDCAD", "BUY", 1.3500, 1.3480, 1.3540, T0),
            signal("expired", "AUDUSD", "BUY", 0.7000, 0.6980, 0.7040,
                   NOW - timedelta(hours=60)),
            signal("still_open", "USDCHF", "BUY", 0.8200, 0.8180, 0.8240,
                   NOW - timedelta(hours=2)),
        ],
        "datasets": [
            dataset("EURUSD", bar0, [[1.1010, 1.0995, 1.1005], [1.1045, 1.1020, 1.1040]]),
            dataset("GBPUSD", bar0, [[1.2990, 1.2955, 1.2960]]),
            dataset("USDJPY", bar0, [[150.10, 149.75, 149.80]]),
            dataset("USDCAD", bar0, [[1.3545, 1.3475, 1.3500]]),
            dataset("AUDUSD", NOW - timedelta(hours=60),
                    [[0.7010, 0.6990, 0.7005], [0.7012, 0.6995, 0.7010]]),
            dataset("USDCHF", NOW - timedelta(hours=2), [[0.8210, 0.8190, 0.8205]]),
        ],
    })

    # ── ۲) برخورد دوگانه با conservative=false → خوش‌بینانه TP ────
    S.append({
        "name": "both_touch_optimistic",
        "now": _iso(NOW), "cfg": CFG_OPTIMISTIC,
        "signals": [signal("bt", "USDCAD", "BUY", 1.3500, 1.3480, 1.3540, T0)],
        "datasets": [dataset("USDCAD", bar0, [[1.3545, 1.3475, 1.3500]])],
    })

    # ── ۳) ژورنال غیرفعال → هیچ چیز بسته نمی‌شود ────────────────
    S.append({
        "name": "journal_disabled",
        "now": _iso(NOW), "cfg": CFG_DISABLED,
        "signals": [signal("x", "EURUSD", "BUY", 1.1000, 1.0980, 1.1040, T0)],
        "datasets": [dataset("EURUSD", bar0, [[1.1045, 1.1020, 1.1040]])],
    })

    # ── ۴) دادهٔ نماد در دسترس نیست + گذشته از پنجرهٔ انقضا ──────
    #     R=0 صادقانه (نه «بازِ ابدی» که کارنامه را خوش‌بینانه نگه دارد)
    S.append({
        "name": "expired_no_data",
        "now": _iso(NOW), "cfg": CFG_STD,
        "signals": [signal("nodata", "XAUUSD", "BUY", 2600.0, 2590.0, 2620.0,
                           NOW - timedelta(hours=72), pip=0.1, risk_pips=100.0)],
        "datasets": [],
    })

    # ── ۵) کندلِ هم‌مرز با ts رد می‌شود (bar.t <= ts → skip) ─────
    #     پینِ صریحِ رفتارِ فعلی: کندلی که دقیقاً روی ts باز می‌شود دیده نمی‌شود
    S.append({
        "name": "bar_at_ts_is_skipped",
        "now": _iso(NOW_NEAR), "cfg": CFG_STD,
        "signals": [signal("edge", "EURUSD", "BUY", 1.1000, 1.0980, 1.1040,
                           T0 + timedelta(minutes=15))],
        # اولین کندل دقیقاً روی ts باز می‌شود و TP را می‌زند؛ دومی هیچ
        "datasets": [dataset("EURUSD", T0 + timedelta(minutes=15),
                             [[1.1050, 1.1000, 1.1045], [1.1010, 1.0995, 1.1005]])],
    })

    # ── ۶) 🔴 بایاسِ ورودِ کهنه — سودِ بیش‌برآوردشده ──────────────
    #     entry=1.1000 قیمتِ کهنهٔ H1 است. سیگنال در T0+47 صادر شده و
    #     تازه‌ترین قیمتِ واقعیِ آن لحظه (بستهٔ M15 با نمایهٔ T0+30) برابرِ
    #     1.1030 است. TP=1.1040 فقط ۱۰ پیپ بالاترِ قیمتِ واقعی است، ولی
    #     ژورنال ۲٫۰R کامل ثبت می‌کند → ۴ برابر بیش‌برآورد.
    S.append({
        "name": "bias_stale_entry_win",
        "now": _iso(NOW), "cfg": CFG_STD,
        "signals": [signal("stale_win", "EURUSD", "BUY", 1.1000, 1.0980, 1.1040,
                           T0 + timedelta(minutes=47))],
        "datasets": [dataset("EURUSD", T0 + timedelta(minutes=30), [
            [1.1032, 1.1028, 1.1030],   # ← قیمتِ واقعیِ لحظهٔ صدور (بستهٔ M15)
            [1.1034, 1.1029, 1.1032],   # نمایه T0+45 ≤ ts → کدِ فعلی ردش می‌کند
            [1.1042, 1.1031, 1.1041],   # نمایه T0+60 → لمسِ TP
        ])],
    })

    # ── ۷) 🔴 بایاسِ ورودِ کهنه — زیانِ کم‌برآوردشده ──────────────
    #     همان هندسه در سمتِ باخت: از قیمتِ واقعیِ 1.1030 تا SL=1.0980
    #     ۵۰ پیپ فاصله است (= ۲٫۵R زیانِ واقعی) ولی ژورنال فقط ۱٫۰R ثبت
    #     می‌کند → ۲٫۵ برابر کم‌برآورد.
    S.append({
        "name": "bias_stale_entry_loss",
        "now": _iso(NOW), "cfg": CFG_STD,
        "signals": [signal("stale_loss", "EURUSD", "BUY", 1.1000, 1.0980, 1.1040,
                           T0 + timedelta(minutes=47))],
        "datasets": [dataset("EURUSD", T0 + timedelta(minutes=30), [
            [1.1032, 1.1028, 1.1030],   # قیمتِ واقعیِ لحظهٔ صدور
            [1.1031, 1.1020, 1.1022],   # رد می‌شود (≤ ts)
            [1.1022, 1.0975, 1.0980],   # لمسِ SL
        ])],
    })

    # ── ۸) رکوردِ دارای entry_ts — کدِ فعلی نادیده‌اش می‌گیرد ─────
    #     پینِ سازگاریِ روبه‌جلو: بعد از فاز ۱ همین سناریو باید از «باز»
    #     به «TP» تغییر کند (چون اسکن از entry_ts=T0+30 شروع می‌شود نه ts).
    S.append({
        "name": "entry_ts_honoured",
        "now": _iso(NOW_NEAR), "cfg": CFG_STD,
        "signals": [signal("with_ts", "EURUSD", "BUY", 1.1000, 1.0980, 1.1040,
                           T0 + timedelta(minutes=47),
                           entry_ts=T0 + timedelta(minutes=30))],
        "datasets": [dataset("EURUSD", T0 + timedelta(minutes=30), [
            [1.1050, 1.1000, 1.1045],   # لمسِ TP — نمایهٔ T0+30
            [1.1010, 1.0995, 1.1005],
        ])],
    })

    # ── ۹) رکورد با rules_version (تفکیکِ آمارِ v0.29) ───────────
    S.append({
        "name": "rules_version_tagged",
        "now": _iso(NOW), "cfg": CFG_STD,
        "signals": [
            signal("rv_new", "EURUSD", "BUY", 1.1000, 1.0980, 1.1040, T0,
                   rules_version=2),
            signal("rv_old", "GBPUSD", "BUY", 1.3000, 1.2980, 1.3040, T0),
        ],
        "datasets": [
            dataset("EURUSD", bar0, [[1.1045, 1.1020, 1.1040]]),
            dataset("GBPUSD", bar0, [[1.3045, 1.3020, 1.3040]]),
        ],
    })

    # ── ۱۰) فروش با ورودِ کهنه (تقارنِ جهت) ──────────────────────
    #       قیمتِ واقعیِ لحظهٔ صدور 1.2970 است؛ TP=1.2960 فقط ۱۰ پیپ
    #       پایین‌تر → ثبتِ ۲٫۰R در برابرِ ۰٫۵Rِ دست‌یافتنی.
    S.append({
        "name": "bias_stale_entry_sell",
        "now": _iso(NOW), "cfg": CFG_STD,
        "signals": [signal("stale_sell", "GBPUSD", "SELL", 1.3000, 1.3020, 1.2960,
                           T0 + timedelta(minutes=47))],
        "datasets": [dataset("GBPUSD", T0 + timedelta(minutes=30), [
            [1.2972, 1.2968, 1.2970],   # قیمتِ واقعیِ لحظهٔ صدور
            [1.2971, 1.2966, 1.2968],   # رد می‌شود (≤ ts)
            [1.2969, 1.2955, 1.2958],   # لمسِ TP
        ])],
    })

    return S


def battery() -> dict:
    """{نام سناریو: نتیجهٔ سریال‌شدنی} — ورودیِ مستقیمِ فایل طلایی."""
    return {sc["name"]: run_scenario(sc) for sc in scenarios()}


if __name__ == "__main__":
    import json
    print(json.dumps(battery(), ensure_ascii=False, indent=2)[:2000])
