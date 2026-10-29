FONT_FILE="$MODDIR/system/fonts/NotoColorEmoji.ttf"
FACEBOOK_APPS="com.facebook.orca com.facebook.katana com.facebook.lite com.facebook.mlite"
KEYBOARD_APPS="com.google.android.inputmethod.latin com.samsung.android.honeyboard com.sec.android.inputmethod"
SYSTEM_FONT_ALIASES="SamsungColorEmoji.ttf LGNotoColorEmoji.ttf HTC_ColorEmoji.ttf AndroidEmoji-htc.ttf ColorUniEmoji.ttf DcmColorEmoji.ttf CombinedColorEmoji.ttf NotoColorEmojiLegacy.ttf NotoColorEmojiFlags.ttf"
GOOGLE_EMOJI_FONT="com.google.android.gms/files/fonts/opentype/Noto_COLR_Emoji_Compat-400-100_0-0_0.ttf"
ACTION_APPS="$KEYBOARD_APPS com.android.chrome com.chrome.beta com.chrome.dev com.chrome.canary com.brave.browser org.mozilla.firefox org.mozilla.firefox_beta org.mozilla.fenix org.mozilla.focus org.mozilla.klar com.google.android.googlequicksearchbox $FACEBOOK_APPS"
GOOGLE_FONT_APPS="com.android.chrome com.chrome.beta com.chrome.dev com.chrome.canary com.brave.browser com.google.android.googlequicksearchbox"
GOOGLE_FONT_CHANGED=0

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

android_cmd() {
    # Binder shell commands pass their stdio to system_server. Give them pipes
    # and /dev/null, since system_server cannot access our private log files.
    local output status
    output=$("$@" < /dev/null 2>&1)
    status=$?
    [ -z "$output" ] || printf '%s\n' "$output"
    return "$status"
}

wait_for_app_storage() {
    local attempt=0
    [ "$(getprop ro.crypto.type)" = file ] || return 0
    while [ "$(getprop sys.user.0.ce_available)" != true ]; do
        if [ "$attempt" -ge 60 ]; then
            log "App storage wait timed out; use Action after unlocking"
            return 0
        fi
        [ "$attempt" != 0 ] || log "Waiting for user-0 app storage to unlock"
        sleep 2
        attempt=$((attempt + 1))
    done
    log "User-0 app storage is ready"
}

restart_google_font_apps() {
    local app result=0
    [ "$GOOGLE_FONT_CHANGED" = 1 ] || return 0
    for app in $GOOGLE_FONT_APPS; do
        # Check only user-0 processes; leave unopened apps and other users alone.
        ps -A -o UID,NAME 2>/dev/null | awk -v app="$app" \
            '$1 >= 10000 && $1 < 100000 && ($2 == app || index($2, app ":") == 1) {found=1} END {exit !found}' || continue
        if android_cmd am force-stop --user 0 "$app"; then
            log "Stopped $app to reload the newly bound Google emoji font"
        else
            log "ERROR: Cannot stop $app after the Google font changed"
            result=1
        fi
    done
    return "$result"
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
        mount_google_emoji_font "$userdir" || result=1
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

mount_google_emoji_font() {
    # Chromium can prefer this downloaded font over the mounted system font.
    # Visit only the observed provider filename; never delete provider caches.
    local target="$1/$GOOGLE_EMOJI_FONT" changed=0
    if [ -f "$FONT_FILE" ] && [ -f "$target" ] && [ ! "$FONT_FILE" -ef "$target" ]; then
        changed=1
    fi
    mount_font "$target" || return 1
    if [ "$changed" = 1 ] && [ "$FONT_FILE" -ef "$target" ] && [ "${1##*/}" = 0 ]; then
        GOOGLE_FONT_CHANGED=1
    fi
    return 0
}

start_service_log() {
    if [ -f "$MODDIR/service.log" ] &&
        [ "$(wc -c < "$MODDIR/service.log")" -gt 262144 ]; then
        mv -f "$MODDIR/service.log" "$MODDIR/service.log.1"
    fi
    exec >> "$MODDIR/service.log" 2>&1
}
