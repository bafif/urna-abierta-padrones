"""Quality figures for an extraction. Reports contain only counts, never personal data."""

import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from .fields import fold


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
