/* ══════════════════════════════════════════════════════════════════════
   components.js — اجزای بصری «Aurora Glass 2.0» (پورت v0.21.0)

   همتای اندرویدیِ src/ui/widgets.py نسخهٔ دسکتاپ. این هشت جزء در v0.20.0
   به ویندوز اضافه شدند و تا پیش از این فایل، هیچ معادلی در اندروید نداشتند:

     دسکتاپ (widgets.py)      ↔   اینجا
     ─────────────────────────────────────────────
     IconChip                 ↔   O.iconChip
     Chip                     ↔   O.chip
     Stars                    ↔   O.stars
     SectionHeader            ↔   O.sectionHeader
     SegmentedControl         ↔   O.segmented
     ConsoleCard              ↔   O.consoleCard  (+ O.consoleColorize)
     KpiCard                  ↔   O.kpiCard      (+ O.kpiRow)
     SignalCard._parse_reasons↔   O.parseReasons

   قراردادهای پروژه که اینجا رعایت شده‌اند:
     • صفر ایموجی در خروجی (v0.13.0) — رشته‌های موتور با O.icoStr آیکونی می‌شوند.
     • همهٔ رنگ‌ها از توکن‌های CSS (style.css :root) می‌آیند، نه هاردکد؛
       پاریتی با theme.py توسط tests/js/smoke_theme_parity.js قفل شده است.
     • متن‌های کاربر/موتور همیشه esc() می‌شوند (XSS در WebView).
     • منطق parseReasons و consoleColorize «مو‌به‌مو» از widgets.py port شده تا
       خروجی دو پلتفرم یکی بماند.
   ══════════════════════════════════════════════════════════════════════ */
