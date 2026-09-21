/* هشدارهای قیمت (v0.16.0) — سطح قیمتی کاربر، بررسی در هر چرخهٔ تحلیل.
 *
 * چرا این ماژول جداست؟ چون هم رابط (UI) و هم سرویس رصد پس‌زمینه در
 * cycleCore مشترک‌اند؛ هشدارها در SharedPreferences ذخیره می‌شوند
 * (کلید alerts.json) پس هر چرخه‌ای — اپ باز یا بسته — آن‌ها را بررسی
 * می‌کند و «یک‌بار فعال‌شدن» با حذف رکورد تضمین می‌شود (اعلان دوبله نمی‌رود).
 *
 * رکورد: {id, symbol, dir:'above'|'below', price, pip, sticky, created_at, last_fired}
 *   id = symbol|dir|price  (یکتا؛ ثبت تکراری رد می‌شود)
 *   sticky=false → با اولین فعال‌شدن حذف می‌شود
 *   sticky=true  → می‌ماند و هر STICKY_COOLDOWN یک‌بار دوباره اعلان می‌دهد
 */
(function (O) {
  'use strict';

  var KEY = 'alerts.json';
  var MAX = 20;
  var STICKY_COOLDOWN_MS = 60 * 60 * 1000;
  O.ALERTS_MAX = MAX;

  O.alertsLoad = function (storage) {
    try {
      var raw = storage.get(KEY);
      var arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (e) { return []; }
  };
  function save(storage, arr) {
    try { storage.set(KEY, JSON.stringify(arr)); } catch (e) { }
  }

  O.alertId = function (symbol, dir, price) {
    return symbol + '|' + dir + '|' + price;
  };

  /** افزودن هشدار. → {ok, why?, count?} */
  O.alertsAdd = function (storage, symbol, dir, price, sticky, pip) {
    price = +price;
    if (!symbol || !isFinite(price) || price <= 0) return { ok: false, why: 'invalid' };
    dir = dir === 'below' ? 'below' : 'above';
    var arr = O.alertsLoad(storage);
    var id = O.alertId(symbol, dir, price);
    for (var i = 0; i < arr.length; i++) {
      if (arr[i].id === id) return { ok: false, why: 'duplicate' };
    }
    if (arr.length >= MAX) return { ok: false, why: 'max' };
    arr.unshift({
      id: id, symbol: symbol, dir: dir, price: price,
      pip: pip > 0 ? pip : 0.0001,
      sticky: !!sticky,
      created_at: new Date().toISOString(),
      last_fired: null
    });
    save(storage, arr);
    return { ok: true, count: arr.length };
  };

  O.alertsRemove = function (storage, id) {
    var arr = O.alertsLoad(storage);
    var next = arr.filter(function (a) { return a.id !== id; });
    if (next.length !== arr.length) save(storage, next);
  };

  /**
   * بررسی عبور قیمت در برابر تحلیل‌های یک چرخه.
   * analyses: [{symbol, price, pip, ...}] (خروجی analyzeSymbol)
   * → آرایهٔ هشدارهای فعال‌شده [{a, price, pip}] (برای اعلان/توست).
   * غیرچسبنده‌ها پس از فعال‌شدن حذف می‌شوند؛ چسبنده‌ها کول‌داون می‌گیرند.
   */
  O.alertsCheck = function (storage, analyses, nowMs) {
    var arr = O.alertsLoad(storage);
    if (!arr.length || !analyses || !analyses.length) return [];
    var now = nowMs || Date.now();
    var bySym = {};
    analyses.forEach(function (a) { bySym[a.symbol] = a; });
    var fired = [];
    var keep = [];
    var dirty = false;
    for (var i = 0; i < arr.length; i++) {
      var al = arr[i];
      var an = bySym[al.symbol];
      if (!an || typeof an.price !== 'number' || !isFinite(an.price)) { keep.push(al); continue; }
      var hit = al.dir === 'above' ? (an.price >= al.price) : (an.price <= al.price);
      if (!hit) { keep.push(al); continue; }
      if (al.sticky) {
        var lf = al.last_fired ? Date.parse(al.last_fired) : 0;
        if (!isFinite(lf)) lf = 0;
        if (now - lf >= STICKY_COOLDOWN_MS) {
          al.last_fired = new Date(now).toISOString();
          fired.push({ a: al, price: an.price, pip: an.pip || al.pip });
          dirty = true;
        }
        keep.push(al);
      } else {
        fired.push({ a: al, price: an.price, pip: an.pip || al.pip });
        dirty = true;            // یک‌بار مصرف → حذف (در keep نمی‌آید)
      }
    }
    if (dirty || keep.length !== arr.length) save(storage, keep);
    return fired;
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
