/* ══════════════════════════════════════════════════════════════════════
   smoke_layout.js — نگهبان چیدمان و خوانایی اپ اندروید

   چرا این تست ساخته شد (مستند، چون دلیلش مهم‌تر از خودش است):
     در بازبینی v0.22.0 چهار دسته باگ ظاهری پیدا شد که «هیچ» تستی نمی‌گرفتشان:
       ۱) ساعت هدر در دو خط شکسته می‌شد — سرریز ۳۲px در گوشی ۳۶۰px
       ۲) متن .stat-defs سفیدِ نیمه‌شفاف بود ولی در v0.21.0 از کارت مشکی به
          کارت سفید منتقل شده بود → سفید روی سفید = کاملاً نامرئی
       ۳) ۸ کلاس CSS مرده (از جمله .sc-acts/.sc-full که همان v0.21.0
          تعریف شده بودند و هرگز استفاده نشدند)
       ۴) ۵۴ متن راهنما با جمع ۳٬۵۸۸ نویسه — رابط شلوغ شده بود
     تست‌های موجود (parity/smoke_icons) «درستی منطق» و «صفر ایموجی» را
     می‌سنجیدند؛ هیچ‌کدام «آیا کاربر می‌تواند این را بخواند» را نمی‌سنجیدند.

   ⚠️ محدودیت صادقانهٔ این تست:
     اینجا مرورگر نیست. عرض متن با «تخمین» محاسبه می‌شود (میانگین پهناى
     نویسه بر حسب em) نه با اندازه‌گیری واقعی گلیف. پس این تست برای گرفتنِ
     سرریزهای بزرگ و رگرسیون‌ها خوب است، ولی جای بازبینی چشمی را نمی‌گیرد.
     آستانه‌ها عمداً کمی سخت‌گیرانه گذاشته شده‌اند تا خطای تخمین پوشش داده شود.

   اجرا:  node tests/js/smoke_layout.js
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

const css = read('style.css');
const html = read('index.html');

// ── ابزار: استخراج ویژگی از یک سلکتور CSS ────────────────────────────────
function cssProp(selector, prop) {
  // دو باگِ نسخهٔ اول این هلپر که هر دو «منفیِ کاذب» می‌دادند:
  //   ۱) فقط سلکتورِ «تنها» را می‌دید؛ قاعدهٔ گروهی مثل
  //      «.ev-time, .cc-stamp { white-space: nowrap }» را پیدا نمی‌کرد.
  //      → حالا سلکتور را بر ویرگول می‌شکند و هر جزء را جدا می‌سنجد.
  //   ۲) جداسازِ ویژگی را فقط «;» یا «آغاز رشته» می‌پذیرفت؛ اگر پیش از
  //      ویژگی یک «کامنت» بود (#greet) پیدا نمی‌کرد.
  //      → حالا هر نویسهٔ سفید هم جداساز معتبر است.
  const want = selector.trim();
  const ruleRe = /([^{}@]+)\{([^{}]*)\}/g;
  let m;
  while ((m = ruleRe.exec(css)) !== null) {
    const parts = m[1].split(',').map((s) => s.trim().split('\n').pop().trim());
    if (!parts.includes(want)) continue;
    const p = new RegExp('(?:^|[;\\s])' + prop.replace(/-/g, '\\-') + '\\s*:\\s*([^;}]+)').exec(m[2]);
    if (p) return p[1].trim();
  }
  return null;
}
function px(v, dflt) {
  if (v == null) return dflt;
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : dflt;
}

// ── تخمین عرض متن (همان ضریب‌هایی که در بازبینی دستی استفاده شد) ────────
// وزیرمتن: نویسهٔ فارسی ≈ 0.50em، لاتین/رقم ≈ 0.55em، فاصله ≈ 0.28em
function textWidth(text, fontSize) {
  let t = 0;
  for (const ch of String(text)) {
    if (ch === ' ') t += fontSize * 0.28;
    else if (/[\u0600-\u06FF\u06F0-\u06F9\u200C\u200D]/.test(ch)) t += fontSize * 0.50;
    else t += fontSize * 0.55;
  }
  return t;
}

console.log('📐 تست چیدمان و خوانایی — اپ اندروید ODIN Assistant');

// هلپر: «مقدار» یک ویژگی از یک سلکتور (نه کل اعلان)
const nowrapOf = (sel) => (cssProp(sel, 'white-space') || '').trim();

// ══════════════════════════════════════════════════════════════════════
group('۱) بودجهٔ عرض هدر در باریک‌ترین گوشی‌ها');
// ══════════════════════════════════════════════════════════════════════
// همهٔ اعداد از خودِ CSS/HTML/JS خوانده می‌شوند، نه هاردکد — وگرنه تست
// با تغییر طراحی کهنه می‌شد و بی‌صدا پاس می‌ماند.
{
  const hdrPad = px(cssProp('#hdr', 'padding'), 0);
  // padding چندمقداری است: «calc(10px + env(...)) 18px 8px» → عرض = ۱۸
  const padNums = (cssProp('#hdr', 'padding') || '').match(/\d+px/g) || [];
  const padX = padNums.length >= 2 ? parseFloat(padNums[1]) : hdrPad;

  const gap = px(cssProp('.hdr-main', 'gap'), 0);
  const greetFs = px(cssProp('#greet', 'font-size'), 21);
  const appsubFs = px(cssProp('#appsub', 'font-size'), 10.5);
  const clockFs = px(cssProp('.clock-pill', 'font-size'), 11);
  const clockPad = ((cssProp('.clock-pill', 'padding') || '').match(/\d+px/g) || [0, 0])
    .map(parseFloat);
  const clockPadX = (clockPad[1] != null ? clockPad[1] : clockPad[0] || 0) * 2;
  const sideGap = px(cssProp('.hdr-side', 'gap'), 8);
  const btnSize = px(cssProp('.circle-btn', 'width'), 34) + 2;   // + border

  const appsubText = (html.match(/<div id="appsub">([^<]*)</) || [])[1] || '';
  ok(appsubText.length > 0, 'متن #appsub از index.html خوانده نشد');

  // متن ساعت را از خودِ JS بخوان (قالب «HH:MM تهران»)
  const clockLine = (read('js/app.js').match(/getElementById\('clock'\)[\s\S]{0,120}?textContent\s*=\s*([^;]+);/) || [])[1] || '';
  const hasTehran = /تهران/.test(clockLine);
  const clockText = '۱۴:۳۲' + (hasTehran ? ' تهران' : '');

  // بلندترین «سلام …» ممکن: نام کاربر تا ۲۰ نویسه لاتین (بدترین حالت)
  const greetWorst = Math.max(textWidth('سلام سوشیان!', greetFs), textWidth('سلام Mohammadreza!', greetFs));
  const left = Math.max(greetWorst, textWidth(appsubText, appsubFs));
  const right = textWidth(clockText, clockFs) + clockPadX + 2 + sideGap + btnSize;

  console.log('    #appsub = «' + appsubText + '» (' + appsubText.length + ' نویسه)');
  console.log('    ساعت    = «' + clockText + '»' + (hasTehran ? '' : '  ⚠ «تهران» در JS پیدا نشد'));
  console.log('    عرض لازم ≈ ' + Math.round(left) + ' + ' + Math.round(gap) + ' + ' + Math.round(right) + ' = ' + Math.round(left + gap + right) + 'px');

  // مدل درست (نسخهٔ اول این تست غلط بود و سرریزِ کاذب گزارش می‌کرد):
  //   سمت متن `flex:1 1 auto; min-width:0` دارد → می‌تواند جمع شود و با
  //   ellipsis کوتاه شود. سمت ساعت `flex:0 0 auto` است → ثابت می‌ماند.
  //   پس قیدِ «سخت» این است که سمت ثابت در باریک‌ترین گوشی جا شود، و قیدِ
  //   «نرم» این است که در حالت عادی حداقل ~۶۰px برای متن بماند.
  for (const screen of [320, 360, 390]) {
    const avail = screen - padX * 2;
    ok(right <= avail - gap,
      'سمتِ ثابت هدر (ساعت+دکمه=' + Math.round(right) + 'px) در گوشی ' + screen +
      'px جا نمی‌شود (موجود ' + Math.round(avail - gap) + 'px) — ساعت دوخطی می‌شود');
    const room = avail - gap - right;
    ok(room >= 60, 'در گوشی ' + screen + 'px فقط ' + Math.round(room) +
      'px برای متن هدر می‌ماند — خیلی تنگ (حداقل ۶۰px لازم است)');
    console.log('    ✓ گوشی ' + screen + 'px: سمت ثابت ' + Math.round(right) +
      'px · فضای متن ' + Math.round(room) + 'px');
    // قیدِ «نرم» ولی مهم: متن هدر باید در گوشی معمولی «بدون بریده‌شدن» جا شود.
    // چرا لازم است: با nowrap+ellipsis، یک appsub خیلی بلند ساعت را نمی‌شکند
    // (پس قیدِ سخت بالا پاس می‌ماند) ولی «بریده» می‌شود و کاربر بخشی از پیام
    // را نمی‌بیند. mutation test نشان داد بدون این assertion، برگرداندن متن
    // بلندِ v0.21.0 بی‌صدا پاس می‌شد.
    if (screen === 360) {
      const needAppsub = textWidth(appsubText, appsubFs);
      ok(needAppsub <= room,
        '#appsub در گوشی ۳۶۰px بریده می‌شود: عرض طبیعی «' + appsubText + '» = ' +
        Math.round(needAppsub) + 'px ولی فقط ' + Math.round(room) + 'px جا هست');
      const needGreet = textWidth('سلام سوشیان!', greetFs);
      ok(needGreet <= room,
        '#greet با نام معمولی بریده می‌شود: ' + Math.round(needGreet) + 'px > ' + Math.round(room) + 'px');
      console.log('    ✓ متن هدر بدون بریده‌شدن جا می‌شود (appsub ' +
        Math.round(needAppsub) + 'px، greet ' + Math.round(needGreet) + 'px از ' + Math.round(room) + 'px)');
    }
  }

  // سه محافظی که با هم لازم‌اند (هر کدام به‌تنهایی کافی نیست)
  // ⚠️ cssProp «مقدار» ویژگی را برمی‌گرداند نه کل اعلان؛ نسخهٔ اول این تست
  //   مقدار را با /white-space:\s*nowrap/ می‌سنجید و همیشه شکست می‌خورد.
  ok(nowrapOf('.clock-pill') === 'nowrap',
    '.clock-pill باید white-space:nowrap داشته باشد وگرنه ساعت دوخطی می‌شود — یافته: ' + nowrapOf('.clock-pill'));
  ok(/0 0 auto/.test(cssProp('.clock-pill', 'flex') || ''),
    '.clock-pill باید flex:0 0 auto داشته باشد وگرنه در flex جمع می‌شود');
  ok(nowrapOf('#appsub') === 'nowrap' && /ellipsis/.test(cssProp('#appsub', 'text-overflow') || ''),
    '#appsub باید nowrap + ellipsis داشته باشد');
  ok(nowrapOf('#greet') === 'nowrap' && /ellipsis/.test(cssProp('#greet', 'text-overflow') || ''),
    '#greet باید nowrap + ellipsis داشته باشد وگرنه نام بلند کل هدر را هل می‌دهد');
  const firstChild = css.split('}').map((b) => b.split('{'))
    .find(([s]) => s && s.trim().endsWith('.hdr-main > div:first-child'));
  ok(!!firstChild && /min-width:\s*0/.test(firstChild[1] || ''),
    '.hdr-main > div:first-child باید min-width:0 داشته باشد (بدون آن، flex آیتم ' +
    'هرگز کوچک‌تر از عرض محتوا نمی‌شود — نکتهٔ رایج و فراموش‌شده)');
  ok(!!firstChild && /flex:\s*1/.test(firstChild[1] || ''),
    '.hdr-main > div:first-child باید flex:1 بگیرد تا فضای باقی‌مانده را پر کند');
}

// ══════════════════════════════════════════════════════════════════════
group('۲) کنتراست: متن روشن فقط روی ظرف تیره');
// ══════════════════════════════════════════════════════════════════════
// باگ واقعی v0.21.0: .stat-defs رنگ سفیدِ نیمه‌شفاف داشت (برای کارت مشکی
// .ink ساخته شده بود) ولی به یک کارت سفید منتقل شد → نامرئی. هیچ تستی
// نگرفتشان چون تست کنتراست نداشتیم.
{
  // ظرف‌های «تیره» در این اپ — هر سلکتوری که با یکی از این پیشوندها بیاید
  // مجاز است رنگ متن روشن داشته باشد.
  // allowlist «صریح» — هر مورد با دلیل. افزودن به این فهرست باید آگاهانه باشد،
  // نه با الگوی تطبیقِ حدسی (نسخهٔ اول حدسی بود و ۶ مثبتِ کاذب داد).
  // این‌ها متنِ روشن دارند چون خودِ ظرفشان تیره یا رنگیِ پررنگ است.
  const DARK_CONTEXTS = [
    '.ink', '#splash', '.splash-', '.cc-body', '.console-card', '.icon-chip',
    '.chip.tone-ink', '.segmented button.on', '.btn.primary', '.pill.on-ink',
    '.tab.active', '.tab .badge', '#toast-root', '.status-pill', '.tg-pill',
    '.progress', '#progress', '.modal-card', '.sig-head', '.r-chip.win',
    '.r-chip.loss', '.dir-chip', '.toast', '.on-ink',
    // ⚠️ در v0.23.0 «#onb-root» و «.onb-» اینجا بودند (صفحهٔ ورود جوهریِ
    //   تمام‌صفحه با زمینهٔ تیره). در v0.24.0 آن صفحه حذف و جریان مودال‌محور
    //   برگردانده شد، پس آن دو مورد هم رفتند. نگه‌داشتنِ allowlistِ بی‌مصرف
    //   خطرناک است: اگر روزی سلکتوری با همان نام و زمینهٔ «روشن» بیاید،
    //   بی‌صدا مجاز شمرده می‌شد.
  ];

  // ⚠️ allowlist به‌تنهایی خطرناک است: اگر ظرفی که «تیره» فرض شده روزی
  //   زمینهٔ روشن بگیرد، این فهرست بی‌صدا متنِ نامرئی را مجاز می‌شمارد و
  //   نگهبان به ضدِّ خودش تبدیل می‌شود. پس فرضِ هر ظرفِ کلیدی راستی‌آزمایی
  //   می‌شود: واقعاً باید تیره باشد.
  //   (در v0.23.0 این بررسی برای #onb-root هم بود؛ آن عنصر در v0.24.0 حذف شد
  //    و assertion مربوطه هم با آن رفت — نگهبانِ عنصرِ ناموجود، پاسِ کاذب است.)
  function lumOf(hex) {
    const h = hex.replace('#', '');
    const f = (i) => {
      const c = parseInt(h.slice(i, i + 2), 16) / 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * f(0) + 0.7152 * f(2) + 0.0722 * f(4);
  }
  {
    // کارت مشکیِ اصلی (.card.ink) باید از توکن تیره بیاید، نه رنگ هاردکد
    const inkTok = (/--ink-card\s*:\s*(#[0-9A-Fa-f]{6})/.exec(css) || [])[1];
    ok(!!inkTok, '--ink-card در :root پیدا نشد');
    if (inkTok) {
      ok(lumOf(inkTok) < 0.12,
        '.card.ink در allowlist کنتراست است چون «تیره» فرض شده، ولی --ink-card = ' +
        inkTok + ' با روشنایی ' + lumOf(inkTok).toFixed(3) + ' تیره نیست');
      console.log('    ✓ فرضِ تیره‌بودنِ .card.ink راستی‌آزمایی شد (--ink-card=' + inkTok +
        '، روشنایی ' + lumOf(inkTok).toFixed(3) + ')');
    }
    const ccBg = cssProp('.console-card .cc-body', 'background');
    ok(ccBg != null && /var\(--console-bg\)/.test(ccBg),
      '.cc-body باید background: var(--console-bg) داشته باشد — یافته: ' + ccBg);
  }
  // ── اسکن اصلی: هر قاعده‌ای که رنگ متنِ روشن می‌دهد باید داخل ظرف تیره باشد
  const lightRe = /(?:^|[{;])\s*color\s*:\s*(rgba?\(\s*255\s*,\s*255\s*,\s*255[^)]*\)|#fff\b|#ffffff\b|var\(--on-ink\)|var\(--console-text\))/gi;
  const offenders = [];
  const ruleRe = /([^{}@]+)\{([^{}]*)\}/g;
  let m;
  while ((m = ruleRe.exec(css)) !== null) {
    const selRaw = m[1].trim().split('\n').pop().trim();
    const body = m[2];
    if (!selRaw || selRaw.startsWith('/*')) continue;
    lightRe.lastIndex = 0;
    if (!lightRe.test(body)) continue;
    for (const sel of selRaw.split(',')) {
      const s = sel.trim();
      if (!s || s.startsWith(':root')) continue;
      const inDark = DARK_CONTEXTS.some((d) => s === d || s.startsWith(d + ' ') ||
        s.startsWith(d + '.') || s.includes(' ' + d + ' ') || s.endsWith(' ' + d) || s.includes(d));
      if (!inDark) {
        lightRe.lastIndex = 0;
        const mm = lightRe.exec(body);
        offenders.push(s + ' → ' + (mm ? mm[1] : '?'));
      }
    }
    lightRe.lastIndex = 0;
  }

  // .stat-defs به‌طور خاص: باید رنگ خوانا روی زمینهٔ روشن داشته باشد
  const sd = cssProp('.stat-defs', 'color');
  ok(sd != null && !/255\s*,\s*255\s*,\s*255|#fff/i.test(sd),
    '.stat-defs دوباره رنگ روشن گرفته — روی کارت سفید نامرئی می‌شود (رگرسیون v0.21.0). یافته: ' + sd);
  ok(/\.ink \.stat-defs|\.card\.ink \.stat-defs/.test(css),
    'باید یک قاعدهٔ «.ink .stat-defs» باشد تا داخل کارت مشکی همان سفید بماند');

  ok(offenders.length === 0,
    'متنِ روشن بیرون از ظرف تیره (' + offenders.length + '): ' + offenders.slice(0, 6).join(' | '));
  if (!offenders.length) console.log('    ✓ هیچ متن روشنی بیرونِ ظرف تیره نیست');
}

// ══════════════════════════════════════════════════════════════════════
group('۳) CSS مرده و سلکتورهای متناقضِ تکراری');
// ══════════════════════════════════════════════════════════════════════
{
  const src = ['js/app.js', 'js/ui.js', 'js/components.js', 'js/chart.js', 'js/alerts.js',
    'js/calendar.js', 'js/news.js', 'js/sharecard.js', 'js/briefing.js', 'js/license.js',
    'js/icons.js', 'js/fa.js', 'index.html'].map(read).join('\n');
  // کامنت‌های CSS هم باید حذف شوند (کلاس مرده‌ای که فقط در کامنتِ توضیحیِ
  // «حذف شد» آمده، تعریف‌شده حساب نمی‌شود)
  const cssCode = css.replace(/\/\*[\s\S]*?\*\//g, ' ');
  // کامنت‌ها را حذف کن: نام کلاس در کامنت، «استفاده» حساب نمی‌شود
  // (دقیقاً اشتباهی که .dir-pill را زنده نشان می‌داد)
  const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '')
    .replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1');

  const dead = [];
  for (const c of ['dir-pill', 'stars-row', 'brief-line', 'l-sub', 'sc-acts', 'sc-full', 'arm', 'tip']) {
    const used = new RegExp('(?<![\\w-])' + c + '(?![\\w-])').test(code);
    // ⚠️ کامنت‌های CSS را پیش از جست‌وجو حذف کن: نسخهٔ اول، نام کلاس را
    //   داخل «کامنتِ توضیحیِ حذف» پیدا می‌کرد و به‌اشتباه می‌گفت هنوز تعریف شده.
    const defined = new RegExp('\\.' + c + '(?![\\w-])').test(cssCode);
    if (defined && !used) dead.push(c);
  }
  ok(dead.length === 0, 'CSS مرده دوباره برگشته: ' + dead.map((c) => '.' + c).join(', ') +
    ' — یا استفاده شود یا حذف');
  if (!dead.length) console.log('    ✓ هیچ‌کدام از ۸ کلاس مردهٔ حذف‌شده برنگشته‌اند');

  // سلکتور تک‌کلاسه‌ای که دوبار با «ویژگی یکسان و مقدار متفاوت» تعریف شده باشد
  const seen = new Map();
  const conflicts = [];
  const ruleRe = /([^{}@]+)\{([^{}]*)\}/g;
  let m;
  while ((m = ruleRe.exec(css)) !== null) {
    const sel = m[1].trim().split('\n').pop().trim();
    if (!/^\.[a-z][\w-]*$/.test(sel)) continue;         // فقط تک‌کلاسه
    for (const decl of m[2].split(';')) {
      const mm = /^\s*([a-z-]+)\s*:\s*(.+?)\s*$/.exec(decl);
      if (!mm) continue;
      const key = sel + '::' + mm[1];
      const prev = seen.get(key);
      if (prev && prev !== mm[2] && !/var\(--/.test(prev + mm[2])) conflicts.push(key.split('::')[0] + ' ' + mm[1] + ': ' + prev + ' ≠ ' + mm[2]);
      seen.set(key, mm[2]);
    }
  }
  ok(conflicts.length === 0,
    'سلکتور تکراری با مقدار متناقض (' + conflicts.length + '): ' + conflicts.slice(0, 5).join(' | '));
  if (!conflicts.length) console.log('    ✓ هیچ سلکتور تکراریِ متناقضی نیست');
}

// ══════════════════════════════════════════════════════════════════════
group('۴) بودجهٔ متن راهنما (شلوغ‌نشدن رابط)');
// ══════════════════════════════════════════════════════════════════════
// در بازبینی v0.22.0 تعداد ۵۴ متن راهنما با جمع ۳٬۵۸۸ نویسه شمرده شد و
// بلندترینشان ۱۴۳ نویسه بود. آستانه‌های زیر همان وضعِ «پس از اصلاح» را
// قفل می‌کنند تا رابط دوباره پرحرف نشود.
{
  const ctx = { console, setTimeout };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  for (const f of ['md5.js', 'fa.js', 'icons.js', 'license.js', 'config.js', 'indicators.js',
    'session.js', 'technical.js', 'calendar.js', 'news.js', 'judge.js', 'journal.js', 'data.js',
    'alerts.js', 'chart.js', 'sharecard.js', 'briefing.js', 'components.js', 'ui.js']) {
    vm.runInContext(read('js/' + f), ctx, { filename: f });
  }
  const O = ctx.ODIN;
  const settings = {
    user_name: 'سوشیان', judge_enabled: true, min_score: 7,
    veto: { weekend: 1, high_impact_event: 1, timeframe_conflict: 1, range_market: 1, volatility_spike: 1, breaking_news: 1 },
    fund_enabled: true, news_enabled: true, tv_enabled: true, auto_refresh_enabled: true,
    auto_refresh_min: 15, notify_enabled: true, background_enabled: true, animations_enabled: true,
  };
  const cfg = O.deepFill(O.CONFIG, { ui: { user_name: 'سوشیان' }, judge: { enabled: true, min_score: 7, veto: settings.veto } });
  const S = {
    cfg, settings, state: null, stats: null, journal: { load: () => [], raw: () => '' },
    storage: { get: () => '', set: () => {}, del: () => {} }, version: '0.22.0',
  };
  const pages = {
    home: O.renderHome(S), signals: O.renderSignals(S), calendar: O.renderCalendar(S),
    news: O.renderNews(S), journal: O.renderJournal(S), settings: O.renderSettings(S),
    about: O.renderAbout(S), briefing: O.renderBriefingPage(S),
  };

  // ⚠️ تفکیک مهم (نسخهٔ اول این تست این را نداشت و ۲ مثبتِ کاذب داد):
  //   • متن «آموزشی» = چیزی که توضیح می‌دهد چطور کار می‌کند. این‌ها رابط را
  //     شلوغ می‌کنند و باید کوتاه باشند.
  //   • متن «حقوقی/اصالت» در صفحهٔ دربارهٔ ما = خودِ محتواست، نه راهنما.
  //     اعلام کپی‌رایت و هشدار ضدتقلب عمداً مفصل‌اند؛ کوتاه‌کردنشان ارزش
  //     حقوقی‌شان را کم می‌کند. پس از سقفِ طول «معاف»‌اند — ولی با یک
  //     assertion جداگانه قفل شده‌اند که حذف نشوند (وگرنه آسان‌ترین راهِ
  //     پاس‌کردن این تست، پاک‌کردن همان متن‌ها بود).
  const HELP = ['set-sub', 'page-sub', 'hint', 'e-s', 'sh-sub'];
  const LEGAL_PAGE = 'about';
  const found = [];
  for (const [pg, h] of Object.entries(pages)) {
    for (const cls of HELP) {
      // [^<] به‌جای [\s\S]*? — وگرنه از divهای تودرتو رد می‌شد و مثلاً ۳۷۸
      // نویسه را به‌عنوان «یک متن راهنما» می‌شمرد (باگ نسخهٔ اول این تست).
      // (?!\/?div) — هم «</div>» و هم «<div» جلوی ادامه را می‌گیرند. نسخهٔ
      // اول فقط «</div>» را می‌دید، پس از divهای تودرتو رد می‌شد و مثلاً
      // ۳۷۸ نویسه را به‌عنوان «یک متن راهنما» می‌شمرد.
      const re = new RegExp('class="[^"]*\\b' + cls + '\\b[^"]*"[^>]*>((?:[^<]|<(?!\\/?div\\b))*)', 'g');
      let m;
      while ((m = re.exec(h)) !== null) {
        const txt = m[1].replace(/<[^>]+>/g, '').replace(/&[a-z#0-9]+;/g, 'x').trim();
        if (txt) found.push({ pg, cls, len: txt.length, txt });
      }
    }
  }
  const LIMIT = 90;
  const instructional = found.filter((r) => r.pg !== LEGAL_PAGE);
  const legal = found.filter((r) => r.pg === LEGAL_PAGE);
  const tooLong = instructional.filter((r) => r.len > LIMIT);
  ok(tooLong.length === 0,
    'متن «آموزشی» بلندتر از ' + LIMIT + ' نویسه (' + tooLong.length + '): ' +
    tooLong.slice(0, 4).map((r) => r.pg + '/' + r.cls + '=' + r.len + ': «' + r.txt.slice(0, 34) + '…»').join('، '));
  const totalChars = instructional.reduce((s, r) => s + r.len, 0);
  const TOTAL_BUDGET = 1700;
  ok(totalChars <= TOTAL_BUDGET,
    'جمع متن آموزشی ' + totalChars + ' نویسه است (سقف ' + TOTAL_BUDGET + ') — رابط دارد شلوغ می‌شود');
  console.log('    ✓ ' + instructional.length + ' متن آموزشی · جمع ' + totalChars +
    ' نویسه · بلندترین ' + (instructional.reduce((a, b) => (a.len > b.len ? a : b), { len: 0 }).len) + ' نویسه');

  // متن‌های حقوقی/اصالت باید «حضور» داشته باشند (نه کوتاه باشند)
  const aboutHtml = pages.about;
  for (const [needle, label] of [
    ['All rights reserved', 'اعلام حق نشر'],
    ['مالکیت انحصاری', 'ادعای مالکیت'],
    ['پیگرد قانونی', 'هشدار کپی‌برداری'],
    ['گواهی دیجیتال', 'اصالت امضا'],
    ['@Khode_Sushian', 'راه ارتباطی رسمی'],
  ]) {
    ok(aboutHtml.includes(needle),
      'متن حقوقی «' + label + '» از صفحهٔ دربارهٔ ما حذف شده — این‌ها محتوای عمدی‌اند، نه راهنما');
  }
  console.log('    ✓ ' + legal.length + ' متن حقوقی/اصالت در «دربارهٔ ما» حاضر است (معاف از سقف طول)');

  // متن‌های ایمنی باید «حفظ» شده باشند (کوتاه‌کردن راهنما نباید این‌ها را ببرد)
  const SAFETY = [
    ['پیشنهاد است، نه دستور معامله', 'سلب مسئولیت سیگنال'],
    ['معامله', 'اشاره به عدم اجرای خودکار معامله'],
    ['سود را تضمین نمی‌کند', 'هشدار تضمین‌نشدن سود'],
  ];
  // ⚠️ این صفحات با state=null رندر شده‌اند، پس کارت سیگنالی وجود ندارد و
  //   سلب مسئولیتِ سیگنال هم رندر نمی‌شود. نسخهٔ اول این تست به‌اشتباه
  //   «حذف شد» گزارش می‌کرد. متن ایمنی باید در «سورس» وجود داشته باشد.
  const uiSrc = read('js/ui.js');
  for (const [needle, label] of SAFETY) {
    ok(uiSrc.includes(needle),
      'متن ایمنی «' + label + '» از js/ui.js حذف شده — نباید در کوتاه‌کردن راهنما از دست برود');
  }
}

// ══════════════════════════════════════════════════════════════════════
group('۵) محافظِ سرریز روی مقدارهای کوتاه');
// ══════════════════════════════════════════════════════════════════════
{
  // عناصری که «یک مقدار کوتاه» نشان می‌دهند — شکستنشان به دو خط بی‌معناست
  const NOWRAP = ['.ev-time', '.countdown', '.r-chip', '.sc-tile-val', '.cc-stamp', '.chip'];
  for (const sel of NOWRAP) {
    const v = cssProp(sel, 'white-space') ||
      (new RegExp(sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '[^{]*\\{[^}]*white-space:\\s*nowrap').test(css) ? 'nowrap' : null);
    ok(v === 'nowrap', sel + ' باید white-space:nowrap داشته باشد (یافته: ' + v + ')');
  }
  // عناصر متنِ بلندِ توضیحی باید سقف ارتفاع داشته باشند
  ok(/-webkit-line-clamp/.test(css), '.j-sym .s2 باید -webkit-line-clamp داشته باشد تا ارتفاع ردیف‌ها قابل پیش‌بینی بماند');
  const ccMax = cssProp('.cc-stamp', 'max-width');
  ok(ccMax != null && /\d+px$/.test(ccMax),
    '.cc-stamp باید max-width پیکسلی داشته باشد (تاریخ شمسی کامل بلند است) — یافته: ' + ccMax);
  ok(nowrapOf('.cc-stamp') === 'nowrap',
    '.cc-stamp باید nowrap داشته باشد — یافته: ' + nowrapOf('.cc-stamp'));
  console.log('    ✓ ' + NOWRAP.length + ' عنصر nowrap + clamp برای متن بلند');
}

console.log('\n' + '═'.repeat(56));
if (failures) {
  console.log('✗ SMOKE LAYOUT FAILED — ' + failures + ' از ' + checks + ' بررسی شکست خورد');
  process.exit(1);
}
console.log('✅ SMOKE LAYOUT OK — ' + checks + ' بررسی پاس؛ چیدمان در ۳۲۰/۳۶۰/۳۹۰px سرریز ندارد و متن‌ها خوانا‌اند');
