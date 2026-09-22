/* ══════════════════════════════════════════════════════════════════════
   smoke_onboarding.js — صفحهٔ ورود اندروید (پورت onboarding.py دسکتاپ)

   چرا این تست وجود دارد:
     در v0.23.0 جریان خوش‌آمدگویی اندروید از «۵ مودال زنجیره‌ای» به یک
     صفحهٔ جوهری پیوسته تبدیل شد. حین همین پورت یک باگ بحرانی پیدا شد که
     «هیچ» تستی نمی‌گرفتشان:

       فیلد کلید لایسنس maxlength="24" داشت، ولی کلید «زمان‌دار» ۲۶ نویسه است
       (XXXX-XXXX-XXXX-XXXX-YYMMDD). کاربر دو نویسهٔ آخرِ تاریخ را نمی‌توانست
       تایپ کند → parseKeyInput هیچ‌وقت ۲۲ هگز نمی‌دید → null → «کلید نامعتبر».

       یعنی قابلیت «لایسنس زمان‌دار/اشتراکی» که در v0.15.0 اضافه شده بود،
       روی اندروید از همان ابتدا کار نمی‌کرد. smoke_license.js هم نمی‌گرفتشان
       چون منطق را «جدا» می‌سنجد (parseKeyInput با ورودی کامل) و هرگز نمی‌پرسد
       «آیا رابط کاربری می‌تواند آن ورودی کامل را تولید کند؟».

     گروه ۲ همین تست آن شکاف را می‌بندد: کلید را واقعاً تولید می‌کند،
     قالب‌دهی می‌کند، به اندازهٔ maxlength می‌بُرد، و بعد اعتبارسنجی.

   اجرا:  node tests/js/smoke_onboarding.js
   ══════════════════════════════════════════════════════════════════════ */
'use strict';

const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const WWW = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www');
const read = (f) => fs.readFileSync(path.join(WWW, f), 'utf8');

let failures = 0, checks = 0;
function ok(cond, msg) {
  checks++;
  if (!cond) { failures++; console.log('  ✗ ' + msg); }
  return !!cond;
}
function group(t) { console.log('\n── ' + t + ' ' + '─'.repeat(Math.max(0, 56 - t.length))); }

// ── بارگذاری ماژول‌ها در vm (بدون DOM — لایهٔ خالص را می‌سنجیم) ─────────
const ctx = { console, setTimeout };
ctx.globalThis = ctx;
vm.createContext(ctx);
for (const f of ['md5.js', 'fa.js', 'icons.js', 'license.js', 'config.js', 'components.js',
  'onboarding.js']) {
  vm.runInContext(read('js/' + f), ctx, { filename: f });
}
const O = ctx.ODIN;
if (!O || !O.startOnboarding) {
  console.error('✗ ماژول onboarding.js بار نشد یا O.startOnboarding تعریف نشده');
  process.exit(2);
}

console.log('🚪 تست صفحهٔ ورود اندروید — js/onboarding.js');

