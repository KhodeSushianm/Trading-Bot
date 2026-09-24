# -*- coding: utf-8 -*-
"""استراتژی ۳ — Carry Trade (اختلاف نرخ بهره + هم‌جهتی فاندامنتال).

منطق (تصویب مالک در Preview استراتژی‌ها، v0.26):

  ۱) اختلاف نرخ بهره: diff = rate(ارز پایه) − rate(ارز مقابل) از جدولِ
     نرخ‌های سیاستیِ config (strategies.carry.rates.values).
     |diff| < min_diff (پیش‌فرض ۱٫۵ واحد درصد) → NONE.
     diff>0 → BUY (نگهداری پایه در برابر مقابل صرفِ مثبت دارد)؛ diff<0 → SELL.
     نرخِ هر ارز در جدول نبود (مثل XAU — طلا نرخ بهره ندارد، یا نمادی که
     صاحب جدولش را پر نکرده) → NONE صادقانه.
  ۲) وضعیت Monetary Policy: جدولِ برچسبِ سیاست (hawkish/neutral/dovish) در
     config — برای BUY نباید پایه dovish یا مقابل hawkish باشد (و برعکس).
     پیش‌فرض همه neutral = فیلتر بی‌اثر تا صاحب آن را دستی به‌روز کند.
  ۳) جهت کلی Macro: اگر رتبه‌بندی قدرت ارزها (ctx.ranking) موجود باشد،
     جریانِ قدرت باید با جهت carry هم‌جهت باشد (برای BUY: رتبهٔ پایه بهتر
     از مقابل). نبودِ رتبه‌بندی → فیلتر رد نمی‌کند (صادقانه: داده نیست).
  ۴) هم‌جهتی فاندامنتال: اگر snapshot اخبار موجود باشد، رأی اخبار
     (news_supports — همان موتورِ داور) نباید *خلافِ* جهت carry باشد
     (verdict < 0 → NONE). نبودِ اخبار → رد نمی‌کند.

محدودیتِ صادقانهٔ مستند (همان §8.1 اسناد داور): منبعِ کلیدآزادِ زنده برای
نرخ‌ها وجود ندارد (FRED کلید می‌خواهد، Wikipedia 403) — جدول از منابع
عمومی seed شده (as_of: 2026-09؛ Fed/ECB/SNB رسمی، بقیه aggregator) و
به‌روزرسانی آن وظیفهٔ صاحب است. carry «سوگیریِ کند» است: proposes=False —
تنها به‌عنوان توافق با جهتِ سیگنال شمرده می‌شود و به‌تنهایی سیگنال نمی‌سازد.

امضا: evaluate(a, md, scfg, ctx) → StrategyVerdict   (قرارداد odin.strategy@1)
  md استفاده نمی‌شود (carry تایم‌فریم‌نشین نیست) — برای یکدستی امضا می‌ماند.
"""
from __future__ import annotations

from typing import Any, Optional

from ..fa import fa_num
from .base import StrategyVerdict, none

KEY = "carry"
NAME_FA = "کری (نرخ بهره)"

_BIASES = ("hawkish", "neutral", "dovish")


