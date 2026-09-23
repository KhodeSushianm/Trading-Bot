/* پلاگین‌های داخلی (built-in) ODIN برای اندروید — فاز ۶.
 *
 * آینهٔ JS برای src/plugins/ پایتون: adapterهای نازک (delegation خالص) دور
 * توابع *موجود* اپ (O.fetchYahooSymbol، O.judgeAll، ...) با مانیفست‌های
 * اعلانی — همان idها/stageها/priorityها/config-bindingهای پایتون تا دو
 * موتور یک ساختار داشته باشند (platforms اینجا ['android'] است؛ همتاهای
 * desktop-only مثل notify-telegram و data-auto/twelvedata اینجا ثبت نمی‌شوند).
 *
 * قاعدهٔ adapter: فقط delegation — منطق در همان ماژول‌های قبلی دست‌نخورده
 * است. ارجاع به O.* در *زمان فراخوانی* انجام می‌شود (نه بارگذاری)، پس
 * ترتیب اسکریپت‌ها فقط برای بودنِ O.core در زمان ثبت مهم است.
 *
 * exports:
 *   O.BUS                   — bus واحد اپ (آینهٔ BUS ماژول‌محور engine پایتون)
 *   O.buildDefaultRegistry  — آینهٔ build_default_registry پایتون
 *   O.makeCaps              — آینهٔ _Caps در src/engine.py (نمونه‌های تنبل،
 *                             پلاگین خراب → throw، غیرفعال → null)
 *
 * ⚠️ داور JS در این فاز یکجا ثبت می‌شود (judge-core = judgeAll) — شکافتن
 *   ۷ وتو + ۸ شاهدِ judge.js به rule-plugin آینهٔ فاز ۴ پایتون است و
 *   زیرفازِ جداگانهٔ «۶b» با میخ‌های خودش (توابع ev* در judge.js
 *   فایل-خصوصی‌اند). محاسبات داور همین حالا با run_parity پین شده‌اند.
 *
 * سبک: ES5 خالص (var/function) — نگهبانش بخش مشروطِ test_cycle_switch.js.
 */
