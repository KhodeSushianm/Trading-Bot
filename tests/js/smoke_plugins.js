/* اسموک‌تست فاز ۷ — enable/disable یکپارچه زیر مانیفست (سمت اندروید) +
 * سخت‌گیری Failure Isolation. آفلاین، قطعی، بدون DOM.
 *
 * اجرا: node tests/js/smoke_plugins.js
 *
 * پوشش:
 *   ۱) bindingها با *همان کلیدهای موجود*: judge.enabled → judge-core/risk ·
 *      fundamental/news/tradingview (از فاز ۶) · journal عمداً بدون binding
 *   ۲) override صریح plugins.<id>.enabled — برنده در هر دو جهت
 *   ۳) literalهای «غیرفعال در تنظیمات» در runPipeline == خروجی guardهای
 *      داخلی O.fetchCalendar/O.fetchNews (تک‌مسیریِ فاز ۷ بایت‌به‌بایت است)
 *   ۴) سطح موتور: override-off روی calendar/news/tv → همان لاگ‌های مسیر
 *      فیچر-خاموش (مقایسه با اجرای settings-off) + state صادقانه
 *   ۵) سخت‌گیری: judge-core خاموش با override (judge.enabled روشن) →
 *      لاگ صادقانهٔ «پلاگین داور/سشن در دسترس نیست» بدون کرش/سیگنال
 *
 * سناریوهای فیچر-خاموشِ طلایی (features_disabled/judge_disabled) در
 * tests/js/test_cycle_switch.js پین‌اند و باید بدون تغییر سبز بمانند.
 */
'use strict';

const gen = require('./golden/gen_cycle_golden.js');

let checks = 0;
let failures = 0;
function ok(cond, msg) {
  checks++;
  if (!cond) { failures++; console.log('  ✗ ' + msg); }
  return !!cond;
}
function group(t) { console.log('\n── ' + t + ' ' + '─'.repeat(Math.max(0, 56 - t.length))); }

function deepEq(a, b) {
  if (a === b) return true;
  if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const ka = Object.keys(a), kb = Object.keys(b);
  if (ka.length !== kb.length) return false;
  return ka.every((k) => deepEq(a[k], b[k]));
}

function waitCycle(calls, n, timeoutMs) {
  return new Promise((res, rej) => {
    const t0 = Date.now();
    const iv = setInterval(() => {
      if (calls.cycleDone.length >= n) { clearInterval(iv); res(); }
      else if (Date.now() - t0 > (timeoutMs || 15000)) {
        clearInterval(iv); rej(new Error('timeout waiting cycleDone #' + n));
      }
    }, 15);
  });
}

