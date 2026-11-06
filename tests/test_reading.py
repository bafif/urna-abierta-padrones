"""The library under the command line and the desktop program, on rolls made up here."""

import copy
import json
import threading
import time

import cv2
import numpy as np
import pypdfium2 as pdfium
import pytest

from fake_roll import COLUMN_X, PAGE_SIZE, ROW_HEIGHT, make_encrypted_pdf, make_fake_roll_pdf, make_text_pdf
from urna_padrones import cli, table
from urna_padrones.fields import clean_document, fold
from urna_padrones.grid import find_grid, straighten
from urna_padrones.ocr import read_cell
from urna_padrones.pdf import page_count, render_page
from urna_padrones.reading import COLUMNS, RollError, read_roll, row_image
from urna_padrones.table import build_vocabulary, infer_orders, smooth_by_neighbours

PAGES = 3
ROWS_PER_PAGE = 20


@pytest.fixture(scope="module")
def roll(tmp_path_factory):
    path = tmp_path_factory.mktemp("roll") / "padron.pdf"
    drawn = make_fake_roll_pdf(path, pages=PAGES, rows_per_page=ROWS_PER_PAGE)
    calls = []
    reading = read_roll(path, on_page=lambda done, total: calls.append((done, total)))
    return path, drawn, reading, calls


def share(hits, total):
    return hits / total if total else 0.0


