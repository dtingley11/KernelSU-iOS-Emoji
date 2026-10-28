"""Extract existing color glyph PNGs using HarfBuzz for sequence shaping."""

from io import BytesIO
from pathlib import Path
import re

from fontTools.ttLib import TTFont
from PIL import Image
import uharfbuzz as hb


NAME = re.compile(r"(?:assets/)?(emoji-([0-9a-f]+(?:-[0-9a-f]+)*)\.png)")


class EmojiAssets:
    def __init__(self, font_path):
        self.font = TTFont(font_path)
        self.order = self.font.getGlyphOrder()
        self.shaper = hb.Font(hb.Face(Path(font_path).read_bytes()))
        hb.ot_font_set_funcs(self.shaper)
        strikes = self.font["CBLC"].strikes
        index = max(range(len(strikes)), key=lambda i: strikes[i].bitmapSizeTable.ppemY)
        self.bitmaps = self.font["CBDT"].strikeData[index]

    def png(self, asset):
        match = NAME.fullmatch(asset.strip())
        if not match:
            return None
        try:
            codepoints = [int(part, 16) for part in match[2].split("-")]
            if any(value > 0x10FFFF or 0xD800 <= value <= 0xDFFF for value in codepoints):
                return None
            buffer = hb.Buffer()
            buffer.add_codepoints(codepoints)
            buffer.flags = hb.BufferFlags.REMOVE_DEFAULT_IGNORABLES
            buffer.guess_segment_properties()
            hb.shape(self.shaper, buffer)
            if len(buffer.glyph_infos) != 1:
                return None
            glyph_id = buffer.glyph_infos[0].codepoint
            if glyph_id == 0:
                return None
            bitmap = self.bitmaps.get(self.order[glyph_id])
            if bitmap is None:
                return None
            data = bitmap.imageData
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                return None
            with Image.open(BytesIO(data)) as image:
                image.verify()
            return match[1], data
        except (KeyError, ValueError, IndexError):
            return None
