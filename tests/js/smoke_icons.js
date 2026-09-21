/* اسموک‌تست سامانهٔ آیکون (v0.13.0) — بدون DOM، مثل smoke_about.
 *
 * دو بخش:
 *  ۱) رشته‌های موتور (TREND_FA/IMPACT_FA/OUTCOME_FA/وتوها/بریفینگ) بعد از
 *     O.icoStr هیچ ایموجی باقی نماند.
 *  ۲) هر ۸ صفحه با دادهٔ مصنوعی رندر شود — خروجی هیچ‌کدام ایموجی نداشته
 *     باشد و همه SVG داشته باشند.
 *
 * اجرا: node tests/js/smoke_icons.js  (از ریشهٔ مخزن) */
'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');

const WWW = path.join(__dirname, '..', '..', 'android', 'app', 'src', 'main', 'assets', 'www', 'js');
const ctx = { console };
ctx.globalThis = ctx;
vm.createContext(ctx);
for (const f of ['md5.js', 'fa.js', 'icons.js', 'config.js', 'indicators.js', 'session.js',
  'technical.js', 'calendar.js', 'news.js', 'judge.js', 'journal.js', 'data.js', 'alerts.js', 'chart.js',
  'briefing.js', 'ui.js']) {
  vm.runInContext(fs.readFileSync(path.join(WWW, f), 'utf8'), ctx, { filename: f });
}
const O = ctx.ODIN;

const EMOJI = O.EMOJI_RE;
function noEmoji(html, where) {
  const m = EMOJI.exec(String(html));
  assert(!m, `emoji left in ${where}: ${JSON.stringify(m && m[0])} @${m && m.index}`);
}
function hasSvg(html, where) {
  assert(String(html).includes('<svg'), `no svg icon in ${where}`);
}

// ── ۱) نقشهٔ ایموجی روی رشته‌های واقعی موتور ─────────────────
const engineStrings = [
  ...Object.values(O.TREND_FA),
  ...Object.values(O.VERDICT_FA),
  ...Object.values(O.IMPACT_FA),
  ...Object.values(O.IMPACT_EMOJI),
  ...Object.values(O.OUTCOME_FA),
  'شنبه — بازار فارکس بسته است 🔒',
  'بازار بسته 🔒',
  '✅ سیگنال صادر شد', '🚫 وتو شد', '⏳ امتیاز ناکافی', '❔ ستاپی شکل نگرفته',
  '⚠️ دادهٔ ناکافی', '🔒 بازار بسته است', '🔀 تضاد جهت بین تایم‌فریم‌ها',
  '😴 بازار بی‌روند (رنج)', '📅 رویداد پراثر تقویم', '📈 جهش غیرعادی نوسان',
  '🚨 خبر فوری', '🌅 بریفینگ صبحگاهی', '🕒 ۰۸:۰۰ به وقت تهران | منبع داده: Yahoo Finance',
  '  ✅ رویداد پراثر یا متوسطی در ۲۴ ساعت آینده نیست — روز آرامی برای معامله است',
  '  ⛔ ورود ممنوع: ۱۶:۰۰ تا ۱۷:۰۰ (تهران) → نمادهای متاثر: EURUSD',
  '  🟢 EURUSD: روند صعودی 📈 | ADX ۲۸ | RSI ۵۵ | قیمت 1.1700',
  '  💡 ایده: قوی‌ترین (USD) در برابر ضعیف‌ترین (JPY) — هم‌جهت با جریان پول',
  'EUR ↑ · JPY ↓', '⭐⭐⭐'
];
for (const s of engineStrings) {
  noEmoji(O.icoStr(s), 'icoStr(' + s.slice(0, 30) + ')');
  if (/[\u{1F300}-\u{1FAFF}]/u.test(s)) hasSvg(O.icoStr(s), 'icoStr svg for: ' + s.slice(0, 30));
}

// ── ۲) رندر هر ۸ صفحه با دادهٔ مصنوعی ─────────────────────────
const nowMs = Date.now();
const settings = {
  user_name: 'تست', judge_enabled: true, min_score: 7,
  veto: { weekend: true, high_impact_event: true, timeframe_conflict: true, range_market: true, volatility_spike: true, breaking_news: true },
  fund_enabled: true, news_enabled: true, tv_enabled: true,
  auto_refresh_enabled: true, auto_refresh_min: 15, notify_enabled: true,
  background_enabled: true
};
const cfg = O.deepFill(O.CONFIG, {
  ui: { user_name: settings.user_name },
  judge: { enabled: true, min_score: 7, veto: settings.veto }
});