// ══════════════════════════════════════════════════════════════════════
group('۱) قالب‌دهی کلید — برابری بایت‌به‌بایت با onboarding.py');
// ══════════════════════════════════════════════════════════════════════
// وکتورها با «اجرای واقعی» الگوریتمِ src/ui/onboarding.py::_fmt_license در
// پایتون تولید شدند (نه حدس). JS باید دقیقاً همان خروجی را بدهد، چون
// سازنده کلید را با src/license.py می‌سازد و کاربر اینجا تایپ می‌کند.
const VECTORS = [
  ['', ''],
  [' ', ''],
  ['abc', 'ABC'],
  ['ABCD', 'ABCD'],
  ['abcd1234', 'ABCD-1234'],
  ['8d8d32c85c9ead32261231', '8D8D-32C8-5C9E-AD32-261231'],
  ['8D8D-32C8-5C9E-AD32-261231', '8D8D-32C8-5C9E-AD32-261231'],
  ['8d8d 32c8 5c9e ad32 261231', '8D8D-32C8-5C9E-AD32-261231'],
  ['6006-693F-3945-F0C3', '6006-693F-3945-F0C3'],
  ['6006693f3945f0c3', '6006-693F-3945-F0C3'],
  ['abcdef0123456789extra', 'ABCD-EF01-2345-6789-EXTRA'],
  ['abc۱۲۳def', 'ABCD-EF'],                 // رقم فارسی باید حذف شود (isascii)
  ['ab-cd-ef-۰۱-۲۳', 'ABCD-EF'],
  ['a', 'A'],
  ['ab', 'AB'],
  ['abcde', 'ABCD-E'],
  ['A1B2C3D4E5F60718', 'A1B2-C3D4-E5F6-0718'],
  ['A1B2C3D4E5F6071826', 'A1B2-C3D4-E5F6-0718-26'],
  ['A1B2C3D4E5F60718261231', 'A1B2-C3D4-E5F6-0718-261231'],
  ['!!!@@@###', ''],
  ['0000-0000-0000-0000-000000', '0000-0000-0000-0000-000000'],
];
{
  let bad = 0;
  for (const [inp, want] of VECTORS) {
    const got = O.onbFormatLicense(inp);
    if (got !== want) { bad++; console.log(`    ✗ «${inp}» → «${got}» (انتظار «${want}»)`); }
  }
  ok(bad === 0, `${bad} از ${VECTORS.length} وکتور قالب‌دهی با پایتون نمی‌خواند`);
  if (!bad) console.log(`  ✓ هر ${VECTORS.length} وکتور با onboarding.py یکی است`);
  // ورودی‌های پرت نباید استثنا بدهند
  for (const v of [null, undefined, 123, {}, []]) {
    let threw = null;
    try { O.onbFormatLicense(v); } catch (e) { threw = e.message; }
    ok(threw === null, `onbFormatLicense(${JSON.stringify(v)}) استثنا داد: ${threw}`);
  }
}

// ══════════════════════════════════════════════════════════════════════
group('۲) نگهبانِ باگِ maxlength — کلید زمان‌دار باید واقعاً قابل ورود باشد');
// ══════════════════════════════════════════════════════════════════════
// این گروه همان باگی را قفل می‌کند که v0.15.0 → v0.22.0 را شکسته بود.
// به‌صورت سرتاسری: کلید واقعی تولید کن → قالب‌دهی کن → به اندازهٔ maxlength ببر →
// parse/validate کن. اگر maxlength کوچک باشد، اینجا قرمز می‌شود.
{
  const MAXLEN = O.ONB_KEY_MAXLEN;
  ok(typeof MAXLEN === 'number' && MAXLEN >= 26,
    `ONB_KEY_MAXLEN باید ≥ ۲۶ باشد (طول کلید زمان‌دار) — یافته: ${MAXLEN}`);

  // maxlength واقعی در HTML رندرشده
  const html = O.onbStepHtml('activate', { deviceCode: 'ABCD-EF01-2345' });
  const mAttr = /id="onb-key"[\s\S]{0,220}?maxlength="(\d+)"/.exec(html);
  ok(!!mAttr, 'فیلد #onb-key با maxlength در HTML گام فعال‌سازی پیدا نشد');
  const domMax = mAttr ? parseInt(mAttr[1], 10) : 0;
  ok(domMax >= 26, `maxlength فیلد کلید = ${domMax} ولی کلید زمان‌دار ۲۶ نویسه است`);
  ok(domMax === MAXLEN, `maxlength فیلد (${domMax}) با ONB_KEY_MAXLEN (${MAXLEN}) یکی نیست`);

  // با کلیدهای «واقعیِ تولیدشده» توسط خودِ license.js بسنج
  const deviceId = 'deadbeefcafebabedeadbeefcafebabe';
  const code = O.deviceCodeFromId(deviceId);
  const keys = [
    ['دائمی', O.licenseKeyFor(code, null)],
    ['زمان‌دار', O.licenseKeyFor(code, '20261231')],
    ['زمان‌دار (انقضای دور)', O.licenseKeyFor(code, '20991231')],
  ];
  for (const [label, raw] of keys) {
    const shown = O.onbFormatLicense(raw);
    ok(shown.length <= domMax,
      `کلید ${label}: طول قالب‌دار ${shown.length} > maxlength ${domMax} — کاربر نمی‌تواند کامل تایپ کند`);
    // شبیه‌سازی رفتار مرورگر: ورودی بیش از maxlength بُریده می‌شود
    const typed = shown.slice(0, domMax);
    const parsed = O.parseKeyInput(typed);
    ok(!!parsed, `کلید ${label}: پس از برشِ maxlength، parseKeyInput → null (یعنی «کلید نامعتبر»)`);
    const valid = parsed ? O.validateKey(typed, code) : false;
    ok(valid, `کلید ${label}: با کلید معتبرِ تولیدشده، validateKey شکست خورد`);
    if (valid) console.log(`  ✓ کلید ${label}: «${shown}» (${shown.length} نویسه) → فعال می‌شود`);
  }

  // placeholder هم باید قالب کامل را نشان دهد (وگرنه کاربر نمی‌داند تاریخ لازم است)
  ok(/XXXX-XXXX-XXXX-XXXX-YYMMDD/.test(html),
    'placeholder باید قالب کامل با بخش تاریخ باشد (کاربر باید بداند کلید زمان‌دار ۶ رقم تاریخ دارد)');
}

