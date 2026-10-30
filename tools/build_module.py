"""Build a root-layout, uncompressed module archive."""

from pathlib import Path
from hashlib import sha256
import importlib.util
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "META-INF/com/google/android/update-binary",
    "META-INF/com/google/android/updater-script",
    "module.prop",
    "config.sh",
    "customize.sh",
    "common.sh",
    "post-fs-data.sh",
    "service.sh",
    "action.sh",
    "clash.sh",
    "diagnose.sh",
    "README.md",
    "docs/clash-prerelease.md",
    "system/fonts/NotoColorEmoji.ttf",
)


def build():
    props = dict(
        line.split("=", 1)
        for line in (ROOT / "module.prop").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    version = props["version"]
    font = ROOT / "system/fonts/NotoColorEmoji.ttf"
    if not font.is_file() or font.stat().st_size == 0:
        raise ValueError("Font file is missing or empty")
    metadata = ("\n".join(f"{key}={value}" for key, value in props.items()) + "\n").encode()
    if any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for char in version):
        raise ValueError("Unsafe module version")
    for name in FILES:
        if not (ROOT / name).is_file():
            raise FileNotFoundError(name)
    spec = importlib.util.spec_from_file_location("clash_native_builder", ROOT / "tools/build_clash_zygisk_font.py")
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    payloads = native.build(integrated=True)
    checksums = "".join(f"{sha256(path.read_bytes()).hexdigest()}  {name}\n"
                        for name, path in payloads.items() if name.endswith((".so", ".apk")))
    output = ROOT / "build" / f"KernelSU-iOS-Emoji-{version}.zip"
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in FILES:
            if name == "module.prop":
                archive.writestr(name, metadata)
            elif name == "system/fonts/NotoColorEmoji.ttf":
                archive.write(font, name)
            else:
                archive.write(ROOT / name, name)
        for name, path in payloads.items():
            archive.write(path, name)
        archive.writestr("clash/payload.sha256", checksums)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("Archive CRC validation failed")
        assert all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist())
        assert archive.read("module.prop") == metadata
    return output


if __name__ == "__main__":
    print(build())
