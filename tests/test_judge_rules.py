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
    # v0.29.1: آستانهٔ وتوی RANGE از ۲۰ به ۳۰ رفت (بازپخشِ تاریخی: بازهٔ
    # ADX<30 در هر دو نیمهٔ زمانی زیرِ خطِ پایه بود). متن، آستانه را embed
    # می‌کند پس این پین هم باید هم‌عدد بماند.
    "RANGE": "ADX=14 زیر آستانهٔ 30 است — استراتژی روندی در بازار رنج کار نمی‌کند",
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
    "range_no_veto": "بازار بی‌روند است (ADX=14 زیر 30)",
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
    # S3 (بازضبطِ مستند): پینِ toggle سرِ جایش است (vetoes==[]) ولی این
    # سناریو دیگر سیگنال نمی‌دهد — ADX=14 زیر آستانهٔ trend_pullback (۳۰ از v0.29.1)
    # است، پس دروازهٔ توافق صادقانه رد می‌کند. موضوعِ پینِ toggle، «وتو
    # برداشته شده» است نه «سیگنال صادر شده».
    A(j2["vetoes"] == [],
      "veto.range_market:false → ADX پایین وتو نمی‌آورد (رفتار toggle حفظ شد)")
    A(j2["reject_reason"] == "NO_STRATEGY" and j2["score"] == 10,
      "S3: روندِ بی‌ADX → دروازهٔ توافق رد می‌کند (امتیاز محاسبه شده باقی است)")
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
    # S3 (بازضبطِ مستند): a3 از rsi=55 به 38 رفت تا در منطقهٔ پولبکِ
    # trend_pullback بماند و «سه سیگنال آماده، سقف ۱» preserved بماند —
    # momentum یک امتیاز گرفت: ۸→۹. ترتیبِ cap (۱۱>۱۰>۹) همان است.
    A((js[1]["score"], js[2]["score"]) == (10, 9),
      "امتیازهای CAPPED حفظ می‌شود (۱۰ و ۹ — S3: a3 داخل منطقهٔ tp)")


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
#  S3 (v0.26) — دروازهٔ توافق استراتژی‌ها
# ══════════════════════════════════════════════════════════════
def test_strategy_gate() -> None:
    """پین‌های خوانای دروازهٔ توافق — گروه strategy_gate طلایی."""
    g = BAT["strategy_gate"]

    j = g["no_agreement"]
    A(j["reject_reason"] == "NO_STRATEGY" and j["signal"] is None,
      "امتیاز ≥ ۷ ولی صفر استراتژیِ هم‌جهت → NO_STRATEGY (دروازه مستقل از امتیاز)")
    A(j["score"] >= 7, "سناریوی no_agreement باید امتیازش کافی باشد (وگرنه پین بی‌معناست)")
    A(j["status_fa"] == "🎯 استراتژی موافق نیست", "status_fa دروازهٔ استراتژی")
    A(j["reject_detail"].startswith("توافقِ استراتژی‌ها کافی نیست"),
      "متن دقیقِ ردِ دروازه")
    A([v["direction"] for v in j["strategies"]] == ["NONE", "NONE", "NONE"],
      "هر سه استراتژی صادقانه NONE دادند و ثبت شدند")

    j = g["carry_only"]
    A(j["reject_reason"] == "NO_STRATEGY",
      "تنها-carry: n_total=1 ≥ min_agree ولی n_prop=0 → رد (D1=R2 پین)")
    A("(پیشنهاددهنده: ۰)" in j["reject_detail"], "جزئیات باید شمارِ پیشنهاددهنده را بگوید")
    cv = [v for v in j["strategies"] if v["key"] == "carry"][0]
    A(cv["direction"] == "BUY" and cv["proposes"] is False,
      "carry هم‌جهت است ولی proposes=False — فقط توافق")

    j = g["min_agree_2"]
    A(j["reject_reason"] == "NO_STRATEGY" and "حداقل لازم: ۲" in j["reject_detail"],
      "min_agree=2 از ctx.strategies_cfg خوانده می‌شود (پینِ config)")

    j = g["fail_closed_empty"]
    A(j["reject_reason"] == "NO_STRATEGY" and j["strategies"] == [],
      "فهرست خالی (همه خاموش) → fail-closed بدون verdict (D3)")
    A(j["reject_detail"].startswith("هیچ استراتژیِ فعالی در دسترس نیست"),
      "متن صادقانهٔ fail-closed")

    j = g["broken_rule_isolated"]
    A(j["signal"] is not None and len(j["strategies"]) == 2,
      "قاعدهٔ خطاداده مانعِ سیگنال نیست (Failure Isolation) — placeholder + tp")
    A(j["strategies"][0]["name_fa"] == "استراتژیِ خطاداده"
      and j["strategies"][0]["direction"] == "NONE",
      "placeholder صادقانه برای استراتژیِ خطاداده")
    A(j["signal"]["journal"]["strategies"] == ["trend_pullback"],
      "ژورنال فقط کلیدِ موافق‌ها را نگه می‌دارد")

    j = g["broken_rule_only"]
    A(j["reject_reason"] == "NO_STRATEGY"
      and j["strategies"][0]["name_fa"] == "استراتژیِ خطاداده",
      "فقط قاعدهٔ خطاداده → هیچ نظرِ واقعی نیست → ردِ صادقانه")

    j = g["opt_out_min_agree_0"]
    A(j["signal"] is not None, "min_agree=0 → دروازه خاموش (opt-out صریحِ کاربر)")
    A(len(j["strategies"]) == 3
      and j["signal"]["journal"]["strategies"] == [],
      "opt-out هم صادقانه ارزیابی/نمایش می‌دهد؛ ژورنالِ موافق‌ها خالی")

    j = g["pass_full"]
    A(j["signal"] is not None, "مسیرِ سالم: tp توافق می‌کند → سیگنال")
    A(j["signal"]["journal"]["strategies"] == ["trend_pullback"],
      "کلیدِ موافق در ژورنال")
    tv = [v for v in j["strategies"] if v["key"] == "trend_pullback"][0]
    A(tv["direction"] == "BUY" and tv["proposes"] is True
      and 0.0 < tv["strength"] <= 1.0 and tv["name_fa"] == "روند + پولبک",
      "verdict استراتژیِ موافق کامل ثبت می‌شود (نام/جهت/قدرت/proposes)")


