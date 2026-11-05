"""Writes the open roll format: a ZIP with manifest.json and electors.jsonl. See docs/formato-padron.md."""

import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

FORMAT_VERSION = "0.1.0"


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
    if record.get("order"):
        elector["order"] = int(record["order"])
    extra = {key: record[key] for key in ("program", "status") if record.get(key)}
    if extra:
        elector["extra"] = extra
    pending = record.get("needs_review") or not record.get("name") or not identifiers
    elector["review"] = {"status": "pending" if pending else "ok"}
    return elector


def write_padron(records: list[dict], out: Path, title: str | None = None) -> dict:
    """Writes the file readable only by its owner, and says how many people went in and how many need a look."""
    seen: set[str] = set()
    electors = []
    for index, record in enumerate(records):
        elector = elector_from(record, index)
        if elector["id"] in seen:
            # A repeated document is a doubt, never a reason to drop someone.
            elector["id"] = f"f-{index + 1}"
            elector["review"] = {"status": "pending"}
        seen.add(elector["id"])
        electors.append(elector)
    manifest = {
        "format": "padron-abierto",
        "format_version": FORMAT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "extraction": {"tool": "urna-padrones", "external_ai": False},
        "extra_fields": [{"key": "program", "label": "Carrera"}, {"key": "status", "label": "Calidad"}],
        "files": {"electors": {"path": "electors.jsonl", "count": len(electors)}},
    }
    if title:
        manifest["title"] = title
    descriptor = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as handle, zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
        archive.writestr("electors.jsonl", "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in electors))
    return {"people": len(electors), "to_review": sum(e["review"]["status"] == "pending" for e in electors)}
