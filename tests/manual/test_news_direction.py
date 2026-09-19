# -*- coding: utf-8 -*-
"""تست رگرسیون: مواردی که در نسخه اول اشتباه بودند."""
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from src.fundamental import news as nw

CASES = [
    # (متن، جهت مورد انتظار، توضیح)
    ("Japanese Yen slides as markets look beyond BoJ rate hike", {"JPY": -1},
     "باگ #۲: حرکت قیمت (slides) باید بر rate hike غلبه کند"),
    ("BREAKING: Dollar surges as Fed signals hawkish rate hike", {"USD": 1},
     "فوری + هاوکیش → دلار قوی"),
    ("Yen set for worst week since Oct 2025 as BoJ's hike seen as not aggressive enough",
     {"JPY": -1}, "بدترین هفته → ین ضعیف"),
    ("USDJPY surges as the BOJ hike disappoints", {"USD": 1, "JPY": -1},
     "باگ #۳: جفت چسبیده + قاعدهٔ جهت جفت‌ارز"),
    ("EURUSD falls to two-week low on dovish ECB tone", {"EUR": -1, "USD": 1},
     "جفت چسبیده + against/جهت جفت"),
    ("Gold rallies as war fears drive safe-haven demand", {"XAU": 1},
     "باگ #۴: فقط طلا جهت بگیرد، نه USD/JPY/CHF"),
    ("investingLive Americas market news wrap: Bonds slump again", {},
     "باگ #۶: مقالهٔ wrap نباید جهت صادر کند"),
    ("How have interest rate expectations changed after this week's events?", {},
     "خبر بدون جهت مشخص"),
    ("Canadian dollar weakens against major currencies in the week ending Sept 19",
     {"CAD": -1}, "weakens → کانادا ضعیف"),
    ("Oil slides after China asks Iran to limit Houthi attacks on Saudi oil fields",
     {"OIL": -1}, "نفت پایین + ریسک‌گریزی"),
    ("Porsche could face another 4,000 job cuts, Handelsblatt reports", {},
     "باگ مرتبط: خبر بدون ارز پوشش‌داده‌شده"),
    ("Sterling rises against the dollar as UK CPI beats expectations", {"GBP": 1, "USD": -1},
     "قاعدهٔ against: پوند ↑ دلار ↓"),
    ("Aussie and kiwi fall as risk-off mood grips markets", {"AUD": -1, "NZD": -1},
     "ریسک‌گریزی → ارزهای پرریسک ضعیف"),
    ("Dollar steadies as traders await Fed decision", {},
     "بدون جهت (steadies/await)"),
]

print("=" * 92)
print("رگرسیون جهت‌دهی اخبار")
print("=" * 92)
fails = 0
for text, expected, why in CASES:
    score, direction, kws, brk, rnd = nw.score_text(text)
    # مقایسه: جهت‌های مورد انتظار باید درست باشند؛ جهت‌های اضافه = سرریز
    ok_dir = all(direction.get(c) == v for c, v in expected.items())
    extra = {c: v for c, v in direction.items() if c not in expected}
    # سرریز مجاز: وقتی انتظار {} است، هیچ جهتی نباید باشد
    if not expected and direction:
        ok_dir = False
    status = "✅" if ok_dir and not extra else ("⚠️" if ok_dir else "❌")
    if status == "❌":
        fails += 1
    print(f"{status} score={score} brk={int(brk)} rnd={int(rnd)} dir={direction}")
    print(f"     متن : {text[:78]}")
    print(f"     انتظار: {expected or '{}'} | چرا: {why}")
    if extra:
        print(f"     ⚠️ سرریز: {extra}")
    if kws:
        print(f"     کلیدواژه: {'، '.join(kws)}")
    print()

print("=" * 92)
print(f"نتیجه: {len(CASES) - fails}/{len(CASES)} درست  ({fails} خطای جهت)")

print()
print("=" * 92)
print("توزیع امتیازها روی دادهٔ زنده (بررسی باگ #۱: تورم امتیاز)")
print("=" * 92)
snap = nw.fetch_news({}, on_log=lambda m: print("   ", m))
dist = {}
for it in snap.items:
    dist[it.score] = dist.get(it.score, 0) + 1
print("توزیع امتیاز:", dict(sorted(dist.items(), reverse=True)))
print(f"کل: {len(snap.items)} خبر | با جهت: {len(snap.directional)} | جمع‌بندی: {sum(1 for i in snap.items if i.roundup)}")
for it in sorted(snap.items, key=lambda x: -x.score)[:10]:
    tag = "🚨" if it.breaking else ("📚" if it.roundup else "  ")
    print(f" {tag}[{it.score}] {it.source[:12]:12s} :: {it.title[:64]}")
    print(f"       → {it.direction_fa() or 'بدون جهت'} | kw: {'، '.join(it.keywords) or '—'}")
