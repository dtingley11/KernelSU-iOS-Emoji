"""Validate the combined font/Clash prerelease without installing it."""
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

from fontTools.ttLib import TTFont
from build_clash_zygisk_font import audit_carrier, audit_entry_elf, NDK

ROOT = Path(__file__).resolve().parents[1]


def check(path=None):
    props = dict(line.split("=", 1) for line in (ROOT / "module.prop").read_text().splitlines() if "=" in line)
    path = Path(path) if path else ROOT / "build" / f"KernelSU-iOS-Emoji-{props['version']}.zip"
    assert "-pre" in props["version"]
    assert props["description"] == "iOS emojis for KernelSU/overlayfs based mounting"
    with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory() as directory:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist())
        assert all(not name.startswith(("/", "..")) for name in names)
        assert not any(name.startswith("zygisk/") or name.endswith(("/enabled", ".p12", ".password", ".log")) for name in names)
        assert not any("discord" in name.lower() or "lsposed" in name.lower() for name in names)
        assert {"module.prop", "customize.sh", "action.sh", "clash.sh", "system/fonts/NotoColorEmoji.ttf",
                "clash/entry.so", "clash/font-hook.so", "clash/font-assets.apk", "clash/payload.sha256",
                "clash/build.json"} <= set(names)
        assert archive.read("module.prop") == (ROOT / "module.prop").read_bytes()
        font_bytes = archive.read("system/fonts/NotoColorEmoji.ttf")
        assert font_bytes == (ROOT / "system/fonts/NotoColorEmoji.ttf").read_bytes()
        font = TTFont(BytesIO(font_bytes))
        assert font["name"].getDebugName(1) == "Noto Color Emoji"
        metadata = json.loads(archive.read("clash/build.json"))
        assert metadata["mode"] == "persistent-opt-in"
        assert metadata["font_sha256"] == sha256(font_bytes).hexdigest()
        checksums = archive.read("clash/payload.sha256").decode().splitlines()
        assert len(checksums) == 3
        for line in checksums:
            digest, name = line.split("  ", 1)
            assert sha256(archive.read(name)).hexdigest() == digest
        stage = Path(directory)
        for name in ("clash/entry.so", "clash/font-hook.so", "clash/font-assets.apk"):
            destination = stage / Path(name).name
            destination.write_bytes(archive.read(name))
        font_path = stage / "font.ttf"
        font_path.write_bytes(font_bytes)
        audit_carrier(stage / "font-assets.apk", font_path)
        report = subprocess.check_output([str(NDK / "toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"),
                                          "--wide", "-l", "-d", "--symbols", str(stage / "entry.so")], text=True)
        audit_entry_elf(report)
        for name in names:
            if name.endswith(".sh"):
                subprocess.run(["sh", "-n"], input=archive.read(name), check=True)
    print(f"Verified {path.name}: default-off Clash, preserved font, payload hashes, minimal entry, separate Discord")


if __name__ == "__main__":
    check()
