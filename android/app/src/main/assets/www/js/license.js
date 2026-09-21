/* لایسنس و قفل دستگاه — همزاد دقیقِ src/license.py برای اندروید (v0.14.0)
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

  /** تولید کلید برای یک کد دستگاه — «XXXX-XXXX-XXXX-XXXX» یا '' اگر کد نامعتبر */
  O.licenseKeyFor = function (deviceCode) {
    var code = O.normalizeCode(deviceCode);
    if (code.length !== 12) return '';
    return O.formatCode(hmacSha256Hex(SECRET, code).toUpperCase().slice(0, 16));
  };

  O.validateKey = function (key, deviceCode) {
    var k = O.normalizeCode(key);
    if (k.length !== 16) return false;
    var exp = O.licenseKeyFor(deviceCode);
    return exp !== '' && O.normalizeCode(exp) === k;
  };

  // ── چرخهٔ ذخیره (SharedPreferences — کلید license.dat مثل دسکتاپ) ──
  O.licLoad = function (storage) {
    try {
      var raw = storage.get('license.dat');
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  };

  /** قفل دو لایه: device_id ذخیره‌شده == دستگاه فعلی، و کلید HMAC درست */
  O.licIsActive = function (storage, deviceId) {
    var d = O.licLoad(storage);
    if (!d || !deviceId || d.device_id !== deviceId) return false;
    return O.validateKey(d.license_key, O.deviceCodeFromId(deviceId));
  };

  O.licActivate = function (storage, key, deviceId, userName) {
    if (!O.validateKey(key, O.deviceCodeFromId(deviceId))) return false;
    try {
      storage.set('license.dat', JSON.stringify({
        license_key: O.normalizeCode(key),
        device_id: deviceId,
        user_name: userName || '',
        activated_at: new Date().toISOString(),
        version: '2.0'
      }));
      return true;
    } catch (e) { return false; }
  };

  O.licDeactivate = function (storage) {
    try { storage.del('license.dat'); } catch (e) { }
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
