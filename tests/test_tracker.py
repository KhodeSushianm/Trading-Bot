# -*- coding: utf-8 -*-
"""میخِ رفتاریِ tracker — فاز ۰ (v0.29).

**چرا این فایل وجود دارد:** تا پیش از این، ``resolve_open_signals`` هیچ تستِ
CI-محوری نداشت (تنها پوششش ``tests/manual/test_journal.py`` بود که در CI
اجرا نمی‌شود). همان خلأ باعث شد باگِ «ورودِ کهنه» ناشناخته بماند و کارنامهٔ
دقت **خوش‌بینانه** گزارش شود. این سوئیت آن خلأ را پر می‌کند.

سه بخش:
  A) پینِ طلایی — باتریٔ ``tracker_scenarios`` باید بایت‌به‌بایت با
     ``tests/golden/tracker_golden.json`` یکی باشد.
  B) ادعاهای ساختاریِ صریح — مستقل از طلایی، تا علتِ شکست روشن باشد.
  C) **سنجهٔ بایاس** — فاصلهٔ Rِ ثبت‌شده تا Rِ دست‌یافتنی (ورود با قیمتِ
     واقعیِ لحظهٔ صدور). این بخش در فاز ۰ «وجودِ بایاس» را مستند می‌کند و
     بعد از فاز ۲ باید «بایاس ≈ صفر» شود.

اجرا:  python tests/test_tracker.py
"""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timedelta

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from tests.tracker_scenarios import battery, scenarios  # noqa: E402
from src.journal.store import EXPIRED, SL, TP  # noqa: E402

GOLDEN = _ROOT / "tests" / "golden" / "tracker_golden.json"

CHECKS = 0
FAILS: list = []


