package com.odin.assistant;

import android.app.Activity;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.provider.MediaStore;
import android.provider.Settings;
import android.util.Base64;
import android.view.HapticFeedbackConstants;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * پل نیتیو ↔ وب: درخواست HTTP (بدون محدودیت CORS)، حافظهٔ محلی
 * (ژورنال و تنظیمات)، اعلان اندروید، اشتراک‌گذاری، ذخیره در دانلودها،
 * لرزش لمسی، روشن‌نگه‌داشتن صفحه، بازکردن لینک بیرونی و — از v0.13.0 —
 * کنترل سرویس «رصد پس‌زمینه» (OdinService) و مجوزهای پایداری آن.
 *
 * دو حالت ساخت (v0.13.0):
 *   • از MainActivity:  Bridge(activity, activity, web) — همهٔ قابلیت‌ها
 *   • از OdinService:   Bridge(appCtx, null, web) — حالت بی‌سر؛ HTTP،
 *     حافظه، اعلان‌ها و زمان‌بندی چرخه کار می‌کنند و قابلیت‌های وابسته به
 *     رابط (لرزش، اشتراک، صفحهٔ روشن، خروج) بی‌صدا رد می‌شوند.
 *
 * پاسخ HTTP به‌صورت Base64 به JS برمی‌گردد تا متن UTF-8 (فارسی/XML)
 * بدون خرابی کدگذاری منتقل شود.
 */
public class Bridge {

    private static final String UA =
            "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) "
                    + "Chrome/126.0.0.0 Mobile Safari/537.36 ODINAssistant/0.14.2";

    private final Context ctx;          // همیشه غیرnull (application context ترجیحاً)
    private final Activity act;         // در حالت سرویس null است
    private final WebView web;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService pool = Executors.newFixedThreadPool(4);
    private final SharedPreferences prefs;

    public Bridge(Context context, Activity activity, WebView webView) {
        Context app = context.getApplicationContext();
        this.ctx = app != null ? app : context;
        this.act = activity;
        this.web = webView;
        this.prefs = this.ctx.getSharedPreferences("odin", Context.MODE_PRIVATE);
    }

    /** درخواست HTTP روی thread پس‌زمینه؛ نتیجه با ODIN.httpDone به JS برمی‌گردد. */
    @JavascriptInterface
    public void http(final int cbId, final String url, final String method,
                     final String body, final String contentType) {
        pool.execute(new Runnable() {
            @Override
            public void run() {
                int status = -1;
                String payloadB64 = "";
                HttpURLConnection c = null;
                try {
                    c = (HttpURLConnection) new URL(url).openConnection();
                    String m = (method == null || method.isEmpty()) ? "GET" : method.toUpperCase();
                    c.setRequestMethod(m);
                    c.setConnectTimeout(20000);
                    c.setReadTimeout(25000);
                    c.setInstanceFollowRedirects(true);
                    c.setRequestProperty("User-Agent", UA);
                    c.setRequestProperty("Accept", "*/*");
                    c.setRequestProperty("Accept-Language", "en-US,en;q=0.9");
                    if (body != null && !body.isEmpty()) {
                        c.setDoOutput(true);
                        c.setRequestProperty("Content-Type",
                                contentType == null ? "application/json" : contentType);
                        OutputStream os = c.getOutputStream();
                        os.write(body.getBytes("UTF-8"));
                        os.close();
                    }
                    status = c.getResponseCode();
                    InputStream in;
                    try {
                        in = (status >= 200 && status < 400) ? c.getInputStream() : c.getErrorStream();
                    } catch (Exception e) {
                        in = null;
                    }
                    ByteArrayOutputStream bos = new ByteArrayOutputStream();
                    if (in != null) {
                        byte[] buf = new byte[16384];
                        int n;
                        while ((n = in.read(buf)) > 0) bos.write(buf, 0, n);
                        in.close();
                    }
                    payloadB64 = Base64.encodeToString(bos.toByteArray(), Base64.NO_WRAP);
                } catch (Exception e) {
                    String msg = e.getClass().getSimpleName() + ": "
                            + (e.getMessage() == null ? "" : e.getMessage());
                    payloadB64 = Base64.encodeToString(msg.getBytes(), Base64.NO_WRAP);
                } finally {
                    if (c != null) c.disconnect();
                }
                final int fs = status;
                final String fp = payloadB64;
                ui.post(new Runnable() {
                    @Override
                    public void run() {
                        web.evaluateJavascript(
                                "ODIN.httpDone(" + cbId + "," + fs + ","
                                        + JSONObject.quote(fp) + ")", null);
                    }
                });
            }
        });
    }

    // ── حافظهٔ محلی (ژورنال append-only، تنظیمات، کش) ──────────────
    // SharedPreferences مشترک بین WebView رابط و WebView سرویس — ژورنال،
    // ضداسپم (sent_signals) و state.last در هر دو حالت یکی می‌ماند.
    @JavascriptInterface
    public String getPref(String key) {
        return prefs.getString(key, "");
    }

