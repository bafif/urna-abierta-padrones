"""End to end on a scan made up here: invented people, drawn, rotated and dirtied like a photocopy."""

import random
import subprocess

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from urna_padrones.fields import fold
from urna_padrones.table import extract_page

FAMILY = ["Prueba", "Ejemplo", "Modelo", "Muestra", "Núñez", "Peña", "Ibáñez", "Quiroga", "Rodríguez", "Benítez"]
GIVEN = ["Ana", "Luis", "María José", "Tomás", "Sofía", "Andrés", "Inés", "Ramiro"]
COLUMN_X = [150, 330, 1010, 1420, 1690, 1960, 2190, 2400]
ROW_HEIGHT = 46
TOP = 200


def fake_rows(count, seed=3):
    rng = random.Random(seed)
    rows = []
    for order in range(1, count + 1):
        legajo = "" if rng.random() < 0.2 else f"{rng.choice('ACLS')}-{rng.randint(1000, 9999)}/{rng.randint(0, 9)}"
        rows.append(
            {
                "order": str(order),
                "name": f"{rng.choice(FAMILY)}, {rng.choice(GIVEN)}",
                "program": "Ingeniería Civil",
                "file_number": legajo,
                "document": str(rng.randint(30_000_000, 49_999_999)),
                "status": rng.choice("AAAP"),
            }
        )
    return rows


def full_font(size):
    """The font bundled with Pillow has no accents: it would draw boxes instead of letters."""
    path = subprocess.run(["fc-match", "-f", "%{file}", "Liberation Sans"], capture_output=True, text=True)
    if path.returncode != 0 or not path.stdout:
        pytest.skip("hace falta una fuente con acentos")
    return ImageFont.truetype(path.stdout, size=size)


def draw_page(rows, angle=0.8, seed=5):
    font = full_font(32)
    image = Image.new("L", (2480, 3508), 250)
    draw = ImageDraw.Draw(image)
    bottom = TOP + ROW_HEIGHT * (len(rows) + 1)
    for x in COLUMN_X:
        draw.line([(x, TOP), (x, bottom)], fill=40, width=3)
    for i in range(len(rows) + 2):
        y = TOP + i * ROW_HEIGHT
        draw.line([(COLUMN_X[0], y), (COLUMN_X[-1], y)], fill=60, width=2)
    headers = ["Nº", "Nombre", "Propuesta", "Legajo", "Documento", "Calidad", "Firma"]
    for x, header in zip(COLUMN_X, headers):
        draw.text((x + 12, TOP + 4), header, fill=20, font=font)
    keys = ["order", "name", "program", "file_number", "document", "status"]
    for r, row in enumerate(rows, start=1):
        y = TOP + r * ROW_HEIGHT + 4
        for x, key in zip(COLUMN_X, keys):
            draw.text((x + 12, y), row[key], fill=25, font=font)
    image = image.rotate(angle, resample=Image.BICUBIC, fillcolor=250).filter(ImageFilter.GaussianBlur(0.6))
    pixels = np.asarray(image, dtype=np.int16)
    noise = np.random.default_rng(seed).normal(0, 6, pixels.shape)
    return np.clip(pixels + noise, 0, 255).astype(np.uint8)


@pytest.fixture(scope="module")
def extracted():
    rows = fake_rows(40)
    return rows, extract_page(draw_page(rows), page=1)


def test_finds_every_row_and_skips_the_header(extracted):
    rows, found = extracted
    assert len(found) == len(rows)


def test_reads_documents_and_order(extracted):
    rows, found = extracted
    documents = [row.checked("document").value for row in found]
    orders = [row.checked("order").value for row in found]
    hits = sum(a == b["document"] for a, b in zip(documents, rows))
    assert hits / len(rows) >= 0.95
    assert sum(a == b["order"] for a, b in zip(orders, rows)) / len(rows) >= 0.95


def test_reads_names_without_losing_accents(extracted):
    rows, found = extracted
    names = [row.checked("name").value or "" for row in found]
    assert sum(fold(a) == fold(b["name"]) for a, b in zip(names, rows)) / len(rows) >= 0.9
    assert any("ñ" in name or "í" in name or "á" in name for name in names)


def test_blank_file_numbers_stay_blank(extracted):
    rows, found = extracted
    for row, expected in zip(found, rows):
        if not expected["file_number"]:
            assert row.checked("file_number").value is None
