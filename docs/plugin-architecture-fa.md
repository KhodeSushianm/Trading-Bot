# 🏗️ معماری پلاگین ODIN — Contract-Based + Plugin-Driven

> **وضعیت:** فاز ۱ اجرا شد (هستهٔ پایتون `src/core/` — اسکلت، بدون اتصال به engine)
> **نسخهٔ پایهٔ سند:** v0.24.0 — کامیت `07b17d4`
> **اصل حاکم:** Behavior Preservation + Incremental Refactoring
> **مخاطب:** توسعه‌دهنده (انسان) و هوش مصنوعی — همراه با `ODIN-AI-Context-Pack-fa.md`

---

## ۰) چرا این سند؟

پروژه امروز یک **Modular Monolith** است: ماژول‌ها تمیز جدا شده‌اند
(`src/{data,analysis,fundamental,judge,journal,notify,report}` و همزاد JS آن)،
ولی **هسته به همه‌چیز وابسته است** — `src/engine.py` در سطح ماژول ۱۸ import
مستقیم از همهٔ فیچرها دارد. هدفِ این مهاجرت:

- **Core کوچک، پایدار و مستقل از قابلیت‌ها** — هسته فقط *قراردادها* را بشناسد،
  نه RSI، نه Yahoo، نه News، نه TradingView.
- **قابلیت‌ها به Plugin تبدیل شوند** — با Manifest، Lifecycle، وابستگی‌های
  صریح، Enable/Disable و Failure Isolation.
- **بدون بازنویسی** — منطق فعلی دست‌نخورده می‌ماند؛ فقط مرزهای وابستگی
  کنترل‌شده اصلاح می‌شوند و هر قدم با تست‌های موجود (parity + smoke +
  selftest) اثبات می‌شود.

---

## ۱) معماری فعلی (As-Is) — خلاصهٔ فنی

### ۱.۱ دو پیاده‌سازی، یک رفتار

| لایه | پایتون (اوراکل parity + دسکتاپ منجمد) | JS (اندروید — پلتفرم فعال) |
|---|---|---|
| ارکستراتور | `src/engine.py` — `run_cycle` / `run_briefing` / `check_event_alerts` / `BotLoop` | `js/data.js::runPipeline` + `js/app.js::cycleCore` / `svcTick` |
| مصرف‌کننده | `main.py` (CLI) · `panel.py` (Qt — منجمد) | `index.html` (۲۱ اسکریپت با ترتیب دستی) · `OdinService` |
| الگوی ماژول | پکیج‌های `src/*` با import صریح | namespace سراسری `ODIN` (هر فایل توابعش را به `O.` می‌افزاید) |
| پیکربندی | `config.yaml` + `config.local.yaml` + `src/config.py` | `js/config.js::O.CONFIG` (همان کلیدها) + تنظیمات گوشی |

### ۱.۲ ترتیب دقیق چرخهٔ فعلی (باید مو‌به‌مو حفظ شود)

```
run_cycle / cycleCore:
  collect_market   (yahoo/auto → analyze_symbol → currency_strength → TV → calendar → news)
  journal_pre      resolve_open_signals + compute_stats
                   ⚠️ عمداً *قبل* از بررسی موفقیت داده — اگر منبع قطع باشد هم
                      سیگنال‌های باز باید منقضی/بسته شوند
  [early-exit]     هیچ analysis نیست → errors=max(errors,1) و بازگشت
  compute_vetoes   وتوهای نماد-محور تقویم
  judge            judge_all → signals + render_judge_summary
  render           render_report (با journal_line)
  dispatch_signals should_send_signal (ضداسپم) → telegram → journal_signal
  price_alerts     check_alerts → telegram
  chart_cache      chart_<SYM>.json (دسکتاپ) / chart.<SYM> (اندروید)
  dashboard        ranking / upcoming / symbols_summary / fundamental_report
  archive_notify   _archive(report) → telegram گزارش کامل
```

`BotLoop._run` (دسکتاپ) و `svcTick` (اندروید) زمان‌بندی‌اند:
cycle / event_alerts / briefing / journal(nightly+weekly).

### ۱.۳ سنگ‌بنایی که از قبل هست

1. **قرارداد `DataSource`** (`src/data/base.py`): ABC با
   `connect/disconnect/fetch` + دیتاکلاس `MarketData` + کارخانهٔ
   `get_source(cfg)` — یعنی الگوی Contract-Based در لایهٔ داده *همین حالا*
   وجود دارد؛ فقط تعمیم نیافته.
