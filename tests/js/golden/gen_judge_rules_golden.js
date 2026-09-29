#!/usr/bin/env node
/* تولیدکنندهٔ طلاییِ قواعد داور JS — فاز ۶b (آینهٔ tests/golden/gen_judge_golden.py).
 *
 * انضباط «اول میخ، بعد چکش»:
 *   ۱) این اسکریپت باتری کامل سناریوهای داوری را با دادهٔ **ساختگیِ قطعی**
 *      و **بدون شبکه** روی judge.js *فعلی* (فقط API عمومیِ امروز:
 *      judgeSymbol/judgeAll/collectVetoes/computeLevels) اجرا می‌کند و
 *      نتیجه را در tests/js/golden/judge_rules_js_golden.json ضبط می‌کند.
 *   ۲) tests/js/test_judge_switch.js همان باتری را تکرار و با طلایی مقایسه
 *      می‌کند. بعد از سوییچِ ۶b (استخراج ۷ وتو + export شاهدها +
 *      rule-pluginها در plugins.js) باید **بدون هیچ تغییری** سبز بماند —
 *      یعنی ترتیب/آستانه‌ها/متن‌های فارسی بایت‌به‌بایت حفظ شده‌اند.
 *
 * سناریوها عمداً آینهٔ باتری پایتون‌اند (gen_judge_golden.py) — چون parity
 * دو موتور با run_parity اثبات شده، خروجی‌های متناظر باید یکی باشند؛ این
 * طلایی، حفظِ همان خروجی‌ها را در طول ریفکتور ۶b تضمین می‌کند.
 *
 * buildBattery(O, opts): opts.judgeSymbolFn/opts.judgeAllFn تزریق *اختیاری*
 * مسیر داوری است (پیش‌فرض = توابع مستقیم O.*) — test_judge_switch با تزریقِ
 * مسیر rule-plugin (JudgeAdapter + registry) همان باتری را اجرا می‌کند و
 * خروجی باید بایت‌به‌بایت با همین طلایی یکی باشد.
 *
 * اجرا (برای ضبط/بازتولید عمدیِ طلایی — فقط با دلیل موجه):
 *   node tests/js/golden/gen_judge_rules_golden.js
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HERE = __dirname;
const ROOT = path.resolve(HERE, '..', '..', '..');
const WWW = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www', 'js');
const GOLDEN_PATH = path.join(HERE, 'judge_rules_js_golden.json');

// فقط ماژول‌های لازم (بدون DOM/app) — core/plugins اگر حاضر باشند اول بار
// می‌شوند (بعد از سوییچ) تا هارنس قبل/بعد از سوییچ بدون تغییر معتبر باشد
function fileList() {
  const base = ['md5.js', 'fa.js', 'icons.js', 'license.js', 'config.js',
    'indicators.js', 'session.js', 'technical.js', 'calendar.js', 'news.js', 'judge.js',
    'strategies.js',   // S3: دروازهٔ توافق، استراتژی‌ها را در VM لازم دارد
    // v0.29 (فاز ۴): journal.js هم لازم است — testJournalRecordSchema
    // رفت‌وبرگشتِ واقعیِ رکورد را از O.Journal می‌سنجد و O.entryRules/
    // JOURNAL_RULES_VERSION را مقایسه می‌کند. افزودنش فقط کلیدهای تازه به
    // O می‌چسباند؛ رفتارِ داور را عوض نمی‌کند (با diffِ طلایی راستی‌آزمایی شد).
    'journal.js'];
  const pre = ['core.js', 'plugins.js'].filter((f) => fs.existsSync(path.join(WWW, f)));
  return pre.concat(base);
}

function createVm() {
  const ctx = { console, Date, Math, JSON };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  for (const f of fileList()) {
    vm.runInContext(fs.readFileSync(path.join(WWW, f), 'utf8'), ctx, { filename: f });
  }
  return ctx.ODIN;
}

// لحظه‌های ثابت (۲۰۲۶-۰۹-۲۳ چهارشنبه / ۲۰۲۶-۰۹-۱۹ شنبه)
const FIXED_WED = Date.UTC(2026, 8, 23, 14, 0, 0);   // هم‌پوشانی لندن/NY
const WED_LONDON = Date.UTC(2026, 8, 23, 8, 0, 0);   // فقط لندن (نقدشونده)
const WED_THIN = Date.UTC(2026, 8, 23, 3, 0, 0);     // توکیو/سیدنی (کم‌نقدینگی)
const FIXED_SAT = Date.UTC(2026, 8, 19, 12, 0, 0);   // شنبه — بازار بسته

const RANK_DEFAULT = [['EUR', 0.30], ['GBP', 0.10], ['USD', -0.20], ['JPY', -0.40]];
const RANK_USD_STRONG = [['USD', 0.30], ['GBP', 0.10], ['EUR', -0.20], ['JPY', -0.40]];

// ══════════════════════════════════════════════════════════════
//  سازنده‌های دادهٔ ساختگیِ قطعی
// ══════════════════════════════════════════════════════════════
function makeAnalysis(over) {
  const a = {
    symbol: 'EURUSD', fa_name: 'یورو به دلار آمریکا', base: 'EUR', quote: 'USD',
    price: 1.1490, pip: 0.0001, trend: 'bullish', h1_agrees: true, adx: 32.0,
    rsi: 38.0, rsi_rising: true, atr: 0.0010, support: 1.1486, resistance: 1.1560,
    last_candle: FIXED_WED, verdict: 'BUY_SETUP'
  };
  Object.keys(over || {}).forEach((k) => { a[k] = over[k]; });
  return a;
}

function makeSellAnalysis(over) {
  return makeAnalysis(Object.assign({
    trend: 'bearish', rsi: 62.0, rsi_rising: false, verdict: 'SELL_SETUP',
    support: 1.1400, resistance: 1.1494
  }, over || {}));
}

/* کندل‌های H1 قطعی (زیگزاگ) — برای وتوی VOL_SPIKE با spike انتهایی */
function makeH1(n, base, atr, spikeLast, lastDir) {
  const t0 = Date.UTC(2026, 7, 1);
  const out = [];
  for (let i = 0; i < n; i++) {
    const c = base + 0.00002 * base * i + 0.00012 * base * ((i * 7) % 11 - 5);
    let h = c + 0.4 * atr, l = c - 0.4 * atr;
    if (spikeLast && i === n - 1) { h = c + 30 * atr; l = c - 30 * atr; }
    // S3: جهتِ کندل آخر برای تأییدِ ادامهٔ trend_pullback باید *قطعی* باشد.
    // Open در TR/ATR نقشی ندارد → بقیهٔ سناریوها بایت‌به‌بایت دست‌نخورده.
    // پیش‌فرض 'bull' (آینهٔ seed-7 پایتون که کندل آخرش صعودی از آب درآمد).
    let o = c;
    if (i === n - 1 && lastDir !== 'none') {
      o = (lastDir === 'bear') ? c + 0.5 * atr : c - 0.5 * atr;
    }
    out.push({ t: t0 + i * 3600e3, o: o, h: h, l: l, c: c });
  }
  return out;
}

