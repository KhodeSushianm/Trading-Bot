#!/usr/bin/env node
/* تولیدکنندهٔ طلاییِ چرخهٔ سرویس — فاز ۶ (سوییچ JS به پلاگین‌ها).
 *
 * ایده (انضباط «اول میخ، بعد چکش» — آینهٔ tests/golden/gen_engine_golden.py):
 *   ۱) این اسکریپت ۸ سناریوی کامل svcTick/cycleCore/runPipeline را با دادهٔ
 *      **ساختگیِ قطعی** و **بدون شبکه** روی موتور *فعلی* اجرا می‌کند و
 *      خروجی نرمال‌شده (لاگ‌ها/اعلان‌ها/storage/نتایج) را در
 *      tests/js/golden/cycle_core_golden.json ضبط می‌کند (قبل از سوییچ).
 *   ۲) tests/js/test_cycle_switch.js همان اجرا را تکرار و با طلایی مقایسه
 *      می‌کند. بعد از سوییچِ فاز ۶ باید **بدون هیچ تغییری** سبز بماند.
 *
 * seamها عمداً «مستقل از نسخه» انتخاب شده‌اند تا همین هارنس قبل و بعد از
 * سوییچ معتبر باشد:
 *   • O.fetchYahooSymbol / O.fetchTvSnapshot (پچ سطح namespace — هر دو نسخه
 *     همان‌ها را صدا می‌زنند؛ بعد از سوییچ از راه adapter پلاگین)
 *   • O.fetchCalendar / O.fetchNews فقط در حالت «فعال» پچ می‌شوند — مسیر
 *     غیرفعال (guard داخلی data.js) عمداً واقعی می‌ماند چون خودِ مسیرِ
 *     fallback فاز ۶ است و باید بایت‌به‌بایت حفظ شود
 *   • ODINNative (prefs حافظه‌ای + جاسوس‌های اعلان) — مثل smoke_service
 *   • Date با FakeDate ثابت (چهارشنبه ۱۴:۰۰ UTC / شنبه ۱۲:۰۰ UTC)
 *   • فهرست فایل‌ها پویا است: اگر core.js/plugins.js وجود داشته باشند
 *     (بعد از سوییچ) به ترتیب index.html اول بار می‌شوند — بدون تغییر هارنس
 *
 * اجرا (برای ضبط/بازتولید عمدیِ طلایی — فقط با دلیل موجه):
 *   node tests/js/golden/gen_cycle_golden.js
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HERE = __dirname;
const ROOT = path.resolve(HERE, '..', '..', '..');
const WWW = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www', 'js');
const GOLDEN_PATH = path.join(HERE, 'cycle_core_golden.json');

// ترتیب بارگذاری = ترتیب index.html؛ core/plugins (فاز ۵/۶) اگر حاضر باشند اول‌اند
const BASE_FILES = ['md5.js', 'fa.js', 'icons.js', 'license.js', 'config.js', 'indicators.js',
  'session.js', 'technical.js', 'calendar.js', 'news.js', 'judge.js', 'strategies.js', 'journal.js', 'data.js',
  'alerts.js', 'chart.js', 'sharecard.js', 'briefing.js', 'components.js', 'ui.js', 'app.js'];

function fileList() {
  const pre = ['core.js', 'plugins.js'].filter((f) => fs.existsSync(path.join(WWW, f)));
  return pre.concat(BASE_FILES);
}

// لحظه‌های ثابت (۲۰۲۶-۰۹-۲۳ چهارشنبه / ۲۰۲۶-۰۹-۱۹ شنبه)
const FIXED_WED = Date.UTC(2026, 8, 23, 14, 0, 0);
const FIXED_SAT = Date.UTC(2026, 8, 19, 12, 0, 0);
const DEVICE_ID = 'ab'.repeat(32);

// قیمت پایهٔ قطعی به ازای هر نماد — همان BASES در gen_engine_golden.py
const BASES = {
  EURUSD: 1.1000, GBPUSD: 1.3000, USDJPY: 150.00, USDCAD: 1.3600,
  AUDUSD: 0.6600, USDCHF: 0.8800, XAUUSD: 2400.0
};

// ══════════════════════════════════════════════════════════════
//  دادهٔ ساختگیِ قطعی — فرمول‌ها بایت‌به‌بایت از gen_engine_golden.py
//  پورت شده‌اند (همان _mk_frame و _mk_frame_pullback) تا موتور JS (که
//  parity‌اش با پایتون اثبات شده) همان الگوها را ببیند.
// ══════════════════════════════════════════════════════════════
const T0 = Date.UTC(2026, 7, 1);
const STEP = { '15m': 900e3, '1h': 3600e3, '4h': 14400e3 };

function mkFrame(n, base, stepMs, drift) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const c = base + drift * i + 0.00012 * base * ((i * 7) % 11 - 5);
    out.push({ t: T0 + i * stepMs, o: c - 0.0001 * base, h: c + 0.0004 * base, l: c - 0.0004 * base, c: c });
  }
  return out;
}

/* الگوی «روند صعودی + پولبک + برگشت» — ستاپ خریدِ EURUSD با دادهٔ قطعی */
function mkPullback(n, base, stepMs) {
  const cut1 = Math.floor(n * 0.84);
  const cut2 = Math.floor(n * 0.94);
  const out = [];
  let last = base;
  for (let i = 0; i < n; i++) {
    let step;
    if (i < cut1) step = 0.00055 * base;         // صعود پایدار
    else if (i < cut2) step = -0.0016 * base;    // پولبک (RSI ≈ ۴۰)
    else step = 0.00035 * base;                  // برگشت ملایم (rsi_rising)
    last = last + step + 0.00008 * base * ((i * 7) % 9 - 4);
    out.push({ t: T0 + i * stepMs, o: last - 0.0001 * base, h: last + 0.0004 * base, l: last - 0.0004 * base, c: last });
  }
  return out;
}

