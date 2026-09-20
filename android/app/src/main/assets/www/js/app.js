/* کنترل‌گر اصلی اپ — وضعیت، ناوبری، اجرای چرخهٔ تحلیل، تنظیمات.
 *
 * جریان تحلیل دقیقاً آینهٔ run_cycle دسکتاپ است:
 *   داده ← تحلیل تکنیکال ← قدرت ارزها ← تریدینگ‌ویو ← تقویم ← اخبار
 *   ← ژورنال (بستن سیگنال‌های باز) ← ⚖️ داور ← ثبت سیگنال‌ها (با کنترل اسپم)
 * تفاوت: تلگرام ندارد و هیچ معامله‌ای انجام نمی‌دهد. تازه‌سازی خودکار
 * (اختیاری) فقط «تحلیل» را تکرار می‌کند — آن هم فقط وقتی اپ باز و بازار فعال است.
 */
(function (O) {
  'use strict';

  var S = {
    cfg: null, settings: null, storage: null, journal: null,
    state: null, stats: null, tab: 'home', busy: false,
    version: '0.10.0', lastBack: 0
  };
  O.S = S;

  var DEFAULT_SETTINGS = {
    user_name: 'سوشیان',
    judge_enabled: true,
    min_score: 7,
    veto: {
      weekend: true, high_impact_event: true, timeframe_conflict: true,
      range_market: true, volatility_spike: true, breaking_news: true
    },
    fund_enabled: true, news_enabled: true, tv_enabled: true,
    auto_refresh_enabled: true, auto_refresh_min: 15, notify_enabled: true
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

  // ── ابزار UI ────────────────────────────────────────────────
  var toastTimer = null;
  O.toast = function (msg) {
    var el = document.getElementById('toast-root');
    el.textContent = msg;
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

  // ── پل نیتیو (اعلان، اشتراک، ذخیره فایل، روشن‌نگه‌داشتن صفحه) ──
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
    }
  };

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
    d.textContent = '[' + O.hhmm(t) + ':' + String(t.getUTCSeconds()).padStart(2, '0') + '] ' + msg;
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
    document.getElementById('progress-title').textContent = keepOpen ? 'تحلیل تمام شد (با خطا)' : '✅ تحلیل کامل شد';
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
      briefing: ['page-briefing', function () { return O.renderBriefingPage(S); }]
    };
    var m = map[tab] || map.home;
    var el = document.getElementById(m[0]);
    el.innerHTML = m[1]();
    el.classList.remove('hidden');
    el.scrollTop = 0;
    // تب‌های اصلی در نوار پایین «فعال» نمی‌شوند اگر زیرصفحه باشیم
    if (tab === 'settings' || tab === 'briefing') {
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

  // ── چرخهٔ تحلیل ─────────────────────────────────────────────
  // opts.silent → بدون پنجرهٔ پیشرفت و بدون پیام‌های اضافه (تازه‌سازی خودکار)
  O.runAnalysis = function (opts) {
    opts = opts || {};
    var silent = !!opts.silent;
    if (S.busy) { if (!silent) O.toast('تحلیل قبلی هنوز در جریان است'); return; }
    S.busy = true;
    var btn = document.getElementById('btn-analyze');
    if (btn) btn.disabled = true;
    if (silent) { progLog = null; }
    else progressOpen('در حال تحلیل...');
    O.native.keepScreenOn(true);              // تا پایان تحلیل، صفحه خاموش نشود

    var nowMs = Date.now();
    var prevNewsSnap = S.state ? S.state.newsSnap : null;
    O.runPipeline(S.cfg, S.storage, progressLog).then(function (mkt) {
      var status = O.marketStatus(new Date(nowMs));

      // 📔 ژورنال اول (مثل دسکتاپ): سیگنال‌های باز از روی کندل‌ها بسته می‌شوند
      var resolved = [];
      try {
        if (S.cfg.journal.enabled !== false) {
          resolved = O.resolveOpenSignals(S.journal, mkt.datasets, nowMs, S.cfg, progressLog);
        }
      } catch (e) { progressLog('[!] پیگیری ژورنال ناموفق: ' + e); }

      // ⚖️ داور
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
        catch (e) { progressLog('[!] خطای داور: ' + e); }
      } else {
        progressLog('[i] داور امتیازدهی در تنظیمات غیرفعال است');
      }

      var signals = judgments.filter(function (j) { return j.signal; }).map(function (j) { return j.signal; });
      progressLog(signals.length
        ? '⚖️ داور: ' + O.faNum(signals.length) + ' سیگنال صادر شد 🎯'
        : '⚖️ داور: هیچ سیگنالی صادر نشد (دلیل هر نماد در صفحهٔ سیگنال‌ها هست)');

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
          progressLog('🎯 سیگنال ' + sig.symbol + ' (' + (sig.direction === 'BUY' ? 'خرید' : 'فروش') + ') در ژورنال ثبت شد');
        } else {
          progressLog('[i] سیگنال ' + sig.symbol + ' تکراری است — ' + dec.why);
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

      // 🔔 اعلان اندروید: سیگنال تازه + خبر فوری (فقط در برابر چرخهٔ قبل)
      if (S.settings.notify_enabled !== false) {
        if (newSignals.length) {
          var nTitle = newSignals.length === 1
            ? '🎯 سیگنال جدید: ' + newSignals[0].symbol + ' (' + (newSignals[0].direction === 'BUY' ? 'خرید' : 'فروش') + ')'
            : '🎯 ' + O.faNum(newSignals.length) + ' سیگنال جدید صادر شد';
          var nBody = newSignals.slice(0, 3).map(function (sg) {
            return sg.symbol + ' · امتیاز ' + O.faNum(sg.score) + '/۱۱ · ورود ' + O.fmtPrice(sg.entry, sg.pip) +
              ' · حد ضرر ' + O.fmtPrice(sg.sl, sg.pip) + ' · هدف ' + O.fmtPrice(sg.tp, sg.pip);
          }).join('\n') + '\n🕒 ' + O.faNum(O.hhmmTeh(new Date(nowMs))) + ' به وقت تهران — پیشنهاد است، نه دستور معامله';
          O.native.notify(nTitle, nBody);
        }
        if (prevNewsSnap && mkt.newsSnap && mkt.newsSnap.ok) {
          var seenBr = {};
          (prevNewsSnap.ok ? prevNewsSnap.items : []).forEach(function (i) { if (i.breaking) seenBr[i.link] = 1; });
          var freshBr = mkt.newsSnap.items.filter(function (i) { return i.breaking && !seenBr[i.link]; });
          if (freshBr.length) {
            O.native.notify('🚨 خبر فوری — ' + freshBr[0].source,
              freshBr.slice(0, 2).map(function (i) { return O.headlineFa(i, 110); }).join('\n'));
          }
        }
      }

      if (!silent) progressDone(mkt.errors > 0 && !mkt.analyses.length);
      if (!O.modalOpen()) O.navigate(S.tab === 'settings' ? 'home' : S.tab);
      O.renderHeaderStatus();
      if (!mkt.analyses.length) {
        if (silent) O.toast('⚠️ تازه‌سازی خودکار: داده‌ای نرسید — اتصال اینترنت را بررسی کن');
        else O.modal('❌ داده‌ای نرسید',
          'هیچ نمادی تحلیل نشد — اتصال اینترنت را بررسی کن و دوباره تلاش کن.<br><br>منابع لازم: Yahoo Finance (قیمت‌ها)، ForexFactory (تقویم)، فیدهای خبری RSS.',
          [{ label: 'باشه', cls: 'primary' }]);
      } else if (!silent) {
        var msg = signals.length
          ? '🎯 ' + O.faNum(signals.length) + ' سیگنال صادر شد — صفحهٔ سیگنال‌ها را ببین'
          : '⛔ سیگنالی صادر نشد — دلیل هر نماد در صفحهٔ سیگنال‌ها هست';
        if (resolved.length) msg += ' · 📔 ' + O.faNum(resolved.length) + ' نتیجهٔ ژورنال بسته شد';
        O.toast(msg);
      }
      S.busy = false;
      O.native.keepScreenOn(false);
      var b2 = document.getElementById('btn-analyze');
      if (b2) b2.disabled = false;
    }).catch(function (e) {
      progressLog('❌ خطای غیرمنتظره: ' + (e && e.message || e));
      if (silent) O.toast('⚠️ تازه‌سازی خودکار ناموفق بود');
      else progressDone(true);
      S.busy = false;
      O.native.keepScreenOn(false);
      var b3 = document.getElementById('btn-analyze');
      if (b3) b3.disabled = false;
    });
  };

  // ── رویدادها (delegation) ───────────────────────────────────
  function bindEvents() {
    document.addEventListener('click', function (ev) {
      var t = ev.target.closest ? ev.target.closest('[data-tab],[data-action],[data-expand],[data-ext],[data-step],.cal-filter') : null;
      if (!t) return;

      if (t.dataset.ext) {
        ev.preventDefault();
        try {
          if (typeof ODINNative !== 'undefined') ODINNative.openExternal(t.dataset.ext);
          else window.open(t.dataset.ext, '_blank');
        } catch (e) { }
        return;
      }
      if (t.dataset.tab) { O.navigate(t.dataset.tab); return; }
      if (t.dataset.expand) {
        var body = document.getElementById(t.dataset.expand);
        if (body) {
          body.classList.toggle('closed');
          var arrow = t.querySelector('span');
          if (arrow) arrow.textContent = body.classList.contains('closed') ? '▾' : '▴';
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
      if (act === 'clear-cache') {
        S.storage.del('cache.calendar');
        S.storage.del('state.last');
        S.state = null; S.stats = null;
        O.toast('کش پاک شد — تحلیل بعدی کاملاً تازه است');
        O.navigate('home');
        return;
      }
      if (act === 'reset-settings') {
        O.modal('بازنشانی تنظیمات؟', 'همهٔ تنظیمات به حالت پیش‌فرض برمی‌گردند. ژورنال پاک نمی‌شود.', [
          { label: 'بازنشانی', cls: 'red', fn: function () { S.settings = JSON.parse(JSON.stringify(DEFAULT_SETTINGS)); saveSettings(); O.navigate('settings'); O.toast('تنظیمات بازنشانی شد'); } },
          { label: 'بی‌خیال', cls: 'ghost' }
        ]);
        return;
      }
      if (act === 'journal-export') { exportJournal(); return; }
      if (act === 'journal-clear') {
        O.modal('🗑️ پاک‌کردن ژورنال؟',
          'همهٔ سیگنال‌ها و نتایج از بین می‌روند و کارنامهٔ دقت صفر می‌شود. این کار برگشت‌پذیر نیست.<br>اگر می‌خواهی نگهش داری، اول خروجی JSONL بگیر.', [
          { label: 'پاک کن', cls: 'red', fn: function () { S.journal.clear(); S.storage.del('sent_signals.json'); S.stats = O.computeStats([], Date.now()); O.navigate('journal'); O.toast('ژورنال پاک شد'); } },
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
        S.settings.user_name = String(t.value || '').trim() || 'سوشیان';
        applyUserName();
      } else {
        S.settings[key] = t.checked;
      }
      saveSettings();
      O.toast('ذخیره شد ✓');
    });

    document.getElementById('progress-close').addEventListener('click', function () { progressClose(0); });
    document.getElementById('btn-settings').addEventListener('click', function () { O.navigate('settings'); });
  }

  function applyUserName() {
    var n = S.settings.user_name;
    document.getElementById('greet').textContent = 'سلام ' + n + '!';
    document.getElementById('splash-name').textContent = 'خوش اومدی ' + n;
  }

  function exportJournal() {
    var raw = S.journal.raw();
    if (!raw.trim()) { O.toast('ژورنال خالی است'); return; }
    function fallbackCopy() {
      var ta = document.createElement('textarea');
      ta.value = raw;
      ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); O.toast('در کلیپ‌بورد کپی شد ✓'); }
      catch (e) { O.modal('خروجی ژورنال', '<div class="text-input" style="max-height:200px;overflow:auto;font-size:10px;direction:ltr;user-select:text;-webkit-user-select:text">' + O.esc(raw) + '</div>', [{ label: 'بستن', cls: 'ghost' }]); }
      document.body.removeChild(ta);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(raw).then(function () { O.toast('در کلیپ‌بورد کپی شد ✓'); }).catch(fallbackCopy);
    } else fallbackCopy();
  }

  // ذخیرهٔ ژورنال در پوشهٔ دانلودها (پشتیبان‌گیری)
  function saveJournalFile() {
    var raw = S.journal.raw();
    if (!raw.trim()) { O.toast('ژورنال خالی است'); return; }
    var name = 'odin-journal-' + O.dayKeyTeh(new Date()) + '.jsonl';
    var res = O.native.saveDownload(name, raw);
    if (res === 'ok') O.toast('💾 ذخیره شد: دانلودها/' + name);
    else if (res === 'permission') O.toast('مجوز حافظه لازم است — پس از اجازه، دوباره بزن');
    else if (!res) O.toast('ذخیرهٔ فایل ممکن نیست — از «کپی JSONL» استفاده کن');
    else O.toast('خطا در ذخیره: ' + String(res).slice(0, 60));
  }

  // اشتراک‌گذاری بریفینگ با شیتر اندروید (تلگرام، واتساپ، ...)
  function shareBriefing() {
    if (!S.state) { O.toast('اول یک تحلیل اجرا کن'); return; }
    var lines = O.renderBriefing(S.state, S.cfg, S.state.ranAt);
    var txt = lines.join('\n') + '\n\n— دستیار اودین v' + S.version + ' (اندروید) · ساعت‌ها به وقت تهران';
    if (!O.native.share('بریفینگ دستیار اودین', txt)) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(txt).then(function () { O.toast('در کلیپ‌بورد کپی شد ✓'); }).catch(function () { O.toast('اشتراک‌گذاری ممکن نیست'); });
      } else O.toast('اشتراک‌گذاری ممکن نیست');
    }
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
    // 🔄 تازه‌سازی خودکار — فقط وقتی اپ باز است، بازار فعال است و فاصله رسیده
    setInterval(function () {
      try {
        if (!S.settings || S.settings.auto_refresh_enabled === false) return;
        if (S.busy) return;
        if (typeof document !== 'undefined' && document.hidden) return;
        if (O.modalOpen()) return;
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
    O.modal('⚠️ قبل از شروع — دو قول صادقانه',
      '<b>۱) این اپ معاملهٔ خودکار نمی‌کند.</b> هیچ معامله‌ای انجام نمی‌دهد، به هیچ بروکری وصل نیست و فقط تحلیل و سیگنال <u>پیشنهادی</u> می‌دهد. تصمیم و مسئولیت هر معامله با خودت است. تازه‌سازی خودکار (اگر از تنظیمات روشن باشد) فقط <u>تحلیل</u> را تکرار می‌کند — آن هم فقط وقتی اپ باز و بازار فعال است.<br><br>' +
      '<b>۲) حلقهٔ صداقت.</b> وقتی سیگنالی صادر نشود، دلیلش شفاف گفته می‌شود؛ دادهٔ در دسترس نباشد، آن مدرک «۰ امتیاز با ❔» می‌گیرد — هیچ امتیازی ساخته نمی‌شود. نتایج سیگنال‌ها هم در ژورنال با قاعدهٔ محتاطانه ثبت می‌شود.<br><br>' +
      '<span style="color:var(--text-3)">هیچ سیستمی سود را تضمین نمی‌کند. معامله در فارکس پرریسک است.</span>',
      [{ label: 'متوجه شدم — بزن بریم', cls: 'primary', fn: function () { S.storage.set('disclaimer.ok', '1'); maybeFirstRun(); } }]);
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
    try { S.version = (typeof ODINNative !== 'undefined' && ODINNative.getVersion()) || '0.10.0'; } catch (e) { }
    document.getElementById('splash-ver').textContent = 'v' + S.version + ' · android';
    applyUserName();

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
      else maybeFirstRun();
    }, 1500);
  }

  if (typeof document !== 'undefined' && document.getElementById) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
  }
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
