"""Preserve browser family lookup and glyph data when preparing identifiers."""
from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from prepare_release_font import prepare


class FontMetadataTest(unittest.TestCase):
    def test_browser_font_identity(self):
        with TTFont(ROOT / "system/fonts/NotoColorEmoji.ttf") as font:
            for name_id in (1, 4, 16):
                self.assertEqual(font["name"].getDebugName(name_id), "Noto Color Emoji")
            self.assertEqual(font["name"].getDebugName(6), "iOSColorEmoji")

    def test_legacy_identifier_migration_preserves_names_and_glyphs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "font.ttf"
            with TTFont(ROOT / "system/fonts/NotoColorEmoji.ttf", recalcTimestamp=False) as font:
                for record in list(font["name"].names):
                    if record.nameID in (3, 6):
                        value = "NotoColorEmoji" if record.nameID == 6 else "legacy-build"
                        font["name"].setName(value, record.nameID,
                                             record.platformID, record.platEncID, record.langID)
                font.save(path, reorderTables=False)
            with TTFont(path) as before:
                tables = {tag: before.getTableData(tag) for tag in before.keys()
                          if tag not in ("GlyphOrder", "head", "name")}
                names = [(n.nameID, n.platformID, n.platEncID, n.langID, n.string)
                         for n in before["name"].names if n.nameID not in (3, 6)]
            prepare(path)
            with TTFont(path) as after:
                self.assertEqual(names, [(n.nameID, n.platformID, n.platEncID, n.langID, n.string)
                                        for n in after["name"].names if n.nameID not in (3, 6)])
                self.assertEqual(tables, {tag: after.getTableData(tag) for tag in tables})
                self.assertEqual(after["name"].getDebugName(6), "iOSColorEmoji")
            digest = sha256(path.read_bytes()).hexdigest()
            prepare(path)
            self.assertEqual(sha256(path.read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
