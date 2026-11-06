import json
import zipfile

import pytest

from urna_padrones import cli, quality
from urna_padrones.reference import SpreadsheetError, header_key, read_reference

NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


def write_xlsx(path, rows):
    """A minimal workbook: shared strings for text, plain numbers for numbers, like a spreadsheet saves them."""
    strings: list[str] = []
    xml_rows = []
    for r, row in enumerate(rows, start=1):
        cells = []
        for c, value in enumerate(row):
            ref = f"{chr(65 + c)}{r}"
            if value is None:
                continue
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                strings.append(value)
                cells.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
        xml_rows.append(f'<row r="{r}">{"".join(cells)}</row>')
    shared = "".join(f"<si><t>{s}</t></si>" for s in strings)
    with zipfile.ZipFile(path, "w") as book:
        book.writestr(
            "xl/workbook.xml",
            f'<workbook {NS} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Hoja" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        book.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        book.writestr("xl/sharedStrings.xml", f"<sst {NS}>{shared}</sst>")
        book.writestr("xl/worksheets/sheet1.xml", f"<worksheet {NS}><sheetData>{''.join(xml_rows)}</sheetData></worksheet>")


def record(name, document, file_number="", needs_review=False):
    return {"name": name, "document": document, "file_number": file_number, "needs_review": needs_review}


HEADER = ["N°", "Nombre", "Documento", "Legajo", "Carrera", "Voto", "Observaciones"]


def test_headers_are_compared_without_accents_dots_or_the_kind_of_degree_sign():
    assert header_key(" Nº de Documento ") == header_key("n.° de documento") == "n° de documento"
    assert header_key("Número de documento") == "numero de documento"


def test_only_the_roll_columns_are_read(tmp_path):
    path = tmp_path / "padron.xlsx"
    write_xlsx(path, [HEADER, [1.0, "Prueba, Ana", "99000001", "A-1234/3", "Civil", "Secreto", "Nota privada"]])
    people = read_reference(path)
    assert people == [{"row": 2, "name": "Prueba, Ana", "document": "99000001", "file_number": "A-1234/3"}]
    assert "Secreto" not in json.dumps(people) and "Nota privada" not in json.dumps(people)


def test_numeric_documents_lose_the_decimal_a_spreadsheet_adds(tmp_path):
    path = tmp_path / "padron.xlsx"
    write_xlsx(path, [["Nombre", "DNI"], ["Prueba, Ana", 99000001.0], ["Ejemplo, Luis", 99000002]])
    assert [p["document"] for p in read_reference(path)] == ["99000001", "99000002"]


def test_a_csv_with_a_title_above_and_windows_accents(tmp_path):
    path = tmp_path / "padron.csv"
    path.write_bytes("Padrón de prueba\n\nApellido;Nombres;DNI;Legajo\nNúñez;Inés;99000003;\n".encode("cp1252"))
    assert read_reference(path) == [{"row": 4, "name": "Núñez, Inés", "document": "99000003", "file_number": ""}]


def test_a_sheet_without_a_name_column_is_refused(tmp_path):
    path = tmp_path / "padron.csv"
    path.write_text("DNI;Legajo\n99000001;A-1234/3\n")
    with pytest.raises(SpreadsheetError):
        read_reference(path)


def test_verify_counts_differences_and_says_which_rows_to_check(tmp_path):
    path = tmp_path / "padron.xlsx"
    write_xlsx(
        path,
        [
            HEADER,
            [1, "Prueba, Ana", "99000001", "A-1234/3"],
            [2, "Ejemplo, Luis", "99000002", "C-1009/1"],  # the reading got the name wrong
            [3, "Modelo, Eva", "99000013", "C-1003/1"],  # the spreadsheet has a typo in the document
            [4, "Muestra, Inés", "99000004", "A-1234/5"],  # the legajo's digit does not add up
            [5, "Sinpar, Nadie", "99000005", ""],  # not in the reading
            [6, "Repetida, Una", "99000001", ""],  # same document as row 2
        ],
    )
    records = [
        record("Prueba, Ana", "99000001", "A-1234/3"),
        record("Ejemplo, Lais", "99000002", "C-1009/1"),
        record("Modelo, Eva", "99000003", "C-1003/1", needs_review=True),
        record("Muestra, Inés", "99000004", "A-1234/5"),
        record("Otra, Persona", "99000099"),
    ]
    result, rows = quality.verify(records, read_reference(path))
    assert result["people_in_spreadsheet"] == 6
    assert result["found_in_reading"] == 4
    assert result["read_rows_without_a_person"] == 1
    assert result["spreadsheet"] == {
        "el dígito del legajo no corresponde": 1,
        "DNI repetido en la planilla": 2,
    }
    assert result["rows_the_reading_gave_as_sure"] == {"rows": 3, "with_a_difference": 1, "by_field": {"nombre": 1}}
    assert result["rows_the_reading_flagged"] == {"rows": 1, "with_a_difference": 1}
    assert rows[3] == ["distinto de la lectura: nombre"]
    assert rows[4] == ["distinto de la lectura: DNI"]
    assert rows[5] == ["el dígito del legajo no corresponde"]
    assert "no está en la lectura" in rows[6]


def test_the_command_prints_counts_and_row_numbers_but_no_data(tmp_path, capsys):
    sheet = tmp_path / "padron.xlsx"
    write_xlsx(sheet, [HEADER, [1, "Prueba, Ana", "99000001", "A-1234/3"], [2, "Ejemplo, Luis", "99000002", ""]])
    reading = tmp_path / "lectura.jsonl"
    reading.write_text(
        "\n".join(json.dumps(r) for r in [record("Prueba, Ana", "99000001", "A-1234/3"), record("Ejemplo, Lais", "99000002")])
    )
    assert cli.main(["verify", str(reading), str(sheet), "--filas"]) == 0
    out = capsys.readouterr().out
    assert "fila 3: distinto de la lectura: nombre" in out
    for value in ("Prueba", "Ejemplo", "Lais", "99000001", "99000002", "A-1234/3"):
        assert value not in out
