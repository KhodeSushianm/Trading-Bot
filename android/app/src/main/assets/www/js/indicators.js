/* اندیکاتورهای تکنیکال — پورت دقیق src/analysis/indicators.py
 *
 * همهٔ smoothedها با pandas ewm(adjust=False, ignore_na=False) برابرند:
 *   y[i] = (1-α)·y[i-1] + α·x[i]
 * و در جای NaN، میانگین فعلی بدون تغییر حمل می‌شود (خروجی همان مقدار قبلی)،
 * ولی هر NaNِ رد شده یک ضریب (1-α) اضافه روی وزن دادهٔ قدیمی می‌گذارد:
 *   بعد از g جای خالی: y = (1-α)^(g+1)·y_prev + (1-(1-α)^(g+1))·x
 * (این رفتار در برابر خروجی pandas تست شده است — tests/js/test_indicators)
 */
(function (O) {
  'use strict';

  var NaN_ = NaN;

  function isNum(v) { return v != null && !Number.isNaN(v); }

  // ewm(alpha=…, adjust=False, ignore_na=False) — دقیقاً الگوریتم pandas 3.x:
  //   old_wt در هر گام (مشاهده یا NaN) در (1-α) ضرب می‌شود؛ در مشاهده:
  //     y = (ow·y + α·x)/(ow+α)   سپس ow=1
  //   ویژه‌حالت com==1 (α=0.5): به‌جای α از (1-ow) استفاده می‌شود.
  //   در خانه‌های NaN، میانگین جاری بدون تغییر حمل می‌شود.
  O.ewmAF = function (x, alpha) {
    var out = new Array(x.length);
    var owf = 1 - alpha;
    var special = (alpha === 0.5);          // com == 1
    var weighted = NaN, oldWt = 1, nobs = 0;
    for (var i = 0; i < x.length; i++) {
      var cur = x[i];
      var isObs = cur != null && !Number.isNaN(cur);
      if (isObs) nobs++;
      if (!Number.isNaN(weighted)) {
        oldWt *= owf;                        // ignore_na=False → هر گام ضرب می‌شود
        if (isObs) {
          if (weighted !== cur) {            // پرهیز از خطای عددی در سری ثابت
            var nw = special ? (1 - oldWt) : alpha;
            weighted = (oldWt * weighted + nw * cur) / (oldWt + nw);
          }
          oldWt = 1;
        }
      } else if (isObs) {
        weighted = cur;
      }
      out[i] = nobs >= 1 ? weighted : NaN_;
    }
    return out;
  };

  // میانگین متحرک نمایی: ewm(span=period, adjust=False)
  O.ema = function (close, period) {
    return O.ewmAF(close, 2 / (period + 1));
  };

  // RSI وایلدر: up/down با ewm(alpha=1/period)؛ down==0 → NaN → fillna(50)
  O.rsi = function (close, period) {
    var n = close.length;
    var up = new Array(n), down = new Array(n);
    up[0] = NaN_; down[0] = NaN_;
    for (var i = 1; i < n; i++) {
      var d = close[i] - close[i - 1];
      up[i] = d > 0 ? d : 0;
      down[i] = d < 0 ? -d : 0;
    }
    var ue = O.ewmAF(up, 1 / period);
    var de = O.ewmAF(down, 1 / period);
    var out = new Array(n);
    for (i = 0; i < n; i++) {
      var rs = (de[i] === 0 || !isNum(ue[i]) || !isNum(de[i])) ? NaN_ : ue[i] / de[i];
      out[i] = Number.isNaN(rs) ? 50 : 100 - 100 / (1 + rs);
    }
    return out;
  };

  // دامنهٔ واقعی؛ tr[0] = h0-l0 (مثل pandas max(axis=1, skipna))
  O.trueRange = function (c) {
    var out = new Array(c.length);
    for (var i = 0; i < c.length; i++) {
      if (i === 0) { out[i] = c[i].h - c[i].l; continue; }
      var pc = c[i - 1].c;
      out[i] = Math.max(c[i].h - c[i].l, Math.abs(c[i].h - pc), Math.abs(c[i].l - pc));
    }
    return out;
  };

  O.atr = function (candles, period) {
    return O.ewmAF(O.trueRange(candles), 1 / period);
  };

  // ADX وایلدر — با np.where و replace(0, NaN) دقیقاً مثل پایتون
  O.adx = function (candles, period) {
    var n = candles.length;
    var plusDM = new Array(n), minusDM = new Array(n);
    plusDM[0] = 0; minusDM[0] = 0;                      // diff در خانهٔ اول NaN → where=False → 0
    for (var i = 1; i < n; i++) {
      var up = candles[i].h - candles[i - 1].h;
      var dn = -(candles[i].l - candles[i - 1].l);
      plusDM[i] = (up > dn && up > 0) ? up : 0;
      minusDM[i] = (dn > up && dn > 0) ? dn : 0;
    }
    var a = O.atr(candles, period);
    var pe = O.ewmAF(plusDM, 1 / period);
    var me = O.ewmAF(minusDM, 1 / period);
    var dx = new Array(n);
    for (i = 0; i < n; i++) {
      var pdi = (a[i] === 0 || !isNum(a[i])) ? NaN_ : 100 * pe[i] / a[i];
      var mdi = (a[i] === 0 || !isNum(a[i])) ? NaN_ : 100 * me[i] / a[i];
      var sum = pdi + mdi;
      dx[i] = (!isNum(pdi) || !isNum(mdi) || sum === 0 || Number.isNaN(sum)) ? NaN_
        : 100 * Math.abs(pdi - mdi) / sum;
    }
    var out = O.ewmAF(dx, 1 / period);
    for (i = 0; i < n; i++) if (!isNum(out[i])) out[i] = 0;   // fillna(0)
    return out;
  };

  // قلعه‌ها و کف‌های چرخشی (swing)
  O.swingLevels = function (candles, window) {
    var peakHighs = [], peakLows = [];
    for (var i = window; i < candles.length - window; i++) {
      var hMax = -Infinity, lMin = Infinity, j;
      for (j = i - window; j <= i + window; j++) {
        if (candles[j].h > hMax) hMax = candles[j].h;
        if (candles[j].l < lMin) lMin = candles[j].l;
      }
      if (candles[i].h === hMax) peakHighs.push(candles[i].h);
      if (candles[i].l === lMin) peakLows.push(candles[i].l);
    }
    return { lows: peakLows, highs: peakHighs };
  };

  // نزدیک‌ترین حمایت (زیر قیمت) و مقاومت (بالای قیمت)
  O.nearestLevels = function (price, candles, window) {
    var sw = O.swingLevels(candles, window);
    var support = null, resistance = null;
    sw.lows.forEach(function (x) { if (x < price && (support === null || x > support)) support = x; });
    sw.highs.forEach(function (x) { if (x > price && (resistance === null || x < resistance)) resistance = x; });
    return { support: support, resistance: resistance };
  };

  // آخرین مقدار معتبر یک سری
  O.last = function (arr) { return arr[arr.length - 1]; };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