function makeMarketData(symbol) {
  const base = BASES[symbol] !== undefined ? BASES[symbol] : 1.0;
  if (symbol === 'EURUSD') {
    return { symbol: symbol, m15: mkPullback(260, base, STEP['15m']), h1: mkPullback(260, base, STEP['1h']), h4: mkPullback(260, base, STEP['4h']) };
  }
  return {
    symbol: symbol,
    m15: mkFrame(260, base, STEP['15m'], 0.00002 * base),
    h1: mkFrame(260, base, STEP['1h'], 0.00008 * base),
    h4: mkFrame(260, base, STEP['4h'], 0.0003 * base)
  };
}

function makeCalSnap(fixedNow) {
  // رویداد USD عمداً +۷ ساعت: بیرون پنجرهٔ وتو (۳۰ دقیقه) *و* بیرون پنجرهٔ
  // «تمیز» فاندامنتال (۶ ساعت) — همان منطق gen_engine_golden.py
  return {
    events: [
      { when: fixedNow + 7 * 3600e3, country: 'USD', title: 'Federal Funds Rate', title_fa: 'نرخ بهرهٔ فدرال', impact: 'HIGH', forecast: '4.00%', previous: '4.00%', category: 'نرخ بهره و بانک مرکزی', polarity: 1, source: 'golden' },
      { when: fixedNow + 20 * 3600e3, country: 'EUR', title: 'CPI y/y', title_fa: 'تورم سالانه (CPI)', impact: 'HIGH', forecast: '2.1%', previous: '2.0%', category: 'تورم و قیمت‌ها', polarity: 1, source: 'golden' }
    ],
    fetchedAt: fixedNow, fromCache: false, stale: false, fetched: true,
    error: '', ok: true, source: 'golden-harness', weekRange: ['2026-09-20', '2026-09-26']
  };
}

function makeNewsSnap(fixedNow, withBreaking) {
  const items = [
    { title: 'ECB officials signal further rate hike ahead', link: 'https://example.com/ecb', source: 'TestFeed', published: fixedNow - 3600e3, score: 6, direction: { EUR: 1 }, keywords: ['ecb', 'rate'], breaking: false, roundup: false, summary: '', age_minutes: 60 }
  ];
  if (withBreaking) {
    items.push({ title: 'BREAKING: ECB surprise decision', link: 'https://example.com/brk', source: 'GoldenBrk', published: fixedNow - 60e3, score: 6, direction: { EUR: -1 }, keywords: ['ecb'], breaking: true, roundup: false, summary: '', age_minutes: 1 });
  }
  return { items: items, fetchedAt: fixedNow, feedsOk: 1, feedsFailed: 0, staleFeeds: [], failedNames: [], rawCount: items.length, error: '', ok: items.length > 0 };
}

