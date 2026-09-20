package com.odin.assistant;

import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.ContentValues;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
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
 * لرزش لمسی، روشن‌نگه‌داشتن صفحه و بازکردن لینک بیرونی.
 *
 * پاسخ HTTP به‌صورت Base64 به JS برمی‌گردد تا متن UTF-8 (فارسی/XML)
 * بدون خرابی کدگذاری منتقل شود.
 */
public class Bridge {

    private static final String UA =
            "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) "
                    + "Chrome/126.0.0.0 Mobile Safari/537.36 ODINAssistant/0.10.0";

    private static final String CH_ID = "signals";
    private static final int NOTIF_ID = 1001;

    private final Activity act;
    private final WebView web;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService pool = Executors.newFixedThreadPool(4);
    private final SharedPreferences prefs;

    public Bridge(Activity act, WebView web) {
        this.act = act;
        this.web = web;
        this.prefs = act.getSharedPreferences("odin", Activity.MODE_PRIVATE);
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
            return act.getPackageManager().getPackageInfo(act.getPackageName(), 0).versionName;
        } catch (Exception e) {
            return "0.10.0";
        }
    }

    @JavascriptInterface
    public void toast(final String msg) {
        ui.post(new Runnable() {
            @Override
            public void run() {
                Toast.makeText(act, msg, Toast.LENGTH_SHORT).show();
            }
        });
    }

    @JavascriptInterface
    public void openExternal(String url) {
        try {
            act.startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception ignored) {
        }
    }

    @JavascriptInterface
    public void exit() {
        ui.post(new Runnable() {
            @Override
            public void run() {
                act.finish();
            }
        });
    }

    @JavascriptInterface
    public void haptic() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            ui.post(new Runnable() {
                @Override
                public void run() {
                    act.getWindow().getDecorView()
                            .performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP);
                }
            });
        }
    }

    // ── اعلان اندروید (سیگنال جدید / خبر فوری) ────────────────────
    /** اگر اعلان‌ها خاموش باشند (تنظیمات سیستم یا مجوز رد شده) بی‌صدا رد می‌شود. */
    @JavascriptInterface
    public void notify(final String title, final String body) {
        ui.post(new Runnable() {
            @Override
            public void run() {
                try {
                    NotificationManager nm =
                            (NotificationManager) act.getSystemService(Activity.NOTIFICATION_SERVICE);
                    if (nm == null || !nm.areNotificationsEnabled()) return;

                    long[] vib = {0, 250, 150, 250};
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        NotificationChannel ch = new NotificationChannel(
                                CH_ID, "سیگنال‌ها و اخبار", NotificationManager.IMPORTANCE_HIGH);
                        ch.setDescription("اعلان سیگنال جدید و خبر فوری — دستیار اودین");
                        ch.enableVibration(true);
                        ch.setVibrationPattern(vib);
                        nm.createNotificationChannel(ch);
                    }

                    Intent tap = new Intent(act, MainActivity.class);
                    tap.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
                    int piFlags = PendingIntent.FLAG_UPDATE_CURRENT;
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                        piFlags |= PendingIntent.FLAG_IMMUTABLE;
                    }
                    PendingIntent pi = PendingIntent.getActivity(act, 0, tap, piFlags);

                    Notification.Builder b = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                            ? new Notification.Builder(act, CH_ID)
                            : new Notification.Builder(act);
                    b.setContentTitle(title)
                            .setContentText(body)
                            .setStyle(new Notification.BigTextStyle().bigText(body))
                            .setSmallIcon(R.drawable.ic_stat_odin)
                            .setContentIntent(pi)
                            .setAutoCancel(true);
                    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
                        b.setVibrate(vib);
                        b.setDefaults(Notification.DEFAULT_SOUND);
                    }
                    nm.notify(NOTIF_ID, b.build());
                } catch (Exception ignored) {
                }
            }
        });
    }

    // ── اشتراک‌گذاری متن (شیتر اندروید) ──────────────────────────
    @JavascriptInterface
    public void shareText(final String subject, final String text) {
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
                Uri uri = act.getContentResolver()
                        .insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
                if (uri == null) return "insert-failed";
                OutputStream os = act.getContentResolver().openOutputStream(uri);
                if (os == null) return "open-failed";
                os.write(content.getBytes("UTF-8"));
                os.close();
                cv.clear();
                cv.put(MediaStore.Downloads.IS_PENDING, 0);
                act.getContentResolver().update(uri, cv, null, null);
                return "ok";
            }
            // API 24-28: نوشتن مستقیم در Downloads عمومی (یک‌بار مجوز لازم است)
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
