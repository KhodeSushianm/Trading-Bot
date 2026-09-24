#!/usr/bin/env node
/* میخ‌های رفتاری موتور JS — فاز ۶ (سوییچ runPipeline/cycleCore/svcTick به پلاگین‌ها).
 *
 * اجرا:  node tests/js/test_cycle_switch.js   (آفلاین، بدون شبکه، قطعی)
 *
 * انضباط «اول میخ، بعد چکش» (آینهٔ tests/test_engine_switch.py فاز ۳):
 *   • این تست‌ها ابتدا روی موتور *فعلی* نوشته و سبز شده‌اند (کامیت میخ‌ها).
 *   • سپس سوییچ فاز ۶ انجام می‌شود و **همین تست‌ها بدون هیچ تغییری** باید
 *     سبز بمانند — اثبات اینکه لاگ‌ها/اعلان‌ها/storage/ترتیب‌ها عوض نشده‌اند.
 *   • بخش‌های مشروط (bus/registry/plugins.js): قبل از سوییچ skip، بعد از
 *     سوییچ فعال — چون bus و registry رفتاری *افزودنی* بدون listener هستند
 *     (دقیقاً همان الگویی که در فاز ۳a پایتون جواب داد).
 *
 * طلاییِ ۱۱ سناریو: tests/js/golden/cycle_core_golden.json (با
 * tests/js/golden/gen_cycle_golden.js ضبط شده — FakeDate ثابت، لایسنس تریال،
 * ODINNative ساختگی، seamهای fetcher پچ‌شده؛ کندل‌ها با فرمول‌های همان
 * gen_engine_golden.py پایتون → EURUSD BUY 8/11 در هر دو موتور).
 */
'use strict';

const fs = require('fs');
const path = require('path');

const gen = require('./golden/gen_cycle_golden.js');

let COUNT = 0;
function A(cond, msg) {
  if (!cond) throw new Error(msg);
  COUNT++;
}

function firstDiffPath(a, b, p) {
  p = p || '';
  if (a === b) return null;
  if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') {
    return p || '(root)';
  }
  if (Array.isArray(a) !== Array.isArray(b)) return p || '(root)';
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of Array.from(keys).sort()) {
    const d = firstDiffPath(a[k], b[k], p ? p + '.' + k : k);
    if (d) return d;
  }
  return null;
}

// ══════════════════════════════════════════════════════════════
async function testGoldenScenarios() {
  A(fs.existsSync(gen.GOLDEN_PATH),
    'فایل طلایی وجود ندارد — اول node tests/js/golden/gen_cycle_golden.js');
  const golden = JSON.parse(fs.readFileSync(gen.GOLDEN_PATH, 'utf8'));
  const got = await gen.runAllScenarios();
  for (const name of gen.SCENARIOS) {
    const g = gen.stableStringify(got[name]);
    const e = gen.stableStringify(golden[name]);
    if (g !== e) {
      const at = firstDiffPath(got[name], golden[name]);
      throw new Error(`سناریوی «${name}» با طلایی فرق دارد — اولین اختلاف در: ${at}`);
    }
    A(true, `سناریوی طلایی «${name}» بایت‌به‌بایت مطابقت کرد`);
  }
}

// ── پین‌های خوانای انسانی (مستقل از فایل طلایی) ────────────────
function hasLog(rec, substr) {
  return rec.logs.some((l) => l.indexOf(substr) >= 0);
}

