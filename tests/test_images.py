"""Rolls as pictures, made up here: scans saved as JPEG, PNG or TIFF, and a phone photo."""

import struct
import zlib

import cv2
import numpy as np
import pytest

from fake_layouts import draw_ruled_page, people, photo_of, save_image
from fake_roll import PAGE_SIZE, draw_page, fake_rows, find_font
from urna_padrones import cli
from urna_padrones import pages as pages_module
from urna_padrones.fields import fold
from urna_padrones.pages import LONG_SIDE, PNG, check_roll, kind_of, render
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


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def test_a_picture_with_too_many_pixels_is_refused_before_opening_it(tmp_path):
    """A few hundred bytes may say 40000 by 40000 pixels: opening that would take gigabytes."""
    png = tmp_path / "enorme.png"
    header = struct.pack(">IIBBBBB", 40000, 40000, 8, 0, 0, 0, 0)
    png.write_bytes(PNG + png_chunk(b"IHDR", header) + png_chunk(b"IDAT", zlib.compress(b"\x00" * 100)) + png_chunk(b"IEND", b""))
    jpeg = tmp_path / "enorme.jpg"
    save_image([np.full((100, 80), 250, np.uint8)], jpeg, "jpeg")
    data = bytearray(jpeg.read_bytes())
    frame = data.index(b"\xff\xc0")
    data[frame + 5 : frame + 9] = struct.pack(">HH", 20000, 20000)
    jpeg.write_bytes(bytes(data))
    for path in (png, jpeg):
        with pytest.raises(RollError) as raised:
            check_roll(path)
        assert raised.value.code == "too_many_pixels"
    assert "120 millones" in raised.value.message


def test_the_size_of_each_page_comes_from_the_first_bytes(tmp_path):
    path = tmp_path / "dos.tif"
    save_image([np.full((300, 200), 250, np.uint8), np.full((120, 90), 250, np.uint8)], path, "tiff")
    assert check_roll(path) == 2
    assert pages_module._sizes(path.read_bytes()) == [(200, 300), (90, 120)]


def test_a_png_with_a_transparent_background_is_read_on_white_paper(tmp_path, font):
    """ImageMagick turns a PDF into a PNG with ink on transparent paper, which would otherwise read as black."""
    page = draw_page(fake_rows(10, seed=45, accents=font[1]), angle=0.3, font=font[0])
    rgba = np.dstack([np.zeros_like(page)] * 3 + [255 - page])
    path = tmp_path / "transparente.png"
    assert cv2.imwrite(str(path), rgba)
    shown = render(path, 0)
    assert shown.shape == page.shape
    assert float(np.abs(shown.astype(int) - page.astype(int)).mean()) < 2


def test_a_picture_that_is_not_a_table_is_not_a_roll(tmp_path):
    """Noise, as in a photo of something else, has specks the model cannot bring to its size: they read as nothing."""
    noise = (np.random.default_rng(1).random((1400, 1000)) * 255).astype(np.uint8)
    path = tmp_path / "ruido.jpg"
    save_image([noise], path, "jpeg")
    with pytest.raises(RollError) as raised:
        read_roll(path)
    assert raised.value.code == "unknown_layout"


def test_the_command_line_takes_a_picture(tmp_path, font, capsys):
    rows = fake_rows(8, seed=44, accents=font[1])
    path = tmp_path / "padron.jpeg"
    save_image([draw_page(rows, font=font[0])], path, "jpeg")
    assert cli.main(["extract", str(path), "--out", str(tmp_path / "padron.jsonl")]) == 0
    assert capsys.readouterr().out.startswith("8 filas de 1 páginas")
