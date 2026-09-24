# -*- coding: utf-8 -*-
"""گزارش‌های فارسی ژورنال — مرحله ۴.

  render_stats()   📊 کارنامه دقت (کلی + هفتگی + تفکیک‌ها + همبستگی مدرک↔برد)
  render_nightly() 🌙 خلاصهٔ شبانه (امروز چه گذشت + چه چیزی باز است)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ..fa import fa_num
from ..journal.stats import Stats
from ..journal.store import Entry
from ..journal.tracker import OUTCOME_FA

SEP = "─" * 62
DSEP = "═" * 62

# زیر این تعداد سیگنال بسته، ارقام قطعیت آماری ندارند — صادقانه می‌گوییم
MIN_SAMPLE = 30


def _pct(v: Optional[float]) -> str:
    return f"{fa_num(f'{v * 100:.0f}')}٪" if v is not None else "—"


def _r(v: Optional[float]) -> str:
    return f"{fa_num(f'{v:+.2f}')}" if v is not None else "—"


def _bucket_line(b) -> str:
    hr = _pct(b.hit_rate)
    return (f"بسته {fa_num(b.closed)} · برد {fa_num(b.wins)} · باخت {fa_num(b.losses)} · "
            f"منقضی {fa_num(b.expired)} · نرخ برد {hr} · میانگین R {_r(b.avg_r)}")


def render_stats(stats: Stats, open_entries: list[Entry] | None = None,
                 now: Optional[datetime] = None) -> str:
    """📊 کارنامه دقت — خروجی اصلی «حلقهٔ صداقت»."""
    now = now or stats.now or datetime.now(timezone.utc)
    o = stats.overall
    lines = [
        DSEP,
        "📊 کارنامهٔ دقت — ODIN Assistant",
        f"🕒 {fa_num(f'{now:%Y-%m-%d %H:%M}')} UTC",
        DSEP,
        "─── کلی ───",
        f"   سیگنال ثبت‌شده: {fa_num(stats.total)} | بسته: {fa_num(o.closed)} "
        f"(برد {fa_num(o.wins)} · باخت {fa_num(o.losses)} · منقضی {fa_num(o.expired)}) "
        f"| باز: {fa_num(stats.open_count)}",
        f"   نرخ برد (نتیجهٔ قطعی): {_pct(o.hit_rate)}   "
        f"| نرخ برد (کل بسته‌شده): {_pct(o.closed_win_rate)}",
        f"   میانگین R هر معامله: {_r(o.avg_r)}   "
        f"| مجموع R: {_r(o.r_sum)}",
    ]

    # هفتهٔ جاری در برابر هفتهٔ قبل
    tw, lw = stats.this_week_key, stats.last_week_key
    lines.append("─── این هفته در مقایسه با هفتهٔ قبل ──")
    if tw and tw in stats.by_week:
        lines.append(f"   این هفته ({fa_num(tw)}): {_bucket_line(stats.by_week[tw])}")
    else:
        lines.append("   این هفته: هنوز سیگنالی بسته نشده")
    if lw and lw in stats.by_week:
        b_now = stats.by_week.get(tw)
        b_prev = stats.by_week[lw]
        lines.append(f"   هفتهٔ قبل ({fa_num(lw)}): {_bucket_line(b_prev)}")
        if b_now and b_now.hit_rate is not None and b_prev.hit_rate is not None:
            d = b_now.hit_rate - b_prev.hit_rate
            arrow = "↗ بهتر" if d > 0.001 else ("↘ بدتر" if d < -0.001 else "→ بدون تغییر")
            lines.append(f"   روند هفته‌به‌هفته: {arrow} ({fa_num(f'{d * 100:+.0f}')} نقطهٔ درصد)")
    else:
        lines.append("   هفتهٔ قبل: داده‌ای برای مقایسه نیست (اولین هفتهٔ ثبت است)")

    # تفکیک نماد
    if stats.by_symbol:
        lines.append("─── به تفکیک نماد ───")
        for k in sorted(stats.by_symbol, key=lambda x: -(stats.by_symbol[x].r_sum)):
            lines.append(f"   {k:<8} {_bucket_line(stats.by_symbol[k])}")

    # تفکیک جهت
    if stats.by_direction:
        lines.append("─── به تفکیک جهت ───")
        for k, b in stats.by_direction.items():
            fa_dir = "خرید 🟢" if k == "BUY" else "فروش 🔴"
            lines.append(f"   {fa_dir:<8} {_bucket_line(b)}")

    # تفکیک امتیاز — پاسخ به «آیا آستانهٔ ۷ درست است؟»
    if stats.by_score:
        lines.append("─── به تفکیک امتیاز پشتوانه ───")
        for k in ("۷", "۸", "۹", "۰–۱۱"):
            if k in stats.by_score:
                lines.append(f"   امتیاز {k:<6} {_bucket_line(stats.by_score[k])}")
        lines.append("   ↳ اگر بازهٔ بالاتر نرخ برد بهتری ندارد، آستانه/وزن‌ها بازنگری می‌خواهند.")

    # همبستگی مدرک↔برد
    if stats.by_evidence:
        lines.append("─── کدام مدرک واقعاً به درد خورده؟ ───")
        rows = sorted(stats.by_evidence.items(),
                      key=lambda kv: -((kv[1].hit_rate or 0.0)))
        for k, b in rows:
            lines.append(f"   {k:<12} {_bucket_line(b)}")

    # همبستگی استراتژی↔برد (S4 — v0.27؛ رکوردها از v0.26 برچسب دارند)
    if stats.by_strategy:
        lines.append("─── کدام استراتژی واقعاً به درد خورده؟ ───")
        rows = sorted(stats.by_strategy.items(),
                      key=lambda kv: -((kv[1].hit_rate or 0.0)))
        for k, b in rows:
            lines.append(f"   {k:<16} {_bucket_line(b)}")
        lines.append("   ↳ سرنوشتِ سیگنال‌هایی که استراتژی با آن‌ها توافق کرد"
                     " — همبستگی ≠ علیت (صادقانه).")
    elif stats.total:
        lines.append("─── به تفکیک استراتژی ───")
        lines.append("   رکوردهای پیش از v0.26 برچسب استراتژی ندارند — از اولین"
                     " سیگنالِ v0.26 این بخش پر می‌شود.")

    # یادآوری صداقت دربارهٔ حجم نمونه
    lines.append("")
    if o.closed == 0:
        lines.append("   هنوز هیچ سیگنالی بسته نشده — کارنامه با اولین نتیجه معنا پیدا می‌کند.")
    elif o.closed < MIN_SAMPLE:
        lines.append(f"   ⚠️ فقط {fa_num(o.closed)} سیگنال بسته شده؛ زیر {fa_num(MIN_SAMPLE)} مورد، "
                     f"این درصدها نویز آماری‌اند نه «دقت واقعی». برای قضاوت عجله نکن.")
    lines.append("   ⚠️ این کارنامه توصیف گذشته است، نه وعدهٔ آینده.")
    lines.append(DSEP)
    return "\n".join(lines)


def render_nightly(entries: list[Entry], stats: Stats,
                   now: Optional[datetime] = None) -> str:
    """🌙 خلاصهٔ شبانه — بعد از بسته‌شدن سشن نیویورک."""
    now = now or datetime.now(timezone.utc)
    day = now.date()
    today = [e for e in entries if e.ts.date() == day]
    closed_today = [e for e in today if not e.is_open]
    open_now = [e for e in entries if e.is_open]
    o = stats.overall

    lines = [
        DSEP,
        f"🌙 خلاصهٔ شبانه — {fa_num(f'{now:%Y-%m-%d}')}",
        DSEP,
        f"   سیگنال‌های امروز: {fa_num(len(today))} "
        + (f"(از این تعداد {fa_num(sum(1 for e in today if e.sent))} مورد به تلگرام رفت)"
           if today else ""),
    ]
    if closed_today:
        lines.append("   نتیجهٔ سیگنال‌هایی که امروز بسته شدند:")
        for e in closed_today:
            lines.append(f"      {OUTCOME_FA.get(e.outcome, e.outcome)} — {e.symbol} "
                         f"{('خرید' if e.direction == 'BUY' else 'فروش')} "
                         f"(R {_r(e.r)})")
    else:
        lines.append("   امروز سیگنالی بسته نشد.")

    if open_now:
        lines.append(f"   هنوز باز ({fa_num(len(open_now))}):")
        for e in open_now:
            lines.append(f"      • {e.symbol} {('خرید' if e.direction == 'BUY' else 'فروش')} "
                         f"ورود {e.entry:.5g} | SL {e.sl:.5g} | TP {e.tp:.5g} "
                         f"| امتیاز {fa_num(e.score)}")
    else:
        lines.append("   هیچ سیگنال بازی باقی نمانده.")

    lines += [
        "",
        f"   کارنامهٔ کلی تا امروز: نرخ برد {_pct(o.hit_rate)} | "
        f"میانگین R {_r(o.avg_r)} | بسته‌شده {fa_num(o.closed)}",
        "",
        "⚠️ این خلاصه توصیف عملکرد است، نه سیگنال جدید.",
        DSEP,
    ]
    return "\n".join(lines)