// ══════════════════════════════════════════════════════════════════════
group('۳) onbPlan — کدام گام‌ها برای کدام کاربر');
// ══════════════════════════════════════════════════════════════════════
{
  const plan = (o) => O.onbPlan(o).join(',');
  const fresh = { disclaimerDone: false, nameDone: false, licensed: false, trial: null, bgDone: false };
  ok(plan(fresh) === 'welcome,name,activate,background,done',
    'کاربر تازه باید هر ۵ گام را ببیند — یافته: ' + plan(fresh));

  ok(plan({ ...fresh, disclaimerDone: true }) === 'name,activate,background,done',
    'کاربری که سلب‌مسئولیت را دیده نباید دوباره ببیند — یافته: ' + plan({ ...fresh, disclaimerDone: true }));

  ok(plan({ ...fresh, nameDone: true, disclaimerDone: true }) === 'activate,background,done',
    'کاربر قدیمی با نام ذخیره‌شده نباید گام نام را ببیند');

  ok(plan({ ...fresh, licensed: true }) === 'welcome,name,background,done',
    'کاربر دارای لایسنس نباید گام فعال‌سازی را ببیند — یافته: ' + plan({ ...fresh, licensed: true }));

  ok(plan({ ...fresh, trial: { active: true } }) === 'welcome,name,background,done',
    'کاربر با تریال فعال نباید گام فعال‌سازی را ببیند');

  ok(plan({ ...fresh, trial: { active: false, exists: true } }) === 'welcome,name,activate,background,done',
    'تریال «تمام‌شده» باید گام فعال‌سازی را نشان دهد');

  const all = { disclaimerDone: true, nameDone: true, licensed: true, trial: { active: true }, bgDone: true };
  ok(plan(all) === 'done', 'کاربری که همه‌چیز را تمام کرده باید فقط گام پایان را ببیند');

  // ورودی‌های پرت
  for (const v of [null, undefined, {}]) {
    let p = null, threw = null;
    try { p = O.onbPlan(v); } catch (e) { threw = e.message; }
    ok(!threw && Array.isArray(p) && p[p.length - 1] === 'done',
      `onbPlan(${JSON.stringify(v)}) باید آرایه‌ای با پایان «done» بدهد — یافت: ${JSON.stringify(p)} / ${threw}`);
  }
  console.log('  ✓ ۹ سناریوی plan + ۳ ورودی پرت');
}

