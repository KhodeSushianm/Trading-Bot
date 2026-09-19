# -*- coding: utf-8 -*-
"""گزارش‌نویس فارسی برای موتور فاندامنتال و اخبار (مرحله ۲).

سه خروجی اصلی:
  render_calendar()    — بخش تقویم اقتصادی داخل گزارش دوره‌ای
  render_news()        — بخش اخبار داخل گزارش دوره‌ای
  render_briefing()    — 🌅 بریفینگ صبحگاهی (گزارش مستقل، قبل از باز شدن لندن)
  render_event_alert() — 🚨 هشدار ۳۰ دقیقه قبل از رویداد پراثر
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from ..analysis.technical import SymbolAnalysis
from ..fundamental.calendar import (CalendarEvent, CalendarSnapshot, IMPACT_FA,
                                    next_high_impact, upcoming_events)
from ..fundamental.news import NewsSnapshot
from .console import DSEP, SEP, SOURCE_FA, TREND_FA, VERDICT_FA, _fmt_price

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

WEEKDAY_FA = {0: "دوشنبه", 1: "سه‌شنبه", 2: "چهارشنبه", 3: "پنجشنبه",
              4: "جمعه", 5: "شنبه", 6: "یکشنبه"}
MONTH_FA = {1: "ژانویه", 2: "فوریه", 3: "مارس", 4: "آوریل", 5: "مه", 6: "ژوئن",
            7: "ژوئیه", 8: "اوت", 9: "سپتامبر", 10: "اکتبر", 11: "نوامبر", 12: "دسامبر"}


def fa_num(v) -> str:
    """تبدیل ارقام به فارسی."""
    return str(v).translate(_FA_DIGITS)


def fa_date(dt: datetime, with_time: bool = True) -> str:
    """«شنبه ۱۹ سپتامبر ۲۰۲۶ — ۱۴:۳۰»"""
    s = f"{WEEKDAY_FA[dt.weekday()]} {fa_num(dt.day)} {MONTH_FA[dt.month]} {fa_num(dt.year)}"
    return f"{s} — {fa_num(f'{dt:%H:%M}')}" if with_time else s


def _countdown(minutes: float) -> str:
    """«۱۲ دقیقه دیگر» / «۲ ساعت و ۵ دقیقه دیگر» / «۴۵ دقیقه پیش»"""
    m = int(round(minutes))
    if m < 0:
        m = -m
        tail = "پیش"
    else:
        tail = "دیگر"
    if m < 60:
        return f"{fa_num(m)} دقیقه {tail}"
    h, rem = divmod(m, 60)
    if rem:
        return f"{fa_num(h)} ساعت و {fa_num(rem)} دقیقه {tail}"
    return f"{fa_num(h)} ساعت {tail}"


# ── تقویم اقتصادی ──────────────────────────────────────────────
def render_calendar(snap: CalendarSnapshot, symbols_cfg: Iterable[dict],
                    now: Optional[datetime] = None, horizon_hours: float = 48.0,
                    max_items: int = 12) -> str:
    """بخش «🏦 تقویم اقتصادی» برای گزارش دوره‌ای."""
    now = now or datetime.now(timezone.utc)
    if not snap.events:
        if snap.error:
            why = snap.error
            body = [f"   ⚠️ در دسترس نبود — {str(why)[:80]}",
                    "   ℹ️ تحلیل تکنیکال بدون وتوی خبری انجام شده؛ با احتیاط بیشتری معامله کن"]
        else:
            body = ["   ℹ️ منبع تقویم برای این هفته هیچ رویدادی برنگرداند (تقویم خالی)"]
        return "\n".join([SEP, "🏦 تقویم اقتصادی:"] + body)

    syms = list(symbols_cfg)
    events = upcoming_events(snap, now, hours=horizon_hours, limit=max_items)
    week = f"{fa_num(snap.week_range[0])} تا {fa_num(snap.week_range[1])}"
    head = [SEP,
            f"🏦 تقویم اقتصادی — رویدادهای {fa_num(int(horizon_hours))} ساعت آینده "
            f"(منبع: {snap.source}، پوشش هفتهٔ {week})"]
    if snap.stale:
        head.append(f"   ⚠️ این داده از کش قدیمی است (آخرین دریافت موفق: "
                    f"{fa_date(snap.fetched_at) if snap.fetched_at else '—'})")

    if not events:
        head += ["   ✅ رویداد پراثر یا متوسطی در این بازه نیست — پنجرهٔ معاملاتی باز است",
                 "   ℹ️ فید ForexFactory فقط هفتهٔ جاری را پوشش می‌دهد؛ در روزهای پایانی هفته "
                 "ممکن است رویداد آینده‌ای در آن نباشد (یعنی «خبری نیست»، نه «داده خراب است»)."]
        n_high_today = len([e for e in snap.events if e.impact == "HIGH"])
        head.append(f"   📊 کل این هفته {fa_num(n_high_today)} رویداد پراثر داشت")
        return "\n".join(head)

    lines = list(head)
    last_day = None
    for e in events:
        day = e.when.date()
        if day != last_day:
            day_fa = (f"{WEEKDAY_FA[e.when.weekday()]} {fa_num(e.when.day)} "
                      f"{MONTH_FA[e.when.month]}")
            lines.append(f"   ── {day_fa} ──")
            last_day = day
        exp = e.explain(syms, now).splitlines()
        lines.append("   " + exp[0])          # سطر اول هم‌تراز با بقیهٔ گزارش
        lines.extend(exp[1:])
        lines.append(f"      ⏰ {_countdown(e.minutes_from(now))} "
                     f"({fa_num(f'{e.when:%H:%M}')} UTC) | {IMPACT_FA.get(e.impact, e.impact)} "
                     f"| دسته: {e.category}")
    if len(events) == max_items:
        lines.append(f"   … و رویدادهای بیشتر (فقط {fa_num(max_items)} مورد اول نمایش داده شد)")
    return "\n".join(lines)


def render_veto(events: Iterable[CalendarEvent], symbol: str, now: Optional[datetime] = None) -> str:
    """خط وتوی سیگنال برای یک نماد (داخل بخش همان نماد در گزارش)."""
    now = now or datetime.now(timezone.utc)
    evs = list(events)
    if not evs:
        return ""
    names = "، ".join(f"«{e.title_fa}» ({e.country_fa})" for e in evs[:3])
    soonest = min(evs, key=lambda e: abs(e.minutes_from(now)))
    return (f"   🚫 وتو فعال: {names} — {_countdown(soonest.minutes_from(now))}\n"
            f"      طبق قوانین سیستم، در این پنجره سیگنال {symbol} صادر نمی‌شود "
            f"(نوسان خبری غیرقابل پیش‌بینی است)")


# ── اخبار ──────────────────────────────────────────────────────
def render_news(snap: NewsSnapshot, max_items: int = 8) -> str:
    """بخش «📰 اخبار بازار» برای گزارش دوره‌ای."""
    if not snap.ok:
        why = snap.error or "خبر مرتبطی در بازهٔ زمانی پیدا نشد"
        return "\n".join([SEP, "📰 اخبار بازار:",
                          f"   ⚠️ در دسترس نبود — {str(why)[:90]}",
                          "   ℹ️ این گزارش فقط بر پایهٔ تحلیل تکنیکال و تقویم اقتصادی است"])

    lines = [SEP, f"📰 اخبار بازار — {fa_num(len(snap.items))} خبر مرتبط "
                  f"({fa_num(snap.feeds_ok)} فید موفق"
                  + (f"، {fa_num(snap.feeds_failed)} ناموفق" if snap.feeds_failed else "") + ")"]
    if snap.breaking:
        lines.append(f"   🚨 {fa_num(len(snap.breaking))} خبر فوری در این بازه!")

    shown = 0
    for it in snap.items:
        if shown >= max_items:
            break
        shown += 1
        star = "⭐" * min(it.score, 5)
        age = _countdown(-it.age_minutes) if it.age_minutes else ""
        flag = "🚨 " if it.breaking else ("📚 " if it.roundup else "")
        lines.append(f"   {flag}[{star}] {it.headline_fa(72)}")
        bits = []
        if it.direction_fa():
            bits.append(f"جهت: {it.direction_fa()}")
        if it.keywords:
            bits.append("کلیدواژه: " + "، ".join(it.keywords))
        if it.source:
            bits.append(it.source)
        if age:
            bits.append(age)
        if bits:
            lines.append("        " + " | ".join(bits))

    if snap.stale_feeds:
        lines.append(f"   ℹ️ فیدهای بدون خبر تازه: {'، '.join(snap.stale_feeds[:3])}")
    lines.append("   ⚠️ جهت‌دهی اخبار بر پایهٔ کلیدواژه است (سرنخ، نه حکم قطعی) — "
                 "در داور امتیازدهی فقط ۱ امتیاز از ۱۰ وزن دارد")
    return "\n".join(lines)


def news_lines_for_symbol(snap: NewsSnapshot, base: str, quote: str,
                          bias: str, min_score: int = 4) -> list[str]:
    """خبرهای هم‌جهت و خلاف‌جهت با یک نماد — جدا از هم، تا کاربر بتواند قضاوت کند."""
    from ..fundamental.news import news_supports
    v = news_supports(snap, base, quote, bias, min_score=min_score)
    if not v.has_evidence:
        return []

    bias_fa = "خرید" if bias.lower().startswith("b") else "فروش"
    if v.verdict > 0:
        head = (f"   📰 اخبار، جهت «{bias_fa}» را تایید می‌کند "
                f"(+{fa_num(f'{v.votes:g}')} از ۲ رأی)")
    elif v.verdict < 0:
        head = (f"   📰 اخبار خلاف جهت «{bias_fa}» است "
                f"({fa_num(f'{v.votes:g}')} از ۲ رأی) ⚠️ — با احتیاط بیشتر")
    else:
        head = (f"   📰 اخبار دربارهٔ این نماد یکدست نیست "
                f"({fa_num(f'{v.votes:g}')} رأی) — خنثی")
    out = [head]
    for it in v.support[:2]:
        out.append(f"      ✅ موافق: {it.headline_fa(64)} [{fa_num(it.score)}/۶]")
    for it in v.contradict[:2]:
        out.append(f"      ❌ مخالف: {it.headline_fa(64)} [{fa_num(it.score)}/۶]")
    return out


# ── هشدار رویداد ───────────────────────────────────────────────
def render_event_alert(event: CalendarEvent, symbols_cfg: Iterable[dict],
                       now: Optional[datetime] = None) -> str:
    """🚨 پیام هشدار تلگرام — ۳۰ دقیقه قبل از رویداد پراثر."""
    now = now or datetime.now(timezone.utc)
    syms = list(symbols_cfg)
    pairs = [s["name"] for s in syms
             if s.get("base") == event.country or s.get("quote") == event.country]
    lines = [
        "🚨 هشدار رویداد پراثر — بازار را تنها نگذار!",
        "",
        f"{IMPACT_FA.get(event.impact, '')} {event.title_fa}",
        f"🌍 {event.country_fa} ({event.country}) | 🕒 {fa_num(f'{event.when:%H:%M}')} UTC "
        f"— {_countdown(event.minutes_from(now))}",
    ]
    if event.forecast or event.previous:
        bits = []
        if event.forecast:
            bits.append(f"پیش‌بینی: {fa_num(event.forecast)}")
        if event.previous:
            bits.append(f"قبلی: {fa_num(event.previous)}")
        lines.append("📊 " + " | ".join(bits))
    if pairs:
        lines.append(f"💱 جفت‌ارزهای تحت پوشش ما که متاثر می‌شوند: {'، '.join(pairs)}")
    lines += ["", event.explain(syms, now).split("\n", 1)[-1].strip() or ""]
    lines += [
        "",
        "⚠️ چه کار کنیم؟",
        "• ۳۰ دقیقه قبل تا ۳۰ دقیقه بعد از این رویداد، ورود جدید ممنوع است",
        "• اگر پوزیشن باز داری، حد ضرر را بررسی کن یا حجم را کم کن",
        "• اسپرد در این دقایق معمولاً چند برابر می‌شود",
        "",
        "ℹ️ تصمیم نهایی با توست — این فقط یک هشدار زمانی است.",
    ]
    return "\n".join(x for x in lines if x != "")


# ── بریفینگ صبحگاهی ────────────────────────────────────────────
def render_briefing(analyses: list[SymbolAnalysis],
                    ranking: list[tuple[str, float]],
                    cal_snap: Optional[CalendarSnapshot],
                    news_snap: Optional[NewsSnapshot],
                    symbols_cfg: Iterable[dict],
                    source_name: str = "—",
                    now: Optional[datetime] = None,
                    horizon_hours: float = 24.0) -> str:
    """🌅 بریفینگ صبحگاهی — تقویم پیش‌رو + تیترها + جهت مورد انتظار هر جفت‌ارز."""
    now = now or datetime.now(timezone.utc)
    syms = list(symbols_cfg)
    parts = [
        DSEP,
        f"🌅 بریفینگ صبحگاهی — {fa_date(now)}",
        f"🕒 {fa_num(f'{now:%H:%M}')} UTC | منبع داده: {SOURCE_FA.get(source_name, source_name)}",
        DSEP,
    ]

    # ۱) آنچه امروز در پیش است
    parts.append("▎امروز چه چیزی در پیش داریم؟")
    if cal_snap and cal_snap.ok:
        evs = upcoming_events(cal_snap, now, hours=horizon_hours,
                              impacts=("HIGH", "MEDIUM"), limit=8)
        if evs:
            for e in evs:
                pairs = [s["name"] for s in syms
                         if s.get("base") == e.country or s.get("quote") == e.country]
                tag = f" → {'، '.join(pairs)}" if pairs else ""
                parts.append(f"  {IMPACT_FA.get(e.impact, '')} {fa_num(f'{e.when:%H:%M}')} UTC "
                             f"({WEEKDAY_FA[e.when.weekday()]}): {e.title_fa} "
                             f"[{e.country_fa}]{tag}")
                if e.forecast or e.previous:
                    f_p = f"پیش‌بینی {fa_num(e.forecast)}" if e.forecast else ""
                    p_p = f"قبلی {fa_num(e.previous)}" if e.previous else ""
                    parts.append(f"       {' | '.join(x for x in (f_p, p_p) if x)}"
                                 f" — {_countdown(e.minutes_from(now))}")
        else:
            parts.append("  ✅ رویداد پراثر یا متوسطی در ۲۴ ساعت آینده نیست — روز آرامی برای معامله است")
            parts.append("  ℹ️ فید تقویم فقط هفتهٔ جاری را پوشش می‌دهد؛ شنبه/یکشنبه بازار بسته است")
        nxt = next_high_impact(cal_snap, now=now)
        if nxt and nxt.minutes_from(now) > horizon_hours * 60:
            parts.append(f"  📌 نزدیک‌ترین رویداد پراثر: {nxt.title_fa} ({nxt.country_fa}) — "
                         f"{fa_date(nxt.when)}")
    elif cal_snap:
        parts.append(f"  ⚠️ تقویم اقتصادی در دسترس نبود ({str(cal_snap.error)[:60]})")
    else:
        parts.append("  ⚠️ تقویم اقتصادی غیرفعال است")

    # ۲) پنجره‌های ممنوعه
    if cal_snap and cal_snap.ok:
        vetoes = []
        for e in upcoming_events(cal_snap, now, hours=horizon_hours, impacts=("HIGH",)):
            for s in syms:
                if s.get("base") == e.country or s.get("quote") == e.country:
                    vetoes.append((s["name"], e))
        if vetoes:
            parts.append("")
            parts.append("▎🚫 پنجره‌های ممنوعهٔ ورود (۳۰ دقیقه قبل و بعد از هر رویداد پراثر)")
            by_ev: dict[tuple, list[str]] = {}
            for name, e in vetoes:
                by_ev.setdefault((e.when, e.title_fa, e.country_fa), []).append(name)
            for (when, title, country), names in sorted(by_ev.items())[:6]:
                w = when - timedelta(minutes=30)
                t = when + timedelta(minutes=30)
                parts.append(f"  • {WEEKDAY_FA[when.weekday()]} {fa_num(f'{when:%H:%M}')} UTC — "
                             f"{title} ({country})")
                parts.append(f"       ⛔ ورود ممنوع: {fa_num(f'{w:%H:%M}')} تا {fa_num(f'{t:%H:%M}')} UTC"
                             f" → نمادهای متاثر: {'، '.join(sorted(set(names)))}")

    # ۳) تیترهای مهم
    if news_snap and news_snap.ok:
        parts.append("")
        parts.append("▎📰 تیترهایی که بازار امروز با آن‌ها باز می‌شود")
        movers = [i for i in news_snap.items if i.score >= 4 and not i.roundup][:6]
        for it in (movers or news_snap.items[:4]):
            flag = "🚨" if it.breaking else "•"
            d = f" ← {it.direction_fa()}" if it.direction_fa() else ""
            parts.append(f"  {flag} {it.headline_fa(70)}{d}")
        if not movers:
            parts.append("  ℹ️ خبر پراثری با امتیاز بالا پیدا نشد")

    # ۴) جهت مورد انتظار هر جفت‌ارز
    parts.append("")
    parts.append("▎📊 جهت مورد انتظار هر نماد (تحلیل تکنیکال)")
    if analyses:
        for a in analyses:
            if a.verdict == "DATA":
                parts.append(f"  ⚠️ {a.symbol}: داده کافی نیست")
                continue
            arrow = {"BUY_SETUP": "🟢", "SELL_SETUP": "🔴", "RANGE": "⚪", "WAIT": "⏳"}.get(a.verdict, "❔")
            lvl = []
            if a.support:
                lvl.append(f"حمایت {_fmt_price(a.support, a.pip)}")
            if a.resistance:
                lvl.append(f"مقاومت {_fmt_price(a.resistance, a.pip)}")
            parts.append(f"  {arrow} {a.symbol}: روند {TREND_FA[a.trend]} | ADX {fa_num(f'{a.adx:.0f}')} "
                         f"| RSI {fa_num(f'{a.rsi:.0f}')} | قیمت {_fmt_price(a.price, a.pip)}"
                         + (f" | {'، '.join(lvl)}" if lvl else ""))
            parts.append(f"       {VERDICT_FA.get(a.verdict, a.verdict)}")
    else:
        parts.append("  ⚠️ هیچ نمادی تحلیل نشد")

    # ۵) قدرت ارزها
    if ranking:
        parts.append("")
        parts.append("▎💱 جریان قدرت ارزها (۲۴ ساعت اخیر)")
        parts.append("  " + "  >  ".join(f"{c} ({fa_num(f'{v:+.2f}')}٪)" for c, v in ranking))
        fx = [c for c, _ in ranking if c != "XAU"]
        if len(fx) >= 2:
            parts.append(f"  💡 ایده: قوی‌ترین ({fx[0]}) در برابر ضعیف‌ترین ({fx[-1]}) — "
                         f"هم‌جهت با جریان پول")

    parts += ["", "⚠️ این بریفینگ فقط تحلیل است، نه دستور معامله — تصمیم نهایی با شماست", DSEP]
    return "\n".join(parts)
