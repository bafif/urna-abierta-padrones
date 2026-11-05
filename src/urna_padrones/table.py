"""Extract the rows of a scanned table, reading one column at a time."""

from dataclasses import dataclass, field
from pathlib import Path
from collections import Counter

import cv2
import numpy as np

from . import fields
from .grid import Grid, find_grid, straighten
from .ocr import read_cell
from .pdf import render_page

COLUMNS = ("order", "name", "program", "file_number", "document", "status")
SEPARATORS_EXPECTED = len(COLUMNS) + 1  # the signature column at the right is not read
CLEANERS = {
    "order": fields.clean_order,
    "name": fields.clean_name,
    "program": fields.clean_program,
    "file_number": fields.clean_file_number,
    "document": fields.clean_document,
    "status": fields.clean_status,
}
BLANK_INK_SHARE = 0.002
# Measured against two real rolls: below this, most names read differently in each one.
SURE_CONFIDENCE = 0.90
CONFIDENCE_CHECKED = ("name", "document", "file_number")


@dataclass
class Row:
    page: int
    position: int
    raw: dict[str, str] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)

    def checked(self, column: str) -> fields.Checked:
        return CLEANERS[column](self.raw.get(column, ""))

    def needs_review(self) -> bool:
        """A person reads this row if a value breaks its format or the model was not sure."""
        for column in COLUMNS:
            checked = self.checked(column)
            if not checked.valid or checked.repaired:
                return True
            doubtful = self.raw.get(column) and self.confidence.get(column, 1.0) < SURE_CONFIDENCE
            if doubtful and column in CONFIDENCE_CHECKED:
                return True
        return False


def select_separators(columns: list[int]) -> list[int] | None:
    """Keep the separators of the table; scans may add a line at the right edge of the page."""
    if len(columns) < SEPARATORS_EXPECTED:
        return None
    return columns[:SEPARATORS_EXPECTED]


def _cell(image: np.ndarray, grid: Grid, separators: list[int], row: int, index: int) -> np.ndarray:
    top, bottom = grid.rows[row]
    return image[max(0, top - 5) : bottom + 5, separators[index] + 5 : separators[index + 1] - 5]


def _is_blank(crop: np.ndarray) -> bool:
    return crop.size == 0 or float((crop < 128).mean()) < BLANK_INK_SHARE


def _read_row(straight: np.ndarray, clean: np.ndarray, grid: Grid, separators: list[int], row: Row) -> None:
    for index, column in enumerate(COLUMNS):
        crop = _cell(clean, grid, separators, row.position, index)
        if _is_blank(crop):
            continue
        text, confidence = read_cell(crop)
        row.raw[column] = text
        row.confidence[column] = confidence
        checked = row.checked(column)
        if checked.valid and not checked.repaired:
            continue
        # A doubtful cell gets a second chance: larger, and with the ruling lines left in,
        # because removing them may have cut a letter.
        original = _cell(straight, grid, separators, row.position, index)
        larger = cv2.resize(original, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        second, second_confidence = read_cell(larger)
        retried = CLEANERS[column](second)
        if retried.valid and not retried.repaired:
            row.raw[column] = second
            row.confidence[column] = second_confidence


def is_header(row: Row) -> bool:
    """A row is a person only if it has a number or a document: anything else is a heading."""
    has_order = row.checked("order").value is not None
    has_document = row.checked("document").value is not None
    named_like_header = fields.fold(row.raw.get("name", "")).startswith(("nombre", "apellido"))
    return named_like_header or not (has_order or has_document)


def infer_orders(rows: list[Row]) -> int:
    """Fix numbers that disagree with both neighbours, since numbering is consecutive."""
    fixed = 0
    numbers = [row.checked("order").value for row in rows]
    for i in range(1, len(rows) - 1):
        before, after = numbers[i - 1], numbers[i + 1]
        if before is None or after is None or int(after) != int(before) + 2:
            continue
        expected = str(int(before) + 1)
        if numbers[i] != expected:
            rows[i].raw["order"] = expected
            rows[i].confidence["order"] = -1.0
            numbers[i] = expected
            fixed += 1
    return fixed


def extract_page(gray: np.ndarray, page: int) -> list[Row]:
    straight, _ = straighten(gray)
    grid, clean = find_grid(straight)
    separators = select_separators(grid.columns)
    if separators is None or not grid.rows:
        return []
    rows = [Row(page=page, position=i) for i in range(len(grid.rows))]
    for row in rows:
        _read_row(straight, clean, grid, separators, row)
    return [r for r in rows if not is_header(r)]


def extract_file_page(args: tuple[Path, int]) -> list[Row]:
    path, index = args
    return extract_page(render_page(path, index), index + 1)


def edit_distance(a: str, b: str, limit: int = 4) -> int:
    """Levenshtein distance, giving up once it is known to exceed `limit`."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[-1] + 1, previous[j - 1] + (char_a != char_b)))
        if min(current) > limit:
            return limit + 1
        previous = current
    return previous[-1]


def build_vocabulary(values: list[str], minimum: int = 15) -> dict[str, str]:
    """Map misspellings of a repeated value (such as a degree) to its most frequent form.

    Similarity alone is not enough: «Eléctrica» and «Electrónica» are two different degrees
    and only two letters apart. A frequent value absorbs another frequent one only at a
    distance of one letter, and a rare value only if a single frequent value is closest.
    """
    counts = Counter(v for v in values if v)
    frequent = [v for v, n in counts.most_common() if n >= minimum]
    canonical: list[str] = []
    mapping: dict[str, str] = {}
    for value in frequent:
        twin = next((c for c in canonical if edit_distance(fields.fold(value), fields.fold(c), 1) <= 1), None)
        mapping[value] = twin or value
        if twin is None:
            canonical.append(value)
    for value in counts:
        if value in mapping:
            continue
        folded = fields.fold(value)
        allowed = min(3, max(1, len(folded) // 5))
        distances = sorted((edit_distance(folded, fields.fold(c), allowed), c) for c in canonical)
        if distances and distances[0][0] <= allowed and (len(distances) == 1 or distances[1][0] > distances[0][0]):
            mapping[value] = distances[0][1]
    return mapping


def smooth_by_neighbours(values: list[str | None], radius: int = 7) -> list[str | None]:
    """A roster is grouped by degree, so a value alone among its neighbours is a misreading."""
    smoothed: list[str | None] = []
    for index, value in enumerate(values):
        window = [v for v in values[max(0, index - radius) : index + radius + 1] if v]
        if not window:
            smoothed.append(value)
            continue
        best, count = Counter(window).most_common(1)[0]
        smoothed.append(best if count >= 0.6 * len(window) else value)
    return smoothed
