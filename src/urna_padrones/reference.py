"""A roll typed into a spreadsheet (.xlsx or .csv), read only for what a roll has: name, document and legajo.

It is the reference that `urna-padrones verify` compares a reading against. Any other column (notes, contact data,
anything a group keeps about people) is never read.
"""

import csv
import io
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RELS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
DOC_RELS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
HEADERS = {
    "full_name": ("nombre", "nombre completo", "apellido y nombre", "apellido y nombres", "nombre y apellido"),
    "family": ("apellido", "apellidos"),
    "given": ("nombres",),
    "document": ("dni", "documento", "nro documento", "n° documento", "n° de documento", "numero de documento"),
    "file_number": ("legajo", "n° de legajo", "nro legajo"),
}
HEADER_SEARCH = 10
MAX_UNPACKED = 200 * 1024 * 1024


class SpreadsheetError(Exception):
    """The spreadsheet cannot be used as a reference; the message says why, in Spanish."""


def header_key(text: str) -> str:
    """A header as it is compared: lowercase, without accents or dots, with º and ° as the same sign."""
    text = unicodedata.normalize("NFKD", text.casefold().replace("º", "°"))
    text = "".join(c for c in text if not unicodedata.combining(c)).replace(".", " ")
    return re.sub(r"\s+°", "°", re.sub(r"\s+", " ", text)).strip()


def _columns(cells: list[str]) -> dict[str, int] | None:
    keys = [header_key(cell) for cell in cells]
    found = {field: next((i for i, key in enumerate(keys) if key in names), -1) for field, names in HEADERS.items()}
    return found if found["full_name"] >= 0 or found["family"] >= 0 else None


def _people(rows: list[tuple[int, list[str]]]) -> list[dict]:
    header = next((i for i, (_, cells) in enumerate(rows[:HEADER_SEARCH]) if _columns(cells)), None)
    if header is None:
        raise SpreadsheetError("No encontré una columna con el nombre en las primeras filas.")
    columns = _columns(rows[header][1])
    people = []
    for line, cells in rows[header + 1 :]:
        def cell(field: str, cells: list[str] = cells) -> str:
            at = columns[field]
            return cells[at].strip() if 0 <= at < len(cells) else ""

        name = cell("full_name") or ", ".join(part for part in (cell("family"), cell("given")) if part)
        if not name:
            continue
        number = cell("document")
        people.append(
            {
                "row": line,
                "name": name,
                "document": re.sub(r"\D", "", re.sub(r"\.0+$", "", number)),
                "file_number": re.sub(r"\s", "", cell("file_number")).upper(),
            }
        )
    return people


def _xlsx_rows(path: Path) -> list[tuple[int, list[str]]]:
    try:
        book = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise SpreadsheetError("El archivo no es una planilla .xlsx.") from error
    with book:
        if sum(info.file_size for info in book.infolist()) > MAX_UNPACKED:
            raise SpreadsheetError("La planilla es demasiado grande para leerla.")
        names = set(book.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in item.iter(MAIN + "t")) for item in root.findall(MAIN + "si")]
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        links = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {link.get("Id"): link.get("Target", "") for link in links.findall(RELS + "Relationship")}
        first = workbook.find(f"{MAIN}sheets/{MAIN}sheet")
        if first is None:
            raise SpreadsheetError("La planilla no tiene hojas.")
        target = targets.get(first.get(DOC_RELS + "id"), "").lstrip("/")
        target = target if target.startswith("xl/") else f"xl/{target}"
        sheet = ET.fromstring(book.read(target))
    rows = []
    for row in sheet.iter(MAIN + "row"):
        cells: dict[int, str] = {}
        for cell in row.findall(MAIN + "c"):
            letters = re.match(r"[A-Z]+", cell.get("r", ""))
            if not letters:
                continue
            column = 0
            for letter in letters.group():
                column = column * 26 + ord(letter) - 64
            value = cell.find(MAIN + "v")
            kind = cell.get("t")
            if kind == "s" and value is not None:
                text = shared[int(value.text)]
            elif kind == "inlineStr":
                text = "".join(t.text or "" for t in cell.iter(MAIN + "t"))
            else:
                text = value.text or "" if value is not None else ""
                if kind is None and re.fullmatch(r"-?\d+\.0+", text):
                    text = text.split(".")[0]
            cells[column - 1] = text
        if any(value.strip() for value in cells.values()):
            width = max(cells) + 1
            rows.append((int(row.get("r", len(rows) + 1)), [cells.get(i, "") for i in range(width)]))
    return rows


def _csv_rows(path: Path) -> list[tuple[int, list[str]]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")  # what Excel in Spanish writes on Windows
    lines = text.splitlines()
    separator = max(";,\t", key=lambda s: sum(line.count(s) for line in lines[:HEADER_SEARCH]))
    rows = []
    for number, cells in enumerate(csv.reader(io.StringIO(text), delimiter=separator), start=1):
        if any(cell.strip() for cell in cells):
            rows.append((number, cells))
    return rows


def read_reference(path: Path) -> list[dict]:
    """The people of a spreadsheet roll, each with the row where it is, its name, document and legajo."""
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        rows = _xlsx_rows(path)
    elif suffix == ".csv":
        rows = _csv_rows(path)
    else:
        raise SpreadsheetError("La planilla tiene que ser .xlsx o .csv.")
    if not rows:
        raise SpreadsheetError("La planilla está vacía.")
    return _people(rows)
