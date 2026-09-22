/* کنترل‌گر اصلی اپ — وضعیت، ناوبری، اجرای چرخهٔ تحلیل، تنظیمات.
 *
 * جریان تحلیل دقیقاً آینهٔ run_cycle دسکتاپ است:
 *   داده ← تحلیل تکنیکال ← قدرت ارزها ← تریدینگ‌ویو ← تقویم ← اخبار
 *   ← ژورنال (بستن سیگنال‌های باز) ← داور ← ثبت سیگنال‌ها (با کنترل اسپم)
 *
 * v0.13.0 — دو حالت اجرا:
 *   ۱) UI (پیش‌فرض): رابط کامل + تازه‌سازی خودکار وقتی اپ باز است.
 *   ۲) سرویس (?svc=1): بدون رابط؛ OdinService یک WebView بی‌سر با همین
 *      صفحه می‌سازد و با تیکِ بومی (Handler) چرخه را تکرار می‌کند تا بدون
 *      باز کردن اپ هم سیگنال/خبر فوری با اعلان اندروید برسد.
 *      زمان‌بندی عمداً بومی است: pauseTimers و throttling مرورگر روی
 *      تایمرهای JS اثر دارند، روی Handler اندروید نه.
 *
 * هستهٔ مشترک هر دو حالت: O.cycleCore — بدون هیچ تماسی با DOM.
 * تفاوت با دسکتاپ: تلگرام ندارد و هیچ معامله‌ای نمی‌کند.
 */
