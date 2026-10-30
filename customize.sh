MODDIR="$MODPATH"
. "$MODDIR/common.sh"

ui_print "- Preparing iOS emoji font aliases"
if [ ! -s "$FONT_FILE" ]; then
    abort "! Missing system/fonts/NotoColorEmoji.ttf"
fi
if ! prepare_font_aliases; then
    abort "! Could not prepare emoji font aliases"
fi
set_perm_recursive "$MODPATH" 0 0 0755 0644
ui_print "- Font aliases will be applied by the mount backend after reboot"

if [ -f "$MODDIR/clash.sh" ]; then
    . "$MODDIR/clash.sh"
    clash_install_choice
fi
