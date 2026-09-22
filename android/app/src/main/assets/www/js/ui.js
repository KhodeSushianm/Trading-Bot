/* رندر صفحه‌ها — تم روشن شیشه‌ای، مونوکروم + سبز/قرمز معنایی فقط.
 * همهٔ متن‌ها فارسی؛ قیمت‌ها لاتین، شمارش‌ها فارسی (قرارداد src/fa.py).
 *
 * v0.13.0 — ایموجی حذف شد: همه‌جا آیکون SVG (js/icons.js).
 * رشته‌های موتور (judge/technical/calendar/session/journal/briefing) به‌خاطر
 * تست parity دست‌نخورده‌اند؛ ایموجی‌هایشان در همین لایه با O.icoStr به آیکون
 * تبدیل می‌شود. */
(function (O) {
  'use strict';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  O.esc = esc;

  // متن esc‌شدهٔ موتور → HTML با آیکون (ترتیب مهم: اول esc بعد icoStr)
  function eico(s, size) { return O.icoStr(esc(s), size); }

  // عنوان صفحه/کارت/بخش با آیکون
  function pt(icon, text) {
    return '<div class="page-title">' + O.ico(icon, 20) + '<span>' + text + '</span></div>';
  }
  function ct(icon, text, size) {
    return O.ico(icon, size || 15) + '<span>' + text + '</span>';
  }

  // رشته‌های موتور (وتو/سشن) عمداً UTC می‌مانند (تست parity با پایتون)؛
  // اینجا فقط معادل تهران به متن «بسته» اضافه می‌شود — تبدیل نمایشی.
  // ۲۲:۰۰ UTC = ۰۱:۳۰ تهران · ۲۱:۰۰ UTC = ۰۰:۳۰ تهران (بدون ساعت تابستانی)
  function tehranize(txt) {
    return String(txt == null ? '' : txt)
      .replace('ساعت 22:۰۰ UTC', 'ساعت 22:۰۰ UTC — ۰۱:۳۰ بامداد دوشنبه تهران')
      .replace('ساعت 21:۰۰ UTC', 'ساعت 21:۰۰ UTC — ۰۰:۳۰ بامداد شنبه تهران');
  }
  O.tehranize = tehranize;

  var VERDICT_CHIP = {
    BUY_SETUP: ['buy', 'dot-low', 'ستاپ خرید'],
    SELL_SETUP: ['sell', 'dot-high', 'ستاپ فروش'],
    WAIT: ['wait', 'hourglass', 'انتظار'],
    RANGE: ['range', 'moon', 'رنج'],
    DATA: ['data', 'alert', 'دادهٔ ناقص']
  };

  var IMPACT_ICO = {
    HIGH: ['dot-high', 'c-red'],
    MEDIUM: ['dot-med', 'c-amber'],
    LOW: ['dot-low', 'c-green']
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
      '<i class="dot"></i>' + eico(st.open ? st.label : st.reason_fa, 12) + '</span>';
  };

  // ── خانه ────────────────────────────────────────────────────
  O.renderHome = function (S) {
    var st = S.state;
    var cfg = S.cfg;
    var html = '';

    html += '<div class="action-row">' +
      '<button class="btn primary" data-action="analyze" id="btn-analyze">' + O.ico('refresh', 16) + ' تحلیل تازه</button>' +
      '<button class="btn ghost" data-action="briefing">' + O.ico('sunrise', 16) + ' بریفینگ</button>' +
      '</div>';
    if (S.settings && S.settings.auto_refresh_enabled) {
      var bgOn = O.native && O.native.bgRunning && O.native.bgRunning();
      html += '<div class="card-sub" style="margin:-4px 2px 10px">' + O.ico('refresh', 12) +
        ' تازه‌سازی خودکار هر ' + O.faNum(S.settings.auto_refresh_min || 15) + ' دقیقه — ' +
        (bgOn ? 'رصد پس‌زمینه فعال است (بدون باز کردن اپ هم سیگنال می‌رسد)' : 'فقط وقتی اپ باز و بازار فعال است') +
        (S.settings.notify_enabled === false ? '' : ' · ' + O.ico('bell', 11) + ' اعلان سیگنال روشن') + '</div>';
    }

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
      '<div class="ink-title">' + (status.open
        ? O.ico('dot', 10, 'c-green-lt') + '<span>' + eico(status.label, 13) + '</span>'
        : '<span>' + eico(status.reason_fa, 14) + '</span>') + '</div>' +
      '<div class="ink-cap" style="margin-top:3px">' + (status.open && status.sessions.length ? 'سشن‌های فعال: ' + esc(status.sessions.join(' + ')) : 'بازار فارکس ۲۴ ساعته، ۵ روز در هفته') + '</div>' +
      (status.open ? '' : '<div class="ink-cap" style="margin-top:3px">' + eico(O.tehranMarketHint(status), 11) + '</div>') +
      '</div><div style="text-align:left"><div class="ink-num" id="ink-clock">' + O.faNum(O.hhmmTeh(new Date(nowMs))) + '</div><div class="ink-cap">تهران</div>' +
      '<div class="ink-cap" id="ink-jalali" style="margin-top:4px">' + esc(O.jalaliFa(new Date(nowMs))) + '</div></div></div>' +
      '<div class="ink-tiles">' +
      '<div class="ink-tile"><div class="t-num">' + O.faNum(sigCount) + '</div><div class="t-cap">سیگنال چرخهٔ آخر</div></div>' +
      '<div class="ink-tile"><div class="t-num">' + O.faNum(breaking) + '</div><div class="t-cap">خبر فوری</div></div>' +
      '<div class="ink-tile"><div class="t-num">' + (hi24 === null ? O.ico('unknown', 17) : O.faNum(hi24)) + '</div><div class="t-cap">رویداد پراثر ۲۴ساعت</div></div>' +
      '</div></div>';

    if (!st) {
      html += '<div class="card"><div class="empty-state">' +
        '<div class="e-ico">' + O.ico('antenna', 40) + '</div><div class="e-t">هنوز تحلیلی اجرا نشده</div>' +
        '<div class="e-s">دکمهٔ «تحلیل تازه» را بزن تا قیمت‌ها، تقویم اقتصادی و اخبار دریافت شود و داور امتیازدهی تصمیم بگیرد.<br>اولین تحلیل کمی طول می‌کشد (دریافت ۷ نماد).</div>' +
        '</div></div>';
      html += skeletonCards(3);
      return html;
    }

    // کارت نمادها
    (st.analyses || []).forEach(function (a) {
      var chip = VERDICT_CHIP[a.verdict] || ['wait', 'hourglass', a.verdict];
      var spark = sparkline((st.sparks || {})[a.symbol]);
      html += '<div class="card sym-card">' +
        '<div class="sym-head"><div>' +
        '<div class="sym-name">' + esc(a.symbol.length === 6 ? a.symbol.slice(0, 3) + '/' + a.symbol.slice(3) : a.symbol) + '</div>' +
        '<div class="sym-fa">' + esc(a.fa_name) + '</div>' +
        '</div>' + spark + '</div>' +
        '<div class="card-row" style="align-items:flex-end">' +
        '<div class="sym-price">' + esc(O.fmtPrice(a.price, a.pip)) + '</div>' +
        '<span class="pill verdict-chip ' + chip[0] + '">' + O.ico(chip[1], 9) + ' ' + esc(chip[2]) + '</span>' +
        '</div>' +
        '<div class="sym-meta" style="margin-top:6px">' +
        '<span class="pill outline">روند ۴ساعته: ' + eico(O.TREND_FA[a.trend], 12) + '</span>' +
        (a.h1_agrees
          ? '<span class="pill">H1 هم‌جهت ' + O.ico('check', 11, 'c-green') + '</span>'
          : '<span class="pill red">H1 ناهم‌جهت ' + O.ico('minus', 11) + '</span>') +
        '</div>' +
        '<div class="sym-stats">' +
        '<span class="sym-stat">ADX <b>' + O.faNum(a.adx.toFixed(0)) + '</b></span>' +
        '<span class="sym-stat">RSI <b>' + O.faNum(a.rsi.toFixed(0)) + '</b> ' + O.ico(a.rsi_rising ? 'arrow-up-right' : 'arrow-down-right', 10, a.rsi_rising ? 'c-green' : 'c-red') + '</span>' +
        '<span class="sym-stat">ATR <b>' + esc(O.faPips(a.atr, a.pip, a.pip >= 0.5)) + '</b></span>' +
        '</div>' +
        ((a.support || a.resistance) ? '<div class="sym-stats">' +
          (a.support ? '<span class="sym-stat">حمایت <b>' + esc(O.fmtPrice(a.support, a.pip)) + '</b></span>' : '') +
          (a.resistance ? '<span class="sym-stat">مقاومت <b>' + esc(O.fmtPrice(a.resistance, a.pip)) + '</b></span>' : '') +
          '</div>' : '') +
        '<div style="margin-top:9px;display:flex;gap:6px">' +
          '<button class="btn subtle" data-chart-open="' + esc(a.symbol) + '"' +
            ' style="padding:5px 12px;font-size:10.5px">' + O.ico('chart-line', 11) + ' نمودار</button>' +
          '<button class="btn subtle" data-alert-add="' + esc(a.symbol) + '"' +
            ' style="padding:5px 12px;font-size:10.5px">' + O.ico('bell', 11) + ' هشدار قیمت</button>' +
        '</div>' +
        '</div>';
    });

    // قدرت ارزها
    if (st.ranking && st.ranking.length) {
      var maxAbs = Math.max.apply(null, st.ranking.map(function (x) { return Math.abs(x[1]); })) || 1;
      html += '<div class="card"><div class="card-title">' + ct('exchange', 'جریان قدرت ارزها') + '</div>' +
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
          '<div><div class="card-title">' + ct('calendar', 'رویداد پراثر بعدی') + '</div>' +
          '<div style="font-size:12px;font-weight:500;margin-top:2px">' + esc(nxt.title_fa) + '</div>' +
          '<div class="card-sub">' + esc(O.evCountryFa(nxt)) + ' — ' + O.faNum(O.hhmmTeh(new Date(nxt.when))) + ' تهران</div></div>' +
          '<div style="text-align:left"><div class="countdown" data-cd-ts="' + nxt.when + '">' + esc(O.countdown2(O.evMinutesFrom(nxt, nowMs))) + '</div></div>' +
          '</div></div>';
      } else {
        html += '<div class="card"><div class="card-title">' + ct('calendar', 'رویداد پراثری پیش رو نیست') + '</div>' +
          '<div class="card-sub">تا پایان پوشش فید این هفته، رویداد پراثری باقی نمانده — پنجرهٔ معاملاتی از نظر تقویم باز است</div></div>';
      }
    }

    // تیترهای مهم اخبار
    if (st.newsSnap && st.newsSnap.ok && st.newsSnap.items.length) {
      html += '<div class="card"><div class="card-row"><div class="card-title">' + ct('news', 'تیترهای مهم') + '</div>' +
        '<button class="btn subtle" data-tab="news">همه ' + O.ico('chevron-left', 13) + '</button></div><div style="margin-top:6px">';
      st.newsSnap.items.slice(0, 3).forEach(function (it) {
        html += '<div style="padding:7px 0;border-bottom:1px solid var(--divider)">' +
          (it.breaking ? '<span class="breaking-flag">' + O.ico('siren', 11) + ' فوری</span> ' : '') +
          '<span style="font-size:12px;font-weight:500;line-height:1.9">' + esc(it.title) + '</span>' +
          '<div class="news-src">' + esc(it.source) + ' · ' + esc(O.faNum(it.score)) + '/۶' +
          (O.newsDirectionFa(it) ? ' · ' + eico(O.newsDirectionFa(it), 10) : '') + '</div></div>';
      });
      html += '</div></div>';
    }

    // خلاصهٔ ژورنال
    var stats = S.stats;
    if (stats && stats.overall.closed > 0) {
      html += '<div class="card ink" data-tab="journal" style="cursor:pointer">' +
        '<div class="card-row"><div class="ink-title">' + ct('book', 'کارنامهٔ دقت') + '</div>' +
        '<span class="pill on-ink">لمس کن ' + O.ico('chevron-left', 11) + '</span></div>' +
        '<div class="ink-tiles">' +
        '<div class="ink-tile"><div class="t-num">' + O.faPct(stats.overall.hit_rate) + '</div><div class="t-cap">نرخ برد (قطعی)</div></div>' +
        '<div class="ink-tile"><div class="t-num">' + O.rFmt(stats.overall.avg_r) + '</div><div class="t-cap">میانگین R</div></div>' +
        '<div class="ink-tile"><div class="t-num">' + O.faNum(stats.open_count) + '</div><div class="t-cap">سیگنال باز</div></div>' +
        '</div></div>';
    }

    // هشدارهای قیمت (v0.16.0)
    var alerts = (S.storage && O.alertsLoad) ? O.alertsLoad(S.storage) : [];
    if (alerts.length) {
      html += '<div class="card"><div class="card-title">' + ct('bell', 'هشدارهای قیمت (' + O.faNum(alerts.length) + ')') + '</div>' +
        '<div class="card-sub">با هر چرخهٔ تحلیل بررسی می‌شوند — حتی وقتی اپ بسته است (رصد پس‌زمینه)</div>' +
        '<div style="margin-top:6px">';
      alerts.forEach(function (al) {
        var pair = String(al.symbol).length === 6 ? al.symbol.slice(0, 3) + '/' + al.symbol.slice(3) : al.symbol;
        html += '<div class="j-entry"><div class="j-sym">' +
          '<div style="font-size:12.5px;font-weight:700">' + esc(pair) + ' — ' +
          (al.dir === 'above'
            ? O.ico('arrow-up', 10, 'c-green') + ' عبور به بالای '
            : O.ico('arrow-down', 10, 'c-red') + ' عبور به زیر ') +
          '<b class="mono">' + esc(O.fmtPrice(al.price, al.pip)) + '</b></div>' +
          '<div class="s2">' + (al.sticky ? 'تکرارشونده (حداکثر ساعتی یک‌بار) · ' : '') +
          'ثبت ' + esc(agoFa(Date.parse(al.created_at))) + '</div></div>' +
          '<button class="icon-btn del" data-alert-del="' + esc(al.id) + '" title="حذف هشدار">' + O.ico('trash', 14) + '</button></div>';
      });
      html += '</div></div>';
    }

    // پاصفحه
    html += '<div class="hint" style="text-align:center;padding:4px 10px 10px">' +
      'آخرین تحلیل: ' + esc(agoFa(st.ranAt)) + ' · منبع: Yahoo Finance' +
      (st.errors ? ' · ' + O.faNum(st.errors) + ' خطای دریافت داده' : '') + '<br>' +
      O.ico('seal', 11) + ' این اپ غیرخودکار است: هیچ معامله‌ای انجام نمی‌دهد، فقط تحلیل می‌کند.' +
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
    var html = pt('scale', 'داور امتیازدهی') +
      '<div class="page-sub">آستانهٔ صدور سیگنال: ' + O.faNum(minScore) + ' از ۱۱ امتیاز — اول دروازه‌های وتو، بعد جدول مدارک. «چرا سیگنال نشد» هم خروجی معتبر است.</div>';

    if (S.cfg.judge.enabled === false) {
      return html + '<div class="card"><div class="empty-state"><div class="e-ico">' + O.ico('gear', 40) + '</div><div class="e-t">داور خاموش است</div><div class="e-s">از تنظیمات فعالش کن.</div></div></div>';
    }
    if (!st || !st.judgments || !st.judgments.length) {
      return html + '<div class="card"><div class="empty-state"><div class="e-ico">' + O.ico('antenna', 40) + '</div><div class="e-t">هنوز داوری انجام نشده</div><div class="e-s">اول «تحلیل تازه» را از صفحهٔ خانه اجرا کن.</div></div></div>';
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
      html += '<div class="card ink"><div class="ink-title">' + O.ico('no-entry', 15) + '<span>هیچ سیگنالی صادر نشد — و این خودش یک خروجی معتبر است.</span></div>' +
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

  // آیکون مدرک از وضعیت خود مدرک (نه ایموجی موتور) — رنگ معنایی
  function evIconHtml(e) {
    if (e.points > 0) return O.ico('check-circle', 15, 'c-green');
    if (e.unavailable) return O.ico('unknown', 15);
    return O.ico('minus', 15);
  }

  function evidencesHtml(j, id) {
    var h = '<button class="expand-toggle" data-expand="' + id + '">جدول مدارک (۸ مدرک) <span>' + O.ico('chevron-down', 12) + '</span></button>' +
      '<div class="expand-body closed" id="' + id + '">';
    var sorted = j.evidences.slice().sort(function (a, b) { return (b.points - a.points) || (a.key < b.key ? -1 : 1); });
    sorted.forEach(function (e) {
      h += '<div class="ev-row' + (e.unavailable ? ' unavail' : '') + '">' +
        '<span class="ev-icon">' + evIconHtml(e) + '</span><div>' +
        '<span class="ev-label">' + esc(e.label_fa) + '</span>' +
        '<span class="ev-pts">(' + (e.points > 0 ? '+' + O.faNum(e.points) : O.faNum(0) + ' از ' + O.faNum(e.max_points)) + ')</span>' +
        '<div class="ev-detail">' + eico(e.detail_fa, 11) + '</div></div></div>';
    });
    return h + '</div>';
  }

  /* کارت سیگنال — v0.21.0 به زبان بصری Aurora Glass 2.0 ارتقا یافت.
   *
   * ⚠️ تصمیم طراحی (مستند چون وسوسه‌انگیز است که اشتباه شود):
   *   SignalCard دسکتاپ را «کامل» جایگزین نکردیم. کارت اندروید از قبل
   *   اطلاعاتی داشت که دسکتاپ ندارد (scoreBar با نشانگر آستانه، جدول ۸ مدرک،
   *   ATR، ریسک پیشنهادی، هشدار سیگنال تکراری). جایگزینیِ کامل = رگرسیون
   *   اطلاعاتی. پس: ساختار ردیف‌های ۱..۵ از دسکتاپ گرفته شد (O.signalCard)
   *   و بخش‌های غنی‌ترِ اندروید سر جایشان ماندند.
   * آنچه حذف شد فقط «تکراری‌ها» بودند: dir-pill (→ چیپ جهت)، .levels
   * (→ کاشی‌های sc-tiles با همان فاصلهٔ پیپ)، pill ریسک‌به‌ریوارد (→ ردیف ۳). */
  function signalCard(j, minScore, idx) {
    var s = j.signal;
    var id = 'ev-sig-' + idx;
    var h = '<div class="card sig-card">';

    // ردیف‌های ۱..۵ (چیپ جهت/ارسال/امتیاز، ستاره‌ها، جفت‌ارز، سشن، R:R،
    // کاشی‌های ورود/SL/TP با فاصلهٔ پیپ، دلایل پارس‌شده) — همه از components.js
    h += O.signalCard(s, { sub: true, showWarns: false });

    if (s._dup) {
      h += '<div class="reject-why" style="margin-top:8px">' + O.ico('repeat', 13) + ' ' + esc(s._dupWhy) + '</div>';
    }

    h += scoreBar(j, minScore);

    h += '<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">' +
      '<button class="btn subtle" data-chart-sig="' + esc(s.symbol) + '"' +
      ' style="padding:5px 12px;font-size:10.5px">' + O.ico('chart-line', 12) + ' نمایش روی نمودار</button>' +
      '<button class="btn subtle" data-share-img="' + idx + '"' +
      ' style="padding:5px 12px;font-size:10.5px">' + O.ico('share', 12) + ' اشتراک تصویر</button></div>';

    h += '<div class="sym-meta" style="margin-top:8px">' +
      O.chip('ATR: ' + O.faPips(s.atr, s.pip, s.is_gold), 'outline', { icon: 'wave', iconSize: 11 }) +
      O.chip('ریسک پیشنهادی: حداکثر ۱٪', 'outline', { icon: 'coins', iconSize: 11 }) + '</div>';

    (s.warnings || []).forEach(function (w) { h += '<div class="warn-row">' + O.ico('alert', 12, 'c-amber') + ' ' + eico(w, 12) + '</div>'; });

    h += evidencesHtml(j, id);

    // متن کامل سیگنال → کنسول‌کارت تیره با قرص زمان و دکمهٔ کپی
    // (همتای «متن کامل» در SignalCard دسکتاپ)
    var stamp = s.now ? O.faDateTeh(new Date(s.now)) : '';
    h += '<button class="expand-toggle" data-expand="sigfull-' + idx + '">متن کامل سیگنال <span>' +
      O.ico('chevron-down', 12) + '</span></button>' +
      '<div class="expand-body closed" id="sigfull-' + idx + '" style="width:100%">' +
      O.consoleCard({
        id: 'sig-cc-' + idx, title: 'متن کامل سیگنال', sub: esc(s.symbol),
        icon: 'news', text: s.text || '', stamp: stamp, placeholder: 'متنی نیست'
      }) + '</div>';

    h += '<div class="card-sub" style="margin-top:10px">' + O.ico('clock', 11) + ' ' + esc(O.faDateTeh(new Date(s.now))) + ' تهران · ' +
      O.ico('chart-line', 11) + ' ' + eico(s.session_fa, 11) +
      (s._dup ? '' : ' · ' + O.ico('book', 11) + ' در ژورنال ثبت شد') + '</div>';
    h += '<div class="hint" style="margin-top:6px">' + O.ico('alert', 11, 'c-amber') + ' این یک پیشنهاد است، نه دستور معامله. هیچ سیستمی سود را تضمین نمی‌کند؛ مسئولیت هر معامله با خودت است.</div>';
    return h + '</div>';
  }

  function rejectCard(j, minScore, idx) {
    var statusFa = O.judgmentStatusFa(j);
    var id = 'ev-rej-' + idx;
    var h = '<div class="card sig-card">';
    h += '<div class="sig-head"><div><div style="font-size:14px;font-weight:700;direction:ltr;display:inline-block">' +
      esc(j.symbol) + '</div> <span class="card-sub">' + esc(j.fa_name) + '</span>' +
      '<div style="margin-top:5px"><span class="pill ' + (j.reject_reason === 'VETO' ? 'red' : '') + '">' + eico(statusFa, 11) + '</span>' +
      ((j.reject_reason === 'LOW_SCORE' || j.reject_reason === 'CAPPED')
        ? ' <span class="pill outline">' + O.faNum(j.score) + '/' + O.faNum(j.max_score) + '</span>' : '') +
      '</div></div>' +
      '<div class="card-sub" style="text-align:left">قیمت<br><b class="mono" style="color:var(--text);font-size:13px">' + esc(O.fmtPrice(j.price, j.pip)) + '</b></div></div>';

    if (j.vetoes && j.vetoes.length) {
      h += '<div style="margin-top:8px">';
      j.vetoes.forEach(function (v) {
        h += '<div class="veto-row"><span class="v-icon">' + O.ico('ban', 15) + '</span><div><div class="veto-title">' + eico(v.title_fa, 12) + '</div><div class="veto-detail">' + eico(tehranize(v.detail_fa), 11) + '</div></div></div>';
      });
      h += '</div>';
    }
    if (j.reject_detail && j.reject_reason !== 'VETO') {
      h += '<div class="reject-why">' + O.ico(j.reject_reason === 'LOW_SCORE' ? 'hourglass' : 'search', 13) + ' ' + eico(j.reject_detail, 12) + '</div>';
    }
    if (j.reject_reason === 'LOW_SCORE' && j.evidences && j.evidences.length) {
      var got = j.evidences.filter(function (e) { return e.points > 0; }).map(function (e) { return e.label_fa; });
      var miss = j.evidences.filter(function (e) { return e.points === 0; }).map(function (e) { return e.label_fa; });
      h += '<div style="margin-top:8px;font-size:11px;line-height:2.1">' +
        (got.length ? '<div>' + O.ico('check-circle', 12, 'c-green') + ' داشت: <span style="color:var(--text-2)">' + esc(got.join('، ')) + '</span></div>' : '') +
        (miss.length ? '<div>' + O.ico('minus', 12) + ' نداشت: <span style="color:var(--text-2)">' + esc(miss.join('، ')) + '</span></div>' : '') +
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
    var html = pt('bank', 'تقویم اقتصادی') +
      '<div class="page-sub">منبع: ForexFactory — فقط هفتهٔ جاری (شنبه تا جمعه). همهٔ ساعت‌ها به وقت تهران است. رویداد پراثر در ۳۰ دقیقهٔ آینده = وتوی سیگنال آن نماد.</div>';

    var cal = st && st.calSnap;
    if (!cal) {
      return html + '<div class="card"><div class="empty-state"><div class="e-ico">' + O.ico('antenna', 40) + '</div><div class="e-t">داده‌ای نیست</div><div class="e-s">اول «تحلیل تازه» را اجرا کن.</div></div></div>';
    }
    if (!cal.ok) {
      return html + '<div class="card"><div class="empty-state"><div class="e-ico">' + O.ico('alert', 40, 'c-amber') + '</div><div class="e-t">تقویم در دسترس نبود</div>' +
        '<div class="e-s">' + esc(String(cal.error || '').slice(0, 100)) + '<br>تحلیل تکنیکال بدون وتوی خبری انجام شده — با احتیاط بیشتری معامله کن.</div></div></div>';
    }
    if (cal.stale) {
      html += '<div class="warn-row">' + O.ico('alert', 12, 'c-amber') + ' این داده از کش قدیمی است (آخرین دریافت موفق: ' +
        esc(cal.fetchedAt ? O.faDateTeh(new Date(cal.fetchedAt)) + ' تهران' : '—') + ')</div>';
    }

    var horizon = +(S.cfg.fundamental.horizon_hours) || 48;
    var events = O.upcomingEvents(cal.events, nowMs, horizon, ['HIGH', 'MEDIUM', 'LOW']);
    var weekTxt = cal.weekRange && cal.weekRange[0] ? ' · پوشش هفتهٔ ' + O.faNum(cal.weekRange[0]) + ' تا ' + O.faNum(cal.weekRange[1]) : '';
    html += '<div class="card-sub" style="margin:-6px 2px 10px">' + O.faNum(cal.events.length) + ' رویداد در فید' + weekTxt + '</div>';

    if (!events.length) {
      var nHigh = cal.events.filter(function (e) { return e.impact === 'HIGH'; }).length;
      html += '<div class="card"><div class="empty-state"><div class="e-ico">' + O.ico('check-circle', 40, 'c-green') + '</div>' +
        '<div class="e-t">رویدادی در ' + O.faNum(horizon) + ' ساعت آینده نیست</div>' +
        '<div class="e-s">پنجرهٔ معاملاتی از نظر تقویم باز است.<br>' + O.ico('info', 12) + ' فید ForexFactory فقط هفتهٔ جاری را پوشش می‌دهد؛ در روزهای پایانی هفته ممکن است رویداد آینده‌ای در آن نباشد (یعنی «خبری نیست»، نه «داده خراب است»).<br>' + O.ico('chart-bar', 12) + ' کل این هفته ' + O.faNum(nHigh) + ' رویداد پراثر داشت.</div></div></div>';
      return html;
    }

    // فیلتر اثر
    html += '<div class="sym-meta" style="margin-bottom:12px">' +
      '<button class="pill ink cal-filter" data-impact="ALL">همه</button>' +
      '<button class="pill outline cal-filter" data-impact="HIGH">' + O.ico('dot-high', 9, 'c-red') + ' پراثر</button>' +
      '<button class="pill outline cal-filter" data-impact="MEDIUM">' + O.ico('dot-med', 9, 'c-amber') + ' متوسط</button>' +
      '<button class="pill outline cal-filter" data-impact="LOW">' + O.ico('dot-low', 9, 'c-green') + ' کم‌اثر</button></div>';

    var lastDay = '';
    var shown = 0;
    events.forEach(function (e, i) {
      if (shown >= 40) return;
      shown++;
      var d = new Date(e.when);
      var dayKey = O.dayKeyTeh(d);
      var dayHtml = '';
      if (dayKey !== lastDay) {
        var td = O.tehran(d);
        var greg = O.faNum(td.getUTCDate()) + ' ' + O.MONTH_FA[td.getUTCMonth() + 1];
        dayHtml = '<div class="day-head">' + esc(O.jalaliFa(d)) + ' <span style="opacity:.6;font-weight:400">(' + greg + ')</span></div>';
        lastDay = dayKey;
      }
      var mins = O.evMinutesFrom(e, nowMs);
      var imp = IMPACT_ICO[e.impact] || ['dot-none', ''];
      dayHtml += '<div class="card ev-card" data-impact="' + e.impact + '">' +
        '<div class="ev-top"><span class="ev-time">' + O.faNum(O.hhmmTeh(d)) + '</span>' +
        '<span class="countdown" data-cd-ts="' + e.when + '">' + esc(O.countdown2(mins)) + '</span></div>' +
        '<div class="ev-title">' + O.ico(imp[0], 10, imp[1]) + ' ' + esc(e.title_fa) + '</div>' +
        '<div class="ev-title-en">' + esc(e.title) + '</div>' +
        '<div class="ev-meta"><span class="pill outline">' + esc(O.evCountryFa(e)) + ' (' + esc(e.country) + ')</span>' +
        '<span class="pill">' + esc(e.category) + '</span>' +
        (e.forecast ? '<span class="pill outline">پیش‌بینی: <b class="mono" style="margin-inline-start:4px">' + esc(O.faNum(e.forecast)) + '</b></span>' : '') +
        (e.previous ? '<span class="pill outline">قبلی: <b class="mono" style="margin-inline-start:4px">' + esc(O.faNum(e.previous)) + '</b></span>' : '') +
        '</div>' +
        '<button class="expand-toggle" data-expand="evx-' + i + '">تفسیر به زبان ساده <span>' + O.ico('chevron-down', 12) + '</span></button>' +
        '<div class="expand-body closed" id="evx-' + i + '"><div class="ev-explain">' +
        eico(O.evExplain(e, S.cfg.symbols, nowMs), 12).replace(/\n/g, '<br>') + '</div></div>' +
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
    var html = pt('news', 'اخبار بازار') +
      '<div class="page-sub">رصد زندهٔ ForexLive، Investing.com و FXStreet با امتیازدهی جهت‌دار (۰ تا ۶).</div>';

    var ns = st && st.newsSnap;
    if (!ns) {
      return html + '<div class="card"><div class="empty-state"><div class="e-ico">' + O.ico('antenna', 40) + '</div><div class="e-t">داده‌ای نیست</div><div class="e-s">اول «تحلیل تازه» را اجرا کن.</div></div></div>';
    }
    html += '<div class="card-sub" style="margin:-6px 2px 10px">' +
      O.faNum(ns.items.length) + ' خبر مرتبط · ' + O.faNum(ns.feedsOk) + ' فید موفق' +
      (ns.feedsFailed ? ' · ' + O.faNum(ns.feedsFailed) + ' ناموفق' : '') + '</div>';

    if (!ns.ok) {
      return html + '<div class="card"><div class="empty-state"><div class="e-ico">' + O.ico('alert', 40, 'c-amber') + '</div><div class="e-t">خبری پیدا نشد</div>' +
        '<div class="e-s">' + esc(ns.error || '') + (ns.failedNames && ns.failedNames.length ? '<br>فیدهای ناموفق: ' + esc(ns.failedNames.join('، ')) : '') + '</div></div></div>';
    }

    var brCount = ns.items.filter(function (i) { return i.breaking; }).length;
    if (brCount) {
      html += '<div class="warn-row" style="background:var(--red-tint);border-color:#EBC9C9;color:var(--red-text)">' + O.ico('siren', 12) + ' ' +
        O.faNum(brCount) + ' خبر فوری در این بازه — تا آرام‌شدن بازار، ورود جدید با احتیاط شدید</div>';
    }

    ns.items.forEach(function (it, i) {
      var dots = '';
      for (var d = 0; d < 6; d++) dots += '<i class="' + (d < it.score ? 'on' : '') + '"></i>';
      var age = it.published ? O.countdown2(-(nowMs - it.published) / 60000) : '';
      html += '<div class="card news-card">' +
        '<div class="news-title">' + (it.breaking ? '<span class="breaking-flag">' + O.ico('siren', 11) + ' فوری</span> ' : '') +
        (it.link ? '<a href="#" data-ext="' + esc(it.link) + '">' + esc(it.title) + '</a>' : esc(it.title)) +
        (it.roundup ? ' <span class="pill" style="font-size:9px">' + O.ico('book-open', 10) + ' جمع‌بندی — جهت‌دار نیست</span>' : '') + '</div>' +
        '<div class="news-meta"><span class="score-dots" title="امتیاز اهمیت">' + dots + '</span>' +
        '<span class="news-src">' + O.faNum(it.score) + '/۶</span>' +
        (O.newsDirectionFa(it) ? '<span class="dir-chip">' + eico(O.newsDirectionFa(it), 10) + '</span>' : '') +
        '<span class="news-src">' + esc(it.source) + (age ? ' · ' + esc(age) : '') + '</span></div>' +
        (it.keywords && it.keywords.length ? '<div class="news-meta" style="margin-top:5px">' +
          it.keywords.map(function (k) { return '<span class="kw-chip">' + esc(k) + '</span>'; }).join('') + '</div>' : '') +
        '</div>';
    });

    if (ns.staleFeeds && ns.staleFeeds.length) {
      html += '<div class="hint">' + O.ico('info', 11) + ' فیدهای بدون خبر تازه: ' + esc(ns.staleFeeds.slice(0, 3).join('، ')) + '</div>';
    }
    html += '<div class="hint" style="margin-top:8px">' + O.ico('alert', 11, 'c-amber') + ' جهت‌دهی اخبار بر پایهٔ کلیدواژه است (سرنخ، نه حکم قطعی) — در داور امتیازدهی فقط ۱ امتیاز از ۱۱ وزن دارد.</div>';
    return html;
  };

  // ── ژورنال ──────────────────────────────────────────────────
  O.renderJournal = function (S) {
    var stats = S.stats;
    var entries = S.journal ? S.journal.load() : [];
    var html = pt('book', 'ژورنال و کارنامهٔ دقت') +
      '<div class="page-sub">حلقهٔ صداقت: نتیجهٔ هر سیگنال از روی کندل‌های ۱۵ دقیقه تعیین و اینجا ثبت می‌شود — با قاعدهٔ محتاطانهٔ «برخورد هر دو سطح = ضرر».</div>';

    if (!entries.length) {
      html += '<div class="card"><div class="empty-state"><div class="e-ico">' + O.ico('book', 40) + '</div><div class="e-t">ژورنال خالی است</div>' +
        '<div class="e-s">هر سیگنالی که داور صادر کند اینجا ثبت و نتیجه‌اش پیگیری می‌شود. فعلاً سیگنالی نبوده — این یعنی سیستم وعدهٔ الکی نداده ' + O.ico('smile', 13) + '</div></div></div>';
      return html;
    }

    var o = stats.overall;
    // v0.21.0 — ردیف کارت KPI (همتای «کارنامه: ردیف کارت KPI پارشده» در v0.20.0
    // دسکتاپ). پیش‌تر همین اعداد داخل کاشی‌های یک کارت مشکی بودند و رنگ‌های
    // سبز/قرمزِ روی‌سیاه «هاردکد» شده بودند (#7BE0B0/#FF9A9A) — یعنی دو مقدار
    // رنگ موازی خارج از توکن‌های تم. حالا تُن از O.kpiCard می‌آید و رنگ از
    // توکن‌های CSS، پس تست پاریتی تم آن‌ها را می‌پوشد.
    html += O.sectionHeader('chart-bar', 'کارنامهٔ کلی',
      'آمار دقت از ژورنال — نتیجهٔ هر سیگنال از کندل‌ها پیگیری شده است.',
      O.chip('باز: ' + O.faNum(stats.open_count), 'ink'));

    html += O.kpiRow([
      { icon: 'check-circle', value: O.faNum(o.closed), label: 'بسته‌شده', tone: '' },
      { icon: 'target', value: O.faNum(o.wins), label: 'برد', tone: 'green' },
      { icon: 'stop-sign', value: O.faNum(o.losses), label: 'باخت', tone: 'red' },
      { icon: 'hourglass', value: O.faNum(o.expired), label: 'منقضی', tone: 'amber' }
    ]);
    html += O.kpiRow([
      { icon: 'chart-bar', value: O.faPct(o.hit_rate), label: 'نرخ برد (قطعی)', tone: 'brand' },
      { icon: 'seal', value: O.faPct(o.closed_win_rate), label: 'نرخ برد محتاطانه', tone: '' },
      { icon: 'scale', value: O.rFmt(o.avg_r), label: 'میانگین R (انتظار)', tone: (o.avg_r > 0 ? 'green' : (o.avg_r < 0 ? 'red' : '')) },
      { icon: 'book', value: O.faNum(entries.length), label: 'کل ثبت‌های ژورنال', tone: '' }
    ]);

    html += '<div class="card"><div class="stat-defs">نرخ برد (قطعی) = برد ÷ (برد+باخت) · ' +
      'محتاطانه = برد ÷ کل بسته‌شده‌ها (منقضی «نبرد» شمرده می‌شود) · ' +
      'میانگین R = انتظار ریاضی هر سیگنال بسته. هر سه گزارش می‌شود تا عدد واحدی گمراه‌کننده نباشد.</div></div>';

    // هفتهٔ جاری در برابر قبل
    if (stats.this_week_key && stats.by_week[stats.this_week_key]) {
      var tw = stats.by_week[stats.this_week_key];
      var lw = stats.last_week_key ? stats.by_week[stats.last_week_key] : null;
      html += '<div class="card"><div class="card-title">' + ct('calendar', 'امسال — هفتهٔ ' + esc(O.faNum(stats.this_week_key.slice(-2)))) + '</div>' +
        '<div style="font-size:11.5px;color:var(--text-2);margin-top:6px">' +
        'بسته ' + O.faNum(tw.closed) + ' · برد ' + O.faNum(tw.wins) + ' · باخت ' + O.faNum(tw.losses) + ' · نرخ برد ' + O.faPct(tw.hit_rate) + ' · میانگین R ' + O.rFmt(tw.avg_r) +
        (lw ? '<br>هفتهٔ قبل: بسته ' + O.faNum(lw.closed) + ' · نرخ برد ' + O.faPct(lw.hit_rate) + ' · میانگین R ' + O.rFmt(lw.avg_r) : '') +
        '</div></div>';
    }

    // سیگنال‌های باز
    var open = entries.filter(function (e) { return e.outcome == null; });
    if (open.length) {
      html += '<div class="card"><div class="card-title">' + ct('hourglass', 'سیگنال‌های باز (' + O.faNum(open.length) + ')') + '</div><div style="margin-top:6px">';
      open.forEach(function (e) {
        html += '<div class="j-entry"><div class="j-sym"><div class="s1">' + esc(e.symbol) + ' · ' +
          (e.direction === 'BUY'
            ? O.ico('dot-low', 9, 'c-green') + ' خرید'
            : O.ico('dot-high', 9, 'c-red') + ' فروش') + '</div>' +
          '<div class="s2">ورود ' + esc(O.fmtPrice(e.entry, e.pip)) + ' · SL ' + esc(O.fmtPrice(e.sl, e.pip)) + ' · TP ' + esc(O.fmtPrice(e.tp, e.pip)) + ' · ' + esc(agoFa(e.ts)) + '</div></div>' +
          '<span class="pill outline">' + O.faNum(e.score) + '/' + O.faNum(e.max_score) + '</span></div>';
      });
      html += '</div></div>';
    }

    // بسته‌شده‌ها
    var closed = entries.filter(function (e) { return e.outcome != null; }).slice(-30).reverse();
    if (closed.length) {
      html += '<div class="card"><div class="card-title">' + ct('flag', 'آخرین نتایج') + '</div><div style="margin-top:6px">';
      closed.forEach(function (e) {
        var cls = e.outcome === 'TP' ? 'win' : (e.outcome === 'SL' ? 'loss' : 'exp');
        html += '<div class="j-entry"><div class="j-sym"><div class="s1">' + esc(e.symbol) + ' · ' +
          (e.direction === 'BUY' ? O.ico('dot-low', 9, 'c-green') : O.ico('dot-high', 9, 'c-red')) + '</div>' +
          '<div class="s2">' + eico(O.OUTCOME_FA[e.outcome] || e.outcome, 11) + ' · ' + esc(agoFa(e.ts)) +
          (e.note ? ' — ' + esc(e.note) : '') + '</div></div>' +
          '<span class="r-chip ' + cls + '">' + O.rFmt(e.r) + '</span></div>';
      });
      html += '</div></div>';
    }

    // به تفکیک نماد
    var symKeys = Object.keys(stats.by_symbol);
    if (symKeys.length) {
      html += '<div class="card"><button class="expand-toggle" data-expand="j-syms" style="padding-top:0">' + O.ico('chart-line', 13) + ' تفکیک نمادها <span>' + O.ico('chevron-down', 12) + '</span></button>' +
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
      '<button class="btn ghost sm" data-action="journal-save" style="flex:1">' + O.ico('save', 13) + ' ذخیره در دانلودها</button>' +
      '<button class="btn ghost sm" data-action="journal-export" style="flex:1">' + O.ico('share', 13) + ' کپی JSONL</button>' +
      '<button class="btn red sm" data-action="journal-clear" style="flex:1">' + O.ico('trash', 13) + ' پاک‌کردن</button></div>';
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
    var nat = O.native || {};
    var bgRunning = !!(nat.bgRunning && nat.bgRunning());
    var notifOn = nat.notificationsEnabled ? nat.notificationsEnabled() : true;
    var battOk = nat.isIgnoringBattery ? nat.isIgnoringBattery() : true;
    var html = pt('gear', 'تنظیمات') +
      '<div class="page-sub">تغییرها فوری ذخیره می‌شوند و در تحلیل بعدی اثر می‌کنند.</div>';

    html += '<div class="card"><div class="section-title" style="margin-top:0">' + ct('user', 'شخصی', 13) + '</div>' +
      '<div class="set-row"><div><div class="set-label">نام نمایشی</div><div class="set-sub">در خوش‌آمدگویی و هدر استفاده می‌شود</div></div></div>' +
      '<input class="text-input" data-set="user_name" value="' + esc(set.user_name) + '" maxlength="24">' +
      '</div>';

    // لایسنس و قفل دستگاه (v0.14.0) + دورهٔ آزمایشی (v0.15.0)
    var tr = S.trial || { exists: false, active: false, daysLeft: 0, tampered: false };
    var linfo = S.licenseInfo || null;
    var licState;
    if (S.licensed) {
      var expTxt = ' — لایسنس دائمی';
      if (linfo && linfo.expires_at) {
        var e8 = String(linfo.expires_at);
        var ed = new Date(+e8.slice(0, 4), +e8.slice(4, 6) - 1, +e8.slice(6, 8));
        expTxt = ' — معتبر تا ' + esc(O.jalaliFa(ed));
      }
      licState = '<div class="set-row"><div><div class="set-label">' + O.ico('check-circle', 13, 'c-green') + ' فعال‌سازی شده</div>' +
        '<div class="set-sub">لایسنس به همین دستگاه قفل است' + expTxt + '</div></div>' +
        '<button class="btn ghost sm" data-action="deactivate-license">غیرفعال‌سازی</button></div>';
    } else if (tr.active) {
      licState = '<div class="set-row"><div><div class="set-label">' + O.ico('hourglass', 13, 'c-amber') + ' دورهٔ آزمایشی</div>' +
        '<div class="set-sub">' + O.faNum(tr.daysLeft) + ' روز باقی مانده — همهٔ امکانات (شامل رصد پس‌زمینه) فعال است</div></div>' +
        '<button class="btn ghost sm" data-action="activate-license">فعال‌سازی</button></div>';
    } else {
      licState = '<div class="set-row"><div><div class="set-label">' + O.ico('alert', 13, 'c-red') + ' فعال‌سازی نشده</div>' +
        '<div class="set-sub">' + (tr.tampered
          ? 'دستکاری ساعت تشخیص داده شد — دورهٔ آزمایشی نامعتبر است'
          : (tr.exists ? 'دورهٔ آزمایشی به پایان رسیده — تحلیل و رصد متوقف است' : 'تا فعال‌سازی، تحلیل و رصد اجرا نمی‌شود')) + '</div></div>' +
        '<button class="btn primary sm" data-action="activate-license">فعال‌سازی</button></div>';
    }
    html += '<div class="card"><div class="section-title" style="margin-top:0">' + ct('seal', 'لایسنس و قفل دستگاه', 13) + '</div>' +
      licState +
      '<div class="set-row"><div><div class="set-label">کد دستگاه</div>' +
      '<div class="set-sub mono" dir="ltr" style="letter-spacing:1.5px;font-weight:700;text-align:right">' + esc(S.deviceCode || '—') + '</div></div>' +
      '<button class="btn ghost sm" data-action="copy-device-code">' + O.ico('copy', 12) + ' کپی</button></div>' +
      '</div>';

    // رصد پس‌زمینه — سیگنال بدون باز کردن اپ (v0.13.0)
    html += '<div class="card"><div class="section-title" style="margin-top:0">' + ct('activity', 'رصد پس‌زمینه', 13) + '</div>' +
      '<div class="set-row"><div><div class="set-label">رصد بازار بدون باز کردن اپ</div>' +
      '<div class="set-sub">تحلیل در پس‌زمینه تکرار می‌شود و سیگنال تازه/خبر فوری با اعلان می‌رسد — حتی وقتی اپ بسته است. یک اعلان ماندگار «در حال رصد» نشان داده می‌شود.</div></div>' +
      switchHtml('background_enabled', set.background_enabled !== false) + '</div>' +
      (bgRunning
        ? '<div class="set-row"><div><div class="set-label">' + O.ico('activity', 12, 'c-green') + ' رصد فعال است</div><div class="set-sub">چرخه‌ها توسط سرویس پس‌زمینه اجرا می‌شوند</div></div></div>'
        : '') +
      (!notifOn
        ? '<div class="set-row"><div><div class="set-label">اجازهٔ اعلان داده نشده</div><div class="set-sub">بدون آن، سیگنال پس‌زمینه بی‌صدا می‌ماند</div></div>' +
          '<button class="btn ghost sm" data-action="open-notif-settings">اجازهٔ اعلان</button></div>'
        : '') +
      (!battOk
        ? '<div class="set-row"><div><div class="set-label">بهینه‌سازی باتری فعال است</div><div class="set-sub">اندروید ممکن است رصد پس‌زمینه را متوقف کند — اجازهٔ «نادیده‌گرفتن» بده</div></div>' +
          '<button class="btn ghost sm" data-action="ignore-battery">اجازهٔ باتری</button></div>'
        : '<div class="set-row"><div><div class="set-label">' + O.ico('battery', 12, 'c-green') + ' بهینه‌سازی باتری: نادیده گرفته شده</div><div class="set-sub">رصد پس‌زمینه پایدار می‌ماند</div></div></div>') +
      '</div>';

    html += '<div class="card"><div class="section-title" style="margin-top:0">' + ct('scale', 'داور امتیازدهی', 13) + '</div>' +
      '<div class="set-row"><div><div class="set-label">داور فعال است</div><div class="set-sub">خاموش = هیچ سیگنالی داوری/صادر نمی‌شود</div></div>' + switchHtml('judge_enabled', set.judge_enabled) + '</div>' +
      '<div class="set-row"><div><div class="set-label">آستانهٔ صدور سیگنال</div><div class="set-sub">حداکثر ممکن ۱۱ امتیاز است — پیش‌فرض ۷</div></div>' +
      '<span class="stepper"><button data-step="min_score:-1">−</button><span class="val">' + O.faNum(set.min_score) + '</span><button data-step="min_score:1">+</button></span></div>' +
      '</div>';

    html += '<div class="card"><div class="section-title" style="margin-top:0">' + ct('ban', 'دروازه‌های وتو', 13) + '</div><div class="hint" style="margin-bottom:6px">وتوها بدون استثنا هستند: حتی با امتیاز کامل، سیگنال صادر نمی‌شود.</div>' +
      row('weekend', 'lock', 'بازار بسته', 'شنبه/یکشنبه و جمعه از ۰۰:۳۰ بامداد شنبه (تهران)', v.weekend) +
      row('high_impact_event', 'calendar', 'رویداد پراثر تقویم', 'رویداد پراثر تا ۳۰ دقیقهٔ آینده', v.high_impact_event) +
      row('timeframe_conflict', 'shuffle', 'تضاد تایم‌فریم', 'H4 و H1 هم‌جهت نباشند', v.timeframe_conflict) +
      row('range_market', 'moon', 'بازار بی‌روند', 'ADX زیر آستانهٔ ۲۰', v.range_market) +
      row('volatility_spike', 'trend-up', 'جهش غیرعادی نوسان', 'ATR فعلی بیش از ۲ برابر میانگین', v.volatility_spike) +
      row('breaking_news', 'siren', 'خبر فوری', 'خبر فوری مرتبط با نماد', v.breaking_news) +
      '</div>';

    html += '<div class="card"><div class="section-title" style="margin-top:0">' + ct('plug', 'موتورها', 13) + '</div>' +
      row2('fund_enabled', 'bank', 'تقویم اقتصادی', 'ForexFactory — کش ۳۰ دقیقه‌ای', set.fund_enabled) +
      row2('news_enabled', 'news', 'موتور اخبار', 'RSS فارکس — دریافت زنده در هر تحلیل', set.news_enabled) +
      row2('tv_enabled', 'search', 'تاییدیهٔ تریدینگ‌ویو', 'API غیررسمی — اگر قطع شد، مدرک ' + O.ico('unknown', 10) + ' می‌گیرد', set.tv_enabled) +
      '</div>';

    html += '<div class="card"><div class="section-title" style="margin-top:0">' + ct('refresh', 'تازه‌سازی و اعلان‌ها', 13) + '</div>' +
      '<div class="set-row"><div><div class="set-label">تازه‌سازی خودکار تحلیل</div><div class="set-sub">وقتی اپ باز و بازار فعال است — اگر رصد پس‌زمینه روشن باشد، چرخه‌ها در پس‌زمینه هم اجرا می‌شوند. معامله خودکار نمی‌کند.</div></div>' + switchHtml('auto_refresh_enabled', set.auto_refresh_enabled !== false) + '</div>' +
      '<div class="set-row"><div><div class="set-label">فاصلهٔ تازه‌سازی</div><div class="set-sub">هر چند دقیقه یک‌بار تحلیل تکرار شود (پس‌زمینه هم همین فاصله را دارد)</div></div>' +
      '<span class="stepper"><button data-step="auto_refresh_min:-1">−</button><span class="val">' + O.faNum(set.auto_refresh_min || 15) + ' دقیقه</span><button data-step="auto_refresh_min:1">+</button></span></div>' +
      '<div class="set-row"><div><div class="set-label">اعلان سیگنال جدید و خبر فوری ' + O.ico('bell', 12) + '</div><div class="set-sub">نوتیفیکیشن اندروید + لرزش هنگام صدور سیگنال تازه یا خبر فوری</div></div>' + switchHtml('notify_enabled', set.notify_enabled !== false) + '</div>' +
      '<div class="set-row"><div><div class="set-label">انیمیشن‌ها ' + O.ico('wave', 12) + '</div><div class="set-sub">پس‌زمینهٔ شفق متحرک و حرکت ظریف کارت‌ها — خاموشش کنی همه‌چیز آنی می‌شود (باتری/تمرکز). همتای ui.animations در نسخهٔ ویندوز.</div></div>' + switchHtml('animations_enabled', set.animations_enabled !== false) + '</div>' +
      '</div>';

    html += '<div class="card"><div class="section-title" style="margin-top:0">' + ct('archive', 'داده‌ها', 13) + '</div>' +
      '<div class="set-row"><div><div class="set-label">پاک‌کردن کش تقویم و تحلیل</div><div class="set-sub">دادهٔ بازار دفعهٔ بعد تازه دریافت می‌شود</div></div>' +
      '<button class="btn ghost sm" data-action="clear-cache">پاک‌کردن</button></div>' +
      '<div class="set-row"><div><div class="set-label">بازنشانی تنظیمات</div><div class="set-sub">همه به حالت پیش‌فرض برمی‌گردند (ژورنال پاک نمی‌شود)</div></div>' +
      '<button class="btn ghost sm" data-action="reset-settings">بازنشانی</button></div>' +
      '</div>';

    html += '<div class="card ink"><div class="ink-title">دربارهٔ ODIN ASSISTANT</div>' +
      // شمارهٔ نسخهٔ ویندوز عمداً نوشته نمی‌شود: هاردکدکردنش اینجا باعث شد
      // «دربارهٔ ما» تا v0.20.1 هم «ویندوز (0.8.1)» نشان دهد. نسخهٔ اندروید
      // از PackageManager می‌آید (که از src/app_paths.py مشتق است) و بس.
      '<div class="ink-cap" style="margin-top:6px;line-height:2.2">نسخهٔ اندروید ' + O.faNum(S.version || 'dev') + ' — همراه نسخهٔ ویندوز<br>' +
      O.ico('clock', 11) + ' همهٔ ساعت‌های اپ به وقت تهران است (منطق داخلی موتور UTC — هماهنگ با نسخهٔ دسکتاپ).<br>' +
      O.ico('seal', 11) + ' <b style="color:#fff">غیرخودکار:</b> این اپ هیچ معامله‌ای انجام نمی‌دهد و به هیچ بروکری وصل نیست.</div>' +
      '<button class="btn ghost sm" data-tab="about" style="margin-top:10px;width:100%">' + O.ico('info', 13) + ' دربارهٔ ما، حق نشر و اصالت برنامه ' + O.ico('chevron-left', 12) + '</button></div>';
    return html;

    function row(key, icon, label, sub, on) {
      return '<div class="set-row"><div><div class="set-label">' + O.ico(icon, 13) + ' ' + label + '</div><div class="set-sub">' + sub + '</div></div>' +
        switchHtml('veto.' + key, on !== false) + '</div>';
    }
    function row2(key, icon, label, sub, on) {
      return '<div class="set-row"><div><div class="set-label">' + O.ico(icon, 13) + ' ' + label + '</div><div class="set-sub">' + sub + '</div></div>' +
        switchHtml(key, on !== false) + '</div>';
    }
  };

  // ── دربارهٔ ما (حق نشر، سازنده، اصالت امضا) ─────────────────
  O.renderAbout = function (S) {
    var ver = S.version || 'dev';
    var html = '<div class="action-row"><button class="btn ghost" data-tab="settings">' + O.ico('chevron-right', 14) + ' بازگشت</button></div>' +
      pt('info', 'دربارهٔ ما') +
      '<div class="page-sub">سازنده، حق نشر و راهِ تشخیص نسخهٔ اصلی</div>';

    // کارت اصلی: لوگو + نام برنامه + سازنده
    html += '<div class="card ink" style="text-align:center;padding:22px 16px">' +
      '<svg viewBox="0 0 48 48" width="56" height="56" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" aria-hidden="true">' +
      '<path d="M24 4v8M24 36v8M8 24H4M44 24h-4"/><circle cx="24" cy="24" r="10"/>' +
      '<path d="M24 14a10 10 0 0 1 0 20" fill="#fff" stroke="none"/></svg>' +
      '<div style="font-size:17px;font-weight:800;color:#fff;margin-top:10px" dir="ltr">ODIN ASSISTANT</div>' +
      '<div class="ink-cap" style="margin-top:4px"><span dir="ltr">ODIN ASSISTANT</span> — نسخهٔ اندروید ' + O.faNum(ver) + '</div>' +
      '<div style="margin-top:12px;padding-top:12px;border-top:1px solid rgba(255,255,255,.14);font-size:12.5px;color:rgba(255,255,255,.85)">' +
      'سازنده و توسعه‌دهنده: <b style="color:#fff">Sushian Khoshkhani</b></div>' +
      '<a class="tg-pill" href="#" data-ext="https://t.me/Khode_Sushian">' +
        O.ico('telegram', 15) + ' <span dir="ltr">@Khode_Sushian</span></a>' +
      '<div class="ink-cap" style="margin-top:8px">تلگرام سازنده — خرید لایسنس، پشتیبانی و ارتباط مستقیم</div>' +
      '</div>';

    // تیم پروژه (v0.14.2)
    html += '<div class="card"><div class="section-title" style="margin-top:0">' + ct('user', 'تیم پروژه', 13) + '</div>' +
      '<div class="team-row"><span class="team-ico">' + O.ico('seal', 17) + '</span>' +
        '<div class="team-main"><div class="team-role">سازنده و توسعه‌دهنده</div>' +
        '<div class="team-name" dir="ltr">Sushian Khoshkhani</div></div>' +
        '<a class="tg-pill on-card team-tg" href="#" data-ext="https://t.me/Khode_Sushian" title="تلگرام سازنده">' +
        O.ico('telegram', 13) + ' <span dir="ltr">@Khode_Sushian</span></a></div>' +
      '<div class="team-row"><span class="team-ico">' + O.ico('briefcase', 17) + '</span>' +
        '<div class="team-main"><div class="team-role">مدیر پروژه</div>' +
        '<div class="team-name" dir="ltr">Reza Khoshkhani</div></div></div>' +
      '<div class="team-row"><span class="team-ico">' + O.ico('coins', 17) + '</span>' +
        '<div class="team-main"><div class="team-role">اسپانسر پروژه</div>' +
        '<div class="team-name" dir="ltr">Karen Khoshkhani</div></div></div>' +
      '</div>';

    // حق نشر و مالکیت
    html += '<div class="card"><div class="section-title" style="margin-top:0">' + ct('seal', 'حق نشر و مالکیت', 13) + '</div>' +
      '<div class="hint" style="line-height:2.3">' +
      '<b dir="ltr" style="display:inline-block">© 2026 Sushian Khoshkhani — All rights reserved.</b><br>' +
      'کلیهٔ حقوق این نرم‌افزار محفوظ است. این برنامه و کد منبع آن — شامل موتور تحلیل، داور سیگنال، ژورنال و رابط کاربری — مالکیت انحصاری <b>Sushian Khoshkhani</b> (سازندهٔ برنامه) است.<br>' +
      'هرگونه کپی‌برداری، بازنشر، تغییر نام، تغییر برند یا عرضهٔ برنامه تحت عنوان شخصی دیگر — رایگان یا تجاری — بدون اجازهٔ کتبی سازنده <b>ممنوع</b> است و پیگرد قانونی دارد.' +
      '</div></div>';

    // امضای دیجیتال و اصالت نسخه
    html += '<div class="card"><div class="section-title" style="margin-top:0">' + ct('seal', 'امضای دیجیتال و اصالت نسخه', 13) + '</div>' +
      '<div class="hint" style="line-height:2.3">' +
      'فایل نصبی (APK) رسمی این برنامه با گواهی دیجیتال به نام <b>Sushian Khoshkhani</b> امضا شده است:' +
      '<div dir="ltr" style="text-align:left;margin:8px 0;padding:8px 10px;background:var(--bg,#f4f4f7);border-radius:10px;font-family:monospace;font-size:11px">Subject: CN=Sushian Khoshkhani, OU=ODIN Assistant, O=Sushian Khoshkhani, C=IR</div>' +
      'اثر انگشت SHA-256 گواهی نسخهٔ رسمی (از v0.13.0):' +
      '<div dir="ltr" style="text-align:left;margin:8px 0;padding:8px 10px;background:var(--bg,#f4f4f7);border-radius:10px;font-family:monospace;font-size:10px;word-break:break-all">SHA256: bd11159e003b55b9ae53cd26c192dc6b2bea2840c787fddbd0f523a947cb5189</div>' +
      'در مارکت‌ها و ابزارهای بررسی امضا، نام پابلیشر/امضاکنندهٔ نسخهٔ اصلی <b>Sushian Khoshkhani</b> است. اگر نام دیگری دیدید، آن فایل <b>جعلی یا دست‌کاری‌شده</b> است — نصبش نکنید و گزارش دهید.<br>' +
      'کلید امضای برنامه از نسخهٔ ۰.۱۳.۰ با هویت کامل Sushian Khoshkhani صادر شده است.' +
      '</div></div>';

    // منبع رسمی — بدون لینک گیت‌هاب؛ نسخهٔ رسمی فقط مستقیم از سازنده (تلگرام رسمی)
    html += '<div class="card"><div class="section-title" style="margin-top:0">' + ct('link', 'منبع رسمی', 13) + '</div>' +
      '<div class="hint" style="line-height:2.2">' +
      'نسخهٔ رسمی برنامه فقط <b>مستقیماً از خودِ سازنده (Sushian Khoshkhani)</b> عرضه می‌شود.' +
      ' فایل نصبی را از واسطه‌ها، کانال‌ها یا صفحات متفرقه نگیرید؛ هر نسخه‌ای که امضای بالا را نداشته باشد رسمی نیست.<br>' +
      'راه ارتباطی رسمی (خرید لایسنس و پشتیبانی): تلگرام ' +
      '<a href="#" data-ext="https://t.me/Khode_Sushian" style="color:var(--text);font-weight:700;text-decoration:none" dir="ltr">@Khode_Sushian</a>' +
      '</div></div>';

    // سلب مسئولیت (غیرخودکار)
    html += '<div class="card ink"><div class="ink-title">' + O.ico('alert', 14) + '<span>غیرخودکار — سلب مسئولیت</span></div>' +
      '<div class="ink-cap" style="margin-top:6px;line-height:2.2">' +
      'این اپ هیچ معامله‌ای انجام نمی‌دهد و به هیچ بروکری وصل نیست؛ فقط تحلیل، سیگنال پیشنهادی و پیگیری صداقتِ نتایج.<br>' +
      O.ico('clock', 11) + ' همهٔ ساعت‌های اپ به وقت تهران است (منطق داخلی موتور UTC — هماهنگ با نسخهٔ دسکتاپ).<br>' +
      'هیچ سیستمی سود را تضمین نمی‌کند؛ مسئولیت هر معامله با خودت است.' +
      '</div></div>';

    return html;
  };

  // ── نمودار کندل‌استیک (v0.17.0) ──────────────────────────────
  O.renderChartPage = function (S) {
    var back = '<div class="action-row"><button class="btn ghost" data-tab="home">' +
      O.ico('chevron-right', 14) + ' بازگشت</button></div>';
    var sym = S.chartSym ||
      (S.state && S.state.analyses && S.state.analyses[0] && S.state.analyses[0].symbol);
    if (!sym) {
      return back + '<div class="card"><div class="empty-state"><div class="e-ico">' + O.ico('chart-line', 40) +
        '</div><div class="e-t">نمادی انتخاب نشده</div><div class="e-s">از کارت هر نماد در خانه، «نمودار» را بزن.</div></div></div>';
    }
    var pair = sym.length === 6 ? sym.slice(0, 3) + '/' + sym.slice(3) : sym;
    var a = null;
    ((S.state && S.state.analyses) || []).forEach(function (x) { if (x.symbol === sym) a = x; });
    var raw = null;
    try {
      raw = (S.storage && S.storage.get) ? JSON.parse(S.storage.get('chart.' + sym) || 'null') : null;
    } catch (e) { raw = null; }
    if (!raw || !raw.length || raw.length < 5) {
      return back + pt('chart-line', pair) +
        '<div class="card"><div class="empty-state"><div class="e-ico">' + O.ico('chart-line', 40) +
        '</div><div class="e-t">دادهٔ کندل کافی نیست</div>' +
        '<div class="e-s">اول «تحلیل تازه» را اجرا کن — کندل‌ها برای نمودار هم ذخیره می‌شوند.</div></div></div>';
    }

    var tf = S.chartTf === 'H4' ? 'H4' : 'H1';
    var candles = tf === 'H4' ? O.resample4h(raw) : raw;
    var bars = S.chartBars | 0 || (tf === 'H4' ? 60 : 120);
    var pip = a ? a.pip : (sym === 'XAUUSD' ? 1 : 0.0001);

    var levels = [];
    if (a && a.support) levels.push({ price: a.support, color: O.CHART_COLORS.support, label: 'حمایت ' + O.fmtPrice(a.support, pip) });
    if (a && a.resistance) levels.push({ price: a.resistance, color: O.CHART_COLORS.resistance, label: 'مقاومت ' + O.fmtPrice(a.resistance, pip) });
    var sig = (S.chartSig && S.chartSig.symbol === sym) ? S.chartSig : null;
    if (sig) {
      levels.push({ price: sig.entry, color: O.CHART_COLORS.entry, label: 'ورود ' + O.fmtPrice(sig.entry, pip) });
      levels.push({ price: sig.sl, color: O.CHART_COLORS.sl, label: 'حد ضرر ' + O.fmtPrice(sig.sl, pip), dash: '6 3' });
      levels.push({ price: sig.tp, color: O.CHART_COLORS.tp, label: 'هدف ' + O.fmtPrice(sig.tp, pip), dash: '6 3' });
    }

    var html = back + pt('chart-line', pair + ' — ' + tf);
    html += '<div class="page-sub">' + (a ? esc(a.fa_name) + ' · ' : '') +
      'کندل‌های یک‌ساعتهٔ Yahoo Finance' + (S.state && S.state.ranAt ? ' · آخرین تحلیل ' + esc(agoFa(S.state.ranAt)) : '') +
      ' · ساعت‌ها تهران</div>';

    // قرص‌های تایم‌فریم و تعداد کندل
    var tfPills = ['H1', 'H4'].map(function (t) {
      return '<button class="pill ' + (t === tf ? 'ink' : 'outline') + '" data-chart-tf="' + t + '">' + t + '</button>';
    }).join('');
    var barOpts = tf === 'H4' ? [30, 60, 90] : [60, 120, 240];
    var barPills = barOpts.map(function (b) {
      return '<button class="pill ' + (b === bars ? 'ink' : 'outline') + '" data-chart-bars="' + b + '">' + O.faNum(b) + '</button>';
    }).join('');
    html += '<div class="sym-meta" style="margin-bottom:10px">' + tfPills +
      '<span style="width:8px"></span>' + barPills + '</div>';

    html += '<div class="card" style="padding:10px 8px">' +
      O.renderCandleChart(candles, { pip: pip, levels: levels, height: 300, maxBars: bars }) + '</div>';

    if (sig) {
      html += '<div class="card"><div class="card-title">' +
        ct('target', 'سطوح سیگنال ' + (sig.direction === 'BUY' ? 'خرید' : 'فروش') + ' — ' + pair) + '</div>' +
        '<div class="levels" style="margin-top:8px">' +
        '<div class="level-box"><div class="l-cap">' + O.ico('pin', 11) + ' ورود</div><div class="l-val">' + esc(O.fmtPrice(sig.entry, sig.pip)) + '</div></div>' +
        '<div class="level-box sl"><div class="l-cap">' + O.ico('stop-sign', 11, 'c-red') + ' حد ضرر</div><div class="l-val">' + esc(O.fmtPrice(sig.sl, sig.pip)) + '</div></div>' +
        '<div class="level-box tp"><div class="l-cap">' + O.ico('target', 11, 'c-green') + ' هدف</div><div class="l-val">' + esc(O.fmtPrice(sig.tp, sig.pip)) + '</div></div>' +
        '</div></div>';
    } else if (a && (a.support || a.resistance)) {
      html += '<div class="hint" style="text-align:center">خط‌های خاکستری: حمایت/مقاومت کلیدی — از «سیگنال‌ها» می‌توانی ورود/SL/TP را هم روی نمودار بیاوری</div>';
    }
    return html;
  };

  // ── بریفینگ ─────────────────────────────────────────────────
  O.renderBriefingPage = function (S) {
    var html = '<div class="action-row"><button class="btn ghost" data-tab="home">' + O.ico('chevron-right', 14) + ' بازگشت</button>' +
      '<button class="btn ghost" data-action="share-briefing">' + O.ico('share', 15) + ' اشتراک</button>' +
      '<button class="btn primary" data-action="analyze">' + O.ico('refresh', 15) + ' تحلیل تازه</button></div>';
    if (!S.state || !S.state.analyses || !S.state.analyses.length) {
      return html + '<div class="card"><div class="empty-state"><div class="e-ico">' + O.ico('sunrise', 40) + '</div><div class="e-t">اول تحلیل را اجرا کن</div><div class="e-s">بریفینگ از نتیجهٔ آخرین تحلیل ساخته می‌شود.</div></div></div>';
    }
    var lines = O.renderBriefing(S.state, S.cfg, S.state.ranAt);
    // v0.21.0 — کنسول‌کارت تیره با قرص مهر زمان و دکمهٔ کپی، دقیقاً همتای
    // «همهٔ صفحه‌های متنی → کنسول‌کارت» در v0.20.0 دسکتاپ.
    // رنگ‌آمیزی ساختاری خطوط با O.consoleColorize (port از widgets.py).
    // نشانگر «▎» سرِ خط‌ها حذف می‌شود چون consoleColorize خودش سرتیترها را
    // با رنگ برند برجسته می‌کند (نقش همان نشانگر را دارد).
    var text = lines.map(function (ln) { return String(ln).replace(/^▎/, ''); }).join('\n');
    html += O.consoleCard({
      id: 'briefing-cc',
      title: 'بریفینگ',
      sub: 'خلاصهٔ بامدادی بازار — به وقت تهران',
      icon: 'sunrise',
      text: text,
      stamp: S.state && S.state.ranAt ? O.faDateTeh(new Date(S.state.ranAt)) : ''
    });
    return html;
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