function ev(key, label, pts, max, detail, unavail) {
  return { key, label_fa: label, points: pts, max_points: max, detail_fa: detail, ok: pts > 0, unavailable: !!unavail, icon: pts > 0 ? '✅' : (unavail ? '❔' : '➖') };
}
const evidences = [
  ev('trend', 'هم‌راستایی روند H4/H1', 2, 2, 'روند صعودی 📈 — ADX=28 قوی'),
  ev('level', 'واکنش به سطح کلیدی', 2, 2, 'سایهٔ کندل H4 حمایت را لمس کرد'),
  ev('fundamental', 'پنجرهٔ فاندامنتال پاک', 2, 2, 'رویداد پراثری تا ۶ ساعت آینده نیست'),
  ev('momentum', 'تایید مومنتوم (RSI)', 1, 1, 'RSI=42 در منطقهٔ پولبک ↗'),
  ev('flow', 'جریان قدرت ارزها', 1, 1, 'USD قوی، JPY ضعیف'),
  ev('news', 'تایید خبری', 0, 1, 'خبر هم‌جهت پیدا نشد ❔', true),
  ev('tv', 'هم‌جهتی تریدینگ‌ویو', 1, 1, 'Recommend.All=BUY'),
  ev('session', 'سشن مناسب', 1, 1, 'لندن/نیویورک — نقدشوندگی بالا')
];
const judgments = [
  {
    symbol: 'EURUSD', fa_name: 'یورو به دلار آمریکا', price: 1.17, pip: 0.0001,
    score: 10, max_score: 11, evidences, vetoes: [], reject_reason: null, reject_detail: null,
    signal: {
      symbol: 'EURUSD', fa_name: 'یورو به دلار آمریکا', direction: 'BUY', stars: 5,
      score: 10, max_score: 11, entry: 1.17, sl: 1.165, tp: 1.18, pip: 0.0001,
      is_gold: false, rr: 2.0, atr: 0.0009, now: nowMs, session_fa: 'لندن/نیویورک',
      warnings: ['SL به سقف فاصله رسیده — ریسک را چک کن ⚠️'], _dup: false
    }
  },
  {
    symbol: 'USDJPY', fa_name: 'دلار آمریکا به ین ژاپن', price: 147.2, pip: 0.01,
    score: 4, max_score: 11, evidences,
    vetoes: [{ key: 'EVENT', title_fa: '📅 رویداد پراثر تقویم', detail_fa: 'رویداد پراثر «CPI» (USD) تا ۲۰ دقیقهٔ آینده — ساعت 22:۰۰ UTC' }],
    reject_reason: 'VETO', reject_detail: '📅 رویداد پراثر تقویم', signal: null
  },
  {
    symbol: 'GBPUSD', fa_name: 'پوند به دلار آمریکا', price: 1.31, pip: 0.0001,
    score: 5, max_score: 11, evidences, vetoes: [],
    reject_reason: 'LOW_SCORE', reject_detail: '⏳ امتیاز ۵ از آستانهٔ ۷ کمتر است', signal: null
  }
];
const analyses = [
  { symbol: 'EURUSD', fa_name: 'یورو به دلار آمریکا', price: 1.17, pip: 0.0001, adx: 28, rsi: 42, rsi_rising: true, atr: 0.0009, trend: 'bullish', h1_agrees: true, verdict: 'BUY_SETUP', support: 1.165, resistance: 1.18 },
  { symbol: 'USDJPY', fa_name: 'دلار آمریکا به ین ژاپن', price: 147.2, pip: 0.01, adx: 15, rsi: 55, rsi_rising: false, atr: 0.15, trend: 'none', h1_agrees: false, verdict: 'RANGE', support: null, resistance: null },
  { symbol: 'XAUUSD', fa_name: 'طلا به دلار آمریکا (انس)', price: 3650, pip: 1, adx: 31, rsi: 68, rsi_rising: true, atr: 22, trend: 'bearish', h1_agrees: true, verdict: 'DATA', support: 3600, resistance: 3700 }
];
const calEvents = [
  { when: nowMs + 3600e3, title: 'Core CPI m/m', title_fa: 'تورم هستهٔ ماهانه', impact: 'HIGH', country: 'USD', category: 'Inflation', forecast: '0.3', previous: '0.2' },
  { when: nowMs + 9 * 3600e3, title: 'Flash Manufacturing PMI', title_fa: 'PMI فلش تولید', impact: 'MEDIUM', country: 'EUR', category: 'Business', forecast: '48.1', previous: '' },
  { when: nowMs + 20 * 3600e3, title: 'BOJ Press Conference', title_fa: 'کنفرانس خبری بانک ژاپن', impact: 'LOW', country: 'JPY', category: 'Central Bank', forecast: '', previous: '' }
];
const newsItems = [
  { title: 'Fed officials signal caution on rate cuts', source: 'ForexLive', score: 5, breaking: true, link: 'https://example.com/1', published: nowMs - 1200e3, roundup: false, keywords: ['fed', 'rates'], direction: { USD: 1 } },
  { title: 'Week ahead: inflation data in focus', source: 'FXStreet', score: 3, breaking: false, link: '', published: nowMs - 7200e3, roundup: true, keywords: [], direction: {} },
  { title: 'Gold slips as dollar firms', source: 'Investing.com — طلا', score: 4, breaking: false, link: 'https://example.com/2', published: nowMs - 3000e3, roundup: false, keywords: ['gold'], direction: { XAU: -1, USD: 1 } }
];
const sparks = { EURUSD: [1.16, 1.162, 1.165, 1.163, 1.168, 1.17], USDJPY: [147, 147.4, 147.1, 147.2], XAUUSD: [3640, 3655, 3650] };

