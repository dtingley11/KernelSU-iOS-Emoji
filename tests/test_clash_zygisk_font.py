import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "integrations/clash-zygisk-font"
FIXTURES = ROOT / "tests/clash_zygisk"
SPEC = importlib.util.spec_from_file_location("zygisk_font_builder", ROOT / "tools/build_clash_zygisk_font.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class ClashZygiskFontTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("c++"), "Host C++ compiler required")
    def test_scope_protocol_and_one_shot(self):
        self.compile_and_run("core_test.cpp")

    @unittest.skipUnless(shutil.which("c++"), "Host C++ compiler required")
    def test_exact_asset_routing_and_fallback(self):
        self.compile_and_run("routing_test.cpp", SOURCE / "font_redirect.cpp")

    @unittest.skipUnless(shutil.which("c++"), "Host C++ compiler required")
    def test_duplicate_library_provider_selection(self):
        self.compile_and_run("library_maps_test.cpp")

    @unittest.skipUnless(shutil.which("c++"), "Host C++ compiler required")
    def test_entry_loads_helper_only_in_armed_clash(self):
        self.compile_and_run("entry_test.cpp")

    def test_entry_elf_audit_rejects_initializers_and_dependencies(self):
        report = "Shared library: [libc.so]\nShared library: [libdl.so]\nzygisk_module_entry\nzygisk_companion_entry"
        BUILDER.audit_entry_elf(report)
        for extra in ("Shared library: [libandroid.so]", "Shared library: [libc++_shared.so]",
                      "__cxa_atexit", "__cxa_finalize", "INIT_ARRAY", "FINI_ARRAY",
                      "_GLOBAL__sub_I_RoutingPlugin.cc", "DobbyHook", "AAssetManager_open"):
            with self.assertRaises(ValueError):
                BUILDER.audit_entry_elf(report + "\n" + extra)

    def compile_and_run(self, fixture, *sources):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "test"
            subprocess.run(["c++", "-std=c++17", "-pthread", "-Wall", "-Wextra", "-Werror",
                            "-I", str(SOURCE), "-I", str(FIXTURES / "include"),
                            str(FIXTURES / fixture), *map(str, sources), "-o", str(output)], check=True)
            subprocess.run([str(output)], check=True, timeout=10)

    def test_invalid_uids(self):
        for uid in (0, 9999, 20000, 104740):
            with self.assertRaises(ValueError):
                BUILDER.validate_uid(uid)
        self.assertEqual(BUILDER.validate_uid(10474), 10474)

    def test_carrier_rejects_changed_font_compression_and_extra_files(self):
        with tempfile.TemporaryDirectory() as directory:
            font = Path(directory) / "font.ttf"
            font.write_bytes(b"font")
            carrier = Path(directory) / "assets.apk"
            for data, compression, extra, valid in (
                (b"font", zipfile.ZIP_STORED, False, True),
                (b"oops", zipfile.ZIP_STORED, False, False),
                (b"font", zipfile.ZIP_DEFLATED, False, False),
                (b"font", zipfile.ZIP_STORED, True, False),
            ):
                with zipfile.ZipFile(carrier, "w") as archive:
                    archive.writestr("AndroidManifest.xml", b"manifest")
                    archive.writestr("resources.arsc", b"table")
                    archive.writestr("assets/replacement.ttf", data, compress_type=compression)
                    if extra:
                        archive.writestr("classes.dex", b"unexpected")
                if valid:
                    BUILDER.audit_carrier(carrier, font)
                else:
                    with self.assertRaises(ValueError):
                        BUILDER.audit_carrier(carrier, font)

    def test_installer_shell_syntax(self):
        installer = (SOURCE / "customize.sh").read_text()
        installer = installer.replace("@CLASH_UID@", "10474").replace("@PAYLOAD_SHA@", "0" * 64).replace("@HOOK_SHA@", "0" * 64)
        self.assertNotIn("@", installer)
        subprocess.run(["sh", "-n"], input=installer, text=True, check=True)


if __name__ == "__main__":
    unittest.main()