2. **داور شبه‌پلاگین است:** `collect_vetoes` = ۷ دروازهٔ وتو
   (DATA, WEEKEND, TF_CONFLICT, RANGE, EVENT, VOL_SPIKE, BREAKING_NEWS) و
   `j.evidences` = فهرست ۸ تابع `ev_*` (trend, level, fundamental, momentum,
   strength, news, tradingview, session). تبدیلشان به Rule ثبت‌شده تغییر
   منطق نمی‌خواهد — فقط تغییر مرز.
3. **Failure Isolation قاعدهٔ موجود است:** توابع JS «هرگز استثنا پرتاب
   نمی‌کنند»؛ پایتون try/except با `unavailable` + امتیاز صادقانهٔ ۰. ما
   این را **codify** می‌کنیم، نه اختراع.
4. **پرچم‌های فعال/غیرفعال فیچرها در config موجودند:**
   `fundamental.enabled` · `news.enabled` · `judge.enabled` ·
   `journal.enabled` · `tradingview.enabled` · `briefing.enabled`.

### ۱.۴ مشکلات (انگیزهٔ مهاجرت)

- هسته همهٔ فیچرها را مستقیم می‌شناسد (۱۸ import در engine.py)
- به‌جز data هیچ interface صریحی نیست — قراردادها «امضای تابعِ سخت‌کدشده»اند
- ترتیب بارگذاری JS شکننده و وابستگی‌ها ضمنی‌اند؛ lifecycle رسمی وجود ندارد
- افزودن فیچر جدید = دست‌زدن به هسته در **دو زبان**

---

## ۲) معماری هدف (To-Be)

```
┌─────────────────────────────────────────────────────────────┐
│                        CORE (هسته)                           │
│  ① Contracts      — interfaceهای نسخه‌دار (shape-only)        │
│  ② Manifest       — شناسنامهٔ پلاگین                          │
│  ③ Registry       — ثبت، جست‌وجو با قرارداد، enable/disable   │
│  ④ Resolver       — توپولوژیک؛ حلقه=خطای پرسروصدا؛ مفقود=    │
│                     غیرفعال‌شدن با لاگ فارسی (نه کرش)          │
│  ⑤ Lifecycle      — ماشین حالت + قرنطینهٔ خطا                 │
│  ⑥ Config Bridge  — مانیفست → کلیدهای *موجود* config          │
│  ⑦ Event Bus +    — pub/sub همگام ایزوله + مراحل قطعی         │
│     Pipeline Runner                                          │
└─────────────────────────────────────────────────────────────┘
        ▲ فقط قراردادها را می‌شناسد — نه RSI، نه Yahoo، نه News
        │
┌───────┴─────────────────────────────────────────────────────┐
│                    PLUGINS (built-in adapters)               │
│ data-yahoo · data-twelvedata · data-auto · data-tradingview  │
│ analysis-technical · analysis-strength · session             │
│ fundamental-calendar · fundamental-news                      │
│ judge-core · judge-veto-×۷ · judge-evidence-×۸ · judge-risk  │
│ journal · notify-telegram · alerts-price · report-*          │
└─────────────────────────────────────────────────────────────┘
```

### ۲.۱ تصمیم‌های کلیدی طراحی

| # | تصمیم | دلیل |
|---|---|---|
| ۱ | **Built-in، نه dynamic-load (فعلاً)** | پلاگین‌ها adapterهای نازک دور کد موجودِ همین ریپو هستند. بارگذاری پلاگین خارجی = بازنویسی + ریسک امنیتی. معماری طوری است که بعداً *بدون شکستن قراردادها* اضافه‌شدنی است |
| ۲ | **Contracts ساختاری (structural)** | پایتون: `typing.Protocol` با `@runtime_checkable`؛ JS: shape مستند + اعتبارسنج. ماژول‌های فعلی «ذاتاً» قرارداد را ارضا می‌کنند — بدون import اجباری از core (استقلال هسته) |
| ۳ | **بدون وابستگی جدید** | core پایتون فقط stdlib؛ core JS فقط vanilla (بدون ES modules — WebView فعلی اسکریپت ساده است) |
| ۴ | **Bus همگام و fire-and-forget** | listenerها هرگز خروجی pipeline را عوض نمی‌کنند → قطعیت خروجی → parity با اوراکل حفظ می‌شود |
| ۵ | **Failure Isolation = codification** | خطای پلاگین → لاگ `[!]` با قالب فعلی + `unavailable` + امتیاز صادقانهٔ ۰ + ادامه. هرگز دادهٔ جعلی نه |
| ۶ | **مرز نیتیو دست‌نخورده** | هیچ منطقی به Java/Kotlin منتقل نمی‌شود (OdinBridge/OdinService همان‌ها می‌مانند) |
| ۷ | **لایسنس بیرون از سیستم پلاگین** | گیت دسترسی (access control) فیچر نیست؛ `license.py`/`license.js` و مسیر امنیتی T1–T3/D6 دست‌نخورده |
| ۸ | **کلیدهای config عوض نمی‌شوند** | مانیفست به کلیدهای موجود bind می‌شود؛ بخش `plugins:` فقط override اختیاری با پیش‌فرض خالی است |

