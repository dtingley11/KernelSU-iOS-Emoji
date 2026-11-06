"""Prepare font identifiers while preserving family names and glyphs."""

from pathlib import Path
from fontTools.ttLib import TTFont

FONT = Path(__file__).resolve().parents[1] / "system/fonts/NotoColorEmoji.ttf"
POSTSCRIPT_NAME = "iOSColorEmoji"


def prepare(path=FONT):
    font = TTFont(path, recalcTimestamp=False)
    protected = [(n.nameID, n.platformID, n.platEncID, n.langID, n.string)
                 for n in font["name"].names if n.nameID not in (3, 6)]
    tables = {tag: font.getTableData(tag) for tag in font.keys() if tag not in ("head", "name", "GlyphOrder")}
    changed = False
    identifiers = {3: f"Noto Color Emoji;{POSTSCRIPT_NAME};iOS-26.4", 6: POSTSCRIPT_NAME}
    # Chromium substitutes Google's downloaded emoji when the internal
    # PostScript name is NotoColorEmoji. Keep the Noto family for Gecko lookup.
    for record in list(font["name"].names):
        if record.nameID in identifiers and record.toUnicode() != identifiers[record.nameID]:
            font["name"].setName(identifiers[record.nameID], record.nameID,
                                 record.platformID, record.platEncID, record.langID)
            changed = True
    if changed:
        font.save(path, reorderTables=False)
    result = TTFont(path)
    assert protected == [(n.nameID, n.platformID, n.platEncID, n.langID, n.string)
                         for n in result["name"].names if n.nameID not in (3, 6)]
    assert all(result.getTableData(tag) == data for tag, data in tables.items())
    assert result["name"].getDebugName(6) == POSTSCRIPT_NAME
    font.close()
    result.close()
    print("Font identifiers prepared; family names and glyph tables preserved")


if __name__ == "__main__":
    prepare()
