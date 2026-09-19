# -*- coding: utf-8 -*-
"""گزارش‌نویس فارسی سیگنال‌ها (مرحله ۳).

دو خروجی:
  render_signal()        — پیام کامل یک سیگنال (قالب طراحی پروژه) با دلایل
  render_judge_summary() — بخش «⚖️ داور» در گزارش دوره‌ای: سرنوشت همهٔ نمادها،
                           چه آن‌هایی که سیگنال گرفتند و چه آن‌هایی که رد شدند

قرارداد اعداد (مطابق src/fa.py):
  امتیاز، پیپ، درصد، شمارش‌ها → فارسی | قیمت‌ها → لاتین (برای تایپ در متاتریدر)
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from ..fa import fa_date, fa_num, fa_pips, fa_ratio
from ..judge.scoring import DIR_EMOJI, Judgment, Signal

SEP = "─" * 62
DSEP = "═" * 62


def fmt_price(v: float, pip: float) -> str:
    """قیمت با تعداد اعشار متناسب با pip (JPY سه رقم، طلا یک رقم).

    عمداً با ارقام لاتین: این عددها را کاربر در پلتفرم معاملاتی تایپ می‌کند.
    """
    if not v or not math.isfinite(v):
        return "—"
    dec = max(0, min(6, int(round(-math.log10(pip))) + 1)) if pip > 0 else 2
    return f"{v:.{dec}f}"


def stars(n: int) -> str:
    return "⭐" * max(0, min(5, int(n)))


# ══════════════════════════════════════════════════════════════
#  پیام یک سیگنال
# ══════════════════════════════════════════════════════════════
def render_signal(s: Signal, include_footer: bool = True) -> str:
    """پیام کامل سیگنال — همان قالبی که در طرح طراحی آمده."""
    emoji = DIR_EMOJI.get(s.direction, "⚪")
    pair = s.symbol if len(s.symbol) != 6 else f"{s.symbol[:3]}/{s.symbol[3:]}"

    lines = [
        DSEP,
        f"{emoji} سیگنال {s.direction_fa.split()[0]} — {pair}",
        f"{s.fa_name}",
        f"{stars(s.stars)} پشتوانه: {fa_num(s.score)} از {fa_num(s.max_score)}",
        f"🕒 {fa_date(s.now)} UTC",
        f"💹 سشن: {s.session_fa}",
        "",
        "چرا این سیگنال صادر شد؟",
    ]

    # مدارک مثبت اول، بعد آن‌هایی که امتیاز نگرفتند (شفافیت کامل)
    for e in sorted(s.evidences, key=lambda x: (-x.points, x.key)):
        if e.points > 0:
            lines.append(f"{e.icon} {e.label_fa} (+{fa_num(e.points)}) — {e.detail_fa}")
    missing = [e for e in s.evidences if e.points == 0]
    if missing:
        lines.append("")
        lines.append("مدارکی که امتیاز نگرفتند (صادقانه):")
        for e in missing:
            lines.append(f"{e.icon} {e.label_fa} (۰ از {fa_num(e.max_points)}) — {e.detail_fa}")

    if s.warnings:
        lines.append("")
        lines.append("⚠️ هشدارها")
        for w in s.warnings:
            lines.append(f"   • {w}")

    lines += [
        "",
        f"📍 ورود:     {fmt_price(s.entry, s.pip)}",
        f"🛑 حد ضرر:  {fmt_price(s.sl, s.pip)}"
        f"   ({fa_pips(abs(s.entry - s.sl), s.pip, s.is_gold)} فاصله)",
        f"🎯 هدف:      {fmt_price(s.tp, s.pip)}"
        f"   ({fa_pips(abs(s.tp - s.entry), s.pip, s.is_gold)} فاصله)",
        f"⚖️ نسبت سود به ریسک: ۱:{fa_ratio(s.rr)}",
        "",
        "💰 ریسک پیشنهادی: حداکثر ۱٪ از سرمایه در این معامله",
        f"🌊 نوسان متوسط ساعتی (ATR): {fa_pips(s.atr, s.pip, s.is_gold)}",
    ]
    # نکته: sl_capped عمداً اینجا دوباره چاپ نمی‌شود — همان محتوا در بخش
    # «⚠️ هشدارها» آمده و تکرارش پیام را شلوغ می‌کرد.

    if include_footer:
        lines += [
            "",
            "⚠️ این یک پیشنهاد است، نه دستور معامله. هیچ سیستمی سود را تضمین نمی‌کند؛",
            "   مسئولیت هر معامله با خودت است.",
            DSEP,
        ]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#  بخش «داور» در گزارش دوره‌ای
# ══════════════════════════════════════════════════════════════
def _reason_short(j: Judgment, min_score: int = 7) -> str:
    """دلیل کوتاه رد شدن — برای جدول خلاصه."""
    if j.signal:
        return "سیگنال صادر شد ✅"
    if j.reject_reason == "VETO":
        return "؛ ".join(v.title_fa for v in j.vetoes[:2])
    if j.reject_reason == "LOW_SCORE":
        # کمبود نسبت به **آستانه**، نه نسبت به حداکثر ممکن
        return (f"امتیاز ناکافی — {fa_num(max(0, min_score - j.score))} امتیاز تا "
                f"آستانهٔ {fa_num(min_score)} کم داشت")
    if j.reject_reason == "NO_SETUP":
        return j.reject_detail or "ستاپی شکل نگرفته"
    if j.reject_reason == "CAPPED":
        return "به سقف تعداد سیگنال در این چرخه رسید"
    if j.reject_reason == "DISABLED":
        return "داور خاموش است"
    return j.reject_detail or "—"


def render_judge_summary(judgments: list[Judgment], min_score: int = 7,
                         now: Optional[datetime] = None) -> str:
    """خلاصهٔ داوری همهٔ نمادها — «حلقهٔ صداقت»: چرا سیگنال ندادیم هم مهم است."""
    if not judgments:
        return ""
    lines = [SEP,
             f"⚖️ داور امتیازدهی — آستانهٔ صدور سیگنال: {fa_num(min_score)} از "
             f"{fa_num(judgments[0].max_score)} امتیاز"]

    signals = [j for j in judgments if j.signal]
    if signals:
        lines.append(f"   🎯 {fa_num(len(signals))} سیگنال صادر شد:")
        for j in sorted(signals, key=lambda x: -x.score):
            s = j.signal
            lines.append(
                f"   {DIR_EMOJI.get(s.direction, '⚪')} {j.symbol:<7} "
                f"{s.direction_fa.split()[0]:<5} {stars(s.stars)} "
                f"{fa_num(j.score)}/{fa_num(j.max_score)} | ورود {fmt_price(s.entry, s.pip)}"
                f" | حد ضرر {fmt_price(s.sl, s.pip)} | هدف {fmt_price(s.tp, s.pip)}")
    else:
        lines.append("   ⛔ هیچ سیگنالی صادر نشد — و این خودش یک خروجی معتبر است.")
        lines.append("      وعدهٔ سیستم این است که «سیگنال بدون پشتوانه ندهد»، "
                     "نه اینکه «همیشه سیگنال بدهد».")

    rejected = [j for j in judgments if not j.signal]
    if rejected:
        lines.append("")
        lines.append("   سرنوشت بقیهٔ نمادها:")
        for j in rejected:
            score = (f"{fa_num(j.score)}/{fa_num(j.max_score)}"
                     if j.reject_reason in ("LOW_SCORE", "CAPPED") else "—")
            lines.append(f"   • {j.symbol:<7} {score:>7}  {_reason_short(j, min_score)}")
            if j.reject_reason == "NO_SETUP" and j.reject_detail:
                lines.append(f"       ↳ {j.reject_detail}")
            elif j.reject_reason == "LOW_SCORE":
                got = [e.label_fa for e in j.evidences if e.points > 0]
                miss = [e.label_fa for e in j.evidences if e.points == 0]
                if got:
                    lines.append(f"       ✅ داشت: {'، '.join(got)}")
                if miss:
                    lines.append(f"       ➖ نداشت: {'، '.join(miss)}")
    return "\n".join(lines)


def render_no_signals_note(judgments: list[Judgment]) -> str:
    """یک خط کوتاه برای تلگرام وقتی هیچ سیگنالی نیست (جلوگیری از پیام خالی)."""
    vet = sum(1 for j in judgments if j.reject_reason == "VETO")
    low = sum(1 for j in judgments if j.reject_reason == "LOW_SCORE")
    nos = sum(1 for j in judgments if j.reject_reason == "NO_SETUP")
    return (f"⛔ سیگنالی صادر نشد — {fa_num(vet)} وتو، {fa_num(low)} امتیاز ناکافی، "
            f"{fa_num(nos)} بدون ستاپ (از {fa_num(len(judgments))} نماد)")
