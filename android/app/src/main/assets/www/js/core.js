/* هستهٔ معماری پلاگین ODIN — فاز ۵: آینهٔ کاملِ src/core/ (پایتون).
 *
 * یک فایل vanilla و خودبسنده (بدون هیچ وابستگی به ماژول‌های دیگر اپ) با
 * «همان نام‌ها / همان معنا»ها:
 *
 *   O.core.createRegistry()      ← PluginRegistry (register/get/providers/
 *                                   byStage/all/enable/disable/status)
 *   O.core.resolveOrder(records) ← resolver.resolve (Kahn + آبشار + حلقه پرسروصدا)
 *   O.core.createLifecycle()     ← LifecycleManager (ماشین حالت + قرنطینه)
 *   O.core.createBus()           ← EventBus (on/emit/listenerCount — همگام،
 *                                   هرگز استثنا بیرون نمی‌دهد)
 *   O.core.createPipeline()      ← PipelineRunner (add/run با StageResult)
 *   O.core.manifest()/validateManifest()  ← PluginManifest + validate
 *   O.core.pluginEnabled/pluginConfig/applyConfigState ← config_bridge
 *   O.core.STAGES/SCHEDULER_STAGES/EVENTS/STATES/CONTRACTS ← ثابت‌های هسته
 *
 * قراردادها در JS نوع ندارند؛ معادلِ Protocolهای @runtime_checkable،
 * «فهرست نام متدها» به ازای هر قرارداد + اعتبارسنج سبکِ validateProvider
 * است (shape مستند — parity از راه تست‌ها: tests/js/smoke_core.js فهرست‌ها
 * را مستقیم از سورس پایتون استخراج و مقایسه می‌کند).
 *
 * قرارداد نام‌گذاری (همان عرف موجودِ اپ):
 *   • متدها/توابع JS = camelCase (مثل O.marketStatus در برابر market_status)
 *   • کلیدهای *دادهٔ* بین‌موتوری = snake_case پایتون (statusDict خروجیِ
 *     disabled_reason می‌دهد؛ رکورد خطا plugin_id دارد) تا payloadها در دو
 *     زبان یکی بمانند.
 *
 * ⚠️ CORE_VERSION عمداً در JS آینه نشد: نگهبانِ «شمارهٔ نسخهٔ هاردکد»
 *   (بررسی ۷ در smoke_theme_parity.js) هر semver نقل‌قولی‌شده در www/ را
 *   که APP_VERSION نباشد رد می‌کند — نسخهٔ اطلاعاتیِ هسته فقط در پایتون
 *   می‌ماند (src/core/__init__.py::CORE_VERSION).
 *
 * وضعیت در فاز ۵: **inert** — این فایل فقط O.core را تعریف می‌کند و هیچ
 * مسیر اجرای اپ آن را صدا نمی‌زند (مصرف‌کننده‌ها در فاز ۶ سوییچ می‌شوند).
 * تنها تغییرِ index.html در فاز ۵: بارگذاری همین فایل *پیش از همه* — چون
 * ثبتِ پلاگین‌ها (فاز ۶) به بودنِ O.core در زمان اجرای ماژول‌ها نیاز دارد.
 *
 * سبک: ES5 خالص (var/function) — مثل بقیهٔ js/ اپ؛ برای WebViewهای قدیمی
 * امن است (نگهبانِ ES5 هم در smoke_core.js هست).
 */
