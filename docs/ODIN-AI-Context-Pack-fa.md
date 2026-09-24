# 🎒 بستهٔ زمینهٔ ODIN — برای هوش مصنوعی و توسعه‌دهندهٔ تازه‌وارد

> **نسخهٔ سند:** v0.25.0 (۲۰۲۶-۰۹-۲۳) — پایان مهاجرت معماری پلاگین
> **مخاطب:** هر AI یا انسانی که قرار است روی این ریپو کار کند. این فایل
> «حداقل زمینهٔ لازم برای کارِ امن» است — جزئیات طراحی در
> [`plugin-architecture-fa.md`](plugin-architecture-fa.md) و تاریخچهٔ کامل در
> [`../CHANGELOG.md`](../CHANGELOG.md).
> **وعدهٔ این سند:** اگر آن را رعایت کنید، خروجی کار شما با تست‌های موجود
> سبز می‌ماند و هیچ رفتار کاربری بی‌صدا عوض نمی‌شود.

---

## ۱) پروژه در یک پاراگراف

**ODIN Assistant** یک دستیار تحلیل فارکس/طلا است (نه ربات معامله‌گر — هرگز
معاملهٔ خودکار نمی‌کند): هر ۱۵ دقیقه ۷ نماد را از Yahoo می‌گیرد، تحلیل
تکنیکال H4/H1/M15 می‌کند، تقویم اقتصادی + اخبار جهت‌دار + تاییدیهٔ
TradingView را می‌سنجد و یک **داور امتیازدهی** (۷ دروازهٔ وتو + ۸ شاهد،
حداکثر ۱۱ امتیاز، آستانهٔ صدور ۷) سیگنالِ ورود/SL/TP صادر می‌کند؛ با
ژورنال append-only و کارنامهٔ دقت (حلقهٔ صداقت). **دو موتور هم‌رفتار** دارد:
پایتون (دسکتاپِ منجمد از v0.21 + **اوراکل parity**) و JS (اپ اندروید —
پلتفرم فعال). خروجی قابل‌توزیع: **فقط APK**.

## ۲) قوانین طلایی اجرا (تخطی = بازگشت)

1. **Behavior Preservation:** هیچ تغییر کاربرنمایی بدون تصمیم صریح مالک.
   متن‌های فارسی، ترتیب‌ها، آستانه‌ها و لاگ‌ها با طلایی‌ها پین شده‌اند.
2. **اول میخ، بعد چکش:** قبل از هر ریفکتور، تست طلاییِ رفتارِ موجود را
   بنویس و سبز کن (کامیت جدا)؛ بعد سوییچ کن — میخ‌ها باید **بدون تغییر**
   سبز بمانند. ریفکتور بدون میخ = رد.
3. **Preview + تأیید مالک:** هر فاز/تغییر بزرگ اول Preview مکتوب می‌خواهد
   (scope/طرح/تصمیم‌ها/راستی‌آزمایی/خارج‌از-scope) و فقط با تأیید اجرا می‌شود.
4. **نگهبان یا سبزِ معنادار است یا قرمزِ پرسروصدا** — هرگز بی‌صدا رد نشو.
   شکست تست = همان فاز rollback و گزارش می‌شود.
5. **سه برنچ همیشه روی یک کامیت:** `ANDROID` (پیش‌فرض) + `android` + `main`.
   بعد از هر فاز push هر سه (نگهبان `branch-sync.yml` واگرایی را سخت fail می‌کند).
6. **یک کامیت = یک تغییر revert-پذیر** با پیام فارسیِ پرجزئیات به سبک
   تاریخچه (author: `ODIN Dev <odin-dev@users.noreply.github.com>`).
7. **ریلیز فقط با تگ `v*`** و فقط از ورک‌فلو اندروید (ویندوز منجمد).
   نسخه تا پایان فاز ۸ روی ۰.۲۴.۰ ماند — الان v0.25.0 منتشر شده.
8. **منطق جدید در Java/Kotlin ممنوع** (مرز نیتیو دست‌نخورده) · لایسنس و
   secretها خارج از سیستم پلاگین‌اند (مسیر امنیتی جدا) · UI ویندوز منجمد.

## ۳) نقشهٔ ریپو

