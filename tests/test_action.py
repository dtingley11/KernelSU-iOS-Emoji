"""Exercise manual refresh without Android commands, real mounts, or app data."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.stage = Path(self.temp.name)
        self.calls = self.stage / "calls"
        self.env = dict(os.environ, STAGE=str(self.stage), CALLS=str(self.calls),
                        BOOT="1", SDK="36", CACHE_SUPPORT="1", ACTION_BUSY="0",
                        SERVICE_RESULT="0", DIAG_RESULT="0", FAIL_STOP="", FAIL_CACHE="",
                        INSTALLED="com.android.chrome com.google.android.googlequicksearchbox "
                                  "com.google.android.inputmethod.latin com.google.android.gms "
                                  "com.discord com.supercell.clashofclans")
        (self.stage / "action.sh").write_bytes((ROOT / "action.sh").read_bytes())
        (self.stage / "common.sh").write_text((ROOT / "common.sh").read_text() + r'''
getprop() {
    case "$1" in
        sys.boot_completed) echo "$BOOT" ;;
        ro.build.version.sdk) echo "$SDK" ;;
        *) return 95 ;;
    esac
}
mkdir() {
    [ "$ACTION_BUSY" = 0 ] || return 1
    command mkdir "$STAGE/action.lock"
}
rmdir() { command rmdir "$STAGE/action.lock"; }
pm() {
    case "$1" in
        help)
            if [ "$CACHE_SUPPORT" = 1 ]; then
                echo 'clear [--user USER_ID] [--cache-only] PACKAGE'
            else
                echo 'clear [--user USER_ID] PACKAGE'
            fi
            ;;
        path)
            [ "$#" = 4 ] && [ "$2" = --user ] && [ "$3" = 0 ] || exit 95
            case " $INSTALLED " in
                *" $4 "*) echo 'package:/example/base.apk' ;;
                *) return 1 ;;
            esac
            ;;
        clear)
            # Reject every call that could mean full application-data clearing.
            [ "$#" = 5 ] && [ "$2" = --user ] && [ "$3" = 0 ] &&
                [ "$4" = --cache-only ] || exit 95
            echo "CACHE:$5" >> "$CALLS"
            [ "$FAIL_CACHE" != "$5" ] || return 1
            echo Success
            ;;
        *) exit 95 ;;
    esac
}
am() {
    [ "$#" = 4 ] && [ "$1" = force-stop ] && [ "$2" = --user ] &&
        [ "$3" = 0 ] || exit 95
    echo "STOP:$4" >> "$CALLS"
    [ "$FAIL_STOP" != "$4" ]
}
''')
        (self.stage / "service.sh").write_text('echo MOUNTS >> "$CALLS"\nprintf "%s" "$1" > "$STAGE/service-mode"\nexit "$SERVICE_RESULT"\n')
        (self.stage / "diagnose.sh").write_text('echo DIAGNOSTICS >> "$CALLS"\nexit "$DIAG_RESULT"\n')

    def run_action(self):
        result = subprocess.run(["sh", str(self.stage / "action.sh")], env=self.env,
                                text=True, capture_output=True, timeout=5)
        calls = self.calls.read_text().splitlines() if self.calls.exists() else []
        return result, calls

    def test_refresh_stops_and_clears_only_supported_installed_apps(self):
        result, calls = self.run_action()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls[0], "MOUNTS")
        self.assertEqual(calls[-1], "DIAGNOSTICS")
        self.assertEqual((self.stage / "service-mode").read_text(), "--manual")
        for app in ("com.android.chrome", "com.google.android.googlequicksearchbox",
                    "com.google.android.inputmethod.latin"):
            self.assertIn("STOP:" + app, calls)
            self.assertIn("CACHE:" + app, calls)
            self.assertLess(calls.index("STOP:" + app), calls.index("CACHE:" + app))
        for app in ("com.google.android.gms", "com.discord", "com.supercell.clashofclans"):
            self.assertNotIn("STOP:" + app, calls)
            self.assertNotIn("CACHE:" + app, calls)
        self.assertEqual(result.stdout.splitlines(), ["Refreshing emoji...",
                         "Done. Reopen your apps to see the updated emoji."])
        self.assertEqual((self.stage / "action.log").stat().st_mode & 0o777, 0o600)
        self.assertNotIn("com.android.chrome", result.stdout)
        self.assertFalse((self.stage / "action.lock").exists())

    def test_older_android_still_stops_apps_without_any_cache_clear(self):
        self.env["SDK"] = "32"
        result, calls = self.run_action()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STOP:com.android.chrome", calls)
        self.assertFalse(any(call.startswith("CACHE:") for call in calls))
        self.assertIn("Cache clearing is unavailable", result.stdout)

    def test_unadvertised_cache_flag_never_falls_back_to_data_clear(self):
        self.env["CACHE_SUPPORT"] = "0"
        result, calls = self.run_action()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STOP:com.google.android.googlequicksearchbox", calls)
        self.assertFalse(any(call.startswith("CACHE:") for call in calls))

    def test_invalid_sdk_skips_cache_clear(self):
        self.env["SDK"] = "unknown"
        result, calls = self.run_action()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(call.startswith("CACHE:") for call in calls))

    def test_cache_error_is_reported_without_data_clear_retry(self):
        self.env["FAIL_CACHE"] = "com.android.chrome"
        result, calls = self.run_action()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(calls.count("CACHE:com.android.chrome"), 1)
        self.assertIn("CACHE:com.google.android.googlequicksearchbox", calls)
        self.assertIn("DIAGNOSTICS", calls)
        self.assertIn("Refresh incomplete", result.stdout)
        self.assertNotIn("Done.", result.stdout)

    def test_stop_failure_skips_that_apps_cache(self):
        self.env["FAIL_STOP"] = "com.android.chrome"
        result, calls = self.run_action()
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("CACHE:com.android.chrome", calls)
        self.assertIn("CACHE:com.google.android.googlequicksearchbox", calls)
        self.assertIn("DIAGNOSTICS", calls)

    def test_font_refresh_failure_leaves_all_apps_running_and_caches_untouched(self):
        self.env["SERVICE_RESULT"] = "1"
        result, calls = self.run_action()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(calls, ["MOUNTS"])
        self.assertIn("Refresh incomplete", result.stdout)
        self.assertFalse((self.stage / "action.lock").exists())

    def test_missing_apps_are_skipped(self):
        self.env["INSTALLED"] = ""
        result, calls = self.run_action()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["MOUNTS", "DIAGNOSTICS"])

    def test_original_keyboards_and_facebook_targets_remain_supported(self):
        self.env["INSTALLED"] = "com.samsung.android.honeyboard com.sec.android.inputmethod " \
                                "com.facebook.orca com.facebook.katana com.facebook.lite " \
                                "com.facebook.mlite com.brave.browser org.mozilla.firefox"
        result, calls = self.run_action()
        self.assertEqual(result.returncode, 0, result.stderr)
        for app in self.env["INSTALLED"].split():
            self.assertIn("STOP:" + app, calls)
            self.assertIn("CACHE:" + app, calls)

    def test_action_refuses_to_run_before_boot(self):
        self.env["BOOT"] = "0"
        result, calls = self.run_action()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(calls, [])
        self.assertIn("finish booting", result.stdout)
        self.assertFalse((self.stage / "action.log").exists())

    def test_concurrent_action_leaves_apps_and_existing_lock_untouched(self):
        self.env["ACTION_BUSY"] = "1"
        (self.stage / "action.lock").mkdir()
        result, calls = self.run_action()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(calls, [])
        self.assertIn("already running", result.stdout)
        self.assertTrue((self.stage / "action.lock").is_dir())

    def test_diagnostic_failure_is_not_reported_as_success(self):
        self.env["DIAG_RESULT"] = "1"
        result, calls = self.run_action()
        self.assertEqual(result.returncode, 1)
        self.assertIn("DIAGNOSTICS", calls)
        self.assertIn("Refresh incomplete", result.stdout)


if __name__ == "__main__":
    unittest.main()
