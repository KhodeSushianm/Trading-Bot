/* 🎯 استراتژی‌های ورود (v0.26 — S2) — آینهٔ ES5 بایت‌به‌بایتِ src/strategies/
 *
 * سه استراتژیِ مستقل که جهتِ ورود را «پیشنهاد» می‌دهند (قرارداد
 * odin.strategy@1). در S2 هنوز مصرف‌کننده‌ای ندارند — داور در S3 به آن‌ها
 * وصل می‌شود (دروازهٔ توافق min_agree). میخِ برابری:
 * tests/js/test_strategies_switch.js (طلایی از اوراکل پایتون —
 * tests/js/gen_strategies_golden.py) + پاریتی زنده در run_parity.js.
 *
 * قوانین سخت (همان قواعد src/strategies/base.py):
 *   • خالص و قطعی: بدون I/O، بدون ساعت جهانی (زمان از ctx — تنها نقطهٔ
 *     مجازِ خواندن ساعت ctxNow است)، بدون حالت داخلی.
 *   • صادقانه: نبود داده → direction="NONE" با دلیل فارسی صریح؛ هرگز حدس نه.
 *   • shape خروجی == StrategyVerdict.to_dict پایتون:
 *       key, name_fa, direction (BUY|SELL|NONE), strength (0..1),
 *       proposes (bool), reasons_fa (list), detail_fa
 *     proposes=false یعنی فقط «توافق» (carry) — هرگز منبعِ جهت نیست.
 *   • متن‌های فارسی بایت‌به‌بایت از سورس پایتون کپی شده‌اند (ZWNJ شامل) —
 *     هر تغییر در یکی باید در دیگری هم بازتاب شود (طلایی دو زبان پین است).
 *
 * دام‌های دو-زبانه که اینجا خنثی شده‌اند (درس‌های §9 بستهٔ زمینه):
 *   • min/max پایتون NaN را منتشر نمی‌کند (مقایسه‌محور است) — pyMin/pyMax
 *   • truthiness پایتون: NaN truthy است ولی در JS falsy — pyTruth/orDef
 *     (کپی محلیِ O.core.pyBool — پینِ «مصرف‌کننده‌های مجاز O.core» در
 *     smoke_core اجازهٔ مصرف مستقیم به ماژول‌های فیچر نمی‌دهد؛ برابریِ
 *     این کپی با core.pyBool در test_strategies_switch پین شده)
 *   • f'{v:.0f}'/'.2f'/'+.2f' پایتون گردِ «نصف-به-زوج» است → O.pyFixed؛
 *     ':g'/':.5g' پایتون (ارقام معنادار + نماد ۲-رقمی + nan/inf کوچک)
 *     → pyG محلی (O.fmtG تنها برای .5gِ بدون لبه کافی بود)
 *
 * سبک: ES5 خالص (var/function) — نگهبانش test_strategies_switch.js.
 */
