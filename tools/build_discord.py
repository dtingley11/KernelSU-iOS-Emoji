"""Build the optional Discord-only LSPosed APK with the local Android SDK."""

import argparse
import hashlib
import json
import os
import secrets
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from emoji_assets import EmojiAssets


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "integrations" / "discord"
API_SHA256 = "f48c635f1c7469fdec0e00ad2ea0b7a6b2f5b55065784a35b7ca3a84615e8e25"


def run(*args, env=None):
    subprocess.run([str(arg) for arg in args], check=True, env=env)


def build(args):
    sdk = Path(args.sdk).expanduser()
    android = sdk / "platforms" / "android-36" / "android.jar"
    build_tools = sdk / "build-tools" / "36.0.0"
    api = Path(args.xposed_api)
    if hashlib.sha256(api.read_bytes()).hexdigest() != API_SHA256:
        raise ValueError("Xposed API jar does not match the official API 82 build")
    props = dict(line.split("=", 1) for line in (ROOT / "module.prop").read_text().splitlines() if "=" in line)
    version = props["version"]
    if any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for char in version):
        raise ValueError("Unsafe module version")
    stage = ROOT / "build" / "discord"
    for directory in (stage, stage / "java", stage / "classes", stage / "dex"):
        directory.mkdir(parents=True, exist_ok=True)

    tree = ET.parse(SOURCE / "AndroidManifest.xml")
    ET.register_namespace("android", "http://schemas.android.com/apk/res/android")
    manifest = tree.getroot()
    manifest.set("{http://schemas.android.com/apk/res/android}versionName", version)
    manifest.set("{http://schemas.android.com/apk/res/android}versionCode", props["versionCode"])
    tree.write(stage / "AndroidManifest.xml", encoding="utf-8", xml_declaration=True)
    run(build_tools / "aapt2", "compile", "--dir", SOURCE / "res", "-o", stage / "resources.zip")
    run(build_tools / "aapt2", "link", "-I", android, "--manifest", stage / "AndroidManifest.xml",
        "-o", stage / "resources.apk", stage / "resources.zip")
    run("javac", "-encoding", "UTF-8", "-source", "8", "-target", "8", "-Xlint:-options",
        "-classpath", f"{android}{os.pathsep}{api}", "-d", stage / "classes",
        *sorted((SOURCE / "src").rglob("*.java")))
    run(build_tools / "d8", "--release", "--lib", android, "--classpath", api,
        "--output", stage / "dex", *sorted((stage / "classes").rglob("*.class")))

    font_path = ROOT / "system" / "fonts" / "NotoColorEmoji.ttf"
    extractor = EmojiAssets(font_path)
    requested = sorted(set(Path(args.assets).read_text().splitlines()))
    replaced, unsupported = [], []
    with zipfile.ZipFile(stage / "unsigned.apk", "w", compression=zipfile.ZIP_STORED) as output:
        with zipfile.ZipFile(stage / "resources.apk") as resources:
            for entry in resources.infolist():
                output.writestr(entry.filename, resources.read(entry))
        output.write(stage / "dex" / "classes.dex", "classes.dex")
        output.writestr("assets/xposed_init", "io.github.dtingley11.emojiassets.DiscordEmoji\n")
        for name in requested:
            result = extractor.png(name)
            if result is None:
                unsupported.append(name)
                continue
            leaf, png = result
            replaced.append(leaf)
            output.writestr("assets/discord/" + leaf, png)
        if not replaced:
            raise ValueError("No supported Discord emoji assets; check the filename list")
        output.writestr("assets/replacement-list.txt", "\n".join(replaced) + "\n")
        coverage = {"version": version, "replaced": len(replaced), "unsupported": unsupported,
                    "font_sha256": hashlib.sha256(font_path.read_bytes()).hexdigest()}
        output.writestr("assets/coverage.json", json.dumps(coverage, indent=2))
    (stage / "coverage.json").write_text(json.dumps(coverage, indent=2) + "\n")
    run(build_tools / "zipalign", "-P", "16", "-f", "4", stage / "unsigned.apk", stage / "aligned.apk")

    keystore = Path(args.keystore) if args.keystore else ROOT / ".signing" / "emoji-assets-release.p12"
    signing_env = os.environ.copy()
    if args.keystore:
        if not signing_env.get("EMOJI_ASSETS_KEYSTORE_PASSWORD"):
            raise ValueError("Set EMOJI_ASSETS_KEYSTORE_PASSWORD for the supplied keystore")
    else:
        keystore.parent.mkdir(mode=0o700, exist_ok=True)
        password_file = keystore.with_suffix(".password")
        if not password_file.exists():
            if keystore.exists():
                raise FileNotFoundError("Release keystore password file is missing")
            descriptor = os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as output:
                output.write(secrets.token_urlsafe(48) + "\n")
        signing_env["EMOJI_ASSETS_KEYSTORE_PASSWORD"] = password_file.read_text().strip()
    if not args.keystore and not keystore.exists():
        run("keytool", "-genkeypair", "-keystore", keystore, "-storetype", "PKCS12",
            "-storepass:env", "EMOJI_ASSETS_KEYSTORE_PASSWORD", "-keypass:env", "EMOJI_ASSETS_KEYSTORE_PASSWORD",
            "-alias", "emoji-assets", "-keyalg", "RSA", "-keysize", "3072", "-validity", "10000",
            "-dname", "CN=iOS Emoji Assets", env=signing_env)
        keystore.chmod(0o600)
    output = ROOT / "build" / f"iOS-Emoji-Discord-{version}.apk"
    run(build_tools / "apksigner", "sign", "--ks", keystore, "--ks-pass", "env:EMOJI_ASSETS_KEYSTORE_PASSWORD",
        "--out", output, stage / "aligned.apk", env=signing_env)
    run(build_tools / "apksigner", "verify", "--verbose", output)
    run(build_tools / "zipalign", "-c", "-P", "16", "4", output)
    print(f"Replaced {len(replaced)}/{len(requested)} emoji assets; unsupported images keep Discord originals")
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", default=str(SOURCE / "emoji-assets.txt"), help="List of Discord assets/emoji-*.png filenames")
    parser.add_argument("--sdk", default=os.environ.get("ANDROID_HOME", str(Path.home() / "Android/Sdk")))
    parser.add_argument("--xposed-api", default=str(ROOT / "build/dependencies/xposed-api-82.jar"))
    parser.add_argument("--keystore", help="Release keystore; password from EMOJI_ASSETS_KEYSTORE_PASSWORD")
    build(parser.parse_args())
