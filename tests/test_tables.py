"""Rolls printed per table: the table of each person, from a «Mesa» column or from a «Mesa 12» title, goes into the roll file."""

import io
import json
import zipfile

from fake_layouts import draw_ruled_page, listing_page, make_listing_pdf, people, text_content
from fake_roll import draw_page, fake_rows, find_font, save_pdf
from urna_padrones import cli
from urna_padrones.padron import elector_from, padron_bytes, units_from
from urna_padrones.reading import read_roll

KEYS = ["order", "name", "document", "table"]
HEADERS = ["Orden", "Apellido y nombre", "DNI", "Mesa"]
COLUMN_X = [40, 90, 300, 420, 500]


def open_padron(data: bytes) -> tuple[dict, list[dict], list[dict]]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        units = archive.read("units.jsonl").decode().splitlines() if "units.jsonl" in archive.namelist() else []
        electors = archive.read("electors.jsonl").decode().splitlines()
    return manifest, [json.loads(u) for u in units], [json.loads(e) for e in electors]


def test_a_table_column_puts_each_person_at_their_table(tmp_path):
    path = tmp_path / "por-mesa.pdf"
    drawn = people(30, seed=31, tables=(12, 13, 14))
    make_listing_pdf(path, [listing_page(drawn, HEADERS, KEYS, COLUMN_X)])
    reading = read_roll(path)
    assert [row.values["table"] for row in reading.rows] == [person["table"] for person in drawn]
    assert reading.tables() == ["12", "13", "14"]
    manifest, units, electors = open_padron(padron_bytes(reading.records(), "Mesas de prueba"))
    assert manifest["levels"] == ["mesa"]
    assert manifest["files"]["units"] == {"path": "units.jsonl", "count": 3}
    assert units == [{"id": f"mesa-{n}", "level": "mesa", "name": f"Mesa {n}"} for n in (12, 13, 14)]
    assert [e["table"] for e in electors] == [f"mesa-{person['table']}" for person in drawn]


def test_a_title_gives_its_table_to_the_whole_page(tmp_path):
    path = tmp_path / "titulos.pdf"
    drawn = people(20, seed=32)
    keys, headers = KEYS[:3], HEADERS[:3]
    pages = [
        listing_page(drawn[:10], headers, keys, COLUMN_X, title="Padrón de prueba - Mesa Nº 3"),
        listing_page(drawn[10:], None, keys, COLUMN_X, title="MESA 0004"),
    ]
    make_listing_pdf(path, pages)
    reading = read_roll(path)
    assert [row.values["table"] for row in reading.rows] == ["3"] * 10 + ["4"] * 10


def test_a_listing_sorted_by_table_has_a_title_before_each(tmp_path):
    path = tmp_path / "agrupado.pdf"
    drawn = people(12, seed=35)
    keys, headers = KEYS[:3], HEADERS[:3]
    first = listing_page(drawn[:5], headers, keys, COLUMN_X, title="Mesa 5")
    second = listing_page(drawn[5:], None, keys, COLUMN_X, title="Mesa 6", top=90 + 14 * 1.4 + 5 * 14 + 40)
    make_listing_pdf(path, [first + second])
    reading = read_roll(path)
    assert [row.values["document"] for row in reading.rows] == [person["document"] for person in drawn]
    assert [row.values["table"] for row in reading.rows] == ["5"] * 5 + ["6"] * 7


def test_a_scanned_title_gives_its_table_and_the_faculty_layout_stays_as_it_was(tmp_path):
    font, accents = find_font()
    rows = fake_rows(16, seed=33, accents=accents)
    path = tmp_path / "escaneado.pdf"
    titled = draw_ruled_page(
        rows[:8], ["Nº", "Nombre", "Propuesta", "Legajo", "Documento", "Calidad", "Firma"],
        ["order", "name", "program", "file_number", "document", "status", ""],
        [150, 330, 1010, 1420, 1690, 1960, 2190, 2400], font=font, title="Mesa N° 7",
    )
    save_pdf([titled, draw_page(rows[8:], font=font)], path)
    reading = read_roll(path)
    assert [row.values.get("table") for row in reading.rows] == ["7"] * 8 + [None] * 8
    assert all(row.layout == "facultad" for row in reading.rows)
    assert "table" not in reading.rows[-1].record()
    # The second page has no title of its own: it does not take the first page's table, and is left for review.
    assert all(row.needs_review and row.valid["table"] is False for row in reading.rows[8:])


