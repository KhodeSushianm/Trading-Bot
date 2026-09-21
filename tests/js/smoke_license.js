/* اسموک‌تست لایسنس اندروید (v0.14.0) — js/license.js در برابر وکتورهای قطعی.
 *
 * مهم‌ترین assert: بُرِد مشترک با src/license.py — همان secret و همان HMAC در
 * دو زبان باید کلید یکسان بسازند (main.py --selftest هم همین برد را چک می‌کند).
 *
 * اجرا: node tests/js/smoke_license.js */
'use strict';
const fs = require('fs');
const vm = require('vm');
const crypto = require('crypto');
const assert = require('assert');
const path = require('path');

const WWW = path.join(__dirname, '..', '..', 'android', 'app', 'src', 'main', 'assets', 'www', 'js');
const ctx = { console };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(WWW, 'license.js'), 'utf8'), ctx, { filename: 'license.js' });
const O = ctx.ODIN;

// ── ۱) SHA-256/HMAC در برابر node:crypto (لبه‌های padding هم پوشش داده شود)
for (const n of [0, 1, 54, 55, 56, 57, 63, 64, 65, 118, 119, 120, 1000]) {
  const s = 'x'.repeat(n);
  assert.strictEqual(O.sha256Hex(s), crypto.createHash('sha256').update(s).digest('hex'),
    'sha256 mismatch at len ' + n);
  const k = 'secret-key-' + n;
  assert.strictEqual(O.hmacSha256Hex(k, s), crypto.createHmac('sha256', k).update(s).digest('hex'),
    'hmac mismatch at len ' + n);
}
assert.strictEqual(O.sha256Hex('abc'),
  'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
assert.strictEqual(O.hmacSha256Hex('key', 'The quick brown fox jumps over the lazy dog'),
  'f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8');

// ── ۲) برد مشترک با پایتون (src/license.py / main.py --selftest) ──
assert.strictEqual(O.licenseKeyFor('AB12-CD34-EF56'), '6F1F-8540-078F-9898');
assert.strictEqual(O.licenseKeyFor('D9AC-5560-5559'), 'B26E-AA4A-E4A2-4641');

// ── ۳) قالب‌ها و نرمال‌سازی ──
assert.strictEqual(O.normalizeCode(' ab12-cd34 ef56 '), 'AB12CD34EF56');
assert.strictEqual(O.formatCode('AB12CD34EF56'), 'AB12-CD34-EF56');
assert.strictEqual(O.deviceCodeFromId('d9ac55605559eec1bad9074c20e84f313fae614cf77ff9ca402e218efb9f2224'),
  'D9AC-5560-5559');
assert.strictEqual(O.licenseKeyFor('short'), '');

// ── ۴) اعتبارسنجی کلید ──
const deviceId = 'ab'.repeat(32);                 // ۶۴ هگز — مثل خروجی Bridge.getDeviceId
const code = O.deviceCodeFromId(deviceId);        // ABAB-ABAB-ABAB
const key = O.licenseKeyFor(code);
assert(O.validateKey(key, code), 'کلید درست باید معتبر باشد');
assert(O.validateKey(key.toLowerCase().replace(/-/g, ' '), code), 'مقاوم به فاصله/کوچک‌بزرگی');
assert(!O.validateKey('AAAA-BBBB-CCCC-DDDD', code), 'کلید غلط باید رد شود');
assert(!O.validateKey('short', code), 'کلید بدقالبه باید رد شود');
assert(!O.validateKey(key, 'FF00-FF00-FF00'), 'کلید دستگاه دیگر باید رد شود');

// ── ۵) چرخهٔ ذخیره (storage جعلی مثل SharedPreferences) ──
const mem = {};
const storage = {
  get: k => mem[k] || '',
  set: (k, v) => { mem[k] = String(v); },
  del: k => { delete mem[k]; }
};
assert(!O.licIsActive(storage, deviceId), 'بدون لایسنس: غیرفعال');
assert(O.licActivate(storage, key, deviceId, 'تستر'), 'فعال‌سازی با کلید درست');
assert(O.licIsActive(storage, deviceId), 'پس از فعال‌سازی: فعال');
assert(!O.licIsActive(storage, 'ff'.repeat(32)), 'device_id بیگانه → غیرفعال (ضدکپی license.dat)');
assert(!O.licActivate(storage, 'AAAA-BBBB-CCCC-DDDD', deviceId, 'هکر'), 'فعال‌سازی با کلید غلط رد می‌شود');
const rec = JSON.parse(mem['license.dat']);
assert.strictEqual(rec.version, '2.0');
assert.strictEqual(rec.device_id, deviceId);
O.licDeactivate(storage);
assert(!O.licIsActive(storage, deviceId), 'پس از غیرفعال‌سازی: غیرفعال');

console.log('SMOKE LICENSE OK — sha256/hmac مطابق node:crypto، برد مشترک با پایتون، قفل دستگاه سالم');
