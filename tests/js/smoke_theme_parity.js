/* ══════════════════════════════════════════════════════════════════════
   smoke_theme_parity.js — نگهبان پاریتی توکن‌های تم بین دو پلتفرم

   چرا این تست وجود دارد (مستند، نه تعارف):
     در v0.20.0 بازطراحی «Aurora Glass 2.0» به تم دسکتاپ ۱۲ توکن تازه اضافه
     کرد (amber، brand، aurora، console و onb) و ۸ ویجت نو آورد. هیچ‌کدام به
     اندروید پورت نشد، ولی هدرِ خودِ android/style.css هنوز ادعا می‌کرد
     «دقیقاً همان توکن‌های src/ui/theme.py نسخهٔ دسکتاپ». یعنی ادعای پاریتی
     در کد نوشته شده بود و هیچ تستی آن را نمی‌سنجید — run_parity.js فقط منطق
     موتور (اندیکاتور/داور/ژورنال) را می‌سنجد، ظاهر را نه.
     نتیجه: سه مقدار متفاوت برای amber در کدبیس وجود داشت
       theme.py   #E0A83C
       style.css  #D98E04   (هاردکد در .ico.c-amber)
       sharecard.js #E8B84B
     این تست آن رانش را قفل می‌کند.

   چه چیزی سنجیده می‌شود:
     ۱) هر توکن رنگ/شعاع/آلفا در dataclass Theme باید معادل kebab-case در
        :rootِ style.css داشته باشد.
     ۲) مقدارها باید دقیقاً یکی باشند (hex بدون حساسیت به بزرگی/کوچکی).
     ۳) هیچ رنگ معناییِ هاردکدی در کلاس‌های .c-* نباید با توکنش فرق کند.
     ۴) پالت sharecard.js (که ادعای برابری با تم دارد) هم باید هم‌عدد باشد.
     ۵) اجزای بصری Aurora Glass 2.0 باید واقعاً در اندروید پیاده باشند
        (کنسول‌کارت، کارت سیگنال ساختاریافته، KPI، ستاره، چیپ، شفق).

   اجرا:  node tests/js/smoke_theme_parity.js
   ══════════════════════════════════════════════════════════════════════ */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const THEME_PY = path.join(ROOT, 'src', 'ui', 'theme.py');
const STYLE_CSS = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www', 'style.css');
const SHARECARD_JS = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www', 'js', 'sharecard.js');
const COMPONENTS_JS = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www', 'js', 'components.js');
const UI_JS = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www', 'js', 'ui.js');
const INDEX_HTML = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www', 'index.html');

let failures = 0;
let checks = 0;
function ok(cond, msg) {
  checks++;
  if (!cond) { failures++; console.log('  ✗ ' + msg); }
  return !!cond;
}
function group(title) { console.log('\n── ' + title + ' ' + '─'.repeat(Math.max(0, 56 - title.length))); }

function read(f, what) {
  if (!fs.existsSync(f)) { console.error('✗ فایل پیدا نشد: ' + what + ' → ' + f); process.exit(2); }
  return fs.readFileSync(f, 'utf8');
}

const kebab = (s) => s.replace(/_/g, '-');
const normHex = (s) => {
  const m = /^#([0-9a-f]{6})$/i.exec(String(s).trim());
  return m ? '#' + m[1].toLowerCase() : null;
};

// ── ۱. استخراج توکن‌ها از dataclass Theme در theme.py ──────────────────
// فقط داخل بدنهٔ کلاس Theme؛ `extra: dict` و `name: str` توکن طراحی نیستند.
const SKIP_FIELDS = new Set(['name', 'extra']);
function parseThemeTokens(py) {
  const start = py.indexOf('class Theme:');
  if (start < 0) { console.error('✗ class Theme در theme.py پیدا نشد'); process.exit(2); }
  // بدنهٔ کلاس تا نخستین تعریف سطح‌بالای بعدی
  let end = py.length;
  const nextTop = py.indexOf('\nDARK = ', start);
  if (nextTop > 0) end = nextTop;
  const body = py.slice(start, end);

  const out = {};
  const re = /^ {4}([a-z][a-z0-9_]*)\s*:\s*(str|int|float)\s*=\s*("([^"]*)"|[-\d.]+)/gm;
  let m;
  while ((m = re.exec(body)) !== null) {
    const field = m[1];
    if (SKIP_FIELDS.has(field)) continue;
    const kind = m[2];
    const raw = m[4] !== undefined ? m[4] : m[3];
    out[field] = { kind, raw };
  }
  return out;
}

