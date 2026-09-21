/* نمودار کندل‌استیک (v0.17.0) — SVG درون‌خطی، بدون هیچ کتابخانهٔ خارجی.
 *
 * چرا SVG و نه Canvas؟ کل اپ با رشتهٔ HTML رندر می‌شود (innerHTML)؛ SVG هم
 * همان‌جا بدون hook پس‌از‌رندر کار می‌کند، با تم شیشه‌ای هم‌خانواده است و در
 * تست‌های بدون DOM هم قابل سنجش است (مثل sparkline).
 *
 * O.renderCandleChart(candles, opts) → رشتهٔ <svg>
 *   candles: [{t,o,h,l,c}] صعودی زمانی (H1 یا H4 — H4 با O.resample4h ساخته می‌شود)
 *   opts: { pip, levels:[{price,color,label,dash}], height, maxBars, lastLabel }
 * رنگ‌ها: فقط سبز/قرمز معنایی تم + مونوکروم (قرارداد طراحی اپ).
 * همهٔ برچسب‌های عددی لاتین‌اند (قرارداد قیمت‌ها در اپ).
 */
(function (O) {
  'use strict';

  var W = 680;                     // viewBox — با width:100% مقیاس می‌شود
  var PAD_L = 6, PAD_R = 74, PAD_T = 10, PAD_B = 26;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // «برچسب‌خوانا» برای محور قیمت — همان دقتِ fmtPrice ولی بدون ارقام فارسی
  function axisPrice(v, pip) {
    var dec = pip > 0 ? Math.max(0, Math.min(6, Math.round(-Math.log10(pip)) + 1)) : 2;
    return O.pyFixed(v, dec);
  }

  O.renderCandleChart = function (candles, opts) {
    opts = opts || {};
    var H = opts.height || 300;
    if (!candles || candles.length < 2) {
      return '<div class="empty-state" style="padding:20px"><div class="e-t">دادهٔ نمودار کافی نیست</div></div>';
    }
    var maxBars = opts.maxBars || candles.length;
    var cs = candles.slice(-Math.min(maxBars, candles.length));
    var pip = opts.pip > 0 ? opts.pip : 0.0001;
    var levels = (opts.levels || []).filter(function (l) { return l && isFinite(l.price); });

    // دامنهٔ قیمت: کندل‌ها + سطوح (تا خط SL/TP همیشه داخل کادر باشد)
    var lo = Infinity, hi = -Infinity;
    cs.forEach(function (c) { if (c.l < lo) lo = c.l; if (c.h > hi) hi = c.h; });
    levels.forEach(function (l) { if (l.price < lo) lo = l.price; if (l.price > hi) hi = l.price; });
    var rng = (hi - lo) || hi * 0.001 || 1;
    lo -= rng * 0.04; hi += rng * 0.04; rng = hi - lo;

    var plotW = W - PAD_L - PAD_R, plotH = H - PAD_T - PAD_B;
    function yOf(p) { return PAD_T + (hi - p) / rng * plotH; }
    var n = cs.length;
    var step = plotW / n;
    var bw = Math.max(1.4, Math.min(12, step * 0.62));   // پهنای بدنه

    var up = 'var(--green)', dn = 'var(--red)';
    var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;height:auto;display:block" dir="ltr" aria-label="نمودار کندل‌استیک">';

    // خطوط افقی شبکه + برچسب قیمت (۴ تقسیم)
    for (var g = 0; g <= 4; g++) {
      var pv = hi - (rng * g / 4);
      var gy = yOf(pv);
      s += '<line x1="' + PAD_L + '" y1="' + gy.toFixed(1) + '" x2="' + (W - PAD_R) + '" y2="' + gy.toFixed(1) +
        '" stroke="var(--divider)" stroke-width="1"/>';
      s += '<text x="' + (W - PAD_R + 6) + '" y="' + (gy + 3).toFixed(1) +
        '" font-size="10" fill="var(--text-3)" font-family="Consolas,monospace">' + esc(axisPrice(pv, pip)) + '</text>';
    }

    // سطوح (حمایت/مقاومت/ورود/SL/TP) — خط‌چین + برچسب
    levels.forEach(function (l) {
      var ly = yOf(l.price);
      if (ly < PAD_T - 2 || ly > H - PAD_B + 2) return;
      s += '<line x1="' + PAD_L + '" y1="' + ly.toFixed(1) + '" x2="' + (W - PAD_R) + '" y2="' + ly.toFixed(1) +
        '" stroke="' + l.color + '" stroke-width="1.3" stroke-dasharray="' + (l.dash || '5 4') + '" opacity="0.85"/>';
      if (l.label) {
        s += '<text x="' + (PAD_L + 4) + '" y="' + (ly - 3.5).toFixed(1) + '" font-size="9.5" fill="' + l.color +
          '" font-weight="700">' + esc(l.label) + '</text>';
      }
    });

    // کندل‌ها
    for (var i = 0; i < n; i++) {
      var c = cs[i];
      var x = PAD_L + i * step + step / 2;
      var bull = c.c >= c.o;
      var col = bull ? up : dn;
      var yO = yOf(c.o), yC = yOf(c.c), yH = yOf(c.h), yL = yOf(c.l);
      var top = Math.min(yO, yC), bh = Math.max(1, Math.abs(yC - yO));
      s += '<line x1="' + x.toFixed(1) + '" y1="' + yH.toFixed(1) + '" x2="' + x.toFixed(1) + '" y2="' + yL.toFixed(1) +
        '" stroke="' + col + '" stroke-width="1" opacity="0.9"/>';
      s += '<rect x="' + (x - bw / 2).toFixed(1) + '" y="' + top.toFixed(1) + '" width="' + bw.toFixed(1) +
        '" height="' + bh.toFixed(1) + '" rx="0.8" fill="' + col + '"/>';
    }

    // برچسب زمان (تهران) — ۴ نقطه: MM/DD HH:MM
    for (var ti = 0; ti < 4; ti++) {
      var idx = Math.min(n - 1, Math.round((n - 1) * ti / 3));
      var d = O.tehran(new Date(cs[idx].t));
      var lbl = String(d.getUTCMonth() + 1).padStart(2, '0') + '/' +
        String(d.getUTCDate()).padStart(2, '0') + ' ' + O.hhmm(d);
      var tx = PAD_L + idx * step + step / 2;
      s += '<text x="' + tx.toFixed(1) + '" y="' + (H - 8) + '" font-size="9" fill="var(--text-3)" text-anchor="middle" font-family="Consolas,monospace">' + esc(lbl) + '</text>';
    }

    // قرص قیمت آخرین کندل (محور راست)
    var last = cs[n - 1];
    var ly2 = Math.max(PAD_T + 8, Math.min(H - PAD_B - 8, yOf(last.c)));
    s += '<rect x="' + (W - PAD_R + 3) + '" y="' + (ly2 - 8.5).toFixed(1) + '" width="66" height="17" rx="8.5" fill="var(--ink)"/>';
    s += '<text x="' + (W - PAD_R + 36) + '" y="' + (ly2 + 3.5).toFixed(1) + '" font-size="10" fill="#fff" text-anchor="middle" font-weight="700" font-family="Consolas,monospace">' +
      esc(axisPrice(last.c, pip)) + '</text>';

    s += '</svg>';
    return s;
  };

  /** رنگ‌های استاندارد سطوح (تم اپ) */
  O.CHART_COLORS = {
    entry: 'var(--ink)',
    sl: 'var(--red)',
    tp: 'var(--green)',
    support: 'var(--text-3)',
    resistance: 'var(--text-3)'
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
