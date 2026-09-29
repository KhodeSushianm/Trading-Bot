/* موتور تحلیل تکنیکال + قدرت ارزها — پورت src/analysis/technical.py و strength.py
 *
 * md = { h4: [candles], h1: [candles], m15: [candles] }  با candle = {t,o,h,l,c}
 */
(function (O) {
  'use strict';

  O.TREND_FA = { bullish: 'صعودی 📈', bearish: 'نزولی 📉', none: 'نامشخص ❔' };
  O.VERDICT_FA = {
    RANGE: '❌ بازار بی‌روند (رنج) — طبق قوانین، فعلاً سیگنالی صادر نمی‌شود',
    BUY_SETUP: '🟢 شرایط «سیگنال خرید» در حال شکل‌گیری است (تصمیم نهایی با داور)',
    SELL_SETUP: '🔴 شرایط «سیگنال فروش» در حال شکل‌گیری است (تصمیم نهایی با داور)',
    WAIT: '⏳ در انتظار — مدارک کافی برای صدور سیگنال جمع نشده',
    DATA: '⚠️ داده کافی برای تحلیل این نماد در دسترس نیست'
  };
  O.RECOMMENDATION_FA = {
    STRONG_BUY: 'خرید قوی 🟢🟢', BUY: 'خرید 🟢', NEUTRAL: 'خنثی ⚪',
    SELL: 'فروش 🔴', STRONG_SELL: 'فروش قوی 🔴🔴'
  };

  O.analyzeSymbol = function (symCfg, md, acfg) {
    var emaFastN = acfg.ema_fast | 0;
    var emaSlowN = acfg.ema_slow | 0;
    var adxN = acfg.adx_period | 0;
    var adxMin = +acfg.adx_min_trend;
    var rsiN = acfg.rsi_period | 0;
    var atrN = acfg.atr_period | 0;
    var swingWin = acfg.swing_window | 0;

    var h4 = md.h4, h1 = md.h1, m15 = md.m15;
    var common = {
      symbol: symCfg.name,
      fa_name: symCfg.fa || symCfg.name,
      base: symCfg.base, quote: symCfg.quote,
      pip: +symCfg.pip
    };

    function lastTs(df) { return df && df.length ? new Date(df[df.length - 1].t) : null; }

    // ── v0.29: دو قیمت، دو نقش — آینهٔ src/analysis/technical.py ──
    //   price      = بستهٔ H1 — لنگرِ *تحلیل* (nearestLevels، ev_level)
    //   exec_price = بستهٔ M15 — قیمتِ *اجرا* (entry/sl/tp/sid/ژورنال)
    // باید همیشه با پایتون هم‌عدد بماند (پاریتی).
    var EXEC_TF_MIN = 15;
    var H1_TF_MIN = 60;

    // زمانِ **بسته‌شدنِ** آخرین کندل = نمایهٔ آن + طولِ بازه (ms).
    // یاهو کندلِ درون‌روزی را با نمایهٔ «باز‌شدن» می‌دهد، پس بستهٔ کندلِ
    // نمایهٔ T برابرِ قیمتِ لحظهٔ T+interval است. null = داده نبود.
    function closeTs(df, intervalMin) {
      if (!df || !df.length) return null;
      return df[df.length - 1].t + intervalMin * 60000;
    }

    // قیمتِ اجرا؛ null یعنی «نداریم» → مصرف‌کننده به price برمی‌گردد.
    function execPrice(m15) {
      return (m15 && m15.length) ? m15[m15.length - 1].c : null;
    }

    // باید هم‌منبعِ execPrice باشد، وگرنه همان باگِ «قیمت از یک لحظه،
    // اسکن از لحظهٔ دیگر» برمی‌گردد.
    function execTs(m15, h1) {
      if (m15 && m15.length) return closeTs(m15, EXEC_TF_MIN);
      return closeTs(h1, H1_TF_MIN);
    }

    // بررسی کفایت داده (دقیقاً مثل دسکتاپ)
    if (h4.length < emaSlowN + 10 || h1.length < emaSlowN + 10 || m15.length < rsiN + 10) {
      return Object.assign(common, {
        price: h1.length ? h1[h1.length - 1].c : 0,
        trend: 'none', h1_agrees: false, adx: 0, rsi: 50, rsi_rising: false,
        atr: 0, support: null, resistance: null,
        last_candle: lastTs(m15), verdict: 'DATA',
        exec_price: execPrice(m15), exec_ts: execTs(m15, h1)
      });
    }

    var price = h1[h1.length - 1].c;

    var closes = function (df) { return df.map(function (x) { return x.c; }); };
    var eFastH4 = O.last(O.ema(closes(h4), emaFastN));
    var eSlowH4 = O.last(O.ema(closes(h4), emaSlowN));
    var trend = eFastH4 > eSlowH4 ? 'bullish' : 'bearish';

    var eFastH1 = O.last(O.ema(closes(h1), emaFastN));
    var eSlowH1 = O.last(O.ema(closes(h1), emaSlowN));
    var h1Bullish = eFastH1 > eSlowH1;
    var h1Agrees = trend === 'bullish' ? h1Bullish : !h1Bullish;

    var adxV = O.last(O.adx(h4, adxN));
    var rsiS = O.rsi(closes(m15), rsiN);
    var rsiV = rsiS[rsiS.length - 1];
    var rsiRising = rsiS[rsiS.length - 1] > rsiS[rsiS.length - 2];
    var atrV = O.last(O.atr(h1, atrN));
    var lv = O.nearestLevels(price, h4, swingWin);

    var verdict;
    if (adxV < adxMin) verdict = 'RANGE';
    else if (trend === 'bullish' && h1Agrees && rsiV < 45) verdict = 'BUY_SETUP';
    else if (trend === 'bearish' && h1Agrees && rsiV > 55) verdict = 'SELL_SETUP';
    else verdict = 'WAIT';

    return Object.assign(common, {
      price: price, trend: trend, h1_agrees: h1Agrees,
      adx: adxV, rsi: rsiV, rsi_rising: rsiRising, atr: atrV,
      support: lv.support, resistance: lv.resistance,
      last_candle: lastTs(m15), verdict: verdict,
      exec_price: execPrice(m15), exec_ts: execTs(m15, h1)
    });
  };

  // ── سنجهٔ قدرت ارزها (پورت strength.py) ──────────────────────
  function splitSymbol(name) {
    var clean = name.replace('=X', '').toUpperCase();
    if (clean.length === 6) return [clean.slice(0, 3), clean.slice(3)];
    return [null, null];
  }

  O.currencyStrength = function (datasets, lookbackH1) {
    var changes = {};
    Object.keys(datasets).forEach(function (name) {
      var h1 = datasets[name].h1;
      var close = h1.map(function (x) { return x.c; });
      if (close.length <= lookbackH1) return;
      var pct = (close[close.length - 1] / close[close.length - 1 - lookbackH1] - 1) * 100;
      var sq = splitSymbol(name);
      if (sq[0] === null) return;
      (changes[sq[0]] = changes[sq[0]] || []).push(pct);
      (changes[sq[1]] = changes[sq[1]] || []).push(-pct);
    });
    var avg = Object.keys(changes).map(function (c) {
      var v = changes[c];
      return [c, v.reduce(function (a, b) { return a + b; }, 0) / v.length];
    });
    avg.sort(function (x, y) { return y[1] - x[1]; });
    return avg;
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
