# Optional Clash support. Sourced by the installer and Action; never runs at boot.
CLASH_MODULES_ROOT=/data/adb/modules

volume_choice() {
    local events
    command -v timeout >/dev/null 2>&1 && command -v getevent >/dev/null 2>&1 || return 0
    events=$(timeout "$1" getevent -ql 2>/dev/null) || :
    printf '%s\n' "$events" | awk '
        /EV_KEY/ && /(DOWN|00000001)/ {
            if ($0 ~ /KEY_VOLUMEUP/) key="up"
            if ($0 ~ /KEY_VOLUMEDOWN/) key="down"
        } END {print key}'
}

clash_supported() {
    local old
    [ "$(getprop ro.product.cpu.abi)" = arm64-v8a ] || return 1
    [ "$(getprop ro.build.version.sdk)" = 36 ] || return 1
    [ -f "$CLASH_MODULES_ROOT/rezygisk/module.prop" ] || return 1
    [ ! -e "$CLASH_MODULES_ROOT/rezygisk/disable" ] &&
        [ ! -e "$CLASH_MODULES_ROOT/rezygisk/remove" ] || return 1
    [ "$(sed -n 's/^versionCode=//p' "$CLASH_MODULES_ROOT/rezygisk/module.prop")" = 552 ] || return 1
    for old in ios_emoji_clash_ns_control ios_emoji_clash_zygisk_font; do
        if [ -d "$CLASH_MODULES_ROOT/$old" ] &&
            [ ! -e "$CLASH_MODULES_ROOT/$old/disable" ] &&
            [ ! -e "$CLASH_MODULES_ROOT/$old/remove" ]; then
            return 1
        fi
    done
}

clash_enable() {
    local uid
    clash_change_allowed || return 1
    if ! clash_supported; then
        echo "Clash needs ARM64, Android 16 and ReZygisk 552. Disable any earlier Clash test module first."
        return 1
    fi
    uid=$(android_cmd pm list packages --user 0 -U com.supercell.clashofclans | awk \
        '$1 == "package:com.supercell.clashofclans" {sub(/^uid:/, "", $2); print $2}')
    case "$uid" in ''|*[!0-9]*) echo "Install Clash for user 0 first."; return 1 ;; esac
    if [ "$uid" -lt 10000 ] || [ "$uid" -ge 20000 ]; then
        echo "Clash user-0 UID is unsupported."
        return 1
    fi
    if ! (cd "$MODDIR" && sha256sum -c clash/payload.sha256 >/dev/null 2>&1); then
        echo "Clash files failed verification. Reinstall the module."
        return 1
    fi
    umask 077
    mkdir -p "$MODDIR/zygisk" || return 1
    chmod 755 "$MODDIR/zygisk" || return 1
    cp "$MODDIR/clash/entry.so" "$MODDIR/zygisk/arm64-v8a.so.new" &&
        chmod 644 "$MODDIR/zygisk/arm64-v8a.so.new" &&
        printf '%s\n' "$uid" > "$MODDIR/clash/enabled.new" &&
        chmod 600 "$MODDIR/clash/enabled.new" &&
        mv -f "$MODDIR/zygisk/arm64-v8a.so.new" "$MODDIR/zygisk/arm64-v8a.so" &&
        mv -f "$MODDIR/clash/enabled.new" "$MODDIR/clash/enabled" || return 1
    echo "Clash enabled. Reboot to apply."
}

clash_disable() {
    clash_change_allowed || return 1
    rm -f "$MODDIR/clash/enabled" "$MODDIR/clash/enabled.new" \
        "$MODDIR/zygisk/arm64-v8a.so" "$MODDIR/zygisk/arm64-v8a.so.new" || return 1
    rmdir "$MODDIR/zygisk" 2>/dev/null || :
    echo "Clash disabled. Reboot to apply."
}

clash_change_allowed() {
    if [ "$MODDIR" = "$CLASH_MODULES_ROOT/iOS_Emoji_KSU" ] &&
        [ -d "${CLASH_MODULES_ROOT%/*}/modules_update/iOS_Emoji_KSU" ]; then
        echo "Reboot to finish the pending module update, then change Clash settings."
        return 1
    fi
}

clash_install_choice() {
    local choice previous=off
    if ! clash_supported; then
        ui_print "- Clash support is off; system emoji will work normally"
        return 0
    fi
    [ ! -f "$CLASH_MODULES_ROOT/iOS_Emoji_KSU/clash/enabled" ] || previous=on
    ui_print "- Optional Clash support (default: $previous)"
    ui_print "- Press volume up to enable or volume down to disable within 6 seconds"
    choice=$(volume_choice 6)
    case "$choice" in
        up) clash_enable || ui_print "- Clash remains off; use Action to review setup" ;;
        down) clash_disable ;;
        *) if [ "$previous" = on ]; then
               clash_enable || ui_print "- Clash remains off; use Action to review setup"
           fi ;;
    esac
    return 0
}

clash_action_menu() {
    local choice label=Enable
    echo "Volume up: refresh emoji. Volume down: Clash settings."
    echo "Waiting 3 seconds; default is refresh."
    choice=$(volume_choice 3)
    [ "$choice" = down ] || return 2
    [ ! -f "$MODDIR/clash/enabled" ] || label=Disable
    echo "Volume up: $label Clash. Volume down: cancel."
    echo "Waiting 5 seconds; default is cancel."
    choice=$(volume_choice 5)
    if [ "$choice" != up ]; then
        echo "Cancelled."
        return 0
    fi
    if [ "$label" = Enable ]; then clash_enable; else clash_disable; fi
}
