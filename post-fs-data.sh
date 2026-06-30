MODDIR=${0%/*}
FONT_FILE="$MODDIR/system/fonts/NotoColorEmoji.ttf"
SYSTEM_FONT_FILE="/system/fonts/NotoColorEmoji.ttf"

mount_font() {
    source="$1"
    target="$2"

    [ -f "$source" ] || return 1
    [ -e "$target" ] || return 1

    mount -o bind "$source" "$target" && chmod 644 "$target"
}

for target in \
    "$SYSTEM_FONT_FILE" \
    /system/fonts/SamsungColorEmoji.ttf \
    /system/fonts/LGNotoColorEmoji.ttf \
    /system/fonts/HTC_ColorEmoji.ttf \
    /system/fonts/AndroidEmoji-htc.ttf \
    /system/fonts/ColorUniEmoji.ttf \
    /system/fonts/DcmColorEmoji.ttf \
    /system/fonts/CombinedColorEmoji.ttf \
    /system/fonts/NotoColorEmojiLegacy.ttf
do
    [ -e "$target" ] || continue
    mount_font "$FONT_FILE" "$target"
done
