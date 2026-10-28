"""Clean the internal build identifier while preserving family names and glyphs."""

from pathlib import Path
from fontTools.ttLib import TTFont

FONT = Path(__file__).resolve().parents[1] / "system/fonts/NotoColorEmoji.ttf"


def prepare():
    font = TTFont(FONT, recalcTimestamp=False)
    protected = [(n.nameID, n.platformID, n.platEncID, n.langID, n.string)
                 for n in font["name"].names if n.nameID != 3]
    tables = {tag: font.getTableData(tag) for tag in font.keys() if tag not in ("head", "name", "GlyphOrder")}
    changed = False
    for record in list(font["name"].names):
        if record.nameID == 3 and record.toUnicode() != "Noto Color Emoji;NotoColorEmoji;iOS-26.4":
            font["name"].setName("Noto Color Emoji;NotoColorEmoji;iOS-26.4", 3,
                                 record.platformID, record.platEncID, record.langID)
            changed = True
    if changed:
        font.save(FONT)
    result = TTFont(FONT)
    assert protected == [(n.nameID, n.platformID, n.platEncID, n.langID, n.string)
                         for n in result["name"].names if n.nameID != 3]
    assert all(result.getTableData(tag) == data for tag, data in tables.items())
    print("Font identifier cleaned; family names and glyph tables preserved")


if __name__ == "__main__":
    prepare()
