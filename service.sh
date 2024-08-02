#!/bin/bash

MODDIR="${0%/*}"
FONT_FILE="$MODDIR/system/fonts/NotoColorEmoji.ttf"
SYSTEM_FONT_FILE="/system/fonts/NotoColorEmoji.ttf"
FACEBOOK_FONT_FILE="$MODDIR/system/fonts/FacebookEmoji.ttf"

# Ensure FONT_FILE exists
if [ ! -f "$FONT_FILE" ]; then
    echo "Font file $FONT_FILE does not exist"
    exit 1
fi

# Samsung Devices
if getprop ro.product.manufacturer | grep -qE -e "^samsung"; then
    SAMSUNG_FONT_FILE="$MODDIR/system/fonts/SamsungColorEmoji.ttf"
    ln -sf "$FONT_FILE" "$SAMSUNG_FONT_FILE"
    chmod 644 "$SAMSUNG_FONT_FILE"

    SYSTEM_ADDITIONAL_XML="/system/etc/fonts_additional.xml"
    FALLBACK_XML="$MODDIR/system/etc/fonts_fallback.xml" # Ensure FALLBACK_XML is defined
    if [ -f "$SYSTEM_ADDITIONAL_XML" ] && [ -f "$FALLBACK_XML" ]; then
        sed 's/<\/familyset>//g' "$SYSTEM_ADDITIONAL_XML" | cat - "$FALLBACK_XML" > "$MODDIR/system/etc/fonts_additional.xml"
        ln -sf "$MODDIR/system/etc/fonts_additional.xml" "$SYSTEM_ADDITIONAL_XML"
    else
        echo "Required XML files do not exist"
    fi
fi

# LG Devices
if getprop ro.product.manufacturer | grep -qE -e "^LGE"; then
    LGE_FONT_FILE="$MODDIR/system/fonts/LGNotoColorEmoji.ttf"
    ln -sf "$FONT_FILE" "$LGE_FONT_FILE"
    chmod 644 "$LGE_FONT_FILE"
fi

# HTC Devices
if getprop ro.product.manufacturer | grep -qE -e "^HTC"; then
    HTC_FONT_FILE="$MODDIR/system/fonts/HTC_ColorEmoji.ttf"
    ln -sf "$FONT_FILE" "$HTC_FONT_FILE"
    chmod 644 "$HTC_FONT_FILE"
fi

# General Replacement
ln -sf "$FONT_FILE" "$SYSTEM_FONT_FILE"
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

# Facebook Specific Replacement
if package_installed "com.facebook.orca"; then
    if [ -f "$FACEBOOK_FONT_FILE" ]; then
        ln -sf "$FACEBOOK_FONT_FILE" "/data/data/com.facebook.orca/app_ras_blobs/FacebookEmoji.ttf"
        chmod 644 "/data/data/com.facebook.orca/app_ras_blobs/FacebookEmoji.ttf"
    else
        echo "FacebookEmoji.ttf does not exist for Messenger"
    fi
fi

if package_installed "com.facebook.katana"; then
    if [ -f "$FACEBOOK_FONT_FILE" ]; then
        ln -sf "$FACEBOOK_FONT_FILE" "/data/data/com.facebook.katana/app_ras_blobs/FacebookEmoji.ttf"
        chmod 644 "/data/data/com.facebook.katana/app_ras_blobs/FacebookEmoji.ttf"
    else
        echo "FacebookEmoji.ttf does not exist for Facebook"
    fi
fi