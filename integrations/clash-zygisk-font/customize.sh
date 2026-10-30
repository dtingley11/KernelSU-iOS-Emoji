[ "$ARCH" = arm64 ] || abort "! This private prototype is ARM64-only"
[ "$KSU" = true ] || abort "! This private prototype requires KernelSU"
[ "$(getprop ro.build.version.sdk)" = 36 ] || abort "! This prototype targets Android 16"
[ -d /data/adb/modules/rezygisk ] || abort "! Existing ReZygisk runtime required"
[ ! -f /data/adb/modules/rezygisk/disable ] || abort "! ReZygisk is disabled"
[ ! -f /data/adb/modules/rezygisk/remove ] || abort "! ReZygisk is scheduled for removal"
runtime=$(sed -n 's/^versionCode=//p' /data/adb/modules/rezygisk/module.prop)
[ "$runtime" = 552 ] || abort "! This prototype targets ReZygisk build 552"
uid=$(pm list packages --user 0 -U com.supercell.clashofclans | awk \
    '$1 == "package:com.supercell.clashofclans" {sub(/^uid:/, "", $2); print $2}')
[ "$uid" = @CLASH_UID@ ] || abort "! Clash UID changed; rebuild the prototype"
if [ -d /data/adb/modules/ios_emoji_clash_ns_control ] && \
    [ ! -f /data/adb/modules/ios_emoji_clash_ns_control/disable ] && \
    [ ! -f /data/adb/modules/ios_emoji_clash_ns_control/remove ]; then
    abort "! Disable the earlier observe-only control before this separate test"
fi
hash=$(sha256sum "$MODPATH/font-assets.apk" | cut -d ' ' -f 1)
[ "$hash" = @PAYLOAD_SHA@ ] || abort "! Font payload checksum mismatch"
hook_hash=$(sha256sum "$MODPATH/font-hook.so" | cut -d ' ' -f 1)
[ "$hook_hash" = @HOOK_SHA@ ] || abort "! Font helper checksum mismatch"
set_perm_recursive "$MODPATH" 0 0 0755 0644
umask 077
: > "$MODPATH/armed"
chmod 600 "$MODPATH/armed"
ui_print "- Armed for one Clash main-process launch after reboot"
ui_print "- Keep Clash outside LSPosed scope"
ui_print "- Log tag: ClashFontZygisk"
ui_print "- No game APK or app-data changes"
