/* اسموک‌تست صفحهٔ «دربارهٔ ما» — رندر بدون DOM، بررسی حق نشر و امضا.
 * اجرا: node tests/js/smoke_about.js  (از ریشهٔ مخزن) */
'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');

const WWW = path.join(__dirname, '..', '..', 'android', 'app', 'src', 'main', 'assets', 'www', 'js');
const ctx = { console };
ctx.globalThis = ctx;
vm.createContext(ctx);
for (const f of ['fa.js', 'ui.js']) {
  vm.runInContext(fs.readFileSync(path.join(WWW, f), 'utf8'), ctx, { filename: f });
}
const O = ctx.ODIN;
assert(O && typeof O.renderAbout === 'function', 'renderAbout missing');

const S = {
  version: '0.11.0',
  settings: {
    user_name: 'سوشیان', judge_enabled: true, min_score: 7, veto: {},
    fund_enabled: true, news_enabled: true, tv_enabled: true,
    auto_refresh_enabled: true, auto_refresh_min: 15, notify_enabled: true
  },
  cfg: { judge: { veto: {} } }
};

const about = O.renderAbout(S);
assert(about.includes('دربارهٔ ما'), 'page title missing');
assert(about.includes('Sushian'), 'creator name missing');
assert(about.includes('© 2026 Sushian — All rights reserved.'), 'copyright line missing');
assert(about.includes('CN=Sushian, OU=ODIN Assistant, O=Sushian, C=IR'), 'cert subject missing');
assert(about.includes('۰.۱۱.۰'), 'persian version missing');
assert(about.includes('KhodeSushianm/Trading-Bot/releases'), 'official source link missing');
assert(about.includes('غیرخودکار'), 'disclaimer missing');

const settings = O.renderSettings(S);
assert(settings.includes('data-tab="about"'), 'settings entry to about missing');
assert(!settings.includes('مسئولیت هر معامله'), 'long disclaimer should be moved out of settings');

console.log('SMOKE ABOUT OK — ' + about.length + ' chars rendered');
