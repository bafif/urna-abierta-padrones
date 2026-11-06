"""Writes the open roll format: a ZIP with manifest.json, electors.jsonl and, for a roll with tables, units.jsonl.

See docs/formato-padron.md.
"""

import io
import json
import os
import re
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .fields import fold

FORMAT_VERSION = "0.1.0"


def order_number(value) -> int | None:
    """The order as a number from 1 up, or None if it is missing or is not one."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    if not text or any(c not in "0123456789" for c in text):
        return None
    number = int(text)
    return number if number >= 1 else None


def unit_id(table: str) -> str:
    """The id of the unit for a table: «12» is mesa-12."""
    return "mesa-" + (re.sub(r"[^a-z0-9]+", "-", fold(str(table))).strip("-") or "sin-numero")


def elector_from(record: dict, index: int) -> dict:
    """One row of the extraction as a person of the roll. Whatever doubt it had is kept for a person to review."""
    document = record.get("document") if record.get("valid", {}).get("document") else None
    file_number = record.get("file_number") if record.get("valid", {}).get("file_number") else None
    identifiers = []
    if document:
        identifiers.append({"type": "DNI", "value": str(document)})
    if file_number:
        identifiers.append({"type": "legajo", "value": str(file_number)})
    # The same person keeps the same id when a corrected roll is loaded again.
    identity = f"d-{document}" if document else f"l-{file_number}" if file_number else f"f-{index + 1}"
    elector: dict = {"id": identity, "full_name": record.get("name") or "(sin leer)", "identifiers": identifiers}
    # A table read wrong is left out, like a bad order: the row is marked for review anyway.
    table = record.get("table") if record.get("valid", {}).get("table", True) else None
    if table:
        elector["table"] = unit_id(table)
    if record.get("address"):
        elector["address"] = str(record["address"])
    order = order_number(record.get("order"))
    if order is not None:
        elector["order"] = order
    # An order that is there but is not a number from 1 up is left out, for a person to look at.
    bad_order = record.get("order") not in (None, "") and order is None
    extra = {key: record[key] for key in ("program", "status") if record.get(key)}
    if extra:
        elector["extra"] = extra
    pending = record.get("needs_review") or not record.get("name") or not identifiers or bad_order
    elector["review"] = {"status": "pending" if pending else "ok"}
    return elector


def _name_key(name: str | None) -> str:
    """A name without case, accents or marks, with its words in order: «Prueba, Ana» and «ANA PRUEBA» are one."""
    return " ".join(sorted(re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFC", fold(name or ""))).split()))


def same_person(first: dict, second: dict) -> bool:
    """Two people with the same id are one only when their names are the same.

    A close name is not enough: Juan and Juana with one document are two people, one with a document read or typed
    wrong. At worst the same person stays twice, marked for review; nobody is left out.
    """
    a = _name_key(first.get("full_name"))
    return bool(a) and a == _name_key(second.get("full_name"))


def electors_from(records: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    electors = []
    for index, record in enumerate(records):
        elector = elector_from(record, index)
        earlier = by_id.get(elector["id"])
        if earlier is not None:
            if same_person(earlier, elector):
                # Someone in two programs is listed once in each, but votes once, where the roll lists them first:
                # on paper the repeats are crossed out.
                continue
            # The same document with another name is a doubt, never a reason to drop someone.
            elector["id"] = f"f-{index + 1}"
            elector["review"] = {"status": "pending"}
        by_id[elector["id"]] = elector
        electors.append(elector)
    return electors


def extraction_of(records: list[dict]) -> dict:
    """How the records were read: whether an outside AI saw them and, when the records say, which service."""
    marks = [record.get("external_ai") for record in records if record.get("external_ai")]
    providers = sorted({str(mark) for mark in marks if isinstance(mark, str)})
    extraction: dict = {"tool": "urna-padrones", "external_ai": bool(marks)}
    if providers:
        extraction["provider"] = "; ".join(providers)
    return extraction


def _summary(electors: list[dict]) -> dict:
    """How many people and how many to review, and how many tables when the roll has them."""
    summary = {"people": len(electors), "to_review": sum(e["review"]["status"] == "pending" for e in electors)}
    tables = len(units_from(electors))
    if tables:
        summary["tables"] = tables
    return summary


def padron_summary(records: list[dict]) -> dict:
    """How many people the file would have and how many of them are marked for review."""
    return _summary(electors_from(records))


def padron_bytes(records: list[dict], title: str | None = None) -> bytes:
    """The .padron file for these records, as bytes: what write_padron writes, with its own created_at.

    `records` are the extraction lines, as RollReading.records() returns them. Review works
    like this: a record with "needs_review": false is written with review.status "ok", and one
    with "needs_review": true with "pending". So a program where a person confirms or fixes a
    row sets needs_review to false (and, if the person fixed the document or the file number,
    also its "valid" flag to true). A row stays "pending" anyway when it has no name, when it
    has neither a valid document nor a valid file number, when its order is not a number from 1
    up (it is then left out), or when its id repeats an earlier one with another name. A later row
    with the same id and the same name is the same person in another program and is left out.

    A record with a "table" puts its person at that table, and the file gets one unit per table. A
    record with an "address" keeps it. A record with "external_ai", the service that read it, makes the
    manifest say that an outside AI saw the data, and which service.
    """
    return _archive(electors_from(records), title, extraction_of(records))


def units_from(electors: list[dict]) -> list[dict]:
    """One unit for each table the people have, in the order the roll first lists it."""
    units: dict[str, dict] = {}
    for elector in electors:
        table = elector.get("table")
        if table and table not in units:
            units[table] = {"id": table, "level": "mesa", "name": "Mesa " + table.removeprefix("mesa-")}
    return list(units.values())


def _archive(electors: list[dict], title: str | None, extraction: dict) -> bytes:
    units = units_from(electors)
    manifest = {
        "format": "padron-abierto",
        "format_version": FORMAT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "extraction": extraction,
        "extra_fields": [{"key": "program", "label": "Carrera"}, {"key": "status", "label": "Calidad"}],
        "files": {"electors": {"path": "electors.jsonl", "count": len(electors)}},
    }
    if title:
        manifest["title"] = title
    if units:
        manifest["levels"] = ["mesa"]
        manifest["files"]["units"] = {"path": "units.jsonl", "count": len(units)}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
        if units:
            archive.writestr("units.jsonl", "".join(json.dumps(u, ensure_ascii=False) + "\n" for u in units))
        archive.writestr("electors.jsonl", "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in electors))
    return buffer.getvalue()


def write_padron(records: list[dict], out: Path, title: str | None = None) -> dict:
    """Writes the file readable only by its owner, and says how many people went in and how many need a look.

    The content is padron_bytes(records, title); see there how review works.
    """
    electors = electors_from(records)
    data = _archive(electors, title, extraction_of(records))
    descriptor = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
    return _summary(electors)