function makeMd(O, symbol, spike, lastDir) {
  const base = symbol === 'EURUSD' ? 1.1490 : 1.0;
  return { symbol: symbol, m15: [], h4: [], h1: makeH1(300, base, 0.0010, !!spike, lastDir) };
}

function ev(whenMs, country, title, titleFa, impact) {
  return {
    when: whenMs, country: country, title: title, title_fa: titleFa,
    impact: impact, forecast: '', previous: '', category: '', polarity: 0, source: 'golden'
  };
}

function snapOf(events, ok, error) {
  return {
    events: events, ok: ok !== false, fetched: ok !== false, fromCache: false,
    stale: false, error: error || '', fetchedAt: FIXED_WED,
    source: 'golden-harness', weekRange: ['2026-09-20', '2026-09-26']
  };
}

const cleanCal = () => snapOf([ev(FIXED_WED + 4 * 86400e3, 'USD', 'CPI y/y', 'تورم سالانه', 'HIGH')]);
const nearCal = (nowMs) => snapOf([ev(nowMs + 12 * 60e3, 'USD', 'Federal Funds Rate', 'نرخ بهره فدرال رزرو', 'HIGH')]);
const highSoonCal = (nowMs) => snapOf([ev(nowMs + 2 * 3600e3, 'USD', 'CPI y/y', 'تورم سالانه', 'HIGH')]);
const medSoonCal = (nowMs) => snapOf([ev(nowMs + 3600e3, 'USD', 'Core Retail Sales m/m', 'خرده‌فروشی هسته', 'MEDIUM')]);
const failedCal = () => snapOf([], false, 'خطای شبکه در دریافت تقویم');

