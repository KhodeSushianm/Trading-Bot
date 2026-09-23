# -*- coding: utf-8 -*-
"""میخ‌های رفتاری قواعد داور — فاز ۴ (۷ وتو + ۸ شاهد + risk → rule-plugin).

اجرا:  python tests/test_judge_rules.py     (از ریشهٔ ریپو — آفلاین، بدون شبکه)

انضباط «اول میخ، بعد چکش» (همان الگوی فاز ۳):
  • این تست‌ها ابتدا روی کد *فعلی* داور (مسیر مستقیم src/judge/scoring)
    نوشته و سبز شده‌اند (کامیتِ میخ‌ها).
  • سپس سوییچ فاز ۴ انجام می‌شود (استخراج ۷ تابع وتو از collect_vetoes +
    ۱۵ adapter قاعده در src/plugins/judge.py + تفکیک judge-risk) و **همین
    تست‌ها بدون هیچ تغییری** باید سبز بمانند — اثبات اینکه
    ترتیب/آستانه‌ها/متن‌های فارسی بایت‌به‌بایت حفظ شده‌اند.
  • باتری طلاییِ کامل سناریوها: tests/golden/judge_rules_golden.json
    (با tests/golden/gen_judge_golden.py ضبط شده — دادهٔ ساختگیِ قطعی،
    لحظه‌های ثابت، بدون شبکه).

پوشش: شلیک تکی هر ۷ وتو (کلید+عنوان+متن) · ترتیب چندوتوی هم‌زمان ·
کلیدهای فعال/غیرفعال موجود config · هر ۳۸ شاخهٔ ۸ شاهد (امتیاز+برچسب+
متن‌های کلیدی) · BUY/SELL طلایی ۱۱/۱۱ · LOW_SCORE + هشدارهای ⚠️ · هر ۵
دلیل NO_SETUP · CAPPED · judge_all با ۴ سرنوشت · ریاضی SL/TP (۶ حالت).

⚠️ این فایل و فایل طلایی «میخ»اند: در طول فاز ۴ هیچ خطشان عوض نمی‌شود.
   parity مسیر پلاگین (adapter == فراخوانی مستقیم) در tests/test_plugins.py
   اثبات می‌شود، نه اینجا.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

COUNT = 0


def A(cond: bool, msg: str) -> None:
    global COUNT
    assert cond, msg
    COUNT += 1


# ── بارگذاری هارنس طلایی (بدون اجرای main آن) ─────────────────
_spec = importlib.util.spec_from_file_location(
    "gen_judge_golden", HERE / "golden" / "gen_judge_golden.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

# باتری یک‌بار اجرا می‌شود — همهٔ میخ‌های زیر روی همین خروجیِ منجمدند.
# (بعد از سوییچ فاز ۴ هم *همین* فراخوانی‌ها تکرار می‌شوند — مسیر مستقیم.)
BAT = gen.build_battery()


# ══════════════════════════════════════════════════════════════
#  جدول میخ‌های متنی — بایت‌به‌بایت از کد فعلی ضبط شده‌اند
# ══════════════════════════════════════════════════════════════
VETO_TITLES = {
    "DATA": "⚠️ دادهٔ ناکافی",
    "WEEKEND": "🔒 بازار بسته است",
    "TF_CONFLICT": "🔀 تضاد جهت بین تایم‌فریم‌ها",
    "RANGE": "😴 بازار بی‌روند (رنج)",
    "EVENT": "📅 رویداد پراثر تقویم",
    "VOL_SPIKE": "📈 جهش غیرعادی نوسان",
    "BREAKING_NEWS": "🚨 خبر فوری",
}

VETO_DETAILS = {
    "DATA": "تعداد کندل‌ها برای محاسبهٔ EMA200 کافی نیست — تحلیل قابل اتکا نیست",
    "WEEKEND": "شنبه — بازار فارکس بسته است 🔒",
    "TF_CONFLICT": "روند ۴ ساعته صعودی 📈 است ولی ۱ ساعته هم‌جهت نیست — طبق قوانین، معامله در تضاد تایم‌فریم ممنوع است",
    "RANGE": "ADX=14 زیر آستانهٔ 20 است — استراتژی روندی در بازار رنج کار نمی‌کند",
    "EVENT": "«نرخ بهره فدرال رزرو» (آمریکا) — ۱۲ دقیقه بعد. نوسان خبری غیرقابل پیش‌بینی است",
    "VOL_SPIKE": "ATR یک‌ساعتهٔ فعلی ۳.۲ برابر میانگین ۱۰۰ کندل اخیر است (آستانهٔ وتو: ۲.۰ برابر). در این شرایط اسپرد وید می‌شود و حد ضرر قابل اتکا نیست",
    "BREAKING_NEWS": "«🚨 BREAKING: ECB surprise decision» — تا آرام‌شدن بازار صبر کن",
}

EV_PINS = {
    "fund_cal_failed": ({
        'key': "fundamental", 'label_fa': "پنجرهٔ فاندامنتال پاک",
        'points': 0, 'max_points': 2,
        'ok': False, 'unavailable': True}),
    "fund_cal_off": ({
        'key': "fundamental", 'label_fa': "پنجرهٔ فاندامنتال پاک",
        'points': 0, 'max_points': 2,
        'ok': False, 'unavailable': True}),
    "fund_clean": ({
        'key': "fundamental", 'label_fa': "پنجرهٔ فاندامنتال پاک",
        'points': 2, 'max_points': 2,
        'ok': True, 'unavailable': False}),
    "fund_high_soon": ({
        'key': "fundamental", 'label_fa': "پنجرهٔ فاندامنتال پاک",
        'points': 0, 'max_points': 2,
        'ok': False, 'unavailable': False}),
    "fund_med_soon": ({
        'key': "fundamental", 'label_fa': "پنجرهٔ فاندامنتال پاک",
        'points': 1, 'max_points': 2,
        'ok': True, 'unavailable': False}),
    "level_buy_close": ({
        'key': "level", 'label_fa': "واکنش به سطح کلیدی (حمایت)",
        'points': 2, 'max_points': 2,
        'ok': True, 'unavailable': False}),
    "level_buy_far": ({
        'key': "level", 'label_fa': "واکنش به سطح کلیدی (حمایت)",
        'points': 0, 'max_points': 2,
        'ok': False, 'unavailable': False}),
    "level_buy_near": ({
        'key': "level", 'label_fa': "واکنش به سطح کلیدی (حمایت)",
        'points': 1, 'max_points': 2,
        'ok': True, 'unavailable': False}),
    "level_buy_unavailable": ({
        'key': "level", 'label_fa': "واکنش به سطح کلیدی (حمایت)",
        'points': 0, 'max_points': 2,
        'ok': False, 'unavailable': True}),
    "level_sell_close": ({
        'key': "level", 'label_fa': "واکنش به سطح کلیدی (مقاومت)",
        'points': 2, 'max_points': 2,
        'ok': True, 'unavailable': False}),
    "mom_buy_confirm": ({
        'key': "momentum", 'label_fa': "تایید مومنتوم (RSI)",
        'points': 1, 'max_points': 1,
        'ok': True, 'unavailable': False}),
    "mom_buy_high": ({
        'key': "momentum", 'label_fa': "تایید مومنتوم (RSI)",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': False}),
    "mom_buy_not_rising": ({
        'key': "momentum", 'label_fa': "تایید مومنتوم (RSI)",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': False}),
    "mom_buy_oversold": ({
        'key': "momentum", 'label_fa': "تایید مومنتوم (RSI)",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': False}),
    "mom_sell_confirm": ({
        'key': "momentum", 'label_fa': "تایید مومنتوم (RSI)",
        'points': 1, 'max_points': 1,
        'ok': True, 'unavailable': False}),
    "mom_sell_low": ({
        'key': "momentum", 'label_fa': "تایید مومنتوم (RSI)",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': False}),
    "mom_sell_overbought": ({
        'key': "momentum", 'label_fa': "تایید مومنتوم (RSI)",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': False}),
    "news_contra": ({
        'key': "news", 'label_fa': "تایید خبری",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': False}),
    "news_neutral": ({
        'key': "news", 'label_fa': "تایید خبری",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': False}),
    "news_supports": ({
        'key': "news", 'label_fa': "تایید خبری",
        'points': 1, 'max_points': 1,
        'ok': True, 'unavailable': False}),
    "news_supports_sell": ({
        'key': "news", 'label_fa': "تایید خبری",
        'points': 1, 'max_points': 1,
        'ok': True, 'unavailable': False}),
    "news_unavailable": ({
        'key': "news", 'label_fa': "تایید خبری",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': True}),
    "sess_closed": ({
        'key': "session", 'label_fa': "زمان‌بندی مناسب (سشن)",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': False}),
    "sess_liquid": ({
        'key': "session", 'label_fa': "زمان‌بندی مناسب (سشن)",
        'points': 1, 'max_points': 1,
        'ok': True, 'unavailable': False}),
    "sess_overlap": ({
        'key': "session", 'label_fa': "زمان‌بندی مناسب (سشن)",
        'points': 1, 'max_points': 1,
        'ok': True, 'unavailable': False}),
    "sess_thin": ({
        'key': "session", 'label_fa': "زمان‌بندی مناسب (سشن)",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': False}),
    "str_buy_aligned": ({
        'key': "strength", 'label_fa': "هم‌جهتی جریان قدرت ارزها",
        'points': 1, 'max_points': 1,
        'ok': True, 'unavailable': False}),
    "str_buy_contra": ({
        'key': "strength", 'label_fa': "هم‌جهتی جریان قدرت ارزها",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': False}),
    "str_empty": ({
        'key': "strength", 'label_fa': "هم‌جهتی جریان قدرت ارزها",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': True}),
    "str_missing": ({
        'key': "strength", 'label_fa': "هم‌جهتی جریان قدرت ارزها",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': True}),
    "str_sell_aligned": ({
        'key': "strength", 'label_fa': "هم‌جهتی جریان قدرت ارزها",
        'points': 1, 'max_points': 1,
        'ok': True, 'unavailable': False}),
    "trend_medium": ({
        'key': "trend", 'label_fa': "هم‌راستایی روند ۴ ساعته و ۱ ساعته",
        'points': 1, 'max_points': 2,
        'ok': True, 'unavailable': False}),
    "trend_strong": ({
        'key': "trend", 'label_fa': "هم‌راستایی روند ۴ ساعته و ۱ ساعته",
        'points': 2, 'max_points': 2,
        'ok': True, 'unavailable': False}),
    "tv_match_buy": ({
        'key': "tv", 'label_fa': "هم‌جهتی با تریدینگ‌ویو",
        'points': 1, 'max_points': 1,
        'ok': True, 'unavailable': False}),
    "tv_match_sell": ({
        'key': "tv", 'label_fa': "هم‌جهتی با تریدینگ‌ویو",
        'points': 1, 'max_points': 1,
        'ok': True, 'unavailable': False}),
    "tv_neutral": ({
        'key': "tv", 'label_fa': "هم‌جهتی با تریدینگ‌ویو",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': False}),
    "tv_opposite": ({
        'key': "tv", 'label_fa': "هم‌جهتی با تریدینگ‌ویو",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': False}),
    "tv_unavailable": ({
        'key': "tv", 'label_fa': "هم‌جهتی با تریدینگ‌ویو",
        'points': 0, 'max_points': 1,
        'ok': False, 'unavailable': True}),
}

EV_TEXTS = {
    "fund_clean": "هیچ رویداد پراثری تا ۶ ساعت آینده روی EUR/USD نیست — مسیر برای معامله باز است",
    "fund_cal_off": "موتور فاندامنتال خاموش است — نمی‌توانیم تاییدش کنیم، پس امتیازی نمی‌گیرد",
    "fund_cal_failed": "تقویم در دسترس نبود — نمی‌توانیم تاییدش کنیم، پس امتیازی نمی‌گیرد",
    "level_buy_far": "حمایت 1.14 در فاصلهٔ ۹.۰ برابر ATR — قیمت از سطح فاصله گرفته (دیر رسیده‌ایم)",
    "mom_buy_confirm": "RSI=38 و رو به بالا ↗️ — پولبک در حال برگشت است (بهترین نقطهٔ ورود)",
    "mom_sell_confirm": "RSI=62 و رو به پایین ↘️ — اصلاح رو به بالا در روند نزولی (بهترین نقطهٔ ورود فروش)",
    "str_buy_contra": "رتبهٔ EUR: ۳ از ۴ | رتبهٔ USD: ۱ از ۴ → جریان قدرت خلاف جهت است (برای EUR قوی‌تر از USD باید برعکس می‌بود)",
    "str_empty": "رتبه‌بندی قدرت ارزها محاسبه نشد",
    "news_contra": "⚠️ اخبار خلاف جهت است (-۱ رأی): «Euro falls as ECB signals rate cuts»",
    "tv_opposite": "⚠️ تریدینگ‌ویو «SELL» می‌گوید — خلاف جهت تحلیل ما",
    "sess_overlap": "سشن لندن + نیویورک (هم‌پوشانی — بهترین نقدینگی ⭐) — بیشترین نقدینگی و کمترین اسپرد هفته",
    "sess_closed": "شنبه — بازار فارکس بسته است 🔒",
}

NO_SETUP_TEXTS = {
    "trend_none": "جهت روند نامشخص است",
    "h1_disagree": "تایم‌فریم ۱ ساعته با ۴ ساعته هم‌جهت نیست",
    "range_no_veto": "بازار بی‌روند است (ADX=14 زیر 20)",
    "bullish_rsi_high": "روند صعودی است ولی RSI=55 در منطقهٔ پولبک نیست (برای ستاپ خرید باید زیر ۴۵ باشد) — یعنی یا دیر رسیده‌ایم یا اصلاح هنوز تمام نشده",
    "bearish_rsi_low": "روند نزولی است ولی RSI=40 در منطقهٔ اصلاح رو به بالا نیست (برای ستاپ فروش باید بالای ۵۵ باشد)",
}


# ══════════════════════════════════════════════════════════════
def test_golden_battery() -> None:
    """باتری کامل == فایل طلایی (بایت‌به‌بایت، همهٔ گروه‌ها)."""
    golden_path = HERE / "golden" / "judge_rules_golden.json"
    A(golden_path.exists(),
      "فایل طلایی وجود ندارد — اول python tests/golden/gen_judge_golden.py")
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    if BAT != golden:
        diff = [k for k in sorted(set(BAT) | set(golden))
                if BAT.get(k) != golden.get(k)]
        raise AssertionError(f"باتری با طلایی فرق دارد — گروه‌های: {diff}")
    A(True, "باتری طلاییِ کامل (وتو/شاهد/داوری/ریسک) بایت‌به‌بایت مطابقت کرد")


def test_veto_single() -> None:
    """هر ۷ وتو به‌تنهایی — کلید + عنوان + متن فارسی دقیق."""
    singles = BAT["veto_single"]
    A(sorted(singles) == sorted(VETO_TITLES),
      "دقیقاً ۷ وتوی ثبت‌شده در باتری حاضر است")
    for key in ("DATA", "WEEKEND", "TF_CONFLICT", "RANGE", "EVENT",
                "VOL_SPIKE", "BREAKING_NEWS"):
        j = singles[key]
        A([v["key"] for v in j["vetoes"]] == [key],
          f"وتوی {key} باید تنها شلیک شود: {[v['key'] for v in j['vetoes']]}")
        v = j["vetoes"][0]
        A(v["title_fa"] == VETO_TITLES[key],
          f"عنوان وتوی {key} عوض شد: {v['title_fa']!r}")
        A(v["detail_fa"] == VETO_DETAILS[key],
          f"متن وتوی {key} عوض شد: {v['detail_fa']!r}")
        A(j["reject_reason"] == "VETO" and j["signal"] is None,
          f"{key}: reject=VETO و بدون سیگنال")
        A(j["status_fa"] == "🚫 وتو شد", f"{key}: status_fa باید «🚫 وتو شد» باشد")


def test_veto_order() -> None:
    """چند وتوی هم‌زمان — ترتیب ارزیابیِ امروز (DATA→…→BREAKING_NEWS)."""
    A([v["key"] for v in BAT["veto_multi"]["all_except_data"]["vetoes"]]
      == ["WEEKEND", "TF_CONFLICT", "RANGE", "EVENT", "VOL_SPIKE", "BREAKING_NEWS"],
      "ترتیب وتوها (همه جز DATA) عوض شد")
    A([v["key"] for v in BAT["veto_multi"]["with_data"]["vetoes"]]
      == ["DATA", "WEEKEND", "EVENT", "VOL_SPIKE", "BREAKING_NEWS"],
      "ترتیب وتوها (با DATA — TF_CONFLICT/RANGE به‌خاطر گارد verdict رد می‌شوند) عوض شد")


def test_veto_toggles_and_clean() -> None:
    """کلیدهای *موجود* config فقط همان دروازه را برمی‌دارند — نه بیشتر."""
    j = BAT["veto_toggles"]["weekend_off_saturday"]
    A(j["vetoes"] == [] and j["signal"] is not None,
      "veto.weekend:false → شنبه بدون وتو سیگنال می‌دهد (رفتار فعلی)")
    A((j["score"], j["max_score"]) == (10, 11),
      "سیگنالِ شنبه فقط امتیاز سشن را از دست می‌دهد (۱۰/۱۱)")
    A(j["evidences"][-1]["key"] == "session"
      and j["evidences"][-1]["points"] == 0
      and j["evidences"][-1]["detail_fa"] == "شنبه — بازار فارکس بسته است 🔒",
      "شاهد سشن در بازار بسته: ۰ امتیاز با دلیل صادقانه")
    j2 = BAT["veto_toggles"]["range_off_low_adx"]
    A(j2["vetoes"] == [] and j2["signal"] is not None,
      "veto.range_market:false → ADX پایین وتو نمی‌آورد (رفتار فعلی)")
    A(j2["evidences"][0]["points"] == 1,
      "روند با ADX متوسط → شاهد trend یک امتیاز (نه دو)")
    A(BAT["veto_clean"] == [], "ستاپ سالم → هیچ وتویی فعال نیست")


def test_evidence_branches() -> None:
    """هر ۳۸ شاخهٔ ۸ شاهد — کلید/برچسب/امتیاز/ok/unavailable + متن‌های کلیدی."""
    ev = BAT["evidence_branches"]
    A(sorted(ev) == sorted(EV_PINS),
      f"همهٔ شاخه‌های شاهد حاضرند ({len(ev)} از {len(EV_PINS)})")
    for name, pin in EV_PINS.items():
        got = ev[name]
        A(got["key"] == pin["key"] and got["label_fa"] == pin["label_fa"],
          f"شاهد «{name}»: کلید/برچسب عوض شد ({got['key']!r}/{got['label_fa']!r})")
        A((got["points"], got["max_points"], got["ok"], got["unavailable"])
          == (pin["points"], pin["max_points"], pin["ok"], pin["unavailable"]),
          f"شاهد «{name}»: امتیاز/حالت عوض شد "
          f"({got['points']}/{got['max_points']} ok={got['ok']} un={got['unavailable']})")
    for name, text in EV_TEXTS.items():
        A(ev[name]["detail_fa"] == text,
          f"متن شاهد «{name}» عوض شد: {ev[name]['detail_fa']!r}")
    A(ev["news_contra"]["detail_fa"].startswith("⚠️"),
      "خبرِ خلاف جهت با ⚠️ شروع می‌شود (سرچشمهٔ warnings داوری)")
    A(ev["tv_opposite"]["detail_fa"].startswith("⚠️"),
      "TV خلاف جهت با ⚠️ شروع می‌شود")
    A(ev["level_sell_close"]["label_fa"].endswith("(مقاومت)"),
      "شاهد سطح در SELL = مقاومت")
    A(ev["level_buy_close"]["label_fa"].endswith("(حمایت)"),
      "شاهد سطح در BUY = حمایت")


def test_judge_full_paths() -> None:
    """BUY و SELL طلایی — ۱۱/۱۱ با سیگنال کامل."""
    b = BAT["judge_full"]["buy"]
    A((b["score"], b["max_score"]) == (11, 11), "BUY طلایی باید ۱۱/۱۱ باشد")
    A([e["key"] for e in b["evidences"]]
      == ["trend", "level", "fundamental", "momentum",
          "strength", "news", "tv", "session"],
      "ترتیب ۸ شاهد = فهرست ثابتِ امروز (trend…session)")
    A(all(e["ok"] for e in b["evidences"]), "در BUY طلایی هر ۸ شاهد امتیاز گرفتند")
    A(b["reject_reason"] == "" and b["status_fa"] == "✅ سیگنال صادر شد",
      "BUY طلایی: بدون رد، status_fa درست")
    A(b["warnings"] == [], "BUY طلایی هیچ هشداری ندارد")
    s = b["signal"]
    A(s["direction"] == "BUY" and s["stars"] == 5 and s["rr"] == 2.0,
      "سیگنال BUY: جهت/ستاره/RR")
    A(s["sl"] < s["entry"] < s["tp"], "BUY: SL < ورود < TP")
    A(s["sl_capped"] is False, "BUY طلایی: SL به سقف نخورده")
    A(s["sid"] == "EURUSD-BUY-20260923140000-1.149", "شناسهٔ ژورنال قطعی (symbol-direction-زمان-قیمت)")
    A(s["session_fa"] == "لندن + نیویورک (هم‌پوشانی — بهترین نقدینگی ⭐)", "برچسب سشنِ هم‌پوشانی")
    A(s["journal"]["kind"] == "signal" and s["journal"]["sent"] is True
      and s["journal"]["score"] == 11,
      "رکورد ژورنالِ سیگنال سالم است")
    sl = BAT["judge_full"]["sell"]
    A(sl["direction"] == "SELL" and (sl["score"], sl["max_score"]) == (11, 11),
      "SELL طلایی ۱۱/۱۱")
    ss = sl["signal"]
    A(ss["tp"] < ss["entry"] < ss["sl"], "SELL: TP < ورود < SL")
    A([e for e in sl["evidences"] if e["key"] == "level"][0]["label_fa"]
      == "واکنش به سطح کلیدی (مقاومت)", "برچسب شاهد سطح در SELL")


def test_low_score() -> None:
    """امتیاز زیر آستانه → LOW_SCORE + هشدارهای ⚠️ جمع‌شده از شاهدها."""
    j = BAT["judge_low_score"]["low_score"]
    A(j["reject_reason"] == "LOW_SCORE" and j["signal"] is None,
      "LOW_SCORE بدون سیگنال")
    A((j["score"], j["max_score"]) == (5, 11), "سناریوی ضعیف: ۵ از ۱۱")
    A(j["reject_detail"] == "امتیاز ۵ از ۱۱ — زیر آستانهٔ ۷ است، پس سیگنال صادر نمی‌شود",
      "متن LOW_SCORE (ارقام فارسی) عوض شد")
    A(j["status_fa"] == "⏳ امتیاز ناکافی", "status_fa برای امتیاز ناکافی")
    A(j["warnings"] == [
        "اخبار خلاف جهت است (-۱ رأی): «Euro falls as ECB signals rate cuts»",
        "تریدینگ‌ویو «SELL» می‌گوید — خلاف جهت تحلیل ما",
    ],
      "⚠️های شاهدها (خبر + TV) به warnings داوری منتقل می‌شوند")


def test_no_setup() -> None:
    """هر ۵ دلیلِ «ستاپی شکل نگرفته» — متن صادقانهٔ دقیق."""
    ns = BAT["judge_no_setup"]
    A(sorted(ns) == sorted(NO_SETUP_TEXTS), "هر ۵ شاخهٔ NO_SETUP در باتری هست")
    for name, text in NO_SETUP_TEXTS.items():
        j = ns[name]
        A(j["reject_reason"] == "NO_SETUP" and j["signal"] is None,
          f"NO_SETUP/{name}: بدون سیگنال")
        A(j["reject_detail"] == text,
          f"NO_SETUP/{name}: متن عوض شد: {j['reject_detail']!r}")


def test_capped() -> None:
    """سقف سیگنال در چرخه — بهترین می‌ماند، بقیه CAPPED (با متن دقیق)."""
    js = BAT["judge_capped"]
    A([j["symbol"] for j in js] == ["EURUSD", "GBPUSD", "USDJPY"],
      "خروجی judge_all با ترتیب امتیازِ نزولی مرتب نشده — ورودی همان ورودی است")
    A(js[0]["signal"] is not None and js[0]["reject_reason"] == "",
      "بهترین (۱۱/۱۱) سیگنال خود را نگه می‌دارد")
    for j in js[1:]:
        A(j["reject_reason"] == "CAPPED" and j["signal"] is None,
          f"{j['symbol']}: CAPPED و سیگنال حذف شد")
        A(j["status_fa"] == "🔢 به سقف تعداد سیگنال رسید", f"{j['symbol']}: status_fa")
    A(js[1]["reject_detail"] == "امتیاز ۱۰ از ۱۱ کافی بود، ولی سقف ۱ سیگنال در هر چرخه پر شده — بهترین‌ها اولویت دارند", "متن CAPPED عوض شد")
    A((js[1]["score"], js[2]["score"]) == (10, 8),
      "امتیازهای CAPPED حفظ می‌شود (۱۰ و ۸)")


def test_judge_all_mixed() -> None:
    """judge_all — ۴ نماد در ۴ سرنوشت متفاوت، در یک فراخوانی."""
    fates = {j["symbol"]: (j["reject_reason"] or "SIGNAL")
             for j in BAT["judge_all_mixed"]}
    A(fates == {"EURUSD": "SIGNAL", "GBPUSD": "VETO",
                "USDJPY": "NO_SETUP", "AUDUSD": "LOW_SCORE"},
      f"۴ سرنوشتِ مورد انتظار در judge_all: {fates}")
    eur = BAT["judge_all_mixed"][0]
    A(eur["score"] == 10
      and [e for e in eur["evidences"] if e["key"] == "news"][0]["unavailable"],
      "بدون موتور خبر: سیگنال ۱۰/۱۱ با شاهدِ صادقانهٔ unavailable")
    gbp = BAT["judge_all_mixed"][1]
    A([v["key"] for v in gbp["vetoes"]] == ["RANGE"],
      "ADX=14 در judge_all هم وتوی RANGE می‌گیرد")


def test_risk_math() -> None:
    """ریاضی SL/TP — ۶ حالت: سطح/بدون سطح/سقف/کف/ATR صفر."""
    rc = gen.judge_config(gen.CFG)["risk"]
    atr = 0.0010
    buf = float(rc["level_buffer_atr"]) * atr
    rm = BAT["risk_math"]
    b = rm["buy_level"]
    A(abs(b["sl"] - (1.1486 - buf)) < 1e-12,
      "BUY با حمایت: SL = حمایت − بافر×ATR")
    A(abs(b["risk"] - (1.1490 - b["sl"])) < 1e-12
      and abs(b["tp"] - (1.1490 + b["risk"] * float(rc["reward_risk"]))) < 1e-12,
      "risk = |ورود−SL| و TP = ورود + risk×RR")
    A(b["capped"] is False, "BUY معمولی: بدون سقف")
    s = rm["sell_level"]
    A(s["sl"] > 1.1490 > s["tp"] and s["capped"] is False,
      "SELL: SL بالای ورود، TP زیر آن")
    c = rm["buy_far_capped"]
    A(c["capped"] is True
      and abs((1.1490 - c["sl"]) - float(rc["max_sl_atr"]) * atr) < 1e-12,
      "سطحِ دور → SL به سقف max_sl_atr×ATR محدود می‌شود")
    f = rm["buy_tight_floor"]
    A(f["capped"] is False
      and abs((1.1490 - f["sl"]) - float(rc["min_sl_atr"]) * atr) < 1e-12,
      "سطحِ خیلی نزدیک → SL به کف min_sl_atr×ATR می‌رسد")
    n = rm["buy_no_level"]
    A(n["capped"] is False
      and abs((1.1490 - n["sl"]) - float(rc["sl_atr_multiplier"]) * atr) < 1e-12,
      "بدون سطح → SL = sl_atr_multiplier×ATR")
    z = rm["atr_zero_guard"]
    A(z["risk"] > 0 and z["sl"] != 1.1490 and z["capped"] is False,
      "ATR=0 → گارد: ریسک صفر نمی‌شود (SL≠ورود)")


# ══════════════════════════════════════════════════════════════
def main() -> int:
    tests = [test_golden_battery, test_veto_single, test_veto_order,
             test_veto_toggles_and_clean, test_evidence_branches,
             test_judge_full_paths, test_low_score, test_no_setup,
             test_capped, test_judge_all_mixed, test_risk_math]
    fails = []
    for t in tests:
        try:
            t()
        except AssertionError as e:
            fails.append(f"{t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            fails.append(f"{t.__name__}: خطای غیرمنتظره {type(e).__name__}: {e}")
    if fails:
        print("❌ JUDGE-RULES TESTS FAILED")
        for f in fails:
            print("  •", f)
        return 1
    print(f"✅ JUDGE-RULES TESTS OK — {COUNT} بررسی پاس؛ میخ‌های رفتاری داور "
          f"(۷ وتو + ۳۸ شاخهٔ شاهد + داوری کامل + CAPPED + ریاضی ریسک) "
          f"+ طلاییِ باتری سناریوها سبز‌اند")
    return 0


if __name__ == "__main__":
    sys.exit(main())