### ۲.۲ جدول قراردادها (نسخه ۱ — `src/core/contracts.py`)

| Contract ID | shape (از کد فعلی) | پلاگین‌های فعلی |
|---|---|---|
| `odin.data.market@1` | `connect()/disconnect()/fetch(sym_cfg)→MarketData\|None` (= ABC موجود) | data-yahoo, data-twelvedata, data-auto |
| `odin.data.tv@1` | `fetch_tv_snapshot(symbols, tf, timeout)→{symbol: TVSnapshot}` | data-tradingview |
| `odin.analysis.technical@1` | `analyze_symbol(sym_cfg, md, acfg)→SymbolAnalysis` | analysis-technical |
| `odin.analysis.strength@1` | `currency_strength(datasets, lookback_h1)→[(ccy, score)]` | analysis-strength |
| `odin.session@1` | `market_status(now)→MarketStatus` | session |
| `odin.fundamental.calendar@1` | `fetch_calendar / upcoming_events / veto_for_symbol` | fundamental-calendar |
| `odin.fundamental.news@1` | `fetch_news(cfg, on_log, max_age_hours)→NewsSnapshot` | fundamental-news |
| `odin.judge.engine@1` | `judge_config(cfg)` + `judge_all(analyses, datasets, ctx)→[Judgment]` | judge-core |
| `odin.judge.veto@1` | `rule(a, sym_cfg, md, ctx)→Veto\|None` — ۷ قاعدهٔ ثبت‌شده | veto-{data,weekend,tf-conflict,range,event,vol-spike,breaking-news} |
| `odin.judge.evidence@1` | `rule(a, ctx, direction)→Evidence` — ۸ قاعده با ترتیب ثابت فعلی | ev-{trend,level,fundamental,momentum,strength,news,tv,session} |
| `odin.judge.risk@1` | `compute_levels(direction, entry, atr, support, resistance, rcfg)→(sl, tp, rr, capped)` | judge-risk |
| `odin.journal@1` | `open(path)` + `resolve_open_signals(...)` + `compute_stats(entries, now)` | journal |
| `odin.notify@1` | `send(cfg, text, on_log, label)→(ok, msg)` | notify-telegram |
| `odin.alerts.price@1` | `check_alerts(analyses, now)→[dict]` | alerts-price |
| `odin.report@1` | `render(kind, payload)` — kind: signal, judge_summary, calendar, news, briefing, stats, nightly, console, ... | report-* |

**نکتهٔ `ev_session`:** امروز فقط `(ctx)` می‌گیرد؛ adapter فاز ۴ همان
shape یکدست `rule(a, ctx, direction)` را با نادیده‌گرفتن ورودی‌های اضافه
فراهم می‌کند — بدون تغییر رفتار.

**نسخه‌گذاری قراردادها:** شناسه `name@major`. تغییر سازگار (متد اختیاری
جدید) بدون bump؛ تغییر ناسازگار → `@2` با نگهداری همزمان تا مهاجرت کامل.
قرارداد جدید فقط با تصمیم معماری (ثبت در `CONTRACTS`) — پلاگین‌ها نمی‌توانند
سرخود قرارداد بسازند (`InvalidManifestError`).

### ۲.۳ مانیفست (`src/core/manifest.py`) — یکسان در دو زبان