async function testInlinePins() {
  // ۱) چرخهٔ کامل با سیگنال
  const s1 = await gen.runScenario('svc_cycle_signals');
  A(s1.cycleDone.length === 1 && s1.cycleDone[0] === 15 && s1.stopBg === 0,
    'چرخهٔ سالم: bgCycleDone(15) و بدون stopBackground');
  A(s1.notify.length === 1 && s1.notify[0][0] === 'سیگنال جدید — EURUSD (خرید)',
    'اعلان سیگنال تازه با عنوان دقیق');
  const st = s1.storage['state.last'];
  A(st && st.judgments.length === 7 && st.verdicts[0] === 'EURUSD=BUY_SETUP',
    '۷ نماد تحلیل شد؛ EURUSD ستاپ خرید (دادهٔ پولبکِ ساختگی)');
  const sig = st.judgments.filter((j) => j.hasSignal);
  A(sig.length === 1 && sig[0].symbol === 'EURUSD' && sig[0].direction === 'BUY'
    && sig[0].score >= 7 && sig[0].signal.sl < sig[0].signal.entry
    && sig[0].signal.entry < sig[0].signal.tp,
    'یک سیگنال BUY با امتیاز ≥ آستانه و SL < ورود < TP');
  const jrec = s1.storage['journal.jsonl'];
  A(Array.isArray(jrec) && jrec.length === 1 && jrec[0].kind === 'signal' && jrec[0].sent === true,
    'سیگنال در ژورنال ثبت شد (kind=signal, sent=true)');
  A(s1.storage['chart.EURUSD'] && s1.storage['chart.EURUSD'].bars === 260,
    'کش نمودار EURUSD با ۲۶۰ کندل نوشته شد');

  // ۱ب) S3 — دروازهٔ توافق در سطح سرویس: min_agree=4 (دست‌یافتنی‌نیست) →
  // سیگنالِ آمادهٔ EURUSD صادقانه NO_STRATEGY می‌شود: بدون اعلان، بدون
  // ژورنال؛ state/لاگ باقی‌اند (نگهبان یا سبز معنادار یا قرمز پرسروصدا).
  const s1g = await gen.runScenario('svc_gated_no_strategy');
  A(s1g.cycleDone.length === 1 && s1g.stopBg === 0,
    'چرخهٔ دروازه‌دار: زمان‌بندی سالم (bgCycleDone یک‌بار)');
  A(s1g.notify.length === 0,
    'دروازه: اعلانِ سیگنال صادر نشد (بی‌صدا هم نیست — state/لاگ می‌گوید)');
  const stg = s1g.storage['state.last'];
  const eurg = stg && stg.judgments.filter((j) => j.symbol === 'EURUSD')[0];
  A(eurg && eurg.reject_reason === 'NO_STRATEGY' && eurg.hasSignal === false
    && eurg.score >= 7,
    'EURUSD: امتیاز ≥ آستانه ولی بدون توافقِ استراتژی → NO_STRATEGY');
  A(!Array.isArray(s1g.storage['journal.jsonl']),
    'بدون سیگنال → رکوردی در ژورنال نیست (حلقهٔ صداقت دست‌نخورده)');
  A(hasLog(s1g, 'هیچ سیگنالی صادر نشد'),
    'لاگِ صادقانهٔ «هیچ سیگنالی صادر نشد» در چرخهٔ دروازه‌دار');

  // ۱پ) S4 — مسیرِ *تنظیمات گوشی*: هر سه استراتژی خاموش → config-bridge →
  // registry → دروازهٔ fail-closed (بدون جهشِ مستقیمِ CONFIG — سیم‌کشی واقعی)
  const s1s = await gen.runScenario('svc_settings_strategies_off');
  A(s1s.notify.length === 0, 'تنظیمات: خاموشِ همهٔ استراتژی‌ها → بدون اعلان سیگنال');
  const st10 = s1s.storage['state.last'];
  const eur10 = st10 && st10.judgments.filter((j) => j.symbol === 'EURUSD')[0];
  A(eur10 && eur10.reject_reason === 'NO_STRATEGY' && eur10.hasSignal === false
    && eur10.score >= 7,
    'تنظیمات: EURUSDِ آماده با امتیاز ≥ آستانه → NO_STRATEGY (fail-closed)');
  const set10 = s1s.storage['settings'] || {};
  A(set10.strategy_tp_enabled === false && set10.strategy_lb_enabled === false
    && set10.strategy_carry_enabled === false && set10.judge_enabled !== false,
    'settings ذخیره‌شده: سه کلید استراتژی خاموش (داور دست‌نخورده)');
  A(!Array.isArray(s1s.storage['journal.jsonl']),
    'بدون سیگنال → ژورنال رکوردی نگرفت');

  // ۱ت) S4 — min_agree=2 از تنظیمات: EURUSD فقط یک موافق دارد → رد
  const s1m = await gen.runScenario('svc_settings_min_agree_2');
  const st11 = s1m.storage['state.last'];
  const eur11 = st11 && st11.judgments.filter((j) => j.symbol === 'EURUSD')[0];
  A(eur11 && eur11.reject_reason === 'NO_STRATEGY' && eur11.hasSignal === false,
    'تنظیمات: min_agree=2 → تک‌موافق کافی نیست → NO_STRATEGY');
  A((s1m.storage['settings'] || {}).strategy_min_agree === 2
    && s1m.notify.length === 0,
    'min_agree=2 در settings ذخیره و بدون اعلان سیگنال');

  // ۲) قطعی داده — early-exit صادقانه
  const s2 = await gen.runScenario('data_outage');
  A(hasLog(s2, 'هیچ نمادی تحلیل نشد — اینترنت را بررسی کنید'),
    'early-exit با پیام دقیقِ فعلی');
  A(s2.notify.length === 0 && s2.cycleDone[0] === 15,
    'بدون اعلان سیگنال؛ زمان‌بندی چرخه بعدی سالم');
  A(s2.storage['state.last'] && s2.storage['state.last'].nAnalyses === 0
    && s2.storage['state.last'].errors >= 1,
    'state.last با صفر تحلیل و errors ≥ 1 ذخیره شد (صادقانه)');

  // ۳) سیگنال تکراری — cooldown ضداسپم
  const s3 = await gen.runScenario('duplicate_cooldown');
  A(s3.cycleDone.length === 2, 'دو چرخه اجرا شد');
  A(hasLog(s3, '[i] سیگنال EURUSD تکراری است —'), 'پیام cooldown با قالب فعلی');
  A(s3.notify.length === 1, 'چرخهٔ دوم اعلان سیگنال نداد (فقط چرخهٔ اول)');
  const sent = s3.storage['sent_signals.json'];
  A(sent && sent['EURUSD|BUY'] && sent['EURUSD|BUY'].score >= 7,
    'sent_signals.json کلید EURUSD|BUY را نگه می‌دارد');

  // ۴) هشدار قیمت — شلیک + حذف یک‌بارمصرف
  const s4 = await gen.runScenario('alerts_fired');
  A(s4.notify.some((x) => x[0] === 'هشدار قیمت — EURUSD'), 'اعلان هشدار قیمت با عنوان دقیق');
  A(s4.notify.some((x) => x[1].indexOf('به سطح 1.25000 رسید (عبور به پایین)') >= 0),
    'بدنهٔ هشدار: سطح/جهت با قیمت pip-فرمت');
  A(Array.isArray(s4.storage['alerts.json']) && s4.storage['alerts.json'].length === 0,
    'هشدار یک‌بارمصرف بعد از شلیک حذف شد');
  A(s4.ongoing.some((x) => x[1].indexOf('۱ هشدار قیمت فعال شد') >= 0),
    'خلاصهٔ ongoing تعداد هشدارها را می‌گوید');

  // ۵) خبر فوری — فقط در برابر چرخهٔ قبل
  const s5 = await gen.runScenario('breaking_news');
  A(s5.notify.some((x) => x[0] === 'خبر فوری — GoldenBrk'), 'اعلان خبر فوری با نام فید');
  A(hasLog(s5, '۱ فوری'), 'لاگ موتور اخبار تعداد فوری را می‌گوید');
  const st5 = s5.storage['state.last'];
  const eur5 = st5.judgments.filter((j) => j.symbol === 'EURUSD')[0];
  A(eur5 && eur5.reject_reason === 'VETO' && eur5.hasSignal === false,
    'خبر فوریِ ناسازگار در چرخهٔ دوم سیگنال را وتو کرد (BREAKING_NEWS)');

  // ۶) داور خاموش — گیت svcTick بدون اجرای چرخه
  const s6 = await gen.runScenario('judge_disabled');
  A(s6.ongoing.some((x) => x[1] === 'داور در تنظیمات خاموش است — سیگنالی صادر نمی‌شود'),
    'گیت داور: پیام ongoing دقیق');
  A(s6.cycleDone[0] === 15 && !hasLog(s6, 'دریافت EURUSD'),
    'چرخه اصلاً اجرا نشد (بدون واکشی داده)');

  // ۷) فیچرها خاموش — مسیر غیرفعالِ guardهای داخلی (fallback فاز ۶)
  const s7 = await gen.runScenario('features_disabled');
  A(hasLog(s7, '[!] تقویم اقتصادی در دسترس نیست: غیرفعال در تنظیمات'),
    'تقویم غیرفعال: snap + لاگ دقیقِ امروز');
  A(hasLog(s7, '[!] موتور اخبار: غیرفعال در تنظیمات'),
    'اخبار غیرفعال: لاگ دقیقِ امروز');
  A(!hasLog(s7, 'دریافت تاییدیه تریدینگ‌ویو'),
    'TV خاموش: هیچ واکشی/لاگی ندارد');
  const st7 = s7.storage['state.last'];
  A(st7 && st7.calOk === false && st7.newsOk === false && st7.tvCount === 0,
    'state.last: calSnap/newsSnap ناسالم و tvMap خالی (صادقانه)');

  // ۸) بازار بسته — گیت بدون شبکه
  const s8 = await gen.runScenario('market_closed');
  A(s8.cycleDone.length === 1 && s8.cycleDone[0] === 30, 'بازار بسته: bgCycleDone(30)');
  A(s8.ongoing.some((x) => x[1].indexOf('بازار بسته است (شنبه — بازار فارکس بسته است)') >= 0),
    'پیام بسته‌بودن بازار (noEmoji شده) در ongoing');
  A(s8.logs.length <= 2 && !hasLog(s8, 'دریافت EURUSD'), 'بدون واکشی داده در بازار بسته');
}

