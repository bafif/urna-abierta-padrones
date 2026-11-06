"""PDFs with real text, made up here: their words are taken as they are, and the table is rebuilt from where they are."""

import json
import time

import cv2
import numpy as np
import pytest

from fake_layouts import listing_page, make_listing_pdf, pdf_bytes, people, text_content, turned_content
from fake_roll import draw_page, fake_rows, find_font
from urna_padrones import cli
from urna_padrones import reading as reading_module
from urna_padrones.reading import RollError, read_roll, row_image
from urna_padrones.textlayer import page_text

KEYS = ["order", "typed_document", "name", "address", "program"]
HEADERS = ["Nº", "Tipo y número", "Apellido y nombre", "Domicilio", "Carrera"]
COLUMN_X = [40, 70, 160, 330, 470, 580]
ROWS_PER_PAGE = 45


@pytest.fixture(scope="module")
def listing(tmp_path_factory):
    """Two pages without ruling, the header only on the first, the numbers aligned to the right."""
    path = tmp_path_factory.mktemp("listado") / "listado.pdf"
    drawn = people(2 * ROWS_PER_PAGE, seed=4)
    pages = [
        listing_page(drawn[:ROWS_PER_PAGE], HEADERS, KEYS, COLUMN_X, right_aligned=("order",)),
        listing_page(drawn[ROWS_PER_PAGE:], None, KEYS, COLUMN_X, right_aligned=("order",)),
    ]
    make_listing_pdf(path, pages)
    started = time.monotonic()
    reading = read_roll(path)
    return path, drawn, reading, time.monotonic() - started


def test_every_row_comes_out_exact(listing):
    _, drawn, reading, _ = listing
    assert len(reading.rows) == len(drawn)
    for row, person in zip(reading.rows, drawn):
        assert row.values["order"] == person["order"]
        assert row.values["name"] == person["name"]
        assert row.values["document"] == person["document"]
        assert row.values["address"] == person["address"]
        assert row.values["program"] == person["program"]
        assert set(row.confidence.values()) == {1.0}
        assert not row.needs_review


