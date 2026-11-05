import json
import stat
import zipfile

from urna_padrones.padron import elector_from, write_padron


def record(**values):
    base = {
        "order": "7",
        "name": "Prueba, Ana",
        "document": "99000001",
        "file_number": "P-1234/5",
        "program": "Civil",
        "status": "A",
        "valid": {"document": True, "file_number": True},
        "needs_review": False,
    }
    return {**base, **values}


def read(path):
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        electors = [json.loads(line) for line in archive.read("electors.jsonl").decode().splitlines()]
    return manifest, electors


def test_a_row_becomes_a_person_with_a_stable_id():
    person = elector_from(record(), 0)
    assert person["id"] == "d-99000001"
    assert person["order"] == 7
    assert person["identifiers"] == [{"type": "DNI", "value": "99000001"}, {"type": "legajo", "value": "P-1234/5"}]
    assert person["extra"] == {"program": "Civil", "status": "A"}
    assert person["review"] == {"status": "ok"}


def test_a_document_that_does_not_validate_is_not_used_and_asks_for_a_look():
    person = elector_from(record(valid={"document": False, "file_number": False}), 4)
    assert person["id"] == "f-5"
    assert person["identifiers"] == []
    assert person["review"] == {"status": "pending"}


def test_a_doubtful_row_stays_and_is_marked():
    assert elector_from(record(needs_review=True), 0)["review"] == {"status": "pending"}
    assert elector_from(record(name=None), 0)["full_name"] == "(sin leer)"


def test_the_file_says_how_many_people_it_has_and_only_its_owner_can_read_it(tmp_path):
    out = tmp_path / "prueba.padron"
    summary = write_padron([record(), record(document="99000002", needs_review=True)], out, title="Prueba")
    assert summary == {"people": 2, "to_review": 1}
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    manifest, electors = read(out)
    assert manifest["format"] == "padron-abierto"
    assert manifest["extraction"]["external_ai"] is False
    assert manifest["files"]["electors"]["count"] == len(electors) == 2


def test_a_repeated_document_never_drops_anyone(tmp_path):
    out = tmp_path / "prueba.padron"
    summary = write_padron([record(), record()], out)
    _, electors = read(out)
    assert summary == {"people": 2, "to_review": 1}
    assert len({person["id"] for person in electors}) == 2
