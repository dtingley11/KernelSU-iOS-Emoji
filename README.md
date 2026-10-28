# KernelSU iOS Emoji

Systemlessly replaces Android's system emoji font with iOS 26.4 emoji. The module ships one font at `system/fonts/NotoColorEmoji.ttf` and uses relative links for supported OEM, legacy, and flag font filenames.

## Downloads

The [v4.2 release](https://github.com/dtingley11/KernelSU-iOS-Emoji/releases/tag/v4.2) includes two independently installable assets:

- **KernelSU-iOS-Emoji-v4.2.zip**: the system emoji module. Install through your KernelSU manager.
- **iOS-Emoji-Discord-v4.2.apk**: the optional Discord image-emoji add-on. Install as an Android application and enable it in LSPosed for Discord only.

The KernelSU module works without Xposed. Discord's bundled PNG emoji require the separate add-on.

## Installation

1. Enable a compatible mount backend, such as Mountify or meta-overlayfs.
2. Install the module ZIP through KernelSU's module manager.
3. Reboot to apply the system font and its aliases.
4. Restart affected apps so they can reload their fonts.

For Discord, install the add-on APK, enable **iOS Emoji for Discord** in LSPosed, select **Discord (`com.discord`)** as its scope, and force-stop and reopen Discord. The add-on has no launcher screen; manage it through LSPosed. If Android rejects an APK update because of a signing mismatch, uninstall the existing add-on, install this APK, and enable it again in LSPosed.

## Compatibility

- Apps using Android's system emoji font must be able to see the replacement mount. KernelSU app profiles and hiding tools can remove module mounts from an app. This module does not change those settings.
- Apps with their own fonts, emoji images, or rendering engines can retain their own emoji designs.
- The Discord add-on supports bundled Unicode PNG emoji. It was verified with Discord **350.8 - Stable** on a OnePlus Ace 6T running Android 16. Custom server emoji and stickers are unchanged; unsupported image names retain Discord's original images.
- **Clash of Clans side-chat emoji are not supported by this release.** Clash is not included in the Discord add-on's scope.
- Device, ROM, root-backend, and app-version differences can affect compatibility.

## Keyboard Refresh

Use the module's **Action** button to refresh existing font targets, restart installed Gboard and Samsung keyboards for user 0, and write a diagnostic report. Open a text field afterward to reload the keyboard.

The Action does not delete keyboard settings, learned words, browser profiles, or caches. Boot scripts do not scan all app data, disable Google services, or automatically force-stop apps.

## Diagnostics

Open an affected app and display emoji, then collect the report from a root shell:

```sh
adb shell
su
sh /data/adb/modules/iOS_Emoji_KSU/diagnose.sh
cp /data/adb/modules/iOS_Emoji_KSU/diagnostics.txt /sdcard/Download/iOS-Emoji-diagnostics.txt
```

The report contains module metadata, device/version information, font configuration, mount counts, loaded emoji font hashes, and selected app profiles where supported. It does not read app messages or preferences. Review device and package information before sharing it publicly.

If a device freezes shortly after boot, disable the module using the root manager's recovery procedure. A reboot is required to discard mounts from earlier versions. Include the module version, mount backend, ROM, and Android version in a bug report.

Earlier versions changed GMS component states and Messenger directory permissions. This release does not make those changes or automatically overwrite their current values, since the original values were not recorded.

## Changelog

### v4.2

- Added the optional Discord LSPosed add-on for bundled image emoji.
- Added install-time aliases for supported OEM, legacy, and split flag fonts without shipping duplicate fonts.
- Removed broad app-data scans, repeated cache deletion, GMS service changes, and automatic app stops from boot.
- Added checks for existing bindings, concurrent-run protection, a bounded boot wait, and service logging.
- Added manual keyboard refresh and font-visibility diagnostics.
- Preserved the Noto family metadata used for browser font fallback.

### v4.1

- Added Noto family metadata for browser emoji fallback and Gecko browser compatibility handling.

### v4.0

- Updated to iOS 26.4 emoji and a single `NotoColorEmoji.ttf` font source.
- Added system and app-specific font bindings.

### v3.0

- Added iOS 18.4 emoji.

### v2.0

- Added Facebook/Messenger package detection and code cleanup.

### v1.1

- Added generic Facebook, Instagram, and Messenger support.

### v1.0

- Added KernelSU support.

## Building

```sh
python3 tools/build_module.py
```

The ZIP is written to `build/` with zero compression and module files at its root. See [the Discord add-on build instructions](integrations/discord/README.md) for the separate APK.

## Device Reports

Reports across module versions include Pixel 6/7 devices on Android 14, Redmi Note 10 Pro with Project Elixir 4.1, OnePlus 12 with OxygenOS 14, POCO X6 5G with LunarisAOSP 3.6, Redmi Note 12 4G with PixelOS 15, and Redmi Note 10S on Android 13.

## Credits

- [topjohnwu](https://github.com/topjohnwu) for Magisk.
- [zx2c4](https://github.com/zx2c4) for the original KernelSU idea.
- [tiann](https://github.com/tiann) for KernelSU.
- [Keinta15](https://github.com/Keinta15/Magisk-iOS-Emoji) for the original emoji module.
- [bugreportion](https://github.com/bugreportion) for the fork that helped inform the KernelSU implementation.

[iOS 26.4 emoji changelog](https://blog.emojipedia.org/apple-ios-26-4-emoji-changelog/)
