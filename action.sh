MODDIR=${0%/*}
. "$MODDIR/common.sh"

if [ "$(getprop sys.boot_completed)" != 1 ]; then
    echo "Wait for Android to finish booting, then try again."
    exit 1
fi

# Prevent two manual refreshes from stopping/clearing the same apps together.
ACTION_LOCK=/dev/iOS_Emoji_KSU_action.lock
if ! mkdir "$ACTION_LOCK" 2>/dev/null; then
    echo "Emoji refresh is already running. Try again shortly."
    exit 1
fi
trap 'rmdir "$ACTION_LOCK"' EXIT

umask 077
ACTION_LOG="$MODDIR/action.log"
if ! : > "$ACTION_LOG" || ! chmod 600 "$ACTION_LOG"; then
    echo "Could not save the refresh log. Try again."
    exit 1
fi

cache_supported=0
refresh_emoji() {
    local sdk app result=0
    log "Manual emoji refresh started"
    if ! sh "$MODDIR/service.sh" --manual; then
        log "ERROR: Font refresh failed; see service.log"
        return 1
    fi

    # Require both a modern parser and an advertised cache-only option. On old
    # parsers, --user MUST precede --cache-only so it cannot become a data wipe.
    sdk=$(getprop ro.build.version.sdk)
    case "$sdk" in
        ''|*[!0-9]*) ;;
        *) if [ "$sdk" -ge 33 ] && android_cmd pm help | grep -q -- '--cache-only'; then
               cache_supported=1
           fi ;;
    esac
    [ "$cache_supported" = 1 ] || log "Cache-only clearing unavailable; apps will still be stopped"

    for app in $ACTION_APPS; do
        android_cmd pm path --user 0 "$app" | grep -q '^package:' || continue
        if ! android_cmd am force-stop --user 0 "$app"; then
            log "ERROR: Cannot stop $app; skipping its cache"
            result=1
            continue
        fi
        log "Stopped $app"
        if [ "$cache_supported" = 1 ]; then
            if android_cmd pm clear --user 0 --cache-only "$app"; then
                log "Cleared cache only: $app"
            else
                log "ERROR: Cache-only clearing failed for $app"
                result=1
            fi
        fi
    done

    if ! sh "$MODDIR/diagnose.sh"; then
        log "ERROR: Could not write diagnostics"
        result=1
    fi
    log "Manual emoji refresh completed: result=$result"
    return "$result"
}

echo "Refreshing emoji..."
if refresh_emoji >> "$ACTION_LOG" 2>&1; then
    if [ "$cache_supported" = 1 ]; then
        echo "Done. Reopen your apps to see the updated emoji."
    else
        echo "Done. Reopen your apps. Cache clearing is unavailable on this Android version."
    fi
else
    echo "Refresh incomplete. See action.log for details."
    exit 1
fi