(function (O) {
  'use strict';

  var core = {};

  // ════════════════════════════════════════════════════════════
  //  قراردادها — آینهٔ کلیدهای src/core/contracts.py::CONTRACTS
  //  مقدار هر کلید در JS: فهرست متدهای لازم (اعتبارسنج ساختاری سبک).
  //  نام متدها با عرف JS است؛ shape پایتون در contracts.py مستند است.
  //  (veto/evidence علاوه بر rule یک شناسه هم دارند: veto_id/evidence_id)
  // ════════════════════════════════════════════════════════════
  var CONTRACTS = {
    'odin.data.market@1': ['connect', 'disconnect', 'fetch'],
    'odin.data.tv@1': ['fetchTvSnapshot'],
    'odin.analysis.technical@1': ['analyzeSymbol'],
    'odin.analysis.strength@1': ['currencyStrength'],
    'odin.session@1': ['marketStatus'],
    'odin.fundamental.calendar@1': ['fetchCalendar', 'upcomingEvents', 'vetoForSymbol'],
    'odin.fundamental.news@1': ['fetchNews'],
    'odin.judge.engine@1': ['judgeConfig', 'judgeAll'],
    'odin.judge.veto@1': ['rule'],
    'odin.judge.evidence@1': ['rule'],
    'odin.judge.risk@1': ['computeLevels'],
    'odin.journal@1': ['open', 'resolveOpenSignals', 'computeStats'],
    'odin.notify@1': ['send'],
    'odin.alerts.price@1': ['checkAlerts'],
    'odin.report@1': ['render']
  };

  var CONTRACT_ID_RE = /^[a-z][a-z0-9]*(?:\.[a-z0-9]+)+@\d+$/;
  var PLUGIN_ID_RE = /^[a-z0-9][a-z0-9._-]*$/;
  var VERSION_RE = /^\d+\.\d+\.\d+$/;
  var VALID_PLATFORMS = ['desktop', 'android'];

  function hasOwn(obj, key) {
    return !!obj && Object.prototype.hasOwnProperty.call(obj, key);
  }

  core.CONTRACTS = CONTRACTS;

  core.isWellformedContractId = function (cid) {
    return typeof cid === 'string' && CONTRACT_ID_RE.test(cid);
  };

  core.isValidContractId = function (cid) {
    return core.isWellformedContractId(cid) && hasOwn(CONTRACTS, cid);
  };

  /* اعتبارسنج ساختاری — معادل JS برای isinstance(x, Protocol) پایتون:
   * همهٔ متدهای قرارداد باید function باشند. */
  core.validateProvider = function (cid, instance) {
    var methods = CONTRACTS[cid];
    if (!methods || !instance) return false;
    for (var i = 0; i < methods.length; i++) {
      if (typeof instance[methods[i]] !== 'function') return false;
    }
    return true;
  };

  // ════════════════════════════════════════════════════════════
  //  خطاها — نام‌ها همان پایتون؛ پیام‌ها فارسی (فلسفهٔ پروژه:
  //  باگِ طراحی پرسروصدا، شرایط محیطی بی‌صدا-ولی-صادقانه)
  //  نام‌ها: InvalidManifestError | DuplicatePluginError |
  //          CircularDependencyError | InvalidTransitionError | ValueError
  // ════════════════════════════════════════════════════════════
  function coreError(name, message) {
    var e = new Error(message);
    e.name = name;
    e.isCoreError = true;
    return e;
  }
  core.coreError = coreError;

  // ════════════════════════════════════════════════════════════
  //  رویدادها — مقادیر بایت‌به‌بایت همان src/core/bus.py::Events
  // ════════════════════════════════════════════════════════════
  var EVENTS = {
    // چرخهٔ تحلیل
    CYCLE_START: 'cycle.start',
    MARKET_COLLECTED: 'market.collected',
    JOURNAL_RESOLVED: 'journal.resolved',
    FUNDAMENTAL_COLLECTED: 'fundamental.collected',
    VETOES_COMPUTED: 'vetoes.computed',
    JUDGE_DONE: 'judge.done',
    SIGNAL_CREATED: 'signal.created',
    SIGNAL_SENT: 'signal.sent',
    ALERTS_FIRED: 'alerts.fired',
    REPORT_RENDERED: 'report.rendered',
    TELEGRAM_SENT: 'telegram.sent',
    CYCLE_END: 'cycle.end',
    // زمان‌بند (BotLoop / svcTick)
    NEWS_BREAKING: 'news.breaking',
    BRIEFING_DUE: 'briefing.due',
    JOURNAL_DUE: 'journal.due',
    // خودِ سیستم پلاگین
    PLUGIN_REGISTERED: 'plugin.registered',
    PLUGIN_FAILED: 'plugin.failed',
    PLUGIN_DISABLED: 'plugin.disabled',
    // مراحل pipeline
    STAGE_START: 'stage.start',
    STAGE_DONE: 'stage.done'
  };
  // ترتیب = همان Events.ALL پایتون
  var EVENTS_ALL = [
    EVENTS.CYCLE_START, EVENTS.MARKET_COLLECTED, EVENTS.JOURNAL_RESOLVED,
    EVENTS.FUNDAMENTAL_COLLECTED, EVENTS.VETOES_COMPUTED, EVENTS.JUDGE_DONE,
    EVENTS.SIGNAL_CREATED, EVENTS.SIGNAL_SENT, EVENTS.ALERTS_FIRED,
    EVENTS.REPORT_RENDERED, EVENTS.TELEGRAM_SENT, EVENTS.CYCLE_END,
    EVENTS.NEWS_BREAKING, EVENTS.BRIEFING_DUE, EVENTS.JOURNAL_DUE,
    EVENTS.PLUGIN_REGISTERED, EVENTS.PLUGIN_FAILED, EVENTS.PLUGIN_DISABLED,
    EVENTS.STAGE_START, EVENTS.STAGE_DONE
  ];
  core.EVENTS = EVENTS;
  core.EVENTS_ALL = EVENTS_ALL;

  // ════════════════════════════════════════════════════════════
  //  مراحل — نام‌ها بایت‌به‌بایت همان src/core/pipeline.py
  //  (ترتیب = ترتیب مو‌به‌موی run_cycle/cycleCore فعلی)
  // ════════════════════════════════════════════════════════════
  var STAGES = [
    'collect_market',       // دادهٔ کندل + تحلیل + قدرت ارز + تاییدیهٔ TV
    'journal_pre',          // بستن سیگنال‌های باز + آمار — عمداً قبل از بررسی داده
    'collect_fundamental',  // تقویم اقتصادی + اخبار — بعد از early-exit
    'compute_vetoes',       // وتوهای نماد-محور تقویم
    'judge',                // داور: ۷ وتو + ۸ شاهد + ریسک
    'render',               // رندر گزارش‌ها
    'dispatch_signals',     // ضداسپم → ارسال → ثبت ژورنال
    'price_alerts',         // هشدارهای قیمت
    'chart_cache',          // کش نمودار
    'dashboard',            // دادهٔ ساختاریافتهٔ داشبورد
    'archive_notify'        // آرشیو گزارش + اعلان نهایی
  ];
  var SCHEDULER_STAGES = ['event_alerts', 'briefing', 'journal_report'];
  core.STAGES = STAGES;
  core.SCHEDULER_STAGES = SCHEDULER_STAGES;

  // ════════════════════════════════════════════════════════════
  //  ماشین حالت — همان src/core/lifecycle.py
  // ════════════════════════════════════════════════════════════
  var STATES = {
    REGISTERED: 'registered',
    RESOLVED: 'resolved',
    INITIALIZED: 'initialized',
    STARTED: 'started',
    STOPPED: 'stopped',
    DISPOSED: 'disposed',
    FAILED: 'failed'
  };
  // گذارهای مجاز (آینهٔ _ALLOWED) — FAILED قرنطینه است: بازگشت خودکار ندارد
  var ALLOWED = {
    registered: ['resolved', 'failed'],
    resolved: ['initialized', 'failed'],
    initialized: ['started', 'stopped', 'failed'],
    started: ['stopped', 'failed'],
    stopped: ['started', 'disposed', 'failed'],
    disposed: [],
    failed: []
  };
  core.STATES = STATES;
  core.ALLOWED_TRANSITIONS = ALLOWED;

  // ════════════════════════════════════════════════════════════
  //  سازگاری truthiness — bool() پایتون در برابر Boolean() جاوااسکریپت:
  //  فهرست/dict خالی در پایتون False است ولی در JS truthy. کلیدهای config
  //  در عمل bool/عدد/رشته‌اند؛ این helper پاریتی را در حالت‌های لبه هم
  //  صادق نگه می‌دارد. (NaN: در هر دو زبان truthy — v !== 0 برای NaN درست است.)
  // ════════════════════════════════════════════════════════════
  function pyBool(v) {
    if (v === null || v === undefined) return false;
    if (typeof v === 'boolean') return v;
    if (typeof v === 'number') return v !== 0;
    if (typeof v === 'string') return v.length > 0;
    if (Object.prototype.toString.call(v) === '[object Array]') return v.length > 0;
    if (typeof v === 'object') return Object.keys(v).length > 0;
    return true;   // تابع و بقیهٔ انواع — مثل پایتون truthy
  }
  core.pyBool = pyBool;

  // ════════════════════════════════════════════════════════════
  //  مانیفست — آینهٔ src/core/manifest.py
  //  مانیفست در JS یک object ساده با همان فیلدهاست:
  //    id, version, provides, requires, config, platforms, stage,
  //    priority, optional, factory
  //  core.manifest(obj, knownStages) = ساخت + نرمال‌سازی (پیش‌فرض‌های
  //  dataclass پایتون) + اعتبارسنجی؛ در صورت مشکل InvalidManifestError.
  // ════════════════════════════════════════════════════════════
  core.manifest = function (obj, knownStages) {
    obj = obj || {};
    var m = {
      id: obj.id,
      version: obj.version,
      provides: obj.provides ? obj.provides.slice() : [],
      requires: obj.requires ? obj.requires.slice() : [],
      config: (obj.config !== undefined && obj.config !== null) ? obj.config : null,
      platforms: obj.platforms ? obj.platforms.slice() : VALID_PLATFORMS.slice(),
      stage: (obj.stage !== undefined && obj.stage !== null) ? obj.stage : '',
      priority: (typeof obj.priority === 'number') ? obj.priority : 100,
      optional: (typeof obj.optional === 'boolean') ? obj.optional : true,
      factory: (typeof obj.factory === 'function') ? obj.factory : null
    };
    return core.validateManifest(m, knownStages);
  };

  core.validateManifest = function (m, knownStages) {
    // ترتیب و متن بررسی‌ها = همان manifest.py::validate (پیام‌های فارسی)
    if (!m.id || !PLUGIN_ID_RE.test(String(m.id))) {
      throw coreError('InvalidManifestError',
        'شناسهٔ پلاگین نامعتبر: ' + JSON.stringify(m.id) + ' — باید kebab-case باشد ' +
        '(حروف کوچک/عدد/خط-تیره/نقطه/زیرخط، بدون حرف اضافه در ابتدا)');
    }
    if (!VERSION_RE.test(String(m.version || ''))) {
      throw coreError('InvalidManifestError',
        'نسخهٔ پلاگین «' + m.id + '» باید semver ساده باشد (مثل 1.0.0)، ' +
        'نه ' + JSON.stringify(m.version));
    }
    if (!m.provides || !m.provides.length) {
      throw coreError('InvalidManifestError',
        'پلاگین «' + m.id + '» هیچ قراردادی فراهم نمی‌کند — provides خالی است');
    }
    var i, cid;
    for (i = 0; i < m.provides.length; i++) {
      cid = m.provides[i];
      if (!core.isWellformedContractId(cid)) {
        throw coreError('InvalidManifestError',
          'شناسهٔ قرارداد نامعتبر در provides پلاگین «' + m.id + '»: ' +
          JSON.stringify(cid) + ' — شکل معتبر: name.domain@1');
      }
      if (!core.isValidContractId(cid)) {
        throw coreError('InvalidManifestError',
          'قرارداد ناشناخته «' + cid + '» در پلاگین «' + m.id + '» — هسته فقط ' +
          'قراردادهای ثبت‌شده در O.core.CONTRACTS را می‌شناسد ' +
          '(قرارداد جدید = تصمیم معماری، نه افزودهٔ سرخود)');
      }
    }
    for (i = 0; i < m.requires.length; i++) {
      cid = m.requires[i];
      if (!core.isWellformedContractId(cid)) {
        throw coreError('InvalidManifestError',
          'شناسهٔ قرارداد نامعتبر در requires پلاگین «' + m.id + '»: ' + JSON.stringify(cid));
      }
      if (!core.isValidContractId(cid)) {
        throw coreError('InvalidManifestError',
          'قرارداد ناشناخته «' + cid + '» در requires پلاگین «' + m.id + '»');
      }
    }
    // هم‌پوشانی provides/requires
    for (i = 0; i < m.provides.length; i++) {
      if (m.requires.indexOf(m.provides[i]) >= 0) {
        var overlap = m.provides.filter(function (c) {
          return m.requires.indexOf(c) >= 0;
        }).sort();
        throw coreError('InvalidManifestError',
          'پلاگین «' + m.id + '» نمی‌تواند به قرارداد خودش وابسته باشد: ' +
          JSON.stringify(overlap));
      }
    }
    if (m.config !== null && m.config !== undefined) {
      if (typeof m.config !== 'object' || Object.prototype.toString.call(m.config) === '[object Array]') {
        throw coreError('InvalidManifestError',
          'config پلاگین «' + m.id + '» باید dict باشد');
      }
      var keys = ['section', 'enabled_key'];
      for (i = 0; i < keys.length; i++) {
        if (!hasOwn(m.config, keys[i])) {
          throw coreError('InvalidManifestError',
            'config پلاگین «' + m.id + '» کلید «' + keys[i] + '» ندارد');
        }
      }
      var dflt = hasOwn(m.config, 'default') ? m.config['default'] : true;
      if (typeof dflt !== 'boolean') {
        throw coreError('InvalidManifestError',
          'config.default پلاگین «' + m.id + '» باید bool باشد');
      }
    }
    for (i = 0; i < m.platforms.length; i++) {
      if (VALID_PLATFORMS.indexOf(m.platforms[i]) < 0) {
        throw coreError('InvalidManifestError',
          'پلتفرم نامعتبر «' + m.platforms[i] + '» در پلاگین «' + m.id + '» ' +
          '(مجاز: ' + VALID_PLATFORMS.join(' | ') + ')');
      }
    }
    if (!m.platforms.length) {
      throw coreError('InvalidManifestError', 'platforms پلاگین «' + m.id + '» خالی است');
    }
    if (!m.stage) {
      throw coreError('InvalidManifestError', 'stage پلاگین «' + m.id + '» خالی است');
    }
    if (knownStages && knownStages.indexOf(m.stage) < 0) {
      throw coreError('InvalidManifestError',
        'مرحلهٔ ناشناخته «' + m.stage + '» برای پلاگین «' + m.id + '» — ' +
        'مراحل معتبر: ' + knownStages.join(', '));
    }
    if (typeof m.priority !== 'number' || Math.floor(m.priority) !== m.priority) {
      throw coreError('InvalidManifestError',
        'priority پلاگین «' + m.id + '» باید int باشد، نه ' + typeof m.priority);
    }
    return m;
  };

  // ════════════════════════════════════════════════════════════
  //  رکورد و رجیستری — آینهٔ src/core/registry.py
  //  record: {id, manifest, factory, enabled, state, instance, error,
  //           order, disabledReason} + statusDict() با کلیدهای پایتون
  // ════════════════════════════════════════════════════════════
  function makeRecord(manifest, factory, order) {
    return {
      id: manifest.id,
      manifest: manifest,
      factory: factory || manifest.factory || null,
      enabled: true,
      state: STATES.REGISTERED,
      instance: null,
      error: '',
      order: order,
      disabledReason: ''
    };
  }

  core.createRegistry = function (opts) {
    opts = opts || {};
    var knownStages = opts.knownStages || null;
    var byId = {};
    var list = [];          // ترتیب ثبت — order قطعی
    var counter = 0;

    // فعال = enabled (config/کاربر) و disable نشده (resolver) و خراب نیست
    function isActive(rec) {
      return rec.enabled && !rec.disabledReason && rec.state !== STATES.FAILED;
    }
    function statusDict(rec) {
      return {
        id: rec.id, version: rec.manifest.version,
        provides: rec.manifest.provides.slice(),
        enabled: rec.enabled, state: rec.state,
        disabled_reason: rec.disabledReason, error: rec.error
      };
    }
    function byPriorityOrder(a, b) {
      return (a.manifest.priority - b.manifest.priority) || (a.order - b.order);
    }

    var reg = {
      knownStages: knownStages,
      isActive: isActive,

      register: function (manifest, factory) {
        var m = core.manifest(manifest, knownStages);   // نرمال‌سازی + اعتبارسنجی
        if (hasOwn(byId, m.id)) {
          throw coreError('DuplicatePluginError',
            'پلاگین «' + m.id + '» قبلاً ثبت شده است — id باید یکتا باشد');
        }
        var rec = makeRecord(m, factory || null, counter++);
        byId[m.id] = rec;
        list.push(rec);
        return rec;
      },

      byId: function (pluginId) {
        return hasOwn(byId, pluginId) ? byId[pluginId] : null;
      },

      providers: function (contractId, onlyActive) {
        if (onlyActive === undefined) onlyActive = true;
        var out = [];
        for (var i = 0; i < list.length; i++) {
          var r = list[i];
          if (r.manifest.provides.indexOf(contractId) >= 0 && (isActive(r) || !onlyActive)) {
            out.push(r);
          }
        }
        out.sort(byPriorityOrder);   // ترتیب قطعی: (priority، سپس ثبت)
        return out;
      },

      get: function (contractId) {
        var ps = reg.providers(contractId);
        return ps.length ? ps[0] : null;
      },

      byStage: function (stage, onlyActive) {
        if (onlyActive === undefined) onlyActive = true;
        var out = [];
        for (var i = 0; i < list.length; i++) {
          var r = list[i];
          if (r.manifest.stage === stage && (isActive(r) || !onlyActive)) out.push(r);
        }
        out.sort(byPriorityOrder);
        return out;
      },

      all: function (onlyActive) {
        var out = list.slice();
        if (onlyActive) out = out.filter(isActive);
        out.sort(function (a, b) { return a.order - b.order; });
        return out;
      },

      enable: function (pluginId) {
        var rec = reg.byId(pluginId);
        if (rec === null) return false;
        rec.enabled = true;
        return true;
      },

      disable: function (pluginId) {
        var rec = reg.byId(pluginId);
        if (rec === null) return false;
        rec.enabled = false;
        return true;
      },

      status: function () {
        return reg.all().map(statusDict);
      }
    };
    return reg;
  };

  // ════════════════════════════════════════════════════════════
  //  حل‌کنندهٔ وابستگی — آینهٔ src/core/resolver.py::resolve
  //  ۱) آبشارِ وابستگی مفقود (بدون استثنا — دلیل فارسی روی رکورد)
  //  ۲) Kahn با صف مرتب (priority, order, id) → خروجی کاملاً قطعی
  //  ۳) حلقه → CircularDependencyError پرسروصدا با مسیر کامل
  // ════════════════════════════════════════════════════════════
  core.resolveOrder = function (records) {
    var pool = {};          // id → record (فقط enabled و بدون disable قبلی)
    var poolIds = [];
    var i, j, cid, pid;

    for (i = 0; i < records.length; i++) {
      var r0 = records[i];
      if (r0.enabled && !r0.disabledReason) {
        pool[r0.id] = r0;
        poolIds.push(r0.id);
      }
    }

    // نگاشت قرارداد → فراهم‌کننده‌های فعال (چند فراهم‌کننده مشروع است)
    var providers = {};
    for (i = 0; i < poolIds.length; i++) {
      var prov = pool[poolIds[i]].manifest.provides;
      for (j = 0; j < prov.length; j++) {
        if (!providers[prov[j]]) providers[prov[j]] = [];
        providers[prov[j]].push(poolIds[i]);
      }
    }

    // ۱) حذف تدریجیِ وابستگی‌های مفقود (waterfall) — چون افتادن A
    //    می‌تواند وابستگی B را هم مفقود کند
    var changed = true;
    while (changed) {
      changed = false;
      var snapshot = poolIds.slice();
      for (i = 0; i < snapshot.length; i++) {
        var rec = pool[snapshot[i]];
        if (!rec) continue;
        var missing = [];
        var reqs = rec.manifest.requires;
        for (j = 0; j < reqs.length; j++) {
          cid = reqs[j];
          if (!providers[cid] || !providers[cid].length) missing.push(cid);
        }
        if (missing.length) {
          delete pool[rec.id];
          poolIds.splice(poolIds.indexOf(rec.id), 1);
          rec.disabledReason = 'وابستگی فراهم نشد: ' + missing.join(', ') +
            ' — پلاگین غیرفعال می‌ماند تا قابلیتِ فراهم‌کننده فعال شود ' +
            '(unavailable، نه کرش)';
          var gives = rec.manifest.provides;
          for (j = 0; j < gives.length; j++) {
            var arr = providers[gives[j]];
            if (arr) {
              var at = arr.indexOf(rec.id);
              if (at >= 0) arr.splice(at, 1);
            }
          }
          changed = true;
        }
      }
    }

    // ۲) گراف وابستگی بین بازماندگان: A → B یعنی B باید قبل از A بیاید
    var deps = {};
    for (i = 0; i < poolIds.length; i++) {
      pid = poolIds[i];
      deps[pid] = {};
      var rq = pool[pid].manifest.requires;
      for (j = 0; j < rq.length; j++) {
        var providersOf = providers[rq[j]] || [];
        for (var k = 0; k < providersOf.length; k++) {
          if (providersOf[k] !== pid) deps[pid][providersOf[k]] = true;
        }
      }
    }

    // ۳) Kahn با صف مرتب (priority, order, id)
    function cmpIds(a, b) {
      var ra = pool[a], rb = pool[b];
      return (ra.manifest.priority - rb.manifest.priority)
        || (ra.order - rb.order)
        || (a < b ? -1 : (a > b ? 1 : 0));
    }
    var indeg = {};
    var ready = [];
    for (i = 0; i < poolIds.length; i++) {
      pid = poolIds[i];
      indeg[pid] = Object.keys(deps[pid]).length;
      if (indeg[pid] === 0) ready.push(pid);
    }
    ready.sort(cmpIds);
    var out = [];
    while (ready.length) {
      pid = ready.shift();
      out.push(pool[pid]);
      for (i = 0; i < poolIds.length; i++) {
        var other = poolIds[i];
        if (hasOwn(deps[other], pid)) {
          delete deps[other][pid];
          indeg[other] -= 1;
          if (indeg[other] === 0) ready.push(other);
        }
      }
      ready.sort(cmpIds);
    }

    // ۴) باقی‌مانده = حلقه → پرسروصدا با مسیر
    if (out.length !== poolIds.length) {
      var outIds = {};
      for (i = 0; i < out.length; i++) outIds[out[i].id] = true;
      var stuck = poolIds.filter(function (p) { return !outIds[p]; });
      stuck.sort(cmpIds);
      var path = findCycle(stuck, deps);
      throw coreError('CircularDependencyError',
        'حلقهٔ وابستگی بین پلاگین‌ها: ' + path.join(' → ') +
        ' — مانیفست‌ها را اصلاح کنید (requires نباید حلقه بسازد)');
    }

    for (i = 0; i < out.length; i++) {
      if (out[i].state === STATES.REGISTERED) out[i].state = STATES.RESOLVED;
    }
    return out;
  };

  // یک حلقهٔ واقعی از میان گره‌های گیرکرده (برای پیام خطا) — آینهٔ _find_cycle
  function findCycle(stuck, deps) {
    var stuckSet = {};
    stuck.forEach(function (s) { stuckSet[s] = true; });
    var seen = {};
    var stack = [];

    function dfs(node) {
      var at = stack.indexOf(node);
      if (at >= 0) return stack.slice(at).concat([node]);
      if (seen[node]) return null;
      seen[node] = true;
      stack.push(node);
      var nxts = Object.keys(deps[node] || {}).sort();
      for (var i = 0; i < nxts.length; i++) {
        if (stuckSet[nxts[i]]) {
          var found = dfs(nxts[i]);
          if (found) return found;
        }
      }
      stack.pop();
      return null;
    }

    for (var n = 0; n < stuck.length; n++) {
      var cycle = dfs(stuck[n]);
      if (cycle) return cycle;
    }
    return stuck.concat(['...']);
  }

  // ════════════════════════════════════════════════════════════
  //  پل پیکربندی — آینهٔ src/core/config_bridge.py
  //  ترتیب اولویت: plugins[id].enabled ← section[enabled_key] ←
  //                 config.default ← true
  // ════════════════════════════════════════════════════════════
  core.pluginEnabled = function (cfg, manifest) {
    cfg = cfg || {};

    // ۱) override صریح در بخش plugins
    var plugins = cfg.plugins || {};
    var over = hasOwn(plugins, manifest.id) ? plugins[manifest.id] : null;
    if (over && typeof over === 'object' && hasOwn(over, 'enabled')) {
      return pyBool(over.enabled);
    }

    // ۲) کلید فیچری موجود
    var c = manifest.config;
    if (c && typeof c === 'object' && pyBool(c.section)) {
      var section = hasOwn(cfg, c.section) ? cfg[c.section] : null;
      var key = hasOwn(c, 'enabled_key') ? c.enabled_key : 'enabled';
      if (section && typeof section === 'object' && hasOwn(section, key)) {
        return pyBool(section[key]);
      }
      // ۳) پیش‌فرض مانیفست
      return pyBool(hasOwn(c, 'default') ? c['default'] : true);
    }

    // ۴) بدون اتصال config → فعال
    return true;
  };

  function isPlainObject(v) {
    return !!v && typeof v === 'object'
      && Object.prototype.toString.call(v) !== '[object Array]';
  }

  // ادغام عمیق — همان معنای _deep_merge (آرایه dict نیست → جایگزین می‌شود)
  function deepMerge(base, over) {
    var keys = Object.keys(over || {});
    for (var i = 0; i < keys.length; i++) {
      var v = over[keys[i]];
      if (isPlainObject(v) && isPlainObject(base[keys[i]])) {
        deepMerge(base[keys[i]], v);
      } else {
        base[keys[i]] = v;
      }
    }
    return base;
  }

  core.pluginConfig = function (cfg, manifest) {
    cfg = cfg || {};
    var c = manifest.config || {};
    var section = pyBool(c.section) && hasOwn(cfg, c.section) ? cfg[c.section] : null;
    var base = isPlainObject(section) ? deepMerge({}, section) : {};
    var entry = hasOwn(cfg.plugins || {}, manifest.id) ? cfg.plugins[manifest.id] : null;
    var over = (entry && entry.config) ? entry.config : {};
    if (isPlainObject(over)) base = deepMerge(base, over);
    return base;
  };

  core.applyConfigState = function (registry, cfg) {
    var out = {};
    var all = registry.all();
    for (var i = 0; i < all.length; i++) {
      var on = core.pluginEnabled(cfg, all[i].manifest);
      if (on) registry.enable(all[i].id); else registry.disable(all[i].id);
      out[all[i].id] = on;
    }
    return out;
  };

  // ════════════════════════════════════════════════════════════
  //  Lifecycle — آینهٔ src/core/lifecycle.py
  //  قرنطینه: خطای پلاگین → FAILED + رکورد PluginFailure + ادامهٔ بقیه؛
  //  گذار نامعتبر = باگ چارچوب → InvalidTransitionError پرسروصدا.
  // ════════════════════════════════════════════════════════════
  core.makeFailure = function (pluginId, phase, error) {
    return {
      plugin_id: pluginId,
      phase: phase,
      error: (error && error.message !== undefined) ? String(error.message) : String(error),
      at: new Date().toISOString()
    };
  };

  core.failureFaMessage = function (f) {
    return '[!] پلاگین «' + f.plugin_id + '» در ' + f.phase +
      ' خطا داد و غیرفعال شد: ' + String(f.error).slice(0, 120);
  };

  core.createLifecycle = function (opts) {
    opts = opts || {};
    var context = (opts.context !== undefined) ? opts.context : null;
    var onFailure = (typeof opts.onFailure === 'function') ? opts.onFailure : null;

    var lm = { failures: [], context: context };

    function transition(rec, to) {
      var allowed = ALLOWED[rec.state] || [];
      if (allowed.indexOf(to) < 0) {
        throw coreError('InvalidTransitionError',
          'گذار ' + rec.state + ' → ' + to + ' برای پلاگین «' +
          rec.manifest.id + '» مجاز نیست');
      }
      rec.state = to;
    }

    function quarantine(rec, phase, exc) {
      var f = core.makeFailure(rec.manifest.id, phase, exc);
      rec.state = STATES.FAILED;
      rec.error = phase + ': ' + f.error;
      lm.failures.push(f);
      if (onFailure !== null) {
        try { onFailure(f); } catch (ignored) { /* گزارشگر خطا هرگز چرخه را نمی‌اندازد */ }
      }
      return f;
    }

    function hookOf(instance, name) {
      if (instance && typeof instance[name] === 'function') return instance[name];
      return null;
    }

    lm.initialize = function (rec) {
      try {
        if (rec.instance === null || rec.instance === undefined) {
          if (rec.factory === null || rec.factory === undefined) {
            throw new Error('factory تعریف نشده — پلاگین قابل ساخت نیست');
          }
          rec.instance = (context !== null && context !== undefined)
            ? rec.factory(context) : rec.factory();
        }
        var hook = hookOf(rec.instance, 'initialize');
        if (hook !== null) hook.call(rec.instance);
        transition(rec, STATES.INITIALIZED);
        return null;
      } catch (e) {
        if (e && e.name === 'InvalidTransitionError') throw e;   // باگ چارچوب — پرسروصدا
        return quarantine(rec, 'initialize', e);                 // خطای پلاگین — قرنطینه
      }
    };

    lm.start = function (rec) {
      try {
        var hook = hookOf(rec.instance, 'start');
        if (hook !== null) hook.call(rec.instance);
        transition(rec, STATES.STARTED);
        return null;
      } catch (e) {
        if (e && e.name === 'InvalidTransitionError') throw e;
        return quarantine(rec, 'start', e);
      }
    };

    lm.stop = function (rec) {
      try {
        var hook = hookOf(rec.instance, 'stop');
        if (hook !== null) hook.call(rec.instance);
        transition(rec, STATES.STOPPED);
        return null;
      } catch (e) {
        if (e && e.name === 'InvalidTransitionError') throw e;
        return quarantine(rec, 'stop', e);
      }
    };

    lm.dispose = function (rec) {
      try {
        var hook = hookOf(rec.instance, 'dispose');
        if (hook !== null) hook.call(rec.instance);
        transition(rec, STATES.DISPOSED);
        rec.instance = null;
        return null;
      } catch (e) {
        if (e && e.name === 'InvalidTransitionError') throw e;
        return quarantine(rec, 'dispose', e);
      }
    };

    // دسته‌جمعی (به ترتیب ورودی) — هر رکورد مستقل؛ پلاگین خراب بقیه را
    // نمی‌اندازد (Failure Isolation)
    lm.initializeAll = function (records, start) {
      var i;
      for (i = 0; i < records.length; i++) {
        if (records[i].state === STATES.RESOLVED) lm.initialize(records[i]);
      }
      if (start) {
        for (i = 0; i < records.length; i++) {
          if (records[i].state === STATES.INITIALIZED) lm.start(records[i]);
        }
      }
      return lm.failures.slice();
    };

    return lm;
  };

  // ════════════════════════════════════════════════════════════
  //  Event Bus — آینهٔ src/core/bus.py
  //  همگام · ترتیب ثبت · ایزولاسیون کامل (emit هرگز استثنا نمی‌دهد؛
  //  خطاها به‌صورت فهرست [listener, message] برگردانده می‌شوند)
  // ════════════════════════════════════════════════════════════
  core.createBus = function () {
    var subs = {};

    var bus = {
      on: function (event, fn) {
        if (!hasOwn(subs, event)) subs[event] = [];
        subs[event].push(fn);
        return function off() {
          var list = hasOwn(subs, event) ? subs[event] : null;
          if (list) {
            var at = list.indexOf(fn);
            if (at >= 0) list.splice(at, 1);
          }
        };
      },

      emit: function (event, payload) {
        var errors = [];
        var list = (hasOwn(subs, event) ? subs[event] : []).slice();  // کپی: unsubscribe حین اجرا امن
        for (var i = 0; i < list.length; i++) {
          try {
            list[i](payload);
          } catch (e) {
            errors.push([list[i], (e && e.message !== undefined) ? String(e.message) : String(e)]);
          }
        }
        return errors;
      },

      listenerCount: function (event) {
        return (hasOwn(subs, event) ? subs[event] : []).length;
      }
    };
    return bus;
  };

  // ════════════════════════════════════════════════════════════
  //  Pipeline — آینهٔ src/core/pipeline.py
  //  StageResult: {stage, ok, value, unavailable, error, stop}
  //  دو منبع هندلر: صریح (add) و پلاگین‌های STARTED همان مرحله با
  //  هوک run(ctx) — هندلرهای صریح *sorted* و سپس هوک‌ها *append*
  //  (بدون sort مجدد — صریح همیشه پیش از پلاگین‌ها، مثل پایتون).
  //  خطای مرحله → unavailable + رویداد plugin.failed + ادامهٔ pipeline.
  // ════════════════════════════════════════════════════════════
  core.stageResult = function (opts) {
    opts = opts || {};
    return {
      _isStageResult: true,
      stage: opts.stage || '',
      ok: (opts.ok !== undefined) ? opts.ok : true,
      value: (opts.value !== undefined) ? opts.value : null,
      unavailable: (opts.unavailable !== undefined) ? opts.unavailable : false,
      error: (opts.error !== undefined) ? opts.error : '',
      stop: (opts.stop !== undefined) ? opts.stop : false
    };
  };

  core.isStageResult = function (v) {
    return !!(v && v._isStageResult === true);
  };

  core.createPipeline = function (opts) {
    opts = opts || {};
    var registry = opts.registry || null;
    var bus = opts.bus || core.createBus();
    var log = (typeof opts.log === 'function') ? opts.log : function () {};
    var stages = opts.stages ? opts.stages.slice() : STAGES.slice();

    var handlers = {};
    for (var s = 0; s < stages.length; s++) handlers[stages[s]] = [];

    function runStage(stage, ctx) {
      bus.emit(EVENTS.STAGE_START, { stage: stage });
      var out = core.stageResult({ stage: stage });

      // هندلرهای صریح (sorted) + هوک‌های پلاگین (append) — ترتیب قطعی
      var chain = handlers[stage].slice().sort(function (a, b) {
        return (a[0] - b[0]) || (a[1] - b[1]);
      });
      if (registry) {
        var recs = registry.byStage(stage);      // فقط activeها (onlyActive پیش‌فرض)
        for (var i = 0; i < recs.length; i++) {
          (function (rec, idx) {
            var hook = rec.instance ? rec.instance.run : null;
            if (typeof hook === 'function' && rec.state === STATES.STARTED) {
              chain.push([rec.manifest.priority, 1000 + idx, function (c) {
                return hook.call(rec.instance, c);
              }]);
            }
          })(recs[i], i);
        }
      }

      try {
        for (var j = 0; j < chain.length; j++) {
          var value = chain[j][2](ctx);
          if (core.isStageResult(value)) {       // کنترل صریح stop/unavailable
            if (value.stop) {
              out.stop = true;
              out.value = value.value;
              break;
            }
            if (value.unavailable) {
              out.unavailable = true;
              out.error = value.error;
              out.value = value.value;
              break;
            }
            out.value = value.value;
          } else {
            out.value = value;
          }
        }
      } catch (e) {                              // قرنطینهٔ مرحله — ادامه هست
        out.ok = false;
        out.unavailable = true;
        out.error = (e && e.message !== undefined) ? String(e.message) : String(e);
        var failure = core.makeFailure('stage:' + stage, 'run', out.error);
        log(core.failureFaMessage(failure));
        bus.emit(EVENTS.PLUGIN_FAILED, failure);
      }

      bus.emit(EVENTS.STAGE_DONE,
        { stage: stage, ok: out.ok, unavailable: out.unavailable, stop: out.stop });
      return out;
    }

    var runner = {
      stages: stages,

      add: function (stage, fn, priority) {
        if (!hasOwn(handlers, stage)) {
          throw coreError('ValueError',
            'مرحلهٔ ناشناخته «' + stage + '» — مراحل معتبر: ' + stages.join(', '));
        }
        handlers[stage].push([(priority !== undefined) ? priority : 100,
                              handlers[stage].length, fn]);
      },

      run: function (ctx, onlyStages) {
        var res = { ok: true, stoppedAt: null, stages: [], context: ctx };
        var list = onlyStages || stages;
        for (var i = 0; i < list.length; i++) {
          var sr = runStage(list[i], ctx);
          res.stages.push(sr);
          if (sr.stop) { res.stoppedAt = list[i]; break; }
          if (!sr.ok) res.ok = false;
        }
        res.stage = function (name) {
          for (var k = 0; k < res.stages.length; k++) {
            if (res.stages[k].stage === name) return res.stages[k];
          }
          return null;
        };
        return res;
      }
    };
    return runner;
  };

  // ثابت‌ها منجمد — سهوِ «تغییر ترتیب مراحل» در زمان اجرا گرفته می‌شود
  function deepFreeze(obj) {
    Object.freeze(obj);
    Object.keys(obj).forEach(function (k) {
      var v = obj[k];
      if (v && typeof v === 'object' && !Object.isFrozen(v)) deepFreeze(v);
    });
    return obj;
  }
  deepFreeze(CONTRACTS);
  deepFreeze(EVENTS);
  Object.freeze(EVENTS_ALL);
  Object.freeze(STAGES);
  Object.freeze(SCHEDULER_STAGES);
  deepFreeze(STATES);
  deepFreeze(ALLOWED);

  O.core = core;
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