// ══════════════════════════════════════════════════════════════════════
group('۴) رندر هر ۵ گام — بدون ایموجی، با کلاس‌ها و کنش‌های درست');
// ══════════════════════════════════════════════════════════════════════
{
  const EMOJI = O.EMOJI_RE || /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{2B00}-\u{2BFF}]/u;
  const steps = O.ONB_STEPS;
  ok(steps.length === 5, 'ONB_STEPS باید ۵ گام داشته باشد، دارد: ' + steps.length);

  const ctxs = {
    welcome: {},
    name: { currentName: 'سوشیان' },
    activate: { deviceCode: 'ABCD-EF01-2345', reason: '', gift: true },
    background: {},
    done: { doneMsg: 'لایسنس فعال شد' },
  };
  for (const s of steps) {
    const h = O.onbStepHtml(s, ctxs[s]);
    ok(h.length > 40, `گام «${s}» خروجی تقریباً خالی داد (${h.length} نویسه)`);
    const em = EMOJI.exec(h);
    ok(!em, `گام «${s}» در خروجی ایموجی دارد: ${JSON.stringify(em && em[0])}`);
    ok(h.includes('<svg'), `گام «${s}» هیچ آیکون SVG ندارد (قرارداد v0.13.0: صفر ایموجی، آیکون SVG)`);
    ok(h.includes(`data-step="${s}"`), `گام «${s}» باید data-step="${s}" داشته باشد`);
    ok(h.includes('onb-title'), `گام «${s}» عنوان ندارد`);
  }

  // کنش‌ها (data-onb) — هر کنشی که لایهٔ DOM هندل می‌کند باید در HTML هم باشد
  const act = O.onbStepHtml('activate', ctxs.activate);
  for (const a of ['copy', 'share', 'trial', 'activate']) {
    ok(act.includes(`data-onb="${a}"`), `گام فعال‌سازی کنش «${a}» ندارد`);
  }
  ok(O.onbFooterHtml('background').includes('data-onb="skip-bg"'),
    'گام رصد پس‌زمینه باید دکمهٔ «فعلاً نه» داشته باشد (اختیاری‌بودن باید واقعی باشد)');
  ok(O.onbFooterHtml('background').includes('data-onb="enable-bg"'),
    'گام رصد پس‌زمینه باید دکمهٔ «شروع رصد» داشته باشد');
  for (const s of ['welcome', 'name', 'done']) {
    ok(O.onbFooterHtml(s).includes('onb-primary'), `گام «${s}» دکمهٔ اصلی ندارد`);
  }
  ok(O.onbPrimary('activate') === null,
    'گام فعال‌سازی نباید دکمهٔ اصلیِ footer داشته باشد (دکمه‌هایش داخل گام‌اند: trial/activate)');
  console.log('  ✓ ۵ گام رندر شد · ایموجی صفر · کنش‌ها کامل');
}

// ══════════════════════════════════════════════════════════════════════
group('۵) متن‌های حقوقی/ایمنی و اطلاعات ضروری حفظ شده باشند');
// ══════════════════════════════════════════════════════════════════════
// ⚠️ کوتاه‌کردن متن در v0.22.0 انجام شد، ولی متن حقوقی و ایمنی «عمداً»
//   مستثنا بود. این گروه قفل می‌کند که پورت صفحهٔ ورود هم آن‌ها را نبرده باشد.
{
  const wel = O.onbStepHtml('welcome', {});
  for (const [needle, label] of [
    ['معاملهٔ خودکار نمی‌کند', 'قول ۱: عدم اجرای خودکار معامله'],
    ['به هیچ بروکری وصل نیست', 'قول ۱: عدم اتصال به بروکر'],
    ['حلقهٔ صداقت', 'قول ۲: حلقهٔ صداقت'],
    ['هیچ امتیازی ساخته نمی‌شود', 'قول ۲: امتیاز ساختگی نمی‌دهد'],
    ['سود را تضمین نمی‌کند', 'هشدار تضمین‌نشدن سود'],
    ['پرریسک', 'هشدار پرریسک‌بودن فارکس'],
  ]) {
    ok(wel.includes(needle), `متن ایمنی «${label}» از گام خوش‌آمدگویی حذف شده`);
  }

  const bg = O.onbStepHtml('background', {});
  for (const [needle, label] of [
    ['اعلان ماندگار', 'شفافیت دربارهٔ اعلان ماندگار (الزام حریم خصوصی)'],
    ['خاموشش کن', 'راه خاموش‌کردن رصد'],
    ['باتری', 'درخواست مجوز باتری'],
    ['معامله همچنان خودکار نیست', 'تأکید مجدد بر غیرخودکار بودن'],
  ]) {
    ok(bg.includes(needle), `«${label}» از گام رصد پس‌زمینه حذف شده`);
  }

  const act = O.onbStepHtml('activate', { deviceCode: 'ABCD-EF01-2345' });
  ok(act.includes('@Khode_Sushian'), 'راه ارتباطی سازنده باید در گام فعال‌سازی باشد');
  ok(act.includes('ABCD-EF01-2345'), 'کد دستگاه باید نمایش داده شود');
  ok(act.includes('آفلاین'), 'باید گفته شود فعال‌سازی آفلاین است (حریم خصوصی)');
  ok(act.includes('۷ روز'), 'پیشنهاد تریال ۷ روزه باید باشد');

  // هر سه «دلیل» بازگشت به فعال‌سازی باید بنر مخصوص خودش را بگیرد
  for (const [reason, needle] of [
    ['expired', 'دورهٔ آزمایشی به پایان رسیده'],
    ['tampered', 'ساعت دستگاه به عقب برگشته'],
    ['key-expired', 'لایسنس زمان‌دار منقضی شده'],
  ]) {
    const h = O.onbStepHtml('activate', { deviceCode: 'X', reason });
    ok(h.includes(needle), `بنر دلیل «${reason}» رندر نشد — کاربر نمی‌فهمد چرا قفل شده`);
    ok(h.includes('onb-note bad'), `بنر «${reason}» باید استایل هشدار (bad) داشته باشد`);
  }
  console.log('  ✓ متن‌های ایمنی/حقوقی + هر ۳ بنر دلیل حاضرند');
}

