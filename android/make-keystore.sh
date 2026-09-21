#!/usr/bin/env bash
# ساخت کلید امضای اپ (یک‌بار اجرا شود).
# خروجی: keystore/sushian-khoshkhani-release.jks + keystore.properties (هیچ‌کدام در گیت ثبت نمی‌شوند)
#
# ⚠️ این فایل را نگه دارید: به‌روزرسانی‌های آیندهٔ اپ باید با همین کلید امضا شوند،
#    وگرنه اندروید آن‌ها را به‌عنوان «اپ متفاوت» می‌شناسد (نیاز به حذف نصب قبلی).
#
# از نسخهٔ ۰.۱۲.۰ هویت رسمی پابلیشر/صاحب اثر «Sushian Khoshkhani» است.
# کلیدهای قدیمی فقط برای اعتبارسنجی نسخه‌های قبل نگه داشته می‌شوند:
#   - sushian-release.jks (نام Sushian) → نسخهٔ ۰.۱۱.۰
#   - odin-release.jks    (نام ODIN)     → نسخه‌های ۰.۹ و ۰.۱۰
set -e
cd "$(dirname "$0")"
mkdir -p keystore

if [ -f keystore/sushian-khoshkhani-release.jks ]; then
  echo "کلید از قبل ساخته شده — چیزی تغییر نکرد."
  exit 0
fi

PASS=$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n' | cut -c1-24)

keytool -genkeypair -v \
  -keystore keystore/sushian-khoshkhani-release.jks -storetype PKCS12 \
  -alias sushian-khoshkhani -keyalg RSA -keysize 2048 -validity 18250 \
  -storepass "$PASS" -keypass "$PASS" \
  -dname "CN=Sushian Khoshkhani, OU=ODIN Assistant, O=Sushian Khoshkhani, C=IR"

cat > keystore.properties <<EOF
storeFile=keystore/sushian-khoshkhani-release.jks
storePassword=$PASS
keyAlias=sushian-khoshkhani
keyPassword=$PASS
EOF

echo "✅ کلید ساخته شد:"
echo "   keystore/sushian-khoshkhani-release.jks"
echo "   keystore.properties (رمز: $PASS)"
echo "از هر دو نسخهٔ پشتیبان بگیرید — بدون آن‌ها امضای نسخهٔ بعدی ممکن نیست."
