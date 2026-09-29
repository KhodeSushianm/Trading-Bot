/* 📔 ژورنال سیگنال و آمار دقت — پورت src/journal/{store,tracker,stats}.py
 *
 * قالب JSONL دقیقاً همان فایل logs/signals.jsonl دسکتاپ است (append-only)
 * ولی روی حافظهٔ گوشی (SharedPreferences از طریق پل نیتیو) نگه داشته می‌شود.
 * قاعدهٔ محتاطانهٔ «هر دو سطح در یک کندل = ضرر» اینجا هم برقرار است.
 */
(function (O) {
  'use strict';

  O.TP = 'TP'; O.SL = 'SL'; O.EXPIRED = 'EXPIRED';
  // v0.29 (فاز ۴) — آینهٔ src/journal/store.py. باید هم‌عدد بماند (پاریتی):
  //   1 = قواعدِ پیش از v0.29 (رکورد فیلد را ندارد → همین فرض می‌شود).
  //       این رکوردها زیرِ بایاسِ «ورودِ کهنه» سنجیده شده‌اند.
  //   2 = قواعدِ v0.29: ورود از بستهٔ M15 · اسکن از entry_ts · net_r.
  O.JOURNAL_RULES_VERSION = 2;
  O.LEGACY_RULES_VERSION = 1;
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

  // netR اختیاری است (v0.29 فاز ۳): null یعنی «هزینه مدل نشده» و خواننده
  // باید همان r را خالص بداند. آینهٔ add_outcome پایتون.
  O.Journal.prototype.addOutcome = function (sid, outcome, closePrice, r, note, tsMs, netRVal, mfeR, maeR) {
    this.appendRec({
      kind: 'outcome', id: sid,
      ts: new Date(tsMs || Date.now()).toISOString(),
      outcome: outcome,
      close_price: closePrice != null ? Math.round(closePrice * 1e6) / 1e6 : null,
      r: r != null ? Math.round(r * 1000) / 1000 : null,
      net_r: netRVal != null ? Math.round(netRVal * 1000) / 1000 : null,
      mfe_r: mfeR != null ? Math.round(mfeR * 1000) / 1000 : null,
      mae_r: maeR != null ? Math.round(maeR * 1000) / 1000 : null,
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
      // v0.29 (فاز ۱): زمانِ بسته‌شدنِ کندلی که قیمتِ ورود از آن آمده.
      // آینهٔ Entry.entry_ts پایتون. رکوردهای قدیمی ندارند → null →
      // scanBars به رفتارِ دقیقاً قبلی برمی‌گردد (سازگاری بدون حدس).
      entry_ts: (function () {
        if (!rec.entry_ts) return null;
        var v = Date.parse(rec.entry_ts);
        return isNaN(v) ? null : v;
      })(),
      spread_pips: +rec.spread_pips || 0,
      // نبودِ فیلد = رکوردِ قدیمی → null → e.rules همان ۱ می‌شود (صریح،
      // نه حدس). آینهٔ Entry.rules_version پایتون.
      rules_version: (rec.rules_version != null ? (rec.rules_version | 0) : null),
      outcome: null, outcome_ts: null, close_price: null, r: null,
      net_r: null, mfe_r: null, mae_r: null, note: ''
    };
  }

  function applyOutcome(e, rec) {
    e.outcome = rec.outcome;
    e.outcome_ts = rec.ts ? Date.parse(rec.ts) : null;
    e.close_price = rec.close_price != null ? rec.close_price : null;
    e.r = rec.r != null ? rec.r : null;
    e.net_r = rec.net_r != null ? rec.net_r : null;
    e.mfe_r = rec.mfe_r != null ? rec.mfe_r : null;
    e.mae_r = rec.mae_r != null ? rec.mae_r : null;
    e.note = rec.note || '';
  }

  // ── ویژگی‌های Entry ─────────────────────────────────────────
  O.entryIsWin = function (e) { return e.outcome === O.TP; };
  O.entryIsLoss = function (e) { return e.outcome === O.SL; };
  O.entryRiskPrice = function (e) { return (e.risk_pips || 0) * (e.pip || 0.0001); };
  // نسخهٔ قواعدِ این رکورد — بی‌فیلد یعنی قدیمی. آینهٔ Entry.rules پایتون.
  O.entryRules = function (e) {
    return (e.rules_version != null) ? e.rules_version : O.LEGACY_RULES_VERSION;
  };

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
  // Rِ خالصِ پس‌از‌هزینه (v0.29 فاز ۳) — آینهٔ _net_r پایتون.
  // ورود taker (نصفِ اسپرد) · هدف limit/maker (بدون جریمه) · استاپ و انقضا
  // taker (نصفِ دیگر). اسپرد صفر → همان Rِ ناخالص (نه صفر، نه null).
  function netR(e, outcome, grossR) {
    if (grossR == null) return null;
    var sp = +(e.spread_pips || 0);
    var risk = +(e.risk_pips || 0);
    if (!(sp > 0) || !(risk > 0)) return grossR;
    var factor = (outcome === O.TP) ? 0.5 : 1;
    return grossR - factor * sp / risk;
  }

  function rFor(e, outcome, closePrice) {
    if (outcome === O.TP) return +e.rr;
    if (outcome === O.SL) return -1;
    var risk = O.entryRiskPrice(e);
    if (risk <= 0) return 0;
    var diff = e.direction === 'BUY' ? (closePrice - e.entry) : (e.entry - closePrice);
    return diff / risk;
  }

  // ── «لحظهٔ ورود» کدام است؟ (v0.29 فاز ۱) ────────────────────
  // پیش‌تر اسکن از e.ts شروع می‌شد — دیوارساعتِ لحظهٔ صدور — در حالی که
  // e.entry (قیمت) بستهٔ یک کندلِ قدیمی‌تر بود. این دو تا یک ساعت اختلاف
  // داشتند و کارنامه را خوش‌بینانه می‌کردند (برد ~۴ برابر بیش‌برآورد و
  // باخت ~۲٫۵ برابر کم‌برآورد). حالا اسکن از entry_ts شروع می‌شود =
  // زمانِ بسته‌شدنِ همان کندلی که قیمت از آن آمده. رکوردهای قدیمی
  // entry_ts ندارند → رفتارِ دقیقاً قبلی (عمداً عوض نمی‌شود تا آمارِ
  // گذشته بی‌صدا جابه‌جا نشود). آینهٔ _in_scope پایتون.
  function inScope(e, barT) {
    return (e.entry_ts != null) ? (barT >= e.entry_ts) : (barT > e.ts);
  }

  // clamp به قراردادِ استاندارد: mfe ≥ ۰ و mae ≤ ۰. null دست‌نخورده
  // (یعنی «ثبت نشده»، نه صفرِ ساختگی). آینهٔ _clamp/_clamp_a پایتون.
  function clampMfe(v) { return v == null ? null : Math.max(0, v); }
  function clampMae(v) { return v == null ? null : Math.min(0, v); }

  // (سودِ این کندل, زیانِ این کندل) بر حسب R — آینهٔ _excursions پایتون.
  // عمداً سقف/کفِ *واقعیِ* کندل سنجیده می‌شود نه سطحِ هدف: پرسشِ «هدفِ ۲R
  // زیادی دور بود؟» فقط با دیدنِ حرکتِ واقعی پاسخ دارد.
  function excursions(e, high, low, risk) {
    if (!(risk > 0)) return null;
    return (e.direction === 'BUY')
      ? [(high - e.entry) / risk, (low - e.entry) / risk]
      : [(e.entry - low) / risk, (e.entry - high) / risk];
  }

  // برمی‌گرداند {hit, mfe, mae}. MFE/MAE روی همهٔ کندل‌های در بازه حساب
  // می‌شود حتی اگر برخوردی نباشد — سناریوی انقضا هم به آن نیاز دارد.
  // `until` کرانِ زمانی است (برای انقضا) تا حرکتِ پس از انقضا قاطی نشود.
  function scanBars(e, candles, conservative, until) {
    var risk = O.entryRiskPrice(e), mfe = null, mae = null;
    for (var i = 0; i < candles.length; i++) {
      var bar = candles[i];
      if (!inScope(e, bar.t)) continue;
      if (until != null && bar.t > until) break;
      var ex = excursions(e, bar.h, bar.l, risk);
      if (ex) {
        mfe = (mfe == null) ? ex[0] : Math.max(mfe, ex[0]);
        mae = (mae == null) ? ex[1] : Math.min(mae, ex[1]);
      }
      var hitTp, hitSl;
      if (e.direction === 'BUY') { hitTp = bar.h >= e.tp; hitSl = bar.l <= e.sl; }
      else { hitTp = bar.l <= e.tp; hitSl = bar.h >= e.sl; }
      if (hitTp && hitSl) {
        return { hit: conservative ? [O.SL, e.sl] : [O.TP, e.tp],
                 mfe: clampMfe(mfe), mae: clampMae(mae) };
      }
      if (hitTp) return { hit: [O.TP, e.tp], mfe: clampMfe(mfe), mae: clampMae(mae) };
      if (hitSl) return { hit: [O.SL, e.sl], mfe: clampMfe(mfe), mae: clampMae(mae) };
    }
    return { hit: null, mfe: clampMfe(mfe), mae: clampMae(mae) };
  }

  // v0.29: پیش‌تر این تابع *همهٔ* کندل‌های موجود را بدون کرانِ زمانی
  // می‌دید — یعنی برخوردِ دوگانه‌ای که پیش از ورود رخ داده بود هم
  // «هر دو سطح در یک کندل خوردند» یادداشت می‌گرفت. حالا همان قاعدهٔ
  // inScope را دارد. آینهٔ _both_touch پایتون.
  function bothTouch(e, candles) {
    if (!candles || !candles.length) return false;
    return candles.some(function (bar) {
      if (!inScope(e, bar.t)) return false;
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
      var bars = (md && md.m15 && md.m15.length) ? md.m15 : [];
      var scan = bars.length ? scanBars(e, bars, conservative, null)
                             : { hit: null, mfe: null, mae: null };
      var hit = scan.hit, mfe = scan.mfe, mae = scan.mae;

      var rOverride = null, outcome, closePrice, note = '';
      if (hit === null && (nowMs - e.ts) > expiryH * 3600e3) {
        var close = (md && md.m15 && md.m15.length) ? md.m15[md.m15.length - 1].c : null;
        outcome = O.EXPIRED; closePrice = close;
        if (close !== null && bars.length) {
          // MFE/MAEٔ معاملهٔ منقضی تا لحظهٔ انقضا، نه تا آخرین کندلِ موجود
          var sc2 = scanBars(e, bars, conservative, e.ts + expiryH * 3600e3);
          mfe = sc2.mfe; mae = sc2.mae;
        }
        if (close === null) {
          note = 'تا ' + O.pyFixed(expiryH, 0) + ' ساعت نه هدف خورد نه حد ضرر؛ قیمت لحظهٔ انقضا در دسترس نبود پس R صفر ثبت شد';
          rOverride = 0;
        } else {
          note = 'تا ' + O.pyFixed(expiryH, 0) + ' ساعت نه هدف خورد نه حد ضرر؛ با قیمت لحظهٔ انقضا بسته شد';
        }
      } else if (hit !== null) {
        outcome = hit[0]; closePrice = hit[1];
        if (outcome === O.SL && conservative && bothTouch(e, bars)) {
          note = 'هر دو سطح در یک کندل خوردند؛ محتاطانه ضرر شمرده شد';
        }
      } else {
        return;
      }

      var r = rOverride !== null ? rOverride : rFor(e, outcome, closePrice);
      var nr = netR(e, outcome, r);
      journal.addOutcome(e.id, outcome, closePrice, r, note, nowMs, nr, mfe, mae);
      e.outcome = outcome; e.close_price = closePrice; e.r = r; e.net_r = nr;
      e.mfe_r = mfe; e.mae_r = mae;
      e.note = note; e.outcome_ts = nowMs;
      resolved.push(e);
      // لاگ هر دو را نشان می‌دهد وقتی هزینه مدل شده — پنهان نمی‌کنیم
      var costTxt = (nr != null && nr !== r)
        ? (' · خالص=' + (nr >= 0 ? '+' : '-') + O.pyFixed(Math.abs(nr), 2)) : '';
      if (onLog) onLog('📔 ژورنال: ' + e.symbol + ' ' + e.direction + ' → ' +
        (O.OUTCOME_FA[outcome] || outcome) + ' (R=' + (r >= 0 ? '+' : '-') + O.pyFixed(Math.abs(r), 2) + costTxt + ')');
    });
    return resolved;
  };

  // ── آمار دقت (پورت stats.py) ────────────────────────────────
  function Bucket() {
    return { closed: 0, wins: 0, losses: 0, expired: 0, r_sum: 0,
             net_r_sum: 0, net_closed: 0 };
  }
  function bucketAdd(b, e) {
    b.closed += 1;
    if (O.entryIsWin(e)) b.wins += 1;
    else if (O.entryIsLoss(e)) b.losses += 1;
    else b.expired += 1;
    b.r_sum += e.r || 0;
    // فقط رکوردهایی که هزینه‌شان *واقعاً* مدل شده — آینهٔ Bucket.add پایتون
    if (e.net_r != null && (+e.spread_pips || 0) > 0) {
      b.net_r_sum += e.net_r;
      b.net_closed += 1;
    }
  }
  function bucketRates(b) {
    var d = b.wins + b.losses;
    b.hit_rate = d ? b.wins / d : null;
    b.closed_win_rate = b.closed ? b.wins / b.closed : null;
    b.avg_r = b.closed ? b.r_sum / b.closed : null;
    // میانگینِ خالص؛ null یعنی «رکوردِ هزینه‌داری نداریم» — عمداً صفر نه،
    // چون صفر یک ادعایِ گمراه‌کننده است (یعنی سربه‌سر).
    b.avg_net_r = b.net_closed ? b.net_r_sum / b.net_closed : null;
    return b;
  }

  // ── آمارِ نوسانِ درون‌معامله‌ای (v0.29 فاز ۴) — آینهٔ Excursions پایتون ──
  // ⚠️ همبستگی ≠ علیت: «سر‌به‌سر در ۱R این باخت‌ها را نجات می‌داد» یک
  // گزارهٔ بازخوانیِ گذشته است. همان قاعده، بردهایی را هم که در ۱R حرارت
  // دیده‌اند می‌کُشد — پس هر دو نرخ با هم گزارش می‌شوند، هیچ‌کدام تنها.
  function Excursions() {
    return { n: 0, mfe_sum: 0, mae_sum: 0, mfe_values: [], mae_values: [],
             losers_reached_1r: 0, losers: 0, winners_dipped_1r: 0, winners: 0 };
  }
  function excursionsAdd(x, mfe, mae, isWin, isLoss) {
    x.n += 1; x.mfe_sum += mfe; x.mae_sum += mae;
    x.mfe_values.push(mfe); x.mae_values.push(mae);
    if (isLoss) { x.losers += 1; if (mfe >= 1.0) x.losers_reached_1r += 1; }
    else if (isWin) { x.winners += 1; if (mae <= -1.0) x.winners_dipped_1r += 1; }
  }
  function medianOf(vals) {
    if (!vals.length) return null;
    var v = vals.slice().sort(function (a, b) { return a - b; });
    var n = v.length, m = Math.floor(n / 2);
    return (n % 2) ? v[m] : (v[m - 1] + v[m]) / 2;
  }
  O.excursionRates = function (x) {
    return {
      median_mfe: medianOf(x.mfe_values), median_mae: medianOf(x.mae_values),
      avg_mfe: x.n ? x.mfe_sum / x.n : null,
      avg_mae: x.n ? x.mae_sum / x.n : null,
      losers_reached_1r_rate: x.losers ? x.losers_reached_1r / x.losers : null,
      winners_dipped_1r_rate: x.winners ? x.winners_dipped_1r / x.winners : null
    };
  };

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
      by_strategy: {},
      // v0.29 (فاز ۴): تفکیک بر پایهٔ نسخهٔ قواعد + آمارِ نوسان
      by_rules: {}, excursions: Excursions()
    };
    entries.forEach(function (e) {
      if (e.outcome == null) { st.open_count += 1; return; }
      bucketAdd(st.overall, e);
      // تفکیکِ نسخهٔ قواعد — رکوردهای بایاس‌دارِ قدیمی هرگز با رکوردهای
      // v0.29 در یک سطل نمی‌روند
      var rv = O.entryRules(e);
      if (!st.by_rules[rv]) st.by_rules[rv] = Bucket();
      bucketAdd(st.by_rules[rv], e);
      // نوسان فقط روی رکوردهایی که *واقعاً* داده دارند (null شمرده نمی‌شود؛
      // میانگین روی مجموعهٔ ناهمگن عددِ بی‌معنی می‌داد)
      if (e.mfe_r != null && e.mae_r != null) {
        excursionsAdd(st.excursions, e.mfe_r, e.mae_r, O.entryIsWin(e), O.entryIsLoss(e));
      }
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
    // v0.29 (فاز ۳): عددِ درست برای تصمیم، کنارِ عددِ ناخالصِ تاریخی.
    // آینهٔ Stats.expectancy_net پایتون.
    st.expectancy_net = st.overall.avg_net_r;
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