    @JavascriptInterface
    public void setPref(String key, String val) {
        prefs.edit().putString(key, val == null ? "" : val).apply();
    }

    @JavascriptInterface
    public void removePref(String key) {
        prefs.edit().remove(key).apply();
    }

    // ── متفرقه ─────────────────────────────────────────────────────
    @JavascriptInterface
    public String getVersion() {
        try {
            return ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0).versionName;
        } catch (Exception e) {
            return "0.14.2";
        }
    }

    @JavascriptInterface
    public void toast(final String msg) {
        ui.post(new Runnable() {
            @Override
            public void run() {
                try {
                    Toast.makeText(ctx, msg, Toast.LENGTH_SHORT).show();
                } catch (Exception ignored) {
                }
            }
        });
    }

    @JavascriptInterface
    public void openExternal(String url) {
        try {
            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(i);
        } catch (Exception ignored) {
        }
    }

    @JavascriptInterface
    public void exit() {
        if (act == null) return;
        ui.post(new Runnable() {
            @Override
            public void run() {
                act.finish();
            }
        });
    }

    @JavascriptInterface
    public void haptic() {
        if (act == null) return;
        ui.post(new Runnable() {
            @Override
            public void run() {
                act.getWindow().getDecorView()
                        .performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP);
            }
        });
    }

    // ── اعلان اندروید (سیگنال جدید / خبر فوری) ────────────────────
    /** اگر اعلان‌ها خاموش باشند (تنظیمات سیستم یا مجوز رد شده) بی‌صدا رد می‌شود. */
    @JavascriptInterface
    public void notify(final String title, final String body) {
        ui.post(new Runnable() {
            @Override
            public void run() {
                Notif.signal(ctx, title, body);
            }
        });
    }

    @JavascriptInterface
    public boolean notificationsEnabled() {
        return Notif.enabled(ctx);
    }

    /** صفحهٔ تنظیمات اعلان‌های اپ (برای راهنمایی کاربر وقتی مجوز رد شده). */
    @JavascriptInterface
    public void openNotificationSettings() {
        try {
            Intent i;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                i = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                        .putExtra(Settings.EXTRA_APP_PACKAGE, ctx.getPackageName());
            } else {
                i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                        .setData(Uri.parse("package:" + ctx.getPackageName()));
            }
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(i);
        } catch (Exception ignored) {
        }
    }

    // ── شناسهٔ دستگاه برای لایسنس (v0.14.0) ──────────────────────
    /**
     * شناسهٔ یکتای دستگاه = SHA-256("android:" + ANDROID_ID) — همان طرح
     * src/license.py دسکتاپ (هم‌نوع، ولی دامنهٔ مقدارها جداست). ANDROID_ID در
     * اندروید ۸+ به کلید امضای اپ گره خورده و بین نصب‌ها (با همان امضا)
     * پایدار است. اگر در دسترس نبود، UUID تصادفی در prefs ماندگار می‌شود.
     */
    @JavascriptInterface
    public String getDeviceId() {
        try {
            String aid = Settings.Secure.getString(
                    ctx.getContentResolver(), Settings.Secure.ANDROID_ID);
            if (aid == null || aid.trim().isEmpty()) {
                aid = prefs.getString("device.fallback", "");
                if (aid.isEmpty()) {
                    aid = "fallback-" + java.util.UUID.randomUUID();
                    prefs.edit().putString("device.fallback", aid).apply();
                }
            }
            java.security.MessageDigest md = java.security.MessageDigest.getInstance("SHA-256");
            byte[] d = md.digest(("android:" + aid).getBytes("UTF-8"));
            StringBuilder sb = new StringBuilder(64);
            for (byte b : d) sb.append(String.format("%02x", b));
            return sb.toString();
        } catch (Exception e) {
            return "";
        }
    }

    // ── رصد پس‌زمینه (v0.13.0) — OdinService ──────────────────────
    /** شروع/زنده‌نگه‌داشتن سرویس رصد. فقط وقتی اپ در پیش‌زمینه است صدا شود. */
    @JavascriptInterface
    public void startBackground() {
        try {
            Notif.ensureChannels(ctx);
            Intent i = new Intent(ctx, OdinService.class);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                ctx.startForegroundService(i);
            } else {
                ctx.startService(i);
            }
        } catch (Exception ignored) {
            // اگر OEM اجازه نداد، اپ مثل قبل با تازه‌سازی در پیش‌زمینه کار می‌کند
        }
    }

    @JavascriptInterface
    public void stopBackground() {
        try {
            ctx.stopService(new Intent(ctx, OdinService.class));
        } catch (Exception ignored) {
        }
    }

    @JavascriptInterface
    public boolean bgRunning() {
        return OdinService.RUNNING;
    }

    /** JS (حالت سرویس) بعد از هر چرخه: زمان‌بندی tick بعدی به دست نیتیو. */
    @JavascriptInterface
    public void bgCycleDone(final int nextMinutes) {
        ui.post(new Runnable() {
            @Override
            public void run() {
                OdinService s = OdinService.INSTANCE;
                if (s != null) s.onCycleDone(nextMinutes);
            }
        });
    }

    /** به‌روزرسانی اعلان ماندگار «در حال رصد» (خلاصهٔ آخرین چرخه). */
    @JavascriptInterface
    public void notifyOngoing(final String title, final String body) {
        ui.post(new Runnable() {
            @Override
            public void run() {
                Notif.postMonitor(ctx, title, body);
            }
        });
    }

    // ── پایداری رصد: بهینه‌سازی باتری ────────────────────────────
    @JavascriptInterface
    public boolean isIgnoringBattery() {
        try {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return true;
            PowerManager pm = (PowerManager) ctx.getSystemService(Context.POWER_SERVICE);
            return pm == null || pm.isIgnoringBatteryOptimizations(ctx.getPackageName());
        } catch (Exception e) {
            return true;
        }
    }

    /**
     * دیالوگ سیستمی «نادیده‌گرفتن بهینه‌سازی باتری» — بدون آن، Doze ممکن است
     * چرخه‌های پس‌زمینه را ساعت‌ها عقب بیندازد. اگر قبلاً داده شده، بی‌صدا رد می‌شود.
     */
    @JavascriptInterface
    public void requestIgnoreBattery() {
        try {
            if (isIgnoringBattery()) return;
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return;
            Intent i = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
                    .setData(Uri.parse("package:" + ctx.getPackageName()));
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(i);
        } catch (Exception ignored) {
        }
    }

    // ── اشتراک‌گذاری متن (شیتر اندروید) ──────────────────────────
    @JavascriptInterface
    public void shareText(final String subject, final String text) {
        if (act == null) return;
        ui.post(new Runnable() {
            @Override
            public void run() {
                try {
                    Intent i = new Intent(Intent.ACTION_SEND);
                    i.setType("text/plain");
                    i.putExtra(Intent.EXTRA_SUBJECT, subject);
                    i.putExtra(Intent.EXTRA_TEXT, text);
                    act.startActivity(Intent.createChooser(i, "اشتراک‌گذاری بریفینگ"));
                } catch (Exception ignored) {
                }
            }
        });
    }

    // ── ذخیرهٔ فایل در پوشهٔ دانلودها ────────────────────────────
    /** «ok» یا «permission» یا شرح خطا برمی‌گرداند (JS ترجمه می‌کند). */
    @JavascriptInterface
    public String saveDownload(String name, String content) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                // API 29+: MediaStore — بدون هیچ مجوزی
                ContentValues cv = new ContentValues();
                cv.put(MediaStore.Downloads.DISPLAY_NAME, name);
                cv.put(MediaStore.Downloads.MIME_TYPE, "application/json");
                cv.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
                cv.put(MediaStore.Downloads.IS_PENDING, 1);
                Uri uri = ctx.getContentResolver()
                        .insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
                if (uri == null) return "insert-failed";
                OutputStream os = ctx.getContentResolver().openOutputStream(uri);
                if (os == null) return "open-failed";
                os.write(content.getBytes("UTF-8"));
                os.close();
                cv.clear();
                cv.put(MediaStore.Downloads.IS_PENDING, 0);
                ctx.getContentResolver().update(uri, cv, null, null);
                return "ok";
            }
            // API 24-28: نوشتن مستقیم در Downloads عمومی (یک‌بار مجوز لازم است)
            if (act == null) return "permission";
            if (act.checkSelfPermission(android.Manifest.permission.WRITE_EXTERNAL_STORAGE)
                    != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                act.requestPermissions(new String[]{
                        android.Manifest.permission.WRITE_EXTERNAL_STORAGE}, 1002);
                return "permission";
            }
            File dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
            if (!dir.exists() && !dir.mkdirs()) return "mkdir-failed";
            FileOutputStream fos = new FileOutputStream(new File(dir, name));
            fos.write(content.getBytes("UTF-8"));
            fos.close();
            return "ok";
        } catch (Exception e) {
            return e.getClass().getSimpleName() + ": "
                    + (e.getMessage() == null ? "" : e.getMessage());
        }
    }

    // ── روشن‌نگه‌داشتن صفحه (فقط هنگام تحلیل) ────────────────────
    @JavascriptInterface
    public void keepScreenOn(final boolean on) {
        if (act == null) return;
        ui.post(new Runnable() {
            @Override
            public void run() {
                if (on) {
                    act.getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                } else {
                    act.getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                }
            }
        });
    }
}
