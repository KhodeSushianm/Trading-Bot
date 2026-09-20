#!/usr/bin/env bash
# ساخت کلید امضای اپ (یک‌بار اجرا شود).
# خروجی: keystore/odin-release.jks + keystore.properties (هیچ‌کدام در گیت ثبت نمی‌شوند)
#
# ⚠️ این فایل را نگه دارید: به‌روزرسانی‌های آیندهٔ اپ باید با همین کلید امضا شوند،
#    وگرنه اندروید آن‌ها را به‌عنوان «اپ متفاوت» می‌شناسد (نیاز به حذف نصب قبلی).
set -e
cd "$(dirname "$0")"
mkdir -p keystore

if [ -f keystore/odin-release.jks ]; then
  echo "کلید از قبل ساخته شده — چیزی تغییر نکرد."
  exit 0
fi

PASS=$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n' | cut -c1-24)

keytool -genkeypair -v \
  -keystore keystore/odin-release.jks \
  -alias odin -keyalg RSA -keysize 2048 -validity 10950 \
  -storepass "$PASS" -keypass "$PASS" \
  -dname "CN=ODIN Assistant, OU=Personal, O=KhodeSushianm, C=IR"

cat > keystore.properties <<EOF
storeFile=keystore/odin-release.jks
storePassword=$PASS
keyAlias=odin
keyPassword=$PASS
EOF

echo "✅ کلید ساخته شد:"
echo "   keystore/odin-release.jks"
echo "   keystore.properties (رمز: $PASS)"
echo "از هر دو نسخهٔ پشتیبان بگیرید — بدون آن‌ها امضای نسخهٔ بعدی ممکن نیست."
