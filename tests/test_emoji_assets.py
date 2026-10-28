from io import BytesIO
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
try:
    from emoji_assets import EmojiAssets
    from PIL import Image
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, "Run with build/python/bin/python for asset-generation tests")
class AssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.extractor = EmojiAssets(ROOT / "system/fonts/NotoColorEmoji.ttf")

    def test_face_is_a_valid_color_png(self):
        name, data = self.extractor.png("assets/emoji-1f600.png")
        self.assertEqual(name, "emoji-1f600.png")
        with Image.open(BytesIO(data)) as image:
            self.assertGreater(image.width, 16)
            self.assertGreater(image.height, 16)
            self.assertIn(image.mode, ("RGBA", "RGB", "P"))

    def test_skin_tone_sequence_shapes_as_one_emoji(self):
        self.assertIsNotNone(self.extractor.png("emoji-1f44d-1f3fd.png"))

    def test_zwj_family_shapes_as_one_emoji(self):
        self.assertIsNotNone(self.extractor.png("emoji-1f468-200d-1f469-200d-1f467.png"))

    def test_multiple_uncombined_faces_are_not_replaced_with_a_single_face(self):
        self.assertIsNone(self.extractor.png("emoji-1f600-1f603.png"))

    def test_unrecognized_paths_and_invalid_codepoints_fall_back(self):
        for name in ("../emoji-1f600.png", "assets/photo.png", "emoji-110000.png", "emoji-d800.png"):
            with self.subTest(asset=name):
                self.assertIsNone(self.extractor.png(name))


if __name__ == "__main__":
    unittest.main()