def evaluate(a: Any, md: Optional[Any] = None, scfg: Optional[dict] = None,
             ctx: Any = None) -> StrategyVerdict:
    scfg = dict(scfg or {})
    rates_cfg = dict(scfg.get("rates") or {})
    values = dict(rates_cfg.get("values") or {})
    bias = dict(rates_cfg.get("bias") or {})
    as_of = str(rates_cfg.get("as_of", "نامعلوم"))
    min_diff = float(scfg.get("min_diff", 1.5))
    news_min = int(scfg.get("news_min_score", 4))

    base = str(getattr(a, "base", "") or "")
    quote = str(getattr(a, "quote", "") or "")

    # ۱) اختلاف نرخ بهره
    rb, rq = values.get(base), values.get(quote)
    if rb is None or rq is None:
        missing = base if rb is None else quote
        return none(KEY, NAME_FA,
                    f"نرخِ سیاستیِ {missing} در جدول نیست (as_of {as_of}) — "
                    f"بدون داده، نظر صادقانه‌ای نداریم", proposes=False)
    diff = float(rb) - float(rq)
    if abs(diff) < min_diff:
        return none(KEY, NAME_FA,
                    f"اختلاف نرخ {base}/{quote} "
                    f"({fa_num(f'{diff:+.2f}')}٪) زیر آستانهٔ "
                    f"{fa_num(f'{min_diff:g}')}٪ است — صرفِ carry ناچیز",
                    proposes=False)
    direction = "BUY" if diff > 0 else "SELL"

    # ۲) وضعیت Monetary Policy (برچسب دستی — پیش‌فرض neutral = بی‌اثر)
    bb = str(bias.get(base, "neutral")).lower()
    qb = str(bias.get(quote, "neutral")).lower()
    if bb not in _BIASES or qb not in _BIASES:
        bb = bb if bb in _BIASES else "neutral"
        qb = qb if qb in _BIASES else "neutral"
    against = (("dovish", "hawkish") if direction == "BUY"
               else ("hawkish", "dovish"))
    if bb == against[0] or qb == against[1]:
        who = f"{base} dovish" if bb == against[0] else f"{quote} hawkish"
        if direction == "SELL":
            who = f"{base} hawkish" if bb == against[0] else f"{quote} dovish"
        return none(KEY, NAME_FA,
                    f"وضعیت سیاست پولی خلاف جهت carry است ({who}) — صبر تا "
                    f"روشن‌شدن مسیر سیاست", proposes=False)

    # ۳) جهت کلی Macro — جریان قدرت ارزها (اگر موجود باشد)
    ranking = list(getattr(ctx, "ranking", None) or []) if ctx is not None else []
    if ranking:
        order = {}
        for i, item in enumerate(ranking):
            try:
                order[str(item[0])] = i
            except Exception:
                continue
        ib, iq = order.get(base), order.get(quote)
        if ib is not None and iq is not None:
            misaligned = (ib > iq) if direction == "BUY" else (ib < iq)
            if misaligned:
                return none(KEY, NAME_FA,
                            f"جریانِ قدرت خلاف جهت carry است — در رتبه‌بندی، "
                            f"{base} ضعیف‌تر از {quote} است؛ صرفِ نرخ به‌تنهایی "
                            f"کافی نیست", proposes=False)

    # ۴) هم‌جهتی فاندامنتال — رأی اخبار (اگر snapshot موجود باشد)
    snap = getattr(ctx, "news_snap", None) if ctx is not None else None
    if snap is not None and getattr(snap, "items", None):
        try:
            from ..fundamental.news import news_supports
            vote = news_supports(snap, base, quote, direction.lower(),
                                 min_score=news_min)
            if getattr(vote, "verdict", 0) < 0:
                return none(KEY, NAME_FA,
                            "اخبارِ فاندامنتال از جهتِ carry پشتیبانی نمی‌کنند "
                            "(رأی خلاف) — هم‌جهتی شرط است", proposes=False)
        except Exception:
            pass  # موتور خبر خطا داد → مثلِ «داده نیست» رفتار کن (رد نمی‌کند)

    strength = min(1.0, abs(diff) / (2.0 * min_diff))
    reasons = [
        f"اختلاف نرخ: {base}={fa_num(f'{float(rb):.2f}')}٪ در برابر "
        f"{quote}={fa_num(f'{float(rq):.2f}')}٪ → "
        f"{fa_num(f'{diff:+.2f}')}٪ به نفع "
        f"{'خرید' if direction == 'BUY' else 'فروش'} جفت",
        "وضعیت سیاست پولی، جریانِ قدرت و اخبار با جهت carry هم‌جهت‌اند "
        "(یا داده‌شان نبود — صادقانه رد نشدند)",
        f"نرخ‌ها از جدولِ config (as_of {as_of}) — به‌روزرسانی دستی لازم دارد",
    ]
    return StrategyVerdict(
        key=KEY, name_fa=NAME_FA, direction=direction,
        strength=strength, proposes=False, reasons_fa=reasons,
        detail_fa=f"{NAME_FA}: سوگیری {direction} — صرفِ نرخ "
                  f"{fa_num(f'{diff:+.2f}')}٪ ({base} در برابر {quote})")
