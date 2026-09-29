# -*- coding: utf-8 -*-
"""تعیین خودکار نتیجهٔ سیگنال‌های باز — مرحله ۴.

برای هر سیگنال باز، کندل‌های M15ِ **بعد از لحظهٔ ورود** بررسی می‌شوند:
  • اگر سقف/کف کندل به TP یا SL برسد، سیگنال بسته می‌شود.
  • اگر یک کندل **هر دو** را بزند، ترتیب برخورد از روی کندل ۱۵ دقیقه‌ای
    قابل دانستن نیست؛ پس با ``conservative_both_touch`` (پیش‌فرض true)
    **ضرر** شمرده می‌شود — همان قاعدهٔ محتاطانهٔ همیشگی: وقتی نمی‌دانیم،
    بدبینانه گزارش می‌کنیم تا آمار دقت باد نکند.
  • اگر تا ``expiry_hours`` هیچ‌کدام نخورد، سیگنال EXPIRED می‌شود و R واقعی
    از قیمت لحظهٔ انقضا محاسبه می‌شود (نه صفرِ ساختگی).

R:
  TP      → +rr
  SL      → −1
  EXPIRED → (قیمت انقضا − ورود) / ریسک، با علامت جهت

── «لحظهٔ ورود» کدام است؟ (v0.29 فاز ۱) ──────────────────────────
پیش‌تر اسکن از ``entry.ts`` شروع می‌شد — **دیوارساعتِ لحظهٔ صدور سیگنال** —
در حالی که ``entry`` (قیمت) بستهٔ یک کندلِ قدیمی‌تر بود. این دو تا یک ساعت
اختلال داشتند و کارنامه را خوش‌بینانه می‌کردند (برد ~۴ برابر بیش‌برآورد و
باخت ~۲٫۵ برابر کم‌برآورد؛ اندازه‌گیری‌شده در ``tests/test_tracker.py`` بخش C).

حالا اسکن از ``entry.entry_ts`` شروع می‌شود = **زمانِ بسته‌شدنِ همان کندلی که
قیمتِ ورود از آن آمده**. یعنی قیمت و زمان به یک لحظه اشاره می‌کنند.
رکوردهای قدیمی ``entry_ts`` ندارند → رفتارِ دقیقاً قبلی حفظ می‌شود
(سازگاریِ backward بدون حدس زدن).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from .store import EXPIRED, SL, TP, Entry, Journal

LogFn = Callable[[str], None]

OUTCOME_FA = {
    TP: "🎯 هدف خورد",
    SL: "🛑 حد ضرر خورد",
    EXPIRED: "⏳ بدون برخورد منقضی شد",
}


def _r_for(entry: Entry, outcome: str, close_price: float) -> float:
    if outcome == TP:
        return float(entry.rr)
    if outcome == SL:
        return -1.0
    risk = entry.risk_price
    if risk <= 0:
        return 0.0
    diff = (close_price - entry.entry) if entry.direction == "BUY" \
        else (entry.entry - close_price)
    return diff / risk


def _net_r(entry: Entry, outcome: str, gross_r: Optional[float]) -> Optional[float]:
    """Rِ خالصِ پس‌از‌هزینه (v0.29 فاز ۳).

    مدلِ هزینه — صریح و مستند، نه ضریبِ جادویی:
      • ورود همیشه سفارشِ بازار است (taker) → نصفِ اسپرد
      • هدف (TP) یک سفارشِ limit است (maker) → بدون جریمهٔ خروج
      • حد ضرر یک stop است که به بازار تبدیل می‌شود (taker) → نصفِ اسپرد
      • انقضا هم با بازار بسته می‌شود (taker) → نصفِ اسپرد
    پس:  TP → ۰٫۵×اسپرد   ·   SL / EXPIRED → ۱٫۰×اسپرد

    اسپرد و ریسک هر دو پیپ‌اند پس واحد حذف می‌شود و نیازی به قیمت نیست.
    اسپرد صفر (رکوردهای قدیمی، یا spread.enabled=false) → **همان Rِ
    ناخالص** برمی‌گردد، نه صفر و نه None. یعنی افزودنِ این لایه هیچ عددِ
    موجود را خراب نمی‌کند.
    """
    if gross_r is None:
        return None
    sp = float(getattr(entry, "spread_pips", 0.0) or 0.0)
    risk = float(getattr(entry, "risk_pips", 0.0) or 0.0)
    if sp <= 0.0 or risk <= 0.0:
        return gross_r
    factor = 0.5 if outcome == TP else 1.0
    return gross_r - factor * sp / risk


def _in_scope(entry: Entry, bar_ts: datetime) -> bool:
    """آیا این کندل در بازهٔ اسکن است؟

    دو حالت — صریح و سازگار:
      • ``entry_ts`` موجود (رکورد v0.29 به بعد): کندل‌هایی که **باز‌شدنشان**
        از لحظهٔ بسته‌شدنِ کندلِ ورود دیرتر یا برابر است. خودِ کندلِ ورود
        شامل می‌شود؟ نه — نمایهٔ کندلِ ورود = ``entry_ts − interval`` است،
        پس با ``bar_ts >= entry_ts`` خودبه‌خود بیرون می‌ماند و اولین کندلِ
        کاملاً پس از ورود، اولین کندلِ اسکن است.
      • ``entry_ts`` غایب (رکورد قدیمی): رفتارِ دقیقاً قبلی — ``bar_ts > ts``.
        عمداً عوض نمی‌شود تا آمارِ گذشته بی‌صدا جابه‌جا نشود.
    """
    ets = getattr(entry, "entry_ts", None)
    if ets is not None:
        return bar_ts >= ets
    return bar_ts > entry.ts


def _build_bars(md) -> list:
    """کندل‌های M15 به فهرست (ts, high, low) — با هم‌جنس‌سازیِ منطقهٔ زمانی."""
    if md is None or getattr(md, "m15", None) is None or not len(md.m15):
        return []
    bars = []
    for idx, row in md.m15.iterrows():
        ts = (idx.to_pydatetime() if hasattr(idx, "to_pydatetime")
              else datetime.fromisoformat(str(idx)))
        # کندل‌های Yahoo naive-UTC هستند ولی entry.ts آگاه به منطقهٔ زمانی؛
        # بدون هم‌جنس‌کردن، مقایسه TypeError می‌دهد.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        bars.append((ts, float(row["High"]), float(row["Low"])))
    return bars


def _clamp(v: Optional[float]) -> Optional[float]:
    """MFE را به قراردادِ ≥۰ می‌برد (None دست‌نخورده — یعنی «ثبت نشده»)."""
    return None if v is None else max(0.0, v)


def _clamp_a(v: Optional[float]) -> Optional[float]:
    """MAE را به قراردادِ ≤۰ می‌برد (None دست‌نخورده)."""
    return None if v is None else min(0.0, v)


def _excursions(entry: Entry, high: float, low: float, risk: float):
    """(سودِ این کندل, زیانِ این کندل) بر حسب R.

    MFE/MAE عمداً **سقف/کفِ واقعیِ کندل** را می‌سنجد، نه قیمتِ بسته و نه
    سطحِ هدف — چون پرسشِ «هدفِ ۲R زیادی دور بود؟» فقط با دیدنِ اینکه قیمت
    *واقعاً* تا کجا رفت پاسخ دارد. اگر تا ۱٫۵R رفته و برگشته، همان ۱٫۵R
    ثبت می‌شود نه ۲Rِ هدف.
    """
    if risk <= 0:
        return None, None
    if entry.direction == "BUY":
        return (high - entry.entry) / risk, (low - entry.entry) / risk
    return (entry.entry - low) / risk, (entry.entry - high) / risk


def _scan_bars(entry: Entry, bars, conservative: bool,
               until: Optional[datetime] = None):
    """بررسی ترتیبی کندل‌ها.

    Returns:
        ``(hit, mfe_r, mae_r)`` که ``hit`` = ``(outcome, close_price)`` یا
        ``None`` است. MFE/MAE روی **همهٔ** کندل‌های در بازه حساب می‌شود،
        حتی وقتی برخوردی رخ نداده — چون سناریوی انقضا هم به آن نیاز دارد.

        ``until`` کرانِ زمانیِ اسکن است (برای انقضا: ورود + expiry_hours) تا
        MFE/MAEٔ یک معاملهٔ منقضی‌شده، حرکتِ پس از انقضا را هم قاطی نکند.
    """
    risk = entry.risk_price
    mfe: Optional[float] = None
    mae: Optional[float] = None
    for ts, high, low in bars:
        if not _in_scope(entry, ts):
            continue
        if until is not None and ts > until:
            break
        fav, adv = _excursions(entry, high, low, risk)
        if fav is not None:
            mfe = fav if mfe is None else max(mfe, fav)
            mae = adv if mae is None else min(mae, adv)
        # قراردادِ استانداردِ MFE/MAE: mfe ≥ ۰ و mae ≤ ۰. اگر قیمت هرگز
        # علیه ما نرفت، mae = 0 است نه یک عددِ مثبتِ گیج‌کننده. صریح
        # clamp می‌کنیم تا خوانندهٔ آمار مجبور به حدسِ علامت نباشد.
        # (مقدارِ خامِ هر کندل در _excursions بدون clamp است.)
        if entry.direction == "BUY":
            hit_tp = high >= entry.tp
            hit_sl = low <= entry.sl
        else:
            hit_tp = low <= entry.tp
            hit_sl = high >= entry.sl
        if hit_tp and hit_sl:
            hit = (SL, entry.sl) if conservative else (TP, entry.tp)
            return hit, _clamp(mfe), _clamp_a(mae)
        if hit_tp:
            return (TP, entry.tp), _clamp(mfe), _clamp_a(mae)
        if hit_sl:
            return (SL, entry.sl), _clamp(mfe), _clamp_a(mae)
    return None, _clamp(mfe), _clamp_a(mae)


def resolve_open_signals(journal: Journal, datasets: dict,
                         now: Optional[datetime] = None,
                         cfg: Optional[dict] = None,
                         on_log: LogFn = lambda _m: None) -> list[Entry]:
    """سیگنال‌های باز را بررسی و نتیجه‌ها را به ژورنال الحاق می‌کند.

    Args:
        datasets: نگاشت نام نماد → MarketData (برای کندل‌های M15)
    Returns:
        فهرست Entryهایی که در این فراخوانی بسته شدند.
    """
    now = now or datetime.now(timezone.utc)
    jcfg = (cfg or {}).get("journal") or {}
    if not jcfg.get("enabled", True):
        return []
    conservative = bool(jcfg.get("conservative_both_touch", True))
    expiry_h = float(jcfg.get("expiry_hours", 48))

    resolved: list[Entry] = []
    for entry in journal.open_entries():
        md = datasets.get(entry.symbol)
        bars = _build_bars(md)
        hit, mfe, mae = (_scan_bars(entry, bars, conservative) if bars
                         else (None, None, None))

        r_override = None
        if hit is None and (now - entry.ts) > timedelta(hours=expiry_h):
            # منقضی: R واقعی از آخرین قیمت موجود
            close = None
            if bars:
                close = float(md.m15["Close"].iloc[-1])
                # MFE/MAEٔ معاملهٔ منقضی باید تا لحظهٔ انقضا باشد، نه تا
                # آخرین کندلِ موجود (که ممکن است روزها بعد باشد — مثلاً اگر
                # اپ خاموش بوده). وگرنه آمارِ نوسانِ این دسته باد می‌کرد.
                _until = entry.ts + timedelta(hours=expiry_h)
                _, mfe, mae = _scan_bars(entry, bars, conservative, until=_until)
            outcome, close_price = EXPIRED, close
            if close is None:
                # قیمتی در دسترس نیست ولی سیگنال قطعاً منقضی شده؛ نگه‌داشتنِ
                # «باز» برای همیشه کارنامه را خوش‌بینانه نگه می‌داشت.
                note = (f"تا {expiry_h:.0f} ساعت نه هدف خورد نه حد ضرر؛ "
                        f"قیمت لحظهٔ انقضا در دسترس نبود پس R صفر ثبت شد")
                r_override = 0.0
            else:
                note = (f"تا {expiry_h:.0f} ساعت نه هدف خورد نه حد ضرر؛ "
                        f"با قیمت لحظهٔ انقضا بسته شد")
                r_override = None
        elif hit is not None:
            outcome, close_price = hit
            note = ("هر دو سطح در یک کندل خوردند؛ محتاطانه ضرر شمرده شد"
                    if outcome == SL and conservative and _both_touch(entry, bars) else "")
        else:
            continue

        r = r_override if r_override is not None else _r_for(entry, outcome, close_price)
        net_r = _net_r(entry, outcome, r)
        journal.add_outcome(entry.id, outcome, close_price, r, note, ts=now,
                            net_r=net_r, mfe_r=mfe, mae_r=mae)
        entry.outcome, entry.close_price, entry.r, entry.note = outcome, close_price, r, note
        entry.net_r, entry.mfe_r, entry.mae_r = net_r, mfe, mae
        entry.outcome_ts = now
        resolved.append(entry)
        # لاگ هر دو را نشان می‌دهد وقتی هزینه مدل شده — پنهان نمی‌کنیم
        _cost = f" · خالص={net_r:+.2f}" if net_r is not None and net_r != r else ""
        on_log(f"📔 ژورنال: {entry.symbol} {entry.direction} → {OUTCOME_FA.get(outcome, outcome)} "
               f"(R={r:+.2f}{_cost})")
    return resolved


def _both_touch(entry: Entry, bars) -> bool:
    """آیا کندلی **در بازهٔ اسکن** هست که هر دو سطح را زده باشد؟

    فقط برای یادداشتِ صادقانه. v0.29: پیش‌تر این تابع همهٔ کندل‌های موجود را
    بدون هیچ کرانِ زمانی می‌دید — یعنی برخوردِ دوگانه‌ای که *پیش از ورود*
    اتفاق افتاده بود هم «هر دو سطح در یک کندل خوردند» یادداشت می‌گرفت.
    حالا همان قاعدهٔ ``_in_scope`` را دارد.
    """
    for ts, high, low in bars:
        if not _in_scope(entry, ts):
            continue
        if entry.direction == "BUY":
            if high >= entry.tp and low <= entry.sl:
                return True
        else:
            if low <= entry.tp and high >= entry.sl:
                return True
    return False