const state = {
  ranAt: nowMs, errors: 0, sourceName: 'yahoo',
  analyses, ranking: [['USD', 1.24], ['EUR', 0.41], ['JPY', -0.87], ['XAU', 0.2]],
  tvMap: {}, tvTf: '4h',
  calSnap: { events: calEvents, ok: true, stale: false, fetchedAt: nowMs, fromCache: false, weekRange: ['۲۰', '۲۶'], error: '' },
  newsSnap: { items: newsItems, ok: true, feedsOk: 5, feedsFailed: 0, staleFeeds: ['FXStreet (از مسیر Google News)'], failedNames: [], fetchedAt: nowMs, rawCount: 40, error: '' },
  judgments, resolvedCount: 1, sparks
};

const journalEntries = [
  { ts: nowMs - 86400e3, symbol: 'EURUSD', direction: 'BUY', entry: 1.16, sl: 1.155, tp: 1.17, pip: 0.0001, is_gold: false, score: 9, max_score: 11, outcome: 'TP', r: 2, note: '' },
  { ts: nowMs - 172800e3, symbol: 'USDJPY', direction: 'SELL', entry: 148, sl: 148.5, tp: 147, pip: 0.01, is_gold: false, score: 8, max_score: 11, outcome: 'SL', r: -1, note: '' },
  { ts: nowMs - 259200e3, symbol: 'XAUUSD', direction: 'BUY', entry: 3600, sl: 3580, tp: 3640, pip: 1, is_gold: true, score: 7, max_score: 11, outcome: 'EXPIRED', r: null, note: 'بدون برخورد' },
  { ts: nowMs - 3600e3, symbol: 'GBPUSD', direction: 'SELL', entry: 1.315, sl: 1.32, tp: 1.305, pip: 0.0001, is_gold: false, score: 8, max_score: 11, outcome: null, r: null, note: '' }
];

const alertMem = {
  'alerts.json': JSON.stringify([
    { id: 'EURUSD|above|1.18', symbol: 'EURUSD', dir: 'above', price: 1.18, pip: 0.0001, sticky: false, created_at: new Date(nowMs - 3600e3).toISOString(), last_fired: null },
    { id: 'XAUUSD|below|3600', symbol: 'XAUUSD', dir: 'below', price: 3600, pip: 1, sticky: true, created_at: new Date(nowMs - 7200e3).toISOString(), last_fired: null }
  ])
};
// کش نمودار مصنوعی (۲۰۰ کندل H1) برای پوشش صفحهٔ نمودار در جاروی بدون-ایموجی
const chartH1 = [];
let cpx = 1.15;
for (let ci = 0; ci < 200; ci++) {
  const co = cpx, cc = co + Math.sin(ci / 6) * 0.0016;
  chartH1.push({ t: nowMs - (200 - ci) * 3600e3, o: co, h: Math.max(co, cc) + 0.0006, l: Math.min(co, cc) - 0.0006, c: cc });
  cpx = cc;
}
alertMem['chart.EURUSD'] = JSON.stringify(chartH1);

