# Clash Zygisk Font TEST

Private, unverified prototype on `test/clash-zygisk-font`. Uses native Zygisk and
a standalone Dobby inline hook, with no LSPosed dependency. It targets only the
exact main Clash process at the user-0 UID supplied to the builder.

It replaces only `titan/fonts/NotoColorEmoji.ttf` requests through
`AAssetManager_open`, returning a real Android asset from a separate, private
asset manager. Other paths pass through. Missing or wrong-size replacement
assets fall back to the original request. The font bytes and family names match
the production module. The asset carrier is not installed as an Android app.

The inline hook is installed before the game starts, so calls made by a later
loaded `libg.so` can reach it. This does not use Zygisk's PLT registration after
specialization. The module remains resident once hook installation is attempted.
Non-target processes request normal library unloading and do not contact the
companion. There are no mounts, game APK edits, app-data writes, SELinux changes,
root-profile changes, Java/Xposed hooks, or protection-check modifications.

## One-shot behavior

Installation arms one launch. A fixed-purpose root companion, reachable through
Zygisk, consumes the root-owned `armed` marker before serving only this module's
`font-assets.apk`. It accepts no paths, commands, or arbitrary requests and serves
only a root peer. Length, ownership, file type, symlinks, and write permissions
are checked. Transfers have a 64 MB ceiling and a five-second socket deadline.

The selected process receives bytes before specialization. After specialization
it places them in a sealed memory file and constructs its own asset manager. No
module file descriptors need to survive the sandbox transition. Private Android
framework methods are version-sensitive: missing/blocked methods fail normally,
without changing hidden-API policy. A failed attempt consumes the marker too;
subsequent launches retain original assets. An installed hook lasts for that
process's lifetime. One-shot arming does not remove hooks from an existing process.

## Build

Requirements: existing SDK 36/build-tools 36, NDK 29.0.14206865, CMake, Ninja,
and the pinned official Zygisk API v4 header already under build dependencies.
Clone Dobby into `build/dependencies/dobby` at revision
`b0176de574104726bb68dff3b77ee666300fc338`.

```sh
build/python/bin/python tools/build_clash_zygisk_font.py --uid 10474
build/python/bin/python -m unittest discover -s tests
```

Output: `build/diagnostics/Clash-Zygisk-Font-Redirect-1.zip`.
The builder uses a clean Git archive of an Android-compatible Dobby revision and
statically links the library without patching it. It does not enable its symbol resolver, linker utilities,
obfuscation, examples, or tests. Metadata records pinned revisions and hashes.
The official Zygisk header is not modified. The module is ARM64/API 30 with
16 KB ELF alignment; the installer requires Android 16 and ReZygisk build 552.

## Device trial

No deployment is implied by building. Explicit installation/reboot/test approval
is required. Revalidate the connected serial, Clash UID, game version, ReZygisk
version, and root profile before deployment. Disable the previous observe-only
control first if still enabled; the installer refuses overlapping controls and
does not disable them itself. Leave Clash outside LSPosed scope.

Start a live `ClashFontZygisk` tag capture before the first cold launch. Expected
stages are `TARGET_SELECTED`, `HOOK_READY`, and `FONT_SERVED`. `HOOK_FAILED` or
`PREPARE_FAILED` is not a successful replacement. Missing retained log records do
not establish non-execution. Logs contain stage/size information, not chat text.

Verify the font source and sent-message appearance independently. The user has
confirmed iOS emoji in the input bar but stock emoji after sending; input-field
appearance is not acceptance. The bundled font load is established, but its use
for sent-message glyphs is still unproven. Historical Samsung behavior is an
uncaptured, possibly older reference, not proof about this game version.

This adds a detectable runtime hook. Passing the earlier observe-only control
does not establish hook compatibility. If startup fails, stop; do not hide the
hook or bypass checks. Disable/remove only this prototype and reboot to unload
it fully. Game data does not need to be reset. The production emoji module and
Discord add-on are independent. Do not publish this diagnostic as a release asset.