// ══════════════════════════════════════════════════════════════
//  بخش‌های مشروط — قبل از سوییچ skip، بعد از سوییچ فعال (بدون تغییر فایل)
// ══════════════════════════════════════════════════════════════
async function testBusEventsWhenPresent() {
  const probe = gen.createApp({});
  if (!probe.O.BUS || typeof probe.O.BUS.on !== 'function') {
    A(true, 'BUS هنوز وجود ندارد (قبل از سوییچ) — این دو بررسی مشروط skip شدند');
    A(true, 'skip');
    return;
  }
  // ۱) چرخهٔ کامل با سیگنال (۶c): ۳۱ رویداد = ۱۱ مرحله × start/done +
  //    ۹ رویداد استانداردِ امروز — آینهٔ ۳۳ رویداد پایتون منهای
  //    report.rendered/telegram.sent/vetoes.computed که معادل JS ندارند
  //    (توالی دقیق در test_pipeline_events.js پین شده؛ اینجا نام‌ها)
  const sink = [];
  const s1 = await gen.runScenario('svc_cycle_signals', sink);
  const seq = sink.map((x) => x[0]);
  const expectedNames = ['cycle.start',
    'stage.start', 'market.collected', 'stage.done',
    'stage.start', 'journal.resolved', 'stage.done',
    'stage.start', 'fundamental.collected', 'stage.done',
    'stage.start', 'stage.done',
    'stage.start', 'judge.done', 'signal.created', 'stage.done',
    'stage.start', 'stage.done',
    'stage.start', 'signal.sent', 'stage.done',
    'stage.start', 'alerts.fired', 'stage.done',
    'stage.start', 'stage.done',
    'stage.start', 'stage.done',
    'stage.start', 'cycle.end', 'stage.done'];
  A(JSON.stringify(seq) === JSON.stringify(expectedNames),
    'ترتیب رویدادهای bus در چرخهٔ کامل (۶c — ۳۱ رویداد): ' + JSON.stringify(seq));
  const stagesDone = sink.filter((x) => x[0] === 'stage.done').map((x) => x[1]);
  A(stagesDone.join(',') === ['collect_market', 'journal_pre', 'collect_fundamental',
    'compute_vetoes', 'judge', 'render', 'dispatch_signals', 'price_alerts',
    'chart_cache', 'dashboard', 'archive_notify'].join(','),
    '۱۱ مرحله به ترتیب کانونیکال (همان STAGES پایتون): ' + stagesDone.join(','));
  A(s1.notify.length === 1, 'رویدادها افزودنی‌اند — خروجی چرخه عوض نشد');

  // ۲) early-exit (۶c — هم‌تراز پایتون): stop در journal_pre → دقیقاً ۷
  //    رویداد، بدون fundamental/judge/alerts و بدون cycle.end
  const sink2 = [];
  await gen.runScenario('data_outage', sink2);
  const expected2 = [
    ['cycle.start', null, null],
    ['stage.start', 'collect_market', null],
    ['market.collected', null, null],
    ['stage.done', 'collect_market', false],
    ['stage.start', 'journal_pre', null],
    ['journal.resolved', null, null],
    ['stage.done', 'journal_pre', true]
  ];
  A(JSON.stringify(sink2) === JSON.stringify(expected2),
    'outage: دقیقاً ۷ رویداد با stop=true در journal_pre (آینهٔ پایتون): '
    + JSON.stringify(sink2));
  A(!sink2.some((x) => x[0] === 'plugin.failed'), 'outage: هیچ plugin.failed منتشر نشد');
}

