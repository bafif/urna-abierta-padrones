from urna_padrones.quality import crosscheck, edit_distance_one, order_report
from urna_padrones.table import build_vocabulary, edit_distance, smooth_by_neighbours


def record(order=None, name="Prueba, Ana", document="99000001", file_number=None, program="Civil", status="A"):
    return {
        "order": order,
        "name": name,
        "document": document,
        "file_number": file_number,
        "program": program,
        "status": status,
        "valid": {"document": True},
    }


def test_order_report_finds_sections_and_gaps():
    rows = [record(order=str(n)) for n in [1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 1, 2, 3]]
    report = order_report(rows)
    assert report["sections"] == 2
    assert report["numbers_skipped"] == 1
    assert report["rows_per_section"] == [12, 3]


def test_a_lost_page_shows_up_as_missing_people():
    numbers = list(range(1, 21)) + list(range(89, 101))
    report = order_report([record(order=str(n)) for n in numbers])
    assert report["sections"] == 1
    assert report["rows_missing"] == 68
    assert report["numbers_skipped"] == 68


def test_a_complete_roll_has_nobody_missing():
    numbers = list(range(1, 31)) + list(range(1, 11))
    assert order_report([record(order=str(n)) for n in numbers])["rows_missing"] == 0


def test_one_misread_number_does_not_open_a_section():
    numbers = [10, 11, 12, 13, 14, 1, 16, 17, 18]
    report = order_report([record(order=str(n)) for n in numbers])
    assert report["sections"] == 1
    assert report["numbers_misread"] == 1


def test_crosscheck_counts_agreement_and_disagreement():
    first = [
        record(name="Prueba, Ana", document="99000001", file_number="A-1000/1"),
        record(name="Ejemplo, Luis", document="99000002"),
        record(name="Modelo, Eva", document="99000003"),
    ]
    second = [
        record(name="Prueba, Ana", document="99000001", file_number="A-1000/1"),
        record(name="Ejemplo, Lais", document="99000002"),
        record(name="Modelo, Eva", document="99000008"),
        record(name="Otra, Persona", document="99000009"),
    ]
    result = crosscheck(first, second)
    assert result["joined_by_document"] == 2
    assert result["agreement"]["name_exact"] == 0.5
    assert result["unmatched_with_same_name_in_first"] == 1
    assert result["of_those_one_digit_away"] == 1
    assert result["unmatched_without_counterpart"] == 1


def test_crosscheck_reports_only_numbers():
    result = crosscheck([record()], [record()])
    assert "Prueba" not in str(result) and "99000001" not in str(result)


def test_edit_distance():
    assert edit_distance_one("123", "124") and edit_distance_one("123", "1234")
    assert not edit_distance_one("123", "123") and not edit_distance_one("123", "145")
    assert edit_distance("electrica", "electronica") == 2


def test_vocabulary_does_not_merge_two_real_degrees():
    values = ["Ingeniería Eléctrica"] * 50 + ["Ingeniería Electrónica"] * 50 + ["Ingeniería Mecánica"] * 50
    mapping = build_vocabulary(values)
    assert len(set(mapping.values())) == 3


def test_vocabulary_fixes_misspellings():
    values = ["Ingeniería Civil"] * 100 + ["Ingentería Civil"] * 20 + ["Ingeniera Civi"] * 2
    mapping = build_vocabulary(values)
    assert mapping["Ingentería Civil"] == "Ingeniería Civil"
    assert mapping["Ingeniera Civi"] == "Ingeniería Civil"


def test_a_value_alone_among_its_neighbours_is_corrected():
    values = ["Civil"] * 8 + ["Cióvil"] + ["Civil"] * 8 + ["Física"] * 8
    smoothed = smooth_by_neighbours(values)
    assert smoothed[8] == "Civil"
    assert smoothed[-1] == "Física"