```
src/core/        🔌 هستهٔ پلاگین پایتون (فقط stdlib): contracts(۱۵ قرارداد) ·
                 manifest · registry · resolver(Kahn+آبشار+حلقه پرسروصدا) ·
                 lifecycle(۷ وضعیت+قرنطینه) · config_bridge(۴ سطح اولویت،
                 dot-path) · bus(همگام ایزوله) · pipeline(۱۱ مرحله+stop)
src/plugins/     🔌 ۳۰ پلاگین پایتون — adapter نازک (فقط delegation با import
                 تنبل) + مانیفست اعلانی. build_default_registry() نقطهٔ ورود.
src/engine.py    چرخهٔ تحلیل روی PipelineRunner (run_cycle) + BotLoop +
                 بریفینگ/هشدار رویداد/کارنامه. BUS ماژول‌محور. _Caps = دسترسی
                 قابلیت‌محور با نمونه‌های تنبل (خراب→throw، خاموش→None).
src/{data,analysis,fundamental,judge,journal,report,notify,fa,config,app_paths}
                 ماژول‌های فیچر — منطق واقعی اینجاست، پلاگین‌ها فقط مرزند.
src/ui/ panel.py 🖥️ منجمد — ولی theme.py منبع حقیقت توکن‌های رنگ اندروید است
                 (smoke_theme_parity ۲۱۱ بررسی). حذف = شکست نگهبان.
android/app/src/main/assets/www/
  index.html     ترتیب بارگذاری: core.js ← plugins.js ← ۲۰ ماژول (پین‌شده)
  js/core.js     🔌 آینهٔ ES5 هستهٔ پایتون (O.core) — smoke_core پاریتیِ
                 فهرست‌ها را *از سورس پایتون* استخراج و مقایسه می‌کند
  js/plugins.js  🔌 ۲۶ پلاگین JS (O.buildDefaultRegistry/O.makeCaps/O.BUS)
  js/app.js      cycleCore/svcTick/svcStart/boot — مصرف caps + ۹ رویداد bus
  js/data.js     runPipeline (واکشی داده→تحلیل→فاندامنتال) — مصرف caps
  js/judge.js    داور JS: O.veto*/O.ev*/VETO_RULES/EVIDENCE_RULES + تزریق
                 اختیاری قواعد در judgeSymbol/judgeAll
tests/           ۶ سوئیت واحد/طلایی پایتون + golden/ + manual/(۱۶) +
                 js/(۱۱ اسموک + run_parity + ۲ میخ رفتاری + golden/)
installer/       release_notes.py (یادداشت ریلیز از CHANGELOG) +
                 stamp_version.py (version_info.txt ← APP_VERSION)
docs/            این بسته + plugin-architecture-fa.md (سند مادر مهاجرت) +
                 راهنماهای کاربری + project-report-fa.md (ممیزی v0.24.0)
```

## ۴) معماری دو موتور (خلاصهٔ عملی)

- **قراردادها** ساختاری‌اند: پایتون `Protocol` با `@runtime_checkable`؛
  JS فهرست متدها + `O.core.validateProvider`. شناسهٔ قرارداد
  `name.domain@major` و فقط از `CONTRACTS` (قرارداد جدید = تصمیم معماری).
- **مانیفست:** `{id, version, provides, requires, config, platforms, stage,
  priority, optional}` — config به کلیدهای *موجود* config.yaml/O.CONFIG
  bind می‌شود (section/enabled_key — dot-path مثل `judge.veto.weekend` مجاز).
  ترتیب اولویت فعال/غیرفعال: `plugins.<id>.enabled` ← کلید فیچری ←
  پیش‌فرض مانیفست ← true.
- **ترتیب قطعی:** providers و resolve با `(priority, order[, id])`.
  ترتیب وتوها (DATA→…→BREAKING_NEWS) و شاهدها (trend→…→session) با
  priority پین شده — عوض کردنش = تغییر رفتار = ممنوع بدون میخ.
- **Failure Isolation:** پلاگین خراب → قرنطینه (FAILED) + رویداد
  `plugin.failed` + لاگ `[!]` فارسی + unavailable صادقانه (امتیاز ۰، نه
  دادهٔ جعلی). گذار نامعتبر حالت = باگ چارچوب → پرسروصدا.