// ══════════════════════════════════════════════════════════════
//  هارنس — vm + FakeDate + ODINNative ساختگی + پچ fetcherها
// ══════════════════════════════════════════════════════════════
function makeFakeDate(fixedNow) {
  class FakeDate extends Date {
    constructor(...args) { if (args.length === 0) super(fixedNow); else super(...args); }
    static now() { return fixedNow; }
  }
  return FakeDate;
}

function createApp(opts) {
  opts = opts || {};
  const fixedNow = opts.fixedNow || FIXED_WED;
  const prefs = new Map();
  Object.keys(opts.prefs || {}).forEach((k) => prefs.set(k, String(opts.prefs[k])));
  const calls = { notify: [], ongoing: [], cycleDone: [], stopBg: 0 };
  const logs = [];
  const errs = [];
  const stubOpts = { outage: !!opts.outage, newsBreaking: false };

  const ctx = {
    console: {
      log: (...a) => logs.push(a.map(String).join(' ')),
      error: (...a) => errs.push(a.map(String).join(' ')),
      warn: (...a) => errs.push(a.map(String).join(' '))
    },
    setTimeout, clearTimeout, setInterval, clearInterval,
    fetch: () => Promise.reject(new Error('network blocked in golden harness')),
    TextDecoder, Promise, Date: makeFakeDate(fixedNow), Math, JSON,
    location: { search: '?svc=1' }
  };
  ctx.globalThis = ctx;
  ctx.ODINNative = {
    getPref: (k) => prefs.get(k) || '',
    setPref: (k, v) => prefs.set(k, String(v)),
    removePref: (k) => prefs.delete(k),
    getVersion: () => 'golden',
    notify: (t, b) => calls.notify.push([t, b]),
    notifyOngoing: (t, b) => calls.ongoing.push([t, b]),
    bgCycleDone: (m) => calls.cycleDone.push(m),
    stopBackground: () => { calls.stopBg++; },
    getDeviceId: () => DEVICE_ID
    // عمداً بدون http — fetcherها پچ شده‌اند و O.http هرگز صدا زده نمی‌شود
  };
  vm.createContext(ctx);
  for (const f of fileList()) {
    vm.runInContext(fs.readFileSync(path.join(WWW, f), 'utf8'), ctx, { filename: f });
  }
  const O = ctx.ODIN;

  // ── پچ seamها (فقط لایهٔ شبکه؛ پارس/تحلیل/داور/ژورنال واقعی‌اند) ──
  O.fetchYahooSymbol = function (symCfg) {
    if (stubOpts.outage) return Promise.resolve(null);
    return Promise.resolve(makeMarketData(symCfg.name));
  };
  O.fetchTvSnapshot = function () {
    return Promise.resolve({
      EURUSD: { symbol: 'EURUSD', close: BASES.EURUSD, recommendation: 'BUY', recommend_ma: 0.35, recommend_other: 0.28, buy: null, sell: null, neutral: null, timeframe: '4h' }
    });
  };
  const realCal = O.fetchCalendar;
  O.fetchCalendar = function (cfg, storage) {
    // مسیر «غیرفعال در تنظیمات» عمداً واقعی است — همان fallback فاز ۶
    if (cfg && cfg.fundamental && cfg.fundamental.enabled === false) return realCal(cfg, storage);
    return Promise.resolve(makeCalSnap(fixedNow));
  };
  const realNews = O.fetchNews;
  O.fetchNews = function (cfg, onLog) {
    if (cfg && cfg.news && cfg.news.enabled === false) return realNews(cfg, onLog);
    return Promise.resolve(makeNewsSnap(fixedNow, stubOpts.newsBreaking));
  };

  const pstorage = {
    get: (k) => prefs.get(k) || '',
    set: (k, v) => prefs.set(k, String(v)),
    del: (k) => prefs.delete(k)
  };
  return { O, ctx, prefs, pstorage, calls, logs, errs, stubOpts, fixedNow };
}

function waitCycle(calls, n, timeoutMs) {
  return new Promise((res, rej) => {
    const t0 = Date.now();
    const iv = setInterval(() => {
      if (calls.cycleDone.length >= n) { clearInterval(iv); res(); }
      else if (Date.now() - t0 > (timeoutMs || 15000)) {
        clearInterval(iv);
        rej(new Error('timeout waiting for cycleDone #' + n));
      }
    }, 15);
  });
}

