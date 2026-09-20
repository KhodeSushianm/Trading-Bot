/* 🌅 بریفینگ صبحگاهی — پورت src/report/fundamental.py::render_briefing
 * خروجی: آرایهٔ خطوط (UI آن‌ها را با استایل مناسب رندر می‌کند؛
 * خطوط «▎» سربخش‌اند). */
(function (O) {
  'use strict';

  O.renderBriefing = function (state, cfg, nowMs) {
    var analyses = state.analyses || [];
    var ranking = state.ranking || [];
    var calSnap = state.calSnap;
    var newsSnap = state.newsSnap;
    var syms = cfg.symbols;
    var horizonHours = +(cfg.briefing && cfg.briefing.horizon_hours) || 24;
    var parts = [];

    parts.push('🌅 بریفینگ صبحگاهی — ' + O.faDate(new Date(nowMs)));
    parts.push('🕒 ' + O.faNum(O.hhmm(new Date(nowMs))) + ' UTC | منبع داده: Yahoo Finance');

    // ۱) آنچه امروز در پیش است
    parts.push('');
    parts.push('▎امروز چه چیزی در پیش داریم؟');
    if (calSnap && calSnap.ok) {
      var evs = O.upcomingEvents(calSnap.events, nowMs, horizonHours, ['HIGH', 'MEDIUM'], null, 8);
      if (evs.length) {
        evs.forEach(function (e) {
          var pairs = syms.filter(function (s) { return s.base === e.country || s.quote === e.country; })
            .map(function (s) { return s.name; });
          var tag = pairs.length ? ' → ' + pairs.join('، ') : '';
          parts.push('  ' + (O.IMPACT_FA[e.impact] || '') + ' ' + O.faNum(O.hhmm(new Date(e.when))) +
            ' UTC (' + O.WEEKDAY_FA[O.pyWeekday(new Date(e.when))] + '): ' + e.title_fa +
            ' [' + O.evCountryFa(e) + ']' + tag);
          if (e.forecast || e.previous) {
            var bits = [];
            if (e.forecast) bits.push('پیش‌بینی ' + O.faNum(e.forecast));
            if (e.previous) bits.push('قبلی ' + O.faNum(e.previous));
            parts.push('       ' + bits.join(' | ') + ' — ' + O.countdown2(O.evMinutesFrom(e, nowMs)));
          }
        });
      } else {
        parts.push('  ✅ رویداد پراثر یا متوسطی در ۲۴ ساعت آینده نیست — روز آرامی برای معامله است');
        parts.push('  ℹ️ فید تقویم فقط هفتهٔ جاری را پوشش می‌دهد؛ شنبه/یکشنبه بازار بسته است');
      }
      var nxt = O.nextHighImpact(calSnap.events, null, null, nowMs);
      if (nxt && O.evMinutesFrom(nxt, nowMs) > horizonHours * 60) {
        parts.push('  📌 نزدیک‌ترین رویداد پراثر: ' + nxt.title_fa + ' (' + O.evCountryFa(nxt) + ') — ' + O.faDate(new Date(nxt.when)));
      }
    } else if (calSnap) {
      parts.push('  ⚠️ تقویم اقتصادی در دسترس نبود (' + String(calSnap.error || '').slice(0, 60) + ')');
    } else {
      parts.push('  ⚠️ تقویم اقتصادی غیرفعال است');
    }

    // ۲) پنجره‌های ممنوعه
    if (calSnap && calSnap.ok) {
      var vetoes = [];
      O.upcomingEvents(calSnap.events, nowMs, horizonHours, ['HIGH']).forEach(function (e) {
        syms.forEach(function (s) {
          if (s.base === e.country || s.quote === e.country) vetoes.push([s.name, e]);
        });
      });
      if (vetoes.length) {
        parts.push('');
        parts.push('▎🚫 پنجره‌های ممنوعهٔ ورود (۳۰ دقیقه قبل و بعد از هر رویداد پراثر)');
        var byEv = {};
        vetoes.forEach(function (x) {
          var e = x[1];
          var k = e.when + '|' + e.title_fa + '|' + O.evCountryFa(e);
          (byEv[k] = byEv[k] || { when: e.when, title: e.title_fa, country: O.evCountryFa(e), names: [] }).names.push(x[0]);
        });
        Object.keys(byEv).sort(function (a, b) { return byEv[a].when - byEv[b].when; }).slice(0, 6).forEach(function (k) {
          var g = byEv[k];
          var when = new Date(g.when);
          var w = new Date(g.when - 30 * 60000), t = new Date(g.when + 30 * 60000);
          parts.push('  • ' + O.WEEKDAY_FA[O.pyWeekday(when)] + ' ' + O.faNum(O.hhmm(when)) + ' UTC — ' +
            g.title + ' (' + g.country + ')');
          parts.push('       ⛔ ورود ممنوع: ' + O.faNum(O.hhmm(w)) + ' تا ' + O.faNum(O.hhmm(t)) +
            ' UTC → نمادهای متاثر: ' + Array.from(new Set(g.names)).sort().join('، '));
        });
      }
    }

    // ۳) تیترهای مهم
    if (newsSnap && newsSnap.ok) {
      parts.push('');
      parts.push('▎📰 تیترهایی که بازار امروز با آن‌ها باز می‌شود');
      var movers = newsSnap.items.filter(function (i) { return i.score >= 4 && !i.roundup; }).slice(0, 6);
      (movers.length ? movers : newsSnap.items.slice(0, 4)).forEach(function (it) {
        var flag = it.breaking ? '🚨' : '•';
        var dfa = O.newsDirectionFa(it);
        parts.push('  ' + flag + ' ' + O.headlineFa(it, 70) + (dfa ? ' ← ' + dfa : ''));
      });
      if (!movers.length) parts.push('  ℹ️ خبر پراثری با امتیاز بالا پیدا نشد');
    }

    // ۴) جهت مورد انتظار هر جفت‌ارز
    parts.push('');
    parts.push('▎📊 جهت مورد انتظار هر نماد (تحلیل تکنیکال)');
    if (analyses.length) {
      analyses.forEach(function (a) {
        if (a.verdict === 'DATA') { parts.push('  ⚠️ ' + a.symbol + ': داده کافی نیست'); return; }
        var arrow = { BUY_SETUP: '🟢', SELL_SETUP: '🔴', RANGE: '⚪', WAIT: '⏳' }[a.verdict] || '❔';
        var lvl = [];
        if (a.support) lvl.push('حمایت ' + O.fmtPrice(a.support, a.pip));
        if (a.resistance) lvl.push('مقاومت ' + O.fmtPrice(a.resistance, a.pip));
        parts.push('  ' + arrow + ' ' + a.symbol + ': روند ' + O.TREND_FA[a.trend] + ' | ADX ' +
          O.faNum(O.pyFixed(a.adx, 0)) + ' | RSI ' + O.faNum(O.pyFixed(a.rsi, 0)) + ' | قیمت ' +
          O.fmtPrice(a.price, a.pip) + (lvl.length ? ' | ' + lvl.join('، ') : ''));
        parts.push('       ' + (O.VERDICT_FA[a.verdict] || a.verdict));
      });
    } else {
      parts.push('  ⚠️ هیچ نمادی تحلیل نشد');
    }

    // ۵) قدرت ارزها
    if (ranking.length) {
      parts.push('');
      parts.push('▎💱 جریان قدرت ارزها (۲۴ ساعت اخیر)');
      parts.push('  ' + ranking.map(function (x) { return x[0] + ' (' + O.rFmt(x[1]) + '٪)'; }).join('  >  '));
      var fx = ranking.map(function (x) { return x[0]; }).filter(function (c) { return c !== 'XAU'; });
      if (fx.length >= 2) {
        parts.push('  💡 ایده: قوی‌ترین (' + fx[0] + ') در برابر ضعیف‌ترین (' + fx[fx.length - 1] + ') — هم‌جهت با جریان پول');
      }
    }

    parts.push('');
    parts.push('⚠️ این بریفینگ فقط تحلیل است، نه دستور معامله — تصمیم نهایی با شماست');
    return parts;
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
