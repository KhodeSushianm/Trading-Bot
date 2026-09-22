/* کارت تصویری سیگنال (v0.18.0) — برای اشتراک در تلگرام/واتساپ/اینستاگرام.
 *
 * دو لایه:
 *   O.buildShareSpec(sig, opt)   → دادهٔ ساختاریافتهٔ کارت (خالص، بدون DOM —
 *                                  در Node با smoke_share.js تست می‌شود)
 *   O.renderShareCanvas(spec)    → رسم روی Canvas (فقط مرورگر/WebView) و
 *                                  برگرداندن canvas برای toDataURL
 *
 * طراحی: کارت مشکی (همان زبان بصری splash/ink اپ)، سبز/قرمز روشنِ روی مشکی،
 * فونت وزیرمتن، قیمت‌ها لاتین و شمارش‌ها فارسی (قرارداد سراسری اپ)،
 * فوتر: سازنده + تلگرام رسمی (بازاریابی هنگام دست‌به‌دست‌شدن کارت).
 */
(function (O) {
  'use strict';

  var CW = 1080, CH = 1350;          // نسبت ۴:۵ — بهینهٔ اینستاگرام/تلگرام

  // ── لایهٔ ۱: spec (خالص) ─────────────────────────────────────
  O.buildShareSpec = function (sig, opt) {
    opt = opt || {};
    var pip = sig.pip > 0 ? sig.pip : 0.0001;
    var now = new Date(sig.now || Date.now());
    return {
      w: CW, h: CH,
      brand: 'ODIN ASSISTANT',
      brandSub: 'دستیار تحلیل فارکس و طلا — غیرخودکار',
      dir: sig.direction === 'BUY' ? 'BUY' : 'SELL',
      dirLabel: sig.direction === 'BUY' ? 'سیگنال خرید' : 'سیگنال فروش',
      pair: String(sig.symbol).length === 6
        ? sig.symbol.slice(0, 3) + '/' + sig.symbol.slice(3) : String(sig.symbol),
      faName: sig.fa_name || '',
      stars: Math.max(0, Math.min(5, Math.trunc(sig.stars || 0))),
      scoreFa: O.faNum(sig.score) + ' از ' + O.faNum(sig.max_score),
      scorePct: sig.max_score ? Math.max(0, Math.min(1, sig.score / sig.max_score)) : 0,
      entry: O.fmtPrice(sig.entry, pip),
      sl: O.fmtPrice(sig.sl, pip),
      tp: O.fmtPrice(sig.tp, pip),
      slDist: O.faPips(Math.abs(sig.entry - sig.sl), pip, sig.is_gold),
      tpDist: O.faPips(Math.abs(sig.tp - sig.entry), pip, sig.is_gold),
      rr: 'ریسک به ریسک ۱:' + O.faRatio(sig.rr),
      jalali: O.jalaliFa(now),
      timeTeh: O.faNum(O.hhmmTeh(now)) + ' تهران',
      session: sig.session_fa || '',
      disclaimer: 'این یک پیشنهاد است، نه دستور معامله — مسئولیت هر معامله با خودت است.',
      footerName: 'سازنده: Sushian Khoshkhani',
      footerTg: '@Khode_Sushian',
      // fallback عمداً 'dev' است نه یک شمارهٔ نسخهٔ واقعی — مُهرِ نسخه روی
      // کارت اشتراکِ بازاریابی می‌نشیند، پس عددِ کهنه یعنی تبلیغِ غلط.
      version: 'v' + (opt.version || 'dev')
    };
  };

  // ── لایهٔ ۲: رندر Canvas (فقط مرورگر) ────────────────────────
  var C = {
    bg0: '#1A1A1F', bg1: '#101013', bg2: '#0A0A0D',
    tile: '#26262B', tileBorder: '#33333A',
    text: '#FFFFFF', dim: 'rgba(255,255,255,.62)', faint: 'rgba(255,255,255,.42)',
    green: '#7BE0B0', greenBg: 'rgba(123,224,176,.12)',
    red: '#FF9A9A', redBg: 'rgba(255,154,154,.12)',
    amber: '#E8B84B', line: 'rgba(255,255,255,.14)'
  };

  function fa(ctx, weight, size) { ctx.font = weight + ' ' + size + 'px Vazirmatn, Tahoma, sans-serif'; }
  function mono(ctx, weight, size) { ctx.font = weight + ' ' + size + 'px Consolas, "Courier New", monospace'; }

  function rr(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function star(ctx, cx, cy, r, fill) {
    ctx.beginPath();
    for (var i = 0; i < 10; i++) {
      var rad = (i % 2 === 0) ? r : r * 0.46;
      var a = -Math.PI / 2 + i * Math.PI / 5;
      var x = cx + Math.cos(a) * rad, y = cy + Math.sin(a) * rad;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath();
    if (fill) { ctx.fillStyle = C.amber; ctx.fill(); }
    else { ctx.strokeStyle = 'rgba(232,184,75,.45)'; ctx.lineWidth = 3; ctx.stroke(); }
  }

  function logo(ctx, cx, cy, r) {
    ctx.save();
    ctx.strokeStyle = C.text; ctx.lineWidth = 7; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(cx, cy - r - 12); ctx.lineTo(cx, cy - r + 2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx, cy + r - 2); ctx.lineTo(cx, cy + r + 12); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx - r - 12, cy); ctx.lineTo(cx - r + 2, cy); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx + r - 2, cy); ctx.lineTo(cx + r + 12, cy); ctx.stroke();
    ctx.lineWidth = 6;
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = C.text;
    ctx.beginPath(); ctx.arc(cx, cy, r, -Math.PI / 2, Math.PI / 2); ctx.fill();
    ctx.restore();
  }

  O.renderShareCanvas = function (spec) {
    var cv = document.createElement('canvas');
    cv.width = spec.w || CW; cv.height = spec.h || CH;
    var ctx = cv.getContext('2d');
    var W = cv.width, H = cv.height;
    var buy = spec.dir === 'BUY';
    var acc = buy ? C.green : C.red;
    var accBg = buy ? C.greenBg : C.redBg;
    var P = 64;                        // حاشیهٔ صفحه
    var right = W - P;                 // لبهٔ راست (RTL)

    // پس‌زمینهٔ گرادیان مشکی (مثل کارت ink اپ)
    var g = ctx.createLinearGradient(0, 0, W * 0.4, H);
    g.addColorStop(0, C.bg0); g.addColorStop(0.55, C.bg1); g.addColorStop(1, C.bg2);
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

    // هالهٔ سبز/قرمز ملایم بالای کارت (حس جهت)
    var rg = ctx.createRadialGradient(W * 0.78, 60, 20, W * 0.78, 60, W * 0.75);
    rg.addColorStop(0, buy ? 'rgba(123,224,176,.10)' : 'rgba(255,154,154,.10)');
    rg.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = rg; ctx.fillRect(0, 0, W, H * 0.5);

    // ── سربرگ: لوگو + برند ──
    logo(ctx, right - 34, P + 34, 26);
    ctx.direction = 'ltr'; ctx.textAlign = 'right'; ctx.textBaseline = 'alphabetic';
    fa(ctx, '700', 34); ctx.fillStyle = C.text;
    // letter-spacing دستی برای لاتین
    var bx = right - 92;
    var letters = spec.brand.split('');
    for (var i = letters.length - 1; i >= 0; i--) {
      ctx.fillText(letters[i], bx, P + 32);
      bx -= ctx.measureText(letters[i]).width + 5;
    }
    ctx.direction = 'rtl';
    fa(ctx, '400', 21); ctx.fillStyle = C.faint;
    ctx.fillText(spec.brandSub, right - 92, P + 64);

    // ── قرص جهت ──
    var y = P + 128;
    fa(ctx, '700', 34);
    var pillW = ctx.measureText(spec.dirLabel).width + 130;
    rr(ctx, right - pillW, y, pillW, 76, 38);
    ctx.fillStyle = accBg; ctx.fill();
    ctx.strokeStyle = acc; ctx.lineWidth = 2.5; ctx.stroke();
    // فلش جهت
    ctx.beginPath();
    var ax = right - pillW + 44, ay = y + 38;
    if (buy) { ctx.moveTo(ax, ay + 14); ctx.lineTo(ax, ay - 14); ctx.moveTo(ax - 10, ay - 4); ctx.lineTo(ax, ay - 14); ctx.lineTo(ax + 10, ay - 4); }
    else { ctx.moveTo(ax, ay - 14); ctx.lineTo(ax, ay + 14); ctx.moveTo(ax - 10, ay + 4); ctx.lineTo(ax, ay + 14); ctx.lineTo(ax + 10, ay + 4); }
    ctx.strokeStyle = acc; ctx.lineWidth = 5; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.stroke();
    ctx.direction = 'rtl'; ctx.textAlign = 'right';
    fa(ctx, '700', 34); ctx.fillStyle = acc;
    ctx.fillText(spec.dirLabel, right - 34, y + 50);

    // ── نماد + نام فارسی + ستاره‌ها ──
    y += 116;
    ctx.direction = 'ltr'; ctx.textAlign = 'right';
    fa(ctx, '700', 84); ctx.fillStyle = C.text;
    ctx.fillText(spec.pair, right, y + 40);
    ctx.direction = 'rtl';
    fa(ctx, '400', 25); ctx.fillStyle = C.dim;
    ctx.fillText(spec.faName, right, y + 82);
    // ستاره‌ها (زیر نام، راست‌چین)
    for (var st = 0; st < 5; st++) {
      star(ctx, right - 26 - st * 52, y + 130, 21, st < spec.stars);
    }

    // ── امتیاز: نوار + متن ──
    y += 176;
    fa(ctx, '500', 26); ctx.fillStyle = C.dim; ctx.textAlign = 'right'; ctx.direction = 'rtl';
    ctx.fillText('امتیاز پشتوانه: ' + spec.scoreFa, right, y);
    var barY = y + 18, barH = 16;
    rr(ctx, P, barY, W - 2 * P, barH, 8);
    ctx.fillStyle = C.tile; ctx.fill();
    if (spec.scorePct > 0.02) {
      rr(ctx, P + (W - 2 * P) * (1 - spec.scorePct), barY, (W - 2 * P) * spec.scorePct, barH, 8);
      ctx.fillStyle = acc; ctx.fill();
    }

    // ── سه کاشی سطح (ورود / حد ضرر / هدف) ──
    y = barY + 62;
    var gap = 20, tw = (W - 2 * P - 2 * gap) / 3, th = 178;
    var tiles = [
      { cap: 'هدف (TP)', val: spec.tp, sub: spec.tpDist, col: C.green },
      { cap: 'حد ضرر (SL)', val: spec.sl, sub: spec.slDist, col: C.red },
      { cap: 'ورود', val: spec.entry, sub: 'قیمت فعلی', col: C.text }
    ];
    // ترتیب RTL: هدف راست‌ترین؟ در اپ ورود|SL|TP راست‌به‌چپ است؛ اینجا هم همان
    for (var ti = 0; ti < 3; ti++) {
      var t = tiles[ti];
      var tx = right - (ti + 1) * tw - ti * gap;
      rr(ctx, tx, y, tw, th, 26);
      ctx.fillStyle = C.tile; ctx.fill();
      ctx.strokeStyle = C.tileBorder; ctx.lineWidth = 1.5; ctx.stroke();
      ctx.textAlign = 'center';
      ctx.direction = 'rtl'; fa(ctx, '500', 21); ctx.fillStyle = C.faint;
      ctx.fillText(t.cap, tx + tw / 2, y + 42);
      ctx.direction = 'ltr'; mono(ctx, '700', 37); ctx.fillStyle = t.col;
      ctx.fillText(t.val, tx + tw / 2, y + 98);
      ctx.direction = 'rtl'; fa(ctx, '400', 19); ctx.fillStyle = C.dim;
      ctx.fillText(t.sub, tx + tw / 2, y + 140);
    }

    // ── rr + سشن ──
    y += th + 42;
    ctx.textAlign = 'right'; ctx.direction = 'rtl';
    fa(ctx, '500', 27); ctx.fillStyle = C.dim;
    ctx.fillText(spec.rr + (spec.session ? '  ·  سشن: ' + spec.session : ''), right, y);

    // ── تاریخ ──
    y += 52;
    fa(ctx, '700', 27); ctx.fillStyle = C.text;
    ctx.fillText(spec.jalali + '  ·  ساعت ' + spec.timeTeh, right, y);

    // ── سلب مسئولیت ──
    y += 76;
    ctx.strokeStyle = C.line; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(P, y - 30); ctx.lineTo(right, y - 30); ctx.stroke();
    fa(ctx, '400', 23); ctx.fillStyle = C.faint;
    ctx.fillText(spec.disclaimer, right, y);

    // ── فوتر: سازنده + تلگرام + نسخه ──
    var fy = H - 74;
    ctx.strokeStyle = C.line;
    ctx.beginPath(); ctx.moveTo(P, fy - 42); ctx.lineTo(right, fy - 42); ctx.stroke();
    ctx.direction = 'rtl'; ctx.textAlign = 'right';
    fa(ctx, '700', 25); ctx.fillStyle = C.text;
    ctx.fillText(spec.footerName, right, fy);
    fa(ctx, '400', 21); ctx.fillStyle = C.faint;
    ctx.fillText('خرید لایسنس و پشتیبانی — تلگرام', right, fy + 34);
    ctx.direction = 'ltr'; ctx.textAlign = 'left';
    fa(ctx, '700', 26); ctx.fillStyle = C.green;
    ctx.fillText(spec.footerTg, P, fy);
    fa(ctx, '400', 20); ctx.fillStyle = C.faint;
    ctx.fillText(spec.brand + ' ' + spec.version, P, fy + 34);

    return cv;
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