def test_reads_every_row_in_order(roll):
    _, drawn, reading, _ = roll
    rows = reading.rows
    assert len(rows) == len(drawn)
    assert [row.index for row in rows] == list(range(len(drawn)))
    assert [row.page for row in rows] == [i // ROWS_PER_PAGE for i in range(len(drawn))]
    for column in ("order", "document", "status"):
        assert share(sum(r.values[column] == d[column] for r, d in zip(rows, drawn)), len(rows)) >= 0.95
    names = sum(fold(r.values["name"] or "") == fold(d["name"]) for r, d in zip(rows, drawn))
    assert share(names, len(rows)) >= 0.9


def test_the_degree_is_consistent_along_the_roll(roll):
    _, drawn, reading, _ = roll
    assert [row.values["program"] for row in reading.rows] == [d["program"] for d in drawn]


def test_says_what_it_read(roll):
    path, _, reading, _ = roll
    assert reading.source_name == path.name
    assert (reading.pages_total, reading.pages_read, reading.pages_without_table) == (PAGES, PAGES, [])
    assert reading.inferred_orders == 0


def test_reports_progress_page_by_page(roll):
    *_, calls = roll
    assert calls == [(done, PAGES) for done in range(PAGES + 1)]


def test_every_row_has_a_box_inside_its_page(roll):
    _, _, reading, _ = roll
    width, height = PAGE_SIZE
    for row in reading.rows:
        box = row.box
        assert box is not None and box.page == row.page
        assert 0 <= box.top < box.bottom <= height and 0 <= box.left < box.right <= width
        assert abs((box.bottom - box.top) - ROW_HEIGHT) <= 4
        assert abs(box.skew) <= 3
    for page in range(PAGES):
        tops = [row.box.top for row in reading.rows if row.page == page]
        assert tops == sorted(tops) and len(set(tops)) == len(tops)
    assert any(abs(row.box.skew) > 0.05 for row in reading.rows)


def test_records_are_the_extraction_lines(roll):
    _, _, reading, _ = roll
    records = reading.records()
    assert len(records) == len(reading.rows)
    keys = [*COLUMNS, "page", "valid", "confidence", "repaired_file_number", "needs_review"]
    for record, row in zip(records, reading.rows):
        assert list(record) == keys
        assert record["page"] == row.page + 1
        assert list(record["valid"]) == list(COLUMNS)


def test_a_person_can_fix_a_value(roll):
    _, _, reading, _ = roll
    row = copy.deepcopy(reading.rows[0])
    assert not row.fix("document", "99.12")
    assert row.values["document"] == "9912" and not row.valid["document"]
    assert row.fix("document", "99.123.456")
    assert row.values["document"] == "99123456" and row.valid["document"]
    assert not row.fix("order", "0") and not row.valid["order"]
    assert not row.fix("order", "²") and not row.valid["order"]
    assert row.fix("order", "1")
    row.needs_review = False
    assert row.record()["needs_review"] is False


def test_row_image_shows_the_row_that_was_read(roll):
    path, drawn, reading, _ = roll
    for row in (reading.rows[0], reading.rows[ROWS_PER_PAGE + 7], reading.rows[-1]):
        png = row_image(path, row.box, margin=0, scale=1.0)
        assert png.startswith(b"\x89PNG")
        image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
        assert image.shape == (row.box.bottom - row.box.top, row.box.right - row.box.left)
        start = COLUMN_X[4] - COLUMN_X[0]
        text, _ = read_cell(image[:, start + 8 : start + COLUMN_X[5] - COLUMN_X[4] - 8])
        assert clean_document(text).value == drawn[row.index]["document"]


def test_row_image_adds_the_margin_and_scales(roll):
    path, _, reading, _ = roll
    box = reading.rows[3].box
    image = cv2.imdecode(np.frombuffer(row_image(path, box), np.uint8), cv2.IMREAD_GRAYSCALE)
    assert image.shape == (round((box.bottom - box.top + 24) * 0.5), round((box.right - box.left + 24) * 0.5))


def test_reads_only_the_first_pages_when_asked(roll):
    path, *_ = roll
    reading = read_roll(path, pages=1, workers=1)
    assert (reading.pages_total, reading.pages_read) == (PAGES, 1)
    assert len(reading.rows) == ROWS_PER_PAGE


def test_cancelling_before_starting_reads_nothing(roll):
    path, *_ = roll
    calls = []
    with pytest.raises(RollError) as raised:
        read_roll(path, on_page=lambda *args: calls.append(args), cancelled=lambda: True)
    assert raised.value.code == "cancelled"
    assert calls == []


def test_cancelling_stops_in_the_middle_of_a_page(roll, monkeypatch):
    path, *_ = roll
    cells = []

    def counting(image):
        cells.append(time.monotonic())
        return read_cell(image)

    monkeypatch.setattr(table, "read_cell", counting)
    flag = {}

    def cancelled():
        if "at" not in flag and len(cells) >= 3:
            flag["at"], flag["cells"] = time.monotonic(), len(cells)
        return "at" in flag

    with pytest.raises(RollError) as raised:
        read_roll(path, workers=1, cancelled=cancelled)
    assert raised.value.code == "cancelled"
    # The page stops at its next row: at most the rest of one row is read, twice for doubtful cells.
    assert len(cells) - flag["cells"] <= 2 * len(COLUMNS)
    assert time.monotonic() - flag["at"] < 1.5
    assert not [t for t in threading.enumerate() if t.name.startswith("urna-padrones")]


def test_cancelling_while_a_page_is_straightened_reads_no_cell(roll, monkeypatch):
    path, *_ = roll
    started, seen = threading.Event(), threading.Event()
    cells, grids = [], []
    real_straighten, real_find_grid = table.straighten, table.find_grid

    def slow_straighten(image):
        started.set()
        # The cancel arrives while the page is still being straightened.
        assert seen.wait(10)
        time.sleep(0.3)
        return real_straighten(image)

    monkeypatch.setattr(table, "straighten", slow_straighten)
    monkeypatch.setattr(table, "find_grid", lambda image: grids.append(1) or real_find_grid(image))
    monkeypatch.setattr(table, "read_cell", lambda image: cells.append(1) or read_cell(image))

    def cancelled():
        if started.is_set():
            seen.set()
        return seen.is_set()

    with pytest.raises(RollError) as raised:
        read_roll(path, workers=1, cancelled=cancelled)
    assert raised.value.code == "cancelled"
    assert grids == [] and cells == []
    assert not [t for t in threading.enumerate() if t.name.startswith("urna-padrones")]


def test_cancelling_between_pages_drops_the_rest(roll):
    path, *_ = roll
    calls = []
    with pytest.raises(RollError) as raised:
        read_roll(path, workers=1, on_page=lambda *args: calls.append(args), cancelled=lambda: len(calls) >= 2)
    assert raised.value.code == "cancelled"
    assert calls == [(0, PAGES), (1, PAGES)]


@pytest.fixture
def bad_files(tmp_path):
    files = {
        "not_pdf": tmp_path / "carta.pdf",
        "zero_bytes": tmp_path / "vacio.pdf",
        "damaged": tmp_path / "roto.pdf",
        "encrypted": tmp_path / "clave.pdf",
        "empty": tmp_path / "sin-paginas.pdf",
        "unknown_layout": tmp_path / "sin-tabla.pdf",
    }
    files["not_pdf"].write_text("Esto es una carta, no un PDF.\n", encoding="utf-8")
    files["zero_bytes"].write_bytes(b"")
    files["damaged"].write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nbasura basura\n")
    make_encrypted_pdf(files["encrypted"], "prueba")
    document = pdfium.PdfDocument.new()
    document.save(files["empty"])
    document.close()
    make_text_pdf(files["unknown_layout"], pages=2)
    return files


@pytest.mark.parametrize(
    "name, code",
    [
        ("not_pdf", "not_pdf"),
        ("zero_bytes", "not_pdf"),
        ("damaged", "damaged"),
        ("encrypted", "encrypted"),
        ("empty", "empty"),
        ("unknown_layout", "unknown_layout"),
    ],
)
def test_a_file_it_cannot_read_says_why(bad_files, name, code):
    with pytest.raises(RollError) as raised:
        read_roll(bad_files[name])
    assert raised.value.code == code
    assert str(raised.value) and raised.value.message_en


def test_the_encrypted_sample_really_is_a_pdf_with_a_password(bad_files):
    document = pdfium.PdfDocument(bad_files["encrypted"], password="prueba")
    assert len(document) == 1
    document.close()


@pytest.mark.parametrize("size", [(0.2, 842), (595, 0.2)])
def test_a_page_one_pixel_thin_is_a_page_without_a_table(tmp_path, size):
    path = tmp_path / "fina.pdf"
    document = pdfium.PdfDocument.new()
    document.new_page(*size)
    document.save(path)
    document.close()
    image = render_page(path, 0)
    assert image.ndim == 2 and 1 in image.shape
    with pytest.raises(RollError) as raised:
        read_roll(path)
    assert raised.value.code == "unknown_layout"


def test_a_missing_file_is_an_os_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_roll(tmp_path / "no-existe.pdf")


def faculty_page_as_before(gray, page):
    """One page read as before headers were looked at: the faculty's columns in their order, nothing else."""
    straight, angle = straighten(gray)
    grid, clean = find_grid(straight)
    separators = table.select_separators(grid.columns)
    if separators is None or not grid.rows:
        return []
    rows = []
    for position in range(len(grid.rows)):
        band = table._band(grid.rows[position], separators, straight.shape)
        row = table.Row(page=page, position=position, band=band, skew=angle)
        for index, column in enumerate(COLUMNS):
            crop = table._cell(clean, grid, separators, position, index)
            if table._is_blank(crop):
                continue
            row.raw[column], row.confidence[column] = read_cell(crop)
            checked = table.CLEANERS[column](row.raw[column])
            if checked.valid and not checked.repaired:
                continue
            original = table._cell(straight, grid, separators, position, index)
            second = read_cell(cv2.resize(original, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC))
            retried = table.CLEANERS[column](second[0])
            if retried.valid and not retried.repaired:
                row.raw[column], row.confidence[column] = second
        rows.append(row)
    return [row for row in rows if not table.is_header(row)]


def old_extract_lines(pdf):
    """The extraction exactly as the command line wrote it before the library existed, and before headers."""
    per_page = [faculty_page_as_before(render_page(pdf, i), i + 1) for i in range(page_count(pdf))]
    rows = [row for page in per_page for row in page]
    infer_orders(rows)
    raw_programs = [r.checked("program").value for r in rows]
    vocabulary = build_vocabulary([p or "" for p in raw_programs])
    programs = smooth_by_neighbours([vocabulary.get(p, p) for p in raw_programs])
    lines = []
    for row, program in zip(rows, programs):
        checked = {c: row.checked(c) for c in COLUMNS}
        record = {c: checked[c].value for c in COLUMNS}
        record["program"] = program
        record.update(
            page=row.page,
            valid={c: checked[c].valid for c in COLUMNS},
            confidence=row.confidence,
            repaired_file_number=checked["file_number"].repaired,
            needs_review=row.needs_review(),
        )
        lines.append(json.dumps(record, ensure_ascii=False) + "\n")
    return "".join(lines).encode("utf-8")


def test_the_command_line_writes_the_same_bytes_as_before(roll, tmp_path, capsys):
    path, *_ = roll
    out = tmp_path / "padron.jsonl"
    assert cli.main(["extract", str(path), "--out", str(out)]) == 0
    assert out.read_bytes() == old_extract_lines(path)
    assert capsys.readouterr().out.startswith(f"{PAGES * ROWS_PER_PAGE} filas de {PAGES} páginas")


def test_the_command_line_refuses_to_write_inside_a_repo(tmp_path, capsys):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    out = tmp_path / "repo" / "padron.jsonl"
    assert cli.main(["extract", str(tmp_path / "no-existe.pdf"), "--out", str(out)]) == 2
    assert not out.exists()
    assert "repo de git" in capsys.readouterr().err


def test_the_command_line_ends_the_progress_line_before_an_error(tmp_path, capsys, monkeypatch):
    def broken(path, *, on_page=None, **kwargs):
        on_page(0, 2)
        on_page(1, 2)
        raise RollError("damaged")

    monkeypatch.setattr(cli, "read_roll", broken)
    monkeypatch.setattr(cli.sys.stderr, "isatty", lambda: True)
    assert cli.main(["extract", str(tmp_path / "roto.pdf"), "--out", str(tmp_path / "padron.jsonl")]) == 1
    assert capsys.readouterr().err == f"\rpágina 0 de 2\rpágina 1 de 2\n{RollError('damaged')}\n"


def test_the_command_line_explains_a_file_it_cannot_read(bad_files, tmp_path, capsys):
    out = tmp_path / "padron.jsonl"
    assert cli.main(["extract", str(bad_files["not_pdf"]), "--out", str(out)]) == 1
    assert not out.exists()
    assert "no es un PDF" in capsys.readouterr().err