def A(cond: bool, msg: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(msg)


# ══════════════════════════════════════════════════════════════
#  A) پینِ طلایی
# ══════════════════════════════════════════════════════════════
print("═" * 70)
print("A) پینِ طلاییِ رفتارِ tracker")
print("═" * 70)

if not GOLDEN.exists():
    print(f"❌ فایل طلایی وجود ندارد: {GOLDEN}")
    print("   ابتدا اجرا کنید:  python tests/golden/gen_tracker_golden.py")
    raise SystemExit(1)

expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
actual = battery()

A(set(actual) == set(expected),
  f"مجموعهٔ سناریوها یکی نیست: +{set(actual) - set(expected)} "
  f"-{set(expected) - set(actual)}")

for name in sorted(expected):
    if name not in actual:
        continue
    a = json.dumps(actual[name], ensure_ascii=False, sort_keys=True)
    e = json.dumps(expected[name], ensure_ascii=False, sort_keys=True)
    if a != e:
        # اولین تفاوت را نشان بده (اشکال‌زدایی)
        for k in sorted(set(list(actual[name]) + list(expected[name]))):
            av, ev = actual[name].get(k), expected[name].get(k)
            if json.dumps(av, sort_keys=True, ensure_ascii=False) != \
               json.dumps(ev, sort_keys=True, ensure_ascii=False):
                A(False, f"سناریوی «{name}» — کلید «{k}»:\n"
                         f"      انتظار: {ev}\n"
                         f"      واقعی : {av}")
                break
    else:
        A(True, f"سناریوی «{name}» بایت‌به‌بایت")

print(f"   {len(expected)} سناریو مقایسه شد")

# ══════════════════════════════════════════════════════════════
#  B) ادعاهای ساختاریِ صریح
# ══════════════════════════════════════════════════════════════
print("═" * 70)
print("B) ادعاهای ساختاری")
print("═" * 70)

base = actual.get("base_outcomes", {}).get("entries", {})

A(base.get("buy_tp", {}).get("outcome") == TP, "خرید → هدف خورد")
A(base.get("buy_tp", {}).get("r") == 2.0, f"خرید → R=+2.0 ({base.get('buy_tp', {}).get('r')})")
A(base.get("sell_tp", {}).get("outcome") == TP, "فروش → هدف خورد")
A(base.get("buy_sl", {}).get("outcome") == SL, "خرید → حد ضرر خورد")
A(base.get("buy_sl", {}).get("r") == -1.0, "حد ضرر → R=-1.0")
A(base.get("both_touch", {}).get("outcome") == SL, "برخورد دوگانه → محتاطانه ضرر")
A("محتاطانه" in (base.get("both_touch", {}).get("note") or ""),
  "برخورد دوگانه → یادداشتِ صادقانه ثبت شد")
A(base.get("expired", {}).get("outcome") == EXPIRED, "گذشته از پنجره → منقضی")
A(abs((base.get("expired", {}).get("r") or 0) - 0.5) < 1e-6,
  f"انقضا → R از قیمتِ واقعی نه صفرِ ساختگی ({base.get('expired', {}).get('r')})")
A(base.get("still_open", {}).get("is_open") is True, "بدون برخورد و داخل پنجره → باز می‌ماند")
A(len(actual.get("base_outcomes", {}).get("resolved_first_call", [])) == 5,
  "دقیقاً ۵ سیگنال در فراخوانیِ اول بسته شد")
A(actual.get("base_outcomes", {}).get("resolved_second_call") == [],
  "فراخوانیِ دوم چیزی را دوباره نمی‌بندد (idempotency)")

A(actual.get("both_touch_optimistic", {}).get("entries", {})
  .get("bt", {}).get("outcome") == TP,
  "conservative=false → برخورد دوگانه خوش‌بینانه TP شمرده می‌شود")

A(actual.get("journal_disabled", {}).get("resolved_first_call") == [],
  "journal.enabled=false → هیچ چیز بسته نمی‌شود")

A(actual.get("expired_no_data", {}).get("entries", {})
  .get("nodata", {}).get("outcome") == EXPIRED,
  "بدون داده + گذشته از پنجره → منقضی (نه بازِ ابدی)")
A(actual.get("expired_no_data", {}).get("entries", {}).get("nodata", {}).get("r") == 0.0,
  "بدون داده → R=0 صادقانه با یادداشت")

A(actual.get("bar_at_ts_is_skipped", {}).get("entries", {})
  .get("edge", {}).get("is_open") is True,
  "کندلی که دقیقاً روی ts باز می‌شود رد می‌شود (پینِ `bar.t <= ts`)")

print(f"   {CHECKS} بررسی تا اینجا")

# ══════════════════════════════════════════════════════════════
#  C) سنجهٔ بایاس — Rِ ثبت‌شده در برابر Rِ دست‌یافتنی
# ══════════════════════════════════════════════════════════════
print("═" * 70)
print("C) سنجهٔ بایاسِ «ورودِ کهنه»")
print("═" * 70)


def achievable_entry(sc: dict, symbol: str, ts_iso: str) -> float | None:
    """تازه‌ترین قیمتِ واقعیِ در دسترس در لحظهٔ صدور.

    = بستهٔ آخرین کندلی که **تا ts کاملاً بسته شده** باشد (نمایه + گام ≤ ts).
    کندلِ در حال تشکیل قیمتِ قابل اتکایی ندارد — همین قاعدهٔ
    ``drop_forming_candle`` است. این قیمتی است که کاربر *واقعاً* می‌توانست
    با آن وارد شود، نه قیمتی که ژورنال ثبت کرده.
    """
    ts = datetime.fromisoformat(ts_iso)
    for d in sc.get("datasets", []):
        if d["symbol"] != symbol:
            continue
        start = datetime.fromisoformat(d["start"])
        step = timedelta(minutes=d["step_min"])
        best = None
        for i, bar in enumerate(d["bars"]):
            if start + i * step + step <= ts:      # کندل کاملاً بسته شده
                best = bar[2]
        return best
    return None


def bias_of(sc_name: str, sig_id: str, direction: str, recorded_r: float,
            entry: float, sl: float, tp: float) -> dict:
    sc = next(s for s in scenarios() if s["name"] == sc_name)
    rec = next(r for r in sc["signals"] if r["id"] == sig_id)
    real = achievable_entry(sc, rec["symbol"], rec["ts"])
    if real is None:
        return {"real_entry": None, "achievable_r": None, "gap": None}
    risk = abs(entry - sl)
    if direction == "BUY":
        ach = (tp - real) / risk if recorded_r > 0 else (sl - real) / risk
    else:
        ach = (real - tp) / risk if recorded_r > 0 else (real - sl) / risk
    return {"real_entry": real, "achievable_r": ach,
            "gap": recorded_r - ach, "ratio": (recorded_r / ach) if ach else None}


bias_rows = []
for sc_name, sig_id, direction, entry, sl, tp in [
    ("bias_stale_entry_win", "stale_win", "BUY", 1.1000, 1.0980, 1.1040),
    ("bias_stale_entry_loss", "stale_loss", "BUY", 1.1000, 1.0980, 1.1040),
    ("bias_stale_entry_sell", "stale_sell", "SELL", 1.3000, 1.3020, 1.2960),
]:
    got = actual.get(sc_name, {}).get("entries", {}).get(sig_id, {})
    rec_r = got.get("r")
    A(rec_r is not None, f"{sc_name}: نتیجه ثبت شده است")
    if rec_r is None:
        continue
    b = bias_of(sc_name, sig_id, direction, rec_r, entry, sl, tp)
    bias_rows.append((sc_name, rec_r, b["achievable_r"], b["gap"], b["ratio"]))
    print(f"   {sc_name:<26} ثبت‌شده={rec_r:+.2f}R  "
          f"دست‌یافتنی={b['achievable_r']:+.2f}R  "
          f"شکاف={b['gap']:+.2f}R  (×{b['ratio']:.1f})")

# ── پینِ فاز ۰: بایاس *وجود دارد* و بزرگ است ──────────────────
# بعد از فاز ۲ (ورود از بستهٔ M15) این سه ادعا وارونه می‌شوند:
# شکاف باید ≈ صفر شود. وارونه‌کردنِ این بخش، بخشی از سوییچِ مستندِ فاز ۲ است.
BIAS_PINNED = True          # ← فاز ۲ این را False می‌کند
max_gap = max(abs(r[3]) for r in bias_rows)
if BIAS_PINNED:
    A(max_gap > 0.5,
      f"[فاز ۰] بایاسِ ورودِ کهنه باید قابل اندازه‌گیری باشد (بزرگ‌ترین شکاف "
      f"{max_gap:.2f}R) — اگر این ادعا شکست، یعنی یا باگ رفع شده (باید "
      f"BIAS_PINNED=False شود) یا سنجه خراب است")
    A(all(r[4] is not None and (r[4] > 1.5 or r[4] < 0.6) for r in bias_rows),
      "[فاز ۰] Rِ ثبت‌شده باید دست‌کم ۱٫۵ برابرِ Rِ دست‌یافتنی باشد "
      f"(نسبت‌ها: {[round(r[4], 2) for r in bias_rows]})")
else:
    A(max_gap < 1e-9,
      f"[فاز ۲] بایاس باید بسته شده باشد (بزرگ‌ترین شکاف {max_gap:.6f}R)")

A(actual.get("entry_ts_honoured", {}).get("entries", {})
  .get("with_ts", {}).get("is_open") is (True if BIAS_PINNED else False),
  "entry_ts_honoured: در فاز ۰ باز می‌ماند (کد فعلی entry_ts را نادیده "
  "می‌گیرد)؛ در فاز ۱ باید TP شود")

print(f"   بزرگ‌ترین شکافِ اندازه‌گیری‌شده: {max_gap:+.2f}R")

# ══════════════════════════════════════════════════════════════
print("═" * 70)
if FAILS:
    print(f"❌ TRACKER TESTS FAILED — {len(FAILS)} از {CHECKS} بررسی")
    for f in FAILS:
        print(f"  • {f}")
    print("═" * 70)
    raise SystemExit(1)
print(f"✅ TRACKER TESTS OK — {CHECKS} بررسی پاس؛ میخِ رفتاریِ تعیینِ نتیجهٔ "
      f"سیگنال‌ها (۱۰ سناریو) + سنجهٔ بایاسِ ورودِ کهنه")
print("═" * 70)
