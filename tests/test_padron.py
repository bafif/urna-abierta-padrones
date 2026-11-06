import io
import json
import stat
import zipfile

from urna_padrones.padron import elector_from, padron_bytes, padron_summary, write_padron


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


def test_an_order_that_is_not_a_number_from_1_is_left_out_and_asks_for_a_look():
    for order in ("0", "00", "²", "①", "1²", "-3", "x", 0, True):
        person = elector_from(record(order=order), 0)
        assert "order" not in person, order
        assert person["review"] == {"status": "pending"}, order
    assert padron_summary([record(order="²"), record(order="0", document="99000002")]) == {"people": 2, "to_review": 2}


def test_a_missing_order_is_fine():
    for order in (None, ""):
        person = elector_from(record(order=order), 0)
        assert "order" not in person and person["review"] == {"status": "ok"}
    assert elector_from(record(order=12), 0)["order"] == 12


def test_the_file_says_how_many_people_it_has_and_only_its_owner_can_read_it(tmp_path):
    out = tmp_path / "prueba.padron"
    summary = write_padron([record(), record(document="99000002", needs_review=True)], out, title="Prueba")
    assert summary == {"people": 2, "to_review": 1}
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    manifest, electors = read(out)
    assert manifest["format"] == "padron-abierto"
    assert manifest["extraction"]["external_ai"] is False
    assert manifest["files"]["electors"]["count"] == len(electors) == 2


def test_the_manifest_says_whether_an_outside_ai_saw_the_data():
    def extraction(records):
        with zipfile.ZipFile(io.BytesIO(padron_bytes(records))) as archive:
            return json.loads(archive.read("manifest.json"))["extraction"]

    assert extraction([record()]) == {"tool": "urna-padrones", "external_ai": False}
    seen = record(document="99000002", external_ai="api.eu.mistral.ai (mistral-ocr-latest)")
    assert extraction([record(), seen]) == {
        "tool": "urna-padrones",
        "external_ai": True,
        "provider": "api.eu.mistral.ai (mistral-ocr-latest)",
    }


def contents(data):
    """What a .padron holds, without the moment it was made."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read("manifest.json"))
        electors = archive.read("electors.jsonl")
    manifest.pop("created_at")
    return names, manifest, electors


def test_padron_bytes_is_what_write_padron_writes(tmp_path):
    records = [record(), record(document="99000002", needs_review=True)]
    out = tmp_path / "prueba.padron"
    write_padron(records, out, title="Prueba")
    assert contents(padron_bytes(records, title="Prueba")) == contents(out.read_bytes())
    assert padron_summary(records) == {"people": 2, "to_review": 1}


def test_a_row_a_person_confirmed_is_ok():
    def status(data):
        _, _, electors = contents(data)
        return json.loads(electors)["review"]["status"]

    doubtful = record(needs_review=True)
    assert status(padron_bytes([doubtful])) == "pending"
    doubtful["needs_review"] = False
    assert status(padron_bytes([doubtful])) == "ok"
    # Confirming a row without a usable identifier does not make it ok.
    unusable = record(needs_review=False, valid={"document": False, "file_number": False})
    assert status(padron_bytes([unusable])) == "pending"


def test_a_repeated_document_with_another_name_never_drops_anyone(tmp_path):
    out = tmp_path / "prueba.padron"
    summary = write_padron([record(), record(name="Ejemplo, Luis")], out)
    _, electors = read(out)
    assert summary == {"people": 2, "to_review": 1}
    assert len({person["id"] for person in electors}) == 2
    assert electors[1]["review"] == {"status": "pending"}


def test_someone_in_two_programs_is_written_once_where_the_roll_lists_them_first(tmp_path):
    out = tmp_path / "prueba.padron"
    first = record(order="3", program="Civil")
    again = record(order="41", program="Química", name="PRUEBA ANA")
    summary = write_padron([first, again, record(document="99000002", name="Ejemplo, Luis")], out)
    manifest, electors = read(out)
    assert summary == {"people": 2, "to_review": 0}
    assert manifest["files"]["electors"]["count"] == 2
    assert (electors[0]["id"], electors[0].get("order"), electors[0]["extra"]["program"]) == ("d-99000001", 3, "Civil")


def test_a_close_name_with_the_same_document_is_another_person():
    # Juan and Juana, or a letter misread in one listing: both stay, the later one for review.
    for other in ("Prueba, Juana", "Prueba, Anna"):
        name = "Prueba, Juan" if other == "Prueba, Juana" else "Prueba, Ana"
        summary = padron_summary([record(name=name), record(name=other)])
        assert summary == {"people": 2, "to_review": 1}
    # A name without letters is nobody's.
    assert padron_summary([record(name="-"), record(name="?")])["people"] == 2