const S = {
  cfg, settings, state,
  stats: O.computeStats(journalEntries, nowMs),
  journal: { load: () => journalEntries, raw: () => '' },
  storage: { get: k => alertMem[k] || '', set: (k, v) => { alertMem[k] = String(v); }, del: k => { delete alertMem[k]; } },
  version: '0.17.0',
  chartSym: 'EURUSD', chartTf: 'H1', chartBars: 120,
  chartSig: { symbol: 'EURUSD', entry: 1.17, sl: 1.165, tp: 1.18, pip: 0.0001, direction: 'BUY' }
};

const pages = {
  home: O.renderHome(S),
  signals: O.renderSignals(S),
  calendar: O.renderCalendar(S),
  news: O.renderNews(S),
  journal: O.renderJournal(S),
  settings: O.renderSettings(S),
  about: O.renderAbout(S),
  briefing: O.renderBriefingPage(S)
};

// حالت‌های خالی هم باید بدون ایموجی باشند
const SEmpty = { cfg, settings, state: null, stats: null, journal: { load: () => [], raw: () => '' }, version: '0.13.0' };
pages['home-empty'] = O.renderHome(SEmpty);
pages['signals-empty'] = O.renderSignals(SEmpty);
pages['calendar-empty'] = O.renderCalendar(SEmpty);
pages['news-empty'] = O.renderNews(SEmpty);
pages['journal-empty'] = O.renderJournal(SEmpty);
pages['briefing-empty'] = O.renderBriefingPage(SEmpty);

// حالت‌های خطا (calSnap/newsSnap خراب)
const SBad = JSON.parse(JSON.stringify({ cfg, settings, version: '0.13.0' }));
SBad.state = { ranAt: nowMs, analyses: [], calSnap: { ok: false, error: 'HTTP 403' }, newsSnap: { ok: false, error: 'خبر مرتبطی پیدا نشد', items: [], failedNames: ['ForexLive'], staleFeeds: [] }, judgments: [], sparks: {}, ranking: [] };
SBad.journal = { load: () => [], raw: () => '' };
pages['calendar-bad'] = O.renderCalendar(SBad);
pages['news-bad'] = O.renderNews(SBad);

// صفحهٔ نمودار (v0.17.0) — با سیگنال و بدون کش
pages['chart'] = O.renderChartPage(S);
pages['chart-empty'] = O.renderChartPage(Object.assign({}, S, { chartSym: 'GBPUSD' }));

for (const [name, html] of Object.entries(pages)) {
  noEmoji(html, 'page:' + name);
  if (!name.endsWith('-empty')) hasSvg(html, 'page:' + name);
}

// دکمهٔ نمودار روی کارت نماد (v0.17.0)
assert(pages.home.includes('data-chart-open="EURUSD"'), 'chart button missing on symbol card');
assert(pages.signals.includes('data-chart-sig="EURUSD"'), 'show-on-chart button missing on signal card');

// کارت هشدارهای قیمت در خانه (v0.16.0) — بدون ایموجی و با دکمهٔ حذف
assert(pages.home.includes('هشدارهای قیمت'), 'alerts card missing in home');
assert(pages.home.includes('data-alert-del="EURUSD|above|1.18"'), 'alert delete button missing');
assert(pages.home.includes('data-alert-add="EURUSD"'), 'alert add button missing on symbol card');

// تنظیمات باید سوئیچ رصد پس‌زمینه را داشته باشد (v0.13.0)
assert(pages.settings.includes('background_enabled'), 'background switch missing in settings');
assert(pages.settings.includes('رصد پس‌زمینه'), 'background card title missing');

// about باید اثر انگشت کلید v0.13.0 را نشان دهد
assert(pages.about.includes('SHA256: bd11159e003b55b9ae53cd26c192dc6b2bea2840c787fddbd0f523a947cb5189'), 'cert fingerprint missing in about');

// noEmoji ابزار پاک‌سازی متن ساده (اعلان/لاگ سرویس)
assert(O.noEmoji('🎯 سیگنال جدید — EURUSD (خرید) 🕒') === 'سیگنال جدید — EURUSD (خرید)', 'noEmoji failed: ' + O.noEmoji('🎯 سیگنال جدید — EURUSD (خرید) 🕒'));

console.log('SMOKE ICONS OK — ' + Object.keys(pages).length + ' page(s) rendered emoji-free');
