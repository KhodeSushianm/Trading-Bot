package com.odin.assistant;

import android.annotation.SuppressLint;
import android.app.Service;
import android.content.Intent;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * رصد پس‌زمینه (v0.13.0) — سیگنال بدون باز کردن اپ.
 *
 * یک WebView بی‌سر، همان موتور تحلیل بسته‌بندی‌شده در assets/www را در
 * «حالت سرویس» (index.html?svc=1) اجرا می‌کند. زمان‌بندی چرخه‌ها عمداً
 * نیتیو (Handler) است نه تایمر JS: تایمرهای WebView در پس‌زمینه
 * متوقف/محدود می‌شوند (pauseTimers سراسری و throttling کرومیوم)، اما
 * Handler روی Looper اصلی قابل اتکا است.
 *
 * جریان هر چرخه:
 *   نیتیو tick → JS ODIN.svcTick() → cycleCore (داده ← داور ← ژورنال ←
 *   اعلان سیگنال/خبر فوری) → JS bgCycleDone(nextMin) → زمان‌بندی tick بعدی.
 *
 * سرویس foreground از نوع specialUse است: یک اعلان ماندگار کم‌اهمیت
 * «در حال رصد بازار» همیشه نمایان است — هم الزام اندروید، هم شفافیت برای
 * کاربر (اصل صداقت پروژه). ذخیره‌سازی/ضداسپام/ژورنال دقیقاً همان
 * SharedPreferences مشترک با رابط است، پس نتیجهٔ چرخه‌های پس‌زمینه فوراً
 * در اپ دیده می‌شود و سیگنال تکراری دوباره اعلان نمی‌شود.
 */
public class OdinService extends Service {

    public static final String ACTION_STOP = "com.odin.assistant.STOP_MONITOR";

    /** آیا رصد در جریان است؟ (برای Bridge.bgRunning و نمایش وضعیت در UI) */
    public static volatile boolean RUNNING = false;
    /** نمونهٔ فعال — یک پروسه، یک سرویس — برای فراخوان‌های Bridge. */
    static volatile OdinService INSTANCE;

    private final Handler main = new Handler(Looper.getMainLooper());
    private WebView web;
    private volatile boolean pageReady = false;
    private long intervalMs = 15 * 60000L;

    private final Runnable tick = new Runnable() {
        @Override
        public void run() {
            if (web != null && pageReady) {
                web.evaluateJavascript("ODIN.svcTick && ODIN.svcTick()", null);
            } else if (web != null) {
                main.postDelayed(this, 5000);   // صفحه هنوز بارگذاری نشده — تلاش دوباره
            }
        }
    };

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    public void onCreate() {
        super.onCreate();
        INSTANCE = this;
        RUNNING = true;
        Notif.ensureChannels(this);
        startForeground(Notif.MONITOR_ID,
                Notif.monitor(this, "رصد بازار — دستیار اودین", "در حال آماده‌سازی موتور تحلیل..."));

        web = new WebView(getApplicationContext());
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(false);      // همهٔ ذخیره‌سازی از Bridge/SharedPreferences
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setTextZoom(100);
        web.setBackgroundColor(0x00000000);
        web.addJavascriptInterface(new Bridge(getApplicationContext(), null, web), "ODINNative");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                pageReady = true;
                // اولین چرخه بلافاصله؛ tick نیتیو فقط به‌عنوان نگهبان (اگر JS
                // به هر دلیل bgCycleDone را صدا نزد، چرخه‌ها از سر گرفته شوند)
                view.evaluateJavascript("ODIN.svcStart && ODIN.svcStart()", null);
                main.postDelayed(tick, intervalMs);
            }
        });
        web.loadUrl("file:///android_asset/www/index.html?svc=1");
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopSelf();
            return START_NOT_STICKY;
        }
        // اجرای مجدد (از Activity یا BOOT): سرویس زنده است، چیزی ساخته نمی‌شود
        return START_STICKY;
    }

    /** JS بعد از پایان هر چرخه صدا می‌زند: tick بعدی زمان‌بندی شود. */
    void onCycleDone(int nextMinutes) {
        int m = Math.max(1, Math.min(240, nextMinutes));
        intervalMs = m * 60000L;
        main.removeCallbacks(tick);
        main.postDelayed(tick, intervalMs);
    }

    @Override
    public void onDestroy() {
        RUNNING = false;
        INSTANCE = null;
        main.removeCallbacks(tick);
        if (web != null) {
            try {
                web.stopLoading();
                web.loadUrl("about:blank");
                web.destroy();
            } catch (Exception ignored) {
            }
            web = null;
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
