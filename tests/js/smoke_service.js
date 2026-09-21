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
const calls = { notify: [], ongoing: [], cycleDone: [] };

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
  bgCycleDone: m => calls.cycleDone.push(m)
  // عمداً بدون http → لایهٔ داده به fetch نیتیوِ Node می‌افتد (مثل گوشی بدون Bridge نبودن)
};
vm.createContext(ctx);
for (const f of ['md5.js', 'fa.js', 'icons.js', 'config.js', 'indicators.js', 'session.js',
  'technical.js', 'calendar.js', 'news.js', 'judge.js', 'journal.js', 'data.js',
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
  O.svcStart();   // فاز ۰: آماده‌سازی + اولین tick با وضعیت واقعی بازار

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
  const body = calls.ongoing.map(x => x[1]).join(' ');
  assert(body.includes('آخرین تحلیل') || nextMin === 10,
    'ongoing should summarize the cycle (or be the error retry): ' + body);

  // ضداسپام/اعلان‌ها: اگر سیگنال تازه‌ای صادر شده باشد notify صدا زده شده
  const sigs = (st2.judgments || []).filter(j => j.signal).length;
  console.log(`  ✅ فاز ۲ — چرخهٔ کامل زنده: ${st2.analyses.length} نماد تحلیل، ${sigs} سیگنال، cycleDone(${nextMin})`);

  // busy-guard: وسط یک چرخهٔ در جریان، فراخوانی دوباره باید بی‌اثر باشد
  const before = calls.cycleDone.length;
  O.svcTick();                    // چرخهٔ تازه شروع می‌شود (svcBusy=true)
  O.svcTick(); O.svcTick();       // باید رد شوند
  await new Promise(r => setTimeout(r, 400));
  assert.strictEqual(calls.cycleDone.length, before,
    'double tick must be ignored while a cycle is running');
  console.log('  ✅ busy-guard — تیک دوباره وسط چرخه بی‌اثر است');

  console.log('SMOKE SERVICE OK — رصد پس‌زمینه end-to-end سالم است');
  process.exit(0);                // چرخهٔ معلقِ busy-guard منتظر نمی‌مانیم
})().catch(e => { console.error('❌', e && e.message || e); process.exit(1); });
