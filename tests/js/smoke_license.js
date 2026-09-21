/* اسموک‌تست لایسنس اندروید (v0.15.0) — js/license.js در برابر وکتورهای قطعی.
 *
 * پوشش: sha256/hmac (مطابق node:crypto روی طول‌های مرزی) · بُرِدهای مشترک با
 * src/license.py (دائمی + زمان‌دار) · پارس کلید ۲۲ کاراکتری · انقضا · قفل
 * device_id · دورهٔ آزمایشی ۷ روزه · ضدِ عقب‌کشیدن ساعت (high-water-mark).
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

// ── ۱) SHA-256/HMAC در برابر node:crypto (لبه‌های padding) ──
for (const n of [0, 1, 54, 55, 56, 57, 63, 64, 65, 118, 119, 120, 1000]) {
  const s = 'x'.repeat(n);
  assert.strictEqual(O.sha256Hex(s), crypto.createHash('sha256').update(s).digest('hex'),
    'sha256 mismatch at len ' + n);
  const k = 'secret-key-' + n;
  assert.strictEqual(O.hmacSha256Hex(k, s), crypto.createHmac('sha256', k).update(s).digest('hex'),
    'hmac mismatch at len ' + n);
}

// ── ۲) بُرِدهای مشترک با پایتون (main.py --selftest هم همین‌ها را چک می‌کند) ──
assert.strictEqual(O.licenseKeyFor('AB12-CD34-EF56'), '6F1F-8540-078F-9898');            // دائمی
assert.strictEqual(O.licenseKeyFor('D9AC-5560-5559'), 'B26E-AA4A-E4A2-4641');            // دائمی
assert.strictEqual(O.licenseKeyFor('AB12-CD34-EF56', '20301231'), '19DB-2DFA-F0E7-0082-301231'); // زمان‌دار

// ── ۳) پارس کلید (۱۶ = دائمی، ۲۲ = زمان‌دار، بقیه رد) ──
let p = O.parseKeyInput('19db-2dfa-f0e7-0082 301231');
assert(p && p.key === '19DB2DFAF0E70082' && p.expiry8 === '20301231');
assert.strictEqual(O.parseKeyInput('6F1F-8540-078F-9898').expiry8, null);
assert.strictEqual(O.parseKeyInput('short'), null);
assert.strictEqual(O.parseKeyInput('19DB2DFAF0E70082-310231'), null);  // ۳۱ فوریه!
assert.strictEqual(O.parseKeyInput('19DB2DFAF0E70082-3012'), null);    // کوتاه
assert.strictEqual(O.licenseKeyFor('short'), '');

// ── ۴) اعتبارسنجی: دائمی/زمان‌دار/انقضا/دستگاه دیگر ──
const deviceId = 'ab'.repeat(32);                 // مثل خروجی Bridge.getDeviceId
const code = O.deviceCodeFromId(deviceId);        // ABAB-ABAB-ABAB
const kp = O.licenseKeyFor(code);
const kt = O.licenseKeyFor(code, '20301231');
assert(O.validateKey(kp, code), 'دائمی معتبر');
assert(O.validateKey(kp.toLowerCase().replace(/-/g, ' '), code), 'مقاوم به فاصله/کوچک‌بزرگی');
assert(O.validateKey(kt, code), 'زمان‌دار معتبر');
assert(O.validateKey(kt, code, new Date('2030-12-31T10:00:00').getTime()), 'روز انقضا هنوز معتبر');
assert(!O.validateKey(kt, code, new Date('2031-01-01T00:00:00').getTime()), 'منقضی رد می‌شود');
assert(!O.validateKey(O.formatCode(O.normalizeKey(kt).slice(0, 16)), code), 'حذف پسوند تاریخ → رد (HMAC روی تاریخ هم هست)');
assert(!O.validateKey('AAAA-BBBB-CCCC-DDDD', code), 'کلید غلط');
assert(!O.validateKey(kp, 'FF00-FF00-FF00'), 'کلید دستگاه دیگر');

// ── ۵) چرخهٔ ذخیره + قفل device_id + انقضا ──
const mem = {};
const storage = { get: k => mem[k] || '', set: (k, v) => { mem[k] = String(v); }, del: k => { delete mem[k]; } };
assert(!O.licIsActive(storage, deviceId), 'بدون لایسنس: غیرفعال');
assert(O.licActivate(storage, kt, deviceId, 'تستر'), 'فعال‌سازی زمان‌دار');
assert(O.licIsActive(storage, deviceId), 'فعال');
assert(!O.licIsActive(storage, deviceId, new Date('2031-01-02T00:00:00').getTime()), 'پس از انقضا: غیرفعال');
assert(!O.licIsActive(storage, 'ff'.repeat(32)), 'device_id بیگانه → غیرفعال (ضدکپی)');
const rec = JSON.parse(mem['license.dat']);
assert.strictEqual(rec.version, '2.1');
assert.strictEqual(rec.expires_at, '20301231');
assert(rec.last_seen, 'last_seen برای ضدِ دستکاری ساعت ذخیره شود');
// دستکاری رکورد: last_seen آینده → rollback
const tampered = Object.assign({}, rec, { last_seen: new Date(Date.now() + 96 * 3600e3).toISOString() });
mem['license.dat'] = JSON.stringify(tampered);
assert(!O.licIsActive(storage, deviceId), 'عقب‌کشیدن ساعت → غیرفعال');
mem['license.dat'] = JSON.stringify(rec);
assert(!O.licActivate(storage, 'AAAA-BBBB-CCCC-DDDD', deviceId, 'هکر'), 'فعال‌سازی با کلید غلط رد می‌شود');
O.licDeactivate(storage);
assert(!O.licIsActive(storage, deviceId), 'پس از غیرفعال‌سازی');

// ── ۶) دورهٔ آزمایشی: ۷ روز، یک‌بار، ضد ساعت ──
let t0 = O.trialStatus(storage);
assert(!t0.exists && !t0.active && t0.daysLeft === 0);
assert(O.trialStart(storage), 'شروع تریال');
assert(!O.trialStart(storage), 'تریال دوباره شروع نمی‌شود (ضدتقلب)');
let t1 = O.trialStatus(storage);
assert(t1.active && t1.daysLeft === 7);
let t2 = O.trialStatus(storage, Date.now() + 6.5 * 864e5);
assert(t2.active && t2.daysLeft === 1, 'روز ۶.۵ → ۱ روز باقی');
let t3 = O.trialStatus(storage, Date.now() + 7.2 * 864e5);
assert(!t3.active && t3.daysLeft === 0, 'پایان تریال');
let t4 = O.trialStatus(storage, Date.now() - 96 * 36e5);
assert(t4.tampered && !t4.active, 'عقب‌کشیدن ساعت → tampered');

console.log('SMOKE LICENSE OK — hmac/vectors (دائمی+زمان‌دار)، انقضا، قفل دستگاه، تریال ۷ روزه، ضدساعت');
