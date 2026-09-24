# -*- coding: utf-8 -*-
"""استراتژی ۱ — Trend Following + Pullback (روند + پولبک).

منطق (تصویب مالک در Preview استراتژی‌ها، v0.26):

  ۱) تشخیص روند اصلی و جهت غالب: روند H4 (EMA50/200 — همان fیلد
     `trend` تحلیل) *و* هم‌جهتی H1 (`h1_agrees`) — جهت غالب یعنی هر دو
     تایم‌فریم یک حرف را می‌زنند.
  ۲) اعتبار روند: ADX ≥ adx_min (پیش‌فرض ۲۰ — هم‌عدد با
     analysis.adx_min_trend؛ بازار بی‌روند = ستاپی نیست).
  ۳) شناسایی Pullback: RSI(M15) در منطقهٔ اصلاح — برای خرید ۳۰..۴۵
     (هم‌منطقه با شاهد momentum و verdict تحلیل)، برای فروش ۵۵..۷۰.
     ورود در حرکتِ کشیده‌شده (RSI اشباع در جهت روند) رد می‌شود.
  ۴) تأیید ادامهٔ حرکت: RSI در حال برگشت (صعودی: rising / نزولی: غیرِ
     rising) *و* کندل آخر H1 (حتی forming) در جهت روند بسته شده
     (close>open برای خرید). بدون تأیید = «چاقوی در حال سقوط» — NONE.
  ۵) هر چهار شرط با هم = ستاپ معتبر → BUY / SELL؛ وگرنه NONE با دلیل.

صادقانه مستند شود: این استراتژی عمداً با منطق verdict تحلیل هم‌پوشانی
دارد (verdict = trend+h1+RSI) اما دو سخت‌گیریِ اضافه دارد — کفِ منطقهٔ
RSI (۳۰/۷۰؛ verdict فقط «زیر ۴۵/بالای ۵۵» است) و تأییدِ کندلِ ادامه.
پس سیگنالِ لایهٔ استراتژی *زیرمجموعهٔ سخت‌گیرانه‌ترِ* ستاپ تحلیل است.

امضا: evaluate(a, md, scfg, ctx) → StrategyVerdict   (قرارداد odin.strategy@1)
  a    — SymbolAnalysis (trend/h1_agrees/adx/rsi/rsi_rising)
  md   — MarketData (کندل H1 برای تأیید ادامه) یا None
  scfg — cfg["strategies"]["trend_pullback"]
  ctx  — JudgeContext (استفاده نمی‌شود؛ برای یکدستی امضا)
"""
from __future__ import annotations

from typing import Any, Optional

from ..fa import fa_num
from .base import StrategyVerdict, none

KEY = "trend_pullback"
NAME_FA = "روند + پولبک"


def evaluate(a: Any, md: Optional[Any], scfg: Optional[dict] = None,
             ctx: Any = None) -> StrategyVerdict:
    scfg = dict(scfg or {})
    adx_min = float(scfg.get("adx_min", 20))
    rsi_buy = list(scfg.get("rsi_buy", [30, 45]))
    rsi_sell = list(scfg.get("rsi_sell", [55, 70]))

    # ۱) روند اصلی + جهت غالب
    if getattr(a, "trend", "none") not in ("bullish", "bearish"):
        return none(KEY, NAME_FA, "روند اصلی بازار نامشخص است (نه صعودی، نه نزولی)")
    if not getattr(a, "h1_agrees", False):
        return none(KEY, NAME_FA,
                    "جهت غالب تأیید نشده — H1 با H4 هم‌جهت نیست")
    # ۲) اعتبار روند
    adx = float(getattr(a, "adx", 0.0) or 0.0)
    if adx < adx_min:
        return none(KEY, NAME_FA,
                    f"روند معتبر نیست (ADX={fa_num(f'{adx:.0f}')} زیر "
                    f"{fa_num(f'{adx_min:.0f}')})")

    bullish = a.trend == "bullish"
    rsi = float(getattr(a, "rsi", 50.0) or 50.0)
    lo, hi = (rsi_buy if bullish else rsi_sell)

    # ۳) شناسایی Pullback
    if not (float(lo) <= rsi <= float(hi)):
        side = "خرید" if bullish else "فروش"
        return none(KEY, NAME_FA,
                    f"پولبک معتبر نیست — RSI={fa_num(f'{rsi:.0f}')} بیرونِ "
                    f"منطقهٔ {fa_num(f'{float(lo):.0f}')}–{fa_num(f'{float(hi):.0f}')} "
                    f"برای ستاپ {side} است")

    # ۴) تأیید ادامهٔ حرکت — برگشت RSI
    if bullish and not getattr(a, "rsi_rising", False):
        return none(KEY, NAME_FA,
                    "تأیید ادامهٔ حرکت نیست — RSI در پولبک صعودی هنوز بالا "
                    "نمی‌رود")
    if not bullish and getattr(a, "rsi_rising", False):
        return none(KEY, NAME_FA,
                    "تأیید ادامهٔ حرکت نیست — RSI در اصلاحِ روند نزولی هنوز "
                    "پایین نمی‌آید")

    # ۴) تأیید ادامهٔ حرکت — کندل آخر H1 در جهت روند
    candle_ok, candle_reason = _last_candle_confirms(md, bullish)
    if not candle_ok:
        return none(KEY, NAME_FA, candle_reason)

    # ۵) ستاپ معتبر است
    direction = "BUY" if bullish else "SELL"
    trend_fa = "صعودی" if bullish else "نزولی"
    strength = 0.6 + 0.4 * min(1.0, max(0.0, (adx - adx_min) / 20.0))
    reasons = [
        f"روند {trend_fa} با جهت غالب تأییدشده (H4+H1 هم‌جهت، "
        f"ADX={fa_num(f'{adx:.0f}')})",
        f"پولبک شناسایی شد — RSI={fa_num(f'{rsi:.0f}')} در منطقهٔ "
        f"{fa_num(f'{float(lo):.0f}')}–{fa_num(f'{float(hi):.0f}')}",
        ("تأیید ادامهٔ حرکت — RSI در حال برگشت و کندل آخر ۱ ساعته در جهت "
         "روند بسته شده"),
    ]
    return StrategyVerdict(
        key=KEY, name_fa=NAME_FA, direction=direction,
        strength=strength, proposes=True, reasons_fa=reasons,
        detail_fa=f"{NAME_FA}: پیشنهاد {direction} — روند {trend_fa} + پولبک "
                  f"+ تأیید ادامه")


def _last_candle_confirms(md: Optional[Any], bullish: bool) -> tuple:
    """کندل آخر H1 (حتی forming) باید در جهت روند بسته شده باشد.

    نبودِ داده → ردِ صادقانه (تأییدِ ادامه بدون کندل، حدس است).
    """
    side = "صعودی" if bullish else "نزولی"
    h1 = getattr(md, "h1", None) if md is not None else None
    if h1 is None or len(h1) == 0:
        return False, "تأیید ادامهٔ حرکت ممکن نیست — کندل ۱ ساعته در دسترس نیست"
    try:
        o = float(h1["Open"].iloc[-1])
        c = float(h1["Close"].iloc[-1])
    except Exception:
        return False, "تأیید ادامهٔ حرکت ممکن نیست — کندل ۱ ساعته خوانا نیست"
    if bullish and c > o:
        return True, ""
    if not bullish and c < o:
        return True, ""
    return False, (f"تأیید ادامهٔ حرکت نیست — کندل آخر ۱ ساعته در جهت روند "
                   f"بسته نشده (باید {side} باشد)")