- **رویدادها:** ۱۲ رویداد استاندارد پایتون؛ JS ۹ تای معادل دارد
  (report.rendered/telegram.sent/vetoes.computed معادل JS ندارند — نگاشت در
  کامنت cycleCore). bus همگام است و listenerها هرگز خروجی را عوض نمی‌کنند.
- **JS محدودیت‌ها:** همهٔ `www/js` باید **ES5 خالص** بماند (var/function —
  نگهبانش در smoke_core و test_cycle_switch). هیچ semver نقل‌قولی‌شده در
  www/ جز APP_VERSION مجاز نیست (نگهبانِ بررسی ۷ smoke_theme_parity —
  به‌همین دلیل CORE_VERSION فقط در پایتون است و نسخهٔ مانیفست‌های JS از
  اجزا ساخته می‌شود: `var V = [1,0,0].join('.')`).

## ۵) نقشهٔ تست — «چه چیزی چه چیزی را پین کرده»

| سوئیت | چه پین می‌کند | اجازهٔ تغییر |
|---|---|---|
| `tests/golden/run_cycle_golden.json` + `test_engine_switch.py`(۴۷) | چرخهٔ کامل mock پایتون: result+۱۷ لاگ+تلگرام | ❌ میخ — فقط با دلیل موجه و بازضبط عمدی |
| `tests/test_judge_rules.py`(۱۸۸)+`golden/judge_rules_golden.json` | ۷ وتو+۳۸ شاخهٔ شاهد+داوری+ریسک (پایتون) | ❌ میخ |
| `tests/test_pipeline_switch.py`(۱۰) | توالی ۳۳ رویداد/early-exit stop | ❌ میخ |
| `tests/test_core.py`(۸۷) / `js/smoke_core.js`(۱۳۶) | واحدِ هسته (دو زبان، فهرست‌ها از سورس هم) | ➕ افزودنی مجاز؛ موجودی‌ها نه |
| `tests/test_plugins.py`(۱۷۲) | adapter==direct + registry parity + فاز۷ | در سوییچ‌ها به‌روز می‌شود (سابقه دارد) |
| `js/golden/cycle_core_golden.json` + `test_cycle_switch.js`(۵۴) | ۸ سناریوی چرخهٔ سرویس JS (لاگ/اعلان/storage بایت‌به‌بایت) | ❌ میخ |
| `js/golden/judge_rules_js_golden.json` + `test_judge_switch.js`(۱۷۹) | ۵۸ سناریوی داور JS (== طلایی پایتون) | ❌ میخ |
| `js/run_parity.js`(۲۵ زنده) | موتور JS == اوراکل پایتون روی دادهٔ زنده | ❌ اوراکل — فقط افزودنی |
| `js/smoke_*` (۱۱) | UI/لایسنس/تم(۲۱۱)/چیدمان/آیکون/هشدار/نمودار/اشتراک/خوش‌آمد/پلاگین‌ها | ساختاری‌ها با مستندسازی |
| `js/smoke_service.js` (زنده) | رصد پس‌زمینهٔ end-to-end | ❌ |
| `main.py --selftest` · `tests/check_config.py` · `tests/manual/*`(۱۶) | خودآزمایی/کانفیگ/سناریوهای دستی | موردی |

اجرای کامل محلی (ترتیب پیشنهادی):
`python main.py --selftest && python tests/check_config.py && for t in tests/test_*.py; do python $t; done`
سپس `for s in tests/js/smoke_*.js tests/js/test_*.js; do node $s; done`
و در آخر زنده‌ها: `python tests/js/gen_fixtures.py && node tests/js/run_parity.js && node tests/js/smoke_service.js`

## ۶) جریان نسخه و ریلیز

- **منبع حقیقت نسخه:** `src/app_paths.py::APP_VERSION` — از آن مشتق می‌شود:
  `android/app/build.gradle` (versionName + versionCode=major*10000+minor*100+patch)،
  `installer/version_info.txt` (با `python installer/stamp_version.py` بازتولید
  شود — دستی ویرایش نکنید)، یادداشت ریلیز (`installer/release_notes.py` از
  CHANGELOG).
- **تگ `v*`** → `build-android.yml`: گارد reachability از سه برنچ → بیلد →
  امضا با Secrets → **ساخت Release + آپلود APK**. بدون امضا = fail سخت
  (چیزی منتشر نمی‌شود). `build-release.yml` روی تگ فقط تست است.
