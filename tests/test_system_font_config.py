from pathlib import Path
import os
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class SystemFontConfigTest(unittest.TestCase):
    def rewrite(self, value):
        return subprocess.run(["sh", "-c", '. "$REPO/common.sh"; rewrite_emoji_font_config'],
                              input=value, text=True, env=dict(os.environ, REPO=str(ROOT)),
                              check=True, capture_output=True).stdout

    def test_changes_only_main_emoji_lookup_key_and_keeps_standard_filename(self):
        before = '''<familyset version="23">
          <family name="sans-serif"><font weight="400">Roboto-Regular.ttf</font></family>
          <family lang="und-Zsye" variant="elegant">
            <font weight="400" style="normal" postScriptName="NotoColorEmoji">NotoColorEmoji.ttf</font>
            <font weight="400">NotoColorEmojiLegacy.ttf</font>
            <font weight="400">NotoColorEmojiFlags.ttf</font>
          </family>
          <family><font>CustomNotoColorEmoji.ttf</font></family>
          <alias name="sans" to="sans-serif"/>
        </familyset>'''
        expected = ET.fromstring(before)
        emoji = expected.find("./family[@lang='und-Zsye']/font")
        emoji.set("postScriptName", "iOSColorEmoji")
        self.assertEqual(ET.tostring(ET.fromstring(self.rewrite(before))), ET.tostring(expected))

    def test_multiline_text_and_single_quoted_explicit_key(self):
        before = "<familyset><family><font postScriptName = 'NotoColorEmoji'>\nNotoColorEmoji.ttf\n</font></family></familyset>"
        font = ET.fromstring(self.rewrite(before)).find("./family/font")
        self.assertEqual(font.text.strip(), "NotoColorEmoji.ttf")
        self.assertEqual(font.get("postScriptName"), "iOSColorEmoji")

    def test_existing_alias_is_idempotent(self):
        value = '<familyset><family><font postScriptName="iOSColorEmoji">NotoColorEmoji.ttf</font></family></familyset>'
        self.assertEqual(self.rewrite(self.rewrite(value)), value)

    def test_preparation_preserves_stock_files_and_uses_existing_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            stock = stage / "stock"
            (stock / "etc").mkdir(parents=True)
            module = stage / "module"
            (module / "system/fonts").mkdir(parents=True)
            canonical = module / "system/fonts/NotoColorEmoji.ttf"
            canonical.write_bytes(b"canonical-font-with-preserved-family")
            xml = '<familyset><family lang="und-Zsye"><font weight="400">NotoColorEmoji.ttf</font></family></familyset>\n'
            for name in ("fonts.xml", "font_fallback.xml"):
                (stock / "etc" / name).write_text(xml)
            env = dict(os.environ, REPO=str(ROOT), MODDIR=str(module), STOCK=str(stock))
            subprocess.run(["sh", "-c", '''
                . "$REPO/common.sh"
                prepare_system_emoji_config "$STOCK"
                prepare_system_emoji_config "$STOCK"
            '''], env=env, check=True, capture_output=True)
            for name in ("fonts.xml", "font_fallback.xml"):
                self.assertEqual((stock / "etc" / name).read_text(), xml)
                font = ET.parse(module / "system/etc" / name).find("./family/font")
                self.assertEqual(font.text, "NotoColorEmoji.ttf")
                self.assertEqual(font.get("postScriptName"), "iOSColorEmoji")
                self.assertEqual(font.get("weight"), "400")
            alias = module / "system/fonts/iOSColorEmoji.ttf"
            self.assertFalse(alias.exists())
            self.assertEqual(canonical.read_bytes(), b"canonical-font-with-preserved-family")

    def test_missing_or_unrelated_configuration_leaves_existing_install_usable(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            (stage / "stock/etc").mkdir(parents=True)
            (stage / "module/system/fonts").mkdir(parents=True)
            text = '<familyset><family><font>Roboto-Regular.ttf</font><font>CustomNotoColorEmoji.ttf</font></family></familyset>'
            (stage / "stock/etc/fonts.xml").write_text(text)
            env = dict(os.environ, REPO=str(ROOT), MODDIR=str(stage / "module"), STOCK=str(stage / "stock"))
            subprocess.run(["sh", "-c", '. "$REPO/common.sh"; prepare_system_emoji_config "$STOCK"'],
                           env=env, check=True, capture_output=True)
            self.assertFalse((stage / "module/system/etc").exists())
            self.assertFalse((stage / "module/system/fonts/iOSColorEmoji.ttf").exists())
            self.assertEqual((stage / "stock/etc/fonts.xml").read_text(), text)


if __name__ == "__main__":
    unittest.main()