function newsItem(title, score, direction, breaking, source) {
  return {
    title: title, link: 'https://example.com/' + encodeURIComponent(title.slice(0, 12)),
    source: source || 'TestFeed', published: FIXED_WED - 3600e3, score: score,
    direction: direction, keywords: [], breaking: !!breaking, roundup: false,
    summary: '', age_minutes: 60
  };
}
function newsSnap(items) {
  return {
    items: items, fetchedAt: FIXED_WED, feedsOk: 1, feedsFailed: 0,
    staleFeeds: [], failedNames: [], rawCount: items.length, error: '',
    ok: items.length > 0
  };
}
const goodNews = () => newsSnap([
  newsItem('Euro rallies as ECB turns hawkish', 5, { EUR: 1, USD: -1 }),
  newsItem('Dollar slides on soft US data', 5, { USD: -1 }, false, 'ForexLive')
]);
const sellNews = () => newsSnap([newsItem('Dollar rallies as Fed turns hawkish', 5, { EUR: -1, USD: 1 })]);
const contraNews = () => newsSnap([newsItem('Euro falls as ECB signals rate cuts', 5, { EUR: -1, USD: 1 })]);
const neutralNews = () => newsSnap([newsItem('RBA holds rates steady', 5, { AUD: 1 })]);
const breakingNews = () => newsSnap([
  newsItem('BREAKING: ECB surprise decision', 6, { EUR: -1, USD: 1 }, true, 'ForexLive')
]);

const TV_BUY = { EURUSD: { symbol: 'EURUSD', close: 1.149, recommendation: 'BUY', recommend_ma: null, recommend_other: null, buy: 13, sell: 4, neutral: 9, timeframe: '4h' } };
const TV_SELL = { EURUSD: { symbol: 'EURUSD', close: 1.149, recommendation: 'SELL', recommend_ma: null, recommend_other: null, buy: 4, sell: 13, neutral: 9, timeframe: '4h' } };
const TV_NEUTRAL = { EURUSD: { symbol: 'EURUSD', close: 1.149, recommendation: 'NEUTRAL', recommend_ma: null, recommend_other: null, buy: 6, sell: 6, neutral: 13, timeframe: '4h' } };

function makeCtx(O, over) {
  over = over || {};
  const jcfg = JSON.parse(JSON.stringify(O.CONFIG.judge));
  Object.keys(over.jcfg || {}).forEach((k) => { jcfg[k] = over.jcfg[k]; });
  const nowMs = over.nowMs !== undefined ? over.nowMs : FIXED_WED;
  return {
    jcfg: jcfg,
    acfg: O.CONFIG.analysis,
    symbolsCfg: O.CONFIG.symbols,
    ranking: over.ranking !== undefined ? over.ranking : RANK_DEFAULT,
    tvMap: over.tvMap !== undefined ? over.tvMap : TV_BUY,
    calSnap: over.calSnap !== undefined ? over.calSnap : cleanCal(),
    newsSnap: over.newsSnap !== undefined ? over.newsSnap : goodNews(),
    nowMs: nowMs,
    status: O.marketStatus(new Date(nowMs)),
    eventVetoMinutes: 30,
    // S3: دروازهٔ توافق min_agree را از اینجا می‌خواند (آینهٔ make_ctx پایتون)
    strategiesCfg: over.strategiesCfg !== undefined ? over.strategiesCfg : O.CONFIG.strategies
  };
}

