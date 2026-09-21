package com.odin.assistant;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;

import org.json.JSONObject;

/**
 * بعد از راه‌اندازی مجدد گوشی: اگر کاربر «رصد پس‌زمینه» را فعال کرده باشد،
 * سرویس برگردانده می‌شود تا صدور سیگنال بدون باز کردن اپ ادامه یابد.
 *
 * معیار، پرچم‌های ذخیره‌شدهٔ خود اپ است (onboarded.bg + settings.background_enabled)؛
 * اگر کاربر هرگز خوش‌آمدگویی را ندیده باشد، هیچ سرویسی شروع نمی‌شود.
 * شروع FGS از BOOT_COMPLETED برای نوع specialUse مجاز است؛ با این حال هر
 * خطا (محدودیت سازنده/OEM) بی‌صدا رد می‌شود — در اولین باز شدن اپ،
 * سرویس دوباره توسط خود رابط شروع می‌شود.
 */
public class BootReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) return;
        try {
            SharedPreferences prefs = context.getSharedPreferences("odin", Context.MODE_PRIVATE);
            if (!"1".equals(prefs.getString("onboarded.bg", ""))) return;

            boolean enabled = true;
            String raw = prefs.getString("settings", "");
            if (raw != null && !raw.isEmpty()) {
                JSONObject j = new JSONObject(raw);
                enabled = j.optBoolean("background_enabled", true);
            }
            if (!enabled) return;

            Intent svc = new Intent(context, OdinService.class);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(svc);
            } else {
                context.startService(svc);
            }
        } catch (Exception ignored) {
            // رصد تا باز شدن بعدی اپ به تعویق می‌افتد — بی‌صدا، مثل بقیهٔ اپ
        }
    }
}
