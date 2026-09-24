/* 📔 ژورنال سیگنال و آمار دقت — پورت src/journal/{store,tracker,stats}.py
 *
 * قالب JSONL دقیقاً همان فایل logs/signals.jsonl دسکتاپ است (append-only)
 * ولی روی حافظهٔ گوشی (SharedPreferences از طریق پل نیتیو) نگه داشته می‌شود.
 * قاعدهٔ محتاطانهٔ «هر دو سطح در یک کندل = ضرر» اینجا هم برقرار است.
 */
(function (O) {
  'use strict';

  O.TP = 'TP'; O.SL = 'SL'; O.EXPIRED = 'EXPIRED';
  O.OUTCOME_FA = { TP: '🎯 هدف خورد', SL: '🛑 حد ضرر خورد', EXPIRED: '⏳ بدون برخورد منقضی شد' };

  // ── ذخیره‌سازی ──────────────────────────────────────────────
  // storage = {get(key), set(key,val)} — روی گوشی از پل نیتیو می‌آید،
  // در تست Node از حافظهٔ معمولی.
  O.Journal = function (storage) {
    this.storage = storage;
    this.KEY = 'journal.jsonl';
  };

  O.Journal.prototype.raw = function () {
    return (this.storage.get(this.KEY) || '');
  };

  O.Journal.prototype.appendRec = function (rec) {
    this.storage.set(this.KEY, this.raw() + JSON.stringify(rec) + '\n');
  };

  O.Journal.prototype.load = function () {
    var entries = {}, order = [];
    this.raw().split('\n').forEach(function (line) {
      line = line.trim();
      if (!line) return;
      var rec;
      try { rec = JSON.parse(line); } catch (e) { return; }   // خط خراب نادیده، نه کل فایل
      var kind = rec.kind || 'signal';
      if (kind === 'signal') {
        var e = entryFrom(rec);
        if (!entries[e.id]) { entries[e.id] = e; order.push(e.id); }
      } else if (kind === 'outcome') {
        var t = entries[rec.id || ''];
        if (t) applyOutcome(t, rec);
      }
    });
    return order.map(function (i) { return entries[i]; });
  };

  O.Journal.prototype.openEntries = function () { return this.load().filter(function (e) { return e.outcome == null; }); };
  O.Journal.prototype.closedEntries = function () { return this.load().filter(function (e) { return e.outcome != null; }); };

  O.Journal.prototype.addOutcome = function (sid, outcome, closePrice, r, note, tsMs) {
    this.appendRec({
      kind: 'outcome', id: sid,
      ts: new Date(tsMs || Date.now()).toISOString(),
      outcome: outcome,
      close_price: closePrice != null ? Math.round(closePrice * 1e6) / 1e6 : null,
      r: r != null ? Math.round(r * 1000) / 1000 : null,
      note: note || ''
    });
  };

  O.Journal.prototype.clear = function () { this.storage.set(this.KEY, ''); };

  function entryFrom(rec) {
    var ts = rec.ts ? Date.parse(rec.ts) : Date.now();
    if (isNaN(ts)) ts = Date.now();
    var d = new Date(ts);
    var p2 = function (n) { return String(n).padStart(2, '0'); };
    var sid = rec.id || (rec.symbol + '-' + d.getUTCFullYear() + p2(d.getUTCMonth() + 1) + p2(d.getUTCDate()) +
      p2(d.getUTCHours()) + p2(d.getUTCMinutes()) + p2(d.getUTCSeconds()));
    return {
      id: sid, ts: ts,
      symbol: rec.symbol || '', direction: rec.direction || '',
      entry: +rec.entry || 0, sl: +rec.sl || 0, tp: +rec.tp || 0,
      pip: +rec.pip || 0.0001, atr: +rec.atr || 0,
      risk_pips: +rec.risk_pips || 0, reward_pips: +rec.reward_pips || 0,
      rr: +rec.rr || 2, score: rec.score | 0, max_score: (rec.max_score | 0) || 11,
      session: rec.session || '', evidences: (rec.evidences || []).slice(),
      sent: rec.sent !== false,
      // S4 (v0.27): کلیدِ استراتژی‌های هم‌جهت — رکوردهای قدیمی کلید را
      // ندارند → فهرست خالی (صادقانه؛ آینهٔ Entry.strategies پایتون)
      strategies: (rec.strategies || []).slice(),
      outcome: null, outcome_ts: null, close_price: null, r: null, note: ''
    };
  }

  function applyOutcome(e, rec) {
    e.outcome = rec.outcome;
    e.outcome_ts = rec.ts ? Date.parse(rec.ts) : null;
    e.close_price = rec.close_price != null ? rec.close_price : null;
    e.r = rec.r != null ? rec.r : null;
    e.note = rec.note || '';
  }

  // ── ویژگی‌های Entry ─────────────────────────────────────────
  O.entryIsWin = function (e) { return e.outcome === O.TP; };
  O.entryIsLoss = function (e) { return e.outcome === O.SL; };
  O.entryRiskPrice = function (e) { return (e.risk_pips || 0) * (e.pip || 0.0001); };

  O.isoWeekKey = function (ms) {
    var d = new Date(ms);
    var t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
    var dayNum = t.getUTCDay() || 7;
    t.setUTCDate(t.getUTCDate() + 4 - dayNum);
    var yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
    var weekNo = Math.ceil((((t - yearStart) / 86400000) + 1) / 7);
    return t.getUTCFullYear() + '-W' + String(weekNo).padStart(2, '0');
  };

  O.entryWeekKey = function (e) { return O.isoWeekKey(e.ts); };

  // کلیدهای استراتژیِ هم‌جهت (آینهٔ e.strategies پایتون — کپی، نه مرجع)
  O.entryStrategyKeys = function (e) { return (e.strategies || []).slice(); };

  O.entryEvidenceKeys = function (e) {
    var out = [];
    (e.evidences || []).forEach(function (s) {
      var i = s.indexOf(':');
      var key = s.slice(0, i);
      var rest = s.slice(i + 1);
      var got = rest.split('/')[0];
      if (got && got !== '0') out.push(key);
    });
    return out;
  };

  // ── تعیین خودکار نتیجهٔ سیگنال‌های باز (پورت tracker.py) ────
  function rFor(e, outcome, closePrice) {
    if (outcome === O.TP) return +e.rr;
    if (outcome === O.SL) return -1;
    var risk = O.entryRiskPrice(e);
    if (risk <= 0) return 0;
    var diff = e.direction === 'BUY' ? (closePrice - e.entry) : (e.entry - closePrice);
    return diff / risk;
  }

  function scanBars(e, candles, conservative) {
    for (var i = 0; i < candles.length; i++) {
      var bar = candles[i];
      if (bar.t <= e.ts) continue;
      var hitTp, hitSl;
      if (e.direction === 'BUY') { hitTp = bar.h >= e.tp; hitSl = bar.l <= e.sl; }
      else { hitTp = bar.l <= e.tp; hitSl = bar.h >= e.sl; }
      if (hitTp && hitSl) return conservative ? [O.SL, e.sl] : [O.TP, e.tp];
      if (hitTp) return [O.TP, e.tp];
      if (hitSl) return [O.SL, e.sl];
    }
    return null;
  }

  function bothTouch(e, md) {
    if (!md || !md.m15) return false;
    return md.m15.some(function (bar) {
      return e.direction === 'BUY'
        ? (bar.h >= e.tp && bar.l <= e.sl)
        : (bar.l <= e.tp && bar.h >= e.sl);
    });
  }

  O.resolveOpenSignals = function (journal, datasets, nowMs, cfg, onLog) {
    var jcfg = cfg.journal || {};
    if (jcfg.enabled === false) return [];
    var conservative = jcfg.conservative_both_touch !== false;
    var expiryH = +jcfg.expiry_hours || 48;
    var resolved = [];

    journal.openEntries().forEach(function (e) {
      var md = datasets[e.symbol];
      var hit = null;
      if (md && md.m15 && md.m15.length) hit = scanBars(e, md.m15, conservative);

      var rOverride = null, outcome, closePrice, note = '';
      if (hit === null && (nowMs - e.ts) > expiryH * 3600e3) {
        var close = (md && md.m15 && md.m15.length) ? md.m15[md.m15.length - 1].c : null;
        outcome = O.EXPIRED; closePrice = close;
        if (close === null) {
          note = 'تا ' + O.pyFixed(expiryH, 0) + ' ساعت نه هدف خورد نه حد ضرر؛ قیمت لحظهٔ انقضا در دسترس نبود پس R صفر ثبت شد';
          rOverride = 0;
        } else {
          note = 'تا ' + O.pyFixed(expiryH, 0) + ' ساعت نه هدف خورد نه حد ضرر؛ با قیمت لحظهٔ انقضا بسته شد';
        }
      } else if (hit !== null) {
        outcome = hit[0]; closePrice = hit[1];
        if (outcome === O.SL && conservative && bothTouch(e, md)) {
          note = 'هر دو سطح در یک کندل خوردند؛ محتاطانه ضرر شمرده شد';
        }
      } else {
        return;
      }

      var r = rOverride !== null ? rOverride : rFor(e, outcome, closePrice);
      journal.addOutcome(e.id, outcome, closePrice, r, note, nowMs);
      e.outcome = outcome; e.close_price = closePrice; e.r = r; e.note = note; e.outcome_ts = nowMs;
      resolved.push(e);
      if (onLog) onLog('📔 ژورنال: ' + e.symbol + ' ' + e.direction + ' → ' +
        (O.OUTCOME_FA[outcome] || outcome) + ' (R=' + (r >= 0 ? '+' : '-') + O.pyFixed(Math.abs(r), 2) + ')');
    });
    return resolved;
  };

  // ── آمار دقت (پورت stats.py) ────────────────────────────────
  function Bucket() { return { closed: 0, wins: 0, losses: 0, expired: 0, r_sum: 0 }; }
  function bucketAdd(b, e) {
    b.closed += 1;
    if (O.entryIsWin(e)) b.wins += 1;
    else if (O.entryIsLoss(e)) b.losses += 1;
    else b.expired += 1;
    b.r_sum += e.r || 0;
  }
  function bucketRates(b) {
    var d = b.wins + b.losses;
    b.hit_rate = d ? b.wins / d : null;
    b.closed_win_rate = b.closed ? b.wins / b.closed : null;
    b.avg_r = b.closed ? b.r_sum / b.closed : null;
    return b;
  }

  function scoreBucket(score) {
    if (score >= 10) return '۱۰–۱۱';
    if (score >= 9) return '۹';
    if (score >= 8) return '۸';
    return '۷';
  }

  O.computeStats = function (entries, nowMs) {
    var st = {
      now: nowMs, total: entries.length, open_count: 0,
      overall: Bucket(), by_week: {}, by_symbol: {}, by_direction: {}, by_score: {}, by_evidence: {},
      by_strategy: {}
    };
    entries.forEach(function (e) {
      if (e.outcome == null) { st.open_count += 1; return; }
      bucketAdd(st.overall, e);
      var wk = O.entryWeekKey(e);
      if (!st.by_week[wk]) st.by_week[wk] = Bucket();
      bucketAdd(st.by_week[wk], e);
      if (!st.by_symbol[e.symbol]) st.by_symbol[e.symbol] = Bucket();
      bucketAdd(st.by_symbol[e.symbol], e);
      if (!st.by_direction[e.direction]) st.by_direction[e.direction] = Bucket();
      bucketAdd(st.by_direction[e.direction], e);
      var sb = scoreBucket(e.score);
      if (!st.by_score[sb]) st.by_score[sb] = Bucket();
      bucketAdd(st.by_score[sb], e);
      O.entryEvidenceKeys(e).forEach(function (k) {
        if (!st.by_evidence[k]) st.by_evidence[k] = Bucket();
        bucketAdd(st.by_evidence[k], e);
      });
      // S4: تفکیک استراتژی — همان الگوی by_evidence (آینهٔ compute_stats)
      O.entryStrategyKeys(e).forEach(function (k) {
        if (!st.by_strategy[k]) st.by_strategy[k] = Bucket();
        bucketAdd(st.by_strategy[k], e);
      });
    });
    bucketRates(st.overall);
    Object.keys(st.by_week).forEach(function (k) { bucketRates(st.by_week[k]); });
    Object.keys(st.by_symbol).forEach(function (k) { bucketRates(st.by_symbol[k]); });
    Object.keys(st.by_direction).forEach(function (k) { bucketRates(st.by_direction[k]); });
    Object.keys(st.by_score).forEach(function (k) { bucketRates(st.by_score[k]); });
    Object.keys(st.by_evidence).forEach(function (k) { bucketRates(st.by_evidence[k]); });
    Object.keys(st.by_strategy).forEach(function (k) { bucketRates(st.by_strategy[k]); });
    st.expectancy = st.overall.avg_r;
    var wks = Object.keys(st.by_week).sort();
    st.this_week_key = wks.length ? wks[wks.length - 1] : null;
    st.last_week_key = wks.length > 1 ? wks[wks.length - 2] : null;
    return st;
  };

  // ── کنترل اسپم (پورت should_send_signal) ────────────────────
  O.shouldSendSignal = function (state, sig, jcfg, nowMs) {
    var key = sig.symbol + '|' + sig.direction;
    var prev = state[key];
    var cooldown = +jcfg.resend_cooldown_minutes || 180;
    var gain = (jcfg.resend_score_gain | 0) || 2;
    if (!prev || typeof prev !== 'object') return { go: true, why: '' };
    var last = Date.parse(prev.ts);
    if (isNaN(last)) return { go: true, why: '' };
    var ageMin = (nowMs - last) / 60000;
    if (ageMin >= cooldown) return { go: true, why: '' };
    var delta = sig.score - (prev.score | 0);
    if (delta >= gain) return { go: true, why: 'امتیاز ' + O.faNum(delta) + ' واحد بهتر از دفعهٔ قبل شد' };
    return {
      go: false,
      why: 'همین سیگنال ' + O.faNum(Math.trunc(ageMin)) + ' دقیقه پیش ثبت شد — تا ' +
        O.faNum(Math.trunc(cooldown - ageMin)) + ' دقیقهٔ دیگر تکرارش نمی‌کنیم'
    };
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
