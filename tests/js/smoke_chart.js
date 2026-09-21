/* اسموک‌تست نمودار کندل‌استیک (v0.17.0) — chart.js + renderChartPage بدون DOM.
 * اجرا: node tests/js/smoke_chart.js */
'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');

const WWW = path.join(__dirname, '..', '..', 'android', 'app', 'src', 'main', 'assets', 'www', 'js');
const ctx = { console };
ctx.globalThis = ctx;
vm.createContext(ctx);
for (const f of ['fa.js', 'icons.js', 'indicators.js', 'data.js', 'chart.js', 'ui.js']) {
  vm.runInContext(fs.readFileSync(path.join(WWW, f), 'utf8'), ctx, { filename: f });
}
const O = ctx.ODIN;

// ── دادهٔ مصنوعی: ۴۰۰ کندل H1 ──
const base = Date.UTC(2026, 8, 1);
const h1 = [];
let px = 1.15;
for (let i = 0; i < 400; i++) {
  const o = px;
  const c = o + Math.sin(i / 7) * 0.002 + (i % 13 === 0 ? 0.0015 : -0.0004);
  const hi = Math.max(o, c) + 0.0007, lo = Math.min(o, c) - 0.0007;
  h1.push({ t: base + i * 3600e3, o, h: hi, l: lo, c });
  px = c;
}

function count(hay, needle) { return hay.split(needle).length - 1; }

// ── ۱) renderCandleChart مستقیم ──
let svg = O.renderCandleChart(h1.slice(-60), { pip: 0.0001, maxBars: 60 });
assert(svg.startsWith('<svg'), 'svg output');
assert.strictEqual(count(svg, '<rect'), 61, '۶۰ بدنه + ۱ قرص قیمت = ۶۱ rect');
assert(!O.EMOJI_RE.test(svg), 'no emoji in chart svg');
assert(svg.includes('dir="ltr"'), 'chart is LTR');

// برش maxBars
svg = O.renderCandleChart(h1, { pip: 0.0001, maxBars: 30 });
assert.strictEqual(count(svg, '<rect'), 31, 'maxBars slicing');

// سطوح: برچسب و خط‌چین
svg = O.renderCandleChart(h1.slice(-60), {
  pip: 0.0001, maxBars: 60, levels: [
    { price: 1.15, color: 'var(--ink)', label: 'ورود 1.1500' },
    { price: 1.14, color: 'var(--red)', label: 'حد ضرر 1.1400', dash: '6 3' },
    { price: 1.17, color: 'var(--green)', label: 'هدف 1.1700', dash: '6 3' }
  ]
});
assert(svg.includes('هدف') && svg.includes('حد ضرر') && svg.includes('ورود'), 'level labels rendered');
assert(svg.includes('stroke-dasharray="6 3"'), 'dashed SL/TP lines');
// سطح بیرون از دامنهٔ کندل‌ها هم مقیاس را باز می‌کند (tp=1.30 خیلی بالاتر)
svg = O.renderCandleChart(h1.slice(-60), { pip: 0.0001, levels: [{ price: 1.30, color: 'var(--green)', label: 'دور' }] });
assert(svg.includes('دور'), 'far level expands scale and renders');

// دادهٔ کم → حالت خالی، بدون کرش
assert(O.renderCandleChart([], {}).includes('کافی نیست'), 'empty candles → empty state');
assert(O.renderCandleChart(h1.slice(0, 1), {}).includes('کافی نیست'), 'single candle → empty state');

// ── ۲) H4 با resample4h (تابع parity-تست‌شدهٔ data.js) ──
const h4 = O.resample4h(h1);
assert(h4.length > 90 && h4.length < 110, 'H4 ≈ 400/4 = ~100 کندل, got ' + h4.length);
svg = O.renderCandleChart(h4, { pip: 0.0001, maxBars: 90 });
assert(count(svg, '<rect') >= 2, 'H4 chart renders');

// ── ۳) renderChartPage با S مصنوعی ──
const mem = { 'chart.EURUSD': JSON.stringify(h1) };
const storage = { get: k => mem[k] || '', set: (k, v) => { mem[k] = String(v); }, del: k => { delete mem[k]; } };
const analyses = [{
  symbol: 'EURUSD', fa_name: 'یورو به دلار آمریکا', price: h1[h1.length - 1].c, pip: 0.0001,
  adx: 25, rsi: 55, rsi_rising: true, atr: 0.0009, trend: 'bullish', h1_agrees: true,
  verdict: 'BUY_SETUP', support: 1.1400, resistance: 1.1700
}];
const S = {
  cfg: O.CONFIG, settings: { user_name: 'تست' }, version: '0.17.0',
  state: { ranAt: Date.now(), analyses, judgments: [], sparks: {} },
  storage,
  chartSym: 'EURUSD', chartTf: 'H1', chartBars: 120,
  chartSig: { symbol: 'EURUSD', entry: 1.15, sl: 1.14, tp: 1.17, pip: 0.0001, direction: 'BUY' }
};
let page = O.renderChartPage(S);
assert(page.includes('data-chart-tf="H4"'), 'H4 pill');
assert(page.includes('data-chart-bars="240"'), 'bars pill 240');
assert(page.includes('سطوح سیگنال'), 'signal levels card');
assert(page.includes('حمایت') && page.includes('مقاومت'), 'S/R lines on chart');
assert(!O.EMOJI_RE.test(page), 'chart page emoji-free');
assert(page.includes('<svg'), 'chart svg present');

// حالت H4
S.chartTf = 'H4'; S.chartBars = 60;
page = O.renderChartPage(S);
assert(page.includes('— H4'), 'H4 title');
assert(page.includes('data-chart-bars="90"'), 'H4 bar options');

// بدون کش → حالت خالی
S.chartSym = 'GBPUSD';
page = O.renderChartPage(S);
assert(page.includes('دادهٔ کندل کافی نیست'), 'no cache → honest empty state');
assert(!O.EMOJI_RE.test(page), 'empty chart page emoji-free');

// بدون نماد
S.chartSym = null; S.state.analyses = [];
page = O.renderChartPage(S);
assert(page.includes('نمادی انتخاب نشده'), 'no symbol → guidance');

console.log('SMOKE CHART OK — کندل‌ها/برش/سطوح/H4/صفحه/حالت‌های خالی، بدون ایموجی');
