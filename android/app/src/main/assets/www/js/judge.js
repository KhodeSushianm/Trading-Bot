/* ⚖️ داور امتیازدهی (Confluence Judge) — پورت دقیق src/judge/scoring.py
 *
 * دو لایه: ۱) دروازه‌های وتو (بدون استثنا) ۲) جدول امتیاز (حداکثر ۱۱،
 * آستانهٔ پیش‌فرض ۷). دادهٔ unavailable صادقانه ۰ امتیاز با ❔ می‌گیرد.
 */
(function (O) {
  'use strict';

  O.DIR_FA = { BUY: 'خرید 🟢', SELL: 'فروش 🔴' };
  O.DIR_EMOJI = { BUY: '🟢', SELL: '🔴' };
  O.TV_DIR = { STRONG_BUY: 2, BUY: 1, NEUTRAL: 0, SELL: -1, STRONG_SELL: -2 };

  O.dirFaShort = function (d) { return d === 'BUY' ? 'خرید' : 'فروش'; };

  // %g پایتون با ۵ رقم معنادار (بدون صفرهای اضافی)
  O.fmtG = function (v, sig) {
    sig = sig || 5;
    var s = Number(v).toPrecision(sig);
    if (s.indexOf('.') >= 0 && s.indexOf('e') < 0) s = s.replace(/0+$/, '').replace(/\.$/, '');
    return s;
  };
  O.fmtGSign = function (v) {
    var s = O.fmtG(Math.abs(v));
    return (v >= 0 ? '+' : '-') + s;
  };

  function evIcon(e) {
    if (e.points > 0) return '✅';
    if (e.unavailable) return '❔';
    return '➖';
  }
  function Evidence(key, labelFa, points, maxPoints, detailFa, ok, unavailable) {
    return {
      key: key, label_fa: labelFa, points: points, max_points: maxPoints,
      detail_fa: detailFa, ok: !!ok, unavailable: !!unavailable, icon: evIcon({ points: points, unavailable: unavailable })
    };
  }
  function Veto(key, titleFa, detailFa) { return { key: key, title_fa: titleFa, detail_fa: detailFa }; }

  // ── جهش نوسان: ATR فعلی / میانگین ATR ───────────────────────
  O.volatilityRatio = function (md, acfg, lookback) {
    try {
      var s = O.atr(md.h1, (acfg.atr_period | 0) || 14).filter(function (x) { return x != null && !Number.isNaN(x); });
      if (s.length < 20) return [0, 0];
      var cur = s[s.length - 1];
      var hist = s.slice(Math.max(0, s.length - (lookback + 1)), s.length - 1);
      var mean = hist.length ? hist.reduce(function (a, b) { return a + b; }, 0) / hist.length : 0;
      return [mean > 0 ? cur / mean : 0, mean];
    } catch (e) { return [0, 0]; }
  };

  // ── ۷ قاعدهٔ وتو (فاز ۶b) ────────────────────────────────────
  // هر دروازه یک تابع مستقل با shape قرارداد odin.judge.veto@1 است:
  // (a, symCfg, md, ctx) → Veto|null. بدنهٔ هر تابع، جابه‌جاییِ بایت‌به‌بایتِ
  // همان بلوک از collectVetoes قبلی است — فقط مرز عوض شده، نه منطق.
  // دو مسیر مصرف: مستقیم (collectVetoes با پیش‌فرض O.VETO_RULES) و
  // rule-plugin (adapterهای نازک در js/plugins.js). guardهای کلیدِ
  // judge.veto.* عمداً درون بدنه‌اند (مثل پایتون): مسیر مستقیم بدون
  // registry هم همان کلیدها را می‌خواند — binding مانیفست لایهٔ دوم است.
  O.vetoData = function (a, symCfg, md, ctx) {
    if (a.verdict === 'DATA') {
      return Veto('DATA', '⚠️ دادهٔ ناکافی',
        'تعداد کندل‌ها برای محاسبهٔ EMA200 کافی نیست — تحلیل قابل اتکا نیست');
    }
    return null;
  };

  O.vetoWeekend = function (a, symCfg, md, ctx) {
    var vc = ctx.jcfg.veto;
    if (vc.weekend !== false && !ctx.status.open) {
      return Veto('WEEKEND', '🔒 بازار بسته است', ctx.status.reason_fa);
    }
    return null;
  };

  O.vetoTfConflict = function (a, symCfg, md, ctx) {
    var vc = ctx.jcfg.veto;
    if (vc.timeframe_conflict !== false && a.verdict !== 'DATA' && !a.h1_agrees) {
      return Veto('TF_CONFLICT', '🔀 تضاد جهت بین تایم‌فریم‌ها',
        'روند ۴ ساعته ' + O.TREND_FA[a.trend] + ' است ولی ۱ ساعته هم‌جهت نیست — طبق قوانین، معامله در تضاد تایم‌فریم ممنوع است');
    }
    return null;
  };

  O.vetoRange = function (a, symCfg, md, ctx) {
    var vc = ctx.jcfg.veto;
    var adxMin = +((ctx.acfg.adx_min_trend != null) ? ctx.acfg.adx_min_trend : 20);
    if (vc.range_market !== false && a.verdict !== 'DATA' && a.adx < adxMin) {
      return Veto('RANGE', '😴 بازار بی‌روند (رنج)',
        'ADX=' + O.pyFixed(a.adx, 0) + ' زیر آستانهٔ ' + O.pyFixed(adxMin, 0) + ' است — استراتژی روندی در بازار رنج کار نمی‌کند');
    }
    return null;
  };

  O.vetoEvent = function (a, symCfg, md, ctx) {
    var vc = ctx.jcfg.veto;
    if (vc.high_impact_event !== false && ctx.calSnap && ctx.calSnap.events && ctx.calSnap.events.length) {
      var evs = O.vetoForSymbol(ctx.calSnap.events, a.base, a.quote, ctx.nowMs, +ctx.eventVetoMinutes);
      if (evs.length) {
        var names = evs.slice(0, 2).map(function (e) { return '«' + e.title_fa + '» (' + O.evCountryFa(e) + ')'; }).join('، ');
        var soon = evs.slice().sort(function (x, y) { return Math.abs(O.evMinutesFrom(x, ctx.nowMs)) - Math.abs(O.evMinutesFrom(y, ctx.nowMs)); })[0];
        var mins = Math.round(O.evMinutesFrom(soon, ctx.nowMs));
        var when = O.faNum(Math.abs(mins)) + ' دقیقه ' + (mins >= 0 ? 'بعد' : 'پیش');
        return Veto('EVENT', '📅 رویداد پراثر تقویم',
          names + ' — ' + when + '. نوسان خبری غیرقابل پیش‌بینی است');
      }
    }
    return null;
  };

  O.vetoVolSpike = function (a, symCfg, md, ctx) {
    var vc = ctx.jcfg.veto;
    if (vc.volatility_spike !== false && md) {
      var vol = ctx.jcfg.volatility;
      var lookback = (vol.lookback_bars | 0) || 100;
      var ratio = O.volatilityRatio(md, ctx.acfg, lookback)[0];
      var mult = +vol.spike_multiplier;
      if (ratio && ratio > mult) {
        return Veto('VOL_SPIKE', '📈 جهش غیرعادی نوسان',
          'ATR یک‌ساعتهٔ فعلی ' + O.faNum(O.pyFixed(ratio, 1)) + ' برابر میانگین ' + O.faNum(lookback) +
          ' کندل اخیر است (آستانهٔ وتو: ' + O.faNum(O.pyFixed(mult, 1)) + ' برابر). در این شرایط اسپرد وید می‌شود و حد ضرر قابل اتکا نیست');
      }
    }
    return null;
  };

  O.vetoBreakingNews = function (a, symCfg, md, ctx) {
    var vc = ctx.jcfg.veto;
    if (vc.breaking_news !== false) {
      var brs = O.breakingNewsFor(ctx.newsSnap, a.base, a.quote, (ctx.jcfg.news.breaking_min_score | 0) || 5);
      if (brs.length) {
        return Veto('BREAKING_NEWS', '🚨 خبر فوری',
          '«' + O.headlineFa(brs[0], 70) + '» — تا آرام‌شدن بازار صبر کن');
      }
    }
    return null;
  };

  // ترتیب ارزیابی = دقیقاً ترتیب دروازه‌ها در collectVetoes قبلی (میخِ
  // tests/js/test_judge_switch.js)؛ مسیر rule-plugin هم همین ترتیب را با
  // priority مانیفست‌ها پین می‌کند.
  O.VETO_RULES = [O.vetoData, O.vetoWeekend, O.vetoTfConflict, O.vetoRange,
    O.vetoEvent, O.vetoVolSpike, O.vetoBreakingNews];

  O.collectVetoes = function (a, symCfg, md, ctx, rules) {
    var v = [];
    var list = rules || O.VETO_RULES;
    for (var i = 0; i < list.length; i++) {
      var veto = list[i](a, symCfg, md, ctx);
      if (veto) v.push(veto);
    }
    return v;
  };

  // ── جدول امتیاز (۸ مدرک، حداکثر ۱۱) ────────────────────────
  function evTrend(a, ctx) {
    var strong = a.adx >= +ctx.acfg.adx_strong;
    var pts = strong ? 2 : 1;
    return Evidence('trend', 'هم‌راستایی روند ۴ ساعته و ۱ ساعته', pts, 2,
      'روند ' + O.TREND_FA[a.trend] + ' و تایم‌فریم ۱ ساعته هم تایید می‌کند؛ ADX=' + O.pyFixed(a.adx, 0) +
      ' → ' + (strong ? 'روند قوی' : 'روند متوسط'), true);
  }

  function evLevel(a, ctx, direction) {
    var lc = ctx.jcfg.level;
    var level = direction === 'BUY' ? a.support : a.resistance;
    var kind = direction === 'BUY' ? 'حمایت' : 'مقاومت';
    if (!level || a.atr <= 0) {
      return Evidence('level', 'واکنش به سطح کلیدی (' + kind + ')', 0, 2,
        'سطح ' + kind + ' نزدیکی پیدا نشد — این مدرک قابل بررسی نیست', false, true);
    }
    var dist = Math.abs(a.price - level);
    var ratio = dist / a.atr;
    var pts, word;
    if (ratio <= +lc.close_atr) { pts = 2; word = 'قیمت چسبیده به سطح است (واکنش تازه)'; }
    else if (ratio <= +lc.near_atr) { pts = 1; word = 'قیمت نزدیک سطح است'; }
    else { pts = 0; word = 'قیمت از سطح فاصله گرفته (دیر رسیده‌ایم)'; }
    return Evidence('level', 'واکنش به سطح کلیدی (' + kind + ')', pts, 2,
      kind + ' ' + O.fmtG(level) + ' در فاصلهٔ ' + O.faNum(O.pyFixed(ratio, 1)) + ' برابر ATR — ' + word,
      pts > 0);
  }

  function evFundamental(a, ctx) {
    var fc = ctx.jcfg.fundamental;
    if (!ctx.calSnap) {
      return Evidence('fundamental', 'پنجرهٔ فاندامنتال پاک', 0, 2,
        'موتور فاندامنتال خاموش است — نمی‌توانیم تاییدش کنیم، پس امتیازی نمی‌گیرد', false, true);
    }
    if (!ctx.calSnap.ok) {
      return Evidence('fundamental', 'پنجرهٔ فاندامنتال پاک', 0, 2,
        'تقویم در دسترس نبود — نمی‌توانیم تاییدش کنیم، پس امتیازی نمی‌گیرد', false, true);
    }
    var hiH = +fc.clean_high_hours, mdH = +fc.clean_med_hours;
    var highs = O.upcomingEvents(ctx.calSnap.events, ctx.nowMs, hiH, ['HIGH']);
    var relHi = highs.filter(function (e) { return O.evAffects(e, a.base, a.quote); });
    var meds = O.upcomingEvents(ctx.calSnap.events, ctx.nowMs, mdH, ['MEDIUM']);
    var relMd = meds.filter(function (e) { return O.evAffects(e, a.base, a.quote); });

    if (relHi.length) {
      var e = relHi.slice().sort(function (x, y) { return O.evMinutesFrom(x, ctx.nowMs) - O.evMinutesFrom(y, ctx.nowMs); })[0];
      var hrs = O.evMinutesFrom(e, ctx.nowMs) / 60;
      return Evidence('fundamental', 'پنجرهٔ فاندامنتال پاک', 0, 2,
        'رویداد پراثر «' + e.title_fa + '» (' + O.evCountryFa(e) + ') تا ' + O.faNum(O.pyFixed(hrs, 1)) +
        ' ساعت دیگر — ورود به معامله قبل از آن ریسک دارد', false);
    }
    if (relMd.length) {
      var e2 = relMd.slice().sort(function (x, y) { return O.evMinutesFrom(x, ctx.nowMs) - O.evMinutesFrom(y, ctx.nowMs); })[0];
      return Evidence('fundamental', 'پنجرهٔ فاندامنتال پاک', 1, 2,
        'رویداد پراثری تا ' + O.faNum(O.pyFixed(hiH, 0)) + ' ساعت آینده نیست؛ فقط «' + e2.title_fa +
        '» (اثر متوسط) تا ' + O.faNum(O.pyFixed(O.evMinutesFrom(e2, ctx.nowMs) / 60, 1)) + ' ساعت دیگر', true);
    }
    return Evidence('fundamental', 'پنجرهٔ فاندامنتال پاک', 2, 2,
      'هیچ رویداد پراثری تا ' + O.faNum(O.pyFixed(hiH, 0)) + ' ساعت آینده روی ' + a.base + '/' + a.quote +
      ' نیست — مسیر برای معامله باز است', true);
  }

  function evMomentum(a, ctx, direction) {
    var L = 'تایید مومنتوم (RSI)';
    if (direction === 'BUY') {
      if (a.rsi_rising && a.rsi >= 30 && a.rsi < 50) {
        return Evidence('momentum', L, 1, 1,
          'RSI=' + O.pyFixed(a.rsi, 0) + ' و رو به بالا ↗️ — پولبک در حال برگشت است (بهترین نقطهٔ ورود)', true);
      }
      if (a.rsi < 30) {
        return Evidence('momentum', L, 0, 1,
          'RSI=' + O.pyFixed(a.rsi, 0) + ' در اشباع فروش است — هنوز تایید برگشت نیامده؛ ممکن است «کف‌گیری» ادامه داشته باشد');
      }
      return Evidence('momentum', L, 0, 1,
        'RSI=' + O.pyFixed(a.rsi, 0) + (!a.rsi_rising ? ' رو به بالا نیست' : ' بالای ۵۰ است') + ' — مومنتوم، ورود را تایید نمی‌کند');
    }
    if (!a.rsi_rising && a.rsi > 50 && a.rsi <= 70) {
      return Evidence('momentum', L, 1, 1,
        'RSI=' + O.pyFixed(a.rsi, 0) + ' و رو به پایین ↘️ — اصلاح رو به بالا در روند نزولی (بهترین نقطهٔ ورود فروش)', true);
    }
    if (a.rsi > 70) {
      return Evidence('momentum', L, 0, 1,
        'RSI=' + O.pyFixed(a.rsi, 0) + ' در اشباع خرید است — هنوز تایید برگشت نیامده');
    }
    return Evidence('momentum', L, 0, 1,
      'RSI=' + O.pyFixed(a.rsi, 0) + ' — مومنتوم، ورود فروش را تایید نمی‌کند');
  }

  function evStrength(a, ctx, direction) {
    var L = 'هم‌جهتی جریان قدرت ارزها';
    if (!ctx.ranking || !ctx.ranking.length) {
      return Evidence('strength', L, 0, 1, 'رتبه‌بندی قدرت ارزها محاسبه نشد', false, true);
    }
    var order = ctx.ranking.map(function (x) { return x[0]; });
    var rb = order.indexOf(a.base), rq = order.indexOf(a.quote);
    if (rb < 0 || rq < 0) {
      return Evidence('strength', L, 0, 1, a.base + ' یا ' + a.quote + ' در جدول قدرت ارزها نیست', false, true);
    }
    var n = order.length;
    var want = direction === 'BUY' ? a.base + ' قوی‌تر از ' + a.quote : a.quote + ' قوی‌تر از ' + a.base;
    var aligned = direction === 'BUY' ? rb < rq : rq < rb;
    return Evidence('strength', L, aligned ? 1 : 0, 1,
      'رتبهٔ ' + a.base + ': ' + O.faNum(rb + 1) + ' از ' + O.faNum(n) + ' | رتبهٔ ' + a.quote + ': ' +
      O.faNum(rq + 1) + ' از ' + O.faNum(n) + ' → ' +
      (aligned ? 'جریان قدرت به نفع ' + O.dirFaShort(direction) + ' است ✅'
        : 'جریان قدرت خلاف جهت است (برای ' + want + ' باید برعکس می‌بود)'),
      aligned);
  }

  function evNews(a, ctx, direction) {
    var L = 'تایید خبری';
    if (!ctx.newsSnap || !ctx.newsSnap.ok) {
      return Evidence('news', L, 0, 1, 'موتور اخبار در دسترس نبود — این مدرک بررسی نشد', false, true);
    }
    var vote = O.newsSupports(ctx.newsSnap, a.base, a.quote, direction === 'BUY' ? 'buy' : 'sell',
      (ctx.jcfg.news.min_score | 0) || 4);
    if (vote.verdict > 0) {
      var titles = vote.support.slice(0, 2).map(function (i) { return '«' + O.headlineFa(i, 48) + '»'; }).join('؛ ');
      return Evidence('news', L, 1, 1,
        'اخبار جهت ' + O.dirFaShort(direction) + ' را تایید می‌کند (' + O.faNum(O.fmtGSign(vote.votes)) + ' رأی): ' + titles, true);
    }
    if (vote.verdict < 0) {
      var t2 = vote.contradict.slice(0, 2).map(function (i) { return '«' + O.headlineFa(i, 48) + '»'; }).join('؛ ');
      return Evidence('news', L, 0, 1,
        '⚠️ اخبار خلاف جهت است (' + O.faNum(O.fmtGSign(vote.votes)) + ' رأی): ' + t2);
    }
    return Evidence('news', L, 0, 1, 'اخبار سیگنال روشنی برای این نماد ندارد (خنثی)');
  }

  function evTradingView(a, ctx, direction) {
    var L = 'هم‌جهتی با تریدینگ‌ویو';
    var tv = ctx.tvMap ? ctx.tvMap[a.symbol] : null;
    if (!tv) return Evidence('tv', L, 0, 1, 'تاییدیهٔ تریدینگ‌ویو در دسترس نبود', false, true);
    var want = direction === 'BUY' ? 1 : -1;
    var got = O.TV_DIR[tv.recommendation] || 0;
    // شمارش خرید/فروش/خنثی از API فعلی تریدینگ‌ویو گرفته نمی‌شود (null)؛
    // به‌جای آن تفکیک MA/نوسان‌گرها نمایش داده می‌شود — صادقانه، نه عدد ساختگی.
    var counts = (tv.buy != null && tv.sell != null && tv.neutral != null)
      ? '(' + O.faNum(tv.buy) + ' خرید/' + O.faNum(tv.sell) + ' فروش/' + O.faNum(tv.neutral) + ' خنثی)'
      : (tv.recommend_ma != null && tv.recommend_other != null
        ? '(MA: ' + O.faNum(tv.recommend_ma.toFixed(2)) + ' / نوسان‌گرها: ' + O.faNum(tv.recommend_other.toFixed(2)) + ')'
        : '');
    if (got === want) {
      return Evidence('tv', L, 1, 1,
        'امتیاز تکنیکال رسمی تریدینگ‌ویو «' + tv.recommendation + '» است ' + counts + ' — هم‌جهت با ما ✅', true);
    }
    if (got === 0) {
      return Evidence('tv', L, 0, 1, 'تریدینگ‌ویو خنثی است ' + counts + ' — کمکی به تایید نمی‌کند');
    }
    return Evidence('tv', L, 0, 1, '⚠️ تریدینگ‌ویو «' + tv.recommendation + '» می‌گوید — خلاف جهت تحلیل ما');
  }

  function evSession(ctx) {
    var st = ctx.status;
    var L = 'زمان‌بندی مناسب (سشن)';
    if (!st.open) return Evidence('session', L, 0, 1, st.reason_fa);
    if (st.overlap) return Evidence('session', L, 1, 1, 'سشن ' + st.label + ' — بیشترین نقدینگی و کمترین اسپرد هفته', true);
    if (st.liquid) return Evidence('session', L, 1, 1, 'سشن ' + st.label + ' — نقدینگی خوب برای جفت‌ارزهای ما', true);
    return Evidence('session', L, 0, 1, 'سشن ' + st.label + ' — نقدینگی کمتر، حرکت‌ها کم‌جان‌تر و اسپرد نسبتاً بیشتر');
  }

  // ── صادرات شاهدها (فاز ۶b) ──────────────────────────────────
  // منطق دست‌نخورده است؛ adapterها در js/plugins.js فقط delegation می‌کنند.
  O.evTrend = evTrend;
  O.evLevel = evLevel;
  O.evFundamental = evFundamental;
  O.evMomentum = evMomentum;
  O.evStrength = evStrength;
  O.evNews = evNews;
  O.evTradingView = evTradingView;
  O.evSession = evSession;

  // شکل یکدستِ جدول امتیاز: rule(a, ctx, direction) — همان فهرست امروزِ
  // judgeSymbol. trend/fundamental direction را مصرف نمی‌کنند و session فقط
  // ctx می‌گیرد (wrapperها نادیده می‌گیرند — وعدهٔ §۲.۲ سند، آینهٔ
  // _ev_session_rule پایتون). ترتیب با priority مانیفست‌ها هم پین شده.
  O.EVIDENCE_RULES = [
    function (a, ctx, d) { return evTrend(a, ctx); },
    function (a, ctx, d) { return evLevel(a, ctx, d); },
    function (a, ctx, d) { return evFundamental(a, ctx); },
    function (a, ctx, d) { return evMomentum(a, ctx, d); },
    function (a, ctx, d) { return evStrength(a, ctx, d); },
    function (a, ctx, d) { return evNews(a, ctx, d); },
    function (a, ctx, d) { return evTradingView(a, ctx, d); },
    function (a, ctx, d) { return evSession(ctx); }
  ];

  // ── ورود / حد ضرر / هدف (پورت compute_levels) ────────────────
  O.computeLevels = function (direction, entry, atr, support, resistance, rcfg) {
    var sign = direction === 'BUY' ? 1 : -1;
    if (atr <= 0) {
      atr = Math.abs(entry) * 0.001 || +(rcfg.fallback_atr || 0) || 1e-9;
    }
    var buf = (+rcfg.level_buffer_atr) * atr;
    var level = direction === 'BUY' ? support : resistance;
    var capped = false, sl;

    if (level != null && atr > 0) sl = level - sign * buf;
    else sl = entry - sign * (+rcfg.sl_atr_multiplier) * atr;

    var maxD = (+rcfg.max_sl_atr) * atr;
    var minD = (+rcfg.min_sl_atr) * atr;
    var dist = Math.abs(entry - sl);
    if (atr > 0 && dist > maxD) { sl = entry - sign * maxD; capped = true; }
    else if (atr > 0 && dist < minD) { sl = entry - sign * minD; }

    var risk = Math.abs(entry - sl);
    var tp = entry + sign * risk * (+rcfg.reward_risk);
    return { sl: sl, tp: tp, risk: risk, capped: capped };
  };

  // ── چرا ستاپی شکل نگرفته (حلقهٔ صداقت) ──────────────────────
  function noSetupReason(a, ctx) {
    if (a.trend === 'none') return 'جهت روند نامشخص است';
    if (!a.h1_agrees) return 'تایم‌فریم ۱ ساعته با ۴ ساعته هم‌جهت نیست';
    var adxMin = +(ctx.acfg.adx_min_trend != null ? ctx.acfg.adx_min_trend : 20);
    if (a.adx < adxMin) return 'بازار بی‌روند است (ADX=' + O.pyFixed(a.adx, 0) + ' زیر ' + O.pyFixed(adxMin, 0) + ')';
    if (a.trend === 'bullish') {
      return 'روند صعودی است ولی RSI=' + O.pyFixed(a.rsi, 0) + ' در منطقهٔ پولبک نیست (برای ستاپ خرید باید زیر ۴۵ باشد) — یعنی یا دیر رسیده‌ایم یا اصلاح هنوز تمام نشده';
    }
    return 'روند نزولی است ولی RSI=' + O.pyFixed(a.rsi, 0) + ' در منطقهٔ اصلاح رو به بالا نیست (برای ستاپ فروش باید بالای ۵۵ باشد)';
  }

  function pyRound(x) { // round نیمه‌به-زوج پایتون
    var r = Math.round(x);
    if (Math.abs(x % 1) === 0.5 && r % 2 !== 0) r -= 1;
    return r;
  }

  function p2(n) { return String(n).padStart(2, '0'); }
  function sidStamp(d) {
    return '' + d.getUTCFullYear() + p2(d.getUTCMonth() + 1) + p2(d.getUTCDate()) +
      p2(d.getUTCHours()) + p2(d.getUTCMinutes()) + p2(d.getUTCSeconds());
  }

  // ── داوری یک نماد (هرگز استثنا پرتاب نمی‌کند) ───────────────
  O.judgeSymbol = function (a, symCfg, md, ctx, vetoRules, evidenceRules, riskFn) {
    // vetoRules/evidenceRules/riskFn (فاز ۶b): تزریق *اختیاری* قواعد —
    // undefined = فهرست‌های پیش‌فرض همین ماژول (بایت‌به‌بایت رفتار امروز).
    // مسیر rule-plugin (JudgeAdapter + registry) همان قواعد را از registry
    // تزریق می‌کند؛ طلایی‌های test_judge_switch برابری دو مسیر را پین کرده‌اند.
    var j = {
      symbol: a.symbol, fa_name: a.fa_name, direction: null,
      score: 0, max_score: 11, evidences: [], vetoes: [], warnings: [],
      signal: null, reject_reason: '', reject_detail: '',
      price: a.price, pip: a.pip
    };

    j.vetoes = O.collectVetoes(a, symCfg, md, ctx, vetoRules);

    if (a.verdict === 'BUY_SETUP') j.direction = 'BUY';
    else if (a.verdict === 'SELL_SETUP') j.direction = 'SELL';

    if (j.vetoes.length) {
      j.reject_reason = 'VETO';
      j.reject_detail = j.vetoes.map(function (v) { return v.title_fa; }).join('؛ ');
      return j;
    }
    if (j.direction === null) {
      j.reject_reason = 'NO_SETUP';
      j.reject_detail = noSetupReason(a, ctx);
      return j;
    }

    j.evidences = (evidenceRules || O.EVIDENCE_RULES).map(function (rule) {
      return rule(a, ctx, j.direction);
    });
    j.max_score = j.evidences.reduce(function (s, e) { return s + e.max_points; }, 0);
    j.score = j.evidences.reduce(function (s, e) { return s + e.points; }, 0);

    j.evidences.forEach(function (e) {
      if (e.detail_fa.startsWith('⚠️')) {
        j.warnings.push(e.detail_fa.replace(/^[\u26A0\uFE0F\s]+/, '').trim());
      }
    });

    var minScore = (ctx.jcfg.min_score | 0) || 7;
    if (j.score < minScore) {
      j.reject_reason = 'LOW_SCORE';
      j.reject_detail = 'امتیاز ' + O.faNum(j.score) + ' از ' + O.faNum(j.max_score) +
        ' — زیر آستانهٔ ' + O.faNum(minScore) + ' است، پس سیگنال صادر نمی‌شود';
      return j;
    }

    var rcfg = ctx.jcfg.risk;
    var lv = (riskFn || O.computeLevels)(j.direction, a.price, a.atr, a.support, a.resistance, rcfg);
    if (lv.capped) {
      j.warnings.push('حد ضرر از سطح کلیدی دور بود و به سقف ' + O.faNum(O.pyFixed(+rcfg.max_sl_atr, 1)) + '×ATR محدود شد');
    }
    var opp = j.direction === 'BUY' ? a.resistance : a.support;
    if (opp != null && Math.abs(opp - a.price) < Math.abs(lv.tp - a.price)) {
      var kind = j.direction === 'BUY' ? 'مقاومت' : 'حمایت';
      j.warnings.push(kind + ' ' + O.fmtG(opp) + ' سر راه هدف است — رسیدن به هدف سخت‌تر از چیزی است که نسبت ۱:' + O.faRatio(+rcfg.reward_risk) + ' پیشنهاد می‌دهد');
    }

    var pip = a.pip || 0.0001;
    var risk = Math.abs(a.price - lv.sl);
    j.signal = {
      symbol: a.symbol, fa_name: a.fa_name, direction: j.direction,
      sid: a.symbol + '-' + j.direction + '-' + sidStamp(new Date(ctx.nowMs)) + '-' + (Math.round(a.price * 1e6) / 1e6),
      score: j.score, max_score: j.max_score,
      stars: j.max_score ? Math.max(1, Math.min(5, pyRound(j.score / j.max_score * 5))) : 1,
      entry: a.price, sl: lv.sl, tp: lv.tp, pip: pip, atr: a.atr,
      risk_pips: risk / pip, reward_pips: Math.abs(lv.tp - a.price) / pip,
      rr: +rcfg.reward_risk,
      is_gold: pip >= 0.5, session_fa: ctx.status.label, now: ctx.nowMs,
      evidences: j.evidences, warnings: j.warnings, sl_capped: lv.capped
    };
    return j;
  };

  // سرنوشت همهٔ نمادها + سقف تعداد سیگنال در هر چرخه
  // (پارامترهای قواعد، pass-through به judgeSymbol — فاز ۶b)
  O.judgeAll = function (analyses, datasets, ctx, vetoRules, evidenceRules, riskFn) {
    var out = analyses.map(function (a) {
      return O.judgeSymbol(a, {}, datasets[a.symbol], ctx, vetoRules, evidenceRules, riskFn);
    });
    var cap = (ctx.jcfg.max_signals_per_cycle | 0) || 3;
    var ready = out.filter(function (j) { return j.signal; }).sort(function (x, y) { return y.score - x.score; });
    ready.slice(cap).forEach(function (j) {
      j.reject_reason = 'CAPPED';
      j.reject_detail = 'امتیاز ' + O.faNum(j.score) + ' از ' + O.faNum(j.max_score) +
        ' کافی بود، ولی سقف ' + O.faNum(cap) + ' سیگنال در هر چرخه پر شده — بهترین‌ها اولویت دارند';
      j.signal = null;
    });
    return out;
  };

  O.judgmentStatusFa = function (j) {
    if (j.signal) return '✅ سیگنال صادر شد';
    return {
      VETO: '🚫 وتو شد', LOW_SCORE: '⏳ امتیاز ناکافی', NO_SETUP: '❔ ستاپی شکل نگرفته',
      CAPPED: '🔢 به سقف تعداد سیگنال رسید', DISABLED: '⚙️ داور خاموش است'
    }[j.reject_reason] || '—';
  };

  // رکورد JSON ژورنال (پورت Signal.to_journal)
  O.signalToJournal = function (s, sent) {
    return {
      kind: 'signal', id: s.sid, ts: new Date(s.now).toISOString(),
      symbol: s.symbol, direction: s.direction,
      entry: Math.round(s.entry * 1e6) / 1e6,
      sl: Math.round(s.sl * 1e6) / 1e6,
      tp: Math.round(s.tp * 1e6) / 1e6,
      pip: s.pip, atr: Math.round(s.atr * 1e6) / 1e6,
      risk_pips: Math.round(s.risk_pips * 10) / 10,
      reward_pips: Math.round(s.reward_pips * 10) / 10,
      rr: s.rr, score: s.score, max_score: s.max_score, session: s.session_fa,
      evidences: s.evidences.map(function (e) { return e.key + ':' + e.points + '/' + e.max_points; }),
      sent: sent !== false
    };
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
