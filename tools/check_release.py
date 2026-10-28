"""Validate distribution metadata, scope, layout, and human-readable wording."""

from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
BAD = re.compile(r"\b(?:test(?:\d+)?|experimental|unfinished|pending|todo|fixme|wip)\b", re.I)


def check_wording(name, text):
    match = BAD.search(text)
    if match:
        raise ValueError(f"Non-release wording in {name}: {match.group()}")


def check():
    props = dict(line.split("=", 1) for line in (ROOT / "module.prop").read_text().splitlines() if "=" in line)
    version = props["version"]
    module = ROOT / "build" / f"KernelSU-iOS-Emoji-{version}.zip"
    addon = ROOT / "build" / f"iOS-Emoji-Discord-{version}.apk"
    with zipfile.ZipFile(module) as archive:
        assert archive.testzip() is None
        assert "module.prop" in archive.namelist() and "system/fonts/NotoColorEmoji.ttf" in archive.namelist()
        assert all(not name.startswith(("/", "..", "KernelSU-iOS-Emoji/")) for name in archive.namelist())
        assert all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist())
        assert not any("clash" in name.lower() or name.endswith((".log", ".p12", ".password")) for name in archive.namelist())
        for name in archive.namelist():
            if not name.endswith(".ttf"):
                check_wording(name, archive.read(name).decode("utf-8"))
        font = TTFont(BytesIO(archive.read("system/fonts/NotoColorEmoji.ttf")))
        for record in font["name"].names:
            check_wording(f"font name {record.nameID}", record.toUnicode())
        assert font["name"].getDebugName(1) == "Noto Color Emoji"
        assert font["name"].getDebugName(6) == "NotoColorEmoji"
    with zipfile.ZipFile(addon) as archive:
        assert archive.testzip() is None
        coverage = json.loads(archive.read("assets/coverage.json"))
        assert coverage["version"] == version
        assert archive.read("assets/xposed_init").strip() == b"io.github.dtingley11.emojiassets.DiscordEmoji"
        images = [entry for entry in archive.infolist() if entry.filename.startswith("assets/discord/")]
        assert len(images) == coverage["replaced"] > 0
        assert all(entry.compress_type == zipfile.ZIP_STORED for entry in images)
        for name in ("assets/xposed_init", "assets/coverage.json", "assets/replacement-list.txt"):
            check_wording(name, archive.read(name).decode())
        assert not any("clash" in name.lower() or "probe" in name.lower() for name in archive.namelist())
    sdk = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Android/Sdk")))
    tools = sdk / "build-tools/36.0.0"
    badging = subprocess.check_output([str(tools / "aapt2"), "dump", "badging", str(addon)], text=True)
    check_wording("compiled Android manifest", badging)
    assert f"versionName='{version}'" in badging
    assert f"versionCode='{props['versionCode']}'" in badging
    assert "application-label:'iOS Emoji for Discord'" in badging
    manifest = subprocess.check_output([str(tools / "aapt2"), "dump", "xmltree", str(addon), "--file", "AndroidManifest.xml"], text=True)
    check_wording("compiled manifest values", manifest)
    assert "io.github.dtingley11.emojiassets" in manifest
    assert "clash" not in manifest.lower()
    cert = subprocess.check_output([str(tools / "apksigner"), "verify", "--print-certs", str(addon)], text=True)
    check_wording("APK signing certificate", cert)
    assert "CN=iOS Emoji Assets" in cert
    print(f"Verified {version}: release wording, preserved Noto family, stored root ZIP, Discord-only APK, release certificate")


if __name__ == "__main__":
    check()
