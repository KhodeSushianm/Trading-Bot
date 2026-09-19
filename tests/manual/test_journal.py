# -*- coding: utf-8 -*-
"""تست ژورنال مرحله ۴ — تعیین نتیجه، آمار دقت، و گزارش‌ها.

کاملاً آفلاین و قطعی: کندل‌ها مصنوعی‌اند تا هر سناریو (هدف/حدضرر/برخورد
دوگانه/انقضا/باز) دقیقاً کنترل شود.
"""
import os
import pathlib
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import pandas as pd

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from src.data.base import MarketData
from src.journal.stats import compute_stats
from src.journal.store import EXPIRED, SL, TP, Journal
from src.journal.tracker import resolve_open_signals
from src.report.journal import render_nightly, render_stats

FAILS = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


T0 = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)     # دوشنبه هفتهٔ قبل
T1 = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)     # دوشنبه این هفته
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def bars(start, rows):
    """rows: فهرست (high, low, close) به فاصلهٔ ۱۵ دقیقه از start."""
    idx = pd.date_range(start, periods=len(rows), freq="15min", tz="UTC")
    df = pd.DataFrame([(r[0], r[1], r[2]) for r in rows],
                      columns=["High", "Low", "Close"], index=idx)
    df["Open"] = df["Close"]
    return df


def md_for(symbol, start, rows):
    m15 = bars(start, rows)
    return MarketData(symbol=symbol, m15=m15, h1=m15, h4=m15)


def sig_rec(sid, symbol, direction, entry, sl, tp, ts, score=8, rr=2.0,
            risk_pips=20.0, pip=0.0001):
    return {"kind": "signal", "id": sid, "ts": ts.isoformat(), "symbol": symbol,
            "direction": direction, "entry": entry, "sl": sl, "tp": tp, "pip": pip,
            "atr": 0.001, "risk_pips": risk_pips, "reward_pips": risk_pips * rr,
            "rr": rr, "score": score, "max_score": 11, "session": "لندن",
            "evidences": ["trend:2/2", "level:2/2", "news:0/1"], "sent": True}


print("=" * 78)
print("۱) تعیین خودکار نتیجه از روی کندل‌ها")
print("=" * 78)
tmp = tempfile.TemporaryDirectory()
jr = Journal(os.path.join(tmp.name, "s.jsonl"))

# الف) خرید → هدف می‌خورد
jr.append(sig_rec("a", "EURUSD", "BUY", 1.1000, 1.0980, 1.1040, T1))
# ب) فروش → هدف می‌خورد
jr.append(sig_rec("b", "GBPUSD", "SELL", 1.3000, 1.3020, 1.2960, T1))
# ج) خرید → حد ضرر می‌خورد
jr.append(sig_rec("c", "USDJPY", "BUY", 150.00, 149.80, 150.40, T1, pip=0.01,
                  risk_pips=20.0))
# د) خرید → یک کندل هر دو سطح → محتاطانه ضرر
jr.append(sig_rec("d", "USDCAD", "BUY", 1.3500, 1.3480, 1.3540, T1))
# ه) خرید → هیچ برخوردی، منقضی
jr.append(sig_rec("e", "AUDUSD", "BUY", 0.7000, 0.6980, 0.7040,
                  NOW - timedelta(hours=60)))
# و) خرید → هنوز باز (برخوردی نیست و داخل پنجرهٔ انقضا)
jr.append(sig_rec("f", "USDCHF", "BUY", 0.8200, 0.8180, 0.8240,
                  NOW - timedelta(hours=2)))

BAR0 = T1 + timedelta(minutes=15)
datasets = {
    "EURUSD": md_for("EURUSD", BAR0, [(1.1010, 1.0995, 1.1005), (1.1045, 1.1020, 1.1040)]),
    "GBPUSD": md_for("GBPUSD", BAR0, [(1.2990, 1.2955, 1.2960)]),
    "USDJPY": md_for("USDJPY", BAR0, [(150.10, 149.75, 149.80)], ),
    "USDCAD": md_for("USDCAD", BAR0, [(1.3545, 1.3475, 1.3500)]),   # هر دو سطح
    "AUDUSD": md_for("AUDUSD", NOW - timedelta(hours=60),
                     [(0.7010, 0.6990, 0.7005), (0.7012, 0.6995, 0.7010)]),
    "USDCHF": md_for("USDCHF", NOW - timedelta(hours=2),
                     [(0.8210, 0.8190, 0.8205)]),
}
cfg = {"journal": {"enabled": True, "expiry_hours": 48, "conservative_both_touch": True}}
resolved = resolve_open_signals(jr, datasets, now=NOW, cfg=cfg, on_log=lambda m: None)

