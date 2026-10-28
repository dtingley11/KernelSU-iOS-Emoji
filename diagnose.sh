MODDIR=${0%/*}
. "$MODDIR/common.sh"
REPORT="$MODDIR/diagnostics.txt"
umask 077
exec > "$REPORT" 2>&1
chmod 600 "$REPORT"

log "iOS Emoji diagnostic report (no app messages or preferences collected)"
cat "$MODDIR/module.prop"
for prop in ro.product.manufacturer ro.product.model ro.build.version.release sys.boot_completed; do
    printf '%s=%s\n' "$prop" "$(getprop "$prop")"
done
echo "Font files and labels:"
ls -lZ "$FONT_FILE" /system/fonts/*Emoji*.ttf 2>/dev/null
echo "Current font hashes:"
sha256sum "$FONT_FILE" /system/fonts/NotoColorEmoji.ttf
echo "System font mounts (first 40):"
awk '$5 == "/system/fonts" || $5 ~ /^\/system\/fonts\/.*[Ee]moji/ {n++; if (n <= 40) print} END {print "Total:", n+0}' /proc/self/mountinfo
echo "Configured system emoji families:"
for config in /system/etc/fonts.xml /system/etc/font_fallback.xml \
    /product/etc/fonts_customization.xml /system_ext/etc/fonts_base.xml; do
    [ -f "$config" ] && grep -in -E 'emoji|und-Zsye' "$config"
done

echo "Loaded emoji fonts (current processes only):"
ps -A -o PID,NAME 2>/dev/null | while read -r pid name; do
    case "$pid" in ''|*[!0-9]*) continue ;; esac
    case "$name" in
        system_server|*zygote*|com.android.systemui|com.google.android.inputmethod.latin|\
        com.samsung.android.honeyboard|com.sec.android.inputmethod|com.brave.browser*|\
        org.mozilla.*|com.supercell.clashofclans|com.discord)
            printf '\nProcess %s (%s)\n' "$name" "$pid"
            readlink "/proc/$pid/ns/mnt"
            awk 'tolower($0) ~ /emoji/ {if (++n <= 12) print}' "/proc/$pid/maps" 2>/dev/null
            awk 'tolower($0) ~ /emoji/ {if (++n <= 12) print $1}' "/proc/$pid/maps" 2>/dev/null |
                while read -r range; do
                    sha256sum "/proc/$pid/map_files/$range" 2>/dev/null
                done
            ;;
    esac
done

if [ -x /data/adb/ksu/bin/ksud ]; then
    echo "Keyboard, browser, and game profiles (if supported by this ksud):"
    for app in '$' $KEYBOARD_APPS com.brave.browser com.supercell.clashofclans com.discord; do
        /data/adb/ksu/bin/ksud profile get "$app" 2>/dev/null
    done
fi
echo "Recent module service log:"
[ -f "$MODDIR/service.log" ] && tail -60 "$MODDIR/service.log"
log "Report complete"
