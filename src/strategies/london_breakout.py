# -*- coding: utf-8 -*-
"""استراتژی ۲ — London Breakout (شکست محدودهٔ آسیا در سشن لندن).

منطق (تصویب مالک در Preview استراتژی‌ها، v0.26):

  ۱) تشکیل Range: محدودهٔ High/Low کندل‌های H1 سشن آسیا
     (پیش‌فرض ۰۰:۰۰ تا ۰۷:۰۰ UTC همان روزِ 런던) — حداقل
     asia_min_bars کندل لازم است (وگرنه NONE صادقانه).
  ۲) اعتبار محدوده: عرضِ Range نسبت به ATR سنجیده می‌شود —
     خیلی تنگ (< min_range_atr×ATR) = نویز، خیلی پهن
     (> max_range_atr×ATR) = حرکتِ روز قبلش رفته. ATR نبود/صفر بود = NONE.
  ۳) پنجرهٔ لندن: فقط از london_open_hour تا trade_window_hours ساعتِ بعد
     (پیش‌فرض ۰۷:۰۰–۱۱:۰۰ UTC — شروع سشن لندن طبق جدول سشن‌ها) و فقط
     روزهای کاری بازار. بیرونِ پنجره = NONE (شکستِ دیر = تعقیبِ قیمت).
  ۴) شکست معتبر: قیمتِ فعلی (= آخرین بستهٔ H1 — همان price تحلیل، پس
     «بسته شدن» فراتر از سطح است نه فقط سایه) باید از
     high + breakout_margin_atr×ATR بالا بزند (BUY) یا از
     low − margin پایین بزند (SELL). حاشیهٔ نفوذ، شکست‌های لبه‌ای/سایه
     را رد می‌کند.
  ۵) جهت = سمتِ شکست؛ نبودِ هر شرط → NONE با دلیل فارسی.

زمان: همه‌چیز UTC و از ctx.now — ایندکس کندل‌ها طبق قرارداد
src/data/base naive-UTC است (aware هم تحمل می‌شود: utc_of).

امضا: evaluate(a, md, scfg, ctx) → StrategyVerdict   (قرارداد odin.strategy@1)
"""
from __future__ import annotations

from typing import Any, Optional

from ..fa import fa_num
from .base import StrategyVerdict, ctx_now, none, utc_of

KEY = "london_breakout"
NAME_FA = "شکست لندن"


def evaluate(a: Any, md: Optional[Any], scfg: Optional[dict] = None,
             ctx: Any = None) -> StrategyVerdict:
    scfg = dict(scfg or {})
    asia_start = int(scfg.get("asia_start_hour", 0))
    asia_end = int(scfg.get("asia_end_hour", 7))
    open_h = int(scfg.get("london_open_hour", 7))
    window = int(scfg.get("trade_window_hours", 4))
    min_bars = int(scfg.get("asia_min_bars", 5))
    min_w_atr = float(scfg.get("min_range_atr", 0.5))
    max_w_atr = float(scfg.get("max_range_atr", 3.0))
    margin_atr = float(scfg.get("breakout_margin_atr", 0.15))

    now = ctx_now(ctx)

    # ۳) پنجرهٔ لندن — اول زمان، چون ارزان‌ترین رد است
    if now.weekday() >= 5:
        return none(KEY, NAME_FA, "روزهای پایانی هفته — سشن لندن بسته است")
    if not (open_h <= now.hour < open_h + window):
        return none(KEY, NAME_FA,
                    f"بیرونِ پنجرهٔ شکستِ لندن "
                    f"({fa_num(str(open_h))}:۰۰ تا "
                    f"{fa_num(str(open_h + window))}:۰۰ UTC — الان ساعت "
                    f"{fa_num(f'{now.hour:02d}')}:{fa_num(f'{now.minute:02d}')})")

    # ۱) تشکیل Range از کندل‌های آسیایِ همان روز
    h1 = getattr(md, "h1", None) if md is not None else None
    if h1 is None or len(h1) == 0:
        return none(KEY, NAME_FA, "کندل ۱ ساعته در دسترس نیست — Range ساخته نمی‌شود")
    highs, lows = [], []
    for ts, hi, lo in zip(h1.index, h1["High"], h1["Low"]):
        t = utc_of(ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts)
        if t is None or t.date() != now.date():
            continue
        if asia_start <= t.hour < asia_end:
            highs.append(float(hi))
            lows.append(float(lo))
    if len(highs) < min_bars:
        return none(KEY, NAME_FA,
                    f"محدودهٔ آسیا کامل تشکیل نشده — فقط "
                    f"{fa_num(str(len(highs)))} کندل در بازهٔ "
                    f"{fa_num(str(asia_start))}–{fa_num(str(asia_end))} UTC "
                    f"(حداقل {fa_num(str(min_bars))} لازم است)")
    rng_hi, rng_lo = max(highs), min(lows)
    width = rng_hi - rng_lo

    # ۲) اعتبار محدوده نسبت به ATR
    atr = float(getattr(a, "atr", 0.0) or 0.0)
    if atr <= 0:
        return none(KEY, NAME_FA,
                    "ATR در دسترس نیست — اعتبار محدوده و شکست سنجیده نمی‌شود")
    if width < min_w_atr * atr:
        return none(KEY, NAME_FA,
                    f"محدوده خیلی تنگ است ({width:.5g} کمتر از "
                    f"{fa_num(f'{min_w_atr:g}')}×ATR) — شکستش نویز است")
    if width > max_w_atr * atr:
        return none(KEY, NAME_FA,
                    f"محدوده خیلی پهن است ({width:.5g} بیشتر از "
                    f"{fa_num(f'{max_w_atr:g}')}×ATR) — حرکتِ اصلی احتمالا رفته")

    # ۴) شکست معتبر با حاشیهٔ نفوذ
    price = float(getattr(a, "price", 0.0) or 0.0)
    margin = margin_atr * atr
    if price >= rng_hi + margin:
        direction, pen = "BUY", price - (rng_hi + margin)
    elif price <= rng_lo - margin:
        direction, pen = "SELL", (rng_lo - margin) - price
    else:
        return none(KEY, NAME_FA,
                    f"شکست معتبری رخ نداده — قیمت {price:.5g} داخل محدودهٔ "
                    f"{rng_lo:.5g}–{rng_hi:.5g} است (حاشیهٔ نفوذ "
                    f"{fa_num(f'{margin_atr:g}')}×ATR)")

    strength = 0.6 + 0.4 * min(1.0, pen / (0.5 * atr))
    side_fa = "بالای سقف" if direction == "BUY" else "زیر کف"
    reasons = [
        f"محدودهٔ آسیا ({fa_num(str(asia_start))}–{fa_num(str(asia_end))} UTC): "
        f"{rng_lo:.5g} – {rng_hi:.5g} از {fa_num(str(len(highs)))} کندل",
        f"شکست معتبر — قیمت {price:.5g} {side_fa} محدوده با عبور از حاشیهٔ "
        f"{margin_atr:g}×ATR بسته شده",
        f"در پنجرهٔ لندن — ساعت {fa_num(f'{now.hour:02d}')}:{fa_num(f'{now.minute:02d}')} UTC",
    ]
    return StrategyVerdict(
        key=KEY, name_fa=NAME_FA, direction=direction,
        strength=strength, proposes=True, reasons_fa=reasons,
        detail_fa=f"{NAME_FA}: پیشنهاد {direction} — شکستِ "
                  f"{'سقف' if direction == 'BUY' else 'کف'} محدودهٔ آسیا در "
                  f"سشن لندن")
