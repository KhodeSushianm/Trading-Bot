/* ══════════════════════════════════════════════════════════════════════
   smoke_onboarding.js — نگهبانِ جریان خوش‌آمدگویی و فیلد کلید لایسنس

   تاریخچهٔ صادقانهٔ این فایل (چون دو بار بازنویسی شد):
     • v0.23.0 — برای «صفحهٔ ورود جوهری» نوشته شد (۱۱۷ بررسی روی
       js/onboarding.js: گام‌ها، onbPlan، قالب‌دهی کلید، توکن‌های onb-*).
     • v0.24.0 — آن صفحه به درخواست مالک حذف و جریان مودال‌محورِ قبلی
       برگردانده شد. پس بخش بزرگی از این تست بی‌موضوع شد.

     ولی «دور ریخته نشد»، چون یک چیز در آن بود که به هیچ جریانِ خاصی
     وابسته نیست و مهم‌ترین یافتهٔ v0.23.0 هم بود:

   🔴 باگ maxlength فیلد کلید لایسنس
       کلید زمان‌دار = XXXX-XXXX-XXXX-XXXX-YYMMDD = ۲۶ نویسه.
       فیلد maxlength="24" داشت، پس paste کردنِ همان کلیدی که سازنده
       می‌دهد ۲ نویسه کم می‌آورد → parseKeyInput فقط ۲۰ هگز می‌دید →
       null → «این کلید نامعتبر است».
       یعنی قابلیت «لایسنس زمان‌دار / مدل اشتراکی» از v0.15.0 تا v0.22.0
       روی اندروید کار نمی‌کرد — و اندروید حالا تنها پلتفرم فعال است.

       چرا ۸ نسخه هیچ تستی نگرفتشان؟ smoke_license.js منطق را «جدا»
       می‌سنجید (parseKeyInput با ورودی کامل) و هرگز نمی‌پرسید «آیا رابط
       کاربری می‌تواند آن ورودی کامل را تولید کند؟». این یک شکافِ دسته‌ای
       است: هرجا موتور و رابط جدا تست شوند، ناسازگاریِ بینشان دیده نمی‌شود.

   پس این فایل الان همان شکاف را می‌بندد — مستقل از اینکه خوش‌آمدگویی
   مودال باشد یا صفحهٔ جدا. اگر روزی دوباره UI عوض شد، این تست باید
   بدون تغییر سبز بماند (به‌شرط اینکه فیلد کلید سر جایش باشد).

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

const APP_JS = read('js/app.js');
// کامنت‌ها را حذف کن: یک عدد یا نام داخل «توضیح» نباید به‌عنوان کد شمرده شود
// (درسی که سه بار در این پروژه تکرار شد)
const APP_CODE = APP_JS.replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1 ');

const ctx = { console, setTimeout };
ctx.globalThis = ctx;
vm.createContext(ctx);
for (const f of ['md5.js', 'fa.js', 'icons.js', 'license.js']) {
  vm.runInContext(read('js/' + f), ctx, { filename: f });
}
const O = ctx.ODIN;

console.log('🔑 تست فیلد کلید لایسنس و جریان خوش‌آمدگویی');

// ══════════════════════════════════════════════════════════════════════
group('۱) maxlength فیلد کلید باید ≥ طول کلید زمان‌دار باشد');
// ══════════════════════════════════════════════════════════════════════
// طول ۲۶ از خودِ موتور «محاسبه» می‌شود، نه هاردکد — وگرنه اگر قالب کلید
// عوض شد این تست کهنه و بی‌صدا پاس می‌ماند.
{
  const deviceId = 'deadbeefcafebabedeadbeefcafebabe';
  const code = O.deviceCodeFromId(deviceId);
  const timed = O.licenseKeyFor(code, '20261231');
  const perm = O.licenseKeyFor(code, null);
  const needLen = Math.max(timed.length, perm.length);
  console.log('    کلید زمان‌دار واقعی : «' + timed + '» (' + timed.length + ' نویسه)');
  console.log('    کلید دائمی واقعی    : «' + perm + '» (' + perm.length + ' نویسه)');
  ok(needLen === 26,
    'طول کلید زمان‌دار تغییر کرده (یافته ' + needLen + ') — سقفِ انتظار این تست باید بازبینی شود');

  // maxlength واقعیِ فیلد کلید در کد
  const m = /id="onb-key"[\s\S]{0,240}?maxlength="(\d+)"/.exec(APP_CODE);
  ok(!!m, 'فیلد #onb-key با maxlength در js/app.js پیدا نشد');
  const domMax = m ? parseInt(m[1], 10) : 0;
  ok(domMax >= needLen,
    '🔴 maxlength فیلد کلید = ' + domMax + ' ولی کلید زمان‌دار ' + needLen +
    ' نویسه است → کاربر نمی‌تواند کلید را کامل وارد کند و «نامعتبر» می‌گیرد ' +
    '(همان باگی که v0.15.0→v0.22.0 را شکست)');
  console.log('    ✓ maxlength = ' + domMax + ' ≥ ' + needLen);

  // فیلد «نام» باید دست‌نخورده بماند (۲۴ مطابق setMaxLength دسکتاپ)
  const mn = /id="onb-name"[\s\S]{0,160}?maxlength="(\d+)"/.exec(APP_CODE);
  ok(!!mn && parseInt(mn[1], 10) === 24,
    'maxlength فیلد نام باید ۲۴ بماند (مطابق name_input.setMaxLength(24) در onboarding.py) — یافته: ' +
    (mn ? mn[1] : 'پیدا نشد'));

  // placeholder باید بخش تاریخ را نشان دهد، وگرنه کاربر نمی‌داند کل رشته لازم است
  const mp = /id="onb-key"[^>]*placeholder="([^"]*)"/.exec(APP_CODE) ||
             /placeholder="([^"]*)"[^>]*id="onb-key"/.exec(APP_CODE);
  ok(!!mp && /YYMMDD/.test(mp[1]),
    'placeholder فیلد کلید باید قالب کامل با بخش تاریخ باشد (یافته: ' + (mp ? mp[1] : '—') + ')');
}

// ══════════════════════════════════════════════════════════════════════
group('۲) سرتاسری: کلیدِ واقعیِ تولیدشده باید از راه رابط فعال شود');
// ══════════════════════════════════════════════════════════════════════
// این گروه «شکافِ موتور در برابر رابط» را می‌بندد: کلید را با خودِ موتور
// می‌سازد، بعد هر سبکِ ورودیِ محتملِ کاربر را «به اندازهٔ maxlength» می‌بُرد
// (دقیقاً کاری که مرورگر می‌کند) و parse/validate می‌کند.
{
  const deviceId = 'deadbeefcafebabedeadbeefcafebabe';
  const code = O.deviceCodeFromId(deviceId);
  const m = /id="onb-key"[\s\S]{0,240}?maxlength="(\d+)"/.exec(APP_CODE);
  const domMax = m ? parseInt(m[1], 10) : 0;

  const cases = [
    ['دائمی — با خط‌تیره', O.licenseKeyFor(code, null)],
    ['زمان‌دار — با خط‌تیره (paste همان چیزی که سازنده می‌دهد)', O.licenseKeyFor(code, '20261231')],
    ['زمان‌دار — بدون خط‌تیره (تایپ دستی)', O.licenseKeyFor(code, '20261231').replace(/-/g, '')],
    ['زمان‌دار — حروف کوچک', O.licenseKeyFor(code, '20261231').toLowerCase()],
    ['زمان‌دار — فاصله به‌جای خط‌تیره', O.licenseKeyFor(code, '20261231').replace(/-/g, ' ')],
    ['زمان‌دار — انقضای دور', O.licenseKeyFor(code, '20991231')],
  ];
  let pass = 0;
  for (const [label, raw] of cases) {
    const typed = raw.slice(0, domMax);              // رفتار واقعی مرورگر
    const parsed = O.parseKeyInput(typed);
    const valid = parsed ? O.validateKey(typed, code) : false;
    ok(valid, '🔴 ' + label + ': با maxlength=' + domMax + ' فعال نشد (parse=' +
      (parsed ? 'ok' : 'null') + ') — کلیدِ معتبرِ موتور از راه رابط رد نمی‌شود');
    if (valid) pass++;
  }
  if (pass === cases.length) console.log('    ✓ هر ' + pass + ' سبکِ ورود با maxlength=' + domMax + ' فعال می‌شود');

  // کلید «نامعتبر» باید واقعاً رد شود (وگرنه تست بالا بی‌معناست)
  const bogus = 'AAAA-BBBB-CCCC-DDDD-991231';
  ok(!O.validateKey(bogus.slice(0, domMax), code),
    'کلید ساختگی باید رد شود — اگر قبول شد یعنی اعتبارسنجی تشریفاتی است');
  const otherDevice = O.licenseKeyFor(O.deviceCodeFromId('ffffffffffffffffffffffffffffffff'), '20261231');
  ok(!O.validateKey(otherDevice.slice(0, domMax), code),
    'کلیدِ دستگاهِ دیگر باید رد شود (قفل دستگاه)');
}

// ══════════════════════════════════════════════════════════════════════
group('۳) جریان خوش‌آمدگویی: زنجیره کامل و قفلِ ردنشدنی');
// ══════════════════════════════════════════════════════════════════════
{
  // هر پنج تابعِ زنجیره باید وجود داشته باشند و به هم وصل باشند.
  // چرا این مهم است: در v0.23.0 این زنجیره با یک صفحهٔ جدا جایگزین شد و
  // بعد برگشت. اگر بازگشت ناقص باشد (مثلاً askBackground صدا زده نشود)،
  // کاربر در میانهٔ خوش‌آمدگویی گیر می‌کند و هیچ تست دیگری نمی‌فهمد.
  const FUNCS = ['showDisclaimer', 'trialGate', 'askName', 'askBackground', 'afterOnboard'];
  for (const fn of FUNCS) {
    ok(new RegExp('function\\s+' + fn + '\\s*\\(').test(APP_CODE),
      'تابع «' + fn + '» در js/app.js وجود ندارد — زنجیرهٔ خوش‌آمدگویی ناقص است');
  }
  // ترتیبِ صدا زدن‌ها
  const CHAIN = [['showDisclaimer', 'trialGate'], ['trialGate', 'askName'],
                 ['askName', 'askBackground'], ['askBackground', 'afterOnboard']];
  for (const [from, to] of CHAIN) {
    const body = (new RegExp('function\\s+' + from + '\\s*\\([\\s\\S]*?\\n  \\}')).exec(APP_CODE);
    ok(!!body && body[0].includes(to),
      '«' + from + '» باید به «' + to + '» برسد، وگرنه جریان خوش‌آمدگویی قطع می‌شود');
  }
  ok(/O\.showActivation\s*=\s*function/.test(APP_CODE),
    'O.showActivation باید موجود باشد (دو صداکننده دارد: گیتِ پایان تریال و کارت لایسنس در تنظیمات)');
  ok((APP_CODE.match(/O\.showActivation\s*\(/g) || []).length >= 2,
    'صداکننده‌های O.showActivation باید وصل بمانند');

  // قفل «خوش‌آمدگویی ردنشدنی»
  ok(/if\s*\(\s*S\.onbStage\s*\)\s*return/.test(APP_CODE),
    'قفل ناوبری «if (S.onbStage) return» حذف شده — خوش‌آمدگویی ردنشدنی نیست');
  // هر مرحله باید onbStage را ست کند و در پایان پاک
  for (const stg of ['trial', 'license', 'name', 'bg']) {
    ok(new RegExp("S\\.onbStage\\s*=\\s*'" + stg + "'").test(APP_CODE),
      "مرحلهٔ «" + stg + "» باید S.onbStage را ست کند");
  }
  ok((APP_CODE.match(/S\.onbStage\s*=\s*null/g) || []).length >= 3,
    'S.onbStage باید در پایان هر مرحله null شود وگرنه اپ برای همیشه قفل می‌ماند');
  console.log('    ✓ زنجیرهٔ ۵ مرحله‌ای + قفل ناوبری + پاک‌کردن onbStage');
}

// ══════════════════════════════════════════════════════════════════════
group('۴) متن‌های ایمنی/حقوقی و اطلاعات ضروریِ خوش‌آمدگویی');
// ══════════════════════════════════════════════════════════════════════
// ⚠️ این‌ها «راهنمای شلوغ‌کننده» نیستند که در v0.22.0 کوتاه شدند؛ محتوای
//   عمدی‌اند. نگهبان لازم است چون آسان‌ترین راهِ سبک‌کردن یک دیالوگ،
//   پاک‌کردن همین متن‌هاست.
{
  const MUST = [
    ['معاملهٔ خودکار نمی‌کند', 'قول ۱: عدم اجرای خودکار معامله'],
    ['به هیچ بروکری وصل نیست', 'قول ۱: عدم اتصال به بروکر'],
    ['حلقهٔ صداقت', 'قول ۲: حلقهٔ صداقت'],
    ['هیچ امتیازی ساخته نمی‌شود', 'قول ۲: امتیاز ساختگی نمی‌دهد'],
    ['سود را تضمین نمی‌کند', 'هشدار تضمین‌نشدن سود'],
    ['پرریسک', 'هشدار پرریسک‌بودن فارکس'],
    ['اعلان ماندگار', 'شفافیت دربارهٔ اعلان ماندگار رصد (الزام حریم خصوصی)'],
    ['معامله همچنان هیچ‌وقت خودکار نیست', 'تأکید مجدد در گام رصد پس‌زمینه'],
    ['@Khode_Sushian', 'راه ارتباطی سازنده برای گرفتن کلید'],
    ['۷ روز', 'هدیهٔ تریال ۷ روزه'],
    ['هر کلید فقط روی همان دستگاه کار می‌کند', 'قفل دستگاه باید به کاربر گفته شود'],
  ];
  for (const [needle, label] of MUST) {
    ok(APP_CODE.includes(needle), 'متن «' + label + '» از جریان خوش‌آمدگویی حذف شده');
  }
  // سه «دلیل» بازگشت به فعال‌سازی باید پیام روشن داشته باشند
  for (const [reason, needle] of [
    ['expired', 'دورهٔ آزمایشی به پایان رسیده'],
    ['tampered', 'ساعت دستگاه به عقب برگشته'],
    ['key-expired', 'لایسنس زمان‌دار منقضی شده'],
  ]) {
    ok(APP_CODE.includes(reason) && APP_CODE.includes(needle),
      'بنر دلیل «' + reason + '» حضور ندارد — کاربر نمی‌فهمد چرا قفل شده');
  }
  console.log('    ✓ ' + MUST.length + ' متن ایمنی/حقوقی + هر ۳ بنر دلیل');
}

// ══════════════════════════════════════════════════════════════════════
group('۵) پسماندِ صفحهٔ ورودِ حذف‌شده نمانده باشد');
// ══════════════════════════════════════════════════════════════════════
// چرا: در v0.23.0 یک ماژول + CSS + ریشهٔ HTML اضافه شد. اگر حذف ناقص باشد،
// یا کد مرده می‌ماند یا بدتر — دو مسیر موازیِ خوش‌آمدگویی هم‌زمان فعال می‌شود.
{
  ok(!fs.existsSync(path.join(WWW, 'js/onboarding.js')),
    'js/onboarding.js هنوز وجود دارد — باید حذف شده باشد (جریان مودال‌محور برگشته)');
  const idx = read('index.html');
  ok(!/id="onb-root"/.test(idx), 'index.html هنوز ریشهٔ #onb-root دارد');
  ok(!/<script src="js\/onboarding\.js">/.test(idx), 'index.html هنوز js/onboarding.js را بار می‌کند');
  // ارجاع مرده در هیچ ماژولی نماند
  const jsFiles = fs.readdirSync(path.join(WWW, 'js')).filter((f) => f.endsWith('.js'));
  for (const f of jsFiles) {
    const src = read('js/' + f).replace(/\/\*[\s\S]*?\*\//g, ' ')
      .replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1 ');
    ok(!/O\.startOnboarding|O\.onbStepHtml|O\.onbPlan|O\.onbFormatLicense/.test(src),
      'js/' + f + ' هنوز به API صفحهٔ ورودِ حذف‌شده ارجاع می‌دهد → ReferenceError در زمان اجرا');
  }
  // CSS: توکن‌ها باید بمانند (پاریتی با theme.py) ولی سلکتورهای #onb-root نه
  const css = read('style.css');
  ok(/--onb-bg\s*:/.test(css) && /--onb-glass\s*:/.test(css),
    'توکن‌های --onb-bg/--onb-glass باید در :root بمانند (قرارداد پاریتی با theme.py)');
  const cssCode = css.replace(/\/\*[\s\S]*?\*\//g, ' ');
  ok(!/^#onb-root\s*\{/m.test(cssCode) && !/^\.onb-step\s*\{/m.test(cssCode),
    'CSS صفحهٔ ورود (سلکتورهای #onb-root/.onb-step) باید حذف شده باشد');
  console.log('    ✓ ماژول/CSS/HTML حذف‌شده، بدون ارجاع مرده، توکن‌های پاریتی حفظ‌شده');
}

// ══════════════════════════════════════════════════════════════════════
group('۶) پاریتی قالب کلید با پایتون (وکتورهای مشترک)');
// ══════════════════════════════════════════════════════════════════════
// این وکتورها با اجرای واقعی src/license.py تولید شده‌اند. جریان مودال‌محور
// auto-format ندارد (parseKeyInput خودش جداکننده‌ها را حذف می‌کند)، پس اینجا
// «نرمال‌سازی» سنجیده می‌شود نه قالب‌دهی نمایشی.
{
  const VECTORS = [
    ['', null],
    ['   ', null],
    ['not-a-key', null],                    // هیچ هگزِ کافی ندارد
    ['ZZZZ-YYYY-XXXX-WWWW', null],          // حروف غیرhex (Z/Y/X/W) → حذف می‌شوند → null
    ['AAAA-BBBB-CCCC-DDDD', 'AAAABBBBCCCCDDDD|'],   // ۱۶ هگزِ معتبرِ قالب (امضا جدا سنجیده می‌شود)
    ['8D8D-32C8-5C9E-AD32-261231', '8D8D32C85C9EAD32|261231'],
    ['8d8d32c85c9ead32261231', '8D8D32C85C9EAD32|261231'],
    ['8d8d 32c8 5c9e ad32 261231', '8D8D32C85C9EAD32|261231'],
    ['6006-693F-3945-F0C3', '6006693F3945F0C3|'],
    ['۸D۸D-32C8-5C9E-AD32-261231', null],  // رقم فارسی → hex نیست → null
  ];
  let bad = 0;
  for (const [inp, want] of VECTORS) {
    const p = O.parseKeyInput(inp);
    const got = p ? p.key + '|' + (p.expiry8 ? p.expiry8.slice(2) : '') : null;
    if (got !== want) { bad++; console.log('    ✗ «' + inp + '» → ' + got + ' (انتظار ' + want + ')'); }
  }
  ok(bad === 0, bad + ' وکتورِ parseKeyInput با پایتون نمی‌خواند');
  if (!bad) console.log('    ✓ هر ' + VECTORS.length + ' وکتور (شامل جداکننده‌های مختلف و رقم فارسی)');
  // انقضای نامعتبر باید رد شود (۳۱ فوریه، ماه ۱۳)
  ok(O.parseKeyInput('8D8D32C85C9EAD32' + '260231') === null, '۳۱ فوریه باید رد شود');
  ok(O.parseKeyInput('8D8D32C85C9EAD32' + '261331') === null, 'ماه ۱۳ باید رد شود');
}

console.log('\n' + '═'.repeat(56));
if (failures) {
  console.log('✗ SMOKE ONBOARDING FAILED — ' + failures + ' از ' + checks + ' بررسی شکست خورد');
  process.exit(1);
}
console.log('✅ SMOKE ONBOARDING OK — ' + checks +
  ' بررسی پاس؛ کلید لایسنس (دائمی و زمان‌دار) از راه رابط واقعاً فعال می‌شود و زنجیرهٔ خوش‌آمدگویی کامل است');
