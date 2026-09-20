package com.odin.assistant;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Base64;
import android.view.HapticFeedbackConstants;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * پل نیتیو ↔ وب: درخواست HTTP (بدون محدودیت CORS)، حافظهٔ محلی
 * (ژورنال و تنظیمات)، لرزش لمسی و بازکردن لینک بیرونی.
 *
 * پاسخ HTTP به‌صورت Base64 به JS برمی‌گردد تا متن UTF-8 (فارسی/XML)
 * بدون خرابی کدگذاری منتقل شود.
 */
public class Bridge {

    private static final String UA =
            "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) "
                    + "Chrome/126.0.0.0 Mobile Safari/537.36 ODINAssistant/0.9.0";

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
            return "0.9.0";
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
}
