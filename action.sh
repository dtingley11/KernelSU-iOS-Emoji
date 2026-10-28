MODDIR=${0%/*}
. "$MODDIR/common.sh"

if [ "$(getprop sys.boot_completed)" != 1 ]; then
    echo "Wait for Android to finish booting, then run Action again."
    exit 1
fi

echo "Refreshing existing font targets..."
if ! sh "$MODDIR/service.sh"; then
    echo "Font refresh failed; see $MODDIR/service.log"
    exit 1
fi

# Refresh keyboards on request without deleting settings or learned words.
for app in $KEYBOARD_APPS; do
    if pm path --user 0 "$app" 2>/dev/null | grep -q '^package:'; then
        if am force-stop --user 0 "$app"; then
            log "Stopped $app; open a text field to reload the keyboard"
        else
            log "ERROR: Cannot stop $app"
        fi
    fi
done

echo "Writing diagnostics..."
sh "$MODDIR/diagnose.sh"
echo "Report: $MODDIR/diagnostics.txt"
echo "A refresh cannot override module hiding or an app's bundled image emoji."
