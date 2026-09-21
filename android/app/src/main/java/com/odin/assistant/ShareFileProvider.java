package com.odin.assistant;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;

import java.io.File;
import java.io.FileNotFoundException;

/**
 * پرووایدر اشتراک فایل (v0.18.0) — بدون AndroidX.
 *
 * برای اشتراک تصویر کارت سیگنال با اپ‌های دیگر (تلگرام/واتساپ/...) روی همهٔ
 * APIها (۲۴ تا ۳۴+) به content:// URI نیاز داریم؛ FileProvider در androidx است
 * و این اپ عمداً هیچ وابستگی AndroidX ندارد، پس این پرووایدر مینیمال فقط
 * فایل‌های زیر cacheDir/share را (فقط خواندنی) بیرون می‌دهد.
 *
 * امنیت: مسیر با canonical path بررسی می‌شود (path traversal ممنوع)،
 * exported=false + grantUriPermissions=true یعنی فقط گیرندهٔexplicit
 * share intent، و فقط برای همان URI، دسترسی خواندن می‌گیرد.
 */
public class ShareFileProvider extends ContentProvider {

    public static final String AUTHORITY = "com.odin.assistant.share";

    private File baseDir() {
        return new File(getContext().getCacheDir(), "share");
    }

    public static Uri uriFor(String fileName) {
        return Uri.parse("content://" + AUTHORITY + "/" + fileName);
    }

    @Override
    public boolean onCreate() {
        return true;
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        String seg = uri.getLastPathSegment();
        if (seg == null) throw new FileNotFoundException("no segment");
        File base = baseDir();
        File f = new File(base, seg);
        try {
            if (!f.getCanonicalPath().startsWith(base.getCanonicalPath() + File.separator)
                    || !f.exists() || !f.isFile()) {
                throw new FileNotFoundException("invalid path");
            }
        } catch (java.io.IOException e) {
            throw new FileNotFoundException("io error");
        }
        return ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override
    public String getType(Uri uri) {
        return "image/png";
    }

    // بقیهٔ عملیات پشتیبانی نمی‌شود — این پرووایدر فقط خواندنی است
    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) {
        return null;
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }
}