def test_a_table_goes_on_onto_the_next_page_with_text(tmp_path):
    """A listing sorted by table, with a «Mesa N» line before each, where Mesa 1 goes on onto the second page."""
    path = tmp_path / "sigue.pdf"
    drawn = people(20, seed=36)
    keys, headers = KEYS[:3], HEADERS[:3]

    def page(rows, mesas):
        items = [(x, 90, 8.5, header) for x, header in zip(COLUMN_X, headers)]
        y = 90 + 14 * 1.4
        for index, person in enumerate(rows):
            if index in mesas:
                items.append((COLUMN_X[0], y, 9, f"Mesa {mesas[index]}"))
                y += 14
            items += [(x, y, 8.5, person[key]) for x, key in zip(COLUMN_X, keys)]
            y += 14
        return text_content(items)

    make_listing_pdf(path, [page(drawn[:10], {0: 1}), page(drawn[10:], {5: 2})])
    reading = read_roll(path)
    assert [row.values["table"] for row in reading.rows] == ["1"] * 15 + ["2"] * 5
    assert not any(row.needs_review for row in reading.rows)
    _, units, electors = open_padron(padron_bytes(reading.records()))
    assert [unit["id"] for unit in units] == ["mesa-1", "mesa-2"]
    assert sum(elector["table"] == "mesa-1" for elector in electors) == 15


def test_whoever_is_left_without_a_table_is_reviewed(tmp_path):
    path = tmp_path / "sin-mesa.pdf"
    drawn = people(6, seed=37)
    keys, headers = KEYS[:3], HEADERS[:3]
    first = listing_page(drawn[:3], headers, keys, COLUMN_X)
    second = listing_page(drawn[3:], None, keys, COLUMN_X, title="Mesa 2", top=90 + 14 * 1.4 + 3 * 14 + 40)
    make_listing_pdf(path, [first + second])
    reading = read_roll(path)
    assert [row.values.get("table") for row in reading.rows] == [None] * 3 + ["2"] * 3
    assert [row.needs_review for row in reading.rows] == [True] * 3 + [False] * 3
    _, _, electors = open_padron(padron_bytes(reading.records()))
    assert [elector["review"]["status"] for elector in electors] == ["pending"] * 3 + ["ok"] * 3


def test_the_command_line_counts_the_tables(tmp_path, capsys):
    path = tmp_path / "por-mesa.pdf"
    make_listing_pdf(path, [listing_page(people(9, seed=34, tables=(1, 2, 3)), HEADERS, KEYS, COLUMN_X)])
    records, padron = tmp_path / "por-mesa.jsonl", tmp_path / "por-mesa.padron"
    assert cli.main(["extract", str(path), "--out", str(records)]) == 0
    assert "; mesas: 3" in capsys.readouterr().out
    assert cli.main(["padron", str(records), "--out", str(padron)]) == 0
    assert capsys.readouterr().out == "9 personas; 0 para revisar; 3 mesas\n"


def record(**changes) -> dict:
    base = {"order": "1", "name": "Prueba, Ana", "document": "99000001", "file_number": None, "program": None,
            "status": None, "valid": {"document": True, "name": True, "order": True}, "needs_review": False}
    base.update(changes)
    return base


def test_a_table_read_wrong_is_left_out_and_an_address_is_kept():
    assert elector_from(record(table="12", address="Calle Inventada 123"), 0)["table"] == "mesa-12"
    assert elector_from(record(table="12", address="Calle Inventada 123"), 0)["address"] == "Calle Inventada 123"
    wrong = elector_from(record(table="1x", valid={"document": True, "table": False}), 0)
    assert "table" not in wrong


def test_someone_listed_at_two_tables_votes_at_the_first():
    records = [record(table="5", program="Civil"), record(order="2", table="9", program="Química")]
    _, units, electors = open_padron(padron_bytes(records))
    assert [e["table"] for e in electors] == ["mesa-5"]
    assert units == [{"id": "mesa-5", "level": "mesa", "name": "Mesa 5"}]


def test_a_roll_without_tables_has_no_units():
    manifest, units, electors = open_padron(padron_bytes([record()]))
    assert "units" not in manifest["files"] and "levels" not in manifest and units == []
    assert "table" not in electors[0]
    assert units_from(electors) == []