// ── ۲. استخراج متغیرهای :root از style.css ─────────────────────────────
function parseCssVars(css) {
  const rootStart = css.indexOf(':root');
  if (rootStart < 0) { console.error('✗ :root در style.css پیدا نشد'); process.exit(2); }
  const brace = css.indexOf('{', rootStart);
  let depth = 0, i = brace, end = -1;
  for (; i < css.length; i++) {
    if (css[i] === '{') depth++;
    else if (css[i] === '}') { depth--; if (depth === 0) { end = i; break; } }
  }
  const block = css.slice(brace, end < 0 ? css.length : end);
  const out = {};
  const re = /--([a-z0-9-]+)\s*:\s*([^;]+);/g;
  let m;
  while ((m = re.exec(block)) !== null) out[m[1]] = m[2].trim();
  return out;
}

const py = read(THEME_PY, 'theme.py');
const css = read(STYLE_CSS, 'style.css');
const tokens = parseThemeTokens(py);
const vars = parseCssVars(css);

console.log('🎨 تست پاریتی تم — src/ui/theme.py ↔ android/style.css');
console.log('   توکن‌های Theme: ' + Object.keys(tokens).length + '   متغیرهای :root: ' + Object.keys(vars).length);

// ── بررسی ۱: وجود و برابری مقدار هر توکن ──────────────────────────────
group('۱) هر توکن تم باید در :root باشد و هم‌مقدار');
const missing = [], mismatched = [];
for (const [field, info] of Object.entries(tokens)) {
  const name = kebab(field);
  if (!(name in vars)) { missing.push(name); continue; }
  const cssVal = vars[name];
  if (info.kind === 'str') {
    const a = normHex(info.raw), b = normHex(cssVal);
    if (a === null) { ok(true, ''); continue; }        // مقدار غیر hex (مثلاً نام رنگ) — رد کن
    if (a !== b) mismatched.push(name + ': theme=' + info.raw + ' css=' + cssVal);
    else ok(true, '');
  } else {
    // int/float — شعاع‌ها در CSS با px می‌آیند، آلفا بی‌واحد
    const numCss = parseFloat(cssVal);
    const numPy = parseFloat(info.raw);
    if (!Number.isFinite(numCss) || Math.abs(numCss - numPy) > 1e-9) {
      mismatched.push(name + ': theme=' + info.raw + ' css=' + cssVal);
    } else ok(true, '');
  }
  checks++;
}
ok(missing.length === 0,
  'توکن‌های غایب در style.css (' + missing.length + '): ' + missing.join(', '));
ok(mismatched.length === 0,
  'توکن‌های ناهم‌مقدار (' + mismatched.length + '): ' + mismatched.join(' | '));
if (missing.length === 0 && mismatched.length === 0) {
  console.log('  ✓ همهٔ ' + Object.keys(tokens).length + ' توکن حاضر و هم‌مقدارند');
}

