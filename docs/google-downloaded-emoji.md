# Chrome and Google in-app page emoji

On 2026-10-29, the OnePlus was back on the normal v4.2 module. Its module font,
system font, and actual Chrome system-font mappings all had SHA-256
`768692572184c04fbbb33321652144b50e02e459b05f04a9306e9efada48271b`.
Both app profiles and the default KernelSU profile had module unmounting off.

An affected Chrome renderer also mapped the downloaded Google Play services font:

```text
/data/data/com.google.android.gms/files/fonts/opentype/Noto_COLR_Emoji_Compat-400-100_0-0_0.ttf
SHA256 71ec2037f1a8c0f8654315498412fae4015f183afe0a109aafcd9f5602bc12f7
size 5,186,052 bytes
```

Chromium explicitly supports choosing a Google Play services emoji font instead
of the firmware's Noto font. See its
[implementation explanation](https://chromium.googlesource.com/chromium/src/+/ec15c753c35a00946119d41b790e1671cbbcb45d).
This accounts for pages initially showing system emoji and later showing Google's
downloaded design even though the system mount is still correct.

The original downloaded font was copied to ignored
`build/diagnostics/google-emoji-regression/` and hash-verified. A single live bind
of the module font over the canonical `/data/user/0/...` target was applied after
verifying both hashes and refusing an existing target mount. Chrome and Google
were force-stopped once without clearing data. The user reopened affected pages
and confirmed iOS emoji in both Chrome and pages inside Google. Fresh Chrome and
WebView renderer mappings hashed to the module font. No module installation,
reboot, root-profile change, service disablement, or cache deletion was performed.

The source fix adds this exact existing filename to the normal app-font pass for
each numeric Android user. It uses the existing mount deduplication and reports
mount failures. Boot behavior remains bounded, and the Action can refresh a font
downloaded after boot. There is no background watcher or recursive app-data scan.
If Google changes the filename, diagnose the new mapping before expanding the
target list. A newly downloaded font appearing after a boot refresh may require
Action, followed by manually restarting affected browsers. Website-provided emoji
images and fonts are outside this fix.

Diagnostics now include the known downloaded target, Chrome, Google app, WebView,
and their page-renderer process font mappings and relevant app profiles.

The live bind lasts until reboot. A persistent module update requires explicit
installation approval. Restoring the original v4.2 module and rebooting removes
this target from the boot behavior; the original provider font remains beneath
the bind. Do not delete Google font caches or change Google services as rollback.

## Manual refresh in v4.2.2

The user confirmed that both Chrome and Google needed to be force-stopped and
reopened before their pages adopted the replacement. The Action now stops the
known supported apps for user 0 after refreshing mounts, clears only their caches
when SDK 33+ and the package manager explicitly advertises `--cache-only`, and
writes diagnostics. Unsupported platforms still stop the apps and skip cache
clearing. It never falls back to clearing app data, and it does not clear the
Google Play services font-provider cache. This behavior runs only when the user
presses Action; the boot service and font source remain unchanged.

## Action failure and reboot follow-up in v4.2.3

The v4.2.2 Action log recorded `Failed transaction (2147483646)` for every
ActivityManager force-stop, so cache clearing was skipped. A harmless
`am get-current-user` reproduced the failure when stdout/stderr were redirected
directly into a private module log. It succeeded with `/dev/null` or pipes. The
shared Android-command wrapper now supplies `/dev/null` on stdin, captures stdout
and stderr through a pipe, writes the captured text to the log, and preserves the
command's exit status. No SELinux policy or root profile changes are needed.

The boot service finished at 14:48:54 without any app-font binds; the manual
Action at 14:49:14 bound Google, Facebook, and Messenger fonts. This is consistent
with credential-encrypted app storage being unavailable during the first pass;
the property was not recorded at that earlier instant. On file-encrypted devices
the service now waits up to 120 seconds for `sys.user.0.ce_available=true`, logs a
timeout with manual recovery guidance, then performs the known-target refresh.
Other encryption types retain the original behavior.

After a successful new user-0 Google-font bind, the boot pass stops only already
running affected Chrome variants, Brave, and Google processes once so they reload
the font. Unchanged bindings do not cause a restart. Other Android users and
unopened apps are left alone. Boot never clears caches. The manual Action uses
the `--manual` service mode and performs its own requested app/cache refresh.
