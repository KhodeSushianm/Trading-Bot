/* لایهٔ داده — HTTP (پل نیتیو یا fetch)، Yahoo Finance، تریدینگ‌ویو،
 * تقویم اقتصادی و اخبار + ارکستراسیون کل چرخهٔ تحلیل.
 *
 * ⚠️ همهٔ توابع «هرگز استثنا پرتاب نمی‌کنند» — در بدترین حالت دادهٔ
 *    unavailable برمی‌گردد تا داور صادقانه ۰ امتیاز بدهد (حلقهٔ صداقت).
 */
(function (O) {
  'use strict';

  var YAHOO_CHART = 'https://query1.finance.yahoo.com/v8/finance/chart/';

  // ── HTTP ────────────────────────────────────────────────────
  var cbSeq = 1;
  var pending = {};

  O.httpDone = function (cbId, status, b64) {
    var p = pending[cbId];
    if (!p) return;
    delete pending[cbId];
    var text = '';
    try {
      if (b64) {
        var bin = atob(b64);
        var bytes = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        text = new TextDecoder('utf-8').decode(bytes);
      }
    } catch (e) { text = ''; }
    p({ status: status, text: text });
  };

  O.http = function (url, opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      try {
        if (typeof ODINNative !== 'undefined' && ODINNative.http) {
          var id = cbSeq++;
          pending[id] = resolve;
          ODINNative.http(id, url, opts.method || 'GET', opts.body || '', opts.contentType || 'application/json');
          return;
        }
      } catch (e) { /* fallback */ }
      // محیط مرورگر/Node (توسعه و تست) — بدون پل نیتیو
      try {
        var init = { method: opts.method || 'GET', headers: { 'Accept': '*/*' } };
        if (opts.body) {
          init.body = opts.body;
          init.headers['Content-Type'] = opts.contentType || 'application/json';
        }
        fetch(url, init).then(function (r) {
          return r.text().then(function (t) { resolve({ status: r.status, text: t }); });
        }).catch(function (e) { resolve({ status: -1, text: String(e && e.message || e) }); });
      } catch (e2) {
        resolve({ status: -1, text: String(e2 && e2.message || e2) });
      }
    });
  };

  // ── حافظهٔ محلی ─────────────────────────────────────────────
  O.makeStorage = function () {
    if (typeof ODINNative !== 'undefined' && ODINNative.getPref) {
      return {
        get: function (k) { try { return ODINNative.getPref(k) || ''; } catch (e) { return ''; } },
        set: function (k, v) { try { ODINNative.setPref(k, v == null ? '' : String(v)); } catch (e) { } },
        del: function (k) { try { ODINNative.removePref(k); } catch (e) { } }
      };
    }
    var mem = {};
    return {
      get: function (k) { return mem[k] || ''; },
      set: function (k, v) { mem[k] = String(v); },
      del: function (k) { delete mem[k]; }
    };
  };

  // ── Yahoo Finance (معادل yfinance.download) ─────────────────
  function getChart(ticker, range, interval) {
    var url = YAHOO_CHART + encodeURIComponent(ticker) + '?range=' + range + '&interval=' + interval;
    return O.http(url).then(function (r) {
      if (r.status !== 200) return null;
      try {
        var j = JSON.parse(r.text);
        var res = j.chart && j.chart.result && j.chart.result[0];
        if (!res || !res.timestamp) return null;
        var q = res.indicators.quote[0];
        var out = [];
        for (var i = 0; i < res.timestamp.length; i++) {
          var o = q.open[i], h = q.high[i], l = q.low[i], c = q.close[i];
          if (o == null || h == null || l == null || c == null) continue;  // dropna
          out.push({ t: res.timestamp[i] * 1000, o: o, h: h, l: l, c: c });
        }
        return out.length ? out : null;
      } catch (e) { return null; }
    }).catch(function () { return null; });
  }

  // H1 → H4 (دقیقاً مثل pandas resample("4h") روی ایندکس UTC:
  // سطل‌ها از نیمه‌شب UTC هر ۴ ساعت؛ Open=first, High=max, Low=min, Close=last)
  O.resample4h = function (h1) {
    var buckets = new Map();
    h1.forEach(function (x) {
      var key = Math.floor(x.t / 14400000);
      var b = buckets.get(key);
      if (!b) buckets.set(key, { t: key * 14400000, o: x.o, h: x.h, l: x.l, c: x.c });
      else {
        if (x.h > b.h) b.h = x.h;
        if (x.l < b.l) b.l = x.l;
        b.c = x.c;
      }
    });
    return Array.from(buckets.values()).sort(function (a, b) { return a.t - b.t; });
  };

  O.fetchYahooSymbol = function (symCfg, hcfg) {
    var y = symCfg.yahoo || (symCfg.name + '=X');
    var h1Days = (hcfg && hcfg.yahoo_h1_days) || 60;
    var m15Days = (hcfg && hcfg.yahoo_m15_days) || 5;
    var dropForming = !(hcfg && hcfg.drop_forming_candle === false);

    function dl(ticker, interval, range) {
      return getChart(ticker, range, interval).then(function (df) {
        if (df && dropForming && df.length > 1) df = df.slice(0, -1);  // کندل در حال تشکیل
        return df;
      });
    }

    return dl(y, '1h', h1Days + 'd').then(function (h1) {
      return dl(y, '15m', m15Days + 'd').then(function (m15) {
        function alt(cb) {
          if (symCfg.yahoo_alt) {
            return dl(symCfg.yahoo_alt, '1h', h1Days + 'd').then(function (h1b) {
              return dl(symCfg.yahoo_alt, '15m', m15Days + 'd').then(function (m15b) { cb(h1b, m15b); });
            });
          }
          cb(null, null);
        }
        function finish(a, b) {
          if (!a || !b || a.length < 250) return null;
          var h4 = O.resample4h(a);
          if (h4.length < 210) return null;
          return { symbol: symCfg.name, m15: b, h1: a, h4: h4 };
        }
        if (h1 && m15) return finish(h1, m15);
        return new Promise(function (res) {
          alt(function (a2, b2) { res(finish(a2 || h1, b2 || m15)); });
        });
      });
    }).catch(function () { return null; });
  };

  // ── تاییدیه تریدینگ‌ویو (اسکنر غیررسمی، بدون لاگین) ─────────
  // ⚠️ نکتهٔ صادقانه: ستون‌های شمارش (Buy.All و...) دیگر از API گرفته
  // نمی‌شوند (null)؛ مقدار توصیه (Recommend.All) با پسوند دقیقه‌ای کار
  // می‌کند (4h → |240) و ملاک امتیاز داور همان است.
  var TF_SUFFIX = { '15m': '15', '1h': '60', '4h': '240' };

  function recLabel(v) {
    if (v == null) return null;
    if (v > 0.5) return 'STRONG_BUY';
    if (v > 0.1) return 'BUY';
    if (v >= -0.1) return 'NEUTRAL';
    if (v >= -0.5) return 'SELL';
    return 'STRONG_SELL';
  }

  O.fetchTvSnapshot = function (symbolsCfg, timeframe) {
    var tf = String(timeframe || '4h').toLowerCase();
    var suf = TF_SUFFIX[tf] || '240';
    var byScreener = {};
    symbolsCfg.forEach(function (s) {
      var tv = s.tv || {};
      if (!tv.symbol) return;
      var scr = tv.screener || 'forex';
      (byScreener[scr] = byScreener[scr] || []).push({
        name: s.name, ticker: (tv.exchange || 'FX') + ':' + tv.symbol
      });
    });
    var cols = ['close', 'Recommend.All|' + suf, 'Recommend.MA|' + suf, 'Recommend.Other|' + suf,
      'Buy.All|' + suf, 'Sell.All|' + suf, 'Neutral.All|' + suf, 'RSI|' + suf, 'ADX|' + suf];

    return Promise.all(Object.keys(byScreener).map(function (scr) {
      var tickers = byScreener[scr].map(function (x) { return x.ticker; });
      return O.http('https://scanner.tradingview.com/' + scr + '/scan', {
        method: 'POST',
        body: JSON.stringify({ symbols: { tickers: tickers }, columns: cols })
      }).then(function (r) {
        var out = {};
        if (r.status !== 200) return out;
        try {
          var j = JSON.parse(r.text);
          (j.data || []).forEach(function (row) {
            var hit = byScreener[scr].filter(function (x) { return x.ticker === row.s; })[0];
            if (!hit) return;
            var d = row.d || [];
            var rec = recLabel(d[1]);
            if (!rec) return;              // داده‌ای نیست → مدرک unavailable می‌ماند
            out[hit.name] = {
              symbol: hit.name, close: d[0], recommendation: rec,
              recommend_ma: d[2], recommend_other: d[3],
              buy: d[4], sell: d[5], neutral: d[6],
              rsi: d[7], adx: d[8], timeframe: tf
            };
          });
        } catch (e) { /* ignore */ }
        return out;
      }).catch(function () { return {}; });
    })).then(function (maps) {
      var all = {};
      maps.forEach(function (m) { Object.keys(m).forEach(function (k) { all[k] = m[k]; }); });
      return all;
    });
  };

  // ── تقویم اقتصادی (با کش محلی TTL‌دار، مثل دسکتاپ) ──────────
  O.fetchCalendar = function (cfg, storage) {
    var fcfg = cfg.fundamental || {};
    if (fcfg.enabled === false) {
      return Promise.resolve({ events: [], ok: false, error: 'غیرفعال در تنظیمات', fetched: false, stale: false, fromCache: false, weekRange: ['', ''] });
    }
    var ttl = (+(fcfg.cache_ttl_minutes) || 30) * 60000;
    var url = fcfg.source_url || 'https://nfs.faireconomy.media/ff_calendar_thisweek.json';

    function readCache() {
      try {
        var raw = storage.get('cache.calendar');
        if (!raw) return null;
        var blob = JSON.parse(raw);
        if (!blob || !Array.isArray(blob.events)) return null;
        return { raw: blob.events, ts: Date.parse(blob.fetched_at) };
      } catch (e) { return null; }
    }
    function build(raw, fetchedAt, fromCache, stale, fetched) {
      var events = O.parseEvents(raw);
      var dates = events.map(function (e) { return new Date(e.when).toISOString().slice(0, 10); }).sort();
      return {
        events: events, fetchedAt: fetchedAt, fromCache: fromCache, stale: stale,
        fetched: fetched, error: '', ok: events.length > 0, source: O.CAL_SOURCE_NAME,
        weekRange: dates.length ? [dates[0], dates[dates.length - 1]] : ['', '']
      };
    }

    var cached = readCache();
    if (cached && (Date.now() - cached.ts) <= ttl) {
      return Promise.resolve(build(cached.raw, cached.ts, true, false, false));
    }
    return O.http(url).then(function (r) {
      if (r.status === 200) {
        try {
          var raw = JSON.parse(r.text);
          if (Array.isArray(raw)) {
            try { storage.set('cache.calendar', JSON.stringify({ fetched_at: new Date().toISOString(), events: raw })); } catch (e) { }
            return build(raw, Date.now(), false, false, true);
          }
        } catch (e) { /* fallthrough */ }
      }
      // زنده ناموفق — کش کهنه بهتر از هیچی است (و صادقانه علامت می‌خورد)
      if (cached && cached.raw) {
        var s = build(cached.raw, cached.ts, true, true, false);
        s.error = 'HTTP ' + r.status;
        return s;
      }
      return { events: [], ok: false, error: 'HTTP ' + r.status, fetched: false, stale: false, fromCache: false, weekRange: ['', ''] };
    }).catch(function (e) {
      if (cached && cached.raw) {
        var s = build(cached.raw, cached.ts, true, true, false);
        s.error = String(e && e.message || e);
        return s;
      }
      return { events: [], ok: false, error: String(e && e.message || e), fetched: false, stale: false, fromCache: false, weekRange: ['', ''] };
    });
  };

  // ── اخبار (RSS زنده در هر اجرا — بدون کش) ───────────────────
  O.fetchNews = function (cfg, onLog) {
    var ncfg = cfg.news || {};
    if (ncfg.enabled === false) {
      return Promise.resolve({ items: [], ok: false, error: 'غیرفعال در تنظیمات', feedsOk: 0, feedsFailed: 0, staleFeeds: [], failedNames: [], rawCount: 0 });
    }
    var feeds = ncfg.feeds && ncfg.feeds.length ? ncfg.feeds : O.CONFIG.news.feeds;
    var nowMs = Date.now();
    var age = +(ncfg.max_age_hours) || 30;
    var minScore = (ncfg.min_score | 0) || 2;
    var perFeed = (ncfg.max_items_per_feed | 0) || 12;
    var totalMax = (ncfg.max_total | 0) || 18;

    var snap = {
      items: [], fetchedAt: nowMs, feedsOk: 0, feedsFailed: 0,
      staleFeeds: [], failedNames: [], rawCount: 0, error: ''
    };
    var seen = {};
    var itemsAll = [];

    return Promise.all(feeds.map(function (f) {
      var name = f.name || f.url || 'feed';
      return O.http(f.url).then(function (r) {
        if (r.status !== 200 || !r.text) throw new Error('HTTP ' + r.status);
        var entries = O.parseFeedXml(r.text);
        if (!entries.length) throw new Error('فید خالی یا بدون ورودی بود');
        var items = O.parseEntries(entries, name, f.weight | 0 || 1, nowMs, age, minScore);
        items.sort(function (a, b) { return (b.published || nowMs) - (a.published || nowMs); });
        items = items.slice(0, perFeed);
        var fresh = items.filter(function (it) {
          var k = O.dedupeKey(it.title);
          if (seen[k]) return false;
          seen[k] = true;
          return true;
        });
        snap.feedsOk += 1;
        snap.rawCount += entries.length;
        if (!fresh.length && entries.length) {
          snap.staleFeeds.push(name);
          if (onLog) onLog('[i] ' + name + ': همهٔ ' + O.faNum(entries.length) + ' ورودی کهنه یا تکراری بودند — رد شد');
        } else {
          if (onLog) onLog('📰 ' + name + ': ' + O.faNum(fresh.length) + ' خبر تازه (از ' + O.faNum(entries.length) + ' ورودی)');
        }
        itemsAll = itemsAll.concat(fresh);
      }).catch(function (e) {
        snap.feedsFailed += 1;
        snap.failedNames.push(name);
        if (onLog) onLog('[!] فید ' + name + ' ناموفق: ' + String(e && e.message || e).slice(0, 70));
      });
    })).then(function () {
      itemsAll.sort(function (a, b) { return (b.score - a.score) || (a.age_minutes - b.age_minutes); });
      snap.items = itemsAll.slice(0, totalMax);
      snap.ok = snap.items.length > 0;
      if (!snap.ok) snap.error = 'خبر مرتبطی در بازهٔ زمانی پیدا نشد';
      return snap;
    });
  };

  // ── چرخهٔ کامل تحلیل (معادل run_cycle بدون تلگرام) ──────────
  // فاز ۶: قابلیت‌ها از registry مصرف می‌شوند (caps) — ترتیب/لاگ‌ها/خروجی
  // بایت‌به‌بایت همان قبلی (میخ: tests/js/test_cycle_switch.js). رویدادهای
  // BUS افزودنی‌اند: بدون listener هیچ اثر رفتاری ندارند.
  /* ۶c (v0.28): runPipeline به دو بخشِ نام‌دار شکافته شد — collectMarket و
   * collectFundamental — تا cycleCore بتواند آن‌ها را در مراحلِ کانونیکالِ
   * pipeline بگذارد (ترتیبِ پایتون: fundamental *بعد از* journal_pre).
   * caps توسط صداکننده ساخته/رد می‌شود (چرخه یک caps دارد، نه دو تا)؛
   * بدون آن، هر بخش caps خودش را می‌سازد (رفتارِ مستقل حفظ شود).
   * wrapperِ O.runPipeline امضا و رفتارِ قدیم را بایت‌به‌بایت نگه می‌دارد:
   * fundamental فقط وقتی analyses هست (early-out امروز). */
  O.collectMarket = function (cfg, storage, log, caps) {
    log = log || function () { };
    caps = caps || O.makeCaps(cfg);
    var mkt = {
      analyses: [], datasets: {}, ranking: [], tvMap: {}, tvTf: '4h',
      sourceName: 'yahoo', errors: 0
    };
    var syms = cfg.symbols;
    var total = syms.length;
    var done = 0;

    // منبع داده — connect/disconnect در adapter جاوااسکریپت no-op صادقانه‌اند
    // (fetch بی‌حالت است) ولی shape قراردادِ مشترک با دسکتاپ حفظ می‌شود.
    var source = caps.market;
    if (!source) {
      log('❌ منبع داده در دسترس نیست — اینترنت/تنظیمات را بررسی کنید');
      mkt.errors = 1;
      O.BUS.emit(O.core.EVENTS.MARKET_COLLECTED, { analyses: 0, errors: mkt.errors });
      return Promise.resolve(mkt);
    }
    try { source.connect(); }
    catch (e) {
      log('❌ اتصال به منبع داده ناموفق: ' + String(e && e.message || e).slice(0, 120));
      mkt.errors = 1;
      O.BUS.emit(O.core.EVENTS.MARKET_COLLECTED, { analyses: 0, errors: mkt.errors });
      return Promise.resolve(mkt);
    }

    return Promise.all(syms.map(function (s) {
      log('📡 دریافت ' + s.name + '...');
      return source.fetch(s).then(function (md) {
        done++;
        if (!md) {
          mkt.errors++;
          log('[!] دادهٔ ' + s.name + ' ناقص است — رد شد');
        } else {
          mkt.datasets[s.name] = md;
          try { mkt.analyses.push(caps.technical.analyzeSymbol(s, md, cfg.analysis)); }
          catch (e) { mkt.errors++; log('[!] خطای تحلیل ' + s.name + ': ' + e); }
        }
        log('(' + O.faNum(done) + '/' + O.faNum(total) + ') ' + s.name + (md ? ' ✅' : ' ❌'));
      });
    })).then(function () {
      try { source.disconnect(); } catch (e) { }
      if (!mkt.analyses.length) {
        log('❌ هیچ نمادی تحلیل نشد — اینترنت را بررسی کنید');
        mkt.errors = Math.max(mkt.errors, 1);
        O.BUS.emit(O.core.EVENTS.MARKET_COLLECTED, { analyses: 0, errors: mkt.errors });
        return mkt;
      }
      log('✅ تحلیل ' + O.faNum(mkt.analyses.length) + ' نماد انجام شد');
      mkt.ranking = caps.strength.currencyStrength(mkt.datasets, (cfg.analysis.strength_lookback_h1 | 0) || 24);
      // market.collected: payload همان کلیدهای پایتون {analyses, errors} —
      // اینجا منتشر می‌شود چون تعداد تحلیل‌ها قطعی است (TV لایهٔ تاییدیه است
      // و هم‌زمان با فاندامنتال واکشی می‌شود؛ در پایتون بخشی از collect_market است)
      O.BUS.emit(O.core.EVENTS.MARKET_COLLECTED,
        { analyses: mkt.analyses.length, errors: mkt.errors });
      return mkt;
    });
  };

  O.collectFundamental = function (cfg, storage, mkt, log, caps) {
    log = log || function () { };
    caps = caps || O.makeCaps(cfg);

      var tvCfg = cfg.tradingview || {};
      mkt.tvTf = tvCfg.timeframe || '4h';
      var tv = caps.tv;   // binding مانیفست: tradingview.enabled=false → null
      var tvP = (tvCfg.enabled !== false && tv)
        ? (log('🔍 دریافت تاییدیه تریدینگ‌ویو...'),
          tv.fetchTvSnapshot(cfg.symbols, mkt.tvTf).then(function (m) {
            mkt.tvMap = m || {};
            log('✅ تاییدیه تریدینگ‌ویو برای ' + O.faNum(Object.keys(mkt.tvMap).length) + ' نماد دریافت شد');
          }))
        : Promise.resolve();

      // فاز ۷ — تک‌مسیر: پلاگین خاموش (طبق binding) → همان snap
      // «غیرفعال در تنظیمات» درون‌خطی — بایت‌به‌بایت با خروجیِ guard داخلیِ
      // O.fetchCalendar (smoke_plugins برابری این دو را assert می‌کند).
      // guard داخلی سرِ جایش می‌ماند (دفاع لایهٔ دوم + سایر مصرف‌کننده‌ها).
      var cal = caps.calendar;
      var calP = (cal ? cal.fetchCalendar(cfg, storage) : Promise.resolve({
        events: [], ok: false, error: 'غیرفعال در تنظیمات', fetched: false,
        stale: false, fromCache: false, weekRange: ['', '']
      })).then(function (s) {
        mkt.calSnap = s;
        if (s && s.ok) log('🏦 تقویم اقتصادی: ' + O.faNum(s.events.length) + ' رویداد' + (s.fromCache ? ' (از کش)' : ''));
        else log('[!] تقویم اقتصادی در دسترس نیست: ' + String((s && s.error) || '').slice(0, 80));
      });

      var news = caps.news;
      var newsP = (news ? news.fetchNews(cfg, log) : Promise.resolve({
        items: [], ok: false, error: 'غیرفعال در تنظیمات', feedsOk: 0,
        feedsFailed: 0, staleFeeds: [], failedNames: [], rawCount: 0
      })).then(function (s) {
        mkt.newsSnap = s;
        if (s && s.ok) {
          var br = s.items.filter(function (i) { return i.breaking; }).length;
          log('✅ موتور اخبار: ' + O.faNum(s.items.length) + ' خبر (' + O.faNum(s.feedsOk) + ' فید موفق، ' +
            O.faNum(s.feedsFailed) + ' نامفق' + (br ? '، ' + O.faNum(br) + ' فوری' : '') + ')');
        } else log('[!] موتور اخبار: ' + ((s && s.error) || 'خبری پیدا نشد'));
      });

      return Promise.all([tvP, calP, newsP]).then(function () {
        O.BUS.emit(O.core.EVENTS.FUNDAMENTAL_COLLECTED, {
          calendar_ok: !!(mkt.calSnap && mkt.calSnap.ok),
          news_items: (mkt.newsSnap && mkt.newsSnap.items) ? mkt.newsSnap.items.length : 0
        });
        return mkt;
      });
  };

  // wrapper سازگار: همان امضا/رفتارِ پیش از ۶c (مصرف‌کننده‌های مستقل نشکنند)
  O.runPipeline = function (cfg, storage, onProgress) {
    var log = onProgress || function () { };
    var caps = O.makeCaps(cfg);
    return O.collectMarket(cfg, storage, log, caps).then(function (mkt) {
      if (!mkt.analyses.length) return mkt;   // early-out امروز: fundamental واکشی نمی‌شود
      return O.collectFundamental(cfg, storage, mkt, log, caps);
    });
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