- **CHANGELOG قرارداد دارد:** هر بخش `## [x.y.z] - YYYY-MM-DD` بین نشانگرهای
  `RELEASE-NOTES-START/END` — همان متنِ ریلیز است.

## ۷) CI و برنچ‌ها

- push به `ANDROID` → تست کامل (پایتون + همهٔ JS آفلاین) + بیلد APK.
- push به `main`/`android` → فقط `branch-sync.yml` (ارزان؛ واگرایی = fail).
- CI هرگز parity زنده/smoke_service را اجرا نمی‌کند (اینترنت لازم دارند) —
  آن‌ها وظیفهٔ اجرای محلیِ قبل از push‌اند.

## ۸) بدهی‌های ثبت‌شده (کارهای آینده — گم‌شان نکنید)

1. **۶c — pipeline ناهمگام JS:** `O.core.createPipeline` همگام است؛ چرخهٔ JS
   promise-based. آینهٔ async (runStages ناهمگام) برای سوییچ cycleCore به
   مراحل نام‌دار لازم است — با Preview و میخ‌های خودش.
2. **نمایش وضعیت پلاگین‌ها در UI اندروید:** `registry.status()` آماده است؛
   در فاز ۷ به بعد از مهاجرت موکول شد (صفحهٔ تنظیمات گاردِ طولِ متن دارد —
   smoke_layout).
3. **توکن‌های `--onb-bg/--onb-glass`:** حاضر ولی بلااستفاده (میراث بازگردانی
   v0.24.0 — قرارداد پاریتی theme.py نگهشان داشته).
4. **ممیزی نظری `\w` در الگوهای کلیدواژهٔ اخبار** (appreciat\w+ و…): در
   دادهٔ واقعی واگرایی مشاهده نشد (parity سبز) — اگر روزی عنوانی با دنبالهٔ
   چسبیدهٔ غیرASCII دیدید، آنجا را ببینید.

## ۹) دام‌های شناخته‌شده (درس‌هایی که ارزان به دست نیامدند)

- **`\w` در JS فقط ASCII است** ولی در پایتون با `re.UNICODE` یونیکد — هر
  regex «یکسان» در دو زبان را با نویسهٔ غیرلاتین تست کنید (باگ dedupeٔ
  v0.25.0). برای هم‌ارزی: `\p{L}\p{N}_` با پرچم `u` (و try/catch برای
  WebView قدیمی).
- **`bool()` پایتون ≠ `Boolean()` JS** برای فهرست/dict خالی — در مرزهای
  config از `O.core.pyBool` استفاده شده.
- **floatها در طلایی‌ها امن‌اند** (IEEE754 قطعی بین پلتفرم‌ها) — به شرط
  ساختگی بودن ورودی و تزریق زمان (FakeDate/now_override).
- **ZWNJ (نیم‌فاصله) در متن‌های فارسی:** هنگام کپی پین‌های متنی، بایت‌ها را
  از سورس/طلایی استخراج کنید، نه تایپ دستی (ابزار تزریق جدول در تاریخچهٔ
  فاز ۴ هست).
- **`plugins:` override فقط دسترس‌پذیری پلاگین را کنترل می‌کند** — رفتار
  مصرف‌کننده با کلید فیچری است (برای خاموش‌کردن کامل یک فیچر، همان کلید
  فیچری را خاموش کنید). مستند در config.yaml.
- **journal/anti-spam عمداً binding ندارد** (config=None): ضداسپم و سند
  صداقت نباید با یک کلید بمیرند.

## ۱۰) وضعیت در یک نگاه (v0.25.0)

مهاجرت معماری **کامل** است: فازهای ۱·۲·۳a·۳b·۴·۵·۶·۶b·۷·۸ انجام شده‌اند
(تاریخچهٔ دقیق با کامیت‌ها: جدول پیشرفتِ `plugin-architecture-fa.md`).
هر دو موتور ۱۰۰٪ پلاگین‌محورند؛ افزودن قابلیت جدید = یک adapter با مانیفست
در `src/plugins/` و `js/plugins.js` + تست طلایی — **بدون دست‌زدن به هسته**.
