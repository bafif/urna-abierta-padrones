"""Quality figures for an extraction. Reports contain only counts, never personal data."""

import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from .fields import DOCUMENT, FILE_NUMBER, file_number_adds_up, fold


def load_records(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def order_report(records: list[dict]) -> dict:
    """Numbering restarts per section: find the sections and the numbers that are missing.

    A restart needs the next row to confirm it, so one misread number does not open a section.
    """
    numbers = [int(r["order"]) if r["order"] else None for r in records]
    sections, missing, unread, misread, expected, count = [], 0, 0, 0, None, 0
    highest: list[int] = []
    for i, number in enumerate(numbers):
        following = numbers[i + 1] if i + 1 < len(numbers) else None
        restart = (
            number is not None
            and number <= 2
            and expected is not None
            and expected > 10
            and following == number + 1
        )
        if restart:
            sections.append(count)
            highest.append(expected - 1)
            count, expected = 0, None
        count += 1
        if expected is None:
            expected = (number or 0) + 1
        elif number is None:
            unread += 1
            expected += 1
        elif number == expected:
            expected += 1
        elif expected < number <= expected + 5:
            missing += number - expected
            expected = number + 1
        elif following == number + 1 and number > expected:
            # A long jump the next row confirms: a whole page was lost, not a misread number.
            missing += number - expected
            expected = number + 1
        else:
            misread += 1
            expected = number + 1 if following == number + 1 else expected + 1
    sections.append(count)
    highest.append((expected or 1) - 1)
    return {
        "sections": len(sections),
        "rows_per_section": sections,
        # People the roll numbers but the extraction did not find: this must be zero.
        "rows_missing": sum(max(0, top - rows) for top, rows in zip(highest, sections)),
        "numbers_skipped": missing,
        "numbers_unread": unread,
        "numbers_misread": misread,
    }


def report(records: list[dict]) -> dict:
    total = len(records)
    valid = Counter()
    repaired = 0
    blank_file_number = 0
    for record in records:
        for column, ok in record["valid"].items():
            valid[column] += bool(ok)
        repaired += record["repaired_file_number"]
        blank_file_number += record["file_number"] is None
    return {
        "rows": total,
        "valid_share": {c: round(n / total, 4) for c, n in sorted(valid.items())} if total else {},
        "rows_all_valid": sum(all(r["valid"].values()) for r in records),
        "rows_to_review": sum(bool(r.get("needs_review")) for r in records),
        "blank_file_number": blank_file_number,
        "repaired_file_number": repaired,
        # Rare values may be misread text from another column, so they stay out of the report.
        "programs": [
            item
            for item in Counter(r["program"] for r in records if r["program"]).most_common(20)
            if item[1] >= 10
        ],
        "status": Counter(r["status"] for r in records if r["status"] in {"A", "P"}).most_common(),
        "order": order_report(records),
    }


def _key_name(name: str | None) -> str:
    return re.sub(r"[^a-zñ ]", "", fold(name or "")).strip()


def _key_name_compact(name: str | None) -> str:
    """Names compared without spaces: a missing space does not stop anyone finding a person."""
    return _key_name(name).replace(" ", "")


def edit_distance_one(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1 or a == b:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    shorter, longer = sorted((a, b), key=len)
    return any(longer[:i] + longer[i + 1 :] == shorter for i in range(len(longer)))


def crosscheck(first: list[dict], second: list[dict]) -> dict:
    """Compare two scans of overlapping rolls.

    Their OCR errors are independent, so disagreement between them estimates the error of the
    pair. It only needs counts, so nobody has to read personal data to measure quality.
    """
    by_document = {r["document"]: r for r in first if r["document"] and r["valid"]["document"]}
    by_name: dict[str, list[dict]] = {}
    for record in first:
        by_name.setdefault(_key_name(record["name"]), []).append(record)
    joined = name_same = name_compact = name_close = file_same = file_compared = program_same = status_same = 0
    accepted = accepted_name = accepted_file = accepted_file_compared = accepted_status = 0
    unmatched = document_differs = document_one_digit = no_counterpart = 0
    invalid_document = 0
    for record in second:
        document = record["document"]
        if not (document and record["valid"]["document"]):
            invalid_document += 1
            continue
        other = by_document.get(document)
        if other is None:
            unmatched += 1
            twins = by_name.get(_key_name(record["name"]), [])
            twin = next((t for t in twins if t["document"]), None)
            if twin is None:
                no_counterpart += 1
            else:
                document_differs += 1
                document_one_digit += edit_distance_one(document, twin["document"])
            continue
        joined += 1
        a, b = _key_name(record["name"]), _key_name(other["name"])
        name_same += a == b
        same_compact = _key_name_compact(record["name"]) == _key_name_compact(other["name"])
        name_compact += same_compact
        name_close += SequenceMatcher(None, a, b).ratio() >= 0.9
        program_same += record["program"] == other["program"]
        status_same += record["status"] == other["status"]
        if record["file_number"] and other["file_number"]:
            file_compared += 1
            file_same += record["file_number"] == other["file_number"]
        if not record.get("needs_review") and not other.get("needs_review"):
            accepted += 1
            accepted_name += same_compact
            accepted_status += record["status"] == other["status"]
            if record["file_number"] and other["file_number"]:
                accepted_file_compared += 1
                accepted_file += record["file_number"] == other["file_number"]
    share = lambda n, d: round(n / d, 4) if d else None  # noqa: E731
    return {
        "rows_second": len(second),
        "second_invalid_document": invalid_document,
        "joined_by_document": joined,
        "unmatched_document": unmatched,
        "unmatched_with_same_name_in_first": document_differs,
        "of_those_one_digit_away": document_one_digit,
        "unmatched_without_counterpart": no_counterpart,
        "agreement": {
            "name_exact": share(name_same, joined),
            "name_without_spaces": share(name_compact, joined),
            "name_90_percent_similar": share(name_close, joined),
            "program": share(program_same, joined),
            "status": share(status_same, joined),
            "file_number": share(file_same, file_compared),
            "file_numbers_compared": file_compared,
        },
        "agreement_on_rows_nobody_flagged": {
            "rows": accepted,
            "name_without_spaces": share(accepted_name, accepted),
            "status": share(accepted_status, accepted),
            "file_number": share(accepted_file, accepted_file_compared),
        },
    }


def _similar(a: str, b: str) -> bool:
    return a == b or SequenceMatcher(None, a, b).ratio() >= 0.85


def _reference_checks(reference: list[dict]) -> tuple[dict, dict[int, list[str]]]:
    """What is odd in the spreadsheet itself, as counts and as the rows to look at."""
    rows: dict[int, list[str]] = {}
    documents = Counter(p["document"] for p in reference if p["document"])
    file_numbers = Counter(p["file_number"] for p in reference if p["file_number"])
    counts = Counter()
    for person in reference:
        found = []
        if not person["document"]:
            found.append("sin DNI")
        elif not DOCUMENT.match(person["document"]):
            found.append("el DNI no tiene 7 u 8 números")
        elif documents[person["document"]] > 1:
            found.append("DNI repetido en la planilla")
        if person["file_number"]:
            if not FILE_NUMBER.match(person["file_number"]):
                found.append("el legajo no tiene la forma A-1234/3")
            elif not file_number_adds_up(person["file_number"]):
                found.append("el dígito del legajo no corresponde")
            if file_numbers[person["file_number"]] > 1:
                found.append("legajo repetido en la planilla")
        counts.update(found)
        if found:
            rows[person["row"]] = found
    return dict(counts), rows


def verify(records: list[dict], reference: list[dict]) -> tuple[dict, dict[int, list[str]]]:
    """Compare a reading with a roll typed into a spreadsheet, and say where they differ.

    A person of the spreadsheet is matched to a read row when two of document, legajo and name agree, so a
    difference in any one of them still finds its row. A difference may come from the reading or from the
    spreadsheet: the figures say how many, never what. Returns the counts and, by spreadsheet row, what to check.
    """
    by_document: dict[str, list[dict]] = {}
    by_file: dict[str, list[dict]] = {}
    by_name: dict[str, list[dict]] = {}
    for record in records:
        if record.get("document"):
            by_document.setdefault(record["document"], []).append(record)
        if record.get("file_number"):
            by_file.setdefault(record["file_number"], []).append(record)
        by_name.setdefault(_key_name_compact(record.get("name")), []).append(record)
    counts, rows = _reference_checks(reference)
    matched = 0
    used: set[int] = set()
    same = Counter()
    compared = Counter()
    sure = flagged = sure_differs = flagged_differs = 0
    sure_by_field = Counter()
    for person in reference:
        name = _key_name_compact(person["name"])
        candidates = by_document.get(person["document"], []) + by_file.get(person["file_number"], []) + by_name.get(name, [])
        best, best_votes = None, 1
        for record in candidates:
            votes = (
                bool(person["document"]) and record.get("document") == person["document"],
                bool(person["file_number"]) and record.get("file_number") == person["file_number"],
                _similar(_key_name_compact(record.get("name")), name),
            )
            if sum(votes) > best_votes:
                best, best_votes = record, sum(votes)
        if best is None:
            rows.setdefault(person["row"], []).append("no está en la lectura")
            continue
        matched += 1
        used.add(id(best))
        differs = []
        compared["name"] += 1
        if _key_name_compact(best.get("name")) == name:
            same["name"] += 1
        else:
            differs.append("nombre")
        if person["document"]:
            compared["document"] += 1
            if best.get("document") == person["document"]:
                same["document"] += 1
            else:
                differs.append("DNI")
        if person["file_number"] and best.get("file_number"):
            compared["file_number"] += 1
            if best["file_number"] == person["file_number"]:
                same["file_number"] += 1
            else:
                differs.append("legajo")
        if best.get("needs_review"):
            flagged += 1
            flagged_differs += bool(differs)
        else:
            sure += 1
            sure_differs += bool(differs)
            sure_by_field.update(differs)
        if differs:
            rows.setdefault(person["row"], []).append("distinto de la lectura: " + ", ".join(differs))
    share = lambda n, d: round(n / d, 4) if d else None  # noqa: E731
    result = {
        "people_in_spreadsheet": len(reference),
        "spreadsheet": counts,
        "found_in_reading": matched,
        "read_rows_without_a_person": sum(1 for record in records if id(record) not in used),
        "same_as_spreadsheet": {f: share(same[f], compared[f]) for f in ("name", "document", "file_number")},
        "compared": dict(compared),
        "rows_the_reading_gave_as_sure": {"rows": sure, "with_a_difference": sure_differs, "by_field": dict(sure_by_field)},
        "rows_the_reading_flagged": {"rows": flagged, "with_a_difference": flagged_differs},
    }
    return result, dict(sorted(rows.items()))
