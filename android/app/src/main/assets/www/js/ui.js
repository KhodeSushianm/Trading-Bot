/* رندر صفحه‌ها — تم روشن شیشه‌ای، مونوکروم + سبز/قرمز معنایی فقط.
 * همهٔ متن‌ها فارسی؛ قیمت‌ها لاتین، شمارش‌ها فارسی (قرارداد src/fa.py). */
(function (O) {
  'use strict';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  O.esc = esc;

  var VERDICT_CHIP = {
    BUY_SETUP: ['buy', '🟢 ستاپ خرید'],
    SELL_SETUP: ['sell', '🔴 ستاپ فروش'],
    WAIT: ['wait', '⏳ انتظار'],
    RANGE: ['range', '😴 رنج'],
    DATA: ['data', '⚠️ داده ناقص']
  };

  function agoFa(ms) {
    var m = Math.max(0, Math.round((Date.now() - ms) / 60000));
    if (m < 1) return 'همین حالا';
    if (m < 60) return O.faNum(m) + ' دقیقه پیش';
    var h = Math.floor(m / 60);
    if (h < 24) return O.faNum(h) + ' ساعت پیش';
    return O.faNum(Math.floor(h / 24)) + ' روز پیش';
  }
  O.agoFa = agoFa;

  // ── اسپارک‌لاین (SVG درون‌خطی، مونوکروم) ────────────────────
  function sparkline(vals) {
    if (!vals || vals.length < 2) return '';
    var w = 84, h = 34, min = Math.min.apply(null, vals), max = Math.max.apply(null, vals);
    var rng = (max - min) || 1;
    var pts = vals.map(function (v, i) {
      var x = (i / (vals.length - 1)) * (w - 4) + 2;
      var y = h - 3 - ((v - min) / rng) * (h - 6);
      return x.toFixed(1) + ',' + y.toFixed(1);
    });
    var last = pts[pts.length - 1].split(',');
    return '<svg class="spark" viewBox="0 0 ' + w + ' ' + h + '" fill="none">' +
      '<polyline points="' + pts.join(' ') + '" stroke="#101013" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" opacity=".8"/>' +
      '<circle cx="' + last[0] + '" cy="' + last[1] + '" r="2.4" fill="#101013"/></svg>';
  }

  // ── قرص وضعیت بازار (هدر) ──────────────────────────────────
  O.renderHeaderStatus = function () {
    var st = O.marketStatus(new Date());
    var el = document.getElementById('hdr-status');
    if (!el) return;
    el.innerHTML = '<span class="status-pill" data-state="' + (st.open ? 'ok' : 'err') + '">' +
      '<i class="dot"></i>' + esc(st.open ? st.label : st.reason_fa) + '</span>';
  };

  // ── خانه ────────────────────────────────────────────────────
  O.renderHome = function (S) {
    var st = S.state;
    var cfg = S.cfg;
    var html = '';

    html += '<div class="action-row">' +
      '<button class="btn primary" data-action="analyze" id="btn-analyze">⟳ تحلیل تازه</button>' +
      '<button class="btn ghost" data-action="briefing">🌅 بریفینگ</button>' +
      '</div>';

    var nowMs = Date.now();
    var status = O.marketStatus(new Date(nowMs));

    // کارت مشکی وضعیت
    var sigCount = st ? (st.judgments || []).filter(function (j) { return j.signal; }).length : 0;
    var breaking = (st && st.newsSnap && st.newsSnap.ok)
      ? st.newsSnap.items.filter(function (i) { return i.breaking; }).length : 0;
    var hi24 = (st && st.calSnap && st.calSnap.ok)
      ? O.upcomingEvents(st.calSnap.events, nowMs, 24, ['HIGH']).length : null;

    html += '<div class="card ink">' +
      '<div class="card-row"><div>' +
      '<div class="ink-title">' + esc(status.open ? '🟢 ' + status.label : '🔒 ' + status.reason_fa) + '</div>' +
      '<div class="ink-cap" style="margin-top:3px">' + (status.open && status.sessions.length ? 'سشن‌های فعال: ' + esc(status.sessions.join(' + ')) : 'بازار فارکس ۲۴ ساعته، ۵ روز در هفته') + '</div>' +
      '</div><div style="text-align:left"><div class="ink-num" id="ink-clock">' + O.faNum(O.hhmm(new Date(nowMs))) + '</div><div class="ink-cap">UTC</div></div></div>' +
      '<div class="ink-tiles">' +
      '<div class="ink-tile"><div class="t-num">' + O.faNum(sigCount) + '</div><div class="t-cap">سیگنال چرخهٔ آخر</div></div>' +
      '<div class="ink-tile"><div class="t-num">' + O.faNum(breaking) + '</div><div class="t-cap">خبر فوری</div></div>' +
      '<div class="ink-tile"><div class="t-num">' + (hi24 === null ? '❔' : O.faNum(hi24)) + '</div><div class="t-cap">رویداد پراثر ۲۴ساعت</div></div>' +
      '</div></div>';

    if (!st) {
      html += '<div class="card"><div class="empty-state">' +
        '<div class="e-ico">📡</div><div class="e-t">هنوز تحلیلی اجرا نشده</div>' +
        '<div class="e-s">دکمهٔ «تحلیل تازه» را بزن تا قیمت‌ها، تقویم اقتصادی و اخبار دریافت شود و داور امتیازدهی تصمیم بگیرد.<br>اولین تحلیل کمی طول می‌کشد (دریافت ۷ نماد).</div>' +
        '</div></div>';
      html += skeletonCards(3);
      return html;
    }

    // کارت نمادها
    (st.analyses || []).forEach(function (a) {
      var chip = VERDICT_CHIP[a.verdict] || ['wait', a.verdict];
      var spark = sparkline((st.sparks || {})[a.symbol]);
      html += '<div class="card sym-card">' +
        '<div class="sym-head"><div>' +
        '<div class="sym-name">' + esc(a.symbol.length === 6 ? a.symbol.slice(0, 3) + '/' + a.symbol.slice(3) : a.symbol) + '</div>' +
        '<div class="sym-fa">' + esc(a.fa_name) + '</div>' +
        '</div>' + spark + '</div>' +
        '<div class="card-row" style="align-items:flex-end">' +
        '<div class="sym-price">' + esc(O.fmtPrice(a.price, a.pip)) + '</div>' +
        '<span class="pill verdict-chip ' + chip[0] + '">' + chip[1] + '</span>' +
        '</div>' +
        '<div class="sym-meta" style="margin-top:6px">' +
        '<span class="pill outline">روند ۴ساعته: ' + esc(O.TREND_FA[a.trend]) + '</span>' +
        (a.h1_agrees ? '<span class="pill">H1 هم‌جهت ✓</span>' : '<span class="pill red">H1 ناهم‌جهت</span>') +
        '</div>' +
        '<div class="sym-stats">' +
        '<span class="sym-stat">ADX <b>' + O.faNum(a.adx.toFixed(0)) + '</b></span>' +
        '<span class="sym-stat">RSI <b>' + O.faNum(a.rsi.toFixed(0)) + '</b>' + (a.rsi_rising ? ' ↗' : ' ↘') + '</span>' +
        '<span class="sym-stat">ATR <b>' + esc(O.faPips(a.atr, a.pip, a.pip >= 0.5)) + '</b></span>' +
        '</div>' +
        ((a.support || a.resistance) ? '<div class="sym-stats">' +
          (a.support ? '<span class="sym-stat">حمایت <b>' + esc(O.fmtPrice(a.support, a.pip)) + '</b></span>' : '') +
          (a.resistance ? '<span class="sym-stat">مقاومت <b>' + esc(O.fmtPrice(a.resistance, a.pip)) + '</b></span>' : '') +
          '</div>' : '') +
        '</div>';
    });

    // قدرت ارزها
    if (st.ranking && st.ranking.length) {
      var maxAbs = Math.max.apply(null, st.ranking.map(function (x) { return Math.abs(x[1]); })) || 1;
      html += '<div class="card"><div class="card-title">💱 جریان قدرت ارزها</div>' +
        '<div class="card-sub">میانگین تغییر ۲۴ کندل یک‌ساعتهٔ اخیر — قوی‌ترین بالا</div>' +
        '<div style="margin-top:10px">';
      st.ranking.forEach(function (x) {
        var pctw = Math.min(50, Math.abs(x[1]) / maxAbs * 50);
        var neg = x[1] < 0;
        html += '<div class="str-row"><span class="str-code">' + esc(x[0]) + '</span>' +
          '<span class="str-track"><i class="mid"></i>' +
          '<i class="str-fill' + (neg ? ' neg' : '') + '" style="' +
          (neg ? 'right:50%' : 'left:50%') + ';width:' + pctw.toFixed(1) + '%"></i></span>' +
          '<span class="str-pct">' + O.faNum(x[1].toFixed(2)) + '٪</span></div>';
      });
      html += '</div></div>';
    }

    // رویداد پراثر بعدی
    if (st.calSnap && st.calSnap.ok) {
      var nxt = O.nextHighImpact(st.calSnap.events, null, null, nowMs);
      if (nxt) {
        html += '<div class="card"><div class="card-row">' +
          '<div><div class="card-title">📅 رویداد پراثر بعدی</div>' +
          '<div style="font-size:12px;font-weight:500;margin-top:2px">' + esc(nxt.title_fa) + '</div>' +
          '<div class="card-sub">' + esc(O.evCountryFa(nxt)) + ' — ' + O.faNum(O.hhmm(new Date(nxt.when))) + ' UTC</div></div>' +
          '<div style="text-align:left"><div class="countdown" data-cd-ts="' + nxt.when + '">' + esc(O.countdown2(O.evMinutesFrom(nxt, nowMs))) + '</div></div>' +
          '</div></div>';
      } else {
        html += '<div class="card"><div class="card-title">📅 رویداد پراثری پیش رو نیست</div>' +
          '<div class="card-sub">تا پایان پوشش فید این هفته، رویداد پراثری باقی نمانده — پنجرهٔ معاملاتی از نظر تقویم باز است</div></div>';
      }
    }

    // تیترهای مهم اخبار
    if (st.newsSnap && st.newsSnap.ok && st.newsSnap.items.length) {
      html += '<div class="card"><div class="card-row"><div class="card-title">📰 تیترهای مهم</div>' +
        '<button class="btn subtle" data-tab="news">همه ←</button></div><div style="margin-top:6px">';
      st.newsSnap.items.slice(0, 3).forEach(function (it) {
        html += '<div style="padding:7px 0;border-bottom:1px solid var(--divider)">' +
          (it.breaking ? '<span class="breaking-flag">🚨 فوری</span> ' : '') +
          '<span style="font-size:12px;font-weight:500;line-height:1.9">' + esc(it.title) + '</span>' +
          '<div class="news-src">' + esc(it.source) + ' · ' + esc(O.faNum(it.score)) + '/۶' +
          (O.newsDirectionFa(it) ? ' · ' + esc(O.newsDirectionFa(it)) : '') + '</div></div>';
      });
      html += '</div></div>';
    }

    // خلاصهٔ ژورنال
    var stats = S.stats;
    if (stats && stats.overall.closed > 0) {
      html += '<div class="card ink" data-tab="journal" style="cursor:pointer">' +
        '<div class="card-row"><div class="ink-title">📔 کارنامهٔ دقت</div>' +
        '<span class="pill on-ink">لمس کن ←</span></div>' +
        '<div class="ink-tiles">' +
        '<div class="ink-tile"><div class="t-num">' + O.faPct(stats.overall.hit_rate) + '</div><div class="t-cap">نرخ برد (قطعی)</div></div>' +
        '<div class="ink-tile"><div class="t-num">' + O.rFmt(stats.overall.avg_r) + '</div><div class="t-cap">میانگین R</div></div>' +
        '<div class="ink-tile"><div class="t-num">' + O.faNum(stats.open_count) + '</div><div class="t-cap">سیگنال باز</div></div>' +
        '</div></div>';
    }

    // پاصفحه
    html += '<div class="hint" style="text-align:center;padding:4px 10px 10px">' +
      'آخرین تحلیل: ' + esc(agoFa(st.ranAt)) + ' · منبع: Yahoo Finance' +
      (st.errors ? ' · ' + O.faNum(st.errors) + ' خطای دریافت داده' : '') + '<br>' +
      '⚠️ این اپ غیرخودکار است: هیچ معامله‌ای انجام نمی‌دهد، فقط تحلیل می‌کند.' +
      '</div>';
    return html;
  };

  function skeletonCards(n) {
    var h = '';
    for (var i = 0; i < n; i++) h += '<div class="card"><div class="skel" style="height:16px;width:40%;margin-bottom:10px"></div><div class="skel" style="height:30px;width:65%;margin-bottom:10px"></div><div class="skel" style="height:12px;width:85%"></div></div>';
    return h;
  }

  // ── سیگنال‌ها ───────────────────────────────────────────────
  O.renderSignals = function (S) {
    var st = S.state;
    var minScore = S.cfg.judge.min_score | 0;
    var html = '<div class="page-title">⚖️ داور امتیازدهی</div>' +
      '<div class="page-sub">آستانهٔ صدور سیگنال: ' + O.faNum(minScore) + ' از ۱۱ امتیاز — اول دروازه‌های وتو، بعد جدول مدارک. «چرا سیگنال نشد» هم خروجی معتبر است.</div>';

    if (S.cfg.judge.enabled === false) {
      return html + '<div class="card"><div class="empty-state"><div class="e-ico">⚙️</div><div class="e-t">داور خاموش است</div><div class="e-s">از تنظیمات فعالش کن.</div></div></div>';
    }
    if (!st || !st.judgments || !st.judgments.length) {
      return html + '<div class="card"><div class="empty-state"><div class="e-ico">📡</div><div class="e-t">هنوز داوری انجام نشده</div><div class="e-s">اول «تحلیل تازه» را از صفحهٔ خانه اجرا کن.</div></div></div>';
    }

    var order = { SIGNAL: 0, VETO: 1, LOW_SCORE: 2, CAPPED: 3, NO_SETUP: 4 };
    var js = st.judgments.slice().sort(function (a, b) {
      var ka = a.signal ? -1 : (order[a.reject_reason] != null ? order[a.reject_reason] : 9);
      var kb = b.signal ? -1 : (order[b.reject_reason] != null ? order[b.reject_reason] : 9);
      return (ka - kb) || (b.score - a.score);
    });

    var signals = js.filter(function (j) { return j.signal; });
    if (!signals.length) {
      var vet = js.filter(function (j) { return j.reject_reason === 'VETO'; }).length;
      var low = js.filter(function (j) { return j.reject_reason === 'LOW_SCORE'; }).length;
      var nos = js.filter(function (j) { return j.reject_reason === 'NO_SETUP'; }).length;
      html += '<div class="card ink"><div class="ink-title">⛔ هیچ سیگنالی صادر نشد — و این خودش یک خروجی معتبر است.</div>' +
        '<div class="ink-cap" style="margin-top:6px;line-height:2">وعدهٔ سیستم این است که «سیگنال بدون پشتوانه ندهد»، نه اینکه «همیشه سیگنال بدهد».</div>' +
        '<div class="ink-tiles">' +
        '<div class="ink-tile"><div class="t-num">' + O.faNum(vet) + '</div><div class="t-cap">وتو</div></div>' +
        '<div class="ink-tile"><div class="t-num">' + O.faNum(low) + '</div><div class="t-cap">امتیاز ناکافی</div></div>' +
        '<div class="ink-tile"><div class="t-num">' + O.faNum(nos) + '</div><div class="t-cap">بدون ستاپ</div></div>' +
        '</div></div>';
    }

    js.forEach(function (j, idx) {
      html += j.signal ? signalCard(j, minScore, idx) : rejectCard(j, minScore, idx);
    });
    return html;
  };

  function scoreBar(j, minScore) {
    var pct = j.max_score ? (j.score / j.max_score * 100) : 0;
    var thr = j.max_score ? (minScore / j.max_score * 100) : 0;
    return '<div class="score-bar-wrap"><div class="score-bar">' +
      '<i class="fill" style="width:' + pct.toFixed(1) + '%"></i>' +
      '<i class="thr" style="right:' + thr.toFixed(1) + '%"></i>' +
      '</div><div class="score-cap"><span>امتیاز: ' + O.faNum(j.score) + ' از ' + O.faNum(j.max_score) + '</span><span>آستانه: ' + O.faNum(minScore) + '</span></div></div>';
  }

  function evidencesHtml(j, id) {
    var h = '<button class="expand-toggle" data-expand="' + id + '">جدول مدارک (۸ مدرک) <span>▾</span></button>' +
      '<div class="expand-body closed" id="' + id + '">';
    var sorted = j.evidences.slice().sort(function (a, b) { return (b.points - a.points) || (a.key < b.key ? -1 : 1); });
    sorted.forEach(function (e) {
      h += '<div class="ev-row' + (e.unavailable ? ' unavail' : '') + '">' +
        '<span class="ev-icon">' + e.icon + '</span><div>' +
        '<span class="ev-label">' + esc(e.label_fa) + '</span>' +
        '<span class="ev-pts">(' + (e.points > 0 ? '+' + O.faNum(e.points) : O.faNum(0) + ' از ' + O.faNum(e.max_points)) + ')</span>' +
        '<div class="ev-detail">' + esc(e.detail_fa) + '</div></div></div>';
    });
    return h + '</div>';
  }

  function signalCard(j, minScore, idx) {
    var s = j.signal;
    var dirCls = s.direction === 'BUY' ? 'buy' : 'sell';
    var dirTxt = s.direction === 'BUY' ? '🟢 سیگنال خرید' : '🔴 سیگنال فروش';
    var id = 'ev-sig-' + idx;
    var h = '<div class="card sig-card">';
    h += '<div class="sig-head"><div><span class="dir-pill ' + dirCls + '">' + dirTxt + '</span>' +
      '<div style="font-size:14px;font-weight:700;margin-top:6px;direction:ltr;display:inline-block">' +
      esc(s.symbol.length === 6 ? s.symbol.slice(0, 3) + '/' + s.symbol.slice(3) : s.symbol) + '</div> ' +
      '<span class="card-sub">' + esc(s.fa_name) + '</span></div>' +
      '<div style="text-align:left"><div style="font-size:13px">' + O.stars(s.stars) + '</div>' +
      '<div class="card-sub" style="margin-top:2px">' + O.faNum(s.score) + ' از ' + O.faNum(s.max_score) + '</div></div></div>';

    if (s._dup) {
      h += '<div class="reject-why" style="margin-top:8px">🔁 ' + esc(s._dupWhy) + '</div>';
    }

    h += scoreBar(j, minScore);

    h += '<div class="levels">' +
      '<div class="level-box"><div class="l-cap">📍 ورود</div><div class="l-val">' + esc(O.fmtPrice(s.entry, s.pip)) + '</div><div class="l-sub">قیمت فعلی</div></div>' +
      '<div class="level-box sl"><div class="l-cap">🛑 حد ضرر</div><div class="l-val">' + esc(O.fmtPrice(s.sl, s.pip)) + '</div><div class="l-sub">' + esc(O.faPips(Math.abs(s.entry - s.sl), s.pip, s.is_gold)) + '</div></div>' +
      '<div class="level-box tp"><div class="l-cap">🎯 هدف</div><div class="l-val">' + esc(O.fmtPrice(s.tp, s.pip)) + '</div><div class="l-sub">' + esc(O.faPips(Math.abs(s.tp - s.entry), s.pip, s.is_gold)) + '</div></div>' +
      '</div>';

    h += '<div class="sym-meta"><span class="pill outline">⚖️ ریسک به ریسک ۱:' + O.faRatio(s.rr) + '</span>' +
      '<span class="pill outline">🌊 ATR: ' + esc(O.faPips(s.atr, s.pip, s.is_gold)) + '</span>' +
      '<span class="pill outline">💰 ریسک پیشنهادی: حداکثر ۱٪</span></div>';

    (s.warnings || []).forEach(function (w) { h += '<div class="warn-row">⚠️ ' + esc(w) + '</div>'; });

    h += evidencesHtml(j, id);

    h += '<div class="card-sub" style="margin-top:10px">🕒 ' + esc(O.faDate(new Date(s.now))) + ' UTC · 💹 ' + esc(s.session_fa) +
      (s._dup ? '' : ' · 📔 در ژورنال ثبت شد') + '</div>';
    h += '<div class="hint" style="margin-top:6px">⚠️ این یک پیشنهاد است، نه دستور معامله. هیچ سیستمی سود را تضمین نمی‌کند؛ مسئولیت هر معامله با خودت است.</div>';
    return h + '</div>';
  }

  function rejectCard(j, minScore, idx) {
    var statusFa = O.judgmentStatusFa(j);
    var id = 'ev-rej-' + idx;
    var h = '<div class="card sig-card">';
    h += '<div class="sig-head"><div><div style="font-size:14px;font-weight:700;direction:ltr;display:inline-block">' +
      esc(j.symbol) + '</div> <span class="card-sub">' + esc(j.fa_name) + '</span>' +
      '<div style="margin-top:5px"><span class="pill ' + (j.reject_reason === 'VETO' ? 'red' : '') + '">' + esc(statusFa) + '</span>' +
      ((j.reject_reason === 'LOW_SCORE' || j.reject_reason === 'CAPPED')
        ? ' <span class="pill outline">' + O.faNum(j.score) + '/' + O.faNum(j.max_score) + '</span>' : '') +
      '</div></div>' +
      '<div class="card-sub" style="text-align:left">قیمت<br><b class="mono" style="color:var(--text);font-size:13px">' + esc(O.fmtPrice(j.price, j.pip)) + '</b></div></div>';

    if (j.vetoes && j.vetoes.length) {
      h += '<div style="margin-top:8px">';
      j.vetoes.forEach(function (v) {
        h += '<div class="veto-row"><span class="v-icon">🚫</span><div><div class="veto-title">' + esc(v.title_fa) + '</div><div class="veto-detail">' + esc(v.detail_fa) + '</div></div></div>';
      });
      h += '</div>';
    }
    if (j.reject_detail && j.reject_reason !== 'VETO') {
      h += '<div class="reject-why">' + (j.reject_reason === 'LOW_SCORE' ? '⏳ ' : '🔎 ') + esc(j.reject_detail) + '</div>';
    }
    if (j.reject_reason === 'LOW_SCORE' && j.evidences && j.evidences.length) {
      var got = j.evidences.filter(function (e) { return e.points > 0; }).map(function (e) { return e.label_fa; });
      var miss = j.evidences.filter(function (e) { return e.points === 0; }).map(function (e) { return e.label_fa; });
      h += '<div style="margin-top:8px;font-size:11px;line-height:2.1">' +
        (got.length ? '<div>✅ داشت: <span style="color:var(--text-2)">' + esc(got.join('، ')) + '</span></div>' : '') +
        (miss.length ? '<div>➖ نداشت: <span style="color:var(--text-2)">' + esc(miss.join('، ')) + '</span></div>' : '') +
        '</div>';
      h += scoreBar(j, minScore);
      h += evidencesHtml(j, id);
    } else if (j.reject_reason === 'NO_SETUP' && j.price) {
      // توضیح بیشتر بدون جدول مدارک (مدرکی حساب نشده)
    }
    return h + '</div>';
  }

  // ── تقویم ───────────────────────────────────────────────────
  O.renderCalendar = function (S) {
    var st = S.state;
    var nowMs = Date.now();
    var html = '<div class="page-title">🏦 تقویم اقتصادی</div>' +
      '<div class="page-sub">منبع: ForexFactory — فقط هفتهٔ جاری (شنبه تا جمعه). رویداد پراثر در ۳۰ دقیقهٔ آینده = وتوی سیگنال آن نماد.</div>';

    var cal = st && st.calSnap;
    if (!cal) {
      return html + '<div class="card"><div class="empty-state"><div class="e-ico">📡</div><div class="e-t">داده‌ای نیست</div><div class="e-s">اول «تحلیل تازه» را اجرا کن.</div></div></div>';
    }
    if (!cal.ok) {
      return html + '<div class="card"><div class="empty-state"><div class="e-ico">⚠️</div><div class="e-t">تقویم در دسترس نبود</div>' +
        '<div class="e-s">' + esc(String(cal.error || '').slice(0, 100)) + '<br>تحلیل تکنیکال بدون وتوی خبری انجام شده — با احتیاط بیشتری معامله کن.</div></div></div>';
    }
    if (cal.stale) {
      html += '<div class="warn-row">⚠️ این داده از کش قدیمی است (آخرین دریافت موفق: ' +
        esc(cal.fetchedAt ? O.faDate(new Date(cal.fetchedAt)) : '—') + ')</div>';
    }

    var horizon = +(S.cfg.fundamental.horizon_hours) || 48;
    var events = O.upcomingEvents(cal.events, nowMs, horizon, ['HIGH', 'MEDIUM', 'LOW']);
    var weekTxt = cal.weekRange && cal.weekRange[0] ? ' · پوشش هفتهٔ ' + O.faNum(cal.weekRange[0]) + ' تا ' + O.faNum(cal.weekRange[1]) : '';
    html += '<div class="card-sub" style="margin:-6px 2px 10px">' + O.faNum(cal.events.length) + ' رویداد در فید' + weekTxt + '</div>';

    if (!events.length) {
      var nHigh = cal.events.filter(function (e) { return e.impact === 'HIGH'; }).length;
      html += '<div class="card"><div class="empty-state"><div class="e-ico">✅</div>' +
        '<div class="e-t">رویدادی در ' + O.faNum(horizon) + ' ساعت آینده نیست</div>' +
        '<div class="e-s">پنجرهٔ معاملاتی از نظر تقویم باز است.<br>ℹ️ فید ForexFactory فقط هفتهٔ جاری را پوشش می‌دهد؛ در روزهای پایانی هفته ممکن است رویداد آینده‌ای در آن نباشد (یعنی «خبری نیست»، نه «داده خراب است»).<br>📊 کل این هفته ' + O.faNum(nHigh) + ' رویداد پراثر داشت.</div></div></div>';
      return html;
    }

    // فیلتر اثر
    html += '<div class="sym-meta" style="margin-bottom:12px">' +
      '<button class="pill ink cal-filter" data-impact="ALL">همه</button>' +
      '<button class="pill outline cal-filter" data-impact="HIGH">🔴 پراثر</button>' +
      '<button class="pill outline cal-filter" data-impact="MEDIUM">🟠 متوسط</button>' +
      '<button class="pill outline cal-filter" data-impact="LOW">🟢 کم‌اثر</button></div>';

    var lastDay = '';
    var shown = 0;
    events.forEach(function (e, i) {
      if (shown >= 40) return;
      shown++;
      var d = new Date(e.when);
      var dayKey = d.toISOString().slice(0, 10);
      var dayHtml = '';
      if (dayKey !== lastDay) {
        dayHtml = '<div class="day-head">' + esc(O.WEEKDAY_FA[O.pyWeekday(d)] + ' ' + O.faNum(d.getUTCDate()) + ' ' + O.MONTH_FA[d.getUTCMonth() + 1]) + '</div>';
        lastDay = dayKey;
      }
      var mins = O.evMinutesFrom(e, nowMs);
      dayHtml += '<div class="card ev-card" data-impact="' + e.impact + '">' +
        '<div class="ev-top"><span class="ev-time">' + O.faNum(O.hhmm(d)) + ' UTC</span>' +
        '<span class="countdown" data-cd-ts="' + e.when + '">' + esc(O.countdown2(mins)) + '</span></div>' +
        '<div class="ev-title">' + (O.IMPACT_EMOJI[e.impact] || '⚪') + ' ' + esc(e.title_fa) + '</div>' +
        '<div class="ev-title-en">' + esc(e.title) + '</div>' +
        '<div class="ev-meta"><span class="pill outline">' + esc(O.evCountryFa(e)) + ' (' + esc(e.country) + ')</span>' +
        '<span class="pill">' + esc(e.category) + '</span>' +
        (e.forecast ? '<span class="pill outline">پیش‌بینی: <b class="mono" style="margin-inline-start:4px">' + esc(O.faNum(e.forecast)) + '</b></span>' : '') +
        (e.previous ? '<span class="pill outline">قبلی: <b class="mono" style="margin-inline-start:4px">' + esc(O.faNum(e.previous)) + '</b></span>' : '') +
        '</div>' +
        '<button class="expand-toggle" data-expand="evx-' + i + '">تفسیر به زبان ساده <span>▾</span></button>' +
        '<div class="expand-body closed" id="evx-' + i + '"><div class="ev-explain">' +
        esc(O.evExplain(e, S.cfg.symbols, nowMs)).replace(/\n/g, '<br>') + '</div></div>' +
        '</div>';
      html += dayHtml;
    });
    if (shown >= 40) html += '<div class="hint" style="text-align:center">… و رویدادهای بیشتر (فقط ۴۰ مورد اول نمایش داده شد)</div>';
    return html;
  };

  // ── اخبار ───────────────────────────────────────────────────
  O.renderNews = function (S) {
    var st = S.state;
    var nowMs = Date.now();
    var html = '<div class="page-title">📰 اخبار بازار</div>' +
      '<div class="page-sub">رصد زندهٔ ForexLive، Investing.com و FXStreet با امتیازدهی جهت‌دار (۰ تا ۶).</div>';

    var ns = st && st.newsSnap;
    if (!ns) {
      return html + '<div class="card"><div class="empty-state"><div class="e-ico">📡</div><div class="e-t">داده‌ای نیست</div><div class="e-s">اول «تحلیل تازه» را اجرا کن.</div></div></div>';
    }
    html += '<div class="card-sub" style="margin:-6px 2px 10px">' +
      O.faNum(ns.items.length) + ' خبر مرتبط · ' + O.faNum(ns.feedsOk) + ' فید موفق' +
      (ns.feedsFailed ? ' · ' + O.faNum(ns.feedsFailed) + ' ناموفق' : '') + '</div>';

    if (!ns.ok) {
      return html + '<div class="card"><div class="empty-state"><div class="e-ico">⚠️</div><div class="e-t">خبری پیدا نشد</div>' +
        '<div class="e-s">' + esc(ns.error || '') + (ns.failedNames && ns.failedNames.length ? '<br>فیدهای ناموفق: ' + esc(ns.failedNames.join('، ')) : '') + '</div></div></div>';
    }

    var brCount = ns.items.filter(function (i) { return i.breaking; }).length;
    if (brCount) {
      html += '<div class="warn-row" style="background:var(--red-tint);border-color:#EBC9C9;color:var(--red-text)">🚨 ' +
        O.faNum(brCount) + ' خبر فوری در این بازه — تا آرام‌شدن بازار، ورود جدید با احتیاط شدید</div>';
    }

    ns.items.forEach(function (it, i) {
      var dots = '';
      for (var d = 0; d < 6; d++) dots += '<i class="' + (d < it.score ? 'on' : '') + '"></i>';
      var age = it.published ? O.countdown2(-(nowMs - it.published) / 60000) : '';
      html += '<div class="card news-card">' +
        '<div class="news-title">' + (it.breaking ? '<span class="breaking-flag">🚨 فوری</span> ' : '') +
        (it.link ? '<a href="#" data-ext="' + esc(it.link) + '">' + esc(it.title) + '</a>' : esc(it.title)) +
        (it.roundup ? ' <span class="pill" style="font-size:9px">📚 جمع‌بندی — جهت‌دار نیست</span>' : '') + '</div>' +
        '<div class="news-meta"><span class="score-dots" title="امتیاز اهمیت">' + dots + '</span>' +
        '<span class="news-src">' + O.faNum(it.score) + '/۶</span>' +
        (O.newsDirectionFa(it) ? '<span class="dir-chip">' + esc(O.newsDirectionFa(it)) + '</span>' : '') +
        '<span class="news-src">' + esc(it.source) + (age ? ' · ' + esc(age) : '') + '</span></div>' +
        (it.keywords && it.keywords.length ? '<div class="news-meta" style="margin-top:5px">' +
          it.keywords.map(function (k) { return '<span class="kw-chip">' + esc(k) + '</span>'; }).join('') + '</div>' : '') +
        '</div>';
    });

    if (ns.staleFeeds && ns.staleFeeds.length) {
      html += '<div class="hint">ℹ️ فیدهای بدون خبر تازه: ' + esc(ns.staleFeeds.slice(0, 3).join('، ')) + '</div>';
    }
    html += '<div class="hint" style="margin-top:8px">⚠️ جهت‌دهی اخبار بر پایهٔ کلیدواژه است (سرنخ، نه حکم قطعی) — در داور امتیازدهی فقط ۱ امتیاز از ۱۱ وزن دارد.</div>';
    return html;
  };

  // ── ژورنال ──────────────────────────────────────────────────
  O.renderJournal = function (S) {
    var stats = S.stats;
    var entries = S.journal ? S.journal.load() : [];
    var html = '<div class="page-title">📔 ژورنال و کارنامهٔ دقت</div>' +
      '<div class="page-sub">حلقهٔ صداقت: نتیجهٔ هر سیگنال از روی کندل‌های ۱۵ دقیقه تعیین و اینجا ثبت می‌شود — با قاعدهٔ محتاطانهٔ «برخورد هر دو سطح = ضرر».</div>';

    if (!entries.length) {
      html += '<div class="card"><div class="empty-state"><div class="e-ico">📔</div><div class="e-t">ژورنال خالی است</div>' +
        '<div class="e-s">هر سیگنالی که داور صادر کند اینجا ثبت و نتیجه‌اش پیگیری می‌شود. فعلاً سیگنالی نبوده — این یعنی سیستم وعدهٔ الکی نداده 🙂</div></div></div>';
      return html;
    }

    var o = stats.overall;
    html += '<div class="card ink">' +
      '<div class="card-row"><div class="ink-title">📊 کارنامهٔ کلی</div>' +
      '<span class="pill on-ink">باز: ' + O.faNum(stats.open_count) + '</span></div>' +
      '<div class="ink-tiles">' +
      '<div class="ink-tile"><div class="t-num">' + O.faNum(o.closed) + '</div><div class="t-cap">بسته‌شده</div></div>' +
      '<div class="ink-tile"><div class="t-num" style="color:#7BE0B0">' + O.faNum(o.wins) + '</div><div class="t-cap">برد 🎯</div></div>' +
      '<div class="ink-tile"><div class="t-num" style="color:#FF9A9A">' + O.faNum(o.losses) + '</div><div class="t-cap">باخت 🛑</div></div>' +
      '<div class="ink-tile"><div class="t-num">' + O.faNum(o.expired) + '</div><div class="t-cap">منقضی ⏳</div></div>' +
      '</div>' +
      '<div class="ink-tiles" style="margin-top:8px">' +
      '<div class="ink-tile"><div class="t-num">' + O.faPct(o.hit_rate) + '</div><div class="t-cap">نرخ برد (قطعی)</div></div>' +
      '<div class="ink-tile"><div class="t-num">' + O.faPct(o.closed_win_rate) + '</div><div class="t-cap">نرخ برد محتاطانه</div></div>' +
      '<div class="ink-tile"><div class="t-num">' + O.rFmt(o.avg_r) + '</div><div class="t-cap">میانگین R (انتظار)</div></div>' +
      '</div>' +
      '<div class="stat-defs">نرخ برد (قطعی) = برد ÷ (برد+باخت) · محتاطانه = برد ÷ کل بسته‌شده‌ها (منقضی «نبرد» شمرده می‌شود) · میانگین R = انتظار ریاضی هر سیگنال بسته. هر سه گزارش می‌شود تا عدد واحدی گمراه‌کننده نباشد.</div>' +
      '</div>';

    // هفتهٔ جاری در برابر قبل
    if (stats.this_week_key && stats.by_week[stats.this_week_key]) {
      var tw = stats.by_week[stats.this_week_key];
      var lw = stats.last_week_key ? stats.by_week[stats.last_week_key] : null;
      html += '<div class="card"><div class="card-title">🗓️ امسال — هفتهٔ ' + esc(O.faNum(stats.this_week_key.slice(-2))) + '</div>' +
        '<div style="font-size:11.5px;color:var(--text-2);margin-top:6px">' +
        'بسته ' + O.faNum(tw.closed) + ' · برد ' + O.faNum(tw.wins) + ' · باخت ' + O.faNum(tw.losses) + ' · نرخ برد ' + O.faPct(tw.hit_rate) + ' · میانگین R ' + O.rFmt(tw.avg_r) +
        (lw ? '<br>هفتهٔ قبل: بسته ' + O.faNum(lw.closed) + ' · نرخ برد ' + O.faPct(lw.hit_rate) + ' · میانگین R ' + O.rFmt(lw.avg_r) : '') +
        '</div></div>';
    }

    // سیگنال‌های باز
    var open = entries.filter(function (e) { return e.outcome == null; });
    if (open.length) {
      html += '<div class="card"><div class="card-title">⏳ سیگنال‌های باز (' + O.faNum(open.length) + ')</div><div style="margin-top:6px">';
      open.forEach(function (e) {
        html += '<div class="j-entry"><div class="j-sym"><div class="s1">' + esc(e.symbol) + ' · ' +
          (e.direction === 'BUY' ? '🟢 خرید' : '🔴 فروش') + '</div>' +
          '<div class="s2">ورود ' + esc(O.fmtPrice(e.entry, e.pip)) + ' · SL ' + esc(O.fmtPrice(e.sl, e.pip)) + ' · TP ' + esc(O.fmtPrice(e.tp, e.pip)) + ' · ' + esc(agoFa(e.ts)) + '</div></div>' +
          '<span class="pill outline">' + O.faNum(e.score) + '/' + O.faNum(e.max_score) + '</span></div>';
      });
      html += '</div></div>';
    }

    // بسته‌شده‌ها
    var closed = entries.filter(function (e) { return e.outcome != null; }).slice(-30).reverse();
    if (closed.length) {
      html += '<div class="card"><div class="card-title">🏁 آخرین نتایج</div><div style="margin-top:6px">';
      closed.forEach(function (e) {
        var cls = e.outcome === 'TP' ? 'win' : (e.outcome === 'SL' ? 'loss' : 'exp');
        var ico = e.outcome === 'TP' ? '🎯' : (e.outcome === 'SL' ? '🛑' : '⏳');
        html += '<div class="j-entry"><div class="j-sym"><div class="s1">' + esc(e.symbol) + ' · ' +
          (e.direction === 'BUY' ? '🟢' : '🔴') + '</div>' +
          '<div class="s2">' + ico + ' ' + esc(O.OUTCOME_FA[e.outcome] || e.outcome) + ' · ' + esc(agoFa(e.ts)) +
          (e.note ? ' — ' + esc(e.note) : '') + '</div></div>' +
          '<span class="r-chip ' + cls + '">' + O.rFmt(e.r) + '</span></div>';
      });
      html += '</div></div>';
    }

    // به تفکیک نماد
    var symKeys = Object.keys(stats.by_symbol);
    if (symKeys.length) {
      html += '<div class="card"><button class="expand-toggle" data-expand="j-syms" style="padding-top:0">📈 تفکیک نمادها <span>▾</span></button>' +
        '<div class="expand-body closed" id="j-syms" style="width:100%">';
      symKeys.sort().forEach(function (k) {
        var b = stats.by_symbol[k];
        html += '<div class="j-entry"><div class="j-sym"><div class="s1">' + esc(k) + '</div>' +
          '<div class="s2">بسته ' + O.faNum(b.closed) + ' · برد ' + O.faNum(b.wins) + ' · باخت ' + O.faNum(b.losses) + ' · منقضی ' + O.faNum(b.expired) + '</div></div>' +
          '<span class="r-chip ' + ((b.avg_r || 0) >= 0 ? 'win' : 'loss') + '">' + O.rFmt(b.avg_r) + '</span></div>';
      });
      html += '</div></div>';
    }

    html += '<div class="action-row" style="margin-top:4px">' +
      '<button class="btn ghost sm" data-action="journal-export" style="flex:1">📤 خروجی JSONL</button>' +
      '<button class="btn red sm" data-action="journal-clear" style="flex:1">🗑️ پاک‌کردن ژورنال</button></div>';
    return html;
  };

  // ── تنظیمات ─────────────────────────────────────────────────
  function switchHtml(key, on) {
    return '<label class="switch"><input type="checkbox" data-set="' + key + '"' + (on ? ' checked' : '') + '>' +
      '<span class="track"></span><span class="knob"></span></label>';
  }

  O.renderSettings = function (S) {
    var set = S.settings;
    var v = S.cfg.judge.veto;
    var html = '<div class="page-title">⚙️ تنظیمات</div>' +
      '<div class="page-sub">تغییرها فوری ذخیره می‌شوند و در تحلیل بعدی اثر می‌کنند.</div>';

    html += '<div class="card"><div class="section-title" style="margin-top:0">👤 شخصی</div>' +
      '<div class="set-row"><div><div class="set-label">نام نمایشی</div><div class="set-sub">در خوش‌آمدگویی و هدر استفاده می‌شود</div></div></div>' +
      '<input class="text-input" data-set="user_name" value="' + esc(set.user_name) + '" maxlength="24">' +
      '</div>';

    html += '<div class="card"><div class="section-title" style="margin-top:0">⚖️ داور امتیازدهی</div>' +
      '<div class="set-row"><div><div class="set-label">داور فعال است</div><div class="set-sub">خاموش = هیچ سیگنالی داوری/صادر نمی‌شود</div></div>' + switchHtml('judge_enabled', set.judge_enabled) + '</div>' +
      '<div class="set-row"><div><div class="set-label">آستانهٔ صدور سیگنال</div><div class="set-sub">حداکثر ممکن ۱۱ امتیاز است — پیش‌فرض ۷</div></div>' +
      '<span class="stepper"><button data-step="min_score:-1">−</button><span class="val">' + O.faNum(set.min_score) + '</span><button data-step="min_score:1">+</button></span></div>' +
      '</div>';

    html += '<div class="card"><div class="section-title" style="margin-top:0">🚫 دروازه‌های وتو</div><div class="hint" style="margin-bottom:6px">وتوها بدون استثنا هستند: حتی با امتیاز کامل، سیگنال صادر نمی‌شود.</div>' +
      row('weekend', '🔒 بازار بسته', 'شنبه/یکشنبه و جمعه بعد از ۲۱ UTC', v.weekend) +
      row('high_impact_event', '📅 رویداد پراثر تقویم', 'رویداد پراثر تا ۳۰ دقیقهٔ آینده', v.high_impact_event) +
      row('timeframe_conflict', '🔀 تضاد تایم‌فریم', 'H4 و H1 هم‌جهت نباشند', v.timeframe_conflict) +
      row('range_market', '😴 بازار بی‌روند', 'ADX زیر آستانهٔ ۲۰', v.range_market) +
      row('volatility_spike', '📈 جهش غیرعادی نوسان', 'ATR فعلی بیش از ۲ برابر میانگین', v.volatility_spike) +
      row('breaking_news', '🚨 خبر فوری', 'خبر فوری مرتبط با نماد', v.breaking_news) +
      '</div>';

    html += '<div class="card"><div class="section-title" style="margin-top:0">🔌 موتورها</div>' +
      row('fund_enabled', '🏦 تقویم اقتصادی', 'ForexFactory — کش ۳۰ دقیقه‌ای', set.fund_enabled) +
      row('news_enabled', '📰 موتور اخبار', 'RSS فارکس — دریافت زنده در هر تحلیل', set.news_enabled) +
      row('tv_enabled', '🔍 تاییدیهٔ تریدینگ‌ویو', 'API غیررسمی — اگر قطع شد، مدرک ❔ می‌گیرد', set.tv_enabled) +
      '</div>';

    html += '<div class="card"><div class="section-title" style="margin-top:0">🗄️ داده‌ها</div>' +
      '<div class="set-row"><div><div class="set-label">پاک‌کردن کش تقویم و تحلیل</div><div class="set-sub">دادهٔ بازار دفعهٔ بعد تازه دریافت می‌شود</div></div>' +
      '<button class="btn ghost sm" data-action="clear-cache">پاک‌کردن</button></div>' +
      '<div class="set-row"><div><div class="set-label">بازنشانی تنظیمات</div><div class="set-sub">همه به حالت پیش‌فرض برمی‌گردند (ژورنال پاک نمی‌شود)</div></div>' +
      '<button class="btn ghost sm" data-action="reset-settings">بازنشانی</button></div>' +
      '</div>';

    html += '<div class="card ink"><div class="ink-title">دربارهٔ دستیار اودین</div>' +
      '<div class="ink-cap" style="margin-top:6px;line-height:2.2">نسخهٔ اندروید ' + O.faNum(S.version || '0.9.0') + ' — همراه نسخهٔ ویندوز (0.8.0)<br>' +
      '⚠️ <b style="color:#fff">غیرخودکار:</b> این اپ هیچ معامله‌ای انجام نمی‌دهد و به هیچ بروکری وصل نیست. فقط تحلیل، سیگنال پیشنهادی و پیگیری صداقتِ نتایج.<br>' +
      'هیچ سیستمی سود را تضمین نمی‌کند؛ مسئولیت هر معامله با خودت است.</div></div>';
    return html;

    function row(key, label, sub, on) {
      return '<div class="set-row"><div><div class="set-label">' + label + '</div><div class="set-sub">' + sub + '</div></div>' +
        switchHtml('veto.' + key, on !== false) + '</div>';
    }
  };

  // ── بریفینگ ─────────────────────────────────────────────────
  O.renderBriefingPage = function (S) {
    var html = '<div class="action-row"><button class="btn ghost" data-tab="home">→ بازگشت</button>' +
      '<button class="btn primary" data-action="analyze">⟳ تحلیل تازه</button></div>';
    if (!S.state || !S.state.analyses || !S.state.analyses.length) {
      return html + '<div class="card"><div class="empty-state"><div class="e-ico">🌅</div><div class="e-t">اول تحلیل را اجرا کن</div><div class="e-s">بریفینگ از نتیجهٔ آخرین تحلیل ساخته می‌شود.</div></div></div>';
    }
    var lines = O.renderBriefing(S.state, S.cfg, S.state.ranAt);
    html += '<div class="card">';
    lines.forEach(function (ln) {
      var cls = 'brief-line';
      if (ln.startsWith('▎')) cls += ' head';
      else if (ln.startsWith('🌅')) cls += ' title';
      html += '<div class="' + cls + '">' + esc(ln).replace(/^▎/, '') + '</div>';
    });
    html += '</div>';
    return html;
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