// ══════════════════════════════════════════════════════════════
//  نرمال‌سازی ضبط (حجم کم، قطعی، قابل مقایسه)
// ══════════════════════════════════════════════════════════════
function summarizeState(raw) {
  let st;
  try { st = JSON.parse(raw); } catch (e) { return { parseError: String(e) }; }
  const judgments = (st.judgments || []).map((j) => ({
    symbol: j.symbol, direction: j.direction, score: j.score, max_score: j.max_score,
    reject_reason: j.reject_reason || '', hasSignal: !!j.signal,
    signal: j.signal ? { symbol: j.signal.symbol, direction: j.signal.direction, score: j.signal.score, stars: j.signal.stars, entry: j.signal.entry, sl: j.signal.sl, tp: j.signal.tp, risk_pips: j.signal.risk_pips, reward_pips: j.signal.reward_pips, rr: j.signal.rr, sl_capped: j.signal.sl_capped, evidences: j.signal.evidences.map((e) => e.key + ':' + e.points + '/' + e.max_points), warnings: j.signal.warnings } : null
  }));
  return {
    ranAt: st.ranAt, errors: st.errors, sourceName: st.sourceName,
    nAnalyses: (st.analyses || []).length,
    verdicts: (st.analyses || []).map((a) => a.symbol + '=' + a.verdict),
    ranking: st.ranking || [], tvCount: Object.keys(st.tvMap || {}).length, tvTf: st.tvTf,
    calOk: !!(st.calSnap && st.calSnap.ok), newsOk: !!(st.newsSnap && st.newsSnap.ok),
    nJudgments: judgments.length, judgments: judgments, resolvedCount: st.resolvedCount,
    sparkKeys: Object.keys(st.sparks || {}).sort()
  };
}

function normalizePref(key, val, O) {
  if (key === 'state.last') return summarizeState(val);
  if (key.indexOf('chart.') === 0) {
    try { return { bars: JSON.parse(val).length }; } catch (e) { return { bars: -1 }; }
  }
  if (key === 'journal.jsonl') {
    return String(val).split('\n').filter((l) => l.trim()).map((l) => {
      try {
        const r = JSON.parse(l);
        return { kind: r.kind || 'signal', id: r.id || '', symbol: r.symbol || '', direction: r.direction || '', sent: r.sent === undefined ? null : r.sent, score: r.score === undefined ? null : r.score, outcome: r.outcome || null };
      } catch (e) { return { kind: 'broken' }; }
    });
  }
  if (key === 'sent_signals.json' || key === 'alerts.json' || key === 'settings') {
    try { return JSON.parse(val); } catch (e) { return { parseError: String(e) }; }
  }
  if (key === 'trial.dat' || key === 'license.dat') {
    try {
      const t = JSON.parse(val);
      return { hasKey: !!t.license_key || !!t.start_ms || Object.keys(t).length > 0, keys: Object.keys(t).sort() };
    } catch (e) { return { parseError: String(e) }; }
  }
  return String(val).length > 200 ? String(val).slice(0, 200) + '…' : String(val);
}

function record(app) {
  const dump = {};
  const keys = Array.from(app.prefs.keys()).sort();
  keys.forEach((k) => { dump[k] = normalizePref(k, app.prefs.get(k), app.O); });
  let trial = null;
  try { trial = app.O.trialStatus(app.pstorage); } catch (e) { trial = null; }
  return {
    logs: app.logs.slice(),
    consoleErrors: app.errs.slice(),
    notify: app.calls.notify.map((x) => x.slice()),
    ongoing: app.calls.ongoing.map((x) => x.slice()),
    cycleDone: app.calls.cycleDone.slice(),
    stopBg: app.calls.stopBg,
    trial: trial ? { exists: !!trial.exists, active: !!trial.active, tampered: !!trial.tampered } : null,
    storage: dump
  };
}

