# v4.2

This release adds optional Discord image-emoji replacement and reduces background work in the system font module.

## Downloads

- **KernelSU-iOS-Emoji-v4.2.zip**: install through KernelSU with a compatible mount backend, then reboot.
- **iOS-Emoji-Discord-v4.2.apk**: optional Android application; enable **iOS Emoji for Discord** in LSPosed and select **Discord only** as its scope. Force-stop and reopen Discord afterward.

The KernelSU module works independently of Xposed. The separate APK handles Discord's bundled emoji images.

## Changes

- Added Discord image replacements, verified on Discord 350.8 - Stable.
- Added system aliases for supported OEM, legacy, and flag fonts while shipping one font file.
- Removed broad app-data scans, repeated cache deletion, GMS service changes, and automatic app stops from boot.
- Added duplicate-binding checks, concurrent-run protection, bounded startup, and service logging.
- Added manual Gboard/Samsung keyboard refresh and font-visibility diagnostics through the module Action.
- Preserved the Noto family names used for browser emoji fallback.

## Compatibility

- Module-hiding settings affect which apps can see the system font replacement.
- Apps with bundled fonts or images may retain their own emoji designs.
- Discord custom server emoji, stickers, and unsupported bundled images retain their original appearance.
- Clash of Clans side-chat emoji are not supported by this release. Clash is not part of the Discord add-on's scope.
- If Android rejects an add-on APK update because of a signing mismatch, uninstall the existing add-on, install the release APK, and enable its Discord scope again in LSPosed.
