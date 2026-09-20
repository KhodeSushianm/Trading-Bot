package com.odin.assistant;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * پوستهٔ نیتیو اپ: یک WebView تمام‌صفحه که رابط فارسی/RTL
 * (assets/www) را اجرا می‌کند.
 *
 * چرا WebView؟ چون کل منطق تحلیل (داور امتیازدهی، تقویم، اخبار، ژورنال)
 * یک‌بار با JS نوشته شده و ظاهر اپ دقیقاً همان تم شیشه‌ای نسخهٔ دسکتاپ است؛
 * پل نیتیو (Bridge) فقط HTTP و ذخیره‌سازی محلی را فراهم می‌کند تا مشکل
 * CORS مرورگر هم وجود نداشته باشد.
 */
public class MainActivity extends Activity {

    private WebView web;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // نوار وضعیت روشن با آیکون‌های تیره (مطابق تم روشن اپ)
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
        getWindow().setStatusBarColor(Color.parseColor("#E7E7EC"));
        int flags = View.SYSTEM_UI_FLAG_LAYOUT_STABLE;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            flags |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            flags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            getWindow().setNavigationBarColor(Color.parseColor("#F3F3F6"));
        }
        getWindow().getDecorView().setSystemUiVisibility(flags);

        web = new WebView(this);
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setTextZoom(100);                 // زوم فونت سیستم، چیدمان را به هم نریزد
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setMediaPlaybackRequiresUserGesture(false);

        web.setBackgroundColor(Color.parseColor("#E7E7EC"));
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
        web.setVerticalScrollBarEnabled(false);
        web.setHapticFeedbackEnabled(false);

        web.addJavascriptInterface(new Bridge(this, web), "ODINNative");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                // لینک خبرها در مرورگر خود گوشی باز شود، نه داخل اپ
                if (url != null && url.startsWith("http")) {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                    } catch (Exception ignored) {
                    }
                    return true;
                }
                return false;
            }
        });

        web.loadUrl("file:///android_asset/www/index.html");

        // مجوز اعلان در اندروید ۱۳+ — اگر رد شود، اعلان‌ها بی‌صدا غیرفعال
        // می‌مانند و اپ مثل قبل با Toast کار می‌کند.
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
                != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, 1001);
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (web != null) {
            // تایمرهای JS در پس‌زمینه متوقف شوند — تازه‌سازی خودکار و ساعت
            // فقط وقتی اپ باز است کار می‌کنند (بدون مصرف باتری/اینترنت پنهان)
            web.onPause();
            web.pauseTimers();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web != null) {
            web.onResume();
            web.resumeTimers();
        }
    }

    @Override
    public void onBackPressed() {
        // ناوبری برگشت داخل اپ (تب قبلی)؛ اگر جای دیگری نباشد، اپ بسته می‌شود
        web.evaluateJavascript("(window.ODIN && ODIN.back) ? ODIN.back() : null", null);
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
        }
        super.onDestroy();
    }
}
