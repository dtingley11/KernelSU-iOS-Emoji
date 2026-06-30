MODDIR=${0%/*}
FONT_FILE="$MODDIR/system/fonts/NotoColorEmoji.ttf"
FACEBOOK_APPS="com.facebook.orca com.facebook.katana com.facebook.lite com.facebook.mlite"
GMS_FONT_PROVIDER="com.google.android.gms/com.google.android.gms.fonts.provider.FontsProvider"
GMS_FONT_UPDATER="com.google.android.gms/com.google.android.gms.fonts.update.UpdateSchedulerService"
ORCA_FONT_DIR1="/data/data/com.facebook.orca/files/fonts"
ORCA_FONT_DIR2="/data/user/0/com.facebook.orca/files/fonts"
DATA_FONTS_DIR="/data/fonts"
GMS_FONT_DIR_PATTERN="com.google.android.gms/files/fonts"

package_installed() {
    pm list packages | grep -q "$1"
}

bind_font() {
    source="$1"
    target="$2"

    [ -f "$source" ] || return 1
    mkdir -p "$(dirname "$target")"
    [ -e "$target" ] || : > "$target"

    mount -o bind "$source" "$target" && chmod 644 "$target"
}

wait_for_boot() {
    while [ "$(getprop sys.boot_completed)" != "1" ]; do
        sleep 5
    done

    while [ ! -d /sdcard ]; do
        sleep 5
    done
}

display_name() {
    case "$1" in
        com.facebook.orca) echo "Messenger" ;;
        com.facebook.katana) echo "Facebook" ;;
        com.facebook.lite) echo "Facebook Lite" ;;
        com.facebook.mlite) echo "Messenger Lite" ;;
        com.google.android.inputmethod.latin) echo "Gboard" ;;
        *) echo "$1" ;;
    esac
}

replace_emoji_fonts() {
    [ -f "$FONT_FILE" ] || return 0

    find /data/data /data/user/0 -type f -iname '*emoji*.ttf' 2>/dev/null | while read -r font; do
        bind_font "$FONT_FILE" "$font"
    done
}

lock_messenger_fonts() {
    for app in $FACEBOOK_APPS; do
        package_installed "$app" || continue

        case "$app" in
            com.facebook.lite|com.facebook.mlite)
                target="/data/data/$app/files/emoji_font.ttf"
                ;;
            *)
                target="/data/data/$app/app_ras_blobs/FacebookEmoji.ttf"
                ;;
        esac

        bind_font "$FONT_FILE" "$target"
    done
}

clear_cache() {
    app="$1"

    package_installed "$app" || return 0

    for subpath in /cache /code_cache /app_webview /files/GCache; do
        target="/data/data/${app}${subpath}"
        [ -d "$target" ] && rm -rf "$target"
    done

    am force-stop "$app" >/dev/null 2>&1
}

block_messenger_downloads() {
    for dir in "$ORCA_FONT_DIR1" "$ORCA_FONT_DIR2"; do
        [ -d "$dir" ] && rm -rf "$dir"/*
        mkdir -p "$dir"
        chmod 000 "$dir" 2>/dev/null
    done
}

disable_gms_font_services() {
    users=$(ls -d /data/user/* 2>/dev/null)

    for userpath in $users; do
        userid=${userpath##*/}
        pm disable --user "$userid" "$GMS_FONT_PROVIDER" >/dev/null 2>&1
        pm disable --user "$userid" "$GMS_FONT_UPDATER" >/dev/null 2>&1
    done
}

cleanup_generated_fonts() {
    [ -d "$DATA_FONTS_DIR" ] && rm -rf "$DATA_FONTS_DIR"

    find /data -type d -path "*$GMS_FONT_DIR_PATTERN*" 2>/dev/null | while read -r dir; do
        rm -rf "$dir"
    done
}

wait_for_boot

replace_emoji_fonts

for app in $FACEBOOK_APPS; do
    package_installed "$app" || continue
    clear_cache "$app"
done

clear_cache com.google.android.inputmethod.latin
lock_messenger_fonts
block_messenger_downloads
disable_gms_font_services
cleanup_generated_fonts
