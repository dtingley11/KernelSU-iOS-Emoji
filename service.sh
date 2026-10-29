MODDIR=${0%/*}
. "$MODDIR/common.sh"

# A lock under /dev disappears on reboot and prevents concurrent mount passes.
LOCKDIR=/dev/iOS_Emoji_KSU_service.lock
if ! mkdir "$LOCKDIR" 2>/dev/null; then
    exit 0
fi
trap 'rmdir "$LOCKDIR"' EXIT
start_service_log
log "Service started"

attempt=0
while [ "$(getprop sys.boot_completed)" != 1 ]; do
    if [ "$attempt" -ge 60 ]; then
        log "Boot wait timed out; use the module Action after boot"
        exit 0
    fi
    sleep 2
    attempt=$((attempt + 1))
done

if [ ! -s "$FONT_FILE" ]; then
    log "ERROR: Module font is missing or empty"
    exit 1
fi

case "${1:-}" in
    --manual) ;;
    *) wait_for_app_storage ;;
esac

# The mount backend handles the primary system font. Do not scan /data aliases:
# they can refer to the same files through shared mounts and stack bindings.
result=0
mount_oem_fonts || result=1
mount_app_fonts || result=1
if [ "${1:-}" != --manual ]; then
    restart_google_font_apps || result=1
fi
if [ "$result" = 0 ]; then
    log "Service completed; app visibility remains controlled by the root manager"
else
    log "ERROR: One or more font mounts failed"
fi
exit "$result"
