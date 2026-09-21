/* اسموک‌تست کارت تصویری سیگنال (v0.18.0) — buildShareSpec بدون DOM.
 * رندر Canvas در Node ممکن نیست؛ به همان دلیل spec (لایهٔ داده) از رسم
 * جدا شده و اینجا تمام رشته‌ها/اعداد کارت قفل می‌شوند.
 * اجرا: node tests/js/smoke_share.js */
'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');

const WWW = path.join(__dirname, '..', '..', 'android', 'app', 'src', 'main', 'assets', 'www', 'js');
const ctx = { console };
ctx.globalThis = ctx;
vm.createContext(ctx);
for (const f of ['fa.js', 'icons.js', 'sharecard.js']) {
  vm.runInContext(fs.readFileSync(path.join(WWW, f), 'utf8'), ctx, { filename: f });
}
const O = ctx.ODIN;

const now = Date.UTC(2026, 8, 21, 12, 0, 0);   // دوشنبه ۲۱ سپتامبر ۲۰۲۶، ۱۲:۰۰ UTC = ۱۵:۳۰ تهران
const sig = {
  symbol: 'EURUSD', fa_name: 'یورو به دلار آمریکا', direction: 'BUY', stars: 5,
  score: 10, max_score: 11, entry: 1.17, sl: 1.165, tp: 1.18,
  pip: 0.0001, is_gold: false, rr: 2.0, now, session_fa: 'لندن/نیویورک'
};

const spec = O.buildShareSpec(sig, { version: '0.19.0' });

// ── هویت و جهت ──
assert.strictEqual(spec.brand, 'ODIN ASSISTANT');
assert.strictEqual(spec.pair, 'EUR/USD');
assert.strictEqual(spec.dir, 'BUY');
assert.strictEqual(spec.dirLabel, 'سیگنال خرید');

// ── قیمت‌ها لاتین (قرارداد اپ)، پیپ‌ها فارسی ──
assert.strictEqual(spec.entry, '1.17000');
assert.strictEqual(spec.sl, '1.16500');
assert.strictEqual(spec.tp, '1.18000');
assert.strictEqual(spec.slDist, '۵۰ پیپ');
assert.strictEqual(spec.tpDist, '۱۰۰ پیپ');
assert.strictEqual(spec.rr, 'ریسک به ریسک ۱:۲');

// ── امتیاز فارسی + درصد نوار ──
assert.strictEqual(spec.scoreFa, '۱۰ از ۱۱');
assert(Math.abs(spec.scorePct - 10 / 11) < 1e-9);
assert.strictEqual(spec.stars, 5);

// ── تاریخ: جلالی + ساعت تهران ──
assert(spec.jalali.includes('شهریور') && spec.jalali.includes('۱۴۰۵'), 'jalali: ' + spec.jalali);
assert.strictEqual(spec.timeTeh, '۱۵:۳۰ تهران');
assert.strictEqual(spec.session, 'لندن/نیویورک');

// ── فوتر برند/فروش ──
assert.strictEqual(spec.footerTg, '@Khode_Sushian');
assert(spec.footerName.includes('Sushian Khoshkhani'));
assert(spec.disclaimer.includes('پیشنهاد است'));
assert.strictEqual(spec.version, 'v0.19.0');

// ── بدون ایموجی (کل spec) ──
assert(!O.EMOJI_RE.test(JSON.stringify(spec)), 'emoji in share spec');

// ── واریانت فروش ──
const sell = O.buildShareSpec(Object.assign({}, sig, { direction: 'SELL', stars: 3 }));
assert.strictEqual(sell.dirLabel, 'سیگنال فروش');
assert.strictEqual(sell.dir, 'SELL');
assert.strictEqual(sell.stars, 3);

// ── واریانت طلا (پیپ = دلار) ──
const gold = O.buildShareSpec({
  symbol: 'XAUUSD', fa_name: 'طلا', direction: 'SELL', stars: 4, score: 8, max_score: 11,
  entry: 3650, sl: 3672, tp: 3606, pip: 1, is_gold: true, rr: 2, now, session_fa: ''
});
assert.strictEqual(gold.pair, 'XAU/USD');   // ۶ کاراکتر → جفت‌نمایش مثل بقیهٔ اپ
assert.strictEqual(gold.entry, '3650.0');   // دقت fmtPrice برای طلا — یکسان با کارت سیگنال اپ
assert(gold.slDist.includes('$') && gold.tpDist.includes('$'), 'gold distances in $');

// ── ستاره/امتیاز لبه‌ای ──
const edge = O.buildShareSpec(Object.assign({}, sig, { stars: 9, score: 0 }));
assert.strictEqual(edge.stars, 5, 'stars clamped to 5');
assert.strictEqual(edge.scorePct, 0);

console.log('SMOKE SHARE OK — spec کارت تصویری: جهت/قیمت/پیپ/امتیاز/جلالی/تهران/فوتر/بدون ایموجی');
