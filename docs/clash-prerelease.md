# Optional Clash support

This prerelease combines the system font and optional native Clash support in
one KernelSU ZIP. Discord remains a separate LSPosed APK. The module description
stays `iOS emojis for KernelSU/overlayfs based mounting`.

Clash is off on first installation. Press volume up within six seconds during
installation to enable it, or volume down to leave it off. A normal manager
update preserves an enabled choice unless support is unavailable. System emoji
installation continues on unsupported devices and when no volume-key input is
available.

Action waits three seconds for volume input. Volume up or no input performs the
existing emoji refresh, including guarded cache-only clearing and diagnostics.
Volume down opens Clash settings; then volume up toggles Clash, while volume
down or no input cancels. Settings changes do not clear caches, stop apps, or
restart the phone. Reboot to apply an enable/disable change completely.

When enabled, Clash support runs on every main-process launch. It no longer
consumes a one-shot marker. Its UID is obtained from the installed user-0 package
when enabled and validated again during startup. After reinstalling Clash, use
Action to disable and enable support again, then reboot, to refresh that UID.

The prerelease currently permits the tested combination of ARM64, Android 16,
and enabled ReZygisk build 552. Other phones keep the normal system font module.
Disable/remove the earlier separate Clash test module and reboot before using
the integrated feature; the installer does not disable other modules itself.
Clash must remain outside LSPosed scope. No root profiles or detector settings
are changed.

Disabled ZIPs have no active `zygisk/arm64-v8a.so`. Enabling copies only the tiny
entry into that directory and writes a private UID setting. The root companion
serves only the fixed font and hook files while that setting is enabled. The
helper, Android asset library, and font state load only in selected Clash; the
entry unloads afterward. Disabling removes the setting and active entry, with
reboot required to unload existing code. Other apps retain the default font
module's behavior.

The ZIP includes both the normal system font and an identical copy in Clash's
private asset carrier. This increases download/storage size; it does not add a
background polling service. The canonical font family is unchanged for browser
compatibility.

The standalone scoped build 3 was verified on the OnePlus, and the user confirmed
the earlier Duck finding was absent. This combined persistent variant still
needs phone verification: default-off installation, enabling/reboot, repeated
Clash cold starts, disabling/reboot, and normal browser/keyboard refresh. Host
tests and artifact checks do not establish those device outcomes. Do not rescan
Duck automatically; the user asked to stop further rescans.

Build and validate:

```sh
build/python/bin/python tools/build_module.py
build/python/bin/python tools/check_prerelease.py
build/python/bin/python -m unittest discover -s tests
```

The native build needs SDK/build-tools 36, NDK 29, CMake/Ninja, the pinned official
Zygisk v4 header, and the pinned Dobby checkout documented in the integration
README. The build neither installs the ZIP nor publishes a release. Production
`tools/check_release.py` remains a stable-release check and intentionally rejects
Clash payloads; use the prerelease checker on this branch.