(function (O) {
  'use strict';

  // ── ابزارهای محلی ─────────────────────────────────────────────────────
  // O.esc در ui.js تعریف می‌شود؛ چون components.js «پیش از» ui.js بار می‌شود،
  // یک نسخهٔ محلی هم داریم و در زمانِ صدا زدن هرکدام حاضر بود استفاده می‌شود.
  function localEsc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function E(s) { return (O.esc || localEsc)(s); }

  // esc سپس آیکونی‌کردن ایموجی — همان قرارداد eico() در ui.js.
  // چرا داخل خودِ اجزا و نه در فراخوان: قرارداد پروژه «صفر ایموجی در خروجی»
  // است (v0.13.0) و رشته‌های موتور عمداً ایموجی دارند (چون با پایتون parity
  // دارند و نباید دست بخورند). اگر تبدیل را به فراخوان واگذار کنیم، هر
  // فراخوانِ فراموش‌کار یک ایموجی به رابط نشت می‌دهد. پس جزء خودش تضمین می‌کند.
  function ei(s, size) {
    var e = E(s);
    return O.icoStr ? O.icoStr(e, size || 12) : e;
  }

  // ارقام فارسی → لاتین (همتای _en_num در widgets.py)
  var FA_DIGITS = { '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9' };
  function enNum(s) {
    return String(s == null ? '' : s).replace(/[۰-۹]/g, function (d) { return FA_DIGITS[d]; });
  }
  O.enNum = enNum;

  // تُن‌های مجاز — هر چیز ناشناخته به neutral برمی‌گردد تا کلاس CSS شبح نسازد
  var TONES = { '': 1, neutral: 1, ink: 1, green: 1, red: 1, amber: 1, brand: 1, outline: 1 };
  function tone(t) {
    t = String(t || '');
    if (!TONES[t]) return '';
    return t === 'neutral' ? '' : t;
  }
  function toneCls(t) { var v = tone(t); return v ? ' tone-' + v : ''; }

  // نگاشت آیکون‌های دسکتاپ → نام‌های موجود در js/icons.js اندروید.
  // چرا لازم است: widgets.py از نام‌هایی مثل trend_up/zap/layers/gauge/eye/report
  // استفاده می‌کند که در کتابخانهٔ آیکون اندروید وجود ندارند؛ بدون این نگاشت
  // O.ico بی‌صدا به «dot» fallback می‌کرد و همهٔ ردیف‌های دلیل یک‌شکل می‌شدند.
  var ICON_ALIAS = {
    trend_up: 'trend-up', trend_down: 'trend-down', report: 'news', eye: 'search',
    zap: 'activity', layers: 'pin', gauge: 'chart-line', chart: 'chart-bar',
    star_filled: 'star', star: 'star-outline', copy: 'copy', check: 'check',
    alert: 'alert', calendar: 'calendar', clock: 'clock'
  };
  function icon(name) {
    name = String(name || '');
    if (O.HAS_ICON && !O.HAS_ICON(name) && !ICON_ALIAS[name]) name = 'info';
    return ICON_ALIAS[name] || name;
  }

  // ── کپیِ مشترک (پیش‌تر سه‌جا در app.js تکراری نوشته شده بود) ──────────
  // ترتیب: clipboard API → fallback با textarea/execCommand → مودالِ متنِ قابل‌انتخاب.
  // روی WebView اندروید navigator.clipboard ممکن است بدون HTTPS/مجوز رد شود،
  // پس fallback لازم است نه تزئینی.
  O.copyText = function (text, okMsg, opts) {
    opts = opts || {};
    text = String(text == null ? '' : text);
    var say = function (m) { if (O.toast) O.toast(m); };
    function fallback() {
      try {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.top = '0';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        var done = document.execCommand('copy');
        document.body.removeChild(ta);
        if (done) { say(okMsg || 'کپی شد'); return true; }
      } catch (e) { /* ادامه به آخرین چاره */ }
      // فراخوان می‌تواند رفتارِ «آخرین چاره» را عوض کند (مثلاً کد دستگاه
      // باید در خودِ toast دیده شود تا کاربر گمش نکند، نه در یک مودال).
      if (opts.onFail) { try { opts.onFail(); } catch (e) { /* ignore */ } }
      else if (O.modal) {
        O.modal('کپی نشد — دستی انتخاب کن',
          '<div class="text-input" style="max-height:220px;overflow:auto;font-size:10.5px;' +
          'direction:rtl;user-select:text;-webkit-user-select:text">' + E(text) + '</div>',
          [{ label: 'بستن', cls: 'ghost' }]);
      } else say('کپی ممکن نشد');
      return false;
    }
    if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { say(okMsg || 'کپی شد'); }, fallback);
    } else fallback();
  };

  // ── ۱. Chip — برچسب قرصی با تُن معنایی ───────────────────────────────
  // chip(text, tone, opts{icon, raw}) — اگر opts.raw باشد، text از قبل HTML است.
  O.chip = function (text, t, opts) {
    opts = opts || {};
    var inner = opts.raw ? String(text == null ? '' : text) : ei(text, opts.icoSize || 11);
    if (opts.icon) inner = O.ico(icon(opts.icon), opts.iconSize || 11) + '<span>' + inner + '</span>';
    return '<span class="chip' + toneCls(t) + '">' + inner + '</span>';
  };

  // ── ۲. IconChip — مربع گردِ رنگی با آیکون در مرکز ─────────────────────
  // radius: در دسکتاپ max(8, size*0.32) است؛ در CSS با border-radius:32% همان
  // نسبت به‌دست می‌آید، پس اینجا فقط اندازه را ست می‌کنیم.
  O.iconChip = function (name, size, t) {
    var s = Math.max(16, Math.trunc(size || 36));
    var inner = Math.max(10, Math.trunc(s * 0.56));
    if (inner % 2) inner -= 1;                       // فرد نباشد (همان قید دسکتاپ)
    return '<span class="icon-chip' + toneCls(t) + '" style="width:' + s + 'px;height:' + s + 'px">' +
      O.ico(icon(name), inner) + '</span>';
  };

  // ── ۳. Stars — رتبهٔ ستاره‌ای (value از total) ────────────────────────
  // تفاوت با O.starIcons قدیمی: خانه‌های «پر‌نشده» هم رسم می‌شوند تا ۲ از ۵
  // با ۲ از ۵ یکی دیده نشود و طول ردیف ثابت بماند (همان رفتار Stars دسکتاپ).
  O.stars = function (value, total, size) {
    total = Math.max(1, Math.trunc(total || 5));
    value = Math.max(0, Math.min(total, Math.trunc(value || 0)));
    var s = Math.max(8, Math.trunc(size || 14));
    var h = '<span class="stars" role="img" aria-label="' + value + ' از ' + total + '">';
    for (var i = 0; i < total; i++) {
      var on = i < value;
      h += '<span class="ico-wrap' + (on ? ' on' : ' off') + '">' +
        O.ico(on ? 'star' : 'star-outline', s) + '</span>';
    }
    return h + '</span>';
  };

  // ── ۴. SectionHeader — چیپ آیکون + عنوان + زیرعنوان + دنباله ──────────
  O.sectionHeader = function (name, title, sub, trailing, opts) {
    opts = opts || {};
    var h = '<div class="section-header">';
    h += O.iconChip(name, opts.chipSize || 42, opts.tone || '');
    h += '<div class="sh-main"><div class="sh-title">' + ei(title, 15) + '</div>';
    if (sub) h += '<div class="sh-sub">' + (opts.rawSub ? String(sub) : ei(sub, 12)) + '</div>';
    h += '</div>';
    if (trailing) h += '<div class="sh-trail">' + trailing + '</div>';
    return h + '</div>';
  };

  // ── ۵. SegmentedControl — کلید چندحالتهٔ قرصی (مثل H1/H4) ────────────
  // options: [[key, label], ...] · انتخاب با data-seg-group / data-seg-key
  // توسط delegation در پایین همین فایل هندل می‌شود.
  O.segmented = function (group, options, current) {
    var h = '<div class="segmented" data-seg-group="' + E(group) + '">';
    (options || []).forEach(function (o) {
      var key = o[0], label = o[1];
      h += '<button type="button" data-seg-key="' + E(key) + '"' +
        (String(key) === String(current) ? ' class="on" aria-pressed="true"' : ' aria-pressed="false"') +
        '>' + ei(label, 11) + '</button>';
    });
    return h + '</div>';
  };

  // ── ۶. consoleColorize — رنگ‌آمیزی ساختاری متن گزارش ─────────────────
  // port مو‌به‌مو از ConsoleCard.colorize در src/ui/widgets.py:
  //   جداکننده‌ها dim · «───» برند · سرتیترهای ایموجی‌دار برجسته ·
  //   خط سیگنال سبز · خط خطا قرمز · بقیه متن عادی.
  // تفاوت ضروری با دسکتاپ: اینجا ایموجی‌ها با O.icoStr به آیکون تبدیل می‌شوند
  // چون قرارداد اپ اندروید «صفر ایموجی در خروجی» است (v0.13.0). تشخیصِ نوع خط
  // روی متن «خام» انجام می‌شود (قبل از آیکونی‌کردن)، دقیقاً مثل پایتون.
  var HEAVY_FIRST = '🔎⚖📊🕒📅💹🛑🎯⚠📍🌊💰🧭📈📉✅❌🟢🔴🟡';
  O.consoleColorize = function (text, icoSize) {
    var sz = icoSize || 12;
    var lines = String(text == null ? '' : text).split('\n');
    var out = [];
    for (var i = 0; i < lines.length; i++) {
      var raw = lines[i].replace(/\r$/, '');
      var s = raw.trim();
      if (!s) { out.push('&nbsp;'); continue; }

      var body = O.icoStr ? O.icoStr(localEsc(raw), sz) : localEsc(raw);
      var cls;
      var onlyRule = true;
      for (var k = 0; k < s.length; k++) {
        if ('━─═'.indexOf(s.charAt(k)) < 0) { onlyRule = false; break; }
      }
      if (s.charAt(0) === '═' || (onlyRule && s.length > 3)) cls = 'cd';
      else if (s.indexOf('───') === 0) cls = 'cb';
      else if (HEAVY_FIRST.indexOf(Array.from(s)[0]) >= 0) cls = 'cw';
      else if (s.indexOf('سیگنال') >= 0 && (s.indexOf('—') >= 0 || s.indexOf('✅') >= 0)) cls = 'cg';
      else if (s.indexOf('❌') === 0 || s.slice(0, 6).indexOf('خطا') >= 0) cls = 'cr';
      else cls = '';
      out.push(cls ? '<span class="' + cls + '">' + body + '</span>' : body);
    }
    return out.join('<br>');
  };

  // ── ۷. ConsoleCard — سربرگ روشن روی بدنهٔ تیره ───────────────────────
  // o: {id, title, sub, icon, text, stamp, copy=true, icoSize}
  // متن خام در registry نگه داشته می‌شود تا دکمهٔ کپی همان را کپی کند
  // (نه HTML رنگ‌شده را).
  var CONSOLE_REG = {};
  var consoleSeq = 0;
  O.consoleCard = function (o) {
    o = o || {};
    var text = String(o.text == null ? '' : o.text);
    var id = o.id || ('cc-' + (++consoleSeq));
    CONSOLE_REG[id] = text;

    var h = '<div class="console-card" id="' + E(id) + '">';
    h += '<div class="cc-head">';
    h += O.iconChip(o.icon || 'news', 34, '');
    h += '<div class="cc-titles"><div class="cc-title">' + ei(o.title || '', 13) + '</div>';
    if (o.sub) h += '<div class="cc-sub">' + ei(o.sub, 11) + '</div>';
    h += '</div>';
    if (o.stamp) h += '<span class="cc-stamp">' + E(o.stamp) + '</span>';
    if (o.copy !== false) {
      h += '<button type="button" class="cc-copy" data-copy-id="' + E(id) + '" ' +
        'aria-label="کپی متن کامل">' + O.ico('copy', 15) + '</button>';
    }
    h += '</div>';
    if (text.trim()) {
      h += '<div class="cc-body">' + O.consoleColorize(text, o.icoSize) + '</div>';
    } else {
      h += '<div class="cc-empty">' + E(o.placeholder || 'متنی نیست') + '</div>';
    }
    return h + '</div>';
  };

  // ── ۸. KpiCard — چیپ آیکون + عدد بزرگ + برچسب ────────────────────────
  // o: {icon, value, label, tone}
  O.kpiCard = function (o) {
    o = o || {};
    var t = tone(o.tone);
    return '<div class="kpi-card">' +
      O.iconChip(o.icon || 'chart-bar', 30, t) +
      '<div class="kv-main">' +
      '<div class="kv-val' + (t ? ' tone-' + t : '') + '">' + ei(o.value == null ? '—' : o.value, 13) + '</div>' +
      '<div class="kv-lab">' + ei(o.label || '', 11) + '</div>' +
      '</div></div>';
  };
  // ردیف KPI (دو ستونه در موبایل)
  O.kpiRow = function (items) {
    if (!items || !items.length) return '';
    var h = '<div class="kpi-row">';
    items.forEach(function (it) { h += O.kpiCard(it); });
    return h + '</div>';
  };

  // ── ۹. parseReasons — پارسر محافظه‌کارِ دلایل از متن سیگنال ───────────
  // port مستقیم از SignalCard._parse_reasons در src/ui/widgets.py:
  //   • خط «…امتیاز نگرفتند…» حالت negative را روشن می‌کند (بعد از آن دلیل
  //     مثبت ثبت نمی‌شود — چون آن بخش «مدارکی که امتیاز نگرفتند» است).
  //   • خطوط با «•» → هشدار.
  //   • الگو: [نشان] برچسب (+N) — توضیح
  //   • حداکثر ۸ دلیل؛ هر استثنا → خروجی خالی (نه کرش).
  var REASON_RE = /^(?:[^\w\s]+\s*)?(.+?)\s*\(\+([۰-۹0-9]+)\)\s*(?:—|-)\s*(.*)$/;
  var ICON_HINTS = [
    ['روند', 'trend_up'], ['H4', 'trend_up'], ['H1', 'trend_up'],
    ['تقویم', 'calendar'], ['رویداد', 'calendar'], ['خبر', 'news'],
    ['اخبار', 'news'], ['تریدینگ', 'eye'], ['TradingView', 'eye'],
    ['نوسان', 'zap'], ['ATR', 'zap'], ['حمایت', 'layers'],
    ['مقاومت', 'layers'], ['سشن', 'clock'], ['زمان', 'clock'],
    ['فاصله', 'gauge'], ['مومنتوم', 'zap'], ['حجم', 'chart']
  ];
  O.parseReasons = function (text) {
    var reasons = [], warns = [];
    if (!text) return { reasons: reasons, warns: warns };
    try {
      var negative = false;
      var lines = String(text).split('\n');
      for (var i = 0; i < lines.length; i++) {
        var line = lines[i].replace(/\r$/, '').trim();
        if (line.indexOf('امتیاز نگرفتند') >= 0) { negative = true; continue; }
        if (line.charAt(0) === '•') {
          warns.push(line.replace(/^[•\s]+/, '').trim());
          continue;
        }
        var m = REASON_RE.exec(line);
        if (!m || negative) continue;
        var label = m[1].trim();
        var pts = parseInt(enNum(m[2]), 10);
        var detail = m[3].trim();
        var ic = 'check';
        for (var j = 0; j < ICON_HINTS.length; j++) {
          if (label.indexOf(ICON_HINTS[j][0]) >= 0 || detail.indexOf(ICON_HINTS[j][0]) >= 0) {
            ic = ICON_HINTS[j][1]; break;
          }
        }
        // نام آیکون را همین‌جا به نام اندرویدی نگاشت می‌کنیم (نه در لایهٔ رندر)
        // تا مصرف‌کنندهٔ parseReasons خروجیِ مستقیماً قابل‌استفاده بگیرد.
        reasons.push({ icon: icon(ic), label: label, pts: isNaN(pts) ? 0 : pts, detail: detail });
      }
    } catch (e) {
      return { reasons: [], warns: [] };
    }
    return { reasons: reasons.slice(0, 8), warns: warns };
  };

  // ردیف دلیل با چیپ آیکون + متن + چیپ امتیاز (همتای sigreason دسکتاپ)
  O.reasonRow = function (r) {
    var txt = r.detail ? (ei(r.label, 12) + ' — ' + ei(r.detail, 12)) : ei(r.label, 12);
    var pts = r.pts
      ? '<span class="sc-reason-pts">' + O.chip('+' + (O.faNum ? O.faNum(r.pts) : r.pts), 'green') + '</span>'
      : '';
    return '<div class="sc-reason">' + O.iconChip(r.icon || 'check', 24, 'green') +
      '<div class="sc-reason-txt">' + txt + '</div>' + pts + '</div>';
  };
  O.warnRow = function (msg) {
    return '<div class="sc-reason">' + O.iconChip('alert', 24, 'amber') +
      '<div class="sc-reason-txt">' + ei(msg, 12) + '</div></div>';
  };

  // ── ۱۰. SignalCard — لایهٔ ساختاریافتهٔ سیگنال ──────────────────────
  // ⚠️ طراحی عمدی: این تابع «کارت سیگنال کامل» را از صفر نمی‌سازد.
  //   کارت موجود در ui.js اطلاعاتی دارد که SignalCard دسکتاپ ندارد
  //   (scoreBar، جدول مدارک، ATR، ریسک پیشنهادی، هشدار سیگنال تکراری).
  //   جایگزین‌کردنش یک رگرسیون بود. پس اینجا فقط «اجزای ساختاریافتهٔ نو»
  //   ساخته می‌شوند و ui.js آن‌ها را در همان کارت موجود سوار می‌کند:
  //     O.signalCard(...) → ردیف چیپ‌ها + کاشی‌های ورود/SL/TP + دلایل پارس‌شده
  O.signalCard = function (sig, opts) {
    opts = opts || {};
    var s = sig || {};
    var buy = String(s.direction || '').toUpperCase().charAt(0) === 'B';
    var faNum = O.faNum || function (n) { return String(n); };
    var h = '';

    // ── ردیف ۱: جهت · وضعیت ارسال · ستاره‌ها ────────────────────────
    h += '<div class="sc-row">';
    h += O.chip(buy ? 'سیگنال خرید' : 'سیگنال فروش', buy ? 'green' : 'red',
      { icon: buy ? 'arrow-up' : 'arrow-down', iconSize: 11 });
    if (opts.showSent !== false) {
      var sent = s.sent !== false;
      h += O.chip(sent ? 'ارسال شد' : 'ارسال نشد', sent ? 'ink' : 'amber');
    }
    h += '<span class="sc-grow"></span>';
    h += O.stars(s.stars || 0, 5, 14);
    h += '</div>';

    // ── ردیف ۲: جفت‌ارز + نام فارسی + چیپ امتیاز ──────────────────────
    if (s.symbol) {
      var pair = String(s.symbol);
      if (pair.length === 6) pair = pair.slice(0, 3) + '/' + pair.slice(3);
      h += '<div class="sc-row"><span class="sc-pair">\u200E' + E(pair) + '</span>';
      if (s.fa_name) h += '<span class="sc-faname">' + ei(s.fa_name, 11) + '</span>';
      h += '<span class="sc-grow"></span>';
      if (s.score != null) {
        h += O.chip('امتیاز ' + faNum(s.score) + ' از ' + faNum(s.max_score == null ? 11 : s.max_score), 'ink');
      }
      h += '</div>';
    }

    // ── ردیف ۳: زمان + سشن + ریسک‌به‌ریوارد ───────────────────────────
    var meta = '';
    if (opts.stamp) meta += O.chip(opts.stamp, 'outline');
    if (s.session_fa) meta += O.chip('سشن ' + s.session_fa, 'brand');
    if (s.rr) meta += O.chip('ریسک به ریوارد ۱:' + (O.faRatio ? O.faRatio(s.rr) : s.rr), 'green');
    if (meta) h += '<div class="sc-row">' + meta + '</div>';

    // ── ردیف ۴: کاشی‌های ورود / حد ضرر / هدف ──────────────────────────
    // opts.sub=true → زیر هر عدد «فاصله به پیپ» هم می‌آید. چرا اختیاری:
    //   کارت دسکتاپ فقط عدد دارد، ولی کارت اندروید از قبل فاصلهٔ پیپ را
    //   نشان می‌داد؛ حذفش یک رگرسیون اطلاعاتی بود. پس ساختار از دسکتاپ
    //   گرفته شد و این یک قلمِ غنی‌ترِ اندروید روی آن حفظ شد.
    var fmt = O.fmtPrice || function (v) { return String(v); };
    var pips = O.faPips || null;
    function price(v) {
      var n = parseFloat(v);
      if (!isFinite(n)) return '—';
      try { return '\u200E' + fmt(n, s.pip); } catch (e) { return '—'; }
    }
    function dist(a, b) {
      if (!pips || !isFinite(parseFloat(a)) || !isFinite(parseFloat(b))) return '';
      try { return pips(Math.abs(parseFloat(a) - parseFloat(b)), s.pip, s.is_gold); } catch (e) { return ''; }
    }
    if (opts.tiles !== false) {
      var tiles = [
        { cap: 'ورود', val: price(s.entry), tone: '', sub: opts.sub ? 'قیمت فعلی' : '' },
        { cap: 'حد ضرر', val: price(s.sl), tone: 'red', sub: opts.sub ? dist(s.entry, s.sl) : '' },
        { cap: 'هدف', val: price(s.tp), tone: 'green', sub: opts.sub ? dist(s.tp, s.entry) : '' }
      ];
      h += '<div class="sc-tiles">';
      tiles.forEach(function (t) {
        h += '<div class="sc-tile"><div class="sc-tile-cap">' + E(t.cap) + '</div>' +
          '<div class="sc-tile-val' + (t.tone ? ' tone-' + t.tone : '') + '">' + E(t.val) + '</div>';
        if (t.sub) h += '<div class="sc-tile-sub">' + E(t.sub) + '</div>';
        h += '</div>';
      });
      h += '</div>';
    }

    // ── ردیف ۵: دلایل پارس‌شده از متن سیگنال (+ هشدارها) ───────────────
    if (opts.reasons !== false) {
      var parsed = O.parseReasons(s.text || '');
      if (parsed.reasons.length) {
        h += '<div class="sc-reasons-cap">چرا این سیگنال صادر شد؟</div>';
        parsed.reasons.forEach(function (r) { h += O.reasonRow(r); });
      }
      if (opts.showWarns !== false) {
        parsed.warns.slice(0, 3).forEach(function (w) { h += O.warnRow(w); });
      }
    }

    return h;
  };

  // ── delegation: کپی کنسول‌کارت و کلید چندحالته ──────────────────────
  // یک listener سراسری به‌جای اتصال به هر دکمه — چون صفحه‌ها هر بار
  // باز-رندر می‌شوند و اتصال مستقیم نشت می‌داد.
  if (typeof document !== 'undefined' && document.addEventListener) {
    document.addEventListener('click', function (ev) {
      var el = ev.target && ev.target.closest ? ev.target.closest('[data-copy-id],[data-seg-key]') : null;
      if (!el) return;

      if (el.hasAttribute('data-copy-id')) {
        var cid = el.getAttribute('data-copy-id');
        O.copyText(CONSOLE_REG[cid] || '', 'در کلیپ‌بورد کپی شد');
        el.classList.add('done');
        var prev = el.innerHTML;
        el.innerHTML = O.ico('check', 15);
        setTimeout(function () { el.classList.remove('done'); el.innerHTML = prev; }, 1400);
        if (O.haptic) { try { O.haptic(); } catch (e) { /* اختیاری */ } }
        return;
      }

      if (el.hasAttribute('data-seg-key')) {
        var wrap = el.closest('.segmented');
        if (!wrap) return;
        Array.prototype.forEach.call(wrap.children, function (b) {
          var on = b === el;
          b.classList.toggle('on', on);
          b.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
        var key = el.getAttribute('data-seg-key');
        if (O.onSegmented) O.onSegmented(wrap.getAttribute('data-seg-group'), key);
      }
    });
  }

  /** برای تست: پاک‌کردن registry کنسول‌کارت‌ها */
  O._consoleRegistry = CONSOLE_REG;
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
