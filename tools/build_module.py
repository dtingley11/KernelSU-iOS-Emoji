"""Build a root-layout, uncompressed module archive."""

from pathlib import Path
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
    "diagnose.sh",
    "README.md",
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
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("Archive CRC validation failed")
        assert all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist())
        assert archive.read("module.prop") == metadata
    return output


if __name__ == "__main__":
    print(build())
