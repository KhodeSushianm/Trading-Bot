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
for (const f of ['fa.js', 'icons.js', 'components.js', 'onboarding.js', 'ui.js']) {
  vm.runInContext(fs.readFileSync(path.join(WWW, f), 'utf8'), ctx, { filename: f });
}
const O = ctx.ODIN;
assert(O && typeof O.renderAbout === 'function', 'renderAbout missing');

const S = {
  version: '0.19.0',
  settings: {
    user_name: 'سوشیان', judge_enabled: true, min_score: 7, veto: {},
    fund_enabled: true, news_enabled: true, tv_enabled: true,
    auto_refresh_enabled: true, auto_refresh_min: 15, notify_enabled: true
  },
  cfg: { judge: { veto: {} } }
};

const about = O.renderAbout(S);
assert(about.includes('دربارهٔ ما'), 'page title missing');
assert(about.includes('Sushian Khoshkhani'), 'creator name missing');
assert(about.includes('© 2026 Sushian Khoshkhani — All rights reserved.'), 'copyright line missing');
assert(about.includes('CN=Sushian Khoshkhani, OU=ODIN Assistant, O=Sushian Khoshkhani, C=IR'), 'cert subject missing');
assert(about.includes('۰.۱۹.۰'), 'persian version missing');
// اثر انگشت کلید امضای v0.13.0 (کلید تازه به نام Sushian Khoshkhani)
assert(about.includes('bd11159e003b55b9ae53cd26c192dc6b2bea2840c787fddbd0f523a947cb5189'), 'cert SHA-256 fingerprint missing');
// بدون ایموجی — همه‌جا آیکون SVG (v0.13.0)
assert(!O.EMOJI_RE.test(about), 'emoji left in about page');
// برنامه با هدف فروش است — هیچ لینک دانلود/گیت‌هابی نباید در اپ باشد؛
// تنها لینک خارجی مجاز: تلگرام رسمی سازنده (v0.14.2)
assert(!about.includes('github.com'), 'github link must be removed from about page');
assert(!about.includes('KhodeSushianm'), 'repo link must be removed from about page');
const exts = about.match(/data-ext="([^"]+)"/g) || [];
assert(exts.length > 0, 'creator telegram link missing');
assert(exts.every(x => x === 'data-ext="https://t.me/Khode_Sushian"'),
  'only the official telegram link is allowed on about page: ' + exts.join(','));
assert(about.includes('@Khode_Sushian'), 'telegram id missing');
assert(about.includes('تیم پروژه'), 'team card missing');
assert(about.includes('مدیر پروژه') && about.includes('Reza Khoshkhani'), 'project manager missing');
assert(about.includes('اسپانسر پروژه') && about.includes('Karen Khoshkhani'), 'sponsor missing');
assert(about.includes('مستقیماً از خودِ سازنده'), 'official-source note (no link) missing');
assert(about.includes('غیرخودکار'), 'disclaimer missing');

const settings = O.renderSettings(S);
assert(settings.includes('data-tab="about"'), 'settings entry to about missing');
assert(!settings.includes('مسئولیت هر معامله'), 'long disclaimer should be moved out of settings');
assert(!O.EMOJI_RE.test(settings), 'emoji left in settings page');
assert(settings.includes('background_enabled'), 'background-monitor switch missing in settings');
assert(settings.includes('کد دستگاه'), 'license/device-code card missing in settings (v0.14.0)');

console.log('SMOKE ABOUT OK — ' + about.length + ' chars rendered');
