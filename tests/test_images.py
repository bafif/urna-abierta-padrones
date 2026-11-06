"""Rolls as pictures, made up here: scans saved as JPEG, PNG or TIFF, and a phone photo."""

import cv2
import numpy as np
import pytest

from fake_layouts import draw_ruled_page, people, photo_of, save_image
from fake_roll import PAGE_SIZE, draw_page, fake_rows, find_font
from urna_padrones import cli
from urna_padrones.fields import fold
from urna_padrones.pages import LONG_SIDE, check_roll, kind_of, render
from urna_padrones.reading import RollError, read_roll, row_image

ROWS = 20


def share(hits, total):
    return hits / total if total else 0.0


def documents_read(reading, drawn):
    return share(sum(row.values["document"] == person["document"] for row, person in zip(reading.rows, drawn)), len(drawn))


@pytest.fixture(scope="module")
def font():
    return find_font()


def test_a_multi_page_tiff_is_read_page_by_page(tmp_path, font):
    rows = fake_rows(2 * ROWS, seed=41, accents=font[1])
    path = tmp_path / "padron.tif"
    save_image([draw_page(rows[:ROWS], font=font[0]), draw_page(rows[ROWS:], angle=-0.6, font=font[0])], path, "tiff")
    assert (kind_of(path), check_roll(path)) == ("image", 2)
    reading = read_roll(path)
    assert (reading.pages_total, reading.pages_with_text) == (2, [])
    assert [row.page for row in reading.rows] == [0] * ROWS + [1] * ROWS
    assert documents_read(reading, rows) >= 0.95
    row = reading.rows[ROWS + 3]
    image = cv2.imdecode(np.frombuffer(row_image(path, row.box, margin=0, scale=1.0), np.uint8), cv2.IMREAD_GRAYSCALE)
    assert image.shape == (row.box.bottom - row.box.top, row.box.right - row.box.left)


def test_a_png_with_another_layout(tmp_path, font):
    rows = people(ROWS, seed=42, accents=font[1])
    page = draw_ruled_page(rows, ["Orden", "DNI", "Apellido y nombre", "Domicilio"], ["order", "document", "name", "address"],
                           [150, 300, 560, 1200, 2100], font=font[0])
    path = tmp_path / "padron.png"
    save_image([page], path, "png")
    reading = read_roll(path)
    assert documents_read(reading, rows) >= 0.95
    assert share(sum(fold(r.values["name"] or "") == fold(p["name"]) for r, p in zip(reading.rows, rows)), ROWS) >= 0.9


def test_a_picture_is_brought_to_the_size_of_a_page(tmp_path):
    small = np.full((1169, 827), 250, np.uint8)  # an A4 page at 100 dpi
    path = tmp_path / "chica.jpg"
    save_image([small], path, "jpeg")
    assert max(render(path, 0).shape) == LONG_SIDE == max(PAGE_SIZE)


def test_a_phone_photo_of_a_page(tmp_path, font):
    rows = fake_rows(ROWS, seed=43, accents=font[1])
    path = tmp_path / "foto.jpg"
    save_image([photo_of(draw_page(rows, angle=0.3, font=font[0]))], path, "jpeg")
    reading = read_roll(path)
    assert len(reading.rows) == ROWS
    assert documents_read(reading, rows) >= 0.9


def test_a_damaged_picture_says_so(tmp_path):
    path = tmp_path / "rota.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"esto no es una imagen" * 10)
    with pytest.raises(RollError) as raised:
        read_roll(path)
    assert raised.value.code == "damaged"


def test_a_picture_without_a_table_is_not_a_roll(tmp_path):
    path = tmp_path / "blanca.png"
    save_image([np.full((3508, 2480), 250, np.uint8)], path, "png")
    with pytest.raises(RollError) as raised:
        read_roll(path)
    assert raised.value.code == "unknown_layout"


def test_the_command_line_takes_a_picture(tmp_path, font, capsys):
    rows = fake_rows(8, seed=44, accents=font[1])
    path = tmp_path / "padron.jpeg"
    save_image([draw_page(rows, font=font[0])], path, "jpeg")
    assert cli.main(["extract", str(path), "--out", str(tmp_path / "padron.jsonl")]) == 0
    assert capsys.readouterr().out.startswith("8 filas de 1 páginas")
