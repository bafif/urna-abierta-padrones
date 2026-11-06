"""Draw the tiny scanned page the desktop reader checks itself with (--self-test).

    uv run python tools/hacer-muestra.py

It writes src/urna_padrones/lector/muestra.png: the top of a roll page at 300 dpi with the
four invented people of SAMPLE_ROWS in src/urna_padrones/lector/selftest.py, slightly rotated
like a sheet feeder does. A picture and not a PDF, because the repository keeps no PDF at all.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from fake_roll import COLUMN_X, HEADERS, KEYS, PAGE_SIZE, ROW_HEIGHT, TOP, find_font  # noqa: E402

from urna_padrones.lector.selftest import SAMPLE_ROWS  # noqa: E402

OUT = ROOT / "src" / "urna_padrones" / "lector" / "muestra.png"


def draw(rows: list[dict]) -> Image.Image:
    font, accents = find_font()
    if not accents:
        raise SystemExit("Hace falta una letra con acentos (Liberation Sans o DejaVu Sans).")
    width = PAGE_SIZE[0]
    bottom = TOP + ROW_HEIGHT * (len(rows) + 1)
    image = Image.new("L", (width, bottom + TOP), 250)
    pen = ImageDraw.Draw(image)
    for x in COLUMN_X:
        pen.line([(x, TOP), (x, bottom)], fill=40, width=3)
    for i in range(len(rows) + 2):
        y = TOP + i * ROW_HEIGHT
        pen.line([(COLUMN_X[0], y), (COLUMN_X[-1], y)], fill=60, width=2)
    for x, header in zip(COLUMN_X, HEADERS):
        pen.text((x + 12, TOP + 4), header, fill=20, font=font)
    for r, row in enumerate(rows, start=1):
        for x, key in zip(COLUMN_X, KEYS):
            pen.text((x + 12, TOP + r * ROW_HEIGHT + 4), row[key], fill=25, font=font)
    rotated = image.rotate(0.6, resample=Image.BICUBIC, fillcolor=250).filter(ImageFilter.GaussianBlur(0.6))
    # Black and white is enough to read, and keeps the file at a few kilobytes.
    return Image.fromarray(np.asarray(rotated) >= 140)


def main() -> None:
    draw(SAMPLE_ROWS).save(OUT, "PNG", optimize=True)
    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
