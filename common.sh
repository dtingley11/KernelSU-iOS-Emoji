FONT_FILE="$MODDIR/system/fonts/NotoColorEmoji.ttf"
FACEBOOK_APPS="com.facebook.orca com.facebook.katana com.facebook.lite com.facebook.mlite"
KEYBOARD_APPS="com.google.android.inputmethod.latin com.samsung.android.honeyboard com.sec.android.inputmethod"
SYSTEM_FONT_ALIASES="SamsungColorEmoji.ttf LGNotoColorEmoji.ttf HTC_ColorEmoji.ttf AndroidEmoji-htc.ttf ColorUniEmoji.ttf DcmColorEmoji.ttf CombinedColorEmoji.ttf NotoColorEmojiLegacy.ttf NotoColorEmojiFlags.ttf"

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

mount_font() {
    local target="$1"
    [ -f "$FONT_FILE" ] && [ -f "$target" ] || return 0
    if [ "$FONT_FILE" -ef "$target" ]; then
        log "Already bound: $target"
        return 0
    fi
    if mount -o bind "$FONT_FILE" "$target"; then
        log "Bound: $target"
    else
        log "ERROR: Cannot bind $target"
        return 1
    fi
}

mount_oem_fonts() {
    local font result=0
    for font in $SYSTEM_FONT_ALIASES
    do
        # The mount backend already resolves our relative aliases to the main font.
        [ -L "/system/fonts/$font" ] && continue
        mount_font "/system/fonts/$font" || result=1
    done
    return "$result"
}

prepare_font_aliases() {
    local font
    for font in $SYSTEM_FONT_ALIASES; do
        if [ -e "/system/fonts/$font" ] || grep -Fq "$font" \
            /system/etc/fonts.xml /system/etc/font_fallback.xml \
            /system_ext/etc/fonts_base.xml /system_ext/etc/fonts_ule.xml \
            /product/etc/fonts_customization.xml 2>/dev/null; then
            # Relative links stay within the module's overlaid fonts directory.
            ln -sf NotoColorEmoji.ttf "$MODDIR/system/fonts/$font" || return 1
            log "Prepared system font alias: $font"
        fi
    done
    return 0
}

mount_app_fonts() {
    local userdir app target result=0
    for userdir in /data/user/*; do
        [ -d "$userdir" ] || continue
        case "${userdir##*/}" in ''|*[!0-9]*) continue ;; esac
        for app in $FACEBOOK_APPS; do
            case "$app" in
                com.facebook.lite|com.facebook.mlite)
                    target="$userdir/$app/files/emoji_font.ttf" ;;
                *) target="$userdir/$app/app_ras_blobs/FacebookEmoji.ttf" ;;
            esac
            mount_font "$target" || result=1
        done
    done
    return "$result"
}

start_service_log() {
    if [ -f "$MODDIR/service.log" ] &&
        [ "$(wc -c < "$MODDIR/service.log")" -gt 262144 ]; then
        mv -f "$MODDIR/service.log" "$MODDIR/service.log.1"
    fi
    exec >> "$MODDIR/service.log" 2>&1
}
