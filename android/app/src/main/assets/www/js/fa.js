/* ابزار مشترک متن فارسی — پورت دقیق src/fa.py
 *
 * قرارداد پروژه:
 *   • شمارش‌ها، امتیازها، پیپ و درصدها → ارقام فارسی (۰-۹)
 *   • قیمت‌ها → ارقام لاتین (کاربر آن‌ها را در متاتریدر تایپ می‌کند)
 */
(function (O) {
  'use strict';

  var FA_D = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

  O.WEEKDAY_FA = { 0: 'دوشنبه', 1: 'سه‌شنبه', 2: 'چهارشنبه', 3: 'پنجشنبه', 4: 'جمعه', 5: 'شنبه', 6: 'یکشنبه' };
  O.MONTH_FA = { 1: 'ژانویه', 2: 'فوریه', 3: 'مارس', 4: 'آوریل', 5: 'مه', 6: 'ژوئن', 7: 'ژوئیه', 8: 'اوت', 9: 'سپتامبر', 10: 'اکتبر', 11: 'نوامبر', 12: 'دسامبر' };

  // ── قالب‌بندی اعداد مثل f-string پایتون (گردش «نصف به زوج») ──
  // JS در .toFixed نیمه را به بالا گرد می‌کند، پایتون به زوج؛ برای برابری
  // مو‌به‌مو با متن‌های نسخهٔ دسکتاپ، از بسط اعشاری دقیق double تصمیم می‌گیریم.
  O.pyFixed = function (v, dec) {
    if (!isFinite(v)) return String(v);
    var neg = v < 0 || Object.is(v, -0);
    var s = Math.abs(v).toPrecision(21);
    if (s.indexOf('e') >= 0 || s.indexOf('E') >= 0) return v.toFixed(dec);  // خارج از برد قیمت‌ها
    var dot = s.indexOf('.');
    if (dot < 0) { s += '.'; dot = s.length - 1; }
    var ip = s.slice(0, dot);
    var fp = s.slice(dot + 1) + '0000000000';
    var keep = fp.slice(0, dec);
    var rest = fp.slice(dec, dec + 13);
    var half = '5' + '0'.repeat(Math.max(0, rest.length - 1));
    var up;
    if (rest.length === 0) up = false;
    else if (rest > half) up = true;
    else if (rest < half) up = false;
    else {                                   // دقیقاً نصف → به زوج
      var last = keep ? +keep[keep.length - 1] : +ip[ip.length - 1];
      up = last % 2 === 1;
    }
    var digits = (ip + keep).split('').map(Number);
    if (up) {
      var i = digits.length - 1;
      while (i >= 0) { digits[i]++; if (digits[i] < 10) break; digits[i] = 0; i--; }
      if (i < 0) digits.unshift(1);
    }
    var ipLen = digits.length - dec;
    var out = digits.slice(0, ipLen).join('') + (dec ? '.' + digits.slice(ipLen).join('') : '');
    return (neg ? '-' : '') + out;
  };

  // round() پایتون (نصف به زوج) برای اعداد صحیح
  O.pyRound = function (x) {
    var fl = Math.floor(x), frac = x - fl;
    if (frac > 0.5) return fl + 1;
    if (frac < 0.5) return fl;
    return fl % 2 === 0 ? fl : fl + 1;
  };

  // ارقام لاتین → فارسی (رشته‌های ترکیبی مثل «+2» هم کار می‌کنند)
  O.faNum = function (v) {
    return String(v).replace(/[0-9]/g, function (d) { return FA_D[+d]; });
  };

  // weekday پایتون: 0=دوشنبه … 6=یکشنبه | JS getUTCDay: 0=یکشنبه
  O.pyWeekday = function (d) { return (d.getUTCDay() + 6) % 7; };

  O.faDate = function (dt, withTime) {
    if (withTime === undefined) withTime = true;
    var s = O.WEEKDAY_FA[O.pyWeekday(dt)] + ' ' + O.faNum(dt.getUTCDate()) + ' ' +
      O.MONTH_FA[dt.getUTCMonth() + 1] + ' ' + O.faNum(dt.getUTCFullYear());
    if (!withTime) return s;
    return s + ' — ' + O.faNum(O.hhmm(dt));
  };

  O.hhmm = function (dt) {
    var h = String(dt.getUTCHours()).padStart(2, '0');
    var m = String(dt.getUTCMinutes()).padStart(2, '0');
    return h + ':' + m;
  };

  // نسبت بدون صفر اعشار اضافی: ۲.۰ → «۲»، ۱.۵ → «۱٫۵»
  O.faRatio = function (n) {
    var txt = O.pyFixed(n, 1).replace(/0$/, '').replace(/\.$/, '');
    return O.faNum(txt.replace('.', '٫'));
  };

  // فاصلهٔ قیمت: طلا با دلار، بقیه با پیپ
  O.faPips = function (v, pip, isGold) {
    if (isGold || pip >= 0.5) return O.faNum(O.pyFixed(v, 0)) + ' $';
    return O.faNum(O.pyFixed(v / pip, 0)) + ' پیپ';
  };

  // قیمت با اعشار متناسب با pip — عمداً لاتین (تایپ در متاتریدر)
  O.fmtPrice = function (v, pip) {
    if (!v || !isFinite(v)) return '—';
    var dec = pip > 0 ? Math.max(0, Math.min(6, Math.round(-Math.log10(pip)) + 1)) : 2;
    return O.pyFixed(v, dec);
  };

  O.faCountdown = function (minutes) {
    var m = Math.abs(Math.trunc(minutes));
    if (m < 60) return O.faNum(m) + ' دقیقهٔ دیگر';
    if (m < 24 * 60) {
      var h = Math.floor(m / 60), mm = m % 60;
      if (!mm) return O.faNum(h) + ' ساعت دیگر';
      return O.faNum(h) + ' ساعت و ' + O.faNum(mm) + ' دقیقهٔ دیگر';
    }
    return O.faNum(Math.floor(m / (24 * 60))) + ' روز دیگر';
  };

  // «۱۲ دقیقه دیگر» / «۴۵ دقیقه پیش» — دو طرفه (مثل _countdown در report)
  O.countdown2 = function (minutes) {
    var m = O.pyRound(minutes), tail = 'دیگر';
    if (m < 0) { m = -m; tail = 'پیش'; }
    if (m < 60) return O.faNum(m) + ' دقیقه ' + tail;
    var h = Math.floor(m / 60), rem = m % 60;
    if (rem) return O.faNum(h) + ' ساعت و ' + O.faNum(rem) + ' دقیقه ' + tail;
    return O.faNum(h) + ' ساعت ' + tail;
  };

  // ── وقت تهران (لایهٔ نمایش) ────────────────────────────────────
  // منطق داخلی موتور (داور، ژورنال، سشن، کلیدهای کش) عمداً UTC می‌ماند تا
  // با موتور پایتون نسخهٔ دسکتاپ مو‌به‌مو برابر بماند (تست parity).
  // فقط آنچه کاربر می‌بیند به وقت تهران تبدیل می‌شود.
  // ایران از ۱۴۰۱ (۲۰۲۲) ساعت تابستانی ندارد → اختلاف ثابت +۳:۳۰.
  O.TEH_MIN = 210;
  O.tehran = function (dt) { return new Date(dt.getTime() + O.TEH_MIN * 60000); };
  O.hhmmTeh = function (dt) { return O.hhmm(O.tehran(dt)); };
  O.pyWeekdayTeh = function (dt) { return O.pyWeekday(O.tehran(dt)); };

  O.faDateTeh = function (dt, withTime) {
    var t = O.tehran(dt);
    var s = O.WEEKDAY_FA[O.pyWeekday(t)] + ' ' + O.faNum(t.getUTCDate()) + ' ' +
      O.MONTH_FA[t.getUTCMonth() + 1] + ' ' + O.faNum(t.getUTCFullYear());
    if (withTime === false) return s;
    return s + ' — ' + O.faNum(O.hhmm(t));
  };

  // کلید روز YYYY-MM-DD به وقت تهران (گروه‌بندی نمایشی تقویم)
  O.dayKeyTeh = function (dt) { return O.tehran(dt).toISOString().slice(0, 10); };

  // ── تبدیل تاریخ جلالی (الگوریتم jalaali — بدون وابستگی بیرونی) ──
  var J_MONTH_FA = {
    1: 'فروردین', 2: 'اردیبهشت', 3: 'خرداد', 4: 'تیر', 5: 'مرداد', 6: 'شهریور',
    7: 'مهر', 8: 'آبان', 9: 'آذر', 10: 'دی', 11: 'بهمن', 12: 'اسفند'
  };
  O.J_MONTH_FA = J_MONTH_FA;
  var J_BREAKS = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
    1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178];

  function jdiv(a, b) { return ~~(a / b); }
  function jmod(a, b) { return a - ~~(a / b) * b; }

  function g2d(gy, gm, gd) {
    var d = jdiv((gy + jdiv(gm - 8, 6) + 100100) * 1461, 4) +
      jdiv(153 * jmod(gm + 9, 12) + 2, 5) + gd - 34840408;
    d = d - jdiv(jdiv(gy + 100100 + jdiv(gm - 8, 6), 100) * 3, 4) + 752;
    return d;
  }
  function d2g(jdn) {
    var j = 4 * jdn + 139361631;
    j = j + jdiv(jdiv(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
    var i = jdiv(jmod(j, 1461), 4) * 5 + 308;
    var gd = jdiv(jmod(i, 153), 5) + 1;
    var gm = jmod(jdiv(i, 153), 12) + 1;
    var gy = jdiv(j, 1461) - 100100 + jdiv(8 - gm, 6);
    return { gy: gy, gm: gm, gd: gd };
  }
  function jalCal(jy) {
    var bl = J_BREAKS.length, gy = jy + 621, leapJ = -14, jp = J_BREAKS[0],
      jm = 0, jump = 0, leap, leapG, march, n, i;
    for (i = 1; i < bl; i += 1) {
      jm = J_BREAKS[i];
      jump = jm - jp;
      if (jy < jm) break;
      leapJ = leapJ + jdiv(jump, 33) * 8 + jdiv(jmod(jump, 33), 4);
      jp = jm;
    }
    n = jy - jp;
    leapJ = leapJ + jdiv(n, 33) * 8 + jdiv(jmod(n, 33) + 3, 4);
    if (jmod(jump, 33) === 4 && jump - n === 4) leapJ += 1;
    leapG = jdiv(gy, 4) - jdiv((jdiv(gy, 100) + 1) * 3, 4) - 150;
    march = 20 + leapJ - leapG;
    if (jump - n < 6) n = n - jump + jdiv(jump + 4, 33) * 33;
    leap = jmod(jmod(n + 1, 33) - 1, 4);
    if (leap === -1) leap = 4;
    return { leap: leap, gy: gy, march: march };
  }
  function d2j(jdn) {
    var gy = d2g(jdn).gy, jy = gy - 621, r = jalCal(jy),
      jdn1f = g2d(gy, 3, r.march), jd, jm, k = jdn - jdn1f;
    if (k >= 0) {
      if (k <= 185) { jm = 1 + jdiv(k, 31); jd = jmod(k, 31) + 1; return { jy: jy, jm: jm, jd: jd }; }
      k -= 186;
    } else {
      jy -= 1;
      k += 179;
      if (r.leap === 1) k += 1;
    }
    jm = 7 + jdiv(k, 30);
    jd = jmod(k, 30) + 1;
    return { jy: jy, jm: jm, jd: jd };
  }

  // Date دلخواه → {jy,jm,jd} به وقت تهران
  O.toJalaliTeh = function (dt) {
    var t = O.tehran(dt);
    return d2j(g2d(t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate()));
  };

  // «شنبه ۲۸ شهریور ۱۴۰۴» — به وقت تهران
  O.jalaliFa = function (dt) {
    var j = O.toJalaliTeh(dt);
    return O.WEEKDAY_FA[O.pyWeekdayTeh(dt)] + ' ' + O.faNum(j.jd) + ' ' +
      J_MONTH_FA[j.jm] + ' ' + O.faNum(j.jy);
  };

  O.faPct = function (v) { return v == null ? '—' : O.faNum(O.pyFixed(v * 100, 0)) + '٪'; };
  O.rFmt = function (v) {
    if (v == null) return '—';
    return O.faNum((v >= 0 ? '+' : '-') + O.pyFixed(Math.abs(v), 2));
  };
  O.faFloat = function (v, dec) { return O.faNum(O.pyFixed(v, dec === undefined ? 1 : dec)); };
  O.stars = function (n) { return '⭐'.repeat(Math.max(0, Math.min(5, Math.trunc(n)))); };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
