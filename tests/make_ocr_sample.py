"""Draw the sample image that ocr.self_test reads: invented cells, one above the other.

Run once, from the repository root, when SAMPLE_TEXT changes:

    uv run python tests/make_ocr_sample.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from fake_roll import accent_font_path
from urna_padrones.ocr import SAMPLE_CELL_HEIGHT, SAMPLE_IMAGE, SAMPLE_TEXT

WIDTH = 420
OUT = Path(__file__).resolve().parents[1] / "src" / "urna_padrones" / SAMPLE_IMAGE


def main() -> None:
    font_path = accent_font_path()
    if font_path is None:
        raise SystemExit("hace falta Liberation Sans / Liberation Sans is needed")
    font = ImageFont.truetype(font_path, size=32)
    image = Image.new("L", (WIDTH, SAMPLE_CELL_HEIGHT * len(SAMPLE_TEXT)), 255)
    draw = ImageDraw.Draw(image)
    for index, text in enumerate(SAMPLE_TEXT):
        draw.text((14, index * SAMPLE_CELL_HEIGHT + 10), text, fill=20, font=font)
    image = image.filter(ImageFilter.GaussianBlur(0.5))
    # Sixteen levels of gray are plenty for text and keep the file small.
    image = image.quantize(16).convert("L")
    image.save(OUT, optimize=True)
    print(f"{OUT.name}: {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