def test_gate_order_and_legacy() -> None:
    """ترتیبِ رد (LOW_SCORE مقدم) + مسیرِ strategy_rules=None == رفتار v0.25."""
    # LOW_SCORE قبل از دروازه بررسی می‌شود → استراتژی‌ها اصلاً ارزیابی
    # نمی‌شوند (j.strategies خالی) — کمترین جابه‌جایی در آمارِ کاربر
    low = BAT["judge_low_score"]["low_score"]
    A(low["reject_reason"] == "LOW_SCORE" and low["strategies"] == [],
      "LOW_SCORE مقدم بر NO_STRATEGY است و استراتژی‌ها را ارزیابی نمی‌کند")
    for name in ("veto_single", "veto_multi"):
        for j in BAT[name].values() if isinstance(BAT[name], dict) else BAT[name]:
            A(j["strategies"] == [], f"{name}: ردِ پیش‌دروازه‌ای strategies خالی")
    for j in BAT["judge_no_setup"].values():
        A(j["strategies"] == [], "NO_SETUP: ردِ پیش‌دروازه‌ای strategies خالی")

    # مسیر None (ارثی/v0.25): دروازه خاموش — همان mock سناریوی no_agreement
    # باید سیگنال بدهد (بدون دروازه) و strategies خالی بماند
    md = gen.make_md(last_dir="bull")
    a = gen.make_analysis(rsi=25.0)
    ctx = gen.make_ctx(cal=gen.clean_cal(), news=gen.good_news())
    j_legacy = gen.judge_symbol(a, {}, md, ctx)                       # strategy_rules=None
    j_gated = gen.judge_symbol(a, {}, md, ctx,
                               strategy_rules=gen.DEFAULT_STRATEGY_RULES)
    A(j_legacy.signal is not None and j_legacy.strategies == [],
      "None = بایت‌به‌بایت رفتار v0.25: سیگنال صادر، بدون دروازه")
    A(j_gated.signal is None and j_gated.reject_reason == "NO_STRATEGY",
      "تزریق قواعد = دروازه فعال (همان ورودی، سرنوشتِ متفاوتِ مستند)")
    A((j_legacy.score, j_legacy.max_score) == (j_gated.score, j_gated.max_score)
      and [e.points for e in j_legacy.evidences]
      == [e.points for e in j_gated.evidences],
      "دروازه جدول امتیاز را عوض نمی‌کند — فقط لایهٔ رد است")