// ══════════════════════════════════════════════════════════════
//  سریال‌سازی (آینهٔ judgment_dump در gen_judge_golden.py)
// ══════════════════════════════════════════════════════════════
function evidenceDump(e) {
  return {
    key: e.key, label_fa: e.label_fa, points: e.points, max_points: e.max_points,
    detail_fa: e.detail_fa, ok: e.ok, unavailable: e.unavailable, icon: e.icon
  };
}
function vetoDump(v) { return { key: v.key, title_fa: v.title_fa, detail_fa: v.detail_fa }; }
function signalDump(O, s) {
  return {
    symbol: s.symbol, fa_name: s.fa_name, direction: s.direction, sid: s.sid,
    score: s.score, max_score: s.max_score, stars: s.stars,
    entry: s.entry, sl: s.sl, tp: s.tp, pip: s.pip, atr: s.atr,
    risk_pips: s.risk_pips, reward_pips: s.reward_pips, rr: s.rr,
    is_gold: s.is_gold, session_fa: s.session_fa, now: s.now,
    warnings: s.warnings, sl_capped: s.sl_capped,
    evidences: s.evidences.map((e) => e.key + ':' + e.points + '/' + e.max_points),
    strategies: s.strategies,
    journal: O.signalToJournal(s, true)
  };
}
function judgmentDump(O, j) {
  return {
    symbol: j.symbol, fa_name: j.fa_name, direction: j.direction,
    score: j.score, max_score: j.max_score,
    reject_reason: j.reject_reason, reject_detail: j.reject_detail,
    status_fa: O.judgmentStatusFa(j), price: j.price, pip: j.pip,
    vetoes: j.vetoes.map(vetoDump),
    evidences: j.evidences.map(evidenceDump),
    warnings: j.warnings,
    strategies: j.strategies,
    signal: j.signal ? signalDump(O, j.signal) : null
  };
}

// ══════════════════════════════════════════════════════════════
//  باتری سناریوها
// ══════════════════════════════════════════════════════════════
/* S3: قواعد استراتژیِ پیش‌فرضِ باتری — نمونه‌های واقعیِ registry
 * (strategy-* adapters با scfg از O.CONFIG) = آینهٔ DEFAULT_STRATEGY_RULES
 * پایتون (StrategyAdapter با config.yaml؛ هم‌مقداریِ config.js با config.yaml
 * در test_strategies_switch پین شده). طلایی با این قواعد ضبط می‌شود چون
 * مسیر production (JudgeAdapter + registry) همیشه آن‌ها را تزریق می‌کند. */
function defaultStrategyRules(O) {
  const built = O.buildDefaultRegistry(JSON.parse(JSON.stringify(O.CONFIG)), 'android');
  return built.registry.providers('odin.strategy@1').map((rec) =>
    (rec.instance !== null && rec.instance !== undefined) ? rec.instance : rec.factory(built.info.context));
}