(function (O) {
  'use strict';

  // ── هلپرهای هم‌ارزی با پایتون (محلی — بدون مصرف O.core) ─────────────

  function hasOwn(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }

  // bool() پایتون — کپیِ core.pyBool (NaN truthy است، -0 falsy)
  function pyTruth(v) {
    if (v === null || v === undefined) return false;
    if (typeof v === 'boolean') return v;
    if (typeof v === 'number') return v !== 0;
    if (typeof v === 'string') return v.length > 0;
    if (Object.prototype.toString.call(v) === '[object Array]') return v.length > 0;
    if (typeof v === 'object') {
      for (var k in v) { if (hasOwn(v, k)) return true; }
      return false;
    }
    return true;   // تابع و بقیهٔ انواع — مثل پایتون truthy
  }

  // `v or d` پایتون (نه `||` جاوااسکریپت — NaN را نگه می‌دارد)
  function orDef(v, d) { return pyTruth(v) ? v : d; }

  // min/max پایتون: مقایسه‌محور — اگر مقایسه False شود (مثل NaN) آرگومان
  // اول برمی‌گردد؛ Math.min/max جاوااسکریپت NaN را منتشر می‌کند.
  function pyMin(a, b) { return b < a ? b : a; }
  function pyMax(a, b) { return b > a ? b : a; }
  function maxList(xs) { var m = xs[0]; for (var i = 1; i < xs.length; i++) { if (xs[i] > m) m = xs[i]; } return m; }
  function minList(xs) { var m = xs[0]; for (var i = 1; i < xs.length; i++) { if (xs[i] < m) m = xs[i]; } return m; }

  // getattr(o, name, default) پایتون
  function getAttr(o, name, d) {
    return (o !== null && o !== undefined && o[name] !== undefined) ? o[name] : d;
  }

  // dict(x or {}) / list(...) پایتون — کپی سطحی، هرگز کرش نه
  function copyDict(v) {
    var out = {};
    if (!pyTruth(v) || typeof v !== 'object') return out;
    for (var k in v) { if (hasOwn(v, k)) out[k] = v[k]; }
    return out;
  }
  function copyList(v, d) {
    if (Object.prototype.toString.call(v) === '[object Array]') return v.slice();
    return d.slice();
  }

  // int()/float() پایتون روی مقدار config (مقادیر سالم با check_config
  // تضمین‌اند؛ JS طبق Failure Isolation هرگز کرش نمی‌کند). نکتهٔ وفاقی:
  // float(nan) پایتون = nan (کرش نمی‌کند) → عددِ NaN عیناً رد می‌شود تا
  // pyMin/pyMax همان min/max مقایسه‌محورِ پایتون را بازتولید کنند
  // (پین: سناریوی carry_mindiff_nan در طلایی). فقط null/undefined/رشتهٔ
  // بی‌عدد → پیش‌فرض (float(None)/float('abc') پایتون کرش می‌کرد — اینجا
  // صادقانه و بی‌صدا به پیش‌فرض برمی‌گردیم).
  function cfgInt(v, d) {
    if (v === null || v === undefined) return d;
    if (typeof v === 'number') { var t = v < 0 ? Math.ceil(v) : Math.floor(v); return t === t ? t : d; }
    var n = parseInt(v, 10);
    return isNaN(n) ? d : n;
  }
  function cfgFloat(v, d) {
    if (v === null || v === undefined) return d;
    if (typeof v === 'number') return v;
    var n = Number(v);
    return isNaN(n) ? d : n;
  }

  // f'{v:.Nf}' پایتون — گردِ نصف-به-زوج + nan/inf کوچک (O.pyFixed بی‌نهایت
  // را 'Infinity' می‌دهد؛ پایتون 'inf'/'nan' می‌دهد)
  function fmtF(v, dec) {
    if (typeof v !== 'number' || v !== v) return 'nan';
    if (v === Infinity) return 'inf';
    if (v === -Infinity) return '-inf';
    return O.pyFixed(v, dec);
  }
  // f'{v:+.2f}' پایتون — علامت همیشگی (نیم‌فاصله: -0.0 → '-0.00')
  function fmtSign2(v) {
    if (typeof v !== 'number' || v !== v) return 'nan';
    if (v === Infinity) return '+inf';
    if (v === -Infinity) return '-inf';
    var sign = (v < 0 || Object.is(v, -0)) ? '-' : '+';
    return sign + fmtF(Math.abs(v), 2);
  }
  // f'{v:.<sig>g}' پایتون — ارقام معنادار، صفرهای اضافی حذف، نمای نمایی
  // با توانِ دست‌کم ۲ رقم (e+05) و آستانهٔ exp < -4 || exp >= sig
  function pyG(v, sig) {
    if (typeof v !== 'number' || v !== v) return 'nan';
    if (v === Infinity) return 'inf';
    if (v === -Infinity) return '-inf';
    var neg = v < 0 || Object.is(v, -0);
    var m = Math.abs(v);
    if (m === 0) return neg ? '-0' : '0';
    var es = m.toExponential();
    var e = parseInt(es.split('e')[1], 10);
    var out;
    if (e < -4 || e >= sig) {
      var mant = fmtF(m / Math.pow(10, e), sig - 1);
      if (mant.indexOf('.') >= 0) mant = mant.replace(/0+$/, '').replace(/\.$/, '');
      var ex = String(Math.abs(e));
      if (ex.length < 2) ex = '0' + ex;
      out = mant + 'e' + (e < 0 ? '-' : '+') + ex;
    } else {
      out = fmtF(m, sig - 1 - e);
      if (out.indexOf('.') >= 0) out = out.replace(/0+$/, '').replace(/\.$/, '');
    }
    return (neg ? '-' : '') + out;
  }
  function fa(s) { return O.faNum(s); }
  function pad2(n) { return (n < 10 ? '0' : '') + n; }

  // زمانِ چرخه — تنها نقطهٔ مجازِ خواندن ساعت (آینهٔ ctx_now پایتون).
  // پایتون ctx.now (datetime) می‌خواند؛ موتور JS زمان را با ctx.nowMs
  // (میلی‌ثانیه) می‌دهد — هر دو پذیرفته‌اند؛ نبود/خرابی → ساعت جهانی UTC.
  function ctxNow(ctx) {
    if (ctx !== null && ctx !== undefined) {
      var n = ctx.now;
      if (n instanceof Date && !isNaN(n.getTime())) return n;
      var ms = ctx.nowMs;
      if (typeof ms === 'number' && isFinite(ms)) return new Date(ms);
    }
    return new Date();
  }
  // utc_of پایتون برای مهرِ زمانیِ کندل (ms) — خرابی → null (ردِ صادقانه)
  function dateOfMs(ms) {
    if (typeof ms !== 'number' || !isFinite(ms)) return null;
    var d = new Date(ms);
    return isNaN(d.getTime()) ? null : d;
  }

  // ── سازنده‌های verdict (shape == StrategyVerdict.to_dict) ───────────

  function verdict(key, nameFa, direction, strength, proposes, reasonsFa, detailFa) {
    return {
      key: key, name_fa: nameFa, direction: direction, strength: strength,
      proposes: !!proposes, reasons_fa: reasonsFa, detail_fa: detailFa
    };
  }
  function noneV(key, nameFa, reasonFa, proposes) {
    if (proposes === undefined) proposes = true;
    return verdict(key, nameFa, 'NONE', 0.0, proposes, [reasonFa],
      nameFa + ': ' + reasonFa);
  }

  // ══════════════════════════════════════════════════════════════
  //  استراتژی ۱ — روند + پولبک (آینهٔ src/strategies/trend_pullback.py)
  // ══════════════════════════════════════════════════════════════
  var KEY_TP = 'trend_pullback';
  var NAME_TP = 'روند + پولبک';

  function lastCandleConfirms(md, bullish) {
    var side = bullish ? 'صعودی' : 'نزولی';
    var h1 = (md !== null && md !== undefined && md.h1 !== undefined) ? md.h1 : null;
    if (h1 === null || h1.length === 0) {
      return [false, 'تأیید ادامهٔ حرکت ممکن نیست — کندل ۱ ساعته در دسترس نیست'];
    }
    var o, c;
    try {
      var last = h1[h1.length - 1];
      o = Number(last.o);
      c = Number(last.c);
    } catch (e) {
      return [false, 'تأیید ادامهٔ حرکت ممکن نیست — کندل ۱ ساعته خوانا نیست'];
    }
    if (bullish && c > o) return [true, ''];
    if (!bullish && c < o) return [true, ''];
    return [false, 'تأیید ادامهٔ حرکت نیست — کندل آخر ۱ ساعته در جهت روند '
      + 'بسته نشده (باید ' + side + ' باشد)'];
  }

  function evalTrendPullback(a, md, scfg, ctx) {
    scfg = copyDict(scfg);
    var adxMin = cfgFloat(scfg.adx_min, 20);
    var rsiBuy = copyList(scfg.rsi_buy, [30, 45]);
    var rsiSell = copyList(scfg.rsi_sell, [55, 70]);

    // ۱) روند اصلی + جهت غالب
    var trend = getAttr(a, 'trend', 'none');
    if (trend !== 'bullish' && trend !== 'bearish') {
      return noneV(KEY_TP, NAME_TP, 'روند اصلی بازار نامشخص است (نه صعودی، نه نزولی)');
    }
    if (!pyTruth(getAttr(a, 'h1_agrees', false))) {
      return noneV(KEY_TP, NAME_TP, 'جهت غالب تأیید نشده — H1 با H4 هم‌جهت نیست');
    }
    // ۲) اعتبار روند
    var adx = Number(orDef(getAttr(a, 'adx', 0.0), 0.0));
    if (adx < adxMin) {
      return noneV(KEY_TP, NAME_TP,
        'روند معتبر نیست (ADX=' + fa(fmtF(adx, 0)) + ' زیر '
        + fa(fmtF(adxMin, 0)) + ')');
    }

    var bullish = trend === 'bullish';
    var rsi = Number(orDef(getAttr(a, 'rsi', 50.0), 50.0));
    var zone = bullish ? rsiBuy : rsiSell;
    var lo = Number(zone[0]), hi = Number(zone[1]);

    // ۳) شناسایی Pullback
    if (!(lo <= rsi && rsi <= hi)) {
      var side = bullish ? 'خرید' : 'فروش';
      return noneV(KEY_TP, NAME_TP,
        'پولبک معتبر نیست — RSI=' + fa(fmtF(rsi, 0)) + ' بیرونِ '
        + 'منطقهٔ ' + fa(fmtF(lo, 0)) + '–' + fa(fmtF(hi, 0)) + ' '
        + 'برای ستاپ ' + side + ' است');
    }

    // ۴) تأیید ادامهٔ حرکت — برگشت RSI
    if (bullish && !pyTruth(getAttr(a, 'rsi_rising', false))) {
      return noneV(KEY_TP, NAME_TP,
        'تأیید ادامهٔ حرکت نیست — RSI در پولبک صعودی هنوز بالا '
        + 'نمی‌رود');
    }
    if (!bullish && pyTruth(getAttr(a, 'rsi_rising', false))) {
      return noneV(KEY_TP, NAME_TP,
        'تأیید ادامهٔ حرکت نیست — RSI در اصلاحِ روند نزولی هنوز '
        + 'پایین نمی‌آید');
    }

    // ۴) تأیید ادامهٔ حرکت — کندل آخر H1 در جهت روند
    var cc = lastCandleConfirms(md, bullish);
    if (!cc[0]) return noneV(KEY_TP, NAME_TP, cc[1]);

    // ۵) ستاپ معتبر است
    var direction = bullish ? 'BUY' : 'SELL';
    var trendFa = bullish ? 'صعودی' : 'نزولی';
    var strength = 0.6 + 0.4 * pyMin(1.0, pyMax(0.0, (adx - adxMin) / 20.0));
    var reasons = [
      'روند ' + trendFa + ' با جهت غالب تأییدشده (H4+H1 هم‌جهت، '
      + 'ADX=' + fa(fmtF(adx, 0)) + ')',
      'پولبک شناسایی شد — RSI=' + fa(fmtF(rsi, 0)) + ' در منطقهٔ '
      + fa(fmtF(lo, 0)) + '–' + fa(fmtF(hi, 0)),
      'تأیید ادامهٔ حرکت — RSI در حال برگشت و کندل آخر ۱ ساعته در جهت '
      + 'روند بسته شده'
    ];
    return verdict(KEY_TP, NAME_TP, direction, strength, true, reasons,
      NAME_TP + ': پیشنهاد ' + direction + ' — روند ' + trendFa + ' + پولبک '
      + '+ تأیید ادامه');
  }

  // ══════════════════════════════════════════════════════════════
  //  استراتژی ۲ — شکست لندن (آینهٔ src/strategies/london_breakout.py)
  // ══════════════════════════════════════════════════════════════
  var KEY_LB = 'london_breakout';
  var NAME_LB = 'شکست لندن';

  function evalLondonBreakout(a, md, scfg, ctx) {
    scfg = copyDict(scfg);
    var asiaStart = cfgInt(scfg.asia_start_hour, 0);
    var asiaEnd = cfgInt(scfg.asia_end_hour, 7);
    var openH = cfgInt(scfg.london_open_hour, 7);
    var windowH = cfgInt(scfg.trade_window_hours, 4);
    var minBars = cfgInt(scfg.asia_min_bars, 5);
    var minWAtr = cfgFloat(scfg.min_range_atr, 0.5);
    var maxWAtr = cfgFloat(scfg.max_range_atr, 3.0);
    var marginAtr = cfgFloat(scfg.breakout_margin_atr, 0.15);

    var now = ctxNow(ctx);
    var nowHour = now.getUTCHours();

    // ۳) پنجرهٔ لندن — اول زمان، چون ارزان‌ترین رد است
    if (O.pyWeekday(now) >= 5) {
      return noneV(KEY_LB, NAME_LB, 'روزهای پایانی هفته — سشن لندن بسته است');
    }
    if (!(openH <= nowHour && nowHour < openH + windowH)) {
      return noneV(KEY_LB, NAME_LB,
        'بیرونِ پنجرهٔ شکستِ لندن '
        + '(' + fa(String(openH)) + ':۰۰ تا '
        + fa(String(openH + windowH)) + ':۰۰ UTC — الان ساعت '
        + fa(pad2(nowHour)) + ':' + fa(pad2(now.getUTCMinutes())) + ')');
    }

    // ۱) تشکیل Range از کندل‌های آسیایِ همان روز
    var h1 = (md !== null && md !== undefined && md.h1 !== undefined) ? md.h1 : null;
    if (h1 === null || h1.length === 0) {
      return noneV(KEY_LB, NAME_LB, 'کندل ۱ ساعته در دسترس نیست — Range ساخته نمی‌شود');
    }
    var highs = [], lows = [];
    var nowY = now.getUTCFullYear(), nowM = now.getUTCMonth(), nowD = now.getUTCDate();
    for (var i = 0; i < h1.length; i++) {
      var k = h1[i];
      var t = dateOfMs(k === null || k === undefined ? null : k.t);
      if (t === null) continue;
      if (t.getUTCFullYear() !== nowY || t.getUTCMonth() !== nowM
        || t.getUTCDate() !== nowD) continue;
      var hh = t.getUTCHours();
      if (asiaStart <= hh && hh < asiaEnd) {
        highs.push(Number(k.h));
        lows.push(Number(k.l));
      }
    }
    if (highs.length < minBars) {
      return noneV(KEY_LB, NAME_LB,
        'محدودهٔ آسیا کامل تشکیل نشده — فقط '
        + fa(String(highs.length)) + ' کندل در بازهٔ '
        + fa(String(asiaStart)) + '–' + fa(String(asiaEnd)) + ' UTC '
        + '(حداقل ' + fa(String(minBars)) + ' لازم است)');
    }
    var rngHi = maxList(highs), rngLo = minList(lows);
    var width = rngHi - rngLo;

    // ۲) اعتبار محدوده نسبت به ATR
    var atr = Number(orDef(getAttr(a, 'atr', 0.0), 0.0));
    if (atr <= 0) {
      return noneV(KEY_LB, NAME_LB,
        'ATR در دسترس نیست — اعتبار محدوده و شکست سنجیده نمی‌شود');
    }
    if (width < minWAtr * atr) {
      return noneV(KEY_LB, NAME_LB,
        'محدوده خیلی تنگ است (' + pyG(width, 5) + ' کمتر از '
        + fa(pyG(minWAtr, 6)) + '×ATR) — شکستش نویز است');
    }
    if (width > maxWAtr * atr) {
      return noneV(KEY_LB, NAME_LB,
        'محدوده خیلی پهن است (' + pyG(width, 5) + ' بیشتر از '
        + fa(pyG(maxWAtr, 6)) + '×ATR) — حرکتِ اصلی احتمالا رفته');
    }

    // ۴) شکست معتبر با حاشیهٔ نفوذ
    var price = Number(orDef(getAttr(a, 'price', 0.0), 0.0));
    var margin = marginAtr * atr;
    var direction, pen;
    if (price >= rngHi + margin) {
      direction = 'BUY'; pen = price - (rngHi + margin);
    } else if (price <= rngLo - margin) {
      direction = 'SELL'; pen = (rngLo - margin) - price;
    } else {
      return noneV(KEY_LB, NAME_LB,
        'شکست معتبری رخ نداده — قیمت ' + pyG(price, 5) + ' داخل محدودهٔ '
        + pyG(rngLo, 5) + '–' + pyG(rngHi, 5) + ' است (حاشیهٔ نفوذ '
        + fa(pyG(marginAtr, 6)) + '×ATR)');
    }

    var strength = 0.6 + 0.4 * pyMin(1.0, pen / (0.5 * atr));
    var sideFa = direction === 'BUY' ? 'بالای سقف' : 'زیر کف';
    var reasons = [
      'محدودهٔ آسیا (' + fa(String(asiaStart)) + '–' + fa(String(asiaEnd)) + ' UTC): '
      + pyG(rngLo, 5) + ' – ' + pyG(rngHi, 5) + ' از ' + fa(String(highs.length)) + ' کندل',
      'شکست معتبر — قیمت ' + pyG(price, 5) + ' ' + sideFa + ' محدوده با عبور از حاشیهٔ '
      + pyG(marginAtr, 6) + '×ATR بسته شده',
      'در پنجرهٔ لندن — ساعت ' + fa(pad2(nowHour)) + ':' + fa(pad2(now.getUTCMinutes())) + ' UTC'
    ];
    return verdict(KEY_LB, NAME_LB, direction, strength, true, reasons,
      NAME_LB + ': پیشنهاد ' + direction + ' — شکستِ '
      + (direction === 'BUY' ? 'سقف' : 'کف') + ' محدودهٔ آسیا در '
      + 'سشن لندن');
  }

  // ══════════════════════════════════════════════════════════════
  //  استراتژی ۳ — کری (آینهٔ src/strategies/carry.py)
  // ══════════════════════════════════════════════════════════════
  var KEY_CARRY = 'carry';
  var NAME_CARRY = 'کری (نرخ بهره)';
  var BIASES = ['hawkish', 'neutral', 'dovish'];

  function evalCarry(a, md, scfg, ctx) {
    scfg = copyDict(scfg);
    var ratesCfg = copyDict(orDef(scfg.rates, null));
    var values = copyDict(orDef(ratesCfg.values, null));
    var bias = copyDict(orDef(ratesCfg.bias, null));
    var asOfRaw = ratesCfg.as_of;
    var asOf = (asOfRaw === undefined) ? 'نامعلوم' : String(asOfRaw === null ? 'None' : asOfRaw);
    var minDiff = cfgFloat(scfg.min_diff, 1.5);
    var newsMin = cfgInt(scfg.news_min_score, 4);

    var base = String(orDef(getAttr(a, 'base', ''), ''));
    var quote = String(orDef(getAttr(a, 'quote', ''), ''));

    // ۱) اختلاف نرخ بهره
    var rb = hasOwn(values, base) ? values[base] : null;
    var rq = hasOwn(values, quote) ? values[quote] : null;
    if (rb === null || rb === undefined || rq === null || rq === undefined) {
      var missing = (rb === null || rb === undefined) ? base : quote;
      return noneV(KEY_CARRY, NAME_CARRY,
        'نرخِ سیاستیِ ' + missing + ' در جدول نیست (as_of ' + asOf + ') — '
        + 'بدون داده، نظر صادقانه‌ای نداریم', false);
    }
    var diff = Number(rb) - Number(rq);
    if (Math.abs(diff) < minDiff) {
      return noneV(KEY_CARRY, NAME_CARRY,
        'اختلاف نرخ ' + base + '/' + quote + ' '
        + '(' + fa(fmtSign2(diff)) + '٪) زیر آستانهٔ '
        + fa(pyG(minDiff, 6)) + '٪ است — صرفِ carry ناچیز', false);
    }
    var direction = diff > 0 ? 'BUY' : 'SELL';

    // ۲) وضعیت Monetary Policy (برچسب دستی — پیش‌فرض neutral = بی‌اثر)
    function biasOf(cur) {
      var v = hasOwn(bias, cur) ? bias[cur] : 'neutral';
      if (v === undefined) v = 'neutral';
      var s = String(v === null ? 'None' : v).toLowerCase();
      return BIASES.indexOf(s) >= 0 ? s : 'neutral';
    }
    var bb = biasOf(base), qb = biasOf(quote);
    var against = direction === 'BUY' ? ['dovish', 'hawkish'] : ['hawkish', 'dovish'];
    if (bb === against[0] || qb === against[1]) {
      var who;
      if (direction === 'BUY') {
        who = (bb === against[0]) ? base + ' dovish' : quote + ' hawkish';
      } else {
        who = (bb === against[0]) ? base + ' hawkish' : quote + ' dovish';
      }
      return noneV(KEY_CARRY, NAME_CARRY,
        'وضعیت سیاست پولی خلاف جهت carry است (' + who + ') — صبر تا '
        + 'روشن‌شدن مسیر سیاست', false);
    }

    // ۳) جهت کلی Macro — جریان قدرت ارزها (اگر موجود باشد)
    var ranking = (ctx !== null && ctx !== undefined) ? orDef(ctx.ranking, []) : [];
    if (pyTruth(ranking)) {
      var order = {};
      for (var i = 0; i < ranking.length; i++) {
        try { order[String(ranking[i][0])] = i; } catch (e) { continue; }
      }
      var ib = hasOwn(order, base) ? order[base] : null;
      var iq = hasOwn(order, quote) ? order[quote] : null;
      if (ib !== null && iq !== null) {
        var misaligned = direction === 'BUY' ? (ib > iq) : (ib < iq);
        if (misaligned) {
          return noneV(KEY_CARRY, NAME_CARRY,
            'جریانِ قدرت خلاف جهت carry است — در رتبه‌بندی، '
            + base + ' ضعیف‌تر از ' + quote + ' است؛ صرفِ نرخ به‌تنهایی '
            + 'کافی نیست', false);
        }
      }
    }

    // ۴) هم‌جهتی فاندامنتال — رأی اخبار (اگر snapshot موجود باشد)
    var snap = (ctx !== null && ctx !== undefined && ctx.newsSnap !== undefined)
      ? ctx.newsSnap : null;
    if (snap !== null && snap !== undefined && pyTruth(getAttr(snap, 'items', null))) {
      try {
        var vote = O.newsSupports(snap, base, quote,
          direction === 'BUY' ? 'buy' : 'sell', newsMin);
        var vv = Number(getAttr(vote, 'verdict', 0) || 0);
        if (vv < 0) {
          return noneV(KEY_CARRY, NAME_CARRY,
            'اخبارِ فاندامنتال از جهتِ carry پشتیبانی نمی‌کنند '
            + '(رأی خلاف) — هم‌جهتی شرط است', false);
        }
      } catch (e) {
        // موتور خبر خطا داد → مثلِ «داده نیست» رفتار کن (رد نمی‌کند)
      }
    }

    var strength = pyMin(1.0, Math.abs(diff) / (2.0 * minDiff));
    var reasons = [
      'اختلاف نرخ: ' + base + '=' + fa(fmtF(Number(rb), 2)) + '٪ در برابر '
      + quote + '=' + fa(fmtF(Number(rq), 2)) + '٪ → '
      + fa(fmtSign2(diff)) + '٪ به نفع '
      + (direction === 'BUY' ? 'خرید' : 'فروش') + ' جفت',
      'وضعیت سیاست پولی، جریانِ قدرت و اخبار با جهت carry هم‌جهت‌اند '
      + '(یا داده‌شان نبود — صادقانه رد نشدند)',
      'نرخ‌ها از جدولِ config (as_of ' + asOf + ') — به‌روزرسانی دستی لازم دارد'
    ];
    return verdict(KEY_CARRY, NAME_CARRY, direction, strength, false, reasons,
      NAME_CARRY + ': سوگیری ' + direction + ' — صرفِ نرخ '
      + fa(fmtSign2(diff)) + '٪ (' + base + ' در برابر ' + quote + ')');
  }

  // ── صادرات — کلیدها snake_case همان کلیدهای config/registry پایتون ──
  O.strategies = {
    trendPullback: { key: KEY_TP, nameFa: NAME_TP, evaluate: evalTrendPullback },
    londonBreakout: { key: KEY_LB, nameFa: NAME_LB, evaluate: evalLondonBreakout },
    carry: { key: KEY_CARRY, nameFa: NAME_CARRY, evaluate: evalCarry }
  };

  // ترتیب = priority ارزیابی (آینهٔ STRATEGY_RULES در src/plugins/strategies.py)
  O.STRATEGY_KEYS = ['trend_pullback', 'london_breakout', 'carry'];

  var BY_KEY = {
    trend_pullback: O.strategies.trendPullback,
    london_breakout: O.strategies.londonBreakout,
    carry: O.strategies.carry
  };
  O.strategyFor = function (key) {
    var m = BY_KEY[key];
    if (!m) throw new Error('استراتژیِ ناشناخته: ' + key);
    return m;
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
