MODDIR=${0%/*}

sed 's/<\/familyset>//g' /system/etc/fonts.xml | cat - $MODDIR/fallback.xml > $MODDIR/system/etc/fonts.xml

if getprop ro.product.manufacturer |
        grep -qE -e "^samsung"; then
		cp $MODDIR/system/fonts/NotoColorEmoji.ttf $MODDIR/system/fonts/SamsungColorEmoji.ttf
		sed 's/<\/familyset>//g' /system/etc/fonts_additional.xml | cat - $MODDIR/fallback.xml > $MODDIR/system/etc/fonts_additional.xml
fi

if getprop ro.product.manufacturer |
        grep -qE -e "^LGE"; then
		cp $MODDIR/system/fonts/NotoColorEmoji.ttf $MODDIR/system/fonts/LGNotoColorEmoji.ttf
fi

if getprop ro.product.manufacturer |
        grep -qE -e "^HTC"; then
		cp $MODDIR/system/fonts/NotoColorEmoji.ttf $MODDIR/system/fonts/HTC_ColorEmoji.ttf
fi


# Set paths relative to the module's directory
MODDIR="${0%/*}"
FONT_FILE="$MODDIR/system/fonts/NotoColorEmoji.ttf"
SYSTEM_FONT_FILE="/system/fonts/NotoColorEmoji.ttf"
FACEBOOK_FONT_FILE="$MODDIR/system/fonts/FacebookEmoji.ttf"

# Mount overlay to replace system emoji font
mount -o bind "$FONT_FILE" "$SYSTEM_FONT_FILE"

# Ensure correct permissions for the replacement file
chmod 644 "$SYSTEM_FONT_FILE"

# Mount FacebookEmoji.ttf to specified directories
mount -o bind "$FACEBOOK_FONT_FILE" "/data/data/com.facebook.orca/app_ras_blobs/FacebookEmoji.ttf"
mount -o bind "$FACEBOOK_FONT_FILE" "/data/data/com.facebook.katana/app_ras_blobs/FacebookEmoji.ttf"

# Ensure correct permissions for the mounted files
chmod 644 "/data/data/com.facebook.orca/app_ras_blobs/FacebookEmoji.ttf"
chmod 644 "/data/data/com.facebook.katana/app_ras_blobs/FacebookEmoji.ttf"