async function main() {
  // ══════════════════════════════════════════════════════════════
  group('۱) bindingها با همان کلیدهای موجود + override');
  {
    const app = gen.createApp({});
    const O = app.O;
    const built = O.buildDefaultRegistry(O.deepFill(O.CONFIG, {}), 'android');
    ok(built.registry.all().length === 26
       && built.registry.all().every((r) => r.enabled),
      'config پیش‌فرض: هر ۲۶ پلاگین فعال (۱۱ فاز ۶ + ۱۵ قاعدهٔ داور فاز ۶b)');

    const off = O.deepFill(O.CONFIG, { judge: { enabled: false } });
    const b2 = O.buildDefaultRegistry(off, 'android');
    ok(b2.registry.byId('judge-core').enabled === false
       && b2.registry.byId('judge-risk').enabled === false,
      'judge.enabled=false → judge-core/judge-risk غیرفعال (binding فاز ۷)');
    ok(b2.registry.get('odin.judge.engine@1') === null,
      'get() پلاگین خاموش را نمی‌دهد');
    ok(b2.registry.byId('journal').enabled === true
       && b2.registry.byId('alerts-price').enabled === true
       && b2.registry.byId('session').enabled === true,
      'journal/alerts/session بدون binding → همیشه فعال (زیرساخت/ضداسپم)');

    const ov = O.deepFill(O.CONFIG, { plugins: { 'fundamental-news': { enabled: false } } });
    const b3 = O.buildDefaultRegistry(ov, 'android');
    ok(b3.registry.byId('fundamental-news').enabled === false,
      'override: plugins.fundamental-news.enabled=false با news.enabled=true → غیرفعال');

    const ov2 = O.deepFill(O.CONFIG, {
      news: { enabled: false },
      plugins: { 'fundamental-news': { enabled: true } }
    });
    const b4 = O.buildDefaultRegistry(ov2, 'android');
    ok(b4.registry.byId('fundamental-news').enabled === true,
      'override: plugins.enabled=true با news.enabled=false → پلاگین در دسترس');
    ok(b4.info.log.some((l) => l.indexOf('«fundamental-news» ثبت شد') >= 0),
      'لاگ فارسی ثبت برای پلاگین override-روشن حاضر است');
  }

  // ══════════════════════════════════════════════════════════════
  group('۲) literalهای غیرفعال == guardهای داخلی (بایت‌به‌بایت)');
  {
    const app = gen.createApp({});
    const O = app.O;
    const st = { get: () => '', set: () => { }, del: () => { } };
    const cfgOff = { fundamental: { enabled: false }, news: { enabled: false } };
    const calSnap = await O.fetchCalendar(cfgOff, st);
    const newsSnap = await O.fetchNews(cfgOff, null);
    // همان literalهایی که runPipelineِ فاز ۷ در غیبت پلاگین می‌سازد:
    const INLINE_CAL = {
      events: [], ok: false, error: 'غیرفعال در تنظیمات', fetched: false,
      stale: false, fromCache: false, weekRange: ['', '']
    };
    const INLINE_NEWS = {
      items: [], ok: false, error: 'غیرفعال در تنظیمات', feedsOk: 0,
      feedsFailed: 0, staleFeeds: [], failedNames: [], rawCount: 0
    };
    ok(deepEq(calSnap, INLINE_CAL),
      'snap تقویمِ guard داخلی == literal درون‌خطی runPipeline: ' + JSON.stringify(calSnap));
    ok(deepEq(newsSnap, INLINE_NEWS),
      'snap اخبارِ guard داخلی == literal درون‌خطی runPipeline: ' + JSON.stringify(newsSnap));
  }

  // ══════════════════════════════════════════════════════════════
  group('۳) سطح موتور — override-off == فیچر-off (همان لاگ‌ها/ state)');
  async function runWith(prefsSeed, configPatcher) {
    const app = gen.createApp({ prefs: prefsSeed });
    if (configPatcher) configPatcher(app.O);
    app.O.trialStart(app.pstorage);
    app.O.svcStart();
    await waitCycle(app.calls, 1);
    return app;
  }
  {
    // الف) فیچرها خاموش از مسیر settings (همان مکانیزم امروز)
    const viaSettings = await runWith({
      settings: JSON.stringify({ fund_enabled: false, news_enabled: false, tv_enabled: false })
    });
    // ب) فیچرها روشن، ولی پلاگین‌ها با override خاموش (مسیر جدید فاز ۷)
    const viaOverride = await runWith({}, (O) => {
      O.CONFIG.plugins = {
        'fundamental-calendar': { enabled: false },
        'fundamental-news': { enabled: false },
        'data-tradingview': { enabled: false }
      };
    });
    const pick = (rec) => rec.logs.filter((l) =>
      l.indexOf('تقویم اقتصادی') >= 0 || l.indexOf('موتور اخبار') >= 0
      || l.indexOf('تریدینگ‌ویو') >= 0);
    ok(deepEq(pick(viaOverride), pick(viaSettings)),
      'لاگ‌های calendar/news/tv در دو مسیر یکی است:\n    settings=' +
      JSON.stringify(pick(viaSettings)) + '\n    override=' + JSON.stringify(pick(viaOverride)));
    ok(pick(viaOverride).some((l) => l.indexOf('[!] تقویم اقتصادی در دسترس نیست: غیرفعال در تنظیمات') >= 0)
       && pick(viaOverride).some((l) => l.indexOf('[!] موتور اخبار: غیرفعال در تنظیمات') >= 0)
       && !pick(viaOverride).some((l) => l.indexOf('🔍') >= 0 || l.indexOf('تاییدیه تریدینگ‌ویو') >= 0),
      'override-off: snap غیرفعال + بدون واکشی TV (دقیقاً رفتار فیچر-خاموش)');
    const stOv = JSON.parse(viaOverride.prefs.get('state.last') || '{}');
    ok(stOv.calSnap && stOv.calSnap.ok === false && stOv.calSnap.error === 'غیرفعال در تنظیمات'
       && stOv.newsSnap && stOv.newsSnap.ok === false
       && Object.keys(stOv.tvMap || {}).length === 0,
      'state.last: calSnap/newsSnap غیرفعال و tvMap خالی (صادقانه)');
    ok(viaOverride.calls.cycleDone[0] === 15 && viaOverride.calls.stopBg === 0,
      'چرخه با override-off سالم کامل می‌شود (زمان‌بندی عادی)');
  }

  // ══════════════════════════════════════════════════════════════
  group('۴) سخت‌گیری — داور غایب (override) بدون کرش، صادقانه');
  {
    const app = gen.createApp({});
    app.O.CONFIG.plugins = { 'judge-core': { enabled: false } };
    app.O.trialStart(app.pstorage);
    app.O.svcStart();
    await waitCycle(app.calls, 1);
    ok(app.logs.some((l) => l.indexOf('پلاگین داور/سشن در دسترس نیست') >= 0),
      'judge-core غایب + judge.enabled روشن → لاگ صادقانهٔ unavailable');
    ok(app.calls.notify.length === 0, 'بدون پلاگین داور سیگنالی صادر/اعلان نمی‌شود');
    ok(app.calls.cycleDone[0] === 15 && app.calls.stopBg === 0,
      'چرخه نمی‌شکند — زمان‌بندی عادی ادامه می‌یابد');
    const st = JSON.parse(app.prefs.get('state.last') || '{}');
    ok(st && (st.judgments || []).length === 0, 'state.last بدون قضاوت ذخیره شد (صادقانه)');
  }

  // ══════════════════════════════════════════════════════════════
  console.log('\n' + '═'.repeat(56));
  if (failures) {
    console.log('✗ SMOKE PLUGINS FAILED — ' + failures + ' از ' + checks + ' بررسی شکست خورد');
    process.exit(1);
  }
  console.log('✅ SMOKE PLUGINS OK — ' + checks + ' بررسی پاس؛ enable/disable یکپارچه '
    + '(کلیدهای موجود + override) و سخت‌گیری Failure Isolation در موتور اندروید سالم است');
  process.exit(0);
}

main().catch((e) => { console.error('❌ خطای غیرمنتظره: ' + (e && e.stack || e)); process.exit(1); });
