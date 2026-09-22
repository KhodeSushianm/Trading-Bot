/* ══════════════════════════════════════════════════════════════════════
   onboarding.js — صفحهٔ ورود جوهری (پورت src/ui/onboarding.py دسکتاپ)

   چرا این فایل وجود دارد:
     v0.20.0 برای ویندوز یک صفحهٔ ورود نو ساخت (۶۱۶ خط: پنجرهٔ بی‌قاب جوهری،
     ستون برند، گام‌ها، قالب‌دهی خودکار کلید، لرزش خطا) و توکن‌های onb-bg و
     onb-glass هم به تم اضافه شد. در v0.21.0 بقیهٔ Aurora Glass 2.0 به اندروید
     پورت شد ولی این صفحه نه — یعنی توکن‌های onb-* در style.css «حاضر ولی
     بلااستفاده» بودند. این فایل آن نیمه‌کاری را تمام می‌کند.

     پیش‌تر جریان خوش‌آمدگویی اندروید «۵ مودال زنجیره‌ای» بود (سلب‌مسئولیت →
     هدیهٔ تریال → فعال‌سازی → نام → رصد پس‌زمینه). حالا یک صفحهٔ جوهریِ
     پیوسته با نقطه‌های گام است، همان‌طور که دسکتاپ دارد.

   معماری (عمداً دو لایه):
     • لایهٔ «خالص» — بدون DOM: onbPlan / onbFormatLicense / onbStepHtml /
       onbDots. خروجی رشتهٔ HTML است و در node بدون مرورگر تست می‌شود
       (tests/js/smoke_onboarding.js).
     • لایهٔ «DOM» — startOnboarding: فقط رویدادها و گذارها.
     چرا؟ چون بقیهٔ پروژه هم همین‌طور است و بدون این تفکیک، هیچ‌کدام از
     رفتارهای صفحهٔ ورود (به‌جز کلیک‌کردن دستی) قابل تست خودکار نبود.

   ⚠️ باگی که حین این پورت پیدا و رفع شد:
     فیلد کلید لایسنس maxlength="24" داشت، ولی کلید «زمان‌دار» ۲۶ نویسه است
     (XXXX-XXXX-XXXX-XXXX-YYMMDD). یعنی کاربر ۲ نویسهٔ آخر را نمی‌توانست
     تایپ کند، parseKeyInput هیچ‌وقت ۲۲ هگز نمی‌دید و null برمی‌گرداند →
     «این کلید نامعتبر است». پس قابلیت «لایسنس زمان‌دار/اشتراکی» که در
     v0.15.0 اضافه شده بود، روی اندروید از همان ابتدا کار نمی‌کرد.
     smoke_license.js هم نمی‌گرفتشان چون منطق را جدا می‌سنجد، نه maxlength
     رابط را. حالا هم رفع شده و هم smoke_onboarding.js قفلش می‌کند.
   ══════════════════════════════════════════════════════════════════════ */
