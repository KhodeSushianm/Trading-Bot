/* اسموک‌تست هشدارهای قیمت (v0.16.0) — منطق alerts.js بدون DOM.
 * اجرا: node tests/js/smoke_alerts.js */
'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');

const WWW = path.join(__dirname, '..', '..', 'android', 'app', 'src', 'main', 'assets', 'www', 'js');
const ctx = { console };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(WWW, 'alerts.js'), 'utf8'), ctx, { filename: 'alerts.js' });
const O = ctx.ODIN;

const mem = {};
const storage = {
  get: k => mem[k] || '',
  set: (k, v) => { mem[k] = String(v); },
  del: k => { delete mem[k]; }
};
const MIN = 60000;

// ── افزودن ──
let r = O.alertsAdd(storage, 'EURUSD', 'above', 1.18, false, 0.0001);
assert(r.ok && r.count === 1, 'add above');
r = O.alertsAdd(storage, 'EURUSD', 'above', 1.18, false, 0.0001);
assert(!r.ok && r.why === 'duplicate', 'duplicate rejected');
r = O.alertsAdd(storage, 'EURUSD', 'below', 1.18, false, 0.0001);
assert(r.ok, 'same price, other direction = separate alert');
r = O.alertsAdd(storage, 'EURUSD', 'above', 0, false, 0.0001);
assert(!r.ok && r.why === 'invalid', 'invalid price rejected');
assert.strictEqual(O.alertId('EURUSD', 'above', 1.18), 'EURUSD|above|1.18');

// سقف ۲۰ هشدار
for (let i = 0; i < 18; i++) O.alertsAdd(storage, 'XAUUSD', 'above', 3000 + i, false, 1);
r = O.alertsAdd(storage, 'XAUUSD', 'above', 9999, false, 1);
assert(!r.ok && r.why === 'max', 'max 20 alerts enforced, got: ' + JSON.stringify(r));

// ── پاک‌سازی و سناریوی فعال‌شدن ──
mem['alerts.json'] = JSON.stringify([
  { id: 'A', symbol: 'EURUSD', dir: 'above', price: 1.18, pip: 0.0001, sticky: false, created_at: new Date().toISOString(), last_fired: null },
  { id: 'B', symbol: 'EURUSD', dir: 'below', price: 1.10, pip: 0.0001, sticky: false, created_at: new Date().toISOString(), last_fired: null },
  { id: 'C', symbol: 'EURUSD', dir: 'above', price: 1.15, pip: 0.0001, sticky: true, created_at: new Date().toISOString(), last_fired: null }
]);
const t0 = Date.now();
let fired = O.alertsCheck(storage, [{ symbol: 'EURUSD', price: 1.17, pip: 0.0001 }], t0);
assert.strictEqual(fired.length, 1, 'only C (1.17 >= 1.15) fires at 1.17');
assert.strictEqual(fired[0].a.id, 'C');
assert.strictEqual(O.alertsLoad(storage).length, 3, 'sticky stays');

// کول‌داون چسبنده: فوراً دوباره فعال نمی‌شود
fired = O.alertsCheck(storage, [{ symbol: 'EURUSD', price: 1.17, pip: 0.0001 }], t0 + MIN);
assert.strictEqual(fired.length, 0, 'sticky cooldown blocks immediate re-fire');
// بعد از ۶۱ دقیقه دوباره فعال می‌شود
fired = O.alertsCheck(storage, [{ symbol: 'EURUSD', price: 1.17, pip: 0.0001 }], t0 + 61 * MIN);
assert.strictEqual(fired.length, 1, 'sticky re-fires after cooldown');

// عبور به بالا: A فعال و حذف می‌شود (یک‌بار مصرف)
fired = O.alertsCheck(storage, [{ symbol: 'EURUSD', price: 1.185, pip: 0.0001 }], t0 + 62 * MIN);
assert(fired.some(f => f.a.id === 'A'), 'A fires on cross above (>=)');
let left = O.alertsLoad(storage).map(a => a.id);
assert(!left.includes('A'), 'non-sticky removed after firing');
assert(left.includes('B') && left.includes('C'));

// عبور به پایین: B فعال و حذف
fired = O.alertsCheck(storage, [{ symbol: 'EURUSD', price: 1.095, pip: 0.0001 }], t0 + 63 * MIN);
assert(fired.some(f => f.a.id === 'B'), 'B fires on cross below (<=)');
left = O.alertsLoad(storage).map(a => a.id);
assert.strictEqual(left.join(','), 'C', 'only sticky C remains');

// نبودِ نماد در تحلیل‌ها → هشدار دست‌نخورده می‌ماند
fired = O.alertsCheck(storage, [{ symbol: 'USDJPY', price: 147, pip: 0.01 }], t0 + 200 * MIN);
assert.strictEqual(fired.length, 0);
assert.strictEqual(O.alertsLoad(storage).length, 1);

// حذف دستی
O.alertsRemove(storage, 'C');
assert.strictEqual(O.alertsLoad(storage).length, 0);

// دادهٔ خراب در storage → سقوط نمی‌کند
mem['alerts.json'] = '{{{bad json';
assert.strictEqual(O.alertsLoad(storage).length, 0);
assert.strictEqual(O.alertsCheck(storage, [{ symbol: 'EURUSD', price: 1, pip: 0.0001 }], Date.now()).length, 0);

console.log('SMOKE ALERTS OK — افزودن/تکراری/سقف، عبور بالا و پایین، یک‌بارمصرف، چسبنده با کول‌داون، حذف، دادهٔ خراب');
