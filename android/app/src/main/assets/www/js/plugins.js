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
 * ⚠️ فاز ۶b انجام شد: ۷ وتو + ۸ شاهدِ داور هم rule-plugin‌اند (veto-*×۷ +
 *   ev-*×۸ — id/ترتیب/binding دقیقاً آینهٔ پایتون؛ شش وتوی کلیددار به
 *   judge.veto.* با dot-path فاز ۷ bind شدند). judge-core حالا registry-aware
 *   است و قواعد را از registry به judgeAll تزریق می‌کند (fallback صادقانه:
 *   بدون registry → delegation سادهٔ قبلی).
 *
 * ⚠️ S2 (v0.26): سه استراتژی ورود هم ثبت‌اند (strategy-*×۳ با قرارداد
 *   odin.strategy@1 — آینهٔ src/plugins/strategies.py). هنوز مصرف‌کننده
 *   ندارند (چرخه/داور دست‌نخورده) — سوییچ دروازهٔ توافق در S3.
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

  function JudgeAdapter(context) {
    this._context = context || {};
    this._registry = this._context.registry || null;
    this._rulesCache = null;
  }
  // تنظیمات داور در JS از قبل در config.js با پیش‌فرض‌ها ادغام شده
  // (O.deepFill(O.CONFIG, settings) در buildCfg) — پس judgeConfig همان
  // بخشِ ادغام‌شده را برمی‌گرداند (همتای judge_config پایتون).
  JudgeAdapter.prototype.judgeConfig = function (cfg) {
    return (cfg && cfg.judge) || {};
  };
  JudgeAdapter.prototype.judgeAll = function (analyses, datasets, ctx) {
    var r = this._rules();
    if (r.veto === null && r.evidence === null && r.risk === null
      && r.strategies === null) {
      return O.judgeAll(analyses, datasets, ctx);          // delegation ساده
    }
    return O.judgeAll(analyses, datasets, ctx, r.veto, r.evidence, r.risk, r.strategies);
  };
  /* قواعد از registry (فاز ۶b — آینهٔ JudgePlugin._rules پایتون):
   * veto@1/evidence@1 با ترتیب قطعی (priority, order) + risk از get().
   * adapterها stateless‌اند → اگر نمونهٔ lifecycle ساخته نشده، مستقیم با
   * factory ساخته می‌شوند. فهرست‌ها *همان‌طور که هستند* رد می‌شوند (حتی
   * خالی) — coercion به null قواعد پیش‌فرض را بی‌صدا زنده می‌کرد
   * (همان اصلاحیهٔ فاز ۷ پایتون). cache: registry در عمر یک caps ثابت است. */
  JudgeAdapter.prototype._rules = function () {
    if (!this._registry) return { veto: null, evidence: null, risk: null, strategies: null };
    if (this._rulesCache === null) {
      var reg = this._registry;
      var ctx = this._context;
      function inst(rec) {
        return (rec.instance !== null && rec.instance !== undefined)
          ? rec.instance : rec.factory(ctx);
      }
      var veto = reg.providers('odin.judge.veto@1').map(function (rec) {
        var i = inst(rec);
        return i.rule.bind(i);
      });
      var evidence = reg.providers('odin.judge.evidence@1').map(function (rec) {
        var i = inst(rec);
        return i.rule.bind(i);
      });
      var riskRec = reg.get('odin.judge.risk@1');
      var risk = null;
      if (riskRec) {
        var ri = inst(riskRec);
        risk = ri.computeLevels.bind(ri);
      }
      /* S3 (v0.26): providerهای odin.strategy@1 — *نمونه‌های* adapter (نه
       * متدِ bound): دروازه به .evaluate(a, md, ctx) و .key (برای
       * placeholder صادقانهٔ خطا) نیاز دارد — آینهٔ JudgePlugin._rules
       * پایتون. فهرست خالی (همه خاموش) همان‌طور که هست رد می‌شود →
       * fail-closed صادقانه (تصمیم D3)، نه coercion به null. */
      var strategies = reg.providers('odin.strategy@1').map(function (rec) {
        return inst(rec);
      });
      this._rulesCache = { veto: veto, evidence: evidence, risk: risk, strategies: strategies };
    }
    return this._rulesCache;
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

  // ── adapterهای قواعد داور (فاز ۶b) — delegation خالص به judge.js ──
  // shape: odin.judge.veto@1 → rule(a, symCfg, md, ctx) → Veto|null
  function VetoRuleAdapter(vetoId, fnName) {
    this.vetoId = vetoId;
    this._fn = fnName;
  }
  VetoRuleAdapter.prototype.rule = function (a, symCfg, md, ctx) {
    return O[this._fn](a, symCfg, md, ctx);
  };

  // shape: odin.judge.evidence@1 → rule(a, ctx, direction) → Evidence
  // mode: 'full' = (a,ctx,d) · 'no-dir' = (a,ctx) · 'ctx-only' = (ctx)
  // (trend/fundamental direction را مصرف نمی‌کنند؛ session فقط ctx —
  // همان وعدهٔ §۲.۲ سند، آینهٔ EvidenceRuleAdapter پایتون)
  function EvidenceRuleAdapter(evidenceId, fnName, mode) {
    this.evidenceId = evidenceId;
    this._fn = fnName;
    this._mode = mode;
  }
  EvidenceRuleAdapter.prototype.rule = function (a, ctx, direction) {
    var fn = O[this._fn];
    if (this._mode === 'ctx-only') return fn(ctx);
    if (this._mode === 'no-dir') return fn(a, ctx);
    return fn(a, ctx, direction);
  };

  // ── adapter استراتژی (S2) — آینهٔ StrategyAdapter پایتون ──
  // shape: odin.strategy@1 → evaluate(a, md, ctx) → verdict
  // scfg در ساخت گرفته می‌شود (context.cfg.strategies[key]) — factory در هر
  // makeCaps با cfg جاری ساخته می‌شود، پس تغییرات config بین چرخه‌ها درست
  // دیده می‌شود (dict(...) پایتون = کپی سطحی).
  function StrategyAdapter(key, cfg) {
    this.key = key;
    var strategies = (cfg && cfg.strategies) || {};
    var sc = strategies[key];
    var scfg = {};
    if (sc && typeof sc === 'object') {
      for (var k in sc) {
        if (Object.prototype.hasOwnProperty.call(sc, k)) scfg[k] = sc[k];
      }
    }
    this._scfg = scfg;
  }
  StrategyAdapter.prototype.evaluate = function (a, md, ctx) {
    return O.strategyFor(this.key).evaluate(a, md, this._scfg, ctx);
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
      // فاز ۷ — بازبینی انجام شد: bind به judge.enabled امن است چون
      // ۱) guard مصرف‌کننده (S.cfg.judge.enabled) پیش از caps.judge چک می‌شود
      //    و ۲) ctx.jcfg مستقیماً S.cfg.judge است (پیش‌فرض‌ها در config.js
      //    ادغام شده‌اند — judgeConfig در چرخه صدا زده نمی‌شود).
      id: 'judge-core',
      provides: ['odin.judge.engine@1'],
      config: { section: 'judge', enabled_key: 'enabled', 'default': true },
      stage: 'judge', priority: 50,
      factory: function (context) { return new JudgeAdapter(context); }
    },
    {
      // فاز ۷: risk فقط درون judgeAll مصرف می‌شود (مسیر داور) → bind به
      // judge.enabled امن است؛ مصرف‌کنندهٔ مستقیم (UI/تست‌ها) O.computeLevels
      // را صدا می‌زند، نه پلاگین را.
      id: 'judge-risk',
      provides: ['odin.judge.risk@1'],
      config: { section: 'judge', enabled_key: 'enabled', 'default': true },
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

  // ── قواعد داور (فاز ۶b) — id/ترتیب/binding دقیقاً آینهٔ پایتون ──
  // (plugin-id, veto_id, نام تابع judge.js, کلیدِ veto یا null)
  var VETO_DEFS = [
    ['veto-data', 'DATA', 'vetoData', null],
    ['veto-weekend', 'WEEKEND', 'vetoWeekend', 'weekend'],
    ['veto-tf-conflict', 'TF_CONFLICT', 'vetoTfConflict', 'timeframe_conflict'],
    ['veto-range', 'RANGE', 'vetoRange', 'range_market'],
    ['veto-event', 'EVENT', 'vetoEvent', 'high_impact_event'],
    ['veto-vol-spike', 'VOL_SPIKE', 'vetoVolSpike', 'volatility_spike'],
    ['veto-breaking-news', 'BREAKING_NEWS', 'vetoBreakingNews', 'breaking_news']
  ];
  // (plugin-id, evidence_id, نام تابع، mode)
  var EV_DEFS = [
    ['ev-trend', 'TREND', 'evTrend', 'no-dir'],
    ['ev-level', 'LEVEL', 'evLevel', 'full'],
    ['ev-fundamental', 'FUNDAMENTAL', 'evFundamental', 'no-dir'],
    ['ev-momentum', 'MOMENTUM', 'evMomentum', 'full'],
    ['ev-strength', 'STRENGTH', 'evStrength', 'full'],
    ['ev-news', 'NEWS', 'evNews', 'full'],
    ['ev-tv', 'TV', 'evTradingView', 'full'],
    ['ev-session', 'SESSION', 'evSession', 'ctx-only']
  ];

  // ۷ وتو — priority ۱۰..۷۰ = ترتیب ارزیابی؛ شش کلیددار به judge.veto.*
  // bind می‌شوند (dot-path فاز ۷ — کلیدهای *موجود*؛ تنظیمات گوشی از راه
  // buildCfg همان‌ها را می‌سازد). guardهای درون بدنه هم باقی‌اند (مسیر
  // مستقیم بدون registry) — برابری دو مسیر در test_judge_switch پین شده.
  VETO_DEFS.forEach(function (d, i) {
    DEFS.push({
      id: d[0], provides: ['odin.judge.veto@1'],
      config: d[3] ? { section: 'judge', enabled_key: 'veto.' + d[3], 'default': true } : null,
      stage: 'judge', priority: 10 * (i + 1),
      factory: function () { return new VetoRuleAdapter(d[1], d[2]); }
    });
  });
  // ۸ شاهد — priority ۱۰..۸۰ = ترتیب جدول امتیاز (کلید config ندارند)
  EV_DEFS.forEach(function (d, i) {
    DEFS.push({
      id: d[0], provides: ['odin.judge.evidence@1'], config: null,
      stage: 'judge', priority: 10 * (i + 1),
      factory: function () { return new EvidenceRuleAdapter(d[1], d[2], d[3]); }
    });
  });

  // ── استراتژی‌های ورود (S2) — id/ترتیب/binding آینهٔ src/plugins/strategies.py ──
  // (plugin-id, strategy_key) — priority ۱۰..۳۰ = ترتیب ارزیابی قطعی؛
  // اتصال به strategies.<key>.enabled (dot-path فاز ۷). مصرف‌کننده در S3
  // وصل می‌شود — تا آن زمان این ثبت‌ها بی‌اثرند (چرخه دست‌نخورده).
  var STRATEGY_DEFS = [
    ['strategy-trend-pullback', 'trend_pullback'],
    ['strategy-london-breakout', 'london_breakout'],
    ['strategy-carry', 'carry']
  ];
  STRATEGY_DEFS.forEach(function (d, i) {
    DEFS.push({
      id: d[0], provides: ['odin.strategy@1'],
      config: { section: 'strategies', enabled_key: d[1] + '.enabled', 'default': true },
      stage: 'judge', priority: 10 * (i + 1),
      factory: function (context) {
        return new StrategyAdapter(d[1], (context && typeof context === 'object') ? context.cfg : null);
      }
    });
  });

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