def test_a_page_without_a_header_takes_the_columns_of_the_first(listing):
    _, _, reading, _ = listing
    assert reading.pages_with_text == [0, 1]
    assert [row.page for row in reading.rows] == [i // ROWS_PER_PAGE for i in range(2 * ROWS_PER_PAGE)]


def test_it_reads_text_without_recognising_it(listing):
    *_, seconds = listing
    # Recognising two pages from their pictures takes several seconds; their text, a fraction of one.
    assert seconds < 3


def test_the_values_a_roll_lacks_are_left_out_of_valid(listing):
    _, _, reading, _ = listing
    record = reading.rows[0].record()
    assert record["file_number"] is None and record["status"] is None
    assert set(record["valid"]) == {"order", "name", "program", "document", "address"}
    assert record["address"] == reading.rows[0].values["address"]


def test_the_image_of_a_row_is_where_its_text_is(listing):
    path, _, reading, _ = listing
    row = reading.rows[10]
    image = cv2.imdecode(np.frombuffer(row_image(path, row.box, margin=0, scale=1.0), np.uint8), cv2.IMREAD_GRAYSCALE)
    assert image.shape == (row.box.bottom - row.box.top, row.box.right - row.box.left)
    assert row.box.skew == 0
    # The band holds one line of text: dark in the middle, paper above and below.
    ink = (image < 128).mean(axis=1)
    assert ink[len(ink) // 2 - 4 : len(ink) // 2 + 4].max() > 0.05 and ink[0] == 0 and ink[-1] == 0


def test_the_command_line_writes_the_extra_values(listing, tmp_path, capsys):
    path, drawn, _, _ = listing
    out = tmp_path / "listado.jsonl"
    assert cli.main(["extract", str(path), "--out", str(out)]) == 0
    first = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert first["address"] == drawn[0]["address"] and first["document"] == drawn[0]["document"]
    assert "páginas con texto: 2" in capsys.readouterr().out


def test_pages_after_the_header_are_read_from_their_text_at_once(listing, monkeypatch):
    """No page of a listing is recognised from its picture first, even the ones without a header of their own."""
    path, drawn, _, _ = listing
    pictures = []
    monkeypatch.setattr(reading_module, "render", lambda *args: pictures.append(args) or np.full((10, 10), 255, np.uint8))
    again = read_roll(path)
    assert pictures == [] and len(again.rows) == len(drawn)


def test_a_page_of_prose_in_a_listing_is_not_read_as_people(tmp_path):
    path = tmp_path / "con-nota.pdf"
    drawn = people(10, seed=9)
    note = text_content([(60, 100 + 16 * i, 10, f"Por la presente se informa a quien corresponda, renglón {c}.")
                         for i, c in enumerate("abcdefghijklmnopqrst")])
    make_listing_pdf(path, [listing_page(drawn, HEADERS, KEYS, COLUMN_X), note])
    reading = read_roll(path)
    assert [row.values["document"] for row in reading.rows] == [person["document"] for person in drawn]
    assert reading.pages_without_table == [1]


def test_family_name_and_given_names_in_two_columns_make_one_name(tmp_path):
    path = tmp_path / "dos-columnas.pdf"
    drawn = people(12, seed=6)
    keys = ["family", "given", "document", "file_number"]
    make_listing_pdf(path, [listing_page(drawn, ["Apellido", "Nombres", "DNI", "Legajo"], keys, [40, 150, 280, 380, 480])])
    reading = read_roll(path)
    assert [row.values["name"] for row in reading.rows] == [person["name"] for person in drawn]
    assert [row.values["file_number"] for row in reading.rows] == [person["file_number"] or None for person in drawn]


def test_a_title_and_a_footer_are_not_people(tmp_path):
    path = tmp_path / "con-titulo.pdf"
    drawn = people(8, seed=8)
    content = listing_page(drawn, HEADERS, KEYS, COLUMN_X, title="Padrón de prueba, todo inventado")
    content += text_content([(250, 800, 8, "Página 1 de 1")])
    make_listing_pdf(path, [content])
    reading = read_roll(path)
    assert [row.values["document"] for row in reading.rows] == [person["document"] for person in drawn]


WRAP_X = [40, 80, 170, 380, 560]
WRAP_HEADERS = ["Nº", "DNI", "Apellido y nombre", "Carrera"]


def wrapped_listing(path, drawn, wrapped, lines, align="top", spacing=11.0):
    """A listing where the name of person `wrapped` takes `lines`, with the other cells at the top or the bottom."""
    items = [(x, 90, 8.5, header) for x, header in zip(WRAP_X, WRAP_HEADERS)]
    y = 90 + 14 * 1.4
    for index, person in enumerate(drawn):
        names = lines if index == wrapped else [person["name"]]
        items += [(WRAP_X[2], y + spacing * i, 8.5, name) for i, name in enumerate(names)]
        others = y if align == "top" else y + spacing * (len(names) - 1)
        items += [(WRAP_X[0], others, 8.5, person["order"]), (WRAP_X[1], others, 8.5, person["document"])]
        items.append((WRAP_X[3], others, 8.5, person["program"]))
        y += spacing * (len(names) - 1) + 14
    make_listing_pdf(path, [text_content(items)])


@pytest.mark.parametrize("align", ["top", "bottom"])
def test_a_name_that_wraps_onto_a_second_line_stays_one_name(tmp_path, align):
    path = tmp_path / "nombre-largo.pdf"
    drawn = people(5, seed=3)
    wrapped_listing(path, drawn, 2, ["Prueba Inventada, Ana María", "de los Ejemplos"], align)
    reading = read_roll(path)
    assert [row.values["document"] for row in reading.rows] == [person["document"] for person in drawn]
    names = [person["name"] for person in drawn]
    names[2] = "Prueba Inventada, Ana María de los Ejemplos"
    assert [row.values["name"] for row in reading.rows] == names
    assert not any(row.needs_review for row in reading.rows)
    # The image of the row shows both lines of the name.
    assert reading.rows[2].box.bottom - reading.rows[2].box.top > 1.5 * (reading.rows[1].box.bottom - reading.rows[1].box.top)


def test_a_wrapped_line_nearly_as_close_to_the_next_row_leaves_the_row_for_review(tmp_path):
    path = tmp_path / "nombre-dudoso.pdf"
    drawn = people(5, seed=3)
    wrapped_listing(path, drawn, 2, ["Prueba Inventada, Ana María", "de los Ejemplos"], spacing=13)
    reading = read_roll(path)
    assert len(reading.rows) == 5
    assert reading.rows[2].values["name"] == "Prueba Inventada, Ana María de los Ejemplos"
    assert [row.needs_review for row in reading.rows] == [False, False, True, False, False]


def test_a_long_name_stays_whole_on_a_page_with_one_row(tmp_path):
    """The end of the name is past the end of «Apellido y nombre», next to a signature column without values."""
    path = tmp_path / "una-fila.pdf"
    items = [(x, 90, 8.5, header) for x, header in zip([40, 80, 170, 400], ["Nº", "DNI", "Apellido y nombre", "Firma"])]
    items += [(40, 110, 8.5, "1"), (80, 110, 8.5, "99.100.200"), (170, 110, 8.5, "Prueba Ejemplo, María de los Ángeles")]
    make_listing_pdf(path, [text_content(items)])
    reading = read_roll(path)
    assert [row.values["name"] for row in reading.rows] == ["Prueba Ejemplo, María de los Ángeles"]


def test_a_footer_of_words_is_not_a_person(tmp_path):
    path = tmp_path / "con-firma.pdf"
    drawn = people(5, seed=8)
    content = listing_page(drawn, WRAP_HEADERS, ["order", "document", "name", "program"], WRAP_X)
    content += text_content([(200, 800, 8, "Firma del presidente de mesa"), (60, 40, 8, "Elección de prueba, todo inventado")])
    make_listing_pdf(path, [content])
    reading = read_roll(path)
    assert [row.values["name"] for row in reading.rows] == [person["name"] for person in drawn]


def scanned(rows):
    font, accents = find_font()
    return draw_page(rows, angle=0.4, font=font), accents


def test_a_pdf_can_mix_pages_with_text_and_scanned_pages(tmp_path):
    path = tmp_path / "mixto.pdf"
    typed = people(10, seed=2)
    image, accents = scanned(fake_rows(10, seed=5, first_order=11))
    path.write_bytes(pdf_bytes([{"content": listing_page(typed, HEADERS, KEYS, COLUMN_X)}, {"image": image}]))
    reading = read_roll(path)
    assert reading.pages_with_text == [0]
    assert [row.page for row in reading.rows] == [0] * 10 + [1] * 10
    assert [row.values["document"] for row in reading.rows[:10]] == [person["document"] for person in typed]
    scanned_rows = reading.rows[10:]
    assert all(row.layout == "facultad" for row in scanned_rows)
    assert sum(row.values["order"] == str(11 + i) for i, row in enumerate(scanned_rows)) >= 9


def test_invisible_text_a_scanner_added_is_not_taken(tmp_path):
    """A scanner that recognises the page leaves its own reading, invisible, over the picture."""
    path = tmp_path / "escaneo-con-texto.pdf"
    rows = fake_rows(10, seed=7)
    image, _ = scanned(rows)
    hidden = text_content([(40, 90 + 14 * i, 8, f"{i + 1} 99000000 Leído, Mal") for i in range(10)], invisible=True)
    path.write_bytes(pdf_bytes([{"image": image, "content": hidden}]))
    assert page_text(path, 0) is None
    reading = read_roll(path)
    assert reading.pages_with_text == []
    assert sum(row.values["document"] == person["document"] for row, person in zip(reading.rows, rows)) >= 9


def test_a_scanned_page_with_a_stamp_is_read_from_its_picture(tmp_path):
    """The stamp's date is under «Tipo y número» of the typed page: it is not a person, and the scan is read."""
    path = tmp_path / "mixto-con-sello.pdf"
    typed = people(10, seed=2)
    rows = fake_rows(10, seed=5, first_order=11)
    image, _ = scanned(rows)
    stamp = text_content([(40, 825, 7, "Copia fiel"), (90, 825, 7, "05/11/2026"), (190, 825, 7, "Hoja 2 de 2, impresa")])
    path.write_bytes(pdf_bytes([{"content": listing_page(typed, HEADERS, KEYS, COLUMN_X)}, {"image": image, "content": stamp}]))
    assert page_text(path, 1).scanned
    reading = read_roll(path)
    assert reading.pages_with_text == [0] and reading.pages_without_table == []
    second = [row for row in reading.rows if row.page == 1]
    assert len(second) == 10 and all(row.layout == "facultad" for row in second)
    assert sum(row.values["document"] == person["document"] for row, person in zip(second, rows)) >= 9


@pytest.mark.parametrize("how", ["under a picture", "clipping path", "white"])
def test_text_that_does_not_show_is_not_taken(tmp_path, how):
    path = tmp_path / "oculto.pdf"
    items = listing_page(people(10, seed=7), HEADERS, KEYS, COLUMN_X)
    if how == "under a picture":
        page = {"image": np.full((3508, 2480), 250, np.uint8), "under": items}
    elif how == "clipping path":
        page = {"content": items.replace(b"BT /F1", b"BT 7 Tr /F1")}
    else:
        page = {"content": items.replace(b"BT /F1", b"BT 1 g /F1")}
    path.write_bytes(pdf_bytes([page]))
    assert page_text(path, 0) is None


@pytest.mark.parametrize("rotation", [90, 270])
def test_a_page_the_pdf_turns_is_read_from_its_text(tmp_path, rotation):
    """A landscape listing saved as a portrait page turned by the PDF, as a viewer does after turning it."""
    path = tmp_path / "apaisado.pdf"
    drawn = people(20, seed=4)
    column_x = [40, 80, 170, 380, 560]
    items = [(x, 60, 8.5, header) for x, header in zip(column_x, ["Nº", "DNI", "Apellido y nombre", "Carrera", "Domicilio"])]
    for i, person in enumerate(drawn):
        items += [(x, 80 + 14 * i, 8.5, person[key]) for x, key in zip(column_x, ["order", "document", "name", "program", "address"])]
    path.write_bytes(pdf_bytes([{"content": turned_content(items, rotation), "rotate": rotation}]))
    reading = read_roll(path)
    assert reading.pages_with_text == [0]
    assert [row.values["name"] for row in reading.rows] == [person["name"] for person in drawn]
    assert [row.values["address"] for row in reading.rows] == [person["address"] for person in drawn]
    # The image of a row is cut from the page as it is shown, landscape, where the row is.
    row = reading.rows[5]
    image = cv2.imdecode(np.frombuffer(row_image(path, row.box, margin=0, scale=1.0), np.uint8), cv2.IMREAD_GRAYSCALE)
    assert row.box.right > 2480  # wider than the page in portrait
    ink = (image < 128).mean(axis=1)
    assert ink[len(ink) // 2 - 4 : len(ink) // 2 + 4].max() > 0.05 and ink[0] == 0 and ink[-1] == 0


def test_text_without_a_header_it_knows_is_not_a_roll(tmp_path):
    path = tmp_path / "carta.pdf"
    lines = [(60, 100 + 16 * i, 10, f"Renglón {i + 1} de una carta inventada, sin ninguna tabla.") for i in range(30)]
    make_listing_pdf(path, [text_content(lines)])
    assert page_text(path, 0) is not None
    with pytest.raises(RollError) as raised:
        read_roll(path)
    assert raised.value.code == "unknown_layout"
