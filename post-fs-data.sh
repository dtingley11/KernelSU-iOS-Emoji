MODDIR=${0%/*}

if getprop ro.product.manufacturer | grep -qE -e "^samsung"; then
    SAMSUNG_FONT_FILE="$MODDIR/system/fonts/SamsungColorEmoji.ttf"
    mount -o bind "$FONT_FILE" "$SAMSUNG_FONT_FILE"
    chmod 644 "$SAMSUNG_FONT_FILE"

    SYSTEM_ADDITIONAL_XML="/system/etc/fonts_additional.xml"
    sed 's/<\/familyset>//g' "$SYSTEM_ADDITIONAL_XML" | cat - "$FALLBACK_XML" > "$MODDIR/system/etc/fonts_additional.xml"
    mount -o bind "$MODDIR/system/etc/fonts_additional.xml" "$SYSTEM_ADDITIONAL_XML"
fi


if getprop ro.product.manufacturer | grep -qE -e "^LGE"; then
    LGE_FONT_FILE="$MODDIR/system/fonts/LGNotoColorEmoji.ttf"
    mount -o bind "$FONT_FILE" "$LGE_FONT_FILE"
    chmod 644 "$LGE_FONT_FILE"
fi

if getprop ro.product.manufacturer | grep -qE -e "^HTC"; then
    HTC_FONT_FILE="$MODDIR/system/fonts/HTC_ColorEmoji.ttf"
    mount -o bind "$FONT_FILE" "$HTC_FONT_FILE"
    chmod 644 "$HTC_FONT_FILE"
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

# Function to check if a package is installed
package_installed() {
    local package="$1"
    if pm list packages | grep -q "$package"; then
        return 0
    else
        return 1
    fi
}

# Mount FacebookEmoji.ttf to specified directories if Messenger or Facebook are installed
if package_installed "com.facebook.orca"; then
    mount -o bind "$FACEBOOK_FONT_FILE" "/data/data/com.facebook.orca/app_ras_blobs/FacebookEmoji.ttf"
    chmod 644 "/data/data/com.facebook.orca/app_ras_blobs/FacebookEmoji.ttf"
fi

if package_installed "com.facebook.katana"; then
    mount -o bind "$FACEBOOK_FONT_FILE" "/data/data/com.facebook.katana/app_ras_blobs/FacebookEmoji.ttf"
    chmod 644 "/data/data/com.facebook.katana/app_ras_blobs/FacebookEmoji.ttf"
fi