// ── بررسی ۲: رنگ معنایی هاردکد در کلاس‌های .c-* ────────────────────────
group('۲) کلاس‌های .c-* نباید رنگ هاردکدِ واگرا داشته باشند');
// نگاشت کلاس → توکن تم
const SEMANTIC = {
  'c-green': 'green_text', 'c-red': 'red_text', 'c-amber': 'amber',
};
for (const [cls, field] of Object.entries(SEMANTIC)) {
  const re = new RegExp('\\.' + cls.replace(/[-]/g, '\\-') + '\\s*\\{[^}]*color:\\s*([^;}]+)', 'g');
  let m, found = null;
  while ((m = re.exec(css)) !== null) found = m[1].trim();
  if (found === null) { ok(true, ''); checks++; continue; }
  const want = tokens[field] ? normHex(tokens[field].raw) : null;
  const got = normHex(found);
  const viaVar = /^var\(--/.test(found);
  ok(viaVar || got === want,
    '.' + cls + ' → color:' + found + ' ولی --' + kebab(field) + ' = ' +
    (tokens[field] ? tokens[field].raw : '?') + ' (باید var(--…) یا هم‌مقدار باشد)');
}

// ── بررسی ۳: پالت sharecard.js ↔ src/report/sharecard.py ───────────────
// ⚠️ توجه (این invariant یک بار اشتباه نوشته شد و اصلاح شد):
//   کارت اشتراک یک سطح «تیره» است، پس سبز/قرمز/کهرباییِ روی آن عمداً
//   روشن‌تر از توکن‌های تمِ روشن‌اند. معیار درستیِ پاریتی، مقایسه با
//   theme.py نیست (که باعث رگرسیون بصری می‌شد) بلکه مقایسه با
//   src/report/sharecard.py است — همتای دسکتاپِ همان کارت.
group('۳) پالت کارت اشتراک (sharecard.js) با همتای دسکتاپش هم‌عدد باشد');
{
  const sc = read(SHARECARD_JS, 'sharecard.js');
  const pySc = read(path.join(ROOT, 'src', 'report', 'sharecard.py'), 'src/report/sharecard.py');

  // هاردکدهای رنگ در sharecard.py را به‌عنوان مجموعهٔ مجازِ دسکتاپ جمع کن
  const desktopHexes = new Set(
    (pySc.match(/#[0-9A-Fa-f]{6}/g) || []).map((h) => h.toLowerCase())
  );
  ok(desktopHexes.size > 0, 'sharecard.py هیچ رنگی ندارد؟ (استخراج ناموفق)');

  // هر رنگ در پالت Cِ جاوااسکریپت باید در مجموعهٔ دسکتاپ هم باشد
  const palBlock = /var C = \{([\s\S]*?)\n  \};/.exec(sc);
  ok(!!palBlock, 'پالت «var C = {…}» در sharecard.js پیدا نشد');
  if (palBlock) {
    const jsHexes = palBlock[1].match(/#[0-9A-Fa-f]{6}/g) || [];
    const orphans = jsHexes.filter((h) => !desktopHexes.has(h.toLowerCase()));
    ok(orphans.length === 0,
      'sharecard.js رنگ‌هایی دارد که در sharecard.py نیست (' + orphans.length + '): ' +
      orphans.join(', ') + ' — یعنی پالت دو پلتفرم واگرا شده');
    if (orphans.length === 0) {
      console.log('  ✓ هر ' + jsHexes.length + ' رنگ پالت اندروید در پالت دسکتاپ هم هست');
    }
  }

  // سه رنگ اصلی باید «مو‌به‌مو» هم‌نام و هم‌مقدار باشند
  const KEY = [['green', 'ACC'], ['red', 'ACC'], ['amber', 'AMBER']];
  for (const [jsKey] of KEY) {
    const m = new RegExp('\\b' + jsKey + "\\s*:\\s*'(#[0-9a-fA-F]{6})'").exec(sc);
    if (!m) continue;
    ok(desktopHexes.has(m[1].toLowerCase()),
      'sharecard.' + jsKey + ' = ' + m[1] + ' در sharecard.py وجود ندارد');
  }
}

// ── بررسی ۴: اجزای Aurora Glass 2.0 واقعاً پیاده شده باشند ─────────────
group('۴) اجزای Aurora Glass 2.0 در اندروید حاضر باشند');
{
  ok(fs.existsSync(COMPONENTS_JS), 'android/.../js/components.js وجود ندارد (پورت ۸ ویجت v0.20.0)');
  const idx = read(INDEX_HTML, 'index.html');
  ok(/<script[^>]+js\/components\.js/.test(idx), 'index.html باید js/components.js را قبل از ui.js بار کند');
  ok(idx.indexOf('js/components.js') < idx.indexOf('js/ui.js'),
    'components.js باید «پیش از» ui.js بار شود (ui.js به O.stars/O.chip نیاز دارد)');

  if (fs.existsSync(COMPONENTS_JS)) {
    const comp = read(COMPONENTS_JS, 'components.js');
    const API = ['chip', 'iconChip', 'stars', 'sectionHeader', 'segmented',
                 'consoleCard', 'kpiCard', 'signalCard', 'parseReasons', 'consoleColorize'];
    for (const fn of API) {
      ok(new RegExp('O\\.' + fn + '\\s*=').test(comp), 'components.js باید O.' + fn + ' را export کند');
    }
    // پارسر دلایل باید با نسخهٔ پایتون هم‌رفتار باشد:
    // الگوی «برچسب (+N) — توضیح» با ارقام فارسی و لاتین، و مرز «امتیاز نگرفتند»
    ok(/۰-۹0-9/.test(comp),
      'parseReasons باید کلاس ارقام «۰-۹0-9» را بگیرد (مثل widgets.py)');
    ok(/امتیاز نگرفتند/.test(comp),
      'parseReasons باید مرز «امتیاز نگرفتند» را بشناسد (پس از آن دلیل مثبت ثبت نمی‌شود)');
  }

  // کلاس‌های CSS لازم برای آن اجزا — با مرز کلمه، نه substring
  // (پیش‌تر css.indexOf('.stars') با «.stars-row» هم می‌خواند و پاسِ کاذب می‌داد)
  const NEED_CSS = ['console-card', 'kpi-card', 'sig-card', 'chip', 'icon-chip',
                    'stars', 'section-header', 'segmented'];
  for (const c of NEED_CSS) {
    const re = new RegExp('\\.' + c.replace(/-/g, '\\-') + '(?![\\w-])');
    ok(re.test(css), 'style.css باید کلاس .' + c + ' را به‌عنوان سلکتور مستقل تعریف کند');
  }
  // شفق متحرک — سه assertion، چون یکی بودنشان کافی نیست:
  //  (این گروه یک‌بار با /@keyframes\s+aurora/ نوشته شد و در mutation test
  //   لو رفت: «auroraX» هم قبول می‌شد، یعنی حذف انیمیشن قرمز نمی‌شد.)
  //  ۱) keyframe با نامِ «دقیق» تعریف شده باشد
  ok(/@keyframes\s+aurora\s*\{/.test(css),
    'style.css باید «@keyframes aurora {» داشته باشد (نام دقیق، نه پیشوند)');
  //  ۲) واقعاً به #bg وصل شده باشد (تعریفِ استفاده‌نشده = شفق دیده نمی‌شود)
  ok(/#bg::before[\s\S]{0,400}?animation:\s*aurora\s/.test(css),
    'لایهٔ شفق باید به #bg::before با animation: aurora وصل شده باشد');
  //  ۳) دسترسی‌پذیری: کاربری که حرکت کم می‌خواهد نباید مجبور به تماشایش باشد
  ok(/prefers-reduced-motion[\s\S]{0,200}?animation:\s*none/.test(css),
    'انیمیشن شفق باید با prefers-reduced-motion خاموش شود');
  ok(/body\.no-anim[\s\S]{0,300}?animation:\s*none/.test(css),
    'کلید «انیمیشن‌ها» داخل اپ (body.no-anim) هم باید شفق را خاموش کند');
}

// ── بررسی ۴ب: رنگ معناییِ هاردکد در سلکتورهای ستاره/امتیاز ────────────
group('۴ب) کهرباییِ ستاره‌ها باید از توکن بیاید، نه هاردکد');
{
  // ⚠️ این گروه یک بار «بی‌صدا» از کار افتاد: سلکتورِ هدفش (.stars-row) در
  //   v0.22.0 به‌عنوان CSS مرده حذف شد، پس حلقه هیچ‌چیز پیدا نمی‌کرد و بدون
  //   هیچ بررسی‌ای پاس می‌شد (۲۰۸ → ۲۰۷ بررسی). نگهبانی که هدفش ناپدید
  //   شود باید «شکست» بخورد نه اینکه ساکت رد شود — پس یک assertion صریح
  //   اضافه شد که هدف واقعاً وجود داشته باشد.
  const TARGETS = ['.stars .ico-wrap.on', '.stars .ico-wrap.off'];
  for (const sel of TARGETS) {
    const re = new RegExp(sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*\\{[^}]*color:\\s*([^;}]+)');
    const m = re.exec(css);
    ok(!!m, 'سلکتور «' + sel + '» در style.css پیدا نشد — نگهبانِ رنگ ستاره بی‌هدف شده');
    if (!m) continue;
    const v = m[1].trim();
    const want = sel.endsWith('.on') ? tokens.amber.raw : tokens.border_strong.raw;
    ok(/^var\(--/.test(v) || normHex(v) === normHex(want),
      sel + ' → color:' + v + ' (انتظار: var(…) یا ' + want + ')');
  }
  // هیچ کلاس معناییِ دیگری هم نباید amber هاردکد داشته باشد
  const hardcoded = [...css.matchAll(/\.([a-z][\w-]*(?:\s+[\w.-]+)*)\s*\{[^}]*color:\s*(#[0-9a-fA-F]{6})/g)]
    .filter(([, , hex]) => /^#(D98E04|E0A83C|E8B84B)$/i.test(hex));
  ok(hardcoded.length === 0,
    'کهرباییِ هاردکد در CSS پیدا شد: ' + hardcoded.map((m) => '.' + m[1] + '→' + m[2]).join(', ') +
    ' — باید var(--amber) باشد');
}

// ── بررسی ۵: اجزای نو «کد مرده» نباشند ────────────────────────────────
// ⚠️ این بررسی یک بار «ui.js باید O.xxx را صدا بزند» بود و دو مشکل داشت:
//   ۱) گریپِ نامِ تابع در یک فایلِ مشخص، و ۲) وقتی O.stars از داخل
//      O.signalCard صدا زده شد (که درست‌تر بود) تست به‌اشتباه قرمز ماند.
//   حالا دو لایه داریم:
//     • اینجا (واحد): هر API باید دست‌کم در یک فایل «بیرون از» components.js
//       ارجاع شود — یعنی کد مرده نیست.
//     • در smoke_icons.js (یکپارچگی): markup واقعیِ صفحه‌های رندرشده سنجیده
//       می‌شود (چیپ/ستاره/کاشی/کنسول‌کارت/KPI + نبودِ markup قدیمی).
//   فیکسچرِ کامل صفحه‌ها آنجاست؛ تکثیرش اینجا یعنی دو نسخهٔ موازی از یک
//   دادهٔ آزمون — همان الگویی که باعث رانش amber شد.
group('۵) اجزای نو کد مرده نباشند (بیرون از components.js ارجاع شوند)');
{
  const jsDir = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www', 'js');
  // کامنت‌ها را پیش از جست‌وجو حذف می‌کنیم: وگرنه یک نام در «توضیح» هم
  // به‌عنوان استفاده شمرده می‌شد (مثلاً icons.js در کامنتش نوشته «جای O.stars»
  // در حالی که هیچ‌وقت صدایش نمی‌زند) — پاسِ کاذب.
  const stripComments = (s) =>
    s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1');
  const consumers = fs.readdirSync(jsDir)
    .filter((f) => f.endsWith('.js') && f !== 'components.js')
    .map((f) => [f, stripComments(fs.readFileSync(path.join(jsDir, f), 'utf8'))]);
  const API = ['chip', 'iconChip', 'stars', 'sectionHeader', 'consoleCard',
               'kpiRow', 'kpiCard', 'signalCard', 'parseReasons', 'consoleColorize', 'copyText'];
  for (const fn of API) {
    const users = consumers.filter(([, src]) => src.includes('O.' + fn)).map(([f]) => f);
    // stars/parseReasons/consoleColorize ممکن است فقط «داخل» components.js
    // مصرف شوند (توسط signalCard/consoleCard) — آن هم قابل‌قبول است، به‌شرط
    // اینکه آن جزءِ والد جای دیگری مصرف شود.
    ok(users.length > 0 || ['stars', 'parseReasons', 'consoleColorize', 'iconChip', 'kpiCard', 'segmented'].includes(fn),
      'O.' + fn + ' در هیچ فایلی بیرون از components.js ارجاع نشده — کد مرده');
    if (users.length) console.log('    ✓ O.' + fn.padEnd(17) + ' ← ' + users.join(', '));
  }
}

// ── بررسی ۶: خروجیِ واقعیِ اجزای نو بدون ایموجی باشد ───────────────────
// ⚠️ این بررسی یک بار «نحو» (syntactic) نوشته شده بود و غلط از کار درآمد:
//   رشته‌هایی مثل HEAVY_FIRST یا '✅' در components.js برای «تشخیصِ خطِ
//   ورودی» هستند (port مستقیم منطق widgets.py)، نه خروجی. گریپ‌کردن
//   لیترال‌ها آن‌ها را به‌اشتباه رد می‌کرد. پس اینجا واقعاً ماژول را در vm
//   بار می‌کنیم، هر جزء را با دادهٔ «پُر از ایموجی» رندر می‌گیریم و
//   خروجی HTML را می‌سنجیم — همان چیزی که کاربر می‌بیند.
group('۶) خروجیِ واقعیِ اجزای نو بدون ایموجی باشد (قرارداد v0.13.0)');
{
  const vm = require('vm');
  const WWW = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www', 'js');
  const ctx = { console, setTimeout };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  try {
    for (const f of ['fa.js', 'icons.js', 'components.js', 'ui.js']) {
      if (fs.existsSync(path.join(WWW, f))) {
        vm.runInContext(fs.readFileSync(path.join(WWW, f), 'utf8'), ctx, { filename: f });
      }
    }
  } catch (e) {
    ok(false, 'بارگذاری ماژول‌ها در vm شکست خورد: ' + e.message);
  }
  const O = ctx.ODIN;
  if (!O) {
    ok(false, 'فضای نام ODIN پس از بارگذاری موجود نیست');
  } else {
    const EMOJI = O.EMOJI_RE || /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/u;

    // ⚠️ تقسیم مسئولیت (مستند، چون یک‌بار باعث تستِ غلط شد):
    //   O.icoStr فقط ۲۷ ایموجیِ «نگاشت‌شده» را به آیکون تبدیل می‌کند؛ ایموجیِ
    //   نگاشت‌نشده (مثل 🏆) دست‌نخورده رد می‌شود. پس:
    //     • اینکه «رشتهٔ موتور ایموجیِ نگاشت‌نشده نداشته باشد» → وظیفهٔ
    //       smoke_icons.js است (روی رشته‌های واقعی موتور بررسی می‌کند).
    //     • اینکه «اجزای نو خودشان ایموجی به خروجی تزریق نکنند» → وظیفهٔ
    //       همین تست. پس نمونه‌های زیر فقط از ایموجیِ نگاشت‌شده استفاده می‌کنند.
    //   این دو نگهبان با هم کل قرارداد «صفر ایموجی» (v0.13.0) را می‌پوشانند.
    const MAPPED = ['📈', '📉', '↗', '↑', '🟢', '🔴', '✅', '❌', '❔', '⛔', '🔒', '🚨',
      '🛑', '📡', '📅', '📔', '💹', '🕐', '🔄', '💾', '⚙', '🔌', 'ℹ', '📍', '💰', '🙂',
      '📊', '🕒', '🎯', '⭐'];
    for (const em of MAPPED) {
      ok(!O.EMOJI_RE.test(O.icoStr(em, 12)),
        'ایموجی ' + em + ' با O.icoStr به آیکون تبدیل نشد — قرارداد صفر-ایموجی می‌شکند');
    }
    // نمونهٔ متن سیگنال — عمداً پُر از ایموجی، چون موتور همین را تولید می‌کند
    const SIG_TEXT = [
      '══════════════════════════════════════',
      '🟢 سیگنال خرید — CHF/JPY',
      '─── چرا این سیگنال صادر شد؟ ───',
      '✅ هم‌راستایی روند ۴ ساعته و ۱ ساعته (+۲) — روند صعودی؛ ADX=28',
      '✅ واکنش به سطح کلیدی (حمایت) (+۲) — سایهٔ کندل H4 حمایت را لمس کرد',
      '✅ پنجرهٔ فاندامنتال پاک (+۲) — هیچ رویداد مهمی در ۶ ساعت آینده',
      '➖ مدارکی که امتیاز نگرفتند (صادقانه):',
      '➖ تایید خبری (۰ از ۱) — خبر هم‌جهت پیدا نشد',
      '❌ خطا در دریافت داده',
      '• نوسان بازار بالاتر از حد معمول است',
      '📍 ورود: 181.420   🛑 حد ضرر: 180.980   🎯 هدف: 182.520',
    ].join('\n');

    const CASES = {
      chip: () => O.chip('🟢 سیگنال خرید ✅', 'green'),
      iconChip: () => O.iconChip('trend_up', 36, 'green'),
      stars: () => O.stars(3, 5, 14),
      sectionHeader: () => O.sectionHeader('report', '📊 عنوان', '🕒 زیرعنوان'),
      segmented: () => O.segmented('tf', [['h1', 'H1 📈'], ['h4', 'H4 📉']], 'h1'),
      consoleCard: () => O.consoleCard({ title: '🎯 گزارش', icon: 'news', text: SIG_TEXT, stamp: '۱۲:۳۰' }),
      consoleColorize: () => O.consoleColorize(SIG_TEXT),
      kpiCard: () => O.kpiCard({ icon: 'chart', value: '٪۶۲', label: '📊 نرخ برد' }),
      kpiRow: () => O.kpiRow([{ icon: 'target', value: '۵', label: 'برد ✅' }, { icon: 'stop-sign', value: '۲', label: 'باخت ❌' }]),
      signalCard: () => O.signalCard({
        direction: 'BUY', stars: 4, score: 9, max_score: 11, session_fa: '🕒 لندن',
        rr: 2.5, entry: 181.42, sl: 180.98, tp: 182.52, pip: 0.01, text: SIG_TEXT,
      }),
      parseReasons: () => JSON.stringify(O.parseReasons(SIG_TEXT)),
    };
    let emojiFree = 0;
    for (const [name, fn] of Object.entries(CASES)) {
      let out;
      try { out = String(fn()); }
      catch (e) { ok(false, name + '() استثنا داد: ' + e.message); continue; }
      const m = EMOJI.exec(out);
      ok(!m, name + '() در خروجی ایموجی دارد: ' + JSON.stringify(m && m[0]));
      ok(out.length > 0, name + '() خروجی خالی داد');
      if (!m) emojiFree++;
    }
    if (emojiFree === Object.keys(CASES).length) {
      console.log('  ✓ ' + emojiFree + ' جزء رندر شد، همه بدون ایموجی');
    }

    // ── ۶الف: Stars باید خانه‌های «پر» و «خاموش» را تفکیک کند ────────
    // چرا اینجا: O.starIcons قدیمی فقط n ستارهٔ پر می‌کشید، پس «۲ از ۵» و
    // «۲ از ۵» با totalهای مختلف یکسان دیده می‌شد و طول ردیف ثابت نبود.
    // Stars دسکتاپ (widgets.py) هر دو حالت را می‌کشد؛ پورت اندروید هم باید.
    group('۶الف) Stars خانهٔ پر و خاموش را تفکیک کند');
    {
      const s35 = O.stars(3, 5, 14);
      const s55 = O.stars(5, 5, 14);
      const s05 = O.stars(0, 5, 14);
      const count = (h, c) => (h.match(new RegExp(c, 'g')) || []).length;
      ok(count(s35, 'ico-wrap on') === 3, 'stars(3,5) باید ۳ خانهٔ پر داشته باشد، دارد: ' + count(s35, 'ico-wrap on'));
      ok(count(s35, 'ico-wrap off') === 2, 'stars(3,5) باید ۲ خانهٔ خاموش داشته باشد، دارد: ' + count(s35, 'ico-wrap off'));
      ok(count(s55, 'ico-wrap on') === 5 && count(s55, 'ico-wrap off') === 0, 'stars(5,5) باید ۵ پر و ۰ خاموش باشد');
      ok(count(s05, 'ico-wrap off') === 5 && count(s05, 'ico-wrap on') === 0, 'stars(0,5) باید ۵ خاموش و ۰ پر باشد');
      ok(count(s35, '<svg') === 5, 'stars(3,5) باید دقیقاً ۵ SVG بکشد، کشید: ' + count(s35, '<svg'));
      // نام آیکون در markup نمی‌آید (O.ico فقط class="ico" می‌گذارد)، پس
      // «توپر» و «توخالی» بودن از خودِ path سنجیده می‌شود.
      ok(count(s35, 'fill="currentColor"') === 3,
        'stars(3,5) باید ۳ ستارهٔ توپر بکشد، کشید: ' + count(s35, 'fill="currentColor"'));
      ok(count(s35, 'stroke-width="1.6"') === 2,
        'stars(3,5) باید ۲ ستارهٔ توخالی بکشد، کشید: ' + count(s35, 'stroke-width="1.6"'));
      // clamp: مقدار بیرونِ بازه نباید بشکند یا بیش از total بکشد
      ok(count(O.stars(9, 5, 14), '<svg') === 5, 'stars(9,5) باید به ۵ clamp شود');
      ok(count(O.stars(-3, 5, 14), 'ico-wrap off') === 5, 'stars(-3,5) باید به ۰ clamp شود');
      ok(count(O.stars(null, 5, 14), '<svg') === 5, 'stars(null,5) نباید بشکند');
    }

    // ── بررسی ۶ب: parseReasons باید با widgets.py هم‌رفتار باشد ──
    group('۶ب) parseReasons هم‌رفتار با SignalCard._parse_reasons پایتون');
    const r = O.parseReasons(SIG_TEXT);
    ok(r.reasons.length === 3, 'باید ۳ دلیلِ دارای امتیاز پیدا کند، یافت: ' + r.reasons.length);
    ok(r.reasons.length === 0 || r.reasons[0].pts === 2, 'امتیاز فارسی «+۲» باید 2 پارس شود');
    ok(r.reasons.every((x) => x.label.indexOf('امتیاز نگرفتند') < 0),
      'بخش «امتیاز نگرفتند» نباید به‌عنوان دلیل مثبت ثبت شود');
    ok(r.warns.length === 1 && r.warns[0].indexOf('نوسان') >= 0,
      'خطوط «•» باید به warns بروند، یافت: ' + JSON.stringify(r.warns));
    ok(r.reasons[0].icon === 'trend-up',
      'نگاشت آیکون: «روند» باید trend-up شود (نه نام دسکتاپی trend_up)، یافت: ' + r.reasons[0].icon);
    ok(O.parseReasons('').reasons.length === 0, 'ورودی خالی → خروجی خالی');
    ok(O.parseReasons(null).reasons.length === 0, 'ورودی null → خروجی خالی (نه کرش)');
    ok(O.parseReasons('خط کاملاً بی‌ربط بدون الگو').reasons.length === 0, 'خط بدون الگو → دلیل نیست');
  }
}

// ── بررسی ۷: شمارهٔ نسخهٔ هاردکد در منابع اپ ──────────────────────────
// چرا: در یک دور بررسی، «چهار» عدد نسخهٔ کهنهٔ هاردکد پیدا شد:
//   build.gradle → versionName "0.19.0"  (در حالی که دسکتاپ 0.20.0 بود)
//   app.js       → S.version = '0.19.0'  و fallback بوت
//   ui.js        → «همراه نسخهٔ ویندوز (0.8.1)» (۱۲ نسخه عقب!)
//   sharecard.js → مُهر نسخهٔ کارت اشتراک '0.19.0'
// هیچ‌کدام با تست گرفته نمی‌شدند. حالا APP_VERSION تنها منبع است و هر عدد
// نسخهٔ هاردکد در «کد» اندروید = قرمز. (عددهای داخل کامنت ایرادی ندارند —
// آن‌ها مستندِ تاریخچه‌اند؛ پس کامنت‌ها پیش از جست‌وجو حذف می‌شوند.)
group('۷) شمارهٔ نسخهٔ هاردکد در منابع اندروید نباشد');
{
  const APP_PATHS = path.join(ROOT, 'src', 'app_paths.py');
  const appPy = read(APP_PATHS, 'src/app_paths.py');
  const appVersion = (appPy.match(/APP_VERSION\s*=\s*"([^"]+)"/) || [])[1] || '';
  ok(/^\d+\.\d+\.\d+/.test(appVersion),
    'APP_VERSION از src/app_paths.py خوانده نشد (یافته: ' + JSON.stringify(appVersion) + ')');
  console.log('    APP_VERSION (منبع حقیقت) = ' + appVersion);

  // کامنت‌زدا: // و /* */ برای Groovy/JS، و <!-- --> برای HTML
  const stripCode = (s) => s
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/(^|[^:'"`\\])\/\/[^\n]*/g, '$1 ');

  // build.gradle باید versionName/versionCode را از app_paths.py بخواند
  const gradleRaw = read(path.join(ROOT, 'android', 'app', 'build.gradle'), 'build.gradle');
  const gradle = stripCode(gradleRaw);
  ok(/app_paths\.py/.test(gradleRaw) && /APP_VERSION/.test(gradleRaw),
    'build.gradle باید APP_VERSION را از src/app_paths.py بخواند');
  ok(!/versionName\s+["']?\d/.test(gradle),
    'build.gradle هنوز versionName هاردکد دارد (باید از appVersion بیاید)');
  ok(!/versionCode\s+\d/.test(gradle),
    'build.gradle هنوز versionCode هاردکد دارد (باید از computedVersionCode بیاید)');

  // منابع وب اپ: هیچ عدد نسخه‌ای که با APP_VERSION یکی نیست، در «کد» نباشد
  const VER = /['"]v?(\d+\.\d+\.\d+)['"]/g;
  const wwwDir = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www');
  const offenders = [];
  const walk = (dir) => fs.readdirSync(dir, { withFileTypes: true }).forEach((d) => {
    const fp = path.join(dir, d.name);
    if (d.isDirectory()) return walk(fp);
    if (!/\.(js|html|css)$/.test(d.name)) return;
    const code = stripCode(fs.readFileSync(fp, 'utf8'));
    let m; VER.lastIndex = 0;
    while ((m = VER.exec(code)) !== null) {
      if (m[1] !== appVersion) offenders.push(d.name + ' → ' + m[1]);
    }
  });
  walk(wwwDir);
  ok(offenders.length === 0,
    'عدد نسخهٔ هاردکد در منابع اندروید (' + offenders.length + '): ' + offenders.join(' | ') +
    ' — باید از APP_VERSION بیاید یا fallback غیرعددی مثل «dev» باشد');
  if (!offenders.length) console.log('    ✓ هیچ عدد نسخهٔ هاردکدی در www/ نیست');
}

console.log('\n' + '═'.repeat(56));
if (failures) {
  console.log('✗ SMOKE THEME PARITY FAILED — ' + failures + ' از ' + checks + ' بررسی شکست خورد');
  process.exit(1);
}
console.log('✅ SMOKE THEME PARITY OK — ' + checks + ' بررسی پاس؛ تم اندروید با theme.py هم‌توکن و هم‌مقدار است');