function buildBattery(O, opts) {
  opts = opts || {};
  const strategyRules = opts.strategyRules !== undefined
    ? opts.strategyRules : defaultStrategyRules(O);
  const jfn = opts.judgeSymbolFn || function (a, symCfg, md, ctx) {
    return O.judgeSymbol(a, symCfg, md, ctx, undefined, undefined, undefined, strategyRules);
  };
  const jall = opts.judgeAllFn || function (list, datasets, ctx) {
    return O.judgeAll(list, datasets, ctx, undefined, undefined, undefined, strategyRules);
  };

  // rulesOverride: برای سناریوهای strategy_gate که قواعدِ صریحِ خودشون را
  // دارند (شکسته/خالی/تک) — undefined = همان strategyRules باتری
  const judge = (a, md, ctx, rulesOverride) => {
    if (rulesOverride !== undefined) {
      return judgmentDump(O, O.judgeSymbol(a, {},
        md === undefined ? makeMd(O, a.symbol) : md, ctx || makeCtx(O),
        undefined, undefined, undefined, rulesOverride));
    }
    return judgmentDump(O, jfn(a, {}, md === undefined ? makeMd(O, a.symbol) : md, ctx || makeCtx(O)));
  };
  const bat = {};

  // ── وتوها: شلیک تکی ──
  bat.veto_single = {
    DATA: judge(makeAnalysis({ verdict: 'DATA' })),
    WEEKEND: judge(makeAnalysis(), undefined, makeCtx(O, { nowMs: FIXED_SAT })),
    TF_CONFLICT: judge(makeAnalysis({ h1_agrees: false })),
    RANGE: judge(makeAnalysis({ adx: 14.0 })),
    EVENT: judge(makeAnalysis(), undefined, makeCtx(O, { calSnap: nearCal(FIXED_WED) })),
    VOL_SPIKE: judge(makeAnalysis(), makeMd(O, 'EURUSD', true)),
    BREAKING_NEWS: judge(makeAnalysis(), undefined, makeCtx(O, { newsSnap: breakingNews() }))
  };

  // ── وتوها: چندتای هم‌زمان (ترتیب ارزیابی) ──
  const spiky = makeMd(O, 'EURUSD', true);
  bat.veto_multi = {
    all_except_data: judge(makeAnalysis({ h1_agrees: false, adx: 14.0 }), spiky,
      makeCtx(O, { nowMs: FIXED_SAT, calSnap: nearCal(FIXED_SAT), newsSnap: breakingNews() })),
    with_data: judge(makeAnalysis({ verdict: 'DATA', h1_agrees: false, adx: 14.0 }), spiky,
      makeCtx(O, { nowMs: FIXED_SAT, calSnap: nearCal(FIXED_SAT), newsSnap: breakingNews() }))
  };

  // ── وتوها: کلیدهای *موجود* config (guardهای درون بدنه) ──
  bat.veto_toggles = {
    weekend_off_saturday: judge(makeAnalysis(), undefined,
      makeCtx(O, { nowMs: FIXED_SAT, jcfg: { veto: Object.assign(JSON.parse(JSON.stringify(O.CONFIG.judge.veto)), { weekend: false }) } })),
    range_off_low_adx: judge(makeAnalysis({ adx: 14.0 }), undefined,
      makeCtx(O, { jcfg: { veto: Object.assign(JSON.parse(JSON.stringify(O.CONFIG.judge.veto)), { range_market: false }) } }))
  };

  // ── ستاپ سالم: بدون وتو ──
  bat.veto_clean = O.collectVetoes(makeAnalysis(), {}, makeMd(O, 'EURUSD'), makeCtx(O)).map(vetoDump);

  // ── داوری کامل BUY / SELL ──
  // S3: کندل آخرِ قطعی — bull برای BUY و bear برای SELL تا trend_pullback
  // توافق کند و intentِ «سیگنال کامل ۱۱/۱۱» preserved بماند (آینهٔ پایتون)
  bat.judge_full = {
    buy: judge(makeAnalysis(), makeMd(O, 'EURUSD', false, 'bull')),
    sell: judge(makeSellAnalysis(), makeMd(O, 'EURUSD', false, 'bear'),
      makeCtx(O, { ranking: RANK_USD_STRONG, tvMap: TV_SELL, newsSnap: sellNews() }))
  };

  // ── LOW_SCORE + هشدارهای ⚠️ ──
  bat.judge_low_score = {
    low_score: judge(makeAnalysis({ rsi: 55.0, support: 1.1400 }), undefined,
      makeCtx(O, { ranking: RANK_USD_STRONG, tvMap: TV_SELL, newsSnap: contraNews() }))
  };

  // ── NO_SETUP: هر ۵ دلیل ──
  const vOff = (k) => ({ veto: Object.assign(JSON.parse(JSON.stringify(O.CONFIG.judge.veto)), { [k]: false }) });
  bat.judge_no_setup = {
    trend_none: judge(makeAnalysis({ trend: 'none', verdict: 'WAIT' })),
    h1_disagree: judge(makeAnalysis({ h1_agrees: false, verdict: 'WAIT' }), undefined, makeCtx(O, { jcfg: vOff('timeframe_conflict') })),
    range_no_veto: judge(makeAnalysis({ adx: 14.0, verdict: 'WAIT' }), undefined, makeCtx(O, { jcfg: vOff('range_market') })),
    bullish_rsi_high: judge(makeAnalysis({ rsi: 55.0, verdict: 'WAIT' })),
    bearish_rsi_low: judge(makeAnalysis({ trend: 'bearish', rsi: 40.0, verdict: 'WAIT' }))
  };

  // ── شاهدها: همهٔ شاخه‌ها از راه داوری کامل (API عمومیِ امروز) ──
  const S = (over, ctxOver) => judge(makeSellAnalysis(over), undefined,
    makeCtx(O, Object.assign({ ranking: RANK_USD_STRONG, tvMap: TV_SELL, newsSnap: sellNews() }, ctxOver || {})));
  bat.evidence_judgments = {
    trend_medium: judge(makeAnalysis({ adx: 22.0 })),
    level_buy_near: judge(makeAnalysis({ support: 1.1480 })),
    level_buy_far: judge(makeAnalysis({ support: 1.1400 })),
    level_buy_unavailable: judge(makeAnalysis({ support: null })),
    level_sell_close: S({}),
    fund_high_soon: judge(makeAnalysis(), undefined, makeCtx(O, { calSnap: highSoonCal(FIXED_WED) })),
    fund_med_soon: judge(makeAnalysis(), undefined, makeCtx(O, { calSnap: medSoonCal(FIXED_WED) })),
    fund_cal_failed: judge(makeAnalysis(), undefined, makeCtx(O, { calSnap: failedCal() })),
    fund_cal_off: judge(makeAnalysis(), undefined, makeCtx(O, { calSnap: null })),
    mom_buy_oversold: judge(makeAnalysis({ rsi: 25.0 })),
    mom_buy_high: judge(makeAnalysis({ rsi: 55.0 })),
    mom_buy_not_rising: judge(makeAnalysis({ rsi_rising: false })),
    mom_sell_confirm: S({}),
    mom_sell_overbought: S({ rsi: 75.0 }),
    mom_sell_low: S({ rsi: 45.0 }),
    str_buy_contra: judge(makeAnalysis(), undefined, makeCtx(O, { ranking: RANK_USD_STRONG })),
    str_sell_aligned: S({}),
    str_empty: judge(makeAnalysis(), undefined, makeCtx(O, { ranking: [] })),
    str_missing: judge(makeAnalysis(), undefined, makeCtx(O, { ranking: [['GBP', 0.1], ['USD', -0.2]] })),
    news_supports_sell: S({}),
    news_contra: judge(makeAnalysis(), undefined, makeCtx(O, { newsSnap: contraNews() })),
    news_neutral: judge(makeAnalysis(), undefined, makeCtx(O, { newsSnap: neutralNews() })),
    news_unavailable: judge(makeAnalysis(), undefined, makeCtx(O, { newsSnap: null })),
    tv_match_sell: S({}),
    tv_neutral: judge(makeAnalysis(), undefined, makeCtx(O, { tvMap: TV_NEUTRAL })),
    tv_opposite: judge(makeAnalysis(), undefined, makeCtx(O, { tvMap: TV_SELL })),
    tv_unavailable: judge(makeAnalysis(), undefined, makeCtx(O, { tvMap: {} })),
    sess_overlap: judge(makeAnalysis()),
    sess_liquid: judge(makeAnalysis(), undefined, makeCtx(O, { nowMs: WED_LONDON })),
    sess_thin: judge(makeAnalysis(), undefined, makeCtx(O, { nowMs: WED_THIN })),
    sess_closed: judge(makeAnalysis(), undefined,
      makeCtx(O, { nowMs: FIXED_SAT, jcfg: vOff('weekend') }))
  };

  // ── CAPPED: سه سیگنال آماده، سقف ۱ ──
  // S3: datasets دیگر خالی نیست (دروازه به کندل H1 نیاز دارد) و a3
  // rsi=38 گرفت (منطقهٔ tp) — امتیازش ۸→۹؛ ترتیب cap (۱۱>۱۰>۹) preserved
  {
    const a1 = makeAnalysis();
    const a2 = makeAnalysis({ symbol: 'GBPUSD', fa_name: 'پوند به دلار آمریکا', base: 'GBP', quote: 'USD', price: 1.3500, support: 1.3496, resistance: 1.3560 });
    const a3 = makeAnalysis({ symbol: 'USDJPY', fa_name: 'دلار به ین ژاپن', base: 'USD', quote: 'JPY', price: 150.00, pip: 0.01, atr: 0.10, support: 149.96, resistance: 150.60, rsi: 38.0 });
    const datasets = {
      EURUSD: makeMd(O, 'EURUSD', false, 'bull'),
      GBPUSD: makeMd(O, 'GBPUSD', false, 'bull'),
      USDJPY: makeMd(O, 'USDJPY', false, 'bull')
    };
    const ctx = makeCtx(O, { jcfg: { max_signals_per_cycle: 1 } });
    bat.judge_capped = jall([a1, a2, a3], datasets, ctx).map((j) => judgmentDump(O, j));
  }

  // ── judgeAll: ۴ نماد در ۴ سرنوشت ──
  {
    const a1 = makeAnalysis();
    const a2 = makeAnalysis({ symbol: 'GBPUSD', fa_name: 'پوند به دلار آمریکا', base: 'GBP', quote: 'USD', price: 1.3500, adx: 14.0, support: 1.3496, resistance: 1.3560 });
    const a3 = makeAnalysis({ symbol: 'USDJPY', fa_name: 'دلار به ین ژاپن', base: 'USD', quote: 'JPY', price: 150.00, pip: 0.01, atr: 0.10, trend: 'none', verdict: 'WAIT', support: 149.96, resistance: 150.60 });
    const a4 = makeAnalysis({ symbol: 'AUDUSD', fa_name: 'دلار استرالیا به دلار آمریکا', base: 'AUD', quote: 'USD', price: 0.6600, rsi: 55.0, support: 0.6500, resistance: 0.6700 });
    // S3: فقط a1 (سیگنال) به md نیاز دارد — بقیه پیش از دروازه رد می‌شوند
    bat.judge_all_mixed = jall([a1, a2, a3, a4],
      { EURUSD: makeMd(O, 'EURUSD', false, 'bull') },
      makeCtx(O, { newsSnap: null })).map((j) => judgmentDump(O, j));
  }

  // ── S3: دروازهٔ توافق استراتژی‌ها — آینهٔ battery_strategy_gate پایتون ──
  // (همه با judgeSymbol مستقیم و قواعدِ صریح — موضوعِ خودِ دروازه است)
  {
    const ThrowingRule = { key: 'trend_pullback', evaluate: function () { throw new Error('boom'); } };
    const builtG = O.buildDefaultRegistry(JSON.parse(JSON.stringify(O.CONFIG)), 'android');
    const tpInst = builtG.registry.byId('strategy-trend-pullback').factory(builtG.info.context);
    const mdBull = makeMd(O, 'EURUSD', false, 'bull');
    const scfgWith = (over) => Object.assign(JSON.parse(JSON.stringify(O.CONFIG.strategies)), over);

    bat.strategy_gate = {
      // ۱) امتیاز ≥ ۷ ولی RSI=25 زیر منطقهٔ tp → صفر هم‌جهت → NO_STRATEGY
      no_agreement: judge(makeAnalysis({ rsi: 25.0 }), mdBull),
      // ۲) تنها-carry (proposes=false) → n_prop=0 → رد (پینِ D1=R2)
      carry_only: judge(
        makeAnalysis({ symbol: 'USDJPY', fa_name: 'دلار به ین ژاپن', base: 'USD',
          quote: 'JPY', price: 150.00, pip: 0.01, atr: 0.10,
          support: 149.96, resistance: 150.60, rsi: 25.0 }),
        makeMd(O, 'USDJPY', false, 'bull'),
        makeCtx(O, { newsSnap: null, tvMap: {} })),
      // ۳) min_agree=2 از ctx.strategiesCfg
      min_agree_2: judge(makeAnalysis(), mdBull,
        makeCtx(O, { strategiesCfg: scfgWith({ min_agree: 2 }) })),
      // ۴) فهرست خالی → fail-closed صادقانه (D3)
      fail_closed_empty: judge(makeAnalysis(), mdBull, undefined, []),
      // ۵) قاعدهٔ خطاداده + tp سالم → placeholder صادقانه، سیگنال برقرار
      broken_rule_isolated: judge(makeAnalysis(), mdBull, undefined,
        [ThrowingRule, tpInst]),
      // ۶) فقط خطاداده → هیچ نظر واقعی نیست → رد
      broken_rule_only: judge(makeAnalysis(), mdBull, undefined, [ThrowingRule]),
      // ۷) opt-out: min_agree=0 → دروازه خاموش، ارزیابی صادقانه باقی است
      opt_out_min_agree_0: judge(makeAnalysis({ rsi: 25.0 }), mdBull,
        makeCtx(O, { strategiesCfg: scfgWith({ min_agree: 0 }) })),
      // ۸) مسیر سالم — سیگنال با strategies پر
      pass_full: judge(makeAnalysis(), mdBull)
    };
  }

  // ── ریاضی SL/TP (۶ حالت — آینهٔ باتری پایتون) ──
  bat.risk_math = {};
  const rc = O.CONFIG.judge.risk;
  const cases = {
    buy_level: ['BUY', 1.1490, 0.0010, 1.1486, 1.1560],
    sell_level: ['SELL', 1.1490, 0.0010, 1.1440, 1.1495],
    buy_no_level: ['BUY', 1.1490, 0.0010, null, null],
    buy_far_capped: ['BUY', 1.1490, 0.0010, 1.1400, null],
    buy_tight_floor: ['BUY', 1.1490, 0.0010, 1.14895, null],
    atr_zero_guard: ['BUY', 1.1490, 0.0, 1.1486, 1.1560]
  };
  Object.keys(cases).forEach((name) => {
    const lv = O.computeLevels.apply(null, cases[name].concat([rc]));
    bat.risk_math[name] = { sl: lv.sl, tp: lv.tp, risk: lv.risk, capped: lv.capped };
  });

  return bat;
}