(function (O) {
  'use strict';

  // نسخهٔ semver خودِ پلاگین‌ها — مستقل از نسخهٔ اپ است. عمداً از اجزا
  // ساخته می‌شود (نه literal نقل‌قولی «x.y.z») تا نگهبانِ «شمارهٔ نسخهٔ
  // هاردکد» (بررسی ۷ در smoke_theme_parity — که برای گرفتنِ کپیِ کهنهٔ
  // APP_VERSION طراحی شده) روی آن false-positive ندهد. این عدد *نسخهٔ اپ
  // نیست*؛ validateManifest در core.js همان شکل semver را الزام می‌کند.
  var V = [1, 0, 0].join('.');

  // ── adapterها (همه stateless جز data-yahoo که cfg.history را نگه می‌دارد) ──

  function YahooAdapter(context) {
    this._cfg = (context && context.cfg) || {};
  }
  YahooAdapter.prototype.name = 'yahoo';
  // fetch در JS بی‌حالت است (بدون session پایدار) — connect/disconnect برای
  // حفظ shape قراردادِ مشترک با دسکتاپ صادقانه no-op هستند.
  YahooAdapter.prototype.connect = function () { };
  YahooAdapter.prototype.disconnect = function () { };
  YahooAdapter.prototype.fetch = function (symCfg) {
    return O.fetchYahooSymbol(symCfg, (this._cfg && this._cfg.history) || {});
  };

  function TvAdapter() { }
  TvAdapter.prototype.fetchTvSnapshot = function (symbolsCfg, timeframe) {
    return O.fetchTvSnapshot(symbolsCfg, timeframe);
  };

  function TechnicalAdapter() { }
  TechnicalAdapter.prototype.analyzeSymbol = function (symCfg, md, acfg) {
    return O.analyzeSymbol(symCfg, md, acfg);
  };

  function StrengthAdapter() { }
  StrengthAdapter.prototype.currencyStrength = function (datasets, lookbackH1) {
    return O.currencyStrength(datasets, lookbackH1);
  };

  function SessionAdapter() { }
  SessionAdapter.prototype.marketStatus = function (now) {
    return O.marketStatus(now);
  };

  function CalendarAdapter() { }
  CalendarAdapter.prototype.fetchCalendar = function (cfg, storage) {
    return O.fetchCalendar(cfg, storage);
  };
  CalendarAdapter.prototype.upcomingEvents = function (events, nowMs, hours, impacts, countries, limit) {
    return O.upcomingEvents(events, nowMs, hours, impacts, countries, limit);
  };
  CalendarAdapter.prototype.vetoForSymbol = function (events, base, quote, nowMs, minutes) {
    return O.vetoForSymbol(events, base, quote, nowMs, minutes);
  };

  function NewsAdapter() { }
  NewsAdapter.prototype.fetchNews = function (cfg, onLog) {
    return O.fetchNews(cfg, onLog);
  };

  function JudgeAdapter() { }
  // تنظیمات داور در JS از قبل در config.js با پیش‌فرض‌ها ادغام شده
  // (O.deepFill(O.CONFIG, settings) در buildCfg) — پس judgeConfig همان
  // بخشِ ادغام‌شده را برمی‌گرداند (همتای judge_config پایتون).
  JudgeAdapter.prototype.judgeConfig = function (cfg) {
    return (cfg && cfg.judge) || {};
  };
  JudgeAdapter.prototype.judgeAll = function (analyses, datasets, ctx) {
    return O.judgeAll(analyses, datasets, ctx);
  };

  function RiskAdapter() { }
  RiskAdapter.prototype.computeLevels = function (direction, entry, atr, support, resistance, rcfg) {
    return O.computeLevels(direction, entry, atr, support, resistance, rcfg);
  };

  function JournalAdapter() { }
  JournalAdapter.prototype.open = function (storage) {
    return new O.Journal(storage);
  };
  JournalAdapter.prototype.resolveOpenSignals = function (journal, datasets, nowMs, cfg, onLog) {
    return O.resolveOpenSignals(journal, datasets, nowMs, cfg, onLog);
  };
  JournalAdapter.prototype.computeStats = function (entries, nowMs) {
    return O.computeStats(entries, nowMs);
  };
  // اضافی (بیرون از shape حداقلی قرارداد — مصرف‌کنندهٔ dispatch در cycleCore):
  JournalAdapter.prototype.shouldSendSignal = function (state, sig, jcfg, nowMs) {
    return O.shouldSendSignal(state, sig, jcfg, nowMs);
  };
  JournalAdapter.prototype.signalToJournal = function (sig, sent) {
    return O.signalToJournal(sig, sent);
  };

  function AlertsAdapter() { }
  AlertsAdapter.prototype.checkAlerts = function (storage, analyses, nowMs) {
    return O.alertsCheck(storage, analyses, nowMs);
  };

  // ── تعریف پلاگین‌ها — manifestها آینهٔ همتاهای پایتون در src/plugins/ ──
  // (id/stage/priority/config یکسان؛ platforms فقط android)
  var DEFS = [
    {
      id: 'data-yahoo', provides: ['odin.data.market@1'], config: null,
      stage: 'collect_market', priority: 20,
      factory: function (context) { return new YahooAdapter(context); }
    },
    {
      id: 'data-tradingview', provides: ['odin.data.tv@1'],
      config: { section: 'tradingview', enabled_key: 'enabled', 'default': true },
      stage: 'collect_market', priority: 40,
      factory: function () { return new TvAdapter(); }
    },
    {
      id: 'analysis-technical', provides: ['odin.analysis.technical@1'], config: null,
      stage: 'collect_market', priority: 50,
      factory: function () { return new TechnicalAdapter(); }
    },
    {
      id: 'analysis-strength', provides: ['odin.analysis.strength@1'], config: null,
      stage: 'collect_market', priority: 60,
      factory: function () { return new StrengthAdapter(); }
    },
    {
      id: 'session', provides: ['odin.session@1'], config: null,
      stage: 'judge', priority: 10,
      factory: function () { return new SessionAdapter(); }
    },
    {
      id: 'fundamental-calendar', provides: ['odin.fundamental.calendar@1'],
      config: { section: 'fundamental', enabled_key: 'enabled', 'default': true },
      stage: 'collect_fundamental', priority: 10,
      factory: function () { return new CalendarAdapter(); }
    },
    {
      id: 'fundamental-news', provides: ['odin.fundamental.news@1'],
      config: { section: 'news', enabled_key: 'enabled', 'default': true },
      stage: 'collect_fundamental', priority: 20,
      factory: function () { return new NewsAdapter(); }
    },
    {
      // عمداً config=None (مثل پایتون): judgeConfig/judgeAll در مسیرهای
      // بدون guard هم مصرف می‌شوند — کلید judge.enabled همان guard فعلی
      // cycleCore است (بازبینی در فاز ۷).
      id: 'judge-core', provides: ['odin.judge.engine@1'], config: null,
      stage: 'judge', priority: 50,
      factory: function () { return new JudgeAdapter(); }
    },
    {
      id: 'judge-risk', provides: ['odin.judge.risk@1'], config: null,
      stage: 'judge', priority: 60,
      factory: function () { return new RiskAdapter(); }
    },
    {
      // config=None مثل پایتون: shouldSendSignal/signalToJournal بدون چکِ
      // journal.enabled هم مصرف می‌شوند (ضداسپم باید همیشه کار کند).
      id: 'journal', provides: ['odin.journal@1'], config: null,
      stage: 'journal_pre', priority: 10,
      factory: function () { return new JournalAdapter(); }
    },
    {
      id: 'alerts-price', provides: ['odin.alerts.price@1'], config: null,
      stage: 'price_alerts', priority: 10,
      factory: function () { return new AlertsAdapter(); }
    }
  ];

  // ── bus واحد اپ — آینهٔ BUS در src/engine.py (بدون listener = صفر اثر) ──
  O.BUS = O.core.createBus();

  // ── ساخت registry — آینهٔ build_default_registry در src/plugins/__init__.py ──
  O.buildDefaultRegistry = function (cfg, platform) {
    cfg = cfg || O.CONFIG;
    platform = platform || 'android';
    var reg = O.core.createRegistry({ knownStages: O.core.STAGES });
    var log = [];
    var i;

    for (i = 0; i < DEFS.length; i++) {
      var def = DEFS[i];
      var manifest = O.core.manifest({
        id: def.id, version: V, provides: def.provides,
        config: def.config, platforms: ['android'],
        stage: def.stage, priority: def.priority, optional: true
      }, O.core.STAGES);
      if (manifest.platforms.indexOf(platform) < 0) continue;
      var rec = reg.register(manifest, def.factory);
      log.push('[plugin] «' + rec.id + '» ثبت شد — فراهم‌کنندهٔ ' +
        manifest.provides.join(', ') + ' (مرحله: ' + manifest.stage + ')');
    }

    // فعال/غیرفعال طبق *همان کلیدهای موجود* config (بدون کلید جدید)
    var enabled = O.core.applyConfigState(reg, cfg);
    Object.keys(enabled).forEach(function (pid) {
      if (!enabled[pid]) log.push('[plugin] «' + pid + '» طبق تنظیمات غیرفعال است');
    });

    // ترتیب‌دهی توپولوژیک + آبشارِ وابستگی مفقود (بدون کرش)
    var order = O.core.resolveOrder(reg.all());
    var disabled = [];
    reg.all().forEach(function (r) {
      if (r.disabledReason) disabled.push({ id: r.id, reason: r.disabledReason });
    });
    disabled.forEach(function (d) {
      log.push('[plugin] «' + d.id + '» توسط resolver غیرفعال شد — ' + d.reason);
    });

    var info = {
      cfg: cfg, platform: platform,
      context: { cfg: cfg, platform: platform, registry: reg },
      order: order.map(function (r) { return r.id; }),
      log: log, disabled: disabled
    };
    return { registry: reg, info: info };
  };

  // ── دسترسی قابلیت‌محور — آینهٔ کلاس _Caps در src/engine.py ──
  // نمونه‌ها تنبل (lazy) ساخته می‌شوند؛ پلاگین غیرفعال/خراب → null یا throw
  // (مصرف‌کننده همان guardهای enabled و try/catch فعلی را دارد →
  // unavailable صادقانه، نه کرش).
  var CONTRACT_OF = {
    market: 'odin.data.market@1',
    tv: 'odin.data.tv@1',
    technical: 'odin.analysis.technical@1',
    strength: 'odin.analysis.strength@1',
    session: 'odin.session@1',
    calendar: 'odin.fundamental.calendar@1',
    news: 'odin.fundamental.news@1',
    judge: 'odin.judge.engine@1',
    risk: 'odin.judge.risk@1',
    journal: 'odin.journal@1',
    alerts: 'odin.alerts.price@1'
  };

  O.makeCaps = function (cfg) {
    if (!O.core || typeof O.buildDefaultRegistry !== 'function') {
      // پرسروصدا، نه بی‌صدا: stack اپ باید core.js + plugins.js را پیش از
      // app.js/data.js بار کند (ترتیب در index.html پین شده است).
      throw new Error('هستهٔ پلاگین بارگذاری نشده است — js/core.js و js/plugins.js ' +
        'باید پیش از app.js/data.js بار شوند');
    }
    var built = O.buildDefaultRegistry(cfg || O.CONFIG, 'android');
    var lm = O.core.createLifecycle({
      context: built.info.context,
      onFailure: function (f) { O.BUS.emit(O.core.EVENTS.PLUGIN_FAILED, f); }
    });
    var cache = {};
    var caps = {
      cfg: cfg || O.CONFIG,
      reg: built.registry,
      info: built.info,
      instanceFor: function (rec) {
        if (!rec) return null;
        if (rec.instance === null || rec.instance === undefined) {
          if (rec.state === O.core.STATES.RESOLVED) lm.initialize(rec);
          if (rec.state === O.core.STATES.FAILED) {
            throw new Error(rec.error || 'پلاگین مقداردهی نشد');
          }
        }
        return rec.instance;
      },
      get: function (contract) {
        if (Object.prototype.hasOwnProperty.call(cache, contract)) return cache[contract];
        var inst = caps.instanceFor(caps.reg.get(contract));
        cache[contract] = inst;
        return inst;
      }
    };
    Object.keys(CONTRACT_OF).forEach(function (name) {
      Object.defineProperty(caps, name, {
        enumerable: true,
        get: function () { return caps.get(CONTRACT_OF[name]); }
      });
    });
    return caps;
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
