"""Host regression tests; no real mounts or Android app data are modified."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MountTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.font = self.directory / "font.ttf"
        self.font.write_bytes(b"test-font")
        self.target = self.directory / "target.ttf"
        self.target.write_bytes(b"original-font")

    def run_mount(self, script):
        env = dict(os.environ, MODULE=str(ROOT), FONT=str(self.font), TARGET=str(self.target))
        return subprocess.run(
            ["sh", "-c", '. "$MODULE/common.sh"; FONT_FILE="$FONT"; ' + script],
            env=env, text=True, capture_output=True, check=False,
        )

    def test_existing_binding_is_not_stacked(self):
        result = self.run_mount('''
            count=0
            mount() { count=$((count + 1)); rm "$4"; ln "$3" "$4"; }
            mount_font "$TARGET"
            mount_font "$TARGET"
            [ "$count" -eq 1 ]
        ''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Already bound", result.stdout)
        self.assertTrue(os.path.samefile(self.font, self.target))

    def test_missing_target_is_not_created(self):
        self.target.unlink()
        result = self.run_mount('mount() { exit 95; }; mount_font "$TARGET"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.target.exists())

    def test_missing_source_does_not_touch_target(self):
        self.font.unlink()
        result = self.run_mount('mount() { exit 95; }; mount_font "$TARGET"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), b"original-font")

    def test_configured_missing_font_is_prepared_as_relative_alias(self):
        fontdir = self.directory / "system" / "fonts"
        fontdir.mkdir(parents=True)
        (fontdir / "NotoColorEmoji.ttf").write_bytes(b"module-font")
        env = dict(os.environ, MODULE=str(ROOT), STAGE=str(self.directory))
        result = subprocess.run(["sh", "-c", '''
            MODDIR="$STAGE"
            . "$MODULE/common.sh"
            SYSTEM_FONT_ALIASES="NotoColorEmojiLegacy.ttf"
            grep() { return 0; }
            prepare_font_aliases
            prepare_font_aliases
        '''], env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        alias = fontdir / "NotoColorEmojiLegacy.ttf"
        self.assertEqual(os.readlink(alias), "NotoColorEmoji.ttf")
        self.assertEqual(alias.read_bytes(), b"module-font")

    def test_unconfigured_missing_font_is_not_created(self):
        fontdir = self.directory / "system" / "fonts"
        fontdir.mkdir(parents=True)
        env = dict(os.environ, MODULE=str(ROOT), STAGE=str(self.directory))
        result = subprocess.run(["sh", "-c", '''
            MODDIR="$STAGE"
            . "$MODULE/common.sh"
            SYSTEM_FONT_ALIASES="NotARealEmojiFont.ttf"
            grep() { return 1; }
            prepare_font_aliases
        '''], env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((fontdir / "NotARealEmojiFont.ttf").exists())

    def test_mount_failure_is_reported_without_changing_permissions(self):
        self.target.chmod(0o600)
        result = self.run_mount('mount() { return 1; }; mount_font "$TARGET"')
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR", result.stdout)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.target.read_bytes(), b"original-font")

    def test_keyboard_action_refuses_to_run_before_boot(self):
        with tempfile.TemporaryDirectory() as stage:
            stage = Path(stage)
            (stage / "action.sh").write_bytes((ROOT / "action.sh").read_bytes())
            (stage / "common.sh").write_text('getprop() { echo 0; }\n')
            result = subprocess.run(["sh", str(stage / "action.sh")], text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("finish booting", result.stdout)

    def run_service(self, overrides):
        with tempfile.TemporaryDirectory() as stage:
            stage = Path(stage)
            (stage / "service.sh").write_bytes((ROOT / "service.sh").read_bytes())
            (stage / "common.sh").write_text('''
                log() { echo "$*"; }
                start_service_log() { :; }
                mkdir() { return 0; }
                rmdir() { echo lock-released; }
                sleep() { :; }
                mount_oem_fonts() { echo MOUNT-OEM; }
                mount_app_fonts() { echo MOUNT-APPS; }
                find() { echo FORBIDDEN-FIND; exit 95; }
                pm() { echo FORBIDDEN-PM; exit 95; }
                rm() { echo FORBIDDEN-RM; exit 95; }
            ''' + overrides)
            return subprocess.run(["sh", str(stage / "service.sh")], text=True, capture_output=True, timeout=5)

    def test_service_boot_wait_is_bounded(self):
        result = self.run_service('getprop() { echo 0; }\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("timed out", result.stdout)
        self.assertIn("lock-released", result.stdout)
        self.assertNotIn("MOUNT-", result.stdout)
        self.assertNotIn("FORBIDDEN", result.stdout)

    def test_service_lock_prevents_concurrent_run(self):
        result = self.run_service('mkdir() { return 1; }; getprop() { exit 95; }\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_service_mounts_known_targets_after_boot(self):
        result = self.run_service('getprop() { echo 1; }; FONT_FILE="$0"\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MOUNT-OEM", result.stdout)
        self.assertIn("MOUNT-APPS", result.stdout)
        self.assertNotIn("FORBIDDEN", result.stdout)

    def test_service_reports_mount_failures_to_action(self):
        result = self.run_service('getprop() { echo 1; }; FONT_FILE="$0"; mount_app_fonts() { return 1; }\n')
        self.assertEqual(result.returncode, 1)
        self.assertIn("One or more font mounts failed", result.stdout)
        self.assertNotIn("Service completed", result.stdout)

    def test_all_shell_scripts_parse(self):
        for name in ("common.sh", "customize.sh", "post-fs-data.sh", "service.sh", "action.sh", "diagnose.sh", "config.sh"):
            with self.subTest(script=name):
                result = subprocess.run(["sh", "-n", str(ROOT / name)], text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