// سریال‌سازی با کلیدهای مرتب (مقایسهٔ قطعی — مثل sort_keys پایتون)
function stableStringify(v) {
  if (v === null || typeof v !== 'object') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(stableStringify).join(',') + ']';
  return '{' + Object.keys(v).sort().map((k) => JSON.stringify(k) + ':' + stableStringify(v[k])).join(',') + '}';
}

function main() {
  const O = createVm();
  const battery = buildBattery(O);
  fs.writeFileSync(GOLDEN_PATH, JSON.stringify(battery, null, 1) + '\n', 'utf8');
  const n = Object.keys(battery.veto_single).length + Object.keys(battery.veto_multi).length
    + Object.keys(battery.veto_toggles).length + 1 + Object.keys(battery.evidence_judgments).length
    + Object.keys(battery.judge_full).length + Object.keys(battery.judge_low_score).length
    + Object.keys(battery.judge_no_setup).length + battery.judge_capped.length
    + battery.judge_all_mixed.length;
  console.log('✅ طلاییِ قواعد داور JS ضبط شد — ' + path.basename(GOLDEN_PATH) + ': '
    + n + ' سناریوی داوری + ' + Object.keys(battery.strategy_gate).length
    + ' دروازهٔ استراتژی (S3) + ' + Object.keys(battery.risk_math).length + ' حالت ریاضی ریسک');
  return 0;
}

module.exports = {
  createVm, buildBattery, stableStringify, fileList, GOLDEN_PATH,
  defaultStrategyRules,
  FIXED_WED, FIXED_SAT, WED_LONDON, WED_THIN,
  makeAnalysis, makeSellAnalysis, makeMd, makeCtx,
  cleanCal, nearCal, highSoonCal, medSoonCal, failedCal,
  goodNews, sellNews, contraNews, neutralNews, breakingNews,
  TV_BUY, TV_SELL, TV_NEUTRAL, RANK_DEFAULT, RANK_USD_STRONG,
  judgmentDump, WWW, ROOT
};

if (require.main === module) process.exit(main());