```jsonc
{
  "id": "fundamental-calendar",          // یکتا، kebab-case
  "version": "1.0.0",                    // semver ساده
  "provides": ["odin.fundamental.calendar@1"],
  "requires": ["odin.session@1"],        // فقط وابستگی *سخت*؛ نرم‌ها (مثل
                                         // judge با cal_snap=None) عمداً اینجا نمی‌آیند
  "config": { "section": "fundamental",  // → کلید *موجود* config.yaml
              "enabled_key": "enabled",
              "default": true },
  "platforms": ["desktop", "android"],
  "stage": "collect_fundamental",        // مرحلهٔ pipeline (فهرست §۲.۷)
  "priority": 100,                       // کوچک‌تر = زودتر؛ tie-break = ترتیب ثبت
  "optional": true                       // نبودش → unavailable، نه کرش
}
```

### ۲.۴ رجیستری (`src/core/registry.py`)

- `register(manifest, factory)` — id تکراری → `DuplicatePluginError` (پرسروصدا)
- `providers(contract)` — **چند فراهم‌کننده برای یک قرارداد مشروع است**
  (yahoo/twelvedata/auto هر سه `odin.data.market@1`اند)؛ ترتیب قطعی
  `(priority, order)` و انتخاب نهایی config-driven است (مثل `data_source` امروز)
- `get(contract)` — بالاترین اولویت یا `None` (هرگز استثنا)
- `enable/disable` + `status()` — پایهٔ کلید فعال/غیرفعال (فاز ۷: نمایش در UI)

### ۲.۵ حل‌کنندهٔ وابستگی (`src/core/resolver.py`)

الگوریتم: **Kahn** روی گراف `requires → provides` با صف مرتب
`(priority, order, id)` → خروجی کاملاً قطعی.

| وضعیت | رفتار |
|---|---|
| وابستگی مفقود (یا فراهم‌کننده خاموش) | پلاگین `disabled_reason` **فارسی** می‌گیرد و از زنجیره خارج می‌شود — آبشاری (غیرفعال‌شدن A، وابستهٔ B را هم می‌اندازد). بدون استثنا، بدون کرش |
| حلقهٔ وابستگی | `CircularDependencyError` با مسیر کامل حلقه — باگ طراحی است، باید پرسروصدا باشد (درس نگهبان‌های v0.19.1/v0.20.0) |
| سالم | وضعیت `RESOLVED` و ترتیب توپولوژیک |

### ۲.۶ Lifecycle (`src/core/lifecycle.py`)

```
REGISTERED → RESOLVED → INITIALIZED → STARTED → STOPPED → DISPOSED
هر وضعیت (جز DISPOSED) → FAILED (قرنطینه)
```

- هوک‌های اختیاری روی نمونهٔ پلاگین: `initialize/start/stop/dispose/run(ctx)`
- **هر خطای پلاگین → قرنطینه:** `PluginFailure{plugin_id, phase, error, at}` +
  وضعیت FAILED + رویداد `plugin.failed`. بقیهٔ پلاگین‌ها سالم می‌مانند.
- **خطای گذار نامعتبر = باگ چارچوب** → `InvalidTransitionError` پرسروصدا
  (قرنطینه فقط برای خطای *پلاگین* است، نه *چهارچوب*).
- نمونه‌ها **lazy** ساخته می‌شوند (در initialize) — مثل امروز که منابع
  داده در زمان نیاز ساخته می‌شوند.

### ۲.۷ Config Bridge (`src/core/config_bridge.py`)

ترتیب اولویت (بالا = برنده):

```
۱) cfg["plugins"][id]["enabled"]      ← override صریح (اختیاری؛ امروز خالی)
۲) cfg[section][enabled_key]          ← کلید فیچری موجود (مثل امروز)
۳) manifest.config["default"]         ← پیش‌فرض مانیفست
۴) True                               ← مانیفست بدون اتصال config
```

هیچ کلید جدیدی در فازهای ۱–۶ به `config.yaml`/`O.CONFIG` اضافه نمی‌شود →
«فعال/غیرفعال» دقیقاً معنای امروز را دارد (Behavior Preservation).

### ۲.۸ Event Bus (`src/core/bus.py`)

- همگام، روی همان نخ چرخه (بدون threading جدید)؛ `emit` هرگز استثنا نمی‌دهد
- ترتیب اجرا = ترتیب ثبت (قطعی، تست‌پذیر)
- رویدادهای استاندارد (`Events`):
  `cycle.start · market.collected · journal.resolved · fundamental.collected ·
  vetoes.computed · judge.done · signal.created · signal.sent · alerts.fired ·
  report.rendered · telegram.sent · cycle.end · news.breaking · briefing.due ·
  journal.due · plugin.registered · plugin.failed · plugin.disabled ·
  stage.start · stage.done`