# ══════════════════════════════════════════════════════════════
def test_adx_thresholds_v0291() -> None:
    """پینِ صریحِ آستانه‌های ADX (v0.29.1).

    چرا لازم است: تغییرِ ``adx_min_trend`` ۲۰→۳۰ و ``adx_strong`` ۲۵→۴۰ بر
    پایهٔ بازپخشِ تاریخی بود (بازهٔ ADX<30 در *هر دو* نیمهٔ زمانی زیرِ خطِ
    پایه؛ بازهٔ ≥40 در هر دو بالای آن — tools/backtest_v029.py). ولی باتریِ
    طلایی هم‌زمان adx پیش‌فرضش را ۳۲→۴۲ برد تا سناریوهای «کامل» ۱۱/۱۱
    بمانند، پس **طلایی‌ها خودِ آستانه را پین نمی‌کنند**. بدونِ این تست،
    برگرداندنِ آستانه به ۲۰ فقط دو خطِ متنی عوض می‌کرد و بی‌صدا رد می‌شد.

    آستانه‌ها از *config واقعی* خوانده می‌شوند نه عددِ سخت‌کدشده، پس اگر روزی
    دوباره تنظیم شدند این تست خودش به‌روز می‌ماند و فقط «مرز بودن» و
    «هم‌عددیِ دو منبع» را پین می‌کند.
    """
    from src.config import load_config
    # ⚠️ ROOT در این فایل HERE.parents[1] است (پدرِ ریپو، برای sys.path)؛
    # config.yaml در خودِ ریپو است → HERE.parent.
    c = load_config(str(HERE.parent / "config.yaml"))
    lo = float(c["analysis"]["adx_min_trend"])
    hi = float(c["analysis"]["adx_strong"])
    A(hi > lo,
      f"adx_strong ({hi}) باید از adx_min_trend ({lo}) بزرگ‌تر باشد — وگرنه "
      f"هر سیگنالی که از وتو رد شود ADX≥{lo}>{hi} دارد و ev_trend به همه "
      f"۲ امتیاز می‌دهد (نقصِ «امتیازِ مجانی» که v0.29.1 رفعش کرد)")

    # ── مرزِ وتوی RANGE ───────────────────────────────────────
    j_lo = gen.judge_symbol(gen.make_analysis(adx=lo - 0.01), {}, None,
                            gen.make_ctx())
    j_hi = gen.judge_symbol(gen.make_analysis(adx=lo + 0.01), {}, None,
                            gen.make_ctx())
    A(bool(j_lo.vetoes) and j_lo.vetoes[0].key == "RANGE",
      f"ADX={lo - 0.01} باید وتوی RANGE بگیرد (کف={lo})")
    A(not any(v.key == "RANGE" for v in j_hi.vetoes),
      f"ADX={lo + 0.01} نباید وتوی RANGE بگیرد")
    A(f"{lo:.0f}" in j_lo.vetoes[0].detail_fa,
      f"متنِ وتو باید آستانهٔ *واقعی* ({lo:.0f}) را نشان دهد نه عددِ کهنه: "
      f"{j_lo.vetoes[0].detail_fa}")

    # ── مرزِ امتیازِ ev_trend ─────────────────────────────────
    p_lo = gen.ev_trend(gen.make_analysis(adx=hi - 0.01), gen.make_ctx(), "BUY")
    p_hi = gen.ev_trend(gen.make_analysis(adx=hi + 0.01), gen.make_ctx(), "BUY")
    A(p_lo.points == 1 and p_hi.points == 2,
      f"ev_trend باید در adx_strong={hi} از ۱ به ۲ برود "
      f"(پایین={p_lo.points}، بالا={p_hi.points})")
    A(p_lo.points != p_hi.points,
      "دو سطحِ ev_trend باید واقعاً متمایز باشند — اگر یکی باشند این مدرک "
      "اطلاعاتی حمل نمی‌کند")

    # ── هم‌عددیِ داور و استراتژی ──────────────────────────────
    st = float(((c.get("strategies") or {}).get("trend_pullback") or {})
               .get("adx_min", -1))
    A(st == lo,
      f"strategies.trend_pullback.adx_min ({st}) باید هم‌عدد با "
      f"analysis.adx_min_trend ({lo}) باشد — عمدی است تا داور و استراتژی دو "
      f"تعریفِ متفاوت از «روندِ معتبر» نداشته باشند")


def main() -> int:
    tests = [test_golden_battery, test_veto_single, test_veto_order,
             test_veto_toggles_and_clean, test_evidence_branches,
             test_judge_full_paths, test_low_score, test_no_setup,
             test_capped, test_judge_all_mixed, test_risk_math,
             test_strategy_gate, test_gate_order_and_legacy,
             test_adx_thresholds_v0291]
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
          f"(۷ وتو + ۳۸ شاخهٔ شاهد + داوری کامل + CAPPED + ریاضی ریسک "
          f"+ دروازهٔ توافق استراتژی‌ها S3 + مرزهای ADX v0.29.1) "
          f"+ طلاییِ باتری سناریوها سبز‌اند")
    return 0


if __name__ == "__main__":
    sys.exit(main())