// ══════════════════════════════════════════════════════════════════════
group('۶) توکن‌های onb-* واقعاً مصرف می‌شوند (نه حاضرِ بلااستفاده)');
// ══════════════════════════════════════════════════════════════════════
// مشکل v0.21.0: توکن‌های onb-bg/onb-glass به style.css اضافه شدند ولی هیچ
// سلکتوری مصرفشان نکرد — یعنی «پورت شد» ولی عملاً نیمه‌کاره بود.
{
  const css = fs.readFileSync(path.join(WWW, 'style.css'), 'utf8');
  ok(/#onb-root\s*\{/.test(css), '#onb-root در style.css تعریف نشده');
  ok(/var\(--onb-bg\)/.test(css), '--onb-bg تعریف شده ولی مصرف نمی‌شود (بلااستفاده)');

  // --onb-glass یک «رنگ» است که با آلفا مصرف می‌شود؛ CSS نمی‌تواند
  // rgba(var(--hex), .08) بنویسد، پس به‌صورت rgba(255,255,255,.0X) ظاهر
  // می‌شود. نگهبان درست: آن مقدارِ روشن باید با مقدارِ توکن یکی باشد.
  const glassTok = /--onb-glass\s*:\s*(#[0-9A-Fa-f]{6})/.exec(css);
  ok(!!glassTok, '--onb-glass در :root پیدا نشد');
  if (glassTok) {
    const hex = glassTok[1].toLowerCase();
    const rgb = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
    const expect = rgb.join(',');
    const uses = [...css.matchAll(/rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*0?\.0[5-9]\d*\s*\)/g)]
      .map((m) => [m[1], m[2], m[3]].join(','));
    const inOnbBlock = css.slice(css.indexOf('#onb-root {'));
    const onbUses = [...inOnbBlock.matchAll(/rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*0?\.0[5-9]\d*\s*\)/g)]
      .map((m) => [m[1], m[2], m[3]].join(','));
    ok(onbUses.length >= 4,
      `بلوک صفحهٔ ورود باید ≥۴ جا شیشهٔ سفیدِ کم‌آلفا مصرف کند (یافته: ${onbUses.length})`);
    ok(onbUses.every((u) => u === expect),
      `مقادیر rgba در بلوک صفحهٔ ورود با --onb-glass (${expect}) نمی‌خواند: ${[...new Set(onbUses)].join(' / ')}`);
    console.log(`  ✓ ${onbUses.length} مصرفِ شیشه، همه با --onb-glass (${hex}) هم‌مقدار · ${uses.length} مورد در کل CSS`);
  }

  // شفق صفحهٔ ورود باید از توکن‌های aurora بیاید، نه رنگ هاردکد
  const onbCss = css.slice(css.indexOf('#onb-root {'));
  for (const tok of ['--aurora-indigo', '--aurora-cyan', '--aurora-pink', '--brand', '--console-green', '--console-red']) {
    ok(onbCss.includes(`var(${tok})`), `بلوک صفحهٔ ورود باید از var(${tok}) استفاده کند`);
  }
  // دسترسی‌پذیری: مثل #bg باید با no-anim و prefers-reduced-motion خاموش شود
  ok(/body\.no-anim #onb-root::before/.test(css), 'شفق صفحهٔ ورود باید با body.no-anim خاموش شود');
  ok(/prefers-reduced-motion[\s\S]{0,300}?#onb-root/.test(css), 'شفق صفحهٔ ورود باید به prefers-reduced-motion احترام بگذارد');
  ok(/@keyframes onbShake/.test(css), 'انیمیشن لرزش خطا (onbShake) باید تعریف شده باشد');
  ok(/body\.no-anim \.onb-shake/.test(css), 'لرزش هم باید با no-anim خاموش شود');
}

// ══════════════════════════════════════════════════════════════════════
group('۷) سیم‌کشی — index.html و app.js');
// ══════════════════════════════════════════════════════════════════════
{
  const idx = fs.readFileSync(path.join(WWW, 'index.html'), 'utf8');
  ok(/id="onb-root"/.test(idx), 'index.html باید ریشهٔ #onb-root را داشته باشد');
  // ⚠️ ترتیب را از «تگ اسکریپت» بسنج، نه از نخستین اشاره به نام فایل.
  //   نسخهٔ اول این تست indexOf('js/onboarding.js') را می‌گرفت و به «کامنتِ
  //   توضیحی» بالای #onb-root می‌خورد — پس ترتیب را اشتباه گزارش می‌کرد.
  //   (همان درسی که در smoke_theme_parity برای کامنت‌های JS گرفتیم.)
  const scriptOrder = [...idx.matchAll(/<script src="js\/([\w.]+)\.js"><\/script>/g)].map((m) => m[1]);
  ok(scriptOrder.length >= 15, 'فهرست تگ‌های اسکریپت از index.html خوانده نشد (یافته: ' + scriptOrder.length + ')');
  ok(scriptOrder.includes('onboarding'), 'index.html باید js/onboarding.js را بار کند');
  const pos = (n) => scriptOrder.indexOf(n);
  ok(pos('onboarding') < pos('app'),
    'onboarding.js باید «پیش از» app.js بار شود (app.js به O.startOnboarding نیاز دارد) — ' +
    'ترتیب یافت: ' + scriptOrder.slice(-5).join(' → '));
  ok(pos('components') < pos('onboarding'),
    'components.js باید پیش از onboarding.js بار شود (به O.copyText نیاز دارد)');
  ok(pos('license') < pos('onboarding'),
    'license.js باید پیش از onboarding.js بار شود (به O.validateKey/O.licActivate نیاز دارد)');
  ok(pos('icons') < pos('onboarding'),
    'icons.js باید پیش از onboarding.js بار شود (به O.ico نیاز دارد)');
  console.log('  ✓ ترتیب بارگذاری: ' + scriptOrder.slice(-4).join(' → '));

  const app = fs.readFileSync(path.join(WWW, 'js/app.js'), 'utf8');
  const code = app.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1');
  ok(/O\.startOnboarding\s*\(/.test(code), 'app.js باید O.startOnboarding را صدا بزند');
  ok(/startOnboardingFlow\s*\(/.test(code), 'app.js باید startOnboardingFlow را داشته باشد');
  // زنجیرهٔ مودالِ قدیمی باید رفته باشد (وگرنه دو مسیر موازی وجود دارد)
  for (const dead of ['function showDisclaimer', 'function trialGate', 'function askName', 'function askBackground']) {
    ok(!code.includes(dead), `«${dead}» هنوز در app.js است — زنجیرهٔ مودال قدیمی باید حذف شده باشد`);
  }
  // ولی امضای عمومی که صداکننده دارد باید بماند
  ok(/O\.showActivation\s*=\s*function\s*\(onDone,\s*reason\)/.test(code),
    'O.showActivation باید با همان امضای قدیمی (onDone, reason) باقی بماند — دو صداکننده دارد');
  ok((code.match(/O\.showActivation\s*\(/g) || []).length >= 2,
    'صداکننده‌های O.showActivation (پایان تریال و کارت لایسنس تنظیمات) باید وصل بمانند');
  // قفل ناوبری باید حفظ شده باشد (خوش‌آمدگویی ردنشدنی است)
  ok(/if \(S\.onbStage\) return/.test(code),
    'قفل «خوش‌آمدگویی ردنشدنی» (if (S.onbStage) return) باید در ناوبری باقی بماند');
  console.log('  ✓ ترتیب بارگذاری، حذف زنجیرهٔ قدیمی، حفظ امضای عمومی و قفل ناوبری');
}

console.log('\n' + '═'.repeat(56));
if (failures) {
  console.log(`✗ SMOKE ONBOARDING FAILED — ${failures} از ${checks} بررسی شکست خورد`);
  process.exit(1);
}
console.log(`✅ SMOKE ONBOARDING OK — ${checks} بررسی پاس؛ صفحهٔ ورود با onboarding.py هم‌رفتار است و کلید زمان‌دار واقعاً قابل ورود است`);
