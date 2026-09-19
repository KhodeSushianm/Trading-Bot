# -*- coding: utf-8 -*-
"""گزارش‌نویس کنسول به زبان فارسی ساده.

ورودی: فهرست SymbolAnalysis + رتبه‌بندی قدرت ارزها
خروجی: متن کامل گزارش (رشته) — همان متنی که در مراحل بعد به تلگرام هم می‌رود.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple

from ..analysis.technical import SymbolAnalysis

SEP = "─" * 62
DSEP = "═" * 62

VERDICT_FA = {
    "RANGE":     "❌ بازار بی‌روند (رنج) — طبق قوانین، فعلاً سیگنالی صادر نمی‌شود",
    "BUY_SETUP": "🟢 شرایط «سیگنال خرید» در حال شکل‌گیری است (تصمیم نهایی با داور — مرحله ۳)",
    "SELL_SETUP":"🔴 شرایط «سیگنال فروش» در حال شکل‌گیری است (تصمیم نهایی با داور — مرحله ۳)",
    "WAIT":      "⏳ در انتظار — مدارک کافی برای صدور سیگنال جمع نشده",
    "DATA":      "⚠️ داده کافی برای تحلیل این نماد در دسترس نیست",
}

TREND_FA = {"bullish": "صعودی 📈", "bearish": "نزولی 📉", "none": "نامشخص ❔"}

RECOMMENDATION_FA = {
    "STRONG_BUY": "خرید قوی 🟢🟢", "BUY": "خرید 🟢", "NEUTRAL": "خنثی ⚪",
    "SELL": "فروش 🔴", "STRONG_SELL": "فروش قوی 🔴🔴",
}
TV_DIR = {"STRONG_BUY": 2, "BUY": 1, "NEUTRAL": 0, "SELL": -1, "STRONG_SELL": -2}

SOURCE_FA = {
    "yahoo": "Yahoo Finance",
    "twelvedata": "Twelve Data",
    "auto": "خودکار (Yahoo — زاپاس: Twelve Data)",
}


def _fmt_price(v: float, pip: float) -> str:
    return f"{v:.2f}" if pip >= 0.01 else f"{v:.5f}".rstrip("0")


def _fmt_dist(v: float, pip: float) -> str:
    """فاصله تا سطوح: برای طلا با دلار، بقیه با پیپ."""
    if pip >= 0.5:      # طلا و فلزات
        return f"{v:.0f}$"
    return f"{v / pip:.0f} پیپ"


def _adx_word(v: float) -> str:
    if v >= 25:
        return "قوی 💪"
    if v >= 20:
        return "متوسط 🙂"
    return "ضعیف/بی‌روند ⚠️"


def _momentum_line(a: SymbolAnalysis) -> str:
    if a.rsi_rising and a.rsi < 45:
        return f"RSI={a.rsi:.0f} و رو به بالا ↗️ — پولبک در حال برگشت (منطقه ورود) ⭐"
    if not a.rsi_rising and a.rsi > 55:
        return f"RSI={a.rsi:.0f} و رو به پایین ↘️ — اصلاح در روند نزولی (منطقه ورود فروش) ⭐"
    if a.rsi > 70:
        return f"RSI={a.rsi:.0f} — اشباع خرید؛ برای ورود جدید دیر است ⚠️"
    if a.rsi < 30:
        return f"RSI={a.rsi:.0f} — اشباع فروش؛ منتظر تایید برگشت ⏳"
    return f"RSI={a.rsi:.0f} — وضعیت خنثی"


def _tv_line(a: SymbolAnalysis, tv, tf_label: str) -> str:
    """خط تاییدیه تریدینگ‌ویو — مقایسه امتیاز رسمی TV با تحلیل خودمان."""
    if tv is None:
        return f"   🔍 تاییدیه تریدینگ‌ویو ({tf_label}): در دسترس نبود ⚠️"
    rec_fa = RECOMMENDATION_FA.get(tv.recommendation, tv.recommendation)
    rsi_s = f" | RSI={tv.rsi:.0f}" if tv.rsi is not None else ""
    line = (f"   🔍 تاییدیه تریدینگ‌ویو ({tf_label}): {rec_fa} "
            f"({tv.buy} خرید / {tv.sell} فروش / {tv.neutral} خنثی){rsi_s}")
    our = {"BUY_SETUP": 1, "SELL_SETUP": -1}.get(a.verdict, 0)
    tv_dir = TV_DIR.get(tv.recommendation, 0)
    if our != 0:
        if tv_dir == our:
            line += " — هم‌جهت با تحلیل ما ✅ (پشتوانه قوی‌تر)"
        elif tv_dir == 0:
            line += " — تریدینگ‌ویو خنثی است ➖"
        else:
            line += " — خلاف جهت تحلیل ما ⚠️ (با احتیاط!)"
    return line


def render_symbol(a: SymbolAnalysis, tv=None, tv_tf: str = "4h") -> str:
    lines = [
        SEP,
        f"📊 {a.symbol} — {a.fa_name}",
        f"   💵 قیمت فعلی: {_fmt_price(a.price, a.pip)}",
    ]
    if a.verdict == "DATA":
        lines.append(f"   🧾 جمع‌بندی: {VERDICT_FA['DATA']}")
        return "\n".join(lines)

    agree = ("— تایم‌فریم ۱ ساعته هم تایید می‌کند ✅" if a.h1_agrees
             else "— ولی ۱ ساعته هم‌جهت نیست ⚠️")
    lines.append(f"   🧭 روند (۴ ساعته): {TREND_FA[a.trend]} {agree}")
    lines.append(f"   💪 قدرت روند: ADX={a.adx:.0f} → {_adx_word(a.adx)}")
    lines.append(f"   📉 مومنتوم (۱۵ دقیقه): {_momentum_line(a)}")

    sup = (f"حمایت: {_fmt_price(a.support, a.pip)} ({_fmt_dist(a.price - a.support, a.pip)} پایین‌تر)"
           if a.support else "حمایت نزدیکی پیدا نشد")
    res = (f"مقاومت: {_fmt_price(a.resistance, a.pip)} ({_fmt_dist(a.resistance - a.price, a.pip)} بالاتر)"
           if a.resistance else "مقاومت نزدیکی پیدا نشد")
    lines.append(f"   🎚️ {sup} | {res}")
    lines.append(f"   🌊 نوسان متوسط ساعتی: ATR={_fmt_dist(a.atr, a.pip)}")
    lines.append(_tv_line(a, tv, tv_tf))
    lines.append(f"   🧾 جمع‌بندی: {VERDICT_FA.get(a.verdict, a.verdict)}")
    return "\n".join(lines)


def render_strength(ranking: List[Tuple[str, float]],
                    analyses: List[SymbolAnalysis]) -> str:
    if not ranking:
        return ""
    lines = [SEP, "💱 رتبه‌بندی قدرت ارزها (۲۴ ساعت اخیر):"]
    lines.append("   " + "  >  ".join(f"{c} ({v:+.2f}%)" for c, v in ranking))

    fx = [c for c, _ in ranking if c != "XAU"]
    if len(fx) >= 2:
        strong, weak = fx[0], fx[-1]
        aligned = [a.symbol for a in analyses if a.base == strong and a.quote == weak]
        opposite = [a.symbol for a in analyses if a.base == weak and a.quote == strong]
        if aligned:
            lines.append(f"   💡 {strong} قوی‌ترین و {weak} ضعیف‌ترین ارز است → "
                         f"{'، '.join(aligned)} هم‌جهت با جریان قدرت است ✅")
        elif opposite:
            lines.append(f"   💡 {strong} قوی‌ترین و {weak} ضعیف‌ترین ارز است → "
                         f"{'، '.join(opposite)} خلاف جهت جریان قدرت است ⚠️")
        else:
            lines.append(f"   💡 قوی‌ترین ارز: {strong} | ضعیف‌ترین ارز: {weak} "
                         f"(جفت مستقیم این دو در پوشش ما نیست)")
    return "\n".join(lines)


def render_report(analyses: List[SymbolAnalysis],
                  ranking: List[Tuple[str, float]],
                  source_name: str,
                  tv_map: dict | None = None,
                  tv_tf: str = "4h") -> str:
    """گزارش کامل کنسول."""
    now = datetime.now(timezone.utc)
    stamps = [a.last_candle for a in analyses if a.last_candle]
    last = max(stamps).strftime("%Y-%m-%d %H:%M") if stamps else "—"
    src_fa = SOURCE_FA.get(source_name, source_name)
    tv_map = tv_map or {}
    tv_on = bool(tv_map)

    parts = [
        DSEP,
        "🔎 گزارش موتور تکنیکال — دستیار سیگنال فارکس",
        f"🕒 زمان اجرا: {now:%Y-%m-%d %H:%M} UTC | منبع داده: {src_fa}",
        f"📅 آخرین کندل بسته‌شده: {last} UTC"
        + ("" if tv_on else " | ⚠️ تاییدیه تریدینگ‌ویو این بار در دسترس نبود"),
        DSEP,
    ]
    for a in analyses:
        parts.append(render_symbol(a, tv=tv_map.get(a.symbol), tv_tf=tv_tf))
    strength = render_strength(ranking, analyses)
    if strength:
        parts.append(strength)
    if any(a.symbol == "XAUUSD" for a in analyses):
        parts.append(SEP)
        parts.append("📎 طلا از Yahoo به‌صورت فیوچرز (GC=F) است — اختلاف چند دلاری با قیمت اسپات طبیعی است")
    parts.append("")
    parts.append("⚠️ این گزارش فقط تحلیل است، نه دستور معامله — تصمیم نهایی با شماست")
    parts.append(DSEP)
    return "\n".join(parts)