### ۲.۹ Pipeline Runner (`src/core/pipeline.py`)

مراحل چرخه (ترتیب = §۱.۲ فعلی، فقط نام‌گذاری شده):

```
collect_market → journal_pre → [early-exit] → collect_fundamental →
compute_vetoes → judge → render → dispatch_signals → price_alerts →
chart_cache → dashboard → archive_notify
```

⚠️ `collect_fundamental` عمداً **بعد** از early-exit است: اگر منبع داده قطع
باشد (هیچ analysis)، تقویم/خبر هرگز واکشی نمی‌شوند — دقیقاً رفتار امروز.

- `StageResult{ok, value, unavailable, error, stop}` — `stop=True` همان
  early-exit امروز است (هیچ analysis → خروج)
- دو منبع هندلر: صریح (`runner.add(stage, fn, priority)`) و پلاگین‌های
  STARTED همان مرحله با هوک `run(ctx)` — هر دو با ترتیب قطعی
- خطای مرحله → `unavailable` + رویداد `plugin.failed` + **ادامه** (همان
  try/exceptهای فعلی، یکجا و قابل تست)
- مراحل زمان‌بند (خارج از چرخه): `event_alerts · briefing · journal_report`

### ۲.۱۰ آینهٔ JS (طرح فاز ۵ — `js/core.js`)

- یک فایل vanilla با همان نام‌ها/معناها: `O.core = { register, get, providers,
  resolveOrder, enable, disable, status, on, emit, runStages, STAGES }`
- مانیفست = object ساده با همان فیلدها؛ قراردادها = مستند + اعتبارسنج سبک
  (بدون Protocol — JS نوع ندارد؛ parity از راه تست‌ها تضمین می‌شود)
- `index.html`: `core.js` **اول** بارگذاری می‌شود؛ بقیهٔ فایل‌ها فعلاً
  دست‌نخورده (فاز ۶ هر ماژول را با یک بلوک ثبتِ پلاگین تکمیل می‌کند)
- معنای Failure Isolation یکی: پلاگین خراب → `unavailable` + لاگ + ادامه

---

## ۳) فازهای مهاجرت و تضمین‌های حفظ رفتار

| # | فاز | راستی‌آزمایی |
|---|---|---|
| **۱** ✅ | سند طراحی + `src/core/` (اسکلت) + `tests/test_core.py` + قلاب CI | تست جدید (۸۲ بررسی) + selftest + check_config + compileall + smokeها + CI سبز |
| ۲ | adapterهای پایتون (`src/plugins/`) + ثبت در registry | **تست طلایی:** خروجی adapter == فراخوانی مستقیم (روی fixtures ضبط‌شده) + همهٔ تست‌های فاز ۱ |
| ۳ | سوییچ `engine.py` به registry/pipeline/bus — امضاهای عمومی (`run_cycle`, `BotLoop`, ...) ۱۰۰٪ ثابت | ضبط خروجی کامل چرخه قبل/بعد (گزارش، judgments، signals، vetoes) + مقایسهٔ طلایی + selftest + manual tests |
| ۴ | ۷ وتو + ۸ شاهد + risk → rule-plugin (ترتیب/آستانه‌ها/متن‌های فارسی دقیقاً فعلی) | `gen_fixtures.py` + `run_parity.js` کامل (۲۴ تست) + test_judge + selftest |
| ۵ | `js/core.js` + `smoke_core.js` | اسموک جدید + هر ۱۰ اسموک موجود سبز (بدون تغییر در فایل‌های فعلی) |
| ۶ | پلاگین‌سازی JS + سوییچ `runPipeline/cycleCore/svcTick` | `run_parity.js` (۲۴ تست) + ۱۰+۱ اسموک + `smoke_service.js` |
| ۷ | Enable/Disable یکپارچه زیر مانیفست (همان کلیدها؛ بدون UI جدید ویندوز — منجمد) + سخت‌گیری Failure Isolation | smoke_alerts/smoke_service + سناریوهای خاموش‌کردن هر فیچر == رفتار امروزِ `enabled: false` |
| ۸ | به‌روزرسانی مقالهٔ معماری + AI Pack + CHANGELOG + **v0.25.0** + push هر ۳ برنچ + tag + Release فقط APK | CI کامل سبز + APK منتشرشده |