by_id = {e.id: e for e in jr.load()}
check(by_id["a"].outcome == TP and by_id["a"].r == 2.0, f"الف) هدف خورد R=+2 ({by_id['a'].outcome},{by_id['a'].r})")
check(by_id["b"].outcome == TP and by_id["b"].r == 2.0, f"ب) فروش→هدف R=+2 ({by_id['b'].outcome})")
check(by_id["c"].outcome == SL and by_id["c"].r == -1.0, f"ج) حد ضرر R=-1 ({by_id['c'].outcome})")
check(by_id["d"].outcome == SL, f"د) برخورد دوگانه → محتاطانه ضرر ({by_id['d'].outcome})")
check("محتاطانه" in (by_id["d"].note or ""), "د) یادداشت صادقانهٔ برخورد دوگانه ثبت شد")
check(by_id["e"].outcome == EXPIRED, f"ه) انقضا ({by_id['e'].outcome})")
check(abs(by_id["e"].r - 0.5) < 1e-6, f"ه) R انقضا از قیمت واقعی (=+0.5): {by_id['e'].r}")
check(by_id["f"].is_open, "و) سیگنال بدون برخورد و داخل پنجره → باز می‌ماند")
check(len(resolved) == 5, f"۵ سیگنال در این فراخوانی بسته شد ({len(resolved)})")

# تکرار فراخوانی نباید چیزی را دوباره ببندد (idempotency)
again = resolve_open_signals(jr, datasets, now=NOW, cfg=cfg, on_log=lambda m: None)
check(len(again) == 0, f"فراخوانی دوم چیزی را دوباره نمی‌بندد ({len(again)})")

print()
print("۲) آمار دقت")
print("=" * 78)
entries = jr.load()
st = compute_stats(entries, NOW)
o = st.overall
check(o.closed == 5 and o.wins == 2 and o.losses == 2 and o.expired == 1,
      f"کلی: بسته۵ برد۲ باخت۲ منقضی۱ ({o.closed},{o.wins},{o.losses},{o.expired})")
check(abs(o.hit_rate - 0.5) < 1e-9, f"نرخ برد قطعی = ۵۰٪ ({o.hit_rate})")
check(abs(o.avg_r - 0.5) < 1e-9, f"میانگین R = +0.5 ((2+2-1-1+0.5)/5) ({o.avg_r})")
check(st.open_count == 1, f"یک سیگنال باز ({st.open_count})")
check(len(st.by_week) == 1, f"یک هفتهٔ ISO ({sorted(st.by_week)})")
check("trend" in st.by_evidence and st.by_evidence["trend"].wins == 2,
      "همبستگی مدرک trend↔برد محاسبه شد")

print()
print("۳) گزارش‌ها")
print("=" * 78)
txt = render_stats(st, jr.open_entries(), NOW)
print("─" * 78)
print(txt)
print("─" * 78)
for needle in ("کارنامهٔ دقت", "نرخ برد", "میانگین R", "به تفکیک نماد",
               "به تفکیک امتیاز", "کدام مدرک", "نویز آماری"):
    check(needle in txt, f"کارنامه شامل «{needle}» است")

night = render_nightly(entries, st, NOW)
check("خلاصهٔ شبانه" in night and "هنوز باز" in night, "خلاصهٔ شبانه شامل بازهاست")
check("USDCHF" in night, "خلاصهٔ شبانه سیگنال‌های باز را فهرست می‌کند")
check("امروز سیگنالی بسته نشد" in night, "روز بدون سیگنال بسته صادقانه گفته می‌شود")

# مقایسهٔ هفته‌به‌هفته با افزودن سیگنال هفتهٔ قبل
jr.append(sig_rec("g", "EURUSD", "BUY", 1.0900, 1.0880, 1.0940, T0))
jr.add_outcome("g", TP, 1.0940, 2.0, "", ts=T0 + timedelta(hours=3))
st2 = compute_stats(jr.load(), NOW)
check(len(st2.by_week) == 2, f"دو هفته برای مقایسه ({sorted(st2.by_week)})")
txt2 = render_stats(st2, [], NOW)
check("هفتهٔ قبل" in txt2 and "روند هفته‌به‌هفته" in txt2, "مقایسهٔ هفته‌به‌هفته رندر شد")

tmp.cleanup()
print()
print("=" * 78)
if FAILS:
    print(f"❌ {len(FAILS)} خطا:")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("✅ همهٔ تست‌های ژورنال پاس شدند")