(function (O) {
  'use strict';

  // ── نگاشت آیکون‌های دسکتاپ → نام‌های js/icons.js اندروید ──────────────
  // چرا: onboarding.py از نام‌هایی مثل sparkle/layers/shield/monitor/key/
  // check_circle استفاده می‌کند که در کتابخانهٔ آیکون اندروید نیستند. بدون
  // این نگاشت O.ico بی‌صدا به «dot» fallback می‌کرد و همهٔ چیپ‌ها یک‌شکل
  // می‌شدند (همان اشتباهی که در components.js هم نگهبانش را گذاشتیم).
  var ICO = {
    sparkle: 'bulb', layers: 'archive', shield: 'seal', monitor: 'hash',
    key: 'lock', check_circle: 'check-circle', x: 'x-circle', logo: 'seal',
    chevron_left: 'chevron-left', chevron_right: 'chevron-right'
  };
  function ic(name, size, cls) { return O.ico(ICO[name] || name, size, cls); }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function E(s) { return (O.esc || esc)(s); }

  // ════════════════════════════════════════════════════════════════════
  // لایهٔ خالص — بدون DOM، قابل تست در node
  // ════════════════════════════════════════════════════════════════════

  /** شناسهٔ گام‌ها — ترتیب نمایش (دسکتاپ: welcome → activate → done) */
  O.ONB_STEPS = ['welcome', 'name', 'activate', 'background', 'done'];

  /**
   * قالب‌دهی خودکار کلید لایسنس — port مو‌به‌مو از OnboardingDialog._fmt_license:
   *   clean = فقط ASCII alnum، بزرگ‌شده
   *   parts = چهارتا چهارتا از ۱۶ نویسهٔ اول
   *   rest  = ۶ نویسهٔ بعدی (تاریخ YYMMDD کلیدهای زمان‌دار)
   *   out   = parts با «-» + (rest ? "-"+rest : "")
   *
   * ⚠️ تفاوت عمدی با پایتون: هیچ. خروجی باید بایت‌به‌بایت یکی باشد، چون
   *   سازنده کلید را با src/license.py می‌سازد و کاربر اینجا تایپ می‌کند.
   *   smoke_onboarding.js این را با وکتورهای مشترک قفل می‌کند.
   */
  O.onbFormatLicense = function (raw) {
    var clean = String(raw == null ? '' : raw).toUpperCase().replace(/[^A-Z0-9]/g, '');
    var head = clean.slice(0, 16);
    var parts = [];
    for (var i = 0; i < head.length; i += 4) parts.push(head.slice(i, i + 4));
    var out = parts.join('-');
    var rest = clean.slice(16, 22);            // فقط ۶ رقم تاریخ، نه بیشتر
    if (rest) out += '-' + rest;
    return out;
  };

  /**
   * طول بیشینهٔ مجاز فیلد کلید.
   * چرا تابع است و نه عدد هاردکد: اگر روزی قالب کلید عوض شود، این هم باید
   * عوض شود — و smoke_onboarding.js آن را با طول واقعیِ کلیدِ تولیدشده
   * توسط O.licenseKeyFor مقایسه می‌کند. همان چیزی که نبودنش باعث باگ
   * maxlength="24" شد.
   */
  O.ONB_KEY_MAXLEN = 26;                        // XXXX-XXXX-XXXX-XXXX-YYMMDD

  /**
   * کدام گام‌ها برای این کاربر لازم است؟ (کاربر قدیمی نباید دوباره ببیندشان)
   * ctx: {storage, licensed, trial, nameDone, bgDone, disclaimerDone}
   * خروجی: آرایه‌ای از شناسهٔ گام‌ها — همیشه با 'done' تمام می‌شود.
   *
   * این تابع «خالص» است (فقط ctx را می‌خواند) تا قابل تست باشد؛ پیش‌تر این
   * منطق داخل زنجیرهٔ callbackهای مودال پخش بود و هیچ تستی رویش نبود.
   */
  O.onbPlan = function (ctx) {
    ctx = ctx || {};
    var plan = [];
    if (!ctx.disclaimerDone) plan.push('welcome');
    if (!ctx.nameDone) plan.push('name');
    // فعال‌سازی: اگر لایسنس دارد یا تریال فعال است، لازم نیست
    var hasAccess = !!ctx.licensed || !!(ctx.trial && ctx.trial.active);
    if (!hasAccess) plan.push('activate');
    if (!ctx.bgDone) plan.push('background');
    plan.push('done');
    return plan;
  };

  /** نقطه‌های گام (همان _dots دسکتاپ) */
  O.onbDots = function (total, current) {
    var h = '<div class="onb-dots">';
    for (var i = 0; i < total; i++) {
      h += '<span class="onb-dot' + (i === current ? ' on' : '') + '" aria-hidden="true"></span>';
    }
    return h + '</div>';
  };

  /** سربرگ برند — فشرده‌شدهٔ _build_brand_column دسکتاپ برای موبایل */
  O.onbBrandHtml = function (version) {
    var h = '<div class="onb-brand">';
    h += '<span class="onb-logo">' + ic('logo', 26) + '</span>';
    h += '<span class="onb-word"><b dir="ltr">ODIN</b><i dir="ltr">ASSISTANT</i></span>';
    if (version) h += '<span class="onb-ver">نسخهٔ ' + E(version) + '</span>';
    h += '</div>';
    return h;
  };

  /** سه ویژگی برند — همان فهرست _build_brand_column دسکتاپ */
  var BRAND_FEATURES = [
    ['layers', 'تحلیل چندلایه', 'تکنیکال + فاندامنتال + اخبار + تأییدیهٔ تریدینگ‌ویو'],
    ['shield', 'داور و دروازه‌های وتو', 'سیگنال فقط با پشتوانهٔ امتیاز — بدون استثنا'],
    ['bell', 'هشدار و رصد پس‌زمینه', 'حتی وقتی اپ بسته است']
  ];
  O.onbFeaturesHtml = function () {
    var h = '<div class="onb-feats">';
    BRAND_FEATURES.forEach(function (f) {
      h += '<div class="onb-feat"><span class="onb-fico">' + ic(f[0], 17) + '</span>' +
        '<span class="onb-fmain"><b>' + E(f[1]) + '</b><i>' + E(f[2]) + '</i></span></div>';
    });
    return h + '</div>';
  };

  /** بنر خطا + لرزش (همان _show_error دسکتاپ) */
  function errBox(msg) {
    if (!msg) return '<div class="onb-err hidden" id="onb-err"></div>';
    return '<div class="onb-err" id="onb-err">' + ic('alert', 15) + '<span>' + E(msg) + '</span></div>';
  }

  /**
   * HTML یک گام.
   * ⚠️ متن‌های سلب مسئولیت و هشدارها عمداً «کامل» نگه داشته شده‌اند:
   *   کوتاه‌کردن راهنما در v0.22.0 انجام شد ولی متن حقوقی/ایمنی مستثنا بود
   *   (و smoke_layout.js قفلش می‌کند). اینجا هم همان قاعده.
   */
  O.onbStepHtml = function (step, ctx) {
    ctx = ctx || {};
    if (step === 'welcome') {
      return '' +
        '<div class="onb-step" data-step="welcome">' +
        '<span class="onb-chip big">' + ic('sparkle', 24) + '</span>' +
        '<h2 class="onb-title">به ODIN خوش اومدی</h2>' +
        '<p class="onb-sub">قبل از شروع، دو قول صادقانه — چون این اپ دربارهٔ پولِ واقعی حرف می‌زند.</p>' +
        '<div class="onb-glass">' +
        '<div class="onb-promise"><b>' + ic('no-entry', 13) + ' ۱) معاملهٔ خودکار نمی‌کند.</b>' +
        '<span>هیچ معامله‌ای انجام نمی‌دهد، به هیچ بروکری وصل نیست و فقط تحلیل و سیگنال ' +
        '<u>پیشنهادی</u> می‌دهد. تصمیم و مسئولیت هر معامله با خودت است. رصد بازار فقط ' +
        '<u>تحلیل</u> را تکرار می‌کند.</span></div>' +
        '<div class="onb-promise"><b>' + ic('seal', 13) + ' ۲) حلقهٔ صداقت.</b>' +
        '<span>وقتی سیگنالی صادر نشود، دلیلش شفاف گفته می‌شود؛ دادهٔ در دسترس نباشد، آن ' +
        'مدرک «۰ امتیاز با علامت نامشخص» می‌گیرد — هیچ امتیازی ساخته نمی‌شود. نتایج ' +
        'سیگنال‌ها هم در ژورنال با قاعدهٔ محتاطانه ثبت می‌شود.</span></div>' +
        '<div class="onb-risk">' + ic('alert', 12) + ' هیچ سیستمی سود را تضمین نمی‌کند. ' +
        'معامله در فارکس پرریسک است.</div>' +
        '</div>' +
        '</div>';
    }

    if (step === 'name') {
      return '' +
        '<div class="onb-step" data-step="name">' +
        '<span class="onb-chip big">' + ic('user', 24) + '</span>' +
        '<h2 class="onb-title">اسمت چیه؟</h2>' +
        '<p class="onb-sub">تا کل برنامه — از خوش‌آمدگویی تا کارت‌های سیگنال — به نام خودت شخصی شود.</p>' +
        '<input id="onb-name" class="onb-input" type="text" placeholder="نام تو — مثلاً سوشیان" ' +
        'maxlength="24" autocomplete="off" autocorrect="off" spellcheck="false" ' +
        'value="' + E(ctx.currentName || '') + '">' +
        errBox('') +
        '</div>';
    }

    if (step === 'activate') {
      var note = '';
      if (ctx.reason === 'expired') {
        note = '<div class="onb-note bad">' + ic('alert', 13) +
          ' دورهٔ آزمایشی به پایان رسیده — برای ادامه، کلید لایسنس را وارد کن.</div>';
      } else if (ctx.reason === 'tampered') {
        note = '<div class="onb-note bad">' + ic('alert', 13) +
          ' ساعت دستگاه به عقب برگشته — دورهٔ آزمایشی نامعتبر شد. با کلید لایسنس فعال‌سازی کن.</div>';
      } else if (ctx.reason === 'key-expired') {
        note = '<div class="onb-note bad">' + ic('alert', 13) +
          ' لایسنس زمان‌دار منقضی شده — کلید تمدید را از سازنده بگیر.</div>';
      } else if (ctx.gift) {
        note = '<div class="onb-note good">' + ic('seal', 13) +
          ' <b>هدیهٔ خوش‌آمدگویی:</b> همهٔ امکانات — تحلیل، سیگنال، رصد پس‌زمینه و ' +
          'کارنامهٔ دقت — به مدت <b>۷ روز</b> رایگان و بدون محدودیت.</div>';
      }
      return '' +
        '<div class="onb-step" data-step="activate">' +
        '<span class="onb-chip big">' + ic('key', 24) + '</span>' +
        '<h2 class="onb-title">فعال‌سازی برنامه</h2>' +
        '<p class="onb-sub">هر کلید فقط روی همان دستگاه کار می‌کند — کاملاً آفلاین، بدون تماس شبکه‌ای.</p>' +
        note +
        // کارت کد دستگاه (همتای onb_glass دسکتاپ)
        '<div class="onb-glass">' +
        '<div class="onb-cap">' + ic('monitor', 15) + '<span>کد دستگاهٔ تو</span>' +
        '<span class="onb-grow"></span>' +
        '<button type="button" class="onb-ghost sm" data-onb="copy">' + ic('copy', 12) + ' کپی</button>' +
        '<button type="button" class="onb-ghost sm" data-onb="share">' + ic('telegram', 12) + ' ارسال</button>' +
        '</div>' +
        '<div id="onb-code" class="onb-code" dir="ltr">' + E(ctx.deviceCode || '————') + '</div>' +
        '<div class="onb-tg">' + ic('telegram', 13) +
        '<span>این کد را برای سازنده بفرست: <b dir="ltr">@Khode_Sushian</b></span></div>' +
        '</div>' +
        // کلید لایسنس
        '<div class="onb-cap" style="margin-top:14px">' + ic('key', 15) + '<span>کلید لایسنس</span>' +
        '<span class="onb-grow"></span>' +
        '<span class="onb-mini">زمان‌دارها بخش تاریخ هم دارند — همه را وارد کن</span></div>' +
        // ⚠️ maxlength باید ≥ طول کلید زمان‌دار (۲۶) باشد. با ۲۴ کاربر دو
        //    نویسهٔ آخر تاریخ را نمی‌توانست تایپ کند و کلید «نامعتبر» می‌شد.
        '<input id="onb-key" class="onb-input mono" dir="ltr" type="text" ' +
        'placeholder="XXXX-XXXX-XXXX-XXXX-YYMMDD" ' +
        'maxlength="' + O.ONB_KEY_MAXLEN + '" autocomplete="off" autocorrect="off" ' +
        'spellcheck="false" inputmode="text">' +
        errBox('') +
        // دکمه‌ها
        '<div class="onb-acts">' +
        '<button type="button" class="onb-ghost" data-onb="trial">' + ic('clock', 14) +
        ' شروع ۷ روز رایگان</button>' +
        '<button type="button" class="onb-primary" data-onb="activate">' + ic('check', 15) +
        ' فعال‌سازی</button>' +
        '</div>' +
        '</div>';
    }

    if (step === 'background') {
      return '' +
        '<div class="onb-step" data-step="background">' +
        '<span class="onb-chip big">' + ic('bell', 24) + '</span>' +
        '<h2 class="onb-title">سیگنال بدون باز کردن اپ؟</h2>' +
        '<p class="onb-sub">رصد پس‌زمینه هر چند دقیقه بازار را تحلیل می‌کند و سیگنال تازه یا خبر فوری را با اعلان می‌فرستد.</p>' +
        '<div class="onb-glass">' +
        '<div class="onb-promise"><b>' + ic('info', 13) + ' شفاف دربارهٔ اعلان ماندگار</b>' +
        '<span>یک اعلان ماندگار «در حال رصد» در نوار اعلان‌ها دیده می‌شود. طبیعی است و ' +
        'با یک لمس خاموش نمی‌شود — از تنظیمات اپ خاموشش کن.</span></div>' +
        '<div class="onb-promise"><b>' + ic('battery', 13) + ' اجازهٔ باتری</b>' +
        '<span>برای پایداری روی گوشی‌های سخت‌گیر، اجازهٔ «نادیده‌گرفتن بهینه‌سازی باتری» ' +
        'خواسته می‌شود. اختیاری است.</span></div>' +
        '<div class="onb-promise"><b>' + ic('no-entry', 13) + ' معامله همچنان خودکار نیست</b>' +
        '<span>رصد فقط تحلیل را تکرار می‌کند؛ تصمیم با توست.</span></div>' +
        '</div>' +
        errBox('') +
        '</div>';
    }

    if (step === 'done') {
      return '' +
        '<div class="onb-step center" data-step="done">' +
        '<span class="onb-chip huge ok">' + ic('check-circle', 34) + '</span>' +
        '<h2 class="onb-title">همه‌چیز آماده است!</h2>' +
        '<p class="onb-sub">' + E(ctx.doneMsg || 'اولین تحلیل به‌زودی اجرا می‌شود.') + '</p>' +
        '</div>';
    }
    return '';
  };

  /** دکمهٔ اصلیِ هر گام (برچسب + کنش) — جداست تا تست بتواند ترتیب را بسنجد */
  var PRIMARY = {
    welcome: { label: 'متوجه شدم — بزن بریم', act: 'accept-disclaimer', icon: 'chevron-left' },
    name: { label: 'ذخیره و ادامه', act: 'save-name', icon: 'chevron-left' },
    activate: null,                    // دکمه‌هایش داخل خود گام‌اند (trial / activate)
    background: { label: 'شروع رصد', act: 'enable-bg', icon: 'activity' },
    done: { label: 'ورود به برنامه', act: 'finish', icon: 'chevron-left' }
  };
  O.onbPrimary = function (step) { return PRIMARY[step] || null; };

  O.onbFooterHtml = function (step) {
    var p = PRIMARY[step];
    var h = '';
    if (step === 'background') {
      h += '<button type="button" class="onb-ghost" data-onb="skip-bg">فعلاً نه</button>';
    }
    if (p) {
      h += '<button type="button" class="onb-primary" data-onb="' + p.act + '">' +
        ic(p.icon, 15) + E(p.label) + '</button>';
    }
    return h;
  };

  // ════════════════════════════════════════════════════════════════════
  // لایهٔ DOM
  // ════════════════════════════════════════════════════════════════════

  var st = null;    // وضعیت جاریِ صفحهٔ ورود

  function el(id) { return document.getElementById(id); }

  function render() {
    var root = el('onb-root');
    if (!root || !st) return;
    var step = st.plan[st.i];
    var body = '';
    body += O.onbBrandHtml(st.ctx.version);
    if (step === 'welcome' || step === 'activate') body += '';   // برند بالا کافی است
    body += '<div class="onb-card">' + O.onbStepHtml(step, st.ctx) + '</div>';
    body += O.onbDots(st.plan.length, st.i);
    body += '<div class="onb-foot">' + O.onbFooterHtml(step) + '</div>';
    root.innerHTML = body;
    root.setAttribute('data-step', step);

    // فوکوس خودکار روی نخستین ورودی (همان name_input.setFocus دسکتاپ)
    var inp = root.querySelector('.onb-input');
    if (inp && st.animateFocus !== false) {
      setTimeout(function () { try { inp.focus(); } catch (e) { /* اختیاری */ } }, 260);
    }
    if (step === 'done') {
      setTimeout(function () { finish(); }, 1200);          // همان QTimer 1200ms دسکتاپ
    }
  }

  function go(delta) {
    if (!st) return;
    var ni = st.i + delta;
    if (ni < 0 || ni >= st.plan.length) return;
    st.i = ni;
    var root = el('onb-root');
    if (root) { root.classList.remove('onb-in'); void root.offsetWidth; root.classList.add('onb-in'); }
    render();
  }

  function shake(node) {
    if (!node) return;
    node.classList.remove('onb-shake');
    void node.offsetWidth;                       // ری‌استارت انیمیشن
    node.classList.add('onb-shake');
  }

  function showErr(msg) {
    var box = el('onb-err');
    if (!box) return;
    box.innerHTML = ic('alert', 15) + '<span>' + E(msg) + '</span>';
    box.classList.remove('hidden');
    shake(box);
  }

  function finish() {
    if (!st) return;
    var root = el('onb-root');
    var cb = st.ctx.onDone;
    st = null;
    if (root) {
      root.classList.add('onb-out');
      setTimeout(function () {
        root.classList.add('hidden');
        root.classList.remove('onb-out');
        root.innerHTML = '';
      }, 320);
    }
    if (cb) { try { cb(); } catch (e) { /* callback کاربر نباید ما را بخواباند */ } }
  }

  /**
   * شروع صفحهٔ ورود.
   * ctx: {storage, deviceId, deviceCode, version, licensed, trial, currentName,
   *       reason, saveName(name), saveBackground(bool), onActivated(), onDone()}
   */
  O.startOnboarding = function (ctx) {
    if (typeof document === 'undefined' || !document.getElementById) return false;
    if (O.SERVICE_MODE) return false;                  // حالت سرویس UI بوت نمی‌کند
    var root = el('onb-root');
    if (!root) return false;

    ctx = ctx || {};
    var store = ctx.storage || { get: function () { return ''; }, set: function () { } };
    st = {
      ctx: {
        version: ctx.version || '',
        deviceCode: ctx.deviceCode || '',
        currentName: ctx.currentName || '',
        reason: ctx.reason || '',
        gift: !ctx.trialExists && !ctx.licensed,
        doneMsg: ''
      },
      plan: O.onbPlan({
        disclaimerDone: store.get('disclaimer.ok') === '1',
        nameDone: store.get('onboarded.name') === '1',
        licensed: !!ctx.licensed,
        trial: ctx.trial,
        bgDone: store.get('onboarded.bg') === '1'
      }),
      i: 0
    };
    st._store = store;
    st._ctx = ctx;

    root.innerHTML = '';
    root.classList.remove('hidden', 'onb-out');
    root.classList.add('onb-in');
    render();
    return true;
  };

  /** آیا صفحهٔ ورود باز است؟ (برای گیتِ ناوبری — خوش‌آمدگویی ردنشدنی است) */
  O.onboardingOpen = function () { return !!st; };

  // ── رویدادها (delegation؛ چون گام‌ها باز-رندر می‌شوند) ────────────────
  function bind() {
    if (typeof document === 'undefined' || !document.addEventListener) return;

    // قالب‌دهی زندهٔ کلید — همان textChanged → _fmt_license دسکتاپ
    document.addEventListener('input', function (ev) {
      var t = ev.target;
      if (!t || t.id !== 'onb-key') return;
      var before = t.value;
      var after = O.onbFormatLicense(before);
      if (after !== before) {
        // حفظ موقعیت نشانک: اگر کاربر وسط رشته تایپ کند، پرش نشانک آزاردهنده است
        var pos = t.selectionStart == null ? after.length : t.selectionStart + (after.length - before.length);
        t.value = after;
        try { t.setSelectionRange(Math.max(0, pos), Math.max(0, pos)); } catch (e) { /* برخی WebViewها */ }
      }
    });

    document.addEventListener('click', function (ev) {
      if (!st) return;
      var b = ev.target && ev.target.closest ? ev.target.closest('[data-onb]') : null;
      if (!b) return;
      var act = b.getAttribute('data-onb');
      var ctx = st._ctx, store = st._store;
      var step = st.plan[st.i];

      if (act === 'accept-disclaimer') {
        store.set('disclaimer.ok', '1');
        go(1);
        return;
      }

      if (act === 'save-name') {
        var el2 = el('onb-name');
        var n = el2 ? String(el2.value || '').trim() : '';
        if (!n) {                                  // همان لرزشِ دسکتاپ وقتی نام خالی است
          showErr('اول نامت را بنویس — یا خالی نگذار.');
          shake(el2);
          if (el2 && el2.focus) el2.focus();
          return;
        }
        if (ctx.saveName) ctx.saveName(n);
        store.set('onboarded.name', '1');
        go(1);
        return;
      }

      if (act === 'copy') {
        O.copyText(st.ctx.deviceCode, 'کد دستگاه کپی شد', {
          onFail: function () { if (O.toast) O.toast('کد دستگاه (نگه‌دار): ' + st.ctx.deviceCode); }
        });
        b.innerHTML = ic('check', 12) + ' کپی شد';
        setTimeout(function () { if (b.isConnected) b.innerHTML = ic('copy', 12) + ' کپی'; }, 1600);
        return;
      }

      if (act === 'share') {
        var txt = 'کد دستگاه برای فعال‌سازی ODIN ASSISTANT:\n' + st.ctx.deviceCode;
        var sent = O.native && O.native.share ? O.native.share('کد دستگاه — ODIN ASSISTANT', txt) : false;
        if (!sent) {
          O.copyText(st.ctx.deviceCode, 'کپی شد — حالا در تلگرام بچسبان', {
            onFail: function () { if (O.toast) O.toast('کد دستگاه (نگه‌دار): ' + st.ctx.deviceCode); }
          });
        }
        return;
      }

      if (act === 'trial') {
        if (O.trialStart(store)) {
          if (ctx.onTrial) ctx.onTrial();
          st.ctx.doneMsg = 'دورهٔ آزمایشی ۷ روزه شروع شد — همهٔ امکانات فعال است.';
          st.plan = O.onbPlan({ disclaimerDone: true, nameDone: store.get('onboarded.name') === '1', licensed: false, trial: { active: true }, bgDone: store.get('onboarded.bg') === '1' });
          // پرش به گام بعد از activate
          var ai = st.plan.indexOf('activate');
          st.i = ai >= 0 ? ai + 1 : st.plan.length - 1;
          render();
        } else {
          showErr('دورهٔ آزمایشی پیش‌تر استفاده شده — با کلید لایسنس فعال‌سازی کن.');
          shake(el('onb-key'));
        }
        return;
      }

      if (act === 'activate') {
        var keyEl = el('onb-key');
        var key = keyEl ? String(keyEl.value || '') : '';
        if (!key.trim()) {
          showErr('کلید لایسنس را وارد کن — یا دورهٔ آزمایشی را شروع کن.');
          shake(keyEl);
          return;
        }
        var okFlag = ctx.deviceId && O.validateKey(key, st.ctx.deviceCode) &&
          O.licActivate(store, key, ctx.deviceId, ctx.currentName || '');
        if (okFlag) {
          if (ctx.onActivated) ctx.onActivated();
          st.ctx.doneMsg = 'لایسنس با موفقیت فعال شد — همهٔ امکانات بدون محدودیت زمانی.';
          st.plan = O.onbPlan({ disclaimerDone: true, nameDone: store.get('onboarded.name') === '1', licensed: true, trial: null, bgDone: store.get('onboarded.bg') === '1' });
          var ai2 = st.plan.indexOf('activate');
          st.i = ai2 >= 0 ? ai2 + 1 : st.plan.length - 1;
          render();
        } else {
          showErr(!ctx.deviceId
            ? 'شناسهٔ دستگاه در دسترس نیست — اپ را ببند و دوباره باز کن.'
            : 'این کلید نامعتبر است یا برای دستگاه دیگری ساخته شده.');
          shake(keyEl);
        }
        return;
      }

      if (act === 'enable-bg' || act === 'skip-bg') {
        var on = act === 'enable-bg';
        if (ctx.saveBackground) ctx.saveBackground(on);
        store.set('onboarded.bg', '1');
        if (on && O.native) {
          O.native.startBackground();
          if (!O.native.isIgnoringBattery()) O.native.requestIgnoreBattery();
        }
        if (step === 'background') {
          // اگر «رصد» آخرین گامِ باقی‌مانده بود، مستقیم به done
          if (st.i + 1 < st.plan.length) go(1); else finish();
        }
        return;
      }

      if (act === 'finish') { finish(); return; }
    });
  }

  bind();
  O.onbBind = bind;      // برای تست/بوتِ دوم

})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
