# Clash Zygisk Font TEST

Private prototype on `test/clash-zygisk-font`. Build 3 narrows library loading;
its phone behavior is unverified. The user confirmed build 2 works on the OnePlus
on 2026-10-29, then reported a Duck Detector warning. Uses native Zygisk and
a standalone Dobby inline hook, with no LSPosed dependency. It targets only the
exact main Clash process at the user-0 UID supplied to the builder.

It replaces only `titan/fonts/NotoColorEmoji.ttf` requests through
`AAssetManager_open`, returning a real Android asset from a separate, private
asset manager. Other paths pass through. Missing or wrong-size replacement
assets fall back to the original request. The font bytes and family names match
the production module. The asset carrier is not installed as an Android app.

The inline hook is installed before the game starts, so calls made by a later
loaded `libg.so` can reach it. This does not use Zygisk's PLT registration after
specialization. Build 2 reads its own executable mappings and hooks each copy of
the exact system asset library matching the linked provider's device/inode and
symbol file offset (at most four). Each provider has a separate original-function
pointer. Unknown or ambiguous mappings stop preparation before any hook.
The hook helper remains resident once loaded. There are no mounts, game APK edits, app-data writes, SELinux changes,
root-profile changes, Java/Xposed hooks, or protection-check modifications.

## Deferred helper loading

Build 3 has two native libraries. `zygisk/arm64-v8a.so` contains only process
selection, the fixed-file companion, byte transfer, and the helper handoff.
It links no Dobby, Android asset library, or C++ runtime. It has no CRT startup
or shutdown routines: all static data is trivial and Zygisk initialization is
explicit. The builder audits symbols, dependencies, and initializer/finalizer
tables to reject accidental constructors or exit-handler registration.

Other processes request normal unloading and return before any companion
connection or helper loading. Only an armed, exact Clash main-process match
receives the font and helper bytes. After specialization, it creates sealed
memory files and uses the normal Android `android_dlopen_ext` FD interface to
load `font-hook.so`. That helper owns Dobby, the Android asset dependency, the
private asset manager, and all resident hook callbacks. It checks its ABI and
the app UID again. Even in Clash, the small Zygisk entry unloads after its
callback; no hook points back into it. A loaded helper is retained through any
preparation or hook failure, so possible callbacks are never unmapped.

The Duck screenshot reported one exit-handler heuristic with clean memory,
mapping, and linker checks. Read-only inspection showed no font helper retained
in Duck's process. Build 2's linked Dobby constructor registers an exit handler
before process selection, so normal unload residue is a plausible contributor;
causation is not established. Build 3 avoids loading that dependency outside
Clash. It does not modify detector results or exit-handler tables. Reduced scope
does not establish that Duck's warning will disappear or that the hook is
undetectable inside Clash.

## One-shot behavior

Installation arms one launch. A fixed-purpose root companion, reachable through
Zygisk, consumes the root-owned `armed` marker before serving only this module's
`font-assets.apk` and `font-hook.so`. It accepts no paths, commands, or arbitrary requests and serves
only a root peer. Length, ownership, file type, symlinks, and write permissions
are checked. Transfers have a 64 MB ceiling and a five-second socket deadline.

The selected process receives both byte streams before specialization. After
specialization it creates sealed memory files, loads its helper, and constructs
its own asset manager. No
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

Output: `build/diagnostics/Clash-Zygisk-Font-Redirect-3.zip`.
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
stages are `TARGET_SELECTED`, `HELPER_LOADED`, `PROVIDERS_FOUND`, `PROVIDER_HOOKED`, `HOOK_READY`,
and `FONT_SERVED`. `HOOK_FAILED` or
`PREPARE_FAILED` is not a successful replacement. Missing retained log records do
not establish non-execution. Logs contain stage/size information, not chat text.

The first build was tested on the OnePlus. An armed launch reached `HOOK_READY`
and mapped the font carrier, but emitted no `FONT_SERVED` while the user viewed
stock emoji in Clan Chat. Read-only inspection found two copies of libandroid:
the original copy's asset-open instructions were unchanged, while the copy
linked by the module contained Dobby's branch. Build 2 addresses this provider
selection error. On 2026-10-29 the user reported that it worked, confirming the
requested sent-chat emoji replacement. Read-only inspection verified installed
version `redirect2` / code 2. No retained tag logs were available for that
successful launch; do not describe `FONT_SERVED` as independently captured.

Build 3 has not been installed by the builder. Its deferred Android-loader path
needs a fresh device trial. A loader or memory-file denial fails normally before
font hooking; no permissions or SELinux rules are changed to work around it.

Verify the font source and sent-message appearance independently in further
trials. Before build 2, the user saw iOS emoji in the input bar but stock emoji
after sending; input-field appearance alone is not acceptance. Build 2 has one
user-confirmed successful trial. Repeated launches, reboot behavior, and other
devices/runtime versions have not been validated. The one-shot marker is still
consumed per attempt; a later cold launch needs explicit re-arming. Historical Samsung behavior is an
uncaptured, possibly older reference, not proof about this game version.

This adds a detectable runtime hook. Passing the earlier observe-only control
does not establish hook compatibility. If startup fails, stop; do not hide the
hook or bypass checks. Disable/remove only this prototype and reboot to unload
it fully. Game data does not need to be reset. The production emoji module and
Discord add-on are independent. Do not publish this diagnostic as a release asset.
