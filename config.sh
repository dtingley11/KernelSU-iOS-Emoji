# Compatibility settings for installers that support the legacy module format.
MODID=iOS_Emoji_KSU
AUTOMOUNT=true
PROPFILE=false
POSTFSDATA=true
LATESTARTSERVICE=true
REPLACE=""

print_modname() {
    ui_print "*******************************"
    ui_print "     KSU iOS Emoji 26.4"
    ui_print "*******************************"
}

set_permissions() {
    set_perm_recursive "$MODPATH" 0 0 0755 0644
}
