/* اسموک‌تست «حالت سرویس» (v0.13.0) — رصد پس‌زمینه بدون DOM و بدون نیتیو.
 *
 * پل نیتیو (ODINNative) با prefs در حافظه + جاسوس‌های اعلان شبیه‌سازی می‌شود،
 * location.search='?svc=1' اپ را در حالت سرویس بوت می‌کند و ODIN.svcTick
 * دقیقاً مثل OdinService روی گوشی صدا زده می‌شود.
 *
 * دو فاز:
 *   ۱) بازار بسته (marketStatus واقعی یا forcing) → بدون شبکه: notifyOngoing
 *      «بازار بسته» + bgCycleDone(30)
 *   ۲) بازار باز (به‌زور) → چرخهٔ کامل زنده: داده ← داور ← ژورنال ←
 *      state.last/sent_signals در prefs + bgCycleDone(فاصلهٔ تنظیمات)
 *
 * اجرا: node tests/js/smoke_service.js   (فاز ۲ به اینترنت زنده نیاز دارد) */
'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');

const WWW = path.join(__dirname, '..', '..', 'android', 'app', 'src', 'main', 'assets', 'www', 'js');

const prefs = new Map();
const calls = { notify: [], ongoing: [], cycleDone: [], stopBg: 0 };
const DEVICE_ID = 'ab'.repeat(32);   // مثل خروجی Bridge.getDeviceId

const ctx = {
  console, setTimeout, clearTimeout, setInterval, clearInterval,
  fetch, TextDecoder, Promise, Date, Math, JSON,
  location: { search: '?svc=1' }
};
ctx.globalThis = ctx;
ctx.ODINNative = {
  getPref: k => prefs.get(k) || '',
  setPref: (k, v) => prefs.set(k, String(v)),
  removePref: k => prefs.delete(k),
  getVersion: () => '0.13.0',
  notify: (t, b) => calls.notify.push([t, b]),
  notifyOngoing: (t, b) => calls.ongoing.push([t, b]),
  bgCycleDone: m => calls.cycleDone.push(m),
  stopBackground: () => { calls.stopBg++; },
  getDeviceId: () => DEVICE_ID
  // عمداً بدون http → لایهٔ داده به fetch نیتیوِ Node می‌افتد (مثل گوشی بدون Bridge نبودن)
};
vm.createContext(ctx);
for (const f of ['md5.js', 'fa.js', 'icons.js', 'license.js', 'config.js', 'indicators.js', 'session.js',
  'technical.js', 'calendar.js', 'news.js', 'judge.js', 'journal.js', 'data.js', 'alerts.js', 'chart.js',
  'briefing.js', 'ui.js', 'app.js']) {
  vm.runInContext(fs.readFileSync(path.join(WWW, f), 'utf8'), ctx, { filename: f });
}
const O = ctx.ODIN;

assert(O.SERVICE_MODE === true, 'SERVICE_MODE should be true with ?svc=1');
assert(typeof O.svcStart === 'function' && typeof O.svcTick === 'function', 'svc hooks missing');

function waitFor(cond, timeoutMs, what) {
  return new Promise((res, rej) => {
    const t0 = Date.now();
    const iv = setInterval(() => {
      if (cond()) { clearInterval(iv); res(); }
      else if (Date.now() - t0 > timeoutMs) { clearInterval(iv); rej(new Error('timeout waiting for ' + what)); }
    }, 250);
  });
}

const realMarketStatus = O.marketStatus;