(function (O) {
  'use strict';

  // حالت سرویس: از کوئری‌استرینگ URL (WebView بی‌سر) — در Node/تست false
  O.SERVICE_MODE = (function () {
    try {
      return typeof location !== 'undefined' && !!location.search &&
        location.search.indexOf('svc=1') >= 0;
    } catch (e) { return false; }
  })();

  var S = {
    cfg: null, settings: null, storage: null, journal: null,
    state: null, stats: null, tab: 'home', busy: false,
    version: 'dev', lastBack: 0,   // در boot() از PackageManager پر می‌شود
    deviceId: '', deviceCode: '', licensed: false,   // لایسنس (v0.14.0)
    chartSym: null, chartTf: 'H1', chartBars: 120, chartSig: null,   // نمودار (v0.17.0)
    onbStage: null,               // 'license' | 'name' | 'bg' | null — مرحلهٔ خوش‌آمدگویی
    svcBusy: false, svcReady: false
  };
  O.S = S;

  var DEFAULT_SETTINGS = {
    user_name: 'تریدر',
    judge_enabled: true,
    min_score: 7,
    veto: {
      weekend: true, high_impact_event: true, timeframe_conflict: true,
      range_market: true, volatility_spike: true, breaking_news: true
    },
    fund_enabled: true, news_enabled: true, tv_enabled: true,
    auto_refresh_enabled: true, auto_refresh_min: 15, notify_enabled: true,
    background_enabled: true,     // v0.13: رصد پس‌زمینه (در خوش‌آمدگویی پرسیده می‌شود)
    animations_enabled: true      // v0.21: همتای ui.animations در config.yaml دسکتاپ
  };

  function buildCfg() {
    var st = S.settings;
    return O.deepFill(O.CONFIG, {
      ui: { user_name: st.user_name },
      judge: { enabled: st.judge_enabled, min_score: st.min_score, veto: st.veto },
      fundamental: { enabled: st.fund_enabled },
      news: { enabled: st.news_enabled },
      tradingview: { enabled: st.tv_enabled }
    });
  }

  function loadSettings() {
    try {
      var raw = S.storage.get('settings');
      var saved = raw ? JSON.parse(raw) : {};
      S.settings = O.deepFill(DEFAULT_SETTINGS, saved);
    } catch (e) {
      S.settings = JSON.parse(JSON.stringify(DEFAULT_SETTINGS));
    }
    S.cfg = buildCfg();
  }

  function saveSettings() {
    S.cfg = buildCfg();
    try { S.storage.set('settings', JSON.stringify(S.settings)); } catch (e) { }
  }

  // ── پل نیتیو (اعلان، اشتراک، ذخیره فایل، رصد پس‌زمینه) ────────
  // همه با گارد: در مرورگر/تست بدون ODINNative بی‌صدا رد می‌شوند.
  O.native = {
    notify: function (title, body) {
      try { if (typeof ODINNative !== 'undefined' && ODINNative.notify) ODINNative.notify(title, body); } catch (e) { }
    },
    share: function (subject, text) {
      try {
        if (typeof ODINNative !== 'undefined' && ODINNative.shareText) { ODINNative.shareText(subject, text); return true; }
      } catch (e) { }
      return false;
    },
    saveDownload: function (name, content) {
      try { if (typeof ODINNative !== 'undefined' && ODINNative.saveDownload) return ODINNative.saveDownload(name, content); } catch (e) { }
      return '';
    },
    keepScreenOn: function (on) {
      try { if (typeof ODINNative !== 'undefined' && ODINNative.keepScreenOn) ODINNative.keepScreenOn(on); } catch (e) { }
    },
    // ── رصد پس‌زمینه (v0.13.0) ─────────────────────────────────
    startBackground: function () {
      try { if (typeof ODINNative !== 'undefined' && ODINNative.startBackground) ODINNative.startBackground(); } catch (e) { }
    },
    stopBackground: function () {
      try { if (typeof ODINNative !== 'undefined' && ODINNative.stopBackground) ODINNative.stopBackground(); } catch (e) { }
    },
    bgRunning: function () {
      try { if (typeof ODINNative !== 'undefined' && ODINNative.bgRunning) return !!ODINNative.bgRunning(); } catch (e) { }
      return false;
    },
    notifyOngoing: function (title, body) {
      try { if (typeof ODINNative !== 'undefined' && ODINNative.notifyOngoing) ODINNative.notifyOngoing(title, body); } catch (e) { }
    },
    bgCycleDone: function (nextMin) {
      try { if (typeof ODINNative !== 'undefined' && ODINNative.bgCycleDone) ODINNative.bgCycleDone(nextMin | 0); } catch (e) { }
    },
    requestIgnoreBattery: function () {
      try { if (typeof ODINNative !== 'undefined' && ODINNative.requestIgnoreBattery) ODINNative.requestIgnoreBattery(); } catch (e) { }
    },
    isIgnoringBattery: function () {
      try { if (typeof ODINNative !== 'undefined' && ODINNative.isIgnoringBattery) return !!ODINNative.isIgnoringBattery(); } catch (e) { }
      return true;
    },
    notificationsEnabled: function () {
      try { if (typeof ODINNative !== 'undefined' && ODINNative.notificationsEnabled) return !!ODINNative.notificationsEnabled(); } catch (e) { }
      return true;
    },
    openNotificationSettings: function () {
      try { if (typeof ODINNative !== 'undefined' && ODINNative.openNotificationSettings) ODINNative.openNotificationSettings(); } catch (e) { }
    },
    shareImage: function (dataUrl, caption) {
      try { if (typeof ODINNative !== 'undefined' && ODINNative.shareImage) return ODINNative.shareImage(dataUrl, caption); } catch (e) { }
      return '';
    },
    saveImage: function (dataUrl, name) {
      try { if (typeof ODINNative !== 'undefined' && ODINNative.saveImage) return ODINNative.saveImage(dataUrl, name); } catch (e) { }
      return '';
    }
  };

  // ── ابزار UI (فقط حالت رابط) ────────────────────────────────
  var toastTimer = null;
  O.toast = function (msg) {
    var el = document.getElementById('toast-root');
    el.innerHTML = O.icoStr(O.esc(msg), 13);   // ایموجی احتمالی → آیکون
    el.classList.remove('hidden', 'out');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      el.classList.add('out');
      setTimeout(function () { el.classList.add('hidden'); el.classList.remove('out'); }, 300);
    }, 2600);
  };

  O.modal = function (title, bodyHtml, buttons) {
    document.getElementById('modal-title').innerHTML = title;
    document.getElementById('modal-body').innerHTML = bodyHtml;
    var acts = document.getElementById('modal-actions');
    acts.innerHTML = '';
    (buttons || []).forEach(function (b) {
      var btn = document.createElement('button');
      btn.className = 'btn ' + (b.cls || 'ghost');
      btn.textContent = b.label;
      btn.addEventListener('click', function () {
        if (b.keepOpen !== true) closeModal();
        if (b.fn) b.fn();
      });
      acts.appendChild(btn);
    });
    document.getElementById('modal-root').classList.remove('hidden');
  };
  function closeModal() { document.getElementById('modal-root').classList.add('hidden'); }
  O.modalOpen = function () { return !document.getElementById('modal-root').classList.contains('hidden'); };

  var progLog = null;
  function progressOpen(title) {
    progLog = document.getElementById('progress-log');
    progLog.innerHTML = '';
    document.getElementById('progress-title').textContent = title || 'در حال تحلیل...';
    document.getElementById('progress-close').classList.add('hidden');
    document.querySelector('.spinner').style.display = '';
    document.getElementById('progress-root').classList.remove('hidden');
  }
  function progressLog(msg) {
    if (!progLog) return;
    var d = document.createElement('div');
    d.className = 'ln';
    var t = O.tehran(new Date());               // لاگ پیشرفت هم به وقت تهران
    d.innerHTML = '[' + O.hhmm(t) + ':' + String(t.getUTCSeconds()).padStart(2, '0') + '] ' +
      O.icoStr(O.esc(msg), 12);
    progLog.appendChild(d);
    progLog.scrollTop = progLog.scrollHeight;
  }
  function progressClose(delay) {
    setTimeout(function () {
      document.getElementById('progress-root').classList.add('hidden');
    }, delay || 0);
  }
  function progressDone(keepOpen) {
    document.querySelector('.spinner').style.display = 'none';
    document.getElementById('progress-title').innerHTML = keepOpen
      ? O.ico('alert', 15, 'c-amber') + ' تحلیل تمام شد (با خطا)'
      : O.ico('check-circle', 15, 'c-green-lt') + ' تحلیل کامل شد';
    if (keepOpen) document.getElementById('progress-close').classList.remove('hidden');
    else progressClose(900);
  }

  // ── ناوبری ──────────────────────────────────────────────────
  O.navigate = function (tab) {
    S.tab = tab;
    document.querySelectorAll('.page').forEach(function (p) { p.classList.add('hidden'); });
    document.querySelectorAll('.tab').forEach(function (t) {
      t.classList.toggle('active', t.dataset.tab === tab);
    });
    var map = {
      home: ['page-home', function () { return O.renderHome(S); }],
      signals: ['page-signals', function () { return O.renderSignals(S); }],
      calendar: ['page-calendar', function () { return O.renderCalendar(S); }],
      news: ['page-news', function () { return O.renderNews(S); }],
      journal: ['page-journal', function () { return O.renderJournal(S); }],
      settings: ['page-settings', function () { return O.renderSettings(S); }],
      briefing: ['page-briefing', function () { return O.renderBriefingPage(S); }],
      about: ['page-about', function () { return O.renderAbout(S); }],
      chart: ['page-chart', function () { return O.renderChartPage(S); }]
    };
    var m = map[tab] || map.home;
    var el = document.getElementById(m[0]);
    el.innerHTML = m[1]();
    el.classList.remove('hidden');
    el.scrollTop = 0;
    // تب‌های اصلی در نوار پایین «فعال» نمی‌شوند اگر زیرصفحه باشیم
    if (tab === 'settings' || tab === 'briefing' || tab === 'about' || tab === 'chart') {
      document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('active'); });
    }
    if (tab === 'settings') document.getElementById('btn-settings').style.color = 'var(--text)';
    updateBadges();
  };

  function updateBadges() {
    var bSig = document.getElementById('badge-signals');
    var bNews = document.getElementById('badge-news');
    var sigs = (S.state && S.state.judgments || []).filter(function (j) { return j.signal; }).length;
    bSig.textContent = O.faNum(sigs);
    bSig.classList.toggle('hidden', !sigs);
    var br = (S.state && S.state.newsSnap && S.state.newsSnap.ok)
      ? S.state.newsSnap.items.filter(function (i) { return i.breaking; }).length : 0;
    bNews.textContent = O.faNum(br);
    bNews.classList.toggle('hidden', !br);
  }

  // دکمهٔ برگشت گوشی (از MainActivity فراخوانی می‌شود)
  O.back = function () {
    if (S.onbStage) return;                     // خوش‌آمدگویی اجباری — رد نمی‌شود
    if (O.modalOpen()) { closeModal(); return; }
    if (S.busy) return;
    if (S.tab !== 'home') { O.navigate('home'); return; }
    var now = Date.now();
    if (now - S.lastBack < 2200) {
      try { if (typeof ODINNative !== 'undefined') ODINNative.exit(); } catch (e) { }
      return;
    }
    S.lastBack = now;
    O.toast('برای خروج، دوباره بزنید');
  };

  // ── هستهٔ چرخهٔ تحلیل (بدون DOM — مشترک بین UI و سرویس) ─────
  // opts.log: تابع لاگ اختیاری. خروجی: Promise<{mkt, judgments, signals,
  //   newSignals, resolved, stats, nowMs}> — ژورنال/ضداسپام/state.last/
  //   اعلان سیگنال و خبر فوری همین‌جا انجام می‌شود.
  O.cycleCore = function (opts) {
    opts = opts || {};
    // گیت دسترسی (v0.15.0) — بدون لایسنس/تریال هیچ چرخه‌ای اجرا نمی‌شود
    if (!S.accessOK) return Promise.reject(new Error('not-activated'));
    var log = opts.log || function () { };
    var nowMs = Date.now();
    var prevNewsSnap = S.state ? S.state.newsSnap : null;

    return O.runPipeline(S.cfg, S.storage, log).then(function (mkt) {
      var status = O.marketStatus(new Date(nowMs));

      // ژورنال اول (مثل دسکتاپ): سیگنال‌های باز از روی کندل‌ها بسته می‌شوند
      var resolved = [];
      try {
        if (S.cfg.journal.enabled !== false) {
          resolved = O.resolveOpenSignals(S.journal, mkt.datasets, nowMs, S.cfg, log);
        }
      } catch (e) { log('[!] پیگیری ژورنال ناموفق: ' + e); }

      // داور
      var judgments = [];
      if (S.cfg.judge.enabled !== false) {
        var ctx = {
          jcfg: S.cfg.judge, acfg: S.cfg.analysis, symbolsCfg: S.cfg.symbols,
          ranking: mkt.ranking, tvMap: mkt.tvMap,
          calSnap: mkt.calSnap || null, newsSnap: mkt.newsSnap || null,
          nowMs: nowMs, status: status,
          eventVetoMinutes: +(S.cfg.fundamental.veto_minutes_before) || 30
        };
        try { judgments = O.judgeAll(mkt.analyses, mkt.datasets, ctx); }
        catch (e) { log('[!] خطای داور: ' + e); }
      } else {
        log('[i] داور امتیازدهی در تنظیمات غیرفعال است');
      }

      var signals = judgments.filter(function (j) { return j.signal; }).map(function (j) { return j.signal; });
      log(signals.length
        ? 'داور: ' + O.faNum(signals.length) + ' سیگنال صادر شد'
        : 'داور: هیچ سیگنالی صادر نشد (دلیل هر نماد در صفحهٔ سیگنال‌ها هست)');

      // ثبت در ژورنال با کنترل اسپم (cooldown)
      var sentState = {};
      var newSignals = [];                    // سیگنال‌های تازه (غیرتکراری) این چرخه — برای اعلان
      try { sentState = JSON.parse(S.storage.get('sent_signals.json') || '{}'); } catch (e) { }
      signals.forEach(function (sig) {
        var dec = O.shouldSendSignal(sentState, sig, S.cfg.judge, nowMs);
        if (S.cfg.journal.enabled !== false) {
          try { S.journal.appendRec(O.signalToJournal(sig, dec.go)); } catch (e) { }
        }
        if (dec.go) {
          newSignals.push(sig);
          sentState[sig.symbol + '|' + sig.direction] = { ts: new Date(nowMs).toISOString(), score: sig.score };
          log('سیگنال ' + sig.symbol + ' (' + (sig.direction === 'BUY' ? 'خرید' : 'فروش') + ') در ژورنال ثبت شد');
        } else {
          log('[i] سیگنال ' + sig.symbol + ' تکراری است — ' + dec.why);
        }
        sig._dup = !dec.go;
        sig._dupWhy = dec.why;
      });
      try { S.storage.set('sent_signals.json', JSON.stringify(sentState)); } catch (e) { }

      // آمار + وضعیت ماندگار
      var stats = null;
      try { stats = O.computeStats(S.journal.load(), nowMs); } catch (e) { }
      var sparks = {};
      Object.keys(mkt.datasets).forEach(function (k) {
        sparks[k] = mkt.datasets[k].m15.slice(-60).map(function (x) { return x.c; });
      });
      S.state = {
        ranAt: nowMs, errors: mkt.errors, sourceName: mkt.sourceName,
        analyses: mkt.analyses, ranking: mkt.ranking, tvMap: mkt.tvMap, tvTf: mkt.tvTf,
        calSnap: mkt.calSnap || null, newsSnap: mkt.newsSnap || null,
        judgments: judgments, resolvedCount: resolved.length, sparks: sparks
      };
      // قلاب _dup روی signalها برای رندر — داخل judgments هم هست (ref مشترک)
      S.stats = stats;
      try { S.storage.set('state.last', JSON.stringify(S.state)); } catch (e) { }
      // کش نمودار (v0.17.0) — ۳۶۰ کندل H1 اخیر هر نماد برای صفحهٔ نمودار
      // (H4 با resample4h از همین‌ها ساخته می‌شود؛ مشترک بین UI و سرویس)
      try {
        Object.keys(mkt.datasets).forEach(function (k) {
          var h1 = mkt.datasets[k] && mkt.datasets[k].h1;
          if (h1 && h1.length) S.storage.set('chart.' + k, JSON.stringify(h1.slice(-360)));
        });
      } catch (e) { }

      // اعلان اندروید: سیگنال تازه + خبر فوری (فقط در برابر چرخهٔ قبل)
      if (S.settings.notify_enabled !== false) {
        if (newSignals.length) {
          var nTitle = newSignals.length === 1
            ? 'سیگنال جدید — ' + newSignals[0].symbol + ' (' + (newSignals[0].direction === 'BUY' ? 'خرید' : 'فروش') + ')'
            : O.faNum(newSignals.length) + ' سیگنال جدید صادر شد';
          var nBody = newSignals.slice(0, 3).map(function (sg) {
            return sg.symbol + ' · امتیاز ' + O.faNum(sg.score) + '/۱۱ · ورود ' + O.fmtPrice(sg.entry, sg.pip) +
              ' · حد ضرر ' + O.fmtPrice(sg.sl, sg.pip) + ' · هدف ' + O.fmtPrice(sg.tp, sg.pip);
          }).join('\n') + '\n' + O.faNum(O.hhmmTeh(new Date(nowMs))) + ' به وقت تهران — پیشنهاد است، نه دستور معامله';
          O.native.notify(nTitle, nBody);
        }
        if (prevNewsSnap && mkt.newsSnap && mkt.newsSnap.ok) {
          var seenBr = {};
          (prevNewsSnap.ok ? prevNewsSnap.items : []).forEach(function (i) { if (i.breaking) seenBr[i.link] = 1; });
          var freshBr = mkt.newsSnap.items.filter(function (i) { return i.breaking && !seenBr[i.link]; });
          if (freshBr.length) {
            O.native.notify('خبر فوری — ' + freshBr[0].source,
              freshBr.slice(0, 2).map(function (i) { return O.headlineFa(i, 110); }).join('\n'));
          }
        }
      }

      // هشدارهای قیمت (v0.16.0) — در هسته چک می‌شوند تا هم رابط و هم
      // سرویس پس‌زمینه (اپ بسته) آن‌ها را فعال کنند؛ حذفِ پس‌از‌فعال‌شدن
      // تضمین می‌کند یک هشدار دو بار اعلان نمی‌شود.
      var firedAlerts = [];
      try { firedAlerts = O.alertsCheck(S.storage, S.state.analyses, nowMs); }
      catch (e) { log('[!] بررسی هشدار قیمت ناموفق: ' + e); }
      if (firedAlerts.length && S.settings.notify_enabled !== false) {
        firedAlerts.forEach(function (f) {
          O.native.notify('هشدار قیمت — ' + f.a.symbol,
            f.a.symbol + ' به سطح ' + O.fmtPrice(f.a.price, f.pip) +
            (f.a.dir === 'above' ? ' رسید (عبور به بالا)' : ' رسید (عبور به پایین)') +
            ' — قیمت فعلی ' + O.fmtPrice(f.price, f.pip) +
            '\n' + O.faNum(O.hhmmTeh(new Date(nowMs))) + ' به وقت تهران' +
            (f.a.sticky ? ' · هشدار تکرارشونده' : ''));
        });
      }

      return {
        mkt: mkt, judgments: judgments, signals: signals, newSignals: newSignals,
        resolved: resolved, stats: stats, nowMs: nowMs, firedAlerts: firedAlerts
      };
    });
  };

  // ── چرخهٔ تحلیل (حالت رابط) ─────────────────────────────────
  // opts.silent → بدون پنجرهٔ پیشرفت و بدون پیام‌های اضافه (تازه‌سازی خودکار)
  O.runAnalysis = function (opts) {
    opts = opts || {};
    var silent = !!opts.silent;
    if (!S.accessOK) {
      if (!silent) {
        O.toast(S.trial && S.trial.exists
          ? 'دورهٔ آزمایشی تمام شده — کلید لایسنس را وارد کن'
          : 'برنامه فعال نشده است — اول لایسنس را وارد کن');
        O.showActivation(function () { O.navigate(S.tab); }, S.trial && S.trial.exists ? 'expired' : null);
      }
      return;
    }
    if (S.busy) { if (!silent) O.toast('تحلیل قبلی هنوز در جریان است'); return; }
    S.busy = true;
    var btn = document.getElementById('btn-analyze');
    if (btn) btn.disabled = true;
    if (silent) { progLog = null; }
    else progressOpen('در حال تحلیل...');
    O.native.keepScreenOn(true);              // تا پایان تحلیل، صفحه خاموش نشود

    O.cycleCore({ log: progressLog }).then(function (res) {
      var mkt = res.mkt;
      if (!silent) progressDone(mkt.errors > 0 && !mkt.analyses.length);
      if (!O.modalOpen()) O.navigate(S.tab === 'settings' ? 'home' : S.tab);
      O.renderHeaderStatus();
      if (!mkt.analyses.length) {
        if (silent) O.toast('تازه‌سازی خودکار: داده‌ای نرسید — اتصال اینترنت را بررسی کن');
        else O.modal(O.ico('x-circle', 17, 'c-red') + ' داده‌ی نرسید',
          'هیچ نمادی تحلیل نشد — اتصال اینترنت را بررسی کن و دوباره تلاش کن.<br><br>منابع لازم: Yahoo Finance (قیمت‌ها)، ForexFactory (تقویم)، فیدهای خبری RSS.',
          [{ label: 'باشه', cls: 'primary' }]);
      } else if (!silent) {
        var msg = res.signals.length
          ? O.faNum(res.signals.length) + ' سیگنال صادر شد — صفحهٔ سیگنال‌ها را ببین'
          : 'سیگنالی صادر نشد — دلیل هر نماد در صفحهٔ سیگنال‌ها هست';
        if (res.resolved.length) msg += ' · ' + O.faNum(res.resolved.length) + ' نتیجهٔ ژورنال بسته شد';
        if (res.firedAlerts && res.firedAlerts.length) {
          msg += ' · ' + O.faNum(res.firedAlerts.length) + ' هشدار قیمت فعال شد';
        }
        O.toast(msg);
      }
      S.busy = false;
      O.native.keepScreenOn(false);
      var b2 = document.getElementById('btn-analyze');
      if (b2) b2.disabled = false;
    }).catch(function (e) {
      progressLog('خطای غیرمنتظره: ' + (e && e.message || e));
      if (silent) O.toast('تازه‌سازی خودکار ناموفق بود');
      else progressDone(true);
      S.busy = false;
      O.native.keepScreenOn(false);
      var b3 = document.getElementById('btn-analyze');
      if (b3) b3.disabled = false;
    });
  };

  // ── حالت سرویس (پس‌زمینه — بدون DOM) ────────────────────────
  // OdinService بعد از بارگذاری صفحه ODIN.svcStart() را صدا می‌زند و
  // زمان‌بندی چرخه‌های بعدی با bgCycleDone(nextMin) به دست نیتیو می‌افتد.
  O.svcStart = function () {
    if (!O.SERVICE_MODE || S.svcReady) return;
    S.storage = O.makeStorage();
    loadSettings();
    S.journal = new O.Journal(S.storage);
    try { S.version = (typeof ODINNative !== 'undefined' && ODINNative.getVersion()) || S.version; } catch (e) { }
    // لایسنس (v0.14.0): سرویس بدون فعال‌سازی چرخه نمی‌زند — صادقانه اطلاع می‌دهد و می‌ایستد
    try {
      S.deviceId = (typeof ODINNative !== 'undefined' && ODINNative.getDeviceId)
        ? (ODINNative.getDeviceId() || '') : '';
    } catch (e) { S.deviceId = ''; }
    S.deviceCode = S.deviceId ? O.deviceCodeFromId(S.deviceId) : '';
    S.licensed = !!(S.deviceId && O.licIsActive(S.storage, S.deviceId));
    S.trial = O.trialStatus(S.storage);
    S.accessOK = S.licensed || !!(S.trial && S.trial.active);
    if (!S.accessOK) {
      var why = (S.trial && S.trial.exists)
        ? (S.trial.tampered ? 'دورهٔ آزمایشی نامعتبر (دستکاری ساعت)' : 'دورهٔ آزمایشی به پایان رسیده')
        : 'برنامه فعال‌سازی نشده است';
      svcLog('سرویس متوقف شد — ' + why);
      O.native.notifyOngoing('ODIN ASSISTANT — فعال‌سازی لازم است',
        why + ' — برای شروع رصد بازار، اپ را باز کن و با کلید لایسنس فعالش کن');
      O.native.stopBackground();
      return;
    }
    try {
      var raw = S.storage.get('state.last');
      if (raw) S.state = JSON.parse(raw);
    } catch (e) { S.state = null; }
    S.svcReady = true;
    svcLog('سرویس رصد آماده شد — اولین چرخه شروع می‌شود');
    O.svcTick();
  };

  function svcLog(m) {
    try { console.log('[odin-svc] ' + O.noEmoji(String(m))); } catch (e) { }
  }

  O.svcTick = function () {
    if (!O.SERVICE_MODE || !S.svcReady || S.svcBusy) return;
    try {
      loadSettings();                            // تنظیمات تازه (کاربر شاید در UI تغییر داده)
      // بازبررسی دسترسی هر چرخه (انقضای لایسنس زمان‌دار یا پایان تریال)
      if (!S.licensed || !O.licIsActive(S.storage, S.deviceId)) {
        S.trial = O.trialStatus(S.storage);
        S.licensed = !!(S.deviceId && O.licIsActive(S.storage, S.deviceId));
        S.accessOK = S.licensed || !!(S.trial && S.trial.active);
      } else {
        S.accessOK = true;
      }
      if (!S.accessOK) {
        var whyTick = (S.trial && S.trial.exists) ? 'دورهٔ آزمایشی به پایان رسیده' : 'لایسنس معتبر نیست';
        O.native.notifyOngoing('ODIN ASSISTANT — فعال‌سازی لازم است',
          whyTick + ' — رصد متوقف شد؛ اپ را باز کن و فعال‌سازی کن');
        O.native.stopBackground();
        return;
      }
      var nextMin = Math.max(5, Math.min(240, S.settings.auto_refresh_min || 15));

      if (S.settings.background_enabled === false) {   // از UI خاموش شده
        O.native.notifyOngoing('رصد بازار — متوقف', 'رصد پس‌زمینه در تنظیمات خاموش است');
        O.native.bgCycleDone(30);
        return;
      }
      var stt = O.marketStatus(new Date());
      if (!stt.open) {
        O.native.notifyOngoing('رصد بازار — ODIN ASSISTANT',
          'بازار بسته است (' + O.noEmoji(stt.reason_fa) + ') — بررسی هر ۳۰ دقیقه');
        O.native.bgCycleDone(30);
        return;
      }
      if (S.settings.judge_enabled === false) {
        O.native.notifyOngoing('رصد بازار — ODIN ASSISTANT', 'داور در تنظیمات خاموش است — سیگنالی صادر نمی‌شود');
        O.native.bgCycleDone(nextMin);
        return;
      }

      S.svcBusy = true;
      O.cycleCore({ log: svcLog }).then(function (res) {
        S.svcBusy = false;
        var summary = 'آخرین تحلیل ' + O.faNum(O.hhmmTeh(new Date())) + ' تهران · ' +
          (res.newSignals.length
            ? O.faNum(res.newSignals.length) + ' سیگنال تازه صادر شد'
            : 'سیگنال تازه‌ای صادر نشد') +
          (res.resolved.length ? ' · ' + O.faNum(res.resolved.length) + ' نتیجهٔ ژورنال بسته شد' : '') +
          (res.firedAlerts && res.firedAlerts.length ? ' · ' + O.faNum(res.firedAlerts.length) + ' هشدار قیمت فعال شد' : '') +
          ' · چرخهٔ بعدی تا ' + O.faNum(nextMin) + ' دقیقه';
        O.native.notifyOngoing('رصد بازار — ODIN ASSISTANT', summary);
        O.native.bgCycleDone(nextMin);
      }).catch(function (e) {
        S.svcBusy = false;
        svcLog('خطای چرخه: ' + (e && e.message || e));
        O.native.notifyOngoing('رصد بازار — خطا', 'تحلیل ناموفق بود — تلاش مجدد در ۱۰ دقیقه');
        O.native.bgCycleDone(10);
      });
    } catch (e) {
      S.svcBusy = false;
      svcLog('خطای غیرمنتظره svcTick: ' + e);
      try { O.native.bgCycleDone(10); } catch (e2) { }
    }
  };

  // ── رویدادها (delegation) ───────────────────────────────────
  function bindEvents() {
    document.addEventListener('click', function (ev) {
      var t = ev.target.closest ? ev.target.closest('[data-tab],[data-action],[data-expand],[data-ext],[data-step],[data-alert-add],[data-alert-del],[data-chart-open],[data-chart-sig],[data-chart-tf],[data-chart-bars],.cal-filter') : null;
      if (!t) return;

      if (t.dataset.ext) {
        ev.preventDefault();
        try {
          if (typeof ODINNative !== 'undefined') ODINNative.openExternal(t.dataset.ext);
          else window.open(t.dataset.ext, '_blank');
        } catch (e) { }
        return;
      }
      if (t.dataset.shareImg !== undefined && t.dataset.shareImg !== '') {
        var jIdx = parseInt(t.dataset.shareImg, 10);
        var jj = ((S.state && S.state.judgments) || [])[jIdx];
        if (jj && jj.signal) showShareImageModal(jj.signal);
        return;
      }
      if (t.dataset.chartOpen) {
        S.chartSym = t.dataset.chartOpen; S.chartSig = null;
        S.chartTf = 'H1'; S.chartBars = 120;
        O.navigate('chart'); return;
      }
      if (t.dataset.chartSig) {
        var symC = t.dataset.chartSig;
        S.chartSym = symC; S.chartSig = null;
        ((S.state && S.state.judgments) || []).forEach(function (j) {
          if (j.signal && j.signal.symbol === symC) {
            S.chartSig = {
              symbol: symC, entry: j.signal.entry, sl: j.signal.sl, tp: j.signal.tp,
              pip: j.signal.pip, direction: j.signal.direction
            };
          }
        });
        S.chartTf = 'H1'; S.chartBars = 120;
        O.navigate('chart'); return;
      }
      if (t.dataset.chartTf) {
        S.chartTf = t.dataset.chartTf === 'H4' ? 'H4' : 'H1';
        S.chartBars = S.chartTf === 'H4' ? 60 : 120;
        O.navigate('chart'); return;
      }
      if (t.dataset.chartBars) {
        S.chartBars = parseInt(t.dataset.chartBars, 10) || 120;
        O.navigate('chart'); return;
      }
      if (t.dataset.alertAdd) { showAlertAdd(t.dataset.alertAdd); return; }
      if (t.dataset.alertDel) {
        O.alertsRemove(S.storage, t.dataset.alertDel);
        O.toast('هشدار حذف شد');
        O.navigate(S.tab);
        return;
      }
      if (t.dataset.tab) { O.navigate(t.dataset.tab); return; }
      if (t.dataset.expand) {
        var body = document.getElementById(t.dataset.expand);
        if (body) {
          body.classList.toggle('closed');
          var arrow = t.querySelector('span');
          if (arrow) arrow.innerHTML = body.classList.contains('closed')
            ? O.ico('chevron-down', 12) : O.ico('chevron-up', 12);
        }
        return;
      }
      if (t.dataset.step) {
        var parts = t.dataset.step.split(':');
        var key = parts[0], delta = parseInt(parts[1], 10);
        if (key === 'min_score') {
          S.settings.min_score = Math.max(4, Math.min(10, (S.settings.min_score | 0) + delta));
          saveSettings();
          O.navigate('settings');
        } else if (key === 'auto_refresh_min') {
          var cur = S.settings.auto_refresh_min || 15;
          S.settings.auto_refresh_min = Math.max(5, Math.min(120, cur + delta * 5));
          saveSettings();
          O.navigate('settings');
        }
        return;
      }
      if (t.classList.contains('cal-filter')) {
        document.querySelectorAll('.cal-filter').forEach(function (b) {
          b.classList.remove('ink'); b.classList.add('outline');
        });
        t.classList.add('ink'); t.classList.remove('outline');
        var imp = t.dataset.impact;
        document.querySelectorAll('.ev-card').forEach(function (c) {
          c.style.display = (imp === 'ALL' || c.dataset.impact === imp) ? '' : 'none';
        });
        document.querySelectorAll('.day-head').forEach(function (d) { d.style.display = imp === 'ALL' ? '' : 'none'; });
        return;
      }
      var act = t.dataset.action;
      if (act === 'analyze') { O.runAnalysis(); return; }
      if (act === 'briefing') {
        if (!S.state) { O.toast('اول یک تحلیل اجرا کن'); return; }
        O.navigate('briefing'); return;
      }
      if (act === 'share-briefing') { shareBriefing(); return; }
      if (act === 'journal-save') { saveJournalFile(); return; }
      if (act === 'ignore-battery') { O.native.requestIgnoreBattery(); setTimeout(function () { O.navigate('settings'); }, 1200); return; }
      if (act === 'open-notif-settings') { O.native.openNotificationSettings(); return; }
      if (act === 'activate-license') { O.showActivation(function () { O.navigate('settings'); }); return; }
      if (act === 'copy-device-code') { copyDeviceCode(); return; }
      if (act === 'deactivate-license') {
        O.modal(O.ico('seal', 17, 'c-red') + ' غیرفعال‌سازی؟',
          'لایسنس از این دستگاه حذف می‌شود و تحلیل/رصد متوقف می‌شود. برای فعال‌سازی دوباره به کلید لایسنس همین دستگاه نیاز داری.', [
          {
            label: 'غیرفعال کن', cls: 'red', fn: function () {
              O.licDeactivate(S.storage);
              S.licensed = false;
              O.native.stopBackground();
              O.navigate('settings');
              O.toast('برنامه غیرفعال شد');
            }
          },
          { label: 'بی‌خیال', cls: 'ghost' }
        ]);
        return;
      }
      if (act === 'clear-cache') {
        S.storage.del('cache.calendar');
        S.storage.del('state.last');
        S.state = null; S.stats = null;
        O.toast('کش پاک شد — تحلیل بعدی کاملاً تازه است');
        O.navigate('home');
        return;
      }
      if (act === 'reset-settings') {
        O.modal(O.ico('refresh', 17) + ' بازنشانی تنظیمات؟', 'همهٔ تنظیمات به حالت پیش‌فرض برمی‌گردند. ژورنال پاک نمی‌شود.', [
          {
            label: 'بازنشانی', cls: 'red', fn: function () {
              S.settings = JSON.parse(JSON.stringify(DEFAULT_SETTINGS)); saveSettings();
              O.navigate('settings'); O.toast('تنظیمات بازنشانی شد');
            }
          },
          { label: 'بی‌خیال', cls: 'ghost' }
        ]);
        return;
      }
      if (act === 'journal-export') { exportJournal(); return; }
      if (act === 'journal-clear') {
        O.modal(O.ico('trash', 17, 'c-red') + ' پاک‌کردن ژورنال؟',
          'همهٔ سیگنال‌ها و نتایج از بین می‌روند و کارنامهٔ دقت صفر می‌شود. این کار برگشت‌پذیر نیست.<br>اگر می‌خواهی نگهش داری، اول خروجی JSONL بگیر.', [
          {
            label: 'پاک کن', cls: 'red', fn: function () {
              S.journal.clear(); S.storage.del('sent_signals.json');
              S.stats = O.computeStats([], Date.now());
              O.navigate('journal'); O.toast('ژورنال پاک شد');
            }
          },
          { label: 'بی‌خیال', cls: 'ghost' }
        ]);
        return;
      }
    });

    // تغییر تنظیمات (کلیدها و ورودی متن)
    document.addEventListener('change', function (ev) {
      var t = ev.target;
      if (!t.dataset || !t.dataset.set) return;
      var key = t.dataset.set;
      if (key.startsWith('veto.')) {
        S.settings.veto[key.slice(5)] = t.checked;
      } else if (key === 'user_name') {
        S.settings.user_name = String(t.value || '').trim() || 'تریدر';
        applyUserName();
      } else if (key === 'background_enabled') {
        // رصد پس‌زمینه: سرویس نیتیو روشن/خاموش شود (v0.13.0)
        S.settings.background_enabled = t.checked;
        saveSettings();
        if (t.checked) {
          O.native.startBackground();
          if (!O.native.isIgnoringBattery()) O.native.requestIgnoreBattery();
          O.toast('رصد پس‌زمینه روشن شد — بدون باز کردن اپ هم سیگنال می‌رسد');
        } else {
          O.native.stopBackground();
          O.toast('رصد پس‌زمینه خاموش شد');
        }
        O.navigate('settings');
        return;
      } else {
        S.settings[key] = t.checked;
      }
      saveSettings();
      if (key === 'animations_enabled') applyAnimations();
      O.toast('ذخیره شد');
    });

    document.getElementById('progress-close').addEventListener('click', function () { progressClose(0); });
    document.getElementById('btn-settings').addEventListener('click', function () { O.navigate('settings'); });
  }

  function applyUserName() {
    var n = String(S.settings.user_name || '').trim();
    document.getElementById('greet').textContent = n ? 'سلام ' + n + '!' : 'سلام!';
    document.getElementById('splash-name').textContent = n ? 'خوش اومدی ' + n : 'خوش اومدی';
  }

  // v0.21.0 — کلید «انیمیشن‌ها» واقعاً اثر کند.
  // پیش‌تر config.yaml دسکتاپ ui.animations داشت ولی اندروید هیچ معادلی
  // نداشت؛ CSS هم body.no-anim را می‌شناخت ولی هیچ‌کس ستش نمی‌کرد.
  function applyAnimations() {
    var on = S.settings.animations_enabled !== false;
    if (typeof document !== 'undefined' && document.body) {
      document.body.classList.toggle('no-anim', !on);
    }
  }
  O.applyAnimations = applyAnimations;

  function exportJournal() {
    var raw = S.journal.raw();
    if (!raw.trim()) { O.toast('ژورنال خالی است'); return; }
    // v0.21.0 — منطق کپی (clipboard API → execCommand → مودالِ متنِ قابل‌انتخاب)
    // پیش‌تر سه‌جا در همین فایل تکراری نوشته شده بود و هر سه کمی متفاوت؛ حالا
    // یک پیاده‌سازی مشترک در components.js است.
    O.copyText(raw, 'در کلیپ‌بورد کپی شد');
  }

  // ذخیرهٔ ژورنال در پوشهٔ دانلودها (پشتیبان‌گیری)
  function saveJournalFile() {
    var raw = S.journal.raw();
    if (!raw.trim()) { O.toast('ژورنال خالی است'); return; }
    var name = 'odin-journal-' + O.dayKeyTeh(new Date()) + '.jsonl';
    var res = O.native.saveDownload(name, raw);
    if (res === 'ok') O.toast('ذخیره شد: دانلودها/' + name);
    else if (res === 'permission') O.toast('مجوز حافظه لازم است — پس از اجازه، دوباره بزن');
    else if (!res) O.toast('ذخیرهٔ فایل ممکن نیست — از «کپی JSONL» استفاده کن');
    else O.toast('خطا در ذخیره: ' + String(res).slice(0, 60));
  }

  // اشتراک‌گذاری بریفینگ با شیتر اندروید (تلگرام، واتساپ، ...)
  function shareBriefing() {
    if (!S.state) { O.toast('اول یک تحلیل اجرا کن'); return; }
    var lines = O.renderBriefing(S.state, S.cfg, S.state.ranAt);
    var txt = lines.join('\n') + '\n\n— ODIN ASSISTANT v' + S.version + ' (اندروید) · ساعت‌ها به وقت تهران';
    if (!O.native.share('بریفینگ ODIN ASSISTANT', txt)) {
      O.copyText(txt, 'در کلیپ‌بورد کپی شد', { onFail: function () { O.toast('اشتراک‌گذاری ممکن نیست'); } });
    }
  }

  // ── هشدار قیمت (v0.16.0) — افزودن از کارت نماد در خانه ──────
  function toLatinDigits(str) {
    return String(str == null ? '' : str)
      .replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 0x06F0); })
      .replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 0x0660); })
      .replace(/٫/g, '.');
  }

  function showAlertAdd(symbol) {
    var a = null;
    (S.state && S.state.analyses || []).forEach(function (x) { if (x.symbol === symbol) a = x; });
    var pip = a ? a.pip : 0.0001;
    var pair = symbol.length === 6 ? symbol.slice(0, 3) + '/' + symbol.slice(3) : symbol;
    var cur = (a && isFinite(a.price)) ? O.fmtPrice(a.price, pip) : '';
    var dir = 'above';
    O.modal(O.ico('bell', 18) + ' هشدار قیمت — ' + pair,
      '<div class="set-sub" style="margin-bottom:10px">قیمت فعلی: <b class="mono" style="color:var(--text)">' +
        (cur || '—') + '</b>' + (a ? '' : ' — اول یک تحلیل اجرا کن') + '</div>' +
      '<div class="sym-meta" style="margin-bottom:10px">' +
        '<button class="pill ink" id="al-above" type="button">' + O.ico('arrow-up', 11) + ' وقتی بالاتر رفت</button>' +
        '<button class="pill outline" id="al-below" type="button">' + O.ico('arrow-down', 11) + ' وقتی پایین‌تر آمد</button>' +
      '</div>' +
      '<input id="al-price" class="text-input mono" inputmode="decimal" placeholder="مثلاً 1.1800" value="' + cur + '"' +
        ' style="text-align:center;letter-spacing:1px;font-weight:700" autocomplete="off" autocorrect="off" spellcheck="false">' +
      '<div class="set-row" style="padding:12px 2px 0"><div><div class="set-label">هشدار تکرارشونده</div>' +
      '<div class="set-sub">پس از فعال‌شدن حذف نمی‌شود — حداکثر هر ۶۰ دقیقه یک‌بار تکرار می‌شود</div></div>' +
      '<label class="switch"><input type="checkbox" id="al-sticky"><span class="track"></span><span class="knob"></span></label></div>',
      [{
        label: 'ثبت هشدار', cls: 'primary', keepOpen: true, fn: function () {
          var el = document.getElementById('al-price');
          var price = parseFloat(toLatinDigits(el ? el.value : ''));
          if (!isFinite(price) || price <= 0) { O.toast('قیمت معتبر وارد کن (با رقم لاتین)'); return; }
          var stickyEl = document.getElementById('al-sticky');
          var r = O.alertsAdd(S.storage, symbol, dir, price, !!(stickyEl && stickyEl.checked), pip);
          if (!r.ok) {
            O.toast(r.why === 'duplicate' ? 'این هشدار قبلاً ثبت شده است'
              : (r.why === 'max'
                ? 'حداکثر ' + O.faNum(O.ALERTS_MAX) + ' هشدار فعال — اول یکی را حذف کن'
                : 'قیمت نامعتبر است'));
            return;
          }
          closeModal();
          var already = a && isFinite(a.price) &&
            ((dir === 'above' && a.price >= price) || (dir === 'below' && a.price <= price));
          O.toast(already
            ? 'هشدار ثبت شد — قیمت همین حالا از سطح گذشته؛ در چرخهٔ بعد فعال می‌شود'
            : 'هشدار ثبت شد — حتی وقتی اپ بسته باشد فعال می‌شود');
          O.navigate(S.tab);
        }
      }]);
    var up = document.getElementById('al-above'), dn = document.getElementById('al-below');
    if (up) up.addEventListener('click', function () {
      dir = 'above'; up.className = 'pill ink'; dn.className = 'pill outline';
    });
    if (dn) dn.addEventListener('click', function () {
      dir = 'below'; dn.className = 'pill ink'; up.className = 'pill outline';
    });
  }

  // ── کارت تصویری سیگنال (v0.18.0) — پیش‌نمایش، ارسال، ذخیره ──
  function showShareImageModal(sig) {
    var spec = O.buildShareSpec(sig, { version: S.version });
    var dataUrl = null;
    var pending = [];

    function build(cb) {
      if (dataUrl) { cb(dataUrl); return; }
      var fontsReady = (document.fonts && document.fonts.ready)
        ? document.fonts.ready : Promise.resolve();
      Promise.resolve(fontsReady).then(function () {
        try {
          var cv = O.renderShareCanvas(spec);
          dataUrl = cv.toDataURL('image/png');
          cb(dataUrl);
        } catch (e) {
          O.toast('ساخت تصویر ممکن نشد — دوباره تلاش کن');
        }
      });
    }

    O.modal(O.ico('share', 17) + ' اشتراک کارت سیگنال',
      '<div id="sc-wrap" style="text-align:center;min-height:220px">' +
      '<div class="spinner" style="margin:90px auto;border-color:var(--border);border-top-color:var(--ink)"></div></div>',
      [
        {
          label: 'ارسال به…', cls: 'primary', fn: function () {
            build(function (u) {
              var res = O.native.shareImage(u,
                spec.dirLabel + ' ' + spec.pair + ' · امتیاز ' + spec.scoreFa + ' — ODIN ASSISTANT');
              if (res && res !== 'ok') O.toast('اشتراک ناموفق: ' + String(res).slice(0, 50));
            });
          }
        },
        {
          label: 'ذخیره در گالری', cls: 'ghost', fn: function () {
            build(function (u) {
              var name = 'odin-signal-' + sig.symbol + '-' + O.dayKeyTeh(new Date(sig.now || Date.now())) + '.png';
              var res = O.native.saveImage(u, name);
              if (res === 'ok') O.toast('در گالری ذخیره شد (Pictures/ODIN)');
              else if (res === 'permission') O.toast('مجوز حافظه لازم است — پس از اجازه، دوباره بزن');
              else if (!res) O.toast('ذخیره در این محیط ممکن نیست');
              else O.toast('خطا در ذخیره: ' + String(res).slice(0, 50));
            });
          }
        },
        { label: 'بستن', cls: 'ghost' }
      ]);

    build(function (u) {
      var w = document.getElementById('sc-wrap');
      if (w) {
        w.innerHTML = '<img src="' + u + '" alt="کارت سیگنال" ' +
          'style="width:100%;border-radius:18px;box-shadow:var(--shadow-lg)">';
      }
    });
  }

  // ── همگام‌سازی با سرویس پس‌زمینه ────────────────────────────
  // وقتی رصد پس‌زمینه فعال است، چرخه‌ها در WebView سرویس اجرا می‌شوند و
  // نتیجه در state.last می‌نشیند؛ رابط فقط آن را تازه می‌خواند (واکشی دوبله نه).
  function syncFromStorage() {
    try {
      var raw = S.storage.get('state.last');
      if (!raw) return;
      var st = JSON.parse(raw);
      if (st && st.ranAt && (!S.state || st.ranAt > S.state.ranAt)) {
        S.state = st;
        try { S.stats = O.computeStats(S.journal.load(), Date.now()); } catch (e) { }
        if (!S.busy && !O.modalOpen() && !S.onbStage) O.navigate(S.tab);
      }
    } catch (e) { }
  }

  // ── ساعت و شمارش معکوس زنده ─────────────────────────────────
  function startTimers() {
    setInterval(function () {
      var now = new Date();
      var c = document.getElementById('clock');
      if (c) c.textContent = O.faNum(O.hhmmTeh(now)) + ' تهران';
      var ic = document.getElementById('ink-clock');
      if (ic) ic.textContent = O.faNum(O.hhmmTeh(now));
      var ij = document.getElementById('ink-jalali');
      if (ij) {
        var jf = O.jalaliFa(now);
        if (ij.textContent !== jf) ij.textContent = jf;   // سر نیمه‌شب تازه شود
      }
    }, 1000);
    setInterval(function () {
      var now = Date.now();
      document.querySelectorAll('[data-cd-ts]').forEach(function (el) {
        var ts = +el.dataset.cdTs;
        el.textContent = O.countdown2((ts - now) / 60000);
      });
      O.renderHeaderStatus();
    }, 15000);
    // تازه‌سازی خودکار — اگر سرویس پس‌زمینه فعال باشد فقط همگام‌سازی می‌کنیم
    setInterval(function () {
      try {
        if (!S.settings) return;
        // تازة‌سازی وضعیت دسترسی (تریال/لایسنس زمان‌دار ممکن است وسط کار تمام شود)
        if (!S.licensed) {
          S.trial = O.trialStatus(S.storage);
          S.accessOK = !!(S.trial && S.trial.active);
          O.trialTouch(S.storage);
        }
        if (S.busy) return;
        if (typeof document !== 'undefined' && document.hidden) return;
        if (O.modalOpen()) return;
        if (O.native.bgRunning()) { syncFromStorage(); return; }
        if (S.settings.auto_refresh_enabled === false) return;
        if (!S.state || !S.state.ranAt) return;
        var iv = Math.max(5, S.settings.auto_refresh_min || 15) * 60000;
        if (Date.now() - S.state.ranAt < iv) return;
        if (!O.marketStatus(new Date()).open) return;      // آخر هفته‌ها اینترنت مصرف نکن
        O.runAnalysis({ silent: true });
      } catch (e) { }
    }, 30000);
  }

  // ── خوش‌آمدگویی و راه‌اندازی ────────────────────────────────
  function showDisclaimer() {
    O.modal(O.ico('alert', 17, 'c-amber') + ' قبل از شروع — دو قول صادقانه',
      '<b>۱) این اپ معاملهٔ خودکار نمی‌کند.</b> هیچ معامله‌ای انجام نمی‌دهد، به هیچ بروکری وصل نیست و فقط تحلیل و سیگنال <u>پیشنهادی</u> می‌دهد. تصمیم و مسئولیت هر معامله با خودت است. رصد بازار (پیش‌زمینه یا تازه‌سازی خودکار) فقط <u>تحلیل</u> را تکرار می‌کند.<br><br>' +
      '<b>۲) حلقهٔ صداقت.</b> وقتی سیگنالی صادر نشود، دلیلش شفاف گفته می‌شود؛ دادهٔ در دسترس نباشد، آن مدرک «۰ امتیاز با علامت نامشخص» می‌گیرد — هیچ امتیازی ساخته نمی‌شود. نتایج سیگنال‌ها هم در ژورنال با قاعدهٔ محتاطانه ثبت می‌شود.<br><br>' +
      '<span style="color:var(--text-3)">هیچ سیستمی سود را تضمین نمی‌کند. معامله در فارکس پرریسک است.</span>',
      [{
        label: 'متوجه شدم — بزن بریم', cls: 'primary', fn: function () {
          S.storage.set('disclaimer.ok', '1');
          trialGate();
        }
      }]);
  }

  // v0.15.0 — دروازهٔ دسترسی: لایسنس فعال یا دورهٔ آزمایشی یا «هدیهٔ خوش‌آمدگویی»
  function trialGate() {
    if (S.licensed) { askName(); return; }
    var t = O.trialStatus(S.storage);
    S.trial = t;
    S.accessOK = t.active;
    if (t.active) { askName(); return; }
    if (t.exists) {                       // تمام‌شده یا دستکاری‌شده
      O.showActivation(function () { askName(); }, t.tampered ? 'tampered' : 'expired');
      return;
    }
    // تریال شروع نشده → مودال هدیه
    S.onbStage = 'trial';
    O.modal(O.ico('seal', 18) + ' هدیهٔ خوش‌آمدگویی — ۷ روز رایگان',
      'همهٔ امکانات ODIN ASSISTANT — تحلیل، سیگنال، <b>رصد پس‌زمینه</b> و کارنامهٔ دقت — به مدت <b>۷ روز</b> رایگان و بدون محدودیت.<br><br>' +
      'بعد از پایان، کلید لایسنس مخصوص دستگاهت را از تلگرام سازنده بگیر (<span dir="ltr">@Khode_Sushian</span> — در صفحهٔ «دربارهٔ ما» هم هست).<br><br>' +
      '<span style="color:var(--text-3)">اگر همین حالا کلید داری، می‌توانی فعال‌سازی کنی.</span>',
      [
        {
          label: 'شروع ۷ روز رایگان', cls: 'primary', fn: function () {
            O.trialStart(S.storage);
            S.trial = O.trialStatus(S.storage);
            S.accessOK = S.trial.active;
            S.onbStage = null;
            O.toast('دورهٔ آزمایشی شروع شد — ۷ روز تمام‌امکانات');
            askName();
          }
        },
        {
          label: 'کلید لایسنس دارم', cls: 'ghost', fn: function () {
            S.onbStage = null;
            O.showActivation(function () { askName(); });
          }
        }
      ]);
  }

  O.showActivation = function (onDone, reason) {
    S.onbStage = 'license';
    var note = '';
    if (reason === 'expired') {
      note = '<div class="hint" style="color:var(--red-text);margin-bottom:8px">دورهٔ آزمایشی به پایان رسیده — برای ادامه، کلید لایسنس را وارد کن.</div>';
    } else if (reason === 'tampered') {
      note = '<div class="hint" style="color:var(--red-text);margin-bottom:8px">ساعت دستگاه به عقب برگشته — دورهٔ آزمایشی نامعتبر شد. با کلید لایسنس فعال‌سازی کن.</div>';
    } else if (reason === 'key-expired') {
      note = '<div class="hint" style="color:var(--red-text);margin-bottom:8px">لایسنس زمان‌دار منقضی شده — کلید تمدید را از سازنده بگیر.</div>';
    }
    O.modal(O.ico('seal', 18) + ' فعال‌سازی برنامه',
      note +
      '<div class="set-sub" style="margin-bottom:10px">«کد دستگاه» زیر را برای سازنده (Sushian Khoshkhani — تلگرام <span dir="ltr">@Khode_Sushian</span>) بفرست و کلید اختصاصی‌ات را دریافت کن. هر کلید فقط روی همان دستگاه کار می‌کند. کلیدهای زمان‌دار یک بخش تاریخ هم دارند — <b>کل رشتهٔ دریافتی</b> را وارد کن.</div>' +
      '<input id="onb-code" class="text-input" readonly value="' + O.esc(S.deviceCode || '') + '" style="letter-spacing:2px;text-align:center;font-weight:700;direction:ltr">' +
      '<input id="onb-key" class="text-input" placeholder="XXXX-XXXX-XXXX-XXXX" maxlength="24" autocomplete="off" autocorrect="off" spellcheck="false" style="margin-top:8px;text-align:center;letter-spacing:1px;direction:ltr">' +
      '<div id="onb-err" class="hint" style="color:var(--red-text);min-height:20px;margin-top:6px"></div>',
      [
        { label: 'کپی کد', cls: 'ghost', keepOpen: true, fn: function () { copyDeviceCode(); } },
        {
          label: 'ارسال', cls: 'ghost', keepOpen: true, fn: function () {
            if (!O.native.share('کد دستگاه — ODIN ASSISTANT',
              'کد دستگاه برای فعال‌سازی ODIN ASSISTANT:\n' + S.deviceCode)) copyDeviceCode();
          }
        },
        {
          label: 'فعال‌سازی', cls: 'primary', keepOpen: true, fn: function () {
            var keyEl = document.getElementById('onb-key');
            var errEl = document.getElementById('onb-err');
            var key = keyEl ? String(keyEl.value || '') : '';
            if (S.deviceId && O.validateKey(key, S.deviceCode) &&
                O.licActivate(S.storage, key, S.deviceId, S.settings.user_name)) {
              S.licensed = true;
              S.accessOK = true;
              S.licenseInfo = O.licLoad(S.storage);
              S.onbStage = null;
              closeModal();
              O.toast('برنامه فعال شد');
              if (onDone) onDone();
            } else if (errEl) {
              errEl.textContent = !S.deviceId
                ? 'شناسهٔ دستگاه در دسترس نیست — اپ را دوباره باز کن'
                : 'این کلید نامعتبر است یا برای دستگاه دیگری ساخته شده';
            }
          }
        }
      ]);
  };

  function copyDeviceCode() {
    // کد دستگاه حیاتی است (فعال‌سازی لایسنس به آن وابسته است)؛ پس در آخرین
    // چاره هم باید «دیده» شود، نه اینکه فقط پیام «کپی نشد» بگیریم.
    O.copyText(S.deviceCode, 'کد دستگاه کپی شد', {
      onFail: function () { O.toast('کد دستگاه (نگه‌دار): ' + S.deviceCode); }
    });
  }

  // v0.13.0 — پرسیدن نام در اولین اجرا (هدر «سلام {نام}!» می‌شود)
  function askName() {
    if (S.storage.get('onboarded.name') === '1') { askBackground(); return; }
    S.onbStage = 'name';
    O.modal(O.ico('user', 18) + ' اسمت چیه؟',
      '<div class="set-sub" style="margin-bottom:10px">هدر برنامه و خوش‌آمدگویی با اسم خودت شخصی می‌شود.</div>' +
      '<input id="onb-name" class="text-input" placeholder="مثلاً: سوشیان" maxlength="24" autocomplete="off" autocorrect="off" spellcheck="false">',
      [{
        label: 'ذخیره و ادامه', cls: 'primary', fn: function () {
          var el = document.getElementById('onb-name');
          var n = el ? String(el.value || '').trim() : '';
          S.settings.user_name = n || 'تریدر';
          saveSettings();
          applyUserName();
          S.storage.set('onboarded.name', '1');
          S.onbStage = null;
          askBackground();
        }
      }]);
    setTimeout(function () {
      var el = document.getElementById('onb-name');
      if (el && el.focus) el.focus();
    }, 350);
  }

  // v0.13.0 — پیشنهاد رصد پس‌زمینه (سیگنال بدون باز کردن اپ)
  function askBackground() {
    if (S.storage.get('onboarded.bg') === '1') { afterOnboard(); return; }
    S.onbStage = 'bg';
    O.modal(O.ico('activity', 18) + ' سیگنال بدون باز کردن اپ؟',
      'رصد پس‌زمینه هر چند دقیقه یک‌بار بازار را تحلیل می‌کند و <b>سیگنال تازه یا خبر فوری</b> را با اعلان اندروید می‌فرستد — حتی وقتی اپ بسته است.<br><br>' +
      '· یک اعلان ماندگار «در حال رصد» در نوار اعلان‌ها دیده می‌شود (طبیعی است و با یک لمس خاموش نمی‌شود — از تنظیمات اپ خاموشش کن).<br>' +
      '· برای پایداری روی گوشی‌های سخت‌گیر، اجازهٔ «نادیده‌گرفتن بهینه‌سازی باتری» خواسته می‌شود.<br>' +
      '· معامله همچنان هیچ‌وقت خودکار نیست — تصمیم با توست.',
      [
        {
          label: 'شروع رصد', cls: 'primary', fn: function () {
            S.settings.background_enabled = true;
            saveSettings();
            S.storage.set('onboarded.bg', '1');
            S.onbStage = null;
            O.native.startBackground();
            if (!O.native.isIgnoringBattery()) O.native.requestIgnoreBattery();
            O.toast('رصد پس‌زمینه فعال شد');
            afterOnboard();
          }
        },
        {
          label: 'فعلاً نه', cls: 'ghost', fn: function () {
            S.settings.background_enabled = false;
            saveSettings();
            S.storage.set('onboarded.bg', '1');
            S.onbStage = null;
            afterOnboard();
          }
        }
      ]);
  }

  function afterOnboard() {
    // اگر رصد پس‌زمینه روشن است (از قبل)، سرویس را زنده نگه داریم
    if (S.settings.background_enabled !== false) O.native.startBackground();
    maybeFirstRun();
  }

  function maybeFirstRun() {
    if (!S.state) {
      O.toast('اولین تحلیل در حال اجراست...');
      O.runAnalysis();
    }
  }

  function boot() {
    S.storage = O.makeStorage();
    loadSettings();
    S.journal = new O.Journal(S.storage);
    // نسخه از PackageManager می‌آید که خودش از APP_VERSION در src/app_paths.py
    // مشتق می‌شود (v0.20.1). fallback عمداً «dev» است نه یک شمارهٔ نسخهٔ
    // واقعی — چون هاردکدکردن عدد اینجا همان چیزی است که باعث شد اپ روی
    // «0.19.0» بماند در حالی که دسکتاپ 0.20.0 بود.
    try { S.version = (typeof ODINNative !== 'undefined' && ODINNative.getVersion()) || 'dev'; } catch (e) { S.version = 'dev'; }
    document.getElementById('splash-ver').textContent = 'v' + S.version + ' · android';
    applyUserName();
    applyAnimations();

    // لایسنس و قفل دستگاه (v0.14.0)
    try {
      S.deviceId = (typeof ODINNative !== 'undefined' && ODINNative.getDeviceId)
        ? (ODINNative.getDeviceId() || '') : '';
    } catch (e) { S.deviceId = ''; }
    if (!S.deviceId) S.deviceId = 'deadbeefcafebabedeadbeefcafebabe';  // حالت مرورگر/توسعه
    S.deviceCode = O.deviceCodeFromId(S.deviceId);
    S.licensed = O.licIsActive(S.storage, S.deviceId);
    // دورهٔ آزمایشی (v0.15.0): دسترسی = لایسنس معتبر یا تریال فعال
    S.trial = O.trialStatus(S.storage);
    O.trialTouch(S.storage);
    S.accessOK = S.licensed || !!(S.trial && S.trial.active);
    S.licenseInfo = O.licLoad(S.storage);

    // بارگذاری آخرین وضعیت (رندر فوری بدون مصرف اینترنت)
    try {
      var raw = S.storage.get('state.last');
      if (raw) S.state = JSON.parse(raw);
    } catch (e) { S.state = null; }
    try { S.stats = O.computeStats(S.journal.load(), Date.now()); } catch (e) { S.stats = null; }

    bindEvents();
    O.renderHeaderStatus();
    O.navigate('home');
    startTimers();

    // Splash
    var splash = document.getElementById('splash');
    splash.classList.remove('hidden');
    setTimeout(function () {
      splash.classList.add('fade-out');
      document.getElementById('app').classList.remove('hidden');
      setTimeout(function () { splash.style.display = 'none'; }, 500);
      if (S.storage.get('disclaimer.ok') !== '1') showDisclaimer();
      else trialGate();
    }, 1500);
  }

  // حالت سرویس هیچ UI بوت نمی‌کند؛ نیتیو بعد از بارگذاری صفحه svcStart را صدا می‌زند
  if (typeof document !== 'undefined' && document.getElementById && !O.SERVICE_MODE) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
  }
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
