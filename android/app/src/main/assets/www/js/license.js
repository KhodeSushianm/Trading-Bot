/* لایسنس و قفل دستگاه — همزاد دقیقِ src/license.py برای اندروید.
 * v0.15.0: کلید زمان‌دار (انقضا در خود رشتهٔ کلید) + دورهٔ آزمایشی ۷ روزه
 * با high-water-mark ضدِ عقب‌کشیدن ساعت. کلیدهای دائمیِ v0.14 بدون تغییر معتبرند.
 *
 * طرح (یکسان در دو پلتفرم — یک ابزار تولید کلید برای هر دو کافی است):
 *   device_id   = SHA-256 هگز (۶۴ کاراکتر) — در اندروید از ANDROID_ID
 *                 (سمت Bridge.getDeviceId محاسبه می‌شود: sha256("android:"+id))
 *   device_code = ۱۲ رقم اولِ device_id، بالا‌حروف، جداکنندهٔ ۴تایی
 *   key         = HMAC-SHA256(SECRET, device_code) → ۱۶ هگز بالا‌حروف
 *
 * SHA-256/HMAC بدون وابستگی پیاده‌سازی شده (offline، قطعی، تست‌پذیر در Node)
 * تا با hmac پایتون بایت‌به‌بایت برابر بماند — بُرِدهای آزمایشی مشترک در
 * tests/js/smoke_license.js و main.py --selftest قفلش کرده‌اند.
 */
