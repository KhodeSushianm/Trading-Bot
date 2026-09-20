/* سشن‌های بازار فارکس — پورت دقیق src/judge/session.py (همه ساعت‌ها UTC)
 *
 * ⚠️ همان نکتهٔ صادقانهٔ نسخهٔ دسکتاپ: ساعت تابستانی لندن/نیویورک دقیق
 * محاسبه نمی‌شود؛ بازهٔ «میانه» در بیشتر سال درست است و فقط روی
 * ۱ امتیاز از ۱۱ اثر دارد (هرگز وتو نمی‌سازد).
 */
(function (O) {
  'use strict';

  // نام سشن → [شروع، پایان] به UTC؛ پایان ≤ شروع یعنی از نیمه‌شب رد می‌شود
  O.SESSIONS = { 'سیدنی': [21, 6], 'توکیو': [0, 9], 'لندن': [7, 16], 'نیویورک': [12, 21] };
  var LIQUID = ['لندن', 'نیویورک'];
  var OVERLAP = [12, 16];
  var FRIDAY_CLOSE_HOUR = 21;
  var SUNDAY_OPEN_HOUR = 22;

  O.sessionsOf = function (now) {
    var h = now.getUTCHours() + now.getUTCMinutes() / 60;
    var active = [];
    for (var name in O.SESSIONS) {
      var s = O.SESSIONS[name][0], e = O.SESSIONS[name][1];
      var inside = (s <= e) ? (s <= h && h < e) : (h >= s || h < e);
      if (inside) active.push(name);
    }
    return active;
  };

  O.sessionLabel = function (sessions, overlap, isOpen) {
    if (!isOpen) return 'بازار بسته 🔒';
    if (!sessions.length) return 'بین دو سشن (خلأ نقدینگی)';
    var txt = sessions.join(' + ');
    return overlap ? txt + ' (هم‌پوشانی — بهترین نقدینگی ⭐)' : txt;
  };

  O.marketStatus = function (now) {
    var wd = O.pyWeekday(now);              // 0=دوشنبه … 4=جمعه 5=شنبه 6=یکشنبه
    var h = now.getUTCHours();

    if (wd === 5) {
      return { open: false, reason_fa: 'شنبه — بازار فارکس بسته است 🔒', sessions: [], overlap: false, liquid: false, label: 'بازار بسته 🔒' };
    }
    if (wd === 6 && h < SUNDAY_OPEN_HOUR) {
      return { open: false, reason_fa: 'یکشنبه — بازار تا ساعت ' + SUNDAY_OPEN_HOUR + ':۰۰ UTC بسته است 🔒', sessions: [], overlap: false, liquid: false, label: 'بازار بسته 🔒' };
    }
    if (wd === 4 && h >= FRIDAY_CLOSE_HOUR) {
      return { open: false, reason_fa: 'جمعه شب — بازار از ساعت ' + FRIDAY_CLOSE_HOUR + ':۰۰ UTC بسته شد 🔒', sessions: [], overlap: false, liquid: false, label: 'بازار بسته 🔒' };
    }
    var sessions = O.sessionsOf(now);
    var overlap = (OVERLAP[0] <= h && h < OVERLAP[1]) &&
      sessions.indexOf('لندن') >= 0 && sessions.indexOf('نیویورک') >= 0;
    var liquid = sessions.some(function (s) { return LIQUID.indexOf(s) >= 0; });
    return {
      open: true, reason_fa: '', sessions: sessions, overlap: overlap, liquid: liquid,
      label: O.sessionLabel(sessions, overlap, true)
    };
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