// ══════════════════════════════════════════════════════════════
//  ۸ سناریو
// ══════════════════════════════════════════════════════════════
async function runScenario(name, busSink) {
  switch (name) {
    case 'svc_cycle_signals': {
      const app = createApp({});
      if (busSink) subscribeBus(app, busSink);
      app.O.trialStart(app.pstorage);
      app.O.svcStart();
      await waitCycle(app.calls, 1);
      return record(app);
    }
    case 'data_outage': {
      const app = createApp({ outage: true });
      if (busSink) subscribeBus(app, busSink);
      app.O.trialStart(app.pstorage);
      app.O.svcStart();
      await waitCycle(app.calls, 1);
      return record(app);
    }
    case 'duplicate_cooldown': {
      const app = createApp({});
      if (busSink) subscribeBus(app, busSink);
      app.O.trialStart(app.pstorage);
      app.O.svcStart();
      await waitCycle(app.calls, 1);
      app.O.svcTick();                       // چرخهٔ دوم با همان داده/زمان → تکراری
      await waitCycle(app.calls, 2);
      return record(app);
    }
    case 'alerts_fired': {
      const app = createApp({
        prefs: {
          'alerts.json': JSON.stringify([{
            id: 'EURUSD|below|1.25', symbol: 'EURUSD', dir: 'below', price: 1.25, pip: 0.0001,
            sticky: false, created_at: new Date(FIXED_WED).toISOString(), last_fired: null
          }])
        }
      });
      if (busSink) subscribeBus(app, busSink);
      app.O.trialStart(app.pstorage);
      app.O.svcStart();
      await waitCycle(app.calls, 1);
      return record(app);
    }
    case 'breaking_news': {
      const app = createApp({});
      if (busSink) subscribeBus(app, busSink);
      app.O.trialStart(app.pstorage);
      app.O.svcStart();
      await waitCycle(app.calls, 1);
      app.stubOpts.newsBreaking = true;      // چرخهٔ دوم: خبر فوری تازه
      app.O.svcTick();
      await waitCycle(app.calls, 2);
      return record(app);
    }
    case 'judge_disabled': {
      const app = createApp({ prefs: { settings: JSON.stringify({ judge_enabled: false }) } });
      if (busSink) subscribeBus(app, busSink);
      app.O.trialStart(app.pstorage);
      app.O.svcStart();
      await waitCycle(app.calls, 1);
      return record(app);
    }
    case 'features_disabled': {
      const app = createApp({
        prefs: { settings: JSON.stringify({ fund_enabled: false, news_enabled: false, tv_enabled: false }) }
      });
      if (busSink) subscribeBus(app, busSink);
      app.O.trialStart(app.pstorage);
      app.O.svcStart();
      await waitCycle(app.calls, 1);
      return record(app);
    }
    case 'market_closed': {
      const app = createApp({ fixedNow: FIXED_SAT });
      if (busSink) subscribeBus(app, busSink);
      app.O.trialStart(app.pstorage);
      app.O.svcStart();
      await waitCycle(app.calls, 1);
      return record(app);
    }
    default:
      throw new Error('سناریوی ناشناخته: ' + name);
  }
}

function subscribeBus(app, sink) {
  if (!app.O.BUS || typeof app.O.BUS.on !== 'function') return;   // قبل از سوییچ: BUS نیست
  const names = ['cycle.start', 'market.collected', 'fundamental.collected', 'journal.resolved',
    'judge.done', 'signal.created', 'signal.sent', 'alerts.fired', 'cycle.end', 'plugin.failed'];
  names.forEach((n) => app.O.BUS.on(n, (p) => sink.push([n, p && p.stage ? p.stage : null])));
}

const SCENARIOS = ['svc_cycle_signals', 'data_outage', 'duplicate_cooldown', 'alerts_fired',
  'breaking_news', 'judge_disabled', 'features_disabled', 'market_closed'];

async function runAllScenarios() {
  const out = {};
  for (const name of SCENARIOS) out[name] = await runScenario(name);
  return out;
}

// سریال‌سازی با کلیدهای مرتب (مقایسهٔ قطعی، مثل sort_keys پایتون)
function stableStringify(v) {
  if (v === null || typeof v !== 'object') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(stableStringify).join(',') + ']';
  return '{' + Object.keys(v).sort().map((k) => JSON.stringify(k) + ':' + stableStringify(v[k])).join(',') + '}';
}

async function main() {
  const battery = await runAllScenarios();
  fs.writeFileSync(GOLDEN_PATH, JSON.stringify(battery, null, 1) + '\n', 'utf8');
  console.log('✅ طلاییِ چرخهٔ سرویس ضبط شد — ' + path.basename(GOLDEN_PATH) + ': ' +
    SCENARIOS.length + ' سناریو (سیگنال/قطعی داده/تکراری/هشدار/خبر فوری/داور خاموش/فیچرها خاموش/بازار بسته)');
  return 0;
}

module.exports = {
  runAllScenarios, runScenario, createApp, record, SCENARIOS, fileList,
  stableStringify, GOLDEN_PATH, FIXED_WED, FIXED_SAT, BASES, makeMarketData, ROOT, WWW
};

if (require.main === module) {
  main().then((c) => process.exit(c), (e) => { console.error('❌ ' + (e && e.stack || e)); process.exit(1); });
}
