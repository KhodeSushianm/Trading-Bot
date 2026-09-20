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

  O.faPct = function (v) { return v == null ? '—' : O.faNum(O.pyFixed(v * 100, 0)) + '٪'; };
  O.rFmt = function (v) {
    if (v == null) return '—';
    return O.faNum((v >= 0 ? '+' : '-') + O.pyFixed(Math.abs(v), 2));
  };
  O.faFloat = function (v, dec) { return O.faNum(O.pyFixed(v, dec === undefined ? 1 : dec)); };
  O.stars = function (n) { return '⭐'.repeat(Math.max(0, Math.min(5, Math.trunc(n)))); };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
