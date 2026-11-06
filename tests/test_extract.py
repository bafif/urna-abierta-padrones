"""End to end on a scan made up here: invented people, drawn, rotated and dirtied like a photocopy."""

import pytest
from PIL import ImageFont

from fake_roll import FONT_SIZE, ROW_HEIGHT, accent_font_path, draw_page, fake_rows
from urna_padrones.fields import fold
from urna_padrones.table import extract_page


def full_font(size):
    """The font bundled with Pillow has no accents: it would draw boxes instead of letters."""
    path = accent_font_path()
    if path is None:
        pytest.skip("hace falta una fuente con acentos")
    return ImageFont.truetype(path, size=size)


@pytest.fixture(scope="module")
def extracted():
    rows = fake_rows(40)
    return rows, extract_page(draw_page(rows, font=full_font(FONT_SIZE)), page=0)


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


def test_every_row_knows_its_band_and_the_page_angle(extracted):
    _, found = extracted
    tops = [row.band[0] for row in found]
    assert tops == sorted(tops)
    assert all(abs((bottom - top) - ROW_HEIGHT) <= 4 for top, bottom, _, _ in (row.band for row in found))
    assert len({row.skew for row in found}) == 1 and abs(found[0].skew) > 0.3