(function (O) {
  'use strict';

  // ⚠️ همان _LICENSE_SECRET در src/license.py — دو طرف با هم عوض شوند
  var SECRET = 'bd604d7cc90e8fe32184e8d6ddb5787c3389438b54156947541f772f61be7347';

  var K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ];

  function rotr(x, n) { return ((x >>> n) | (x << (32 - n))) >>> 0; }

  function utf8Bytes(str) {
    var out = [];
    for (var i = 0; i < str.length; i++) {
      var c = str.charCodeAt(i);
      if (c < 0x80) { out.push(c); }
      else if (c < 0x800) { out.push(0xc0 | (c >> 6), 0x80 | (c & 63)); }
      else if (c >= 0xd800 && c <= 0xdbff && i + 1 < str.length) {
        var c2 = str.charCodeAt(++i);
        var cp = 0x10000 + ((c & 0x3ff) << 10) + (c2 & 0x3ff);
        out.push(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 63),
          0x80 | ((cp >> 6) & 63), 0x80 | (cp & 63));
      } else { out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63)); }
    }
    return out;
  }

  function toHex(bytes, upper) {
    var h = '';
    for (var i = 0; i < bytes.length; i++) {
      h += (bytes[i] < 16 ? '0' : '') + bytes[i].toString(16);
    }
    return upper ? h.toUpperCase() : h;
  }

  /** SHA-256 روی آرایهٔ بایت → آرایهٔ ۳۲ بایت (FIPS 180-4) */
  function sha256(bytes) {
    var H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
    var l = bytes.length;
    // بلوک‌بندی: l بایت داده + ۰x۸۰ + ۸ بایت طول باید در مضرب ۶۴ جا شود.
    // (لنگهٔ l≡55 mod 64 دقیقاً یک بلوک است — آفست +8 نه +9)
    var total = (((l + 8) >> 6) + 1) << 6;
    var msg = bytes.slice();
    msg.push(0x80);
    while (msg.length < total) msg.push(0);
    var bitHi = Math.floor(l / 536870912);       // (l*8) >> 32
    var bitLo = (l << 3) >>> 0;                  // (l*8) & 0xffffffff
    msg[total - 8] = (bitHi >>> 24) & 255; msg[total - 7] = (bitHi >>> 16) & 255;
    msg[total - 6] = (bitHi >>> 8) & 255;  msg[total - 5] = bitHi & 255;
    msg[total - 4] = (bitLo >>> 24) & 255; msg[total - 3] = (bitLo >>> 16) & 255;
    msg[total - 2] = (bitLo >>> 8) & 255;  msg[total - 1] = bitLo & 255;

    var W = new Array(64);
    for (var off = 0; off < total; off += 64) {
      for (var i = 0; i < 16; i++) {
        W[i] = ((msg[off + i * 4] << 24) | (msg[off + i * 4 + 1] << 16) |
          (msg[off + i * 4 + 2] << 8) | msg[off + i * 4 + 3]) >>> 0;
      }
      for (i = 16; i < 64; i++) {
        var x = W[i - 15], y = W[i - 2];
        var s0 = (rotr(x, 7) ^ rotr(x, 18) ^ (x >>> 3)) >>> 0;
        var s1 = (rotr(y, 17) ^ rotr(y, 19) ^ (y >>> 10)) >>> 0;
        W[i] = (W[i - 16] + s0 + W[i - 7] + s1) >>> 0;
      }
      var a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (i = 0; i < 64; i++) {
        var S1 = (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) >>> 0;
        var ch = ((e & f) ^ (~e & g)) >>> 0;
        var t1 = (h + S1 + ch + K[i] + W[i]) >>> 0;
        var S0 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) >>> 0;
        var maj = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
        var t2 = (S0 + maj) >>> 0;
        h = g; g = f; f = e; e = (d + t1) >>> 0;
        d = c; c = b; b = a; a = (t1 + t2) >>> 0;
      }
      H[0] = (H[0] + a) >>> 0; H[1] = (H[1] + b) >>> 0;
      H[2] = (H[2] + c) >>> 0; H[3] = (H[3] + d) >>> 0;
      H[4] = (H[4] + e) >>> 0; H[5] = (H[5] + f) >>> 0;
      H[6] = (H[6] + g) >>> 0; H[7] = (H[7] + h) >>> 0;
    }
    var out = [];
    for (i = 0; i < 8; i++) {
      out.push((H[i] >>> 24) & 255, (H[i] >>> 16) & 255, (H[i] >>> 8) & 255, H[i] & 255);
    }
    return out;
  }

  /** HMAC-SHA256 (RFC 2104) — خروجی هگز کوچک */
  function hmacSha256Hex(keyStr, msgStr) {
    var key = utf8Bytes(keyStr);
    if (key.length > 64) key = sha256(key);
    var ipad = new Array(64), opad = new Array(64);
    for (var i = 0; i < 64; i++) {
      var k = i < key.length ? key[i] : 0;
      ipad[i] = k ^ 0x36;
      opad[i] = k ^ 0x5c;
    }
    var inner = sha256(ipad.concat(utf8Bytes(msgStr)));
    return toHex(sha256(opad.concat(inner)), false);
  }

  // ── API هم‌نام با پایتون ─────────────────────────────────────
  O.sha256Hex = function (s) { return toHex(sha256(utf8Bytes(String(s == null ? '' : s))), false); };
  O.hmacSha256Hex = hmacSha256Hex;

  O.normalizeCode = function (s) {
    return String(s == null ? '' : s).replace(/[^0-9A-Fa-f]/g, '').toUpperCase();
  };
  O.formatCode = function (raw) {
    return String(raw).replace(/(.{4})(?=.)/g, '$1-');
  };
  O.deviceCodeFromId = function (deviceId) {
    return O.formatCode(String(deviceId || '').slice(0, 12).toUpperCase());
  };

  O.LICENSE_TRIAL_DAYS = 7;
  var ROLLBACK_MS = 48 * 3600 * 1000;   // تلورانس عقب‌رفتن ساعت (مثل پایتون)
  var TOUCH_MS = 6 * 3600 * 1000;       // throttle به‌روزرسانی last_seen

  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function ymd8(d) { return '' + d.getFullYear() + pad2(d.getMonth() + 1) + pad2(d.getDate()); }

  /**
   * رشتهٔ کلید → {key:16hex, expiry8:'YYYYMMDD'|null} یا null اگر بدقالبه.
   * دائمی: ۱۶ هگز · زمان‌دار: ۱۶ هگز + ۶ رقم YYMMDD (مثل parse_key_input پایتون)
   */
  O.parseKeyInput = function (raw) {
    var s = String(raw == null ? '' : raw).replace(/[^0-9A-Fa-f]/g, '').toUpperCase();
    if (s.length === 16) return { key: s, expiry8: null };
    if (s.length === 22) {
      var e = s.slice(16);
      var yy = +e.slice(0, 2), mm = +e.slice(2, 4), dd = +e.slice(4, 6);
      if (mm < 1 || mm > 12 || dd < 1 || dd > 31) return null;
      var d = new Date(2000 + yy, mm - 1, dd);
      if (d.getMonth() !== mm - 1 || d.getDate() !== dd) return null;   // مثلاً ۳۱ فوریه
      return { key: s.slice(0, 16), expiry8: '20' + e };
    }
    return null;
  };

  /** تولید کلید — expiry8 اختیاری ('YYYYMMDD'). هم‌فرمت با generate_license_key پایتون */
  O.licenseKeyFor = function (deviceCode, expiry8) {
    var code = O.normalizeCode(deviceCode);
    if (code.length !== 12) return '';
    var msg = expiry8 ? (code + '|' + expiry8) : code;
    var mac = O.formatCode(hmacSha256Hex(SECRET, msg).toUpperCase().slice(0, 16));
    return expiry8 ? (mac + '-' + expiry8.slice(2)) : mac;
  };

  /** اعتبارسنجی: HMAC + انقضا (تاریخ محلی دستگاه، مثل datetime.now پایتون) */
  O.validateKey = function (key, deviceCode, nowMs) {
    var p = O.parseKeyInput(key);
    if (!p) return false;
    var exp = O.licenseKeyFor(deviceCode, p.expiry8);
    if (exp === '' || O.normalizeKey(exp) !== O.normalizeKey(key)) return false;
    if (p.expiry8 && ymd8(new Date(nowMs || Date.now())) > p.expiry8) return false;
    return true;
  };

  /** کلید کاربر را به قالب فشردهٔ ذخیره‌سازی نرمال کن (بدون خط‌تیره) */
  O.normalizeKey = function (key) {
    var p = O.parseKeyInput(key);
    if (!p) return '';
    return p.key + (p.expiry8 ? p.expiry8.slice(2) : '');
  };

  function rolledBack(lastSeenIso, nowMs) {
    if (!lastSeenIso) return false;
    var ls = Date.parse(lastSeenIso);
    if (!isFinite(ls)) return false;
    return (nowMs || Date.now()) < ls - ROLLBACK_MS;
  }
  O.rolledBack = rolledBack;

  // ── چرخهٔ ذخیره (SharedPreferences — کلید license.dat مثل دسکتاپ) ──
  O.licLoad = function (storage) {
    try {
      var raw = storage.get('license.dat');
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  };

  /** قفل‌ها: device_id == دستگاه فعلی · HMAC درست · انقضا نگذشته · ساعت دستکاری نشده */
  O.licIsActive = function (storage, deviceId, nowMs) {
    var now = nowMs || Date.now();
    var d = O.licLoad(storage);
    if (!d || !deviceId || d.device_id !== deviceId) return false;
    if (rolledBack(d.last_seen, now)) return false;
    if (!O.validateKey(d.license_key, O.deviceCodeFromId(deviceId), now)) return false;
    // last_seen را (با throttle) جلو ببر — مبنای تشخیص دستکاری ساعت
    try {
      if (!d.last_seen || now - Date.parse(d.last_seen) > TOUCH_MS) {
        d.last_seen = new Date(now).toISOString();
        storage.set('license.dat', JSON.stringify(d));
      }
    } catch (e) { }
    return true;
  };

  O.licActivate = function (storage, key, deviceId, userName, nowMs) {
    var now = nowMs || Date.now();
    if (!O.validateKey(key, O.deviceCodeFromId(deviceId), now)) return false;
    var p = O.parseKeyInput(key);
    try {
      storage.set('license.dat', JSON.stringify({
        license_key: O.normalizeKey(key),
        device_id: deviceId,
        user_name: userName || '',
        expires_at: p ? p.expiry8 : null,
        activated_at: new Date(now).toISOString(),
        last_seen: new Date(now).toISOString(),
        version: '2.1'
      }));
      return true;
    } catch (e) { return false; }
  };

  O.licDeactivate = function (storage) {
    try { storage.del('license.dat'); } catch (e) { }
  };

  // ── دورهٔ آزمایشی (trial.dat — مثل trial پایتون) ────────────────
  O.trialStatus = function (storage, nowMs) {
    var now = nowMs || Date.now();
    var t = null;
    try { var raw = storage.get('trial.dat'); t = raw ? JSON.parse(raw) : null; } catch (e) { t = null; }
    if (!t) return { exists: false, active: false, daysLeft: 0, tampered: false };
    if (rolledBack(t.last_seen, now)) return { exists: true, active: false, daysLeft: 0, tampered: true };
    var started = Date.parse(t.started_at);
    if (!isFinite(started)) return { exists: true, active: false, daysLeft: 0, tampered: true };
    var days = t.days || O.LICENSE_TRIAL_DAYS;
    var used = Math.max(0, (now - started) / 86400000);
    return { exists: true, active: used < days, daysLeft: Math.max(0, days - Math.floor(used)), tampered: false };
  };

  O.trialStart = function (storage, nowMs) {
    if (O.trialStatus(storage, nowMs).exists) return false;   // یک‌بار بیشتر نه (ضدتقلب)
    var now = new Date(nowMs || Date.now());
    try {
      storage.set('trial.dat', JSON.stringify({
        started_at: now.toISOString(), last_seen: now.toISOString(),
        days: O.LICENSE_TRIAL_DAYS
      }));
      return true;
    } catch (e) { return false; }
  };

  O.trialTouch = function (storage, nowMs) {
    var now = nowMs || Date.now();
    try {
      var raw = storage.get('trial.dat');
      if (!raw) return;
      var t = JSON.parse(raw);
      if (!t.last_seen || now - Date.parse(t.last_seen) > TOUCH_MS) {
        t.last_seen = new Date(now).toISOString();
        storage.set('trial.dat', JSON.stringify(t));
      }
    } catch (e) { }
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