async function testRegistryWhenPresent() {
  const probe = gen.createApp({});
  if (typeof probe.O.buildDefaultRegistry !== 'function') {
    A(true, 'plugins.js هنوز بار نمی‌شود (قبل از سوییچ) — این بخش مشروط skip شد');
    return;
  }
  const O = probe.O;
  const cfg = O.deepFill(O.CONFIG, {});
  const built = O.buildDefaultRegistry(cfg, 'android');
  const reg = built.registry || built.reg || built[0];
  const info = built.info || built[1];
  A(!!reg && !!info, 'buildDefaultRegistry باید (registry, info) بدهد');

  // idهای پلاگین‌های JS — همان نام‌های پایتون (تقارن بین‌موتوری)
  // (فاز ۶b: ۱۵ قاعدهٔ داور اضافه شد — فهرست ساختاری است، نه طلاییِ رفتاری)
  // (S2 v0.26: سه پلاگین strategy-* اضافه شد — ۲۶→۲۹؛ ثبتِ بی‌اثر تا سوییچ
  //  S3؛ آینهٔ src/plugins/strategies.py با همان id/priority/stage/binding)
  const ids = reg.all().map((r) => r.id);
  const expectedIds = ['data-yahoo', 'data-tradingview', 'analysis-technical',
    'analysis-strength', 'session', 'fundamental-calendar', 'fundamental-news',
    'judge-core', 'judge-risk', 'journal', 'alerts-price',
    'veto-data', 'veto-weekend', 'veto-tf-conflict', 'veto-range',
    'veto-event', 'veto-vol-spike', 'veto-breaking-news',
    'ev-trend', 'ev-level', 'ev-fundamental', 'ev-momentum',
    'ev-strength', 'ev-news', 'ev-tv', 'ev-session',
    'strategy-trend-pullback', 'strategy-london-breakout', 'strategy-carry'];
  A(ids.join(',') === expectedIds.join(','),
    '۲۹ پلاگین اندروید با idهای متقارن پایتون (۱۱ فاز ۶ + ۱۵ قاعدهٔ داور فاز ۶b + ۳ استراتژی S2): ' + JSON.stringify(ids));
  A(info.disabled.length === 0, 'با config پیش‌فرض هیچ پلاگینی disabled نیست');

  // bindingها: خاموشی فیچرها → پلاگین مربوطه غیرفعال (همان کلیدهای موجود)
  const off = O.deepFill(O.CONFIG, {
    fundamental: { enabled: false }, news: { enabled: false }, tradingview: { enabled: false }
  });
  const b2 = O.buildDefaultRegistry(off, 'android');
  const reg2 = b2.registry || b2[0];
  A(reg2.byId('fundamental-calendar').enabled === false
    && reg2.byId('fundamental-news').enabled === false
    && reg2.byId('data-tradingview').enabled === false,
    'fundamental/news/tradingview خاموش → پلاگین‌ها غیرفعال (کلیدهای موجود)');
  A(reg2.get('odin.fundamental.calendar@1') === null
    && reg2.byId('journal').enabled === true,
    'get() پلاگین خاموش را نمی‌دهد؛ journal همیشه هست (config=None — مثل پایتون)');

  // adapter == فراخوانی مستقیم (طلاییِ فاز ۲ به سبک JS)
  const sess = reg.get('odin.session@1');
  const lm = O.core.createLifecycle({ context: info.context });
  lm.initialize(sess);
  const d1 = O.marketStatus(new Date(gen.FIXED_WED));
  const d2 = sess.instance.marketStatus(new Date(gen.FIXED_WED));
  A(JSON.stringify(d1) === JSON.stringify(d2), 'session: adapter == O.marketStatus');

  const risk = reg.get('odin.judge.risk@1');
  lm.initialize(risk);
  const rc = cfg.judge.risk;
  const r1 = O.computeLevels('BUY', 1.149, 0.001, 1.1486, 1.156, rc);
  const r2 = risk.instance.computeLevels('BUY', 1.149, 0.001, 1.1486, 1.156, rc);
  A(JSON.stringify(r1) === JSON.stringify(r2), 'judge-risk: adapter == O.computeLevels');

  const tech = reg.get('odin.analysis.technical@1');
  lm.initialize(tech);
  const md = gen.makeMarketData('EURUSD');
  const a1 = O.analyzeSymbol(cfg.symbols[0], md, cfg.analysis);
  const a2 = tech.instance.analyzeSymbol(cfg.symbols[0], md, cfg.analysis);
  A(JSON.stringify(a1) === JSON.stringify(a2), 'analysis-technical: adapter == O.analyzeSymbol');

  const jr = reg.get('odin.journal@1');
  lm.initialize(jr);
  const jInst = jr.instance.open({ get: () => '', set: () => { }, del: () => { } });
  A(jInst instanceof O.Journal, 'journal.open باید نمونهٔ O.Journal بدهد');

  const alerts = reg.get('odin.alerts.price@1');
  lm.initialize(alerts);
  A(JSON.stringify(alerts.instance.checkAlerts({ get: () => '', set: () => { }, del: () => { } }, [], gen.FIXED_WED))
    === JSON.stringify(O.alertsCheck({ get: () => '', set: () => { }, del: () => { } }, [], gen.FIXED_WED)),
    'alerts-price: adapter == O.alertsCheck');

  // ES5 بودن plugins.js (همان نگهبان smoke_core برای core.js)
  const src = fs.readFileSync(path.join(gen.WWW, 'plugins.js'), 'utf8');
  const stripped = src
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/(^|[^:'"`\\])\/\/[^\n]*/g, '$1 ')
    .replace(/'(?:[^'\\]|\\.)*'/g, "''")
    .replace(/"(?:[^"\\]|\\.)*"/g, '""');
  A(!/=>/.test(stripped) && !/\bconst\b/.test(stripped) && !/\blet\b/.test(stripped)
    && !/\bclass\b/.test(stripped) && stripped.indexOf('`') < 0,
    'plugins.js باید ES5 خالص بماند (WebView قدیمی)');
}

// ══════════════════════════════════════════════════════════════
async function main() {
  const tests = [testGoldenScenarios, testInlinePins,
    testBusEventsWhenPresent, testRegistryWhenPresent];
  const fails = [];
  for (const t of tests) {
    try {
      await t();
    } catch (e) {
      fails.push(t.name + ': ' + (e && e.message || e));
    }
  }
  if (fails.length) {
    console.log('❌ CYCLE-SWITCH TESTS FAILED');
    fails.forEach((f) => console.log('  •', f));
    process.exit(1);
  }
  console.log('✅ CYCLE-SWITCH TESTS OK — ' + COUNT + ' بررسی پاس؛ میخ‌های رفتاری موتور JS '
    + '(۱۱ سناریوی طلایی svcTick/cycleCore/runPipeline + پین‌های inline'
    + ' + بخش‌های مشروط bus/registry) سبز‌اند');
  process.exit(0);
}

main();