(async function main() {
  // ── فاز ۰ (v0.14.0): بدون لایسنس، سرویس نباید چرخه بزند ──
  O.svcStart();
  await new Promise(r => setTimeout(r, 200));
  assert.strictEqual(calls.cycleDone.length, 0, 'unlicensed service must not run cycles');
  assert(calls.stopBg === 1, 'unlicensed service must stop itself');
  assert(calls.ongoing.some(([t, b]) => (t + ' ' + b).includes('فعال‌سازی')), 'unlicensed ongoing must ask for activation');
  console.log('  ✅ فاز ۰ — بدون لایسنس: سرویس صادقانه می‌ایستد (stopBackground + اعلان فعال‌سازی)');

  // ── فاز ۰.۵ (v0.15.0): دورهٔ آزمایشی ۷ روزه → سرویس بدون کلید دسترسی دارد ──
  const pstorage = { get: k => prefs.get(k) || '', set: (k, v) => prefs.set(k, String(v)), del: k => prefs.delete(k) };
  assert(O.trialStart(pstorage), 'trial must start');
  ctx.ODIN.S.svcReady = false;
  calls.stopBg = 0; calls.cycleDone.length = 0; calls.ongoing.length = 0; calls.notify.length = 0;
  O.svcStart();
  await waitFor(() => calls.cycleDone.length > 0, 240000, 'trial-based cycleDone');
  assert.strictEqual(calls.stopBg, 0, 'trial grants background access — service must not stop');
  console.log('  ✅ فاز ۰.۵ — با تریال ۷ روزه، رصد پس‌زمینه بدون کلید کار می‌کند');

  // فعال‌سازی با کلید دائمی درست (همان طرح HMAC پایتون)
  const code = O.deviceCodeFromId(DEVICE_ID);
  const key = O.licenseKeyFor(code);
  prefs.set('license.dat', JSON.stringify({
    license_key: O.normalizeKey(key), device_id: DEVICE_ID,
    user_name: 'تستر', activated_at: new Date().toISOString(), version: '2.1'
  }));
  calls.stopBg = 0;
  ctx.ODIN.S.svcReady = false;      // init دوباره تا لایسنس اعمال شود
  calls.cycleDone.length = 0; calls.ongoing.length = 0;
  // هشدار قیمتِ حتماً فعال‌شو (v0.16.0): EURUSD زیر ۹۹۹ — در چرخهٔ زنده شلیک می‌شود
  prefs.set('alerts.json', JSON.stringify([{
    id: 'EURUSD|below|999', symbol: 'EURUSD', dir: 'below', price: 999, pip: 0.0001,
    sticky: false, created_at: new Date().toISOString(), last_fired: null
  }]));

  O.svcStart();   // فاز ۱: آماده‌سازی + اولین tick با وضعیت واقعی بازار

  const st = realMarketStatus(new Date());
  if (!st.open) {
    // ── فاز ۱ (امروز واقعاً بسته است): مسیر «بازار بسته» بدون شبکه ──
    await waitFor(() => calls.cycleDone.length > 0, 10000, 'closed-market cycleDone');
    assert.strictEqual(calls.cycleDone[0], 30, 'closed market should re-check in 30 min');
    assert(calls.ongoing.some(([t, b]) => b.includes('بازار بسته')), 'ongoing should say market closed');
    console.log('  ✅ فاز ۱ — بازار بسته: notifyOngoing + bgCycleDone(30) بدون مصرف شبکه');
  } else {
    console.log('  ⏭️ فاز ۱ رد شد (بازار همین حالا باز است)');
  }

  // ── فاز ۲: بازار باز (به‌زور) — چرخهٔ کامل زنده ──────────────
  calls.notify.length = calls.ongoing.length = calls.cycleDone.length = 0;
  O.marketStatus = () => ({
    open: true, label: 'بازار فعال (تست)', reason_fa: '',
    sessions: ['لندن'], overlap: false, liquid: true
  });
  O.svcTick();
  await waitFor(() => calls.cycleDone.length > 0, 240000, 'full-cycle cycleDone');

  const nextMin = calls.cycleDone[0];
  assert(typeof nextMin === 'number' && nextMin >= 5 && nextMin <= 240,
    'bgCycleDone minutes out of range: ' + nextMin);
  assert(prefs.has('state.last'), 'state.last must persist to shared prefs');
  const st2 = JSON.parse(prefs.get('state.last'));
  assert(st2.ranAt && Array.isArray(st2.analyses), 'state.last malformed');
  assert(calls.ongoing.length > 0, 'ongoing notification summary missing');
  // هشدار قیمت باید در همان چرخهٔ سرویس فعال و اعلان شده باشد (اپ بسته!)
  assert(calls.notify.some(([t]) => t.includes('هشدار قیمت')),
    'price alert must fire from background cycle: ' + JSON.stringify(calls.notify.map(x => x[0])));
  assert.strictEqual(JSON.parse(prefs.get('alerts.json') || '[]').length, 0,
    'non-sticky alert must be consumed after firing');
  const body = calls.ongoing.map(x => x[1]).join(' ');
  assert(body.includes('آخرین تحلیل') || nextMin === 10,
    'ongoing should summarize the cycle (or be the error retry): ' + body);

  // ضداسپام/اعلان‌ها: اگر سیگنال تازه‌ای صادر شده باشد notify صدا زده شده
  const sigs = (st2.judgments || []).filter(j => j.signal).length;
  console.log(`  ✅ فاز ۲ — چرخهٔ کامل زنده: ${st2.analyses.length} نماد تحلیل، ${sigs} سیگنال، cycleDone(${nextMin})`);

  // busy-guard (قطعی): حین یک چرخهٔ در جریان، تیک دوباره باید بی‌اثر باشد
  O.svcTick();                                  // چرخهٔ تازه شروع می‌شود
  assert(ctx.ODIN.S.svcBusy === true, 'a cycle must be running now');
  const before = calls.cycleDone.length;
  O.svcTick(); O.svcTick();                     // باید رد شوند (svcBusy)
  await waitFor(() => calls.cycleDone.length > before, 240000, 'guarded cycle done');
  assert.strictEqual(calls.cycleDone.length, before + 1,
    'exactly one cycle must complete despite triple tick');
  console.log('  ✅ busy-guard — تیک دوباره وسط چرخه بی‌اثر است (دقیقاً یک چرخه)');

  console.log('SMOKE SERVICE OK — رصد پس‌زمینه end-to-end سالم است');
  process.exit(0);                // چرخهٔ معلقِ busy-guard منتظر نمی‌مانیم
})().catch(e => { console.error('❌', e && e.message || e); process.exit(1); });
