from hashlib import sha256
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ClashControlsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.stage = Path(self.temp.name) / "module"
        (self.stage / "clash").mkdir(parents=True)
        self.modules = Path(self.temp.name) / "modules"
        (self.modules / "rezygisk").mkdir(parents=True)
        (self.modules / "rezygisk/module.prop").write_text("versionCode=552\n")
        lines = []
        for name in ("entry.so", "font-hook.so", "font-assets.apk"):
            data = name.encode()
            (self.stage / "clash" / name).write_bytes(data)
            lines.append(f"{sha256(data).hexdigest()}  clash/{name}\n")
        (self.stage / "clash/payload.sha256").write_text("".join(lines))
        self.env = dict(os.environ, REPO=str(ROOT), STAGE=str(self.stage), MODROOT=str(self.modules),
                        SDK="36", ABI="arm64-v8a", APP_UID="10474", CHOICE3="", CHOICE5="", CHOICE6="")

    def run_shell(self, script):
        return subprocess.run(["sh", "-c", r'''
            MODDIR="$STAGE"
            . "$REPO/common.sh"
            . "$REPO/clash.sh"
            CLASH_MODULES_ROOT="$MODROOT"
            getprop() {
                case "$1" in
                    ro.build.version.sdk) echo "$SDK" ;;
                    ro.product.cpu.abi) echo "$ABI" ;;
                    *) return 95 ;;
                esac
            }
            pm() {
                [ "$*" = 'list packages --user 0 -U com.supercell.clashofclans' ] || exit 95
                [ -z "$APP_UID" ] || echo "package:com.supercell.clashofclans uid:$APP_UID"
            }
            ui_print() { printf '%s\n' "$*"; }
            volume_choice() { case "$1" in 3) echo "$CHOICE3";; 5) echo "$CHOICE5";; 6) echo "$CHOICE6";; esac; }
        ''' + script], env=self.env, text=True, capture_output=True, timeout=5)

    def test_enable_then_disable_activates_only_the_entry_and_removes_state(self):
        result = self.run_shell("clash_enable")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.stage / "clash/enabled").read_text(), "10474\n")
        self.assertEqual((self.stage / "clash/enabled").stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.stage / "zygisk/arm64-v8a.so").read_bytes(), b"entry.so")
        self.assertIn("Reboot to apply", result.stdout)
        result = self.run_shell("clash_disable")
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.stage / "clash/enabled").exists())
        self.assertFalse((self.stage / "zygisk/arm64-v8a.so").exists())
        self.assertTrue((self.stage / "clash/font-assets.apk").exists())

    def test_first_install_defaults_off_without_deleting_payloads(self):
        result = self.run_shell("clash_install_choice")
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.stage / "clash/enabled").exists())
        self.assertFalse((self.stage / "zygisk").exists())

    def test_update_preserves_enabled_choice_and_refreshes_reinstalled_uid(self):
        old = self.modules / "iOS_Emoji_KSU/clash"
        old.mkdir(parents=True)
        (old / "enabled").write_text("10400\n")
        self.env["APP_UID"] = "10888"
        result = self.run_shell("clash_install_choice")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.stage / "clash/enabled").read_text(), "10888\n")

    def test_unsupported_android_or_arch_leaves_regular_install_available(self):
        for key, value in (("SDK", "29"), ("ABI", "armeabi-v7a")):
            previous = self.env[key]
            self.env[key] = value
            self.env["CHOICE6"] = "up"
            result = self.run_shell("clash_install_choice")
            self.assertEqual(result.returncode, 0)
            self.assertFalse((self.stage / "clash/enabled").exists())
            self.env[key] = previous

    def test_inactive_runtime_and_previous_test_module_cannot_enable(self):
        disabled = self.modules / "rezygisk/disable"
        disabled.touch()
        self.assertNotEqual(self.run_shell("clash_enable").returncode, 0)
        disabled.unlink()
        (self.modules / "ios_emoji_clash_zygisk_font").mkdir()
        self.assertNotEqual(self.run_shell("clash_enable").returncode, 0)
        self.assertFalse((self.stage / "zygisk").exists())

    def test_payload_tampering_prevents_activation(self):
        (self.stage / "clash/font-hook.so").write_bytes(b"changed")
        result = self.run_shell("clash_enable")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.stage / "clash/enabled").exists())

    def test_missing_or_invalid_app_uid_cannot_enable(self):
        for uid in ("", "0", "9999", "20000", "104740", "10474;false"):
            self.env["APP_UID"] = uid
            self.assertNotEqual(self.run_shell("clash_enable").returncode, 0)
        self.assertFalse((self.stage / "zygisk").exists())

    def test_action_defaults_to_refresh_and_requires_two_choices_to_enable(self):
        result = self.run_shell("clash_action_menu")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.stage / "clash/enabled").exists())
        self.env["CHOICE3"] = "down"
        self.assertEqual(self.run_shell("clash_action_menu").returncode, 0)
        self.assertFalse((self.stage / "clash/enabled").exists())
        self.env["CHOICE5"] = "up"
        self.assertEqual(self.run_shell("clash_action_menu").returncode, 0)
        self.assertTrue((self.stage / "clash/enabled").exists())
        self.assertEqual(self.run_shell("clash_action_menu").returncode, 0)
        self.assertFalse((self.stage / "clash/enabled").exists())

    def test_pending_update_blocks_settings_changes_in_current_module(self):
        active = self.modules / "iOS_Emoji_KSU"
        self.stage.rename(active)
        self.stage = active
        self.env["STAGE"] = str(active)
        (self.modules.parent / "modules_update/iOS_Emoji_KSU").mkdir(parents=True)
        result = self.run_shell("clash_enable")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pending module update", result.stdout)
        self.assertFalse((active / "zygisk").exists())

    def test_volume_parser_ignores_releases_and_expected_timeout_status(self):
        for events, expected in (("EV_KEY KEY_VOLUMEUP DOWN", "up"),
                                 ("EV_KEY KEY_VOLUMEDOWN DOWN", "down"),
                                 ("EV_KEY KEY_VOLUMEUP UP", "")):
            self.env["EVENTS"] = events
            result = self.run_shell('''
                . "$REPO/clash.sh"
                timeout() { printf '%s\\n' "$EVENTS"; return 124; }
                getevent() { :; }
                set -e
                volume_choice 1
            ''')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), expected)


class ClashActionCompatibilityTest(unittest.TestCase):
    def fixture(self, choice3="", choice5=""):
        import test_action
        fixture = test_action.ActionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        controls = (ROOT / "clash.sh").read_text()
        controls += f'\nvolume_choice() {{ case "$1" in 3) echo "{choice3}";; 5) echo "{choice5}";; esac; }}\n'
        (fixture.stage / "clash.sh").write_text(controls)
        return fixture

    def test_default_menu_still_refreshes_browsers_and_preserves_data(self):
        result, calls = self.fixture().run_action()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STOP:com.android.chrome", calls)
        self.assertIn("CACHE:com.google.android.googlequicksearchbox", calls)
        self.assertIn("DIAGNOSTICS", calls)
        self.assertNotIn("STOP:com.supercell.clashofclans", calls)

    def test_cancelled_settings_do_not_stop_apps_or_touch_caches(self):
        result, calls = self.fixture("down").run_action()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [])
        self.assertIn("Cancelled", result.stdout)


if __name__ == "__main__":
    unittest.main()
