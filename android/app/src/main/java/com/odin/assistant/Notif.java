package com.odin.assistant;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.graphics.drawable.Icon;
import android.os.Build;

/**
 * کانال‌ها و سازندهٔ اعلان‌ها — مشترک بین Bridge (سیگنال/خبر فوری) و
 * OdinService (اعلان ماندگار رصد پس‌زمینه).
 *
 * دو کانال:
 *   signals — اهمیت بالا + لرزش (سیگنال تازه، خبر فوری)
 *   monitor — اهمیت کم، بی‌صدا (اعلان ماندگار «در حال رصد» + دکمهٔ توقف)
 */
public final class Notif {

    public static final String CH_SIGNALS = "signals";
    public static final String CH_MONITOR = "monitor";
    public static final int SIGNALS_ID = 1001;
    public static final int MONITOR_ID = 1002;

    private static final long[] VIB = {0, 250, 150, 250};

    private Notif() {
    }

    public static void ensureChannels(Context ctx) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;
        try {
            NotificationChannel sig = new NotificationChannel(
                    CH_SIGNALS, "سیگنال‌ها و اخبار", NotificationManager.IMPORTANCE_HIGH);
            sig.setDescription("اعلان سیگنال جدید و خبر فوری — ODIN ASSISTANT");
            sig.enableVibration(true);
            sig.setVibrationPattern(VIB);
            nm.createNotificationChannel(sig);

            NotificationChannel mon = new NotificationChannel(
                    CH_MONITOR, "رصد پس‌زمینه", NotificationManager.IMPORTANCE_LOW);
            mon.setDescription("اعلان ماندگار «در حال رصد بازار» — نشانهٔ فعال بودن رصد پس‌زمینه");
            mon.enableVibration(false);
            mon.setShowBadge(false);
            nm.createNotificationChannel(mon);
        } catch (Exception ignored) {
        }
    }

    public static boolean enabled(Context ctx) {
        try {
            NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
            return nm != null && nm.areNotificationsEnabled();
        } catch (Exception e) {
            return false;
        }
    }

    private static int piFlags() {
        int f = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) f |= PendingIntent.FLAG_IMMUTABLE;
        return f;
    }

    private static PendingIntent openApp(Context ctx) {
        Intent tap = new Intent(ctx, MainActivity.class);
        tap.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        return PendingIntent.getActivity(ctx, 0, tap, piFlags());
    }

    private static PendingIntent stopMonitor(Context ctx) {
        Intent stop = new Intent(ctx, OdinService.class);
        stop.setAction(OdinService.ACTION_STOP);
        return PendingIntent.getService(ctx, 1, stop, piFlags());
    }

    /** اعلان سیگنال/خبر فوری — اهمیت بالا + لرزش. اگر اعلان‌ها خاموش باشند بی‌صدا رد می‌شود. */
    public static void signal(Context ctx, String title, String body) {
        try {
            NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null || !nm.areNotificationsEnabled()) return;
            Notif.ensureChannels(ctx);

            Notification.Builder b = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                    ? new Notification.Builder(ctx, CH_SIGNALS)
                    : new Notification.Builder(ctx);
            b.setContentTitle(title)
                    .setContentText(body)
                    .setStyle(new Notification.BigTextStyle().bigText(body))
                    .setSmallIcon(R.drawable.ic_stat_odin)
                    .setContentIntent(openApp(ctx))
                    .setAutoCancel(true);
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
                b.setVibrate(VIB);
                b.setDefaults(Notification.DEFAULT_SOUND);
            }
            nm.notify(SIGNALS_ID, b.build());
        } catch (Exception ignored) {
        }
    }

    /** اعلان ماندگار رصد پس‌زمینه — اهمیت کم + دکمهٔ «توقف رصد». */
    public static Notification monitor(Context ctx, String title, String body) {
        Notif.ensureChannels(ctx);
        Notification.Builder b = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(ctx, CH_MONITOR)
                : new Notification.Builder(ctx);
        b.setContentTitle(title)
                .setContentText(body)
                .setStyle(new Notification.BigTextStyle().bigText(body))
                .setSmallIcon(R.drawable.ic_stat_odin)
                .setContentIntent(openApp(ctx))
                .setOngoing(true)
                .setShowWhen(false);
        Notification.Action stopAction = new Notification.Action.Builder(
                Icon.createWithResource(ctx, R.drawable.ic_stat_odin),
                "توقف رصد", stopMonitor(ctx)).build();
        b.addAction(stopAction);
        return b.build();
    }

    public static void postMonitor(Context ctx, String title, String body) {
        try {
            NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null) return;
            nm.notify(MONITOR_ID, monitor(ctx, title, body == null ? "" : body));
        } catch (Exception ignored) {
        }
    }
}
