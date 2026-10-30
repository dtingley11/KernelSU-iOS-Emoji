"""Build an armed, one-shot Clash font redirect for KernelSU/ReZygisk; never deploys it."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "integrations/clash-zygisk-font"
STAGE = ROOT / "build/diagnostics/clash-zygisk-font"
SDK = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Android/Sdk")))
NDK = SDK / "ndk/29.0.14206865"
TOOLS = SDK / "build-tools/36.0.0"
API = ROOT / "build/dependencies/zygisk-api-4.hpp"
API_SHA = "fc6523882c0f8659b4fcd1e04ffb07d3a948090e5a8c08817af6e2b506a078d0"
DOBBY = ROOT / "build/dependencies/dobby"
DOBBY_REV = "b0176de574104726bb68dff3b77ee666300fc338"
FONT = ROOT / "system/fonts/NotoColorEmoji.ttf"
OUTPUT = ROOT / "build/diagnostics/Clash-Zygisk-Font-Redirect-1.zip"


def run(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def validate_uid(uid):
    if not 10000 <= uid < 20000:
        raise ValueError("Expected a verified regular user-0 Clash application UID")
    return uid


def audit_carrier(path, font):
    with zipfile.ZipFile(path) as archive:
        entries = {"AndroidManifest.xml", "resources.arsc", "assets/replacement.ttf"}
        if archive.testzip() is not None or len(archive.namelist()) != len(entries) or set(archive.namelist()) != entries:
            raise ValueError("Unexpected private asset APK entries")
        if archive.getinfo("assets/replacement.ttf").compress_type != zipfile.ZIP_STORED:
            raise ValueError("Font must be stored for file-descriptor access")
        if archive.read("assets/replacement.ttf") != Path(font).read_bytes():
            raise ValueError("Carrier font differs from the module's existing font")


def build(uid):
    validate_uid(uid)
    if sha256(API.read_bytes()).hexdigest() != API_SHA:
        raise ValueError("Official Zygisk API v4 header changed")
    revision = run("git", "-C", DOBBY, "rev-parse", "HEAD", capture_output=True, text=True).stdout.strip()
    if revision != DOBBY_REV:
        raise ValueError("Dobby dependency does not match the pinned revision")
    STAGE.mkdir(parents=True, exist_ok=True)
    dobby_source = STAGE / f"dobby-source-{DOBBY_REV[:12]}"
    if not dobby_source.exists():
        with tempfile.TemporaryFile() as snapshot:
            run("git", "-C", DOBBY, "archive", DOBBY_REV, stdout=snapshot)
            snapshot.seek(0)
            with tarfile.open(fileobj=snapshot) as archive:
                archive.extractall(dobby_source, filter="data")
    dobby_build = STAGE / f"dobby-android-{DOBBY_REV[:12]}"
    run("cmake", "-S", dobby_source, "-B", dobby_build, "-G", "Ninja",
        f"-DCMAKE_TOOLCHAIN_FILE={NDK / 'build/cmake/android.toolchain.cmake'}",
        "-DANDROID_ABI=arm64-v8a", "-DANDROID_PLATFORM=android-30", "-DANDROID_STL=c++_static",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
        "-DCMAKE_POSITION_INDEPENDENT_CODE=ON", "-DDOBBY_DEBUG=OFF", "-DPlugin.SymbolResolver=OFF",
        "-DPlugin.ImportTableReplace=OFF", "-DPlugin.Android.BionicLinkerUtil=OFF",
        "-DDOBBY_BUILD_TEST=OFF", "-DDOBBY_BUILD_EXAMPLE=OFF")
    run("cmake", "--build", dobby_build, "--target", "dobby_static", "-j", "4")

    assets = STAGE / "assets"
    assets.mkdir(exist_ok=True)
    shutil.copyfile(FONT, assets / "replacement.ttf")
    manifest = STAGE / "AndroidManifest.xml"
    manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
                        'package="io.github.dtingley11.clashfontassets" android:versionCode="1" '
                        'android:versionName="1"><uses-sdk android:minSdkVersion="30" '
                        'android:targetSdkVersion="36"/><application android:hasCode="false"/></manifest>\n')
    carrier = STAGE / "font-assets.apk"
    run(TOOLS / "aapt2", "link", "-I", SDK / "platforms/android-36/android.jar",
        "--manifest", manifest, "-A", assets, "-0", "ttf", "-o", STAGE / "assets-unaligned.apk")
    run(TOOLS / "zipalign", "-P", "16", "-f", "4", STAGE / "assets-unaligned.apk", carrier)
    audit_carrier(carrier, FONT)
    if carrier.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Font carrier exceeds runtime payload limit")

    compiler = NDK / "toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android30-clang++"
    library = STAGE / "arm64-v8a.so"
    run(compiler, "-std=c++17", "-O2", "-shared", "-fPIC", "-fvisibility=hidden",
        "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics", "-static-libstdc++",
        "-Wall", "-Wextra", "-Werror", "-Wl,-z,max-page-size=16384", "-Wl,-z,relro,-z,now",
        "-Wl,--no-undefined", "-Wl,--exclude-libs,ALL", f"-DCLASH_FONT_UID={uid}",
        f"-DCLASH_FONT_BYTES={FONT.stat().st_size}LL", f"-DCLASH_APK_BYTES={carrier.stat().st_size}ULL",
        "-I", API.parent, "-I", dobby_source / "include", SOURCE / "module.cpp",
        SOURCE / "font_redirect.cpp", dobby_build / "libdobby.a", "-landroid", "-llog", "-ldl", "-o", library)
    readelf = NDK / "toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"
    elf = run(readelf, "-l", "-d", "--dyn-syms", library, capture_output=True, text=True).stdout
    if "libc++_shared.so" in elf or "zygisk_module_entry" not in elf or "zygisk_companion_entry" not in elf:
        raise ValueError("Unexpected native library dependencies or entry points")
    for line in elf.splitlines():
        if line.strip().startswith("LOAD") and int(line.split()[-1], 16) < 16384:
            raise ValueError("Native library is not aligned for 16 KB pages")
    installer = (SOURCE / "customize.sh").read_text().replace("@CLASH_UID@", str(uid))
    installer = installer.replace("@PAYLOAD_SHA@", sha256(carrier.read_bytes()).hexdigest())
    if "@" in installer:
        raise ValueError("Unresolved installer template")
    run("sh", "-n", input=installer, text=True)
    metadata = {"mode": "native-exact-font-redirect-one-shot", "target_package": "com.supercell.clashofclans",
                "target_uid": uid, "android_sdk": 36, "rezygisk_build": 552, "zygisk_api": 4,
                "api_sha256": API_SHA, "dobby_revision": DOBBY_REV,
                "font_sha256": sha256(FONT.read_bytes()).hexdigest(), "font_bytes": FONT.stat().st_size,
                "carrier_sha256": sha256(carrier.read_bytes()).hexdigest(),
                "library_sha256": sha256(library.read_bytes()).hexdigest(),
                "notice": "Private prototype; not deployed or verified in Clash."}
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in ("module.prop", "README.md"):
            archive.write(SOURCE / name, name)
        archive.writestr("customize.sh", installer)
        archive.writestr("skip_mount", b"")
        archive.writestr("prototype.json", json.dumps(metadata, indent=2) + "\n")
        archive.writestr("LICENSE.zygisk.txt", API.read_text().split("#pragma once", 1)[0])
        archive.write(dobby_source / "LICENSE", "LICENSE.dobby.txt")
        archive.write(carrier, "font-assets.apk")
        archive.write(library, "zygisk/arm64-v8a.so")
    with zipfile.ZipFile(OUTPUT) as archive:
        expected_entries = {"module.prop", "README.md", "customize.sh", "skip_mount", "prototype.json",
                            "LICENSE.zygisk.txt", "LICENSE.dobby.txt", "font-assets.apk", "zygisk/arm64-v8a.so"}
        if set(archive.namelist()) != expected_entries or archive.testzip() is not None:
            raise ValueError("Unexpected prototype ZIP layout")
        if any(item.compress_type != zipfile.ZIP_STORED for item in archive.infolist()):
            raise ValueError("Prototype module ZIP must be stored")
    print(OUTPUT)
    print("SHA256", sha256(OUTPUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uid", required=True, type=int)
    build(parser.parse_args().uid)
