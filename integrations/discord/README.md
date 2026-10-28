# iOS Emoji for Discord

An optional LSPosed application that replaces supported Discord Unicode emoji PNGs with iOS emoji. It is independent of the KernelSU font module and is scoped only to `com.discord`.

Compatibility was verified with Discord **350.8 - Stable** on a OnePlus Ace 6T running Android 16. The included asset manifest covers 4,022 image names; the font provides replacements for 3,996 of them. Unsupported images, custom server emoji, and stickers keep their original appearance.

## Installation

1. Install `iOS-Emoji-Discord-v4.2.apk` as an ordinary Android application.
2. Enable **iOS Emoji for Discord** in LSPosed.
3. Select **Discord (`com.discord`)** as its scope.
4. Force-stop Discord and reopen it. Follow LSPosed's activation instructions if a reboot is requested.

The add-on has no launcher screen and requests no Android permissions. Find it in LSPosed's module list. Disabling its scope or uninstalling it and restarting Discord removes the runtime replacements. Discord itself is neither reinstalled nor modified.

If Android rejects an APK update because of a signing mismatch, uninstall the existing add-on, install this APK, and enable its Discord scope again.

## Behavior

The builder uses HarfBuzz to shape each image name's Unicode sequence using the same font shipped in the KernelSU module. It extracts the corresponding color PNG when a supported single glyph is available. At runtime, hooks replace only matching `AssetManager.open` and `openFd` requests inside Discord. Other asset requests fall through to Discord.

Different Discord versions, image-loading paths, and cached images can affect compatibility. Search LSPosed logs for `iOS Emoji Assets` to inspect hook initialization and matching asset requests.

Clash of Clans, browsers, and system processes are not included in this add-on's scope.

## Building

Requirements: JDK 17 or newer and Android platform/build tools 36. Create a Python environment and install the pinned image-generation dependencies:

```sh
python3 -m venv build/python
build/python/bin/python -m pip install -r tools/requirements-discord.txt
mkdir -p build/dependencies
curl --fail --location --output build/dependencies/xposed-api-82.jar https://api.xposed.info/de/robv/android/xposed/api/82/api-82.jar
build/python/bin/python tools/build_discord.py
```

The official Xposed API jar is checked against its SHA-256 and used only for compilation. It is not bundled into the APK. The tracked `emoji-assets.txt` supplies Discord's Unicode image names; no Discord code or original images are distributed.

The first build creates a release signing key and a randomly generated password under `.signing/`. Both files are private and excluded from Git. Back them up together for future APK updates. To supply an existing signing key, use `--keystore PATH` and set `EMOJI_ASSETS_KEYSTORE_PASSWORD` in the environment.

The APK is written to `build/`. Generated `build/discord/coverage.json` records coverage, and replacement PNGs are stored uncompressed for Android's asset file-descriptor API.