**تضمین‌های سراسری:**
1. هیچ ماژول موجودی در فازهای اولیه **جابه‌جا نمی‌شود** — import pathهای
   `gen_fixtures.py`/`run_parity.js`/`panel.py` پایدار می‌مانند.
2. هر فاز = یک کامیت مستقل revert-پذیر با پیام فارسی.
3. هر سرخیِ تست → همان فاز rollback و گزارش می‌شود (بی‌صدا رد نمی‌شویم).
4. `config.yaml` کلید جدید نمی‌گیرد (تا فاز ۷ هم فقط بخش override اختیاری).
5. شمارهٔ نسخه تا فاز ۸ روی 0.24.0 می‌ماند (APK تغییری نمی‌کند).

**استراتژی انتشار (تصمیم مالک):** هیچ Release در طول مهاجرت منتشر نمی‌شود؛
فقط یک ریلیز **v0.25.0** در پایان فاز ۸ (commit/push هر سه برنچ بعد از هر
فاز انجام می‌شود؛ tag نمی‌زنیم).

**خارج از scope (صریح):** dynamic-load پلاگین خارجی · هر تغییر در لایسنس/
secretها (مسیر جداگانهٔ D6) · هر منطق جدید در Java/Kotlin · UI جدید ویندوز
(منجمد) · تغییر کلیدهای config · تغییر رفتار داوری/رندر/ارسال.

---

## ۴) راهنمای عملی (بعد از اتمام مهاجرت)

**افزودن یک قابلیت جدید بدون دست‌زدن به هسته:**
1. اگر شکلِ قابلیت جدید است → قرارداد جدید فقط با تصمیم معماری در
   `contracts.py` + `CONTRACTS` ثبت شود (و آینهٔ JS آن).
2. پلاگین: یک فایل adapter با مانیفست (provides/requires/stage/priority/
   config-binding) — در پایتون `src/plugins/` و در JS بلوک ثبت انتهای ماژول.
3. تست طلایی + (اگر محاسباتی است) فیکسچر parity جدید.
4. هسته هیچ تغییری نمی‌کند؛ engine/cycleCore هم هیچ.

**غیرفعال‌کردن یک قابلیت:** همان کلید فعلی config (مثلاً `news.enabled:
false`) → config-bridge پلاگین را خاموش می‌کند → resolver وابسته‌ها را
آبشاری می‌اندازد → مصرف‌کننده `unavailable` می‌بیند و صادقانه ۰ امتیاز
می‌دهد. (دقیقاً رفتار امروز، ولی با گراف وابستگی صریح.)

---

## ۵) ثبت پیشرفت فازها

| فاز | تاریخ | کامیت | نتیجه |
|---|---|---|---|
| ۱ — هستهٔ پایتون | ۲۰۲۶-۰۹-۲۳ | `8074d44` + `2b63bff` | ✅ ۱۱ فایل جدید + ۱ step در CI؛ ۸۲ بررسی تست core سبز؛ صفر تغییر در کد موجود. اصلاحیه: افزودن مرحلهٔ `collect_fundamental` بعد از early-exit |
| ۲ — adapterهای پایتون | ۲۰۲۶-۰۹-۲۳ | `b6f0099` | ✅ `src/plugins/` (۱۴ پلاگین، ۱۳ قرارداد با فراهم‌کننده) + ۷۷ بررسی طلایی (adapter == فراخوانی مستقیم)؛ veto@1/evidence@1 عمداً تا فاز ۴ خالی |
| ۳a — سوییچ engine | ۲۰۲۶-۰۹-۲۳ | `84b9de1` (میخ‌ها) + *(این کامیت)* | ✅ importهای فیچر engine: ۱۸ → ۴ (core/plugins + JudgeContext + fa/config/app_paths)؛ BUS با ۱۲ نقطهٔ رویداد؛ بدنهٔ _send_telegram به پلاگین notify منتقل شد؛ میخ‌ها (۴۷ بررسی، شامل طلاییِ چرخهٔ کامل با ۱ سیگنال BUY 8/11) **بدون تغییر** سبز؛ سربار _caps ≈ ۰٫۱۵ms |
| ۳b–۸ | — | — | در انتظار Preview + تأیید مالک (قانون اجرا) |
