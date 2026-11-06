"""Ruled scans laid out otherwise than the faculty's: the header says which column holds what."""

import pytest

from fake_layouts import draw_ruled_page, people
from fake_roll import draw_page, fake_rows, find_font, save_pdf
from urna_padrones.fields import fold
from urna_padrones.reading import read_roll
from urna_padrones.table import extract_page, read_page

ROWS = 30
COMPARED = ("order", "name", "file_number", "document")


def share(hits, total):
    return hits / total if total else 0.0


@pytest.fixture(scope="module")
def drawn():
    font, accents = find_font()
    return font, people(ROWS, seed=12, accents=accents)


@pytest.fixture(scope="module")
def faculty(drawn):
    """The same people in the faculty's layout, read as it always was."""
    font, rows = drawn
    return extract_page(draw_page(rows, angle=0.5, font=font), page=0)


def same_people(found, rows):
    assert len(found) == len(rows)
    assert share(sum(r.checked("document").value == p["document"] for r, p in zip(found, rows)), len(rows)) >= 0.95
    assert share(sum(r.checked("order").value == p["order"] for r, p in zip(found, rows)), len(rows)) >= 0.95
    names = sum(fold(r.checked("name").value or "") == fold(p["name"]) for r, p in zip(found, rows))
    assert share(names, len(rows)) >= 0.9


def agree_with_faculty(found, faculty):
    """Each value reads the same as the same cell read in the faculty's layout, for nearly every row."""
    for column in COMPARED:
        same = sum(a.checked(column).value == b.checked(column).value for a, b in zip(found, faculty))
        assert share(same, len(found)) >= 0.95, column


def test_the_faculty_layout_is_found_by_its_header_and_read_as_always(drawn, faculty):
    _, rows = drawn
    same_people(faculty, rows)
    assert all(row.layout == "facultad" for row in faculty)


def test_a_ruled_table_with_its_columns_in_another_order(drawn, faculty):
    font, rows = drawn
    headers = ["Orden", "DNI", "Apellido y nombre", "Legajo", "Carrera", "Domicilio"]
    keys = ["order", "document", "name", "file_number", "program", "address"]
    page = draw_ruled_page(rows, headers, keys, [150, 300, 560, 1120, 1390, 1820, 2380], font=font)
    reading = read_page(page, 0)
    found = reading.rows
    assert reading.header is not None and reading.header.keys == tuple(keys)
    assert all(row.layout == "encabezado" for row in found)
    same_people(found, rows)
    agree_with_faculty(found, faculty)
    assert share(sum(r.checked("address").value == p["address"] for r, p in zip(found, rows)), ROWS) >= 0.9


def test_a_ruled_table_with_extra_columns(drawn, faculty):
    font, rows = drawn
    headers = ["Nº", "Nombre", "Notas", "Propuesta", "Legajo", "Documento", "Calidad", "Mesa", "Firma"]
    keys = ["order", "name", "", "program", "file_number", "document", "status", "", ""]
    column_x = [60, 170, 760, 1000, 1380, 1620, 1880, 2050, 2200, 2420]
    page = draw_ruled_page(rows, headers, keys, column_x, font=font)
    found = read_page(page, 0).rows
    same_people(found, rows)
    agree_with_faculty(found, faculty)
    assert share(sum(r.checked("status").value == p["status"] for r, p in zip(found, rows)), ROWS) >= 0.95
    # «Notas» and «Firma» are not read; «Mesa» is, and is empty: everyone there needs a look.
    assert all("table" in row.columns and row.needs_review() for row in found)


def test_without_a_header_it_knows_the_page_is_the_faculty_layout():
    font, accents = find_font()
    rows = fake_rows(12, seed=4, accents=accents)
    page = draw_ruled_page(rows, ["Uno", "Nombre y datos", "Tres", "Cuatro", "Cinco", "Seis", "Siete"],
                           ["order", "name", "program", "file_number", "document", "status", ""],
                           [150, 330, 1010, 1420, 1690, 1960, 2190, 2400], font=font)
    reading = read_page(page, 0)
    assert reading.header is None
    assert all(row.layout == "facultad" for row in reading.rows)
    documents = sum(r.checked("document").value == p["document"] for r, p in zip(reading.rows, rows))
    assert share(documents, len(rows)) >= 0.9


def test_a_page_without_a_header_takes_the_header_of_another_page(tmp_path):
    font, accents = find_font()
    rows = people(24, seed=21, accents=accents)
    headers = ["Nº", "Apellido", "Nombres", "DNI", "Domicilio"]
    keys = ["order", "family", "given", "document", "address"]
    column_x = [150, 300, 760, 1200, 1500, 2300]
    pages = [
        draw_ruled_page(rows[:12], headers, keys, column_x, font=font, seed=1),
        draw_ruled_page(rows[12:], [""] * 5, keys, column_x, font=font, seed=2, angle=-0.4),
    ]
    path = tmp_path / "dos-paginas.pdf"
    save_pdf(pages, path)
    reading = read_roll(path)
    assert [row.page for row in reading.rows] == [0] * 12 + [1] * 12
    assert all(row.layout == "encabezado" for row in reading.rows)
    names = sum(fold(r.values["name"] or "") == fold(p["name"]) for r, p in zip(reading.rows, rows))
    assert share(names, len(rows)) >= 0.9
    assert share(sum(r.values["document"] == p["document"] for r, p in zip(reading.rows, rows)), len(rows)) >= 0.95


def test_a_faculty_page_keeps_its_own_header_next_to_a_list_laid_out_otherwise(tmp_path):
    """One PDF may hold two lists: a page with another header and as many columns lends it only to pages without one."""
    font, accents = find_font()
    other = people(12, seed=12, accents=accents)
    headers = ["Orden", "DNI", "Apellido y nombre", "Legajo", "Carrera", "Domicilio", "Firma"]
    keys = ["order", "document", "name", "file_number", "program", "address", ""]
    column_x = [150, 290, 540, 1060, 1330, 1700, 2150, 2400]
    faculty_rows = fake_rows(12, seed=5, first_order=21, accents=accents)
    pages = [draw_ruled_page(other, headers, keys, column_x, font=font), draw_page(faculty_rows, angle=0.4, font=font)]
    path = tmp_path / "dos-listas.pdf"
    save_pdf(pages, path)
    reading = read_roll(path)
    second = [row for row in reading.rows if row.page == 1]
    assert len(second) == len(faculty_rows)
    assert all(row.layout == "facultad" for row in second)
    documents = sum(r.values["document"] == p["document"] for r, p in zip(second, faculty_rows))
    assert share(documents, len(second)) >= 0.9
    names = sum(fold(r.values["name"] or "") == fold(p["name"]) for r, p in zip(second, faculty_rows))
    assert share(names, len(second)) >= 0.9
