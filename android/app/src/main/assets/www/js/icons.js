/* کتابخانهٔ آیکون SVG — جایگزین ایموجی در همهٔ رابط (v0.13.0)
 *
 * طراحی: همهٔ آیکون‌ها ۲۴×۲۴، خطی (stroke=currentColor، ضخامت ۱.۸، لبهٔ گرد) —
 * هم‌خانوادهٔ آیکون‌های نوار تب در index.html تا ظاهر یکدست بماند.
 *
 * دو API:
 *   O.ico(name, size, cls)  →  رشتهٔ SVG درون‌خطی (برای متن‌های static UI)
 *   O.icoStr(text, size)    →  ایموجی‌های «رشته‌های موتور» را با آیکون جایگزین می‌کند.
 *       چرا؟ رشته‌های judge/technical/calendar/session/news/journal/briefing
 *       با موتور پایتون parity دارند و نباید دست بخورند؛ تبدیل فقط در لایهٔ
 *       رندر انجام می‌شود. ورودی باید از قبل esc() شده باشد (ایموجی‌ها را
 *       esc تغییر نمی‌دهد، پس تداخلی نیست).
 */
(function (O) {
  'use strict';

  // name → markup داخلی SVG (ریشه fill=none stroke=currentColor دارد؛
  // موارد «توپر» با fill/stroke درون‌ own element اورراید می‌شوند)
  var P = {
    // ── ناوبری/بخش‌ها ──────────────────────────────────────────
    home: '<path d="M3.5 10.5 12 3.8l8.5 6.7V20a1 1 0 0 1-1 1h-4.6v-5.6H9.1V21H4.5a1 1 0 0 1-1-1z"/>',
    scale: '<path d="M12 4.8v14.4M8.5 19.2h7"/><circle cx="12" cy="4" r="1.2"/><path d="M4.4 9.6 12 7.2l7.6 2.4"/><path d="M4.4 9.6 2.2 14a2.7 2.7 0 0 0 4.4 0z"/><path d="M19.6 9.6 17.4 14a2.7 2.7 0 0 0 4.4 0z"/>',
    calendar: '<rect x="3.5" y="5" width="17" height="16" rx="2.6"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    news: '<path d="M4 5h13a1 1 0 0 1 1 1v13a2 2 0 0 0 2 2H6a2 2 0 0 1-2-2z"/><path d="M7.5 9h6M7.5 12.5h6M7.5 16h3.5"/>',
    book: '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z"/><path d="M5 19.5A1.5 1.5 0 0 1 6.5 18H19v3H6.5A1.5 1.5 0 0 1 5 19.5zM9 7.5h6"/>',
    'book-open': '<path d="M12 6.5C10.5 5.2 8.7 4.6 6.5 4.6h-3v13h3c2.2 0 4 .6 5.5 1.9 1.5-1.3 3.3-1.9 5.5-1.9h3v-13h-3c-2.2 0-4 .6-5.5 1.9z"/><path d="M12 6.5v13"/>',
    gear: '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.8v2.6M12 18.6v2.6M2.8 12h2.6M18.6 12h2.6M5.5 5.5l1.8 1.8M16.7 16.7l1.8 1.8M18.5 5.5l-1.8 1.8M7.3 16.7l-1.8 1.8"/>',
    sunrise: '<path d="M12 3.5v2.8M5.2 6.7l2 2M18.8 6.7l-2 2M2.8 13.5h2.6M18.6 13.5h2.6"/><path d="M7.2 13.5a4.8 4.8 0 0 1 9.6 0"/><path d="M3 17.5h18M7.5 21h9"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11.2v5M12 7.9h.01"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6.8v5.4l3.4 2"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4.8 20.4a7.2 7.2 0 0 1 14.4 0"/>',

    // ── کنش‌ها ─────────────────────────────────────────────────
    refresh: '<path d="M20.6 12a8.6 8.6 0 1 1-2.8-6.35"/><path d="M20.9 3.6v4.9H16"/>',
    share: '<path d="M12 3.5v11"/><path d="M8.2 7 12 3.2 15.8 7"/><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/>',
    save: '<path d="M12 3v11.2"/><path d="M7.8 10.4 12 14.6l4.2-4.2"/><path d="M4.5 17v2.5a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V17"/>',
    trash: '<path d="M4 6.8h16"/><path d="M9.5 6.8V4.4h5v2.4"/><path d="M6.4 6.8 7.5 20a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1L17.6 6.8"/><path d="M10.4 10.6v6.2M13.6 10.6v6.2"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M20.4 20.4 16.2 16.2"/>',
    repeat: '<path d="M4.6 9.6A6.5 6.5 0 0 1 11 5.2h6.4"/><path d="M15 2.7 17.7 5.2 15 7.7"/><path d="M19.4 14.4A6.5 6.5 0 0 1 13 18.8H6.6"/><path d="M9 16.3 6.3 18.8 9 21.3"/>',

    // ── جهت/روند ───────────────────────────────────────────────
    'trend-up': '<path d="M3.5 16.8 9.6 10.7l3.8 3.8 7.1-8"/><path d="M15.4 6.5h5.1v5.1"/>',
    'trend-down': '<path d="M3.5 7.2 9.6 13.3l3.8-3.8 7.1 8"/><path d="M15.4 17.5h5.1v-5.1"/>',
    'arrow-up-right': '<path d="M7 17 17 7"/><path d="M9.2 7H17v7.8"/>',
    'arrow-down-right': '<path d="M7 7l10 10"/><path d="M17 9.2V17H9.2"/>',
    'arrow-up': '<path d="M12 20V4.6"/><path d="M6 10.4 12 4.4l6 6"/>',
    'arrow-down': '<path d="M12 4v15.4"/><path d="M6 13.6l6 6 6-6"/>',
    'chevron-left': '<path d="M14.5 5.5 8 12l6.5 6.5"/>',
    'chevron-right': '<path d="M9.5 5.5 16 12l-6.5 6.5"/>',
    'chevron-down': '<path d="M5.5 9.2 12 15.6l6.5-6.4"/>',
    'chevron-up': '<path d="M5.5 14.8 12 8.4l6.5 6.4"/>',

    // ── وضعیت/قضاوت ────────────────────────────────────────────
    'dot-high': '<circle cx="12" cy="12" r="6" fill="currentColor" stroke="none"/>',
    'dot-med': '<circle cx="12" cy="12" r="6" fill="currentColor" stroke="none"/>',
    'dot-low': '<circle cx="12" cy="12" r="6" fill="currentColor" stroke="none"/>',
    'dot-none': '<circle cx="12" cy="12" r="5.4"/>',
    dot: '<circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/>',
    'check-circle': '<circle cx="12" cy="12" r="9"/><path d="M8.2 12.3 11 15.1l4.9-6.1"/>',
    check: '<path d="M4.8 12.4 9.6 17.2 19.2 6.8"/>',
    'x-circle': '<circle cx="12" cy="12" r="9"/><path d="M9.1 9.1l5.8 5.8M14.9 9.1l-5.8 5.8"/>',
    minus: '<path d="M6 12h12"/>',
    unknown: '<circle cx="12" cy="12" r="9"/><path d="M9.3 9.4a2.8 2.8 0 0 1 5.4 1c0 1.9-2.7 2.3-2.7 4.2"/><path d="M12 17.7h.01"/>',
    alert: '<path d="M12 3.8 21.6 20H2.4z"/><path d="M12 9.8v4.4M12 17.2h.01"/>',
    ban: '<circle cx="12" cy="12" r="9"/><path d="M5.7 5.7l12.6 12.6"/>',
    'no-entry': '<circle cx="12" cy="12" r="9"/><path d="M7.2 12h9.6"/>',
    lock: '<rect x="4.6" y="10" width="14.8" height="10.4" rx="2.4"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><path d="M12 14v2.6"/>',
    shuffle: '<path d="M4 6.6h3.4c1.4 0 2.3.7 3.2 1.9l2.8 3.8c.9 1.2 1.8 1.9 3.2 1.9H20"/><path d="M17.4 11.7 20.2 14.2l-2.8 2.5"/><path d="M4 17.6h3.4c1.4 0 2.3-.7 3.2-1.9l.6-.8"/><path d="M14.6 9.4l.6-.8c.9-1.2 1.8-1.9 3.2-1.9h1.6"/>',
    moon: '<path d="M20.2 14.4A8.6 8.6 0 0 1 9.6 3.8a8.6 8.6 0 1 0 10.6 10.6z"/>',
    siren: '<path d="M6.3 10.6a5.7 5.7 0 0 1 11.4 0c0 3.6.7 5.3 1.6 6.3H4.7c.9-1 1.6-2.7 1.6-6.3z"/><path d="M9.9 20.4a2.3 2.3 0 0 0 4.2 0"/><path d="M12 2.6v1.8M4.4 5.2l1.3 1.3M19.6 5.2l-1.3 1.3"/>',
    target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/>',
    'stop-sign': '<path d="M8.3 3.6h7.4l4.7 4.7v7.4l-4.7 4.7H8.3l-4.7-4.7V8.3z"/><path d="M9 12h6"/>',
    hourglass: '<path d="M7 3.6h10v3.1L12 12l5 5.3v3.1H7v-3.1L12 12 7 6.7z"/>',
    star: '<path d="M12 3.6l2.6 5.5 6 .8-4.4 4.2 1.1 6-5.3-2.9-5.3 2.9 1.1-6L3.4 9.9l6-.8z" fill="currentColor" stroke="none"/>',

    // ── محتوا ──────────────────────────────────────────────────
    antenna: '<circle cx="12" cy="12" r="2.1"/><path d="M7.9 7.9a5.8 5.8 0 0 0 0 8.2M16.1 16.1a5.8 5.8 0 0 0 0-8.2"/><path d="M5.1 5.1a9.8 9.8 0 0 0 0 13.8M18.9 18.9a9.8 9.8 0 0 0 0-13.8"/>',
    exchange: '<path d="M4 8.2h13"/><path d="M14.2 5.2l3 3-3 3"/><path d="M20 15.8H7"/><path d="M9.8 12.8l-3 3 3 3"/>',
    bank: '<path d="M3.6 9.6 12 4.2l8.4 5.4"/><path d="M5.6 10.2v7.6M9.9 10.2v7.6M14.1 10.2v7.6M18.4 10.2v7.6"/><path d="M3.6 20.2h16.8"/>',
    'chart-bar': '<path d="M4 20.2h16"/><rect x="6.1" y="11.2" width="3.6" height="6" rx="1.1"/><rect x="14.3" y="7" width="3.6" height="10.2" rx="1.1"/>',
    'chart-line': '<path d="M4 20.2h16"/><path d="M4.6 15.6 9.2 11l3.4 3.4L19.8 7"/>',
    flag: '<path d="M6.2 21V3.6"/><path d="M6.2 4.4h11.4l-1.9 3.9 1.9 3.9H6.2"/>',
    bell: '<path d="M6.4 10.2a5.6 5.6 0 0 1 11.2 0c0 4 .8 5.8 1.7 6.8H4.7c.9-1 1.7-2.8 1.7-6.8z"/><path d="M10 20.3a2.2 2.2 0 0 0 4 0"/>',
    archive: '<rect x="3.4" y="4" width="17.2" height="4.6" rx="1.4"/><path d="M5.2 8.6V19a1.6 1.6 0 0 0 1.6 1.6h10.4A1.6 1.6 0 0 0 18.8 19V8.6"/><path d="M10 12.4h4"/>',
    plug: '<path d="M9.2 3v4.8M14.8 3v4.8"/><path d="M6.6 7.8h10.8v2.8a5.4 5.4 0 0 1-5.4 5.4 5.4 5.4 0 0 1-5.4-5.4z"/><path d="M12 16v5"/>',
    pin: '<path d="M12 21s7-6.4 7-11.2a7 7 0 1 0-14 0C5 14.6 12 21 12 21z"/><circle cx="12" cy="9.6" r="2.6"/>',
    wave: '<path d="M3 9.4c2-2.6 4-2.6 6 0s4 2.6 6 0 4-2.6 6 0"/><path d="M3 15.4c2-2.6 4-2.6 6 0s4 2.6 6 0 4-2.6 6 0"/>',
    coins: '<ellipse cx="12" cy="6.6" rx="7.2" ry="3"/><path d="M4.8 6.6v4.9c0 1.7 3.2 3 7.2 3s7.2-1.3 7.2-3V6.6"/><path d="M4.8 11.5v5c0 1.6 3.2 2.9 7.2 2.9s7.2-1.3 7.2-2.9v-5"/>',
    seal: '<path d="M12 3.2l7.4 2.9v5.4c0 4.4-3.1 8.1-7.4 9.4-4.3-1.3-7.4-5-7.4-9.4V6.1z"/><path d="M8.9 12.1 11.2 14.5l4.1-4.9"/>',
    link: '<path d="M10.3 13.7a3.6 3.6 0 0 1 0-5.1l1.6-1.6a3.6 3.6 0 0 1 5.1 5.1l-.9.9"/><path d="M13.7 10.3a3.6 3.6 0 0 1 0 5.1l-1.6 1.6a3.6 3.6 0 0 1-5.1-5.1l.9-.9"/>',
    bulb: '<path d="M9.6 17.8h4.8M10.4 20.8h3.2"/><path d="M12 3.2a6 6 0 0 0-3.5 10.9v1.7h7v-1.7A6 6 0 0 0 12 3.2z"/>',
    smile: '<circle cx="12" cy="12" r="9"/><path d="M8.4 13.9a4.6 4.6 0 0 0 7.2 0"/><path d="M9.1 9.6h.01M14.9 9.6h.01"/>',
    hash: '<path d="M5 9.2h14M5 14.8h14M10.2 4.2 8.8 19.8M16 4.2l-1.4 15.6"/>',
    activity: '<path d="M3.4 12.6h3.9L9.9 6.4l4.2 11.2 2.4-5h4.1"/>',
    battery: '<rect x="2.6" y="7.6" width="16.8" height="8.8" rx="2.3"/><path d="M21.8 10.8v2.4"/><path d="M6.2 10.6v2.8M9.7 10.6v2.8M13.2 10.6v2.8"/>'
  };
  O.ICO = P;

  O.ico = function (name, size, cls) {
    var d = P[name] || P.dot;
    var s = size || 16;
    return '<svg class="ico' + (cls ? ' ' + cls : '') + '" viewBox="0 0 24 24" width="' + s +
      '" height="' + s + '" fill="none" stroke="currentColor" stroke-width="1.8" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + d + '</svg>';
  };

  // ستاره‌های امتیاز (n از ۵) — جای O.stars در رندر
  O.starIcons = function (n) {
    n = Math.max(0, Math.min(5, Math.trunc(n || 0)));
    var h = '';
    for (var i = 0; i < n; i++) h += O.ico('star', 13);
    return h;
  };

  // ── نقشهٔ ایموجی → آیکون (برای رشته‌های موتور؛ [name, cls]) ──
  var EMOJI = {
    '📈': ['trend-up', ''], '📉': ['trend-down', ''],
    '↗': ['arrow-up-right', 'c-green'], '↘': ['arrow-down-right', 'c-red'],
    '↑': ['arrow-up', 'c-green'], '↓': ['arrow-down', 'c-red'],
    '🟢': ['dot-low', 'c-green'], '🟠': ['dot-med', 'c-amber'],
    '🔴': ['dot-high', 'c-red'], '⚪': ['dot-none', ''],
    '✅': ['check-circle', 'c-green'], '✓': ['check', 'c-green'],
    '❌': ['x-circle', 'c-red'], '➖': ['minus', ''],
    '❔': ['unknown', ''], '⚠': ['alert', 'c-amber'],
    '⛔': ['no-entry', 'c-red'], '🚫': ['ban', 'c-red'],
    '🔒': ['lock', ''], '🔀': ['shuffle', ''], '😴': ['moon', ''],
    '🚨': ['siren', 'c-red'], '🎯': ['target', 'c-green'],
    '🛑': ['stop-sign', 'c-red'], '⏳': ['hourglass', ''],
    '📡': ['antenna', ''], '💱': ['exchange', ''], '🏦': ['bank', ''],
    '📅': ['calendar', ''], '🗓': ['calendar', ''], '📰': ['news', ''],
    '📔': ['book', ''], '📚': ['book-open', ''], '📊': ['chart-bar', ''],
    '💹': ['chart-line', ''], '🏁': ['flag', ''], '🌅': ['sunrise', ''],
    '🕐': ['clock', ''], '🕒': ['clock', ''], '🔔': ['bell', ''],
    '🔄': ['refresh', ''], '⟳': ['refresh', ''], '📤': ['share', ''],
    '💾': ['save', ''], '🗄': ['archive', ''], '🗑': ['trash', ''],
    '⚙': ['gear', ''], '👤': ['user', ''], '⚖': ['scale', ''],
    '🔌': ['plug', ''], '🔍': ['search', ''], '🔎': ['search', ''],
    'ℹ': ['info', ''], '🔏': ['seal', ''], '🔗': ['link', ''],
    '📍': ['pin', ''], '📌': ['pin', ''], '🌊': ['wave', ''],
    '💰': ['coins', ''], '💡': ['bulb', 'c-amber'], '🔁': ['repeat', ''],
    '🙂': ['smile', ''], '🔢': ['hash', ''], '⭐': ['star', 'c-amber'],
    '←': ['chevron-left', ''], '→': ['chevron-right', ''],
    '▾': ['chevron-down', ''], '▴': ['chevron-up', '']
  };
  // کلیدهای چندکدپیکسلی (سورشیت astral) اول جایگزین شوند
  var KEYS = Object.keys(EMOJI).sort(function (a, b) { return b.length - a.length; });

  /** ایموجی‌های متن (esc‌شده) را با SVG جایگزین می‌کند. */
  O.icoStr = function (s, size) {
    var out = String(s == null ? '' : s).replace(/\uFE0F/g, '');
    for (var i = 0; i < KEYS.length; i++) {
      var k = KEYS[i];
      if (out.indexOf(k) < 0) continue;
      var m = EMOJI[k];
      out = out.split(k).join(O.ico(m[0], size || 13, m[1]));
    }
    return out;
  };

  /** ایموجی‌ها را بی‌آنکه آیکونی بگذارد حذف می‌کند (متن ساده: اعلان/لاگ) */
  O.noEmoji = function (s) {
    var out = String(s == null ? '' : s).replace(/\uFE0F/g, '');
    for (var i = 0; i < KEYS.length; i++) out = out.split(KEYS[i]).join('');
    return out.replace(/ {2,}/g, ' ').trim();
  };

  /** بررسی باقی‌ماندن ایموجی (برای تست‌ها) */
  O.EMOJI_RE = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{2190}-\u{21FF}\u{2300}-\u{23FF}\u{25B8}-\u{25C2}\u{25B4}\u{25BE}\uFE0F\u2713\u2717\u2726]/u;
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
