"""Quality figures for an extraction. Reports contain only counts, never personal data."""

import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from .fields import DOCUMENT, FILE_NUMBER, file_number_adds_up, fold
from .i18n import TEXTS

# What verify finds is said in Spanish here, and the command line says it in the language of its messages.
_SAYS = TEXTS["es"]


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


def _key_program(program: str | None) -> str:
    """A program as rows are compared: without case, accents or marks, keeping digits ("Plan 2010" is not "Plan 2023")."""
    return "".join(c for c in fold(program or "") if c.isalnum())


def _key_person(name: str | None) -> str:
    """A name as two rows of one person are compared: its words in any order, without case, accents or marks."""
    return " ".join(sorted(_key_name(name).split()))


SAME_PERSON = _SAYS["check.same_person"]


def _repeated(group: list[dict], other_name: str, by_file: bool) -> tuple[str, list[dict], bool]:
    """Rows that share a document or a legajo: one person in more than one program, or something to check.

    A student enrolled in two or three programs is in the roll once per program, with the same name, and votes
    once. It is the same person only when the name is the same (case, marks and word order aside): Juan and Juana
    with one document are two people, one of them with a document typed wrong. Returns what to say, the rows to say
    it about, and whether the group holds one person in more than one program.
    """
    names = {_key_person(p["name"]) for p in group}
    if len(names) > 1 or not next(iter(names)):
        return other_name, group, False
    if by_file and len({p["document"] for p in group if p["document"]}) > 1:
        # The same legajo and name with two documents: one of the documents is wrong.
        return _SAYS["check.file_number_other_document"], group, False
    keys = [_key_program(p.get("program")) for p in group]
    programs = Counter(keys)
    # Without a program, or with the same one, there is no telling the rows apart: the person was typed twice.
    twice = group if "" in programs else [p for p, key in zip(group, keys) if programs[key] > 1]
    return _SAYS["check.repeated_row"], twice, len(programs.keys() - {""}) > 1


def _reference_checks(reference: list[dict]) -> tuple[dict, dict[int, list[str]]]:
    """What is odd in the spreadsheet itself, as counts and as the rows to look at."""
    rows: dict[int, list[str]] = {}

    def note(person: dict, what: str) -> None:
        found = rows.setdefault(person["row"], [])
        if what not in found:
            found.append(what)

    by_document: dict[str, list[dict]] = {}
    by_file: dict[str, list[dict]] = {}
    for person in reference:
        if not person["document"]:
            note(person, _SAYS["check.no_document"])
        elif not DOCUMENT.match(person["document"]):
            note(person, _SAYS["check.bad_document"])
        else:
            by_document.setdefault(person["document"], []).append(person)
        if person["file_number"]:
            if not FILE_NUMBER.match(person["file_number"]):
                note(person, _SAYS["check.bad_file_number"])
            elif not file_number_adds_up(person["file_number"]):
                note(person, _SAYS["check.file_number_digit"])
            by_file.setdefault(person["file_number"], []).append(person)
    in_programs = 0
    counted: set[int] = set()  # rows already counted as one person in more than one program
    for groups, other_name in (
        (by_document, _SAYS["check.document_other_name"]),
        (by_file, _SAYS["check.file_number_other_name"]),
    ):
        for group in groups.values():
            if len(group) < 2:
                continue
            what, to_check, one_person = _repeated(group, other_name, groups is by_file)
            for person in to_check:
                note(person, what)
            if one_person:
                group_rows = {p["row"] for p in group}
                in_programs += not group_rows & counted
                counted |= group_rows
    counts = Counter(what for found in rows.values() for what in found)
    if in_programs:
        counts[SAME_PERSON] = in_programs
    return dict(counts), rows


def verify(records: list[dict], reference: list[dict]) -> tuple[dict, dict[int, list[str]]]:
    """Compare a reading with a roll typed into a spreadsheet, and say where they differ.

    A person of the spreadsheet is matched to a read row when two of document, legajo and name agree, so a
    difference in any one of them still finds its row; among equally good rows it prefers one not taken yet and then
    one of the same program. A difference may come from the reading or from the spreadsheet: the figures say how
    many, never what. Returns the counts and, by spreadsheet row, what to check.
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
        program = _key_program(person.get("program"))
        candidates = by_document.get(person["document"], []) + by_file.get(person["file_number"], []) + by_name.get(name, [])
        best, best_rank = None, None
        for record in candidates:
            votes = (
                bool(person["document"]) and record.get("document") == person["document"],
                bool(person["file_number"]) and record.get("file_number") == person["file_number"],
                _similar(_key_name_compact(record.get("name")), name),
            )
            # Someone in two programs is read twice: each row of the spreadsheet takes a read row of its own when it
            # can, the one of its program if the reading has programs, before the one with more votes. Otherwise
            # both rows would take the clean read row and a misread in the other would never show. The program is
            # never a vote: two votes are always needed.
            rank = (
                id(record) not in used,
                bool(program) and _key_program(record.get("program")) == program,
                sum(votes),
            )
            if sum(votes) >= 2 and (best_rank is None or rank > best_rank):
                best, best_rank = record, rank
        if best is None:
            rows.setdefault(person["row"], []).append(_SAYS["check.not_read"])
            continue
        matched += 1
        used.add(id(best))
        differs = []
        compared["name"] += 1
        if _key_name_compact(best.get("name")) == name:
            same["name"] += 1
        else:
            differs.append(_SAYS["field.name"])
        if person["document"]:
            compared["document"] += 1
            if best.get("document") == person["document"]:
                same["document"] += 1
            else:
                differs.append(_SAYS["field.document"])
        if person["file_number"] and best.get("file_number"):
            compared["file_number"] += 1
            if best["file_number"] == person["file_number"]:
                same["file_number"] += 1
            else:
                differs.append(_SAYS["field.file_number"])
        if best.get("needs_review"):
            flagged += 1
            flagged_differs += bool(differs)
        else:
            sure += 1
            sure_differs += bool(differs)
            sure_by_field.update(differs)
        if differs:
            rows.setdefault(person["row"], []).append(_SAYS["check.differs"].format(fields=", ".join(differs)))
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
