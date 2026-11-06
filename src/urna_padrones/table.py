"""Extract the rows of a table, reading one column at a time.

The columns of a scanned table are found by the names in its header row. A table whose header names
nothing this program knows is read as the faculty's rolls are laid out, exactly as before headers
were looked at.
"""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

import cv2
import numpy as np

from . import fields
from .grid import Grid, even_out_light, find_grid, straighten
from .headers import Header, mesa_in, recognise
from .ocr import read_cell

COLUMNS = ("order", "name", "program", "file_number", "document", "status")
# Values that only a roll found by its header can have. The extraction lists them after COLUMNS.
EXTRA = ("table", "address")
SEPARATORS_EXPECTED = len(COLUMNS) + 1  # the signature column at the right is not read
CLEANERS = {
    "order": fields.clean_order,
    "name": fields.clean_name,
    "program": fields.clean_program,
    "file_number": fields.clean_file_number,
    "document": fields.clean_document,
    "status": fields.clean_status,
}
# A roll found by its header has the same values, written in more ways than the faculty's.
HEADER_CLEANERS = {
    **CLEANERS,
    "name": fields.clean_name_any,
    "document": fields.clean_document_typed,
    "file_number": fields.clean_file_number_any,
    "status": fields.clean_status_any,
    "table": fields.clean_table,
    "address": fields.clean_address,
    "family": fields.clean_name_part,
    "given": fields.clean_name_part,
}
FACULTY = "facultad"
BY_HEADER = "encabezado"
BLANK_INK_SHARE = 0.002
# Measured against two real rolls: below this, most names read differently in each one.
SURE_CONFIDENCE = 0.90
CONFIDENCE_CHECKED = ("name", "document", "file_number")
# The header is looked for in the first rows of the table: a title may come before it, or the header may
# take two lines.
HEADER_ROWS = 3
# A title above the table is looked for in its last lines, of a height text can have.
TITLE_LINES = 4
TITLE_HEIGHT = (12, 160)
# Words of a title further apart than this, in pixels, are read separately.
TITLE_GAP = 80


def cleaner(column: str, layout: str = FACULTY) -> Callable[[str], fields.Checked]:
    """How a value of `column` is cleaned and checked in a roll read with `layout`."""
    return (CLEANERS if layout == FACULTY else HEADER_CLEANERS)[column]


@dataclass
class Row:
    page: int
    position: int
    raw: dict[str, str] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    # Where the row is on the straightened page: top, bottom, left, right, in pixels.
    band: tuple[int, int, int, int] | None = None
    # Degrees the page was rotated to straighten it, to rebuild the same image later.
    skew: float = 0.0
    # The faculty's layout or a header, and the values the roll has with it.
    layout: str = FACULTY
    columns: tuple[str, ...] = COLUMNS
    # "ocr" when the values were read from an image, "text" when they are the text of a PDF, exact.
    source: str = "ocr"
    # The table a title such as «Mesa 12» gives to the whole page, for a row without a table of its own.
    title_table: str | None = None

    def checked(self, column: str) -> fields.Checked:
        return cleaner(column, self.layout)(self.raw.get(column, ""))

    def needs_review(self) -> bool:
        """A person reads this row if a value breaks its format or the model was not sure."""
        for column in self.columns:
            checked = self.checked(column)
            if not checked.valid or checked.repaired:
                return True
            doubtful = self.raw.get(column) and self.confidence.get(column, 1.0) < SURE_CONFIDENCE
            if doubtful and column in CONFIDENCE_CHECKED:
                return True
        return False


@dataclass
class PageReading:
    """What one page gave: its people, and what a page of the same roll without a header can take from it."""

    rows: list[Row]
    # The header the page has, unless it is the faculty's layout, which needs no header.
    header: Header | None = None
    # How many column lines its table has: a page without a header takes only a header with as many columns.
    separators: int = 0
    # The columns of a page with text, found by its header (see textlayer).
    text_columns: object | None = None
    # Whether the PDF page has text at all, even when it gave no rows.
    has_text: bool = False


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


def _read_row(
    straight: np.ndarray,
    clean: np.ndarray,
    grid: Grid,
    separators: list[int],
    row: Row,
    cells: list[tuple[int, str]],
) -> None:
    """Read the cells of a row: `cells` says which column of the table holds which value."""
    for index, column in cells:
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
        retried = cleaner(column, row.layout)(second)
        if retried.valid and not retried.repaired:
            row.raw[column] = second
            row.confidence[column] = second_confidence


def is_header(row: Row) -> bool:
    """A row is a person only if it has a number or a document: anything else is a heading."""
    has_order = row.checked("order").value is not None
    has_document = row.checked("document").value is not None
    named_like_header = fields.fold(row.raw.get("name", "")).startswith(("nombre", "apellido"))
    return named_like_header or not (has_order or has_document)


def join_name(row: Row) -> None:
    """A roll with the family name and the given names in two columns gets one name, «Family, Given»."""
    parts = [fields.clean_name_part(row.raw.pop(key, "")).value for key in ("family", "given")]
    scores = [row.confidence.pop(key) for key in ("family", "given") if key in row.confidence]
    if any(parts):
        row.raw["name"] = ", ".join(part for part in parts if part)
        row.confidence["name"] = min(scores, default=1.0)


def is_person(row: Row) -> bool:
    """In a roll found by its header, a row is a person when it has a document, or a name with a number or a
    name that looks like one. Anything else, such as a repeated header or a page footer, is not."""
    name = row.checked("name")
    if fields.fold(row.raw.get("name", "")).startswith(("nombre", "apellido")):
        return False
    if row.checked("document").value is not None:
        return True
    numbered = any(row.checked(column).value is not None for column in ("order", "file_number"))
    return bool(name.value) and (numbered or name.valid)


def fits_faculty(header: Header) -> bool:
    """Whether every column a header names is where the faculty's layout has it."""
    return all(key is None or (i < len(COLUMNS) and COLUMNS[i] == key) for i, key in enumerate(header.keys))


def find_header(clean: np.ndarray, grid: Grid, checkpoint: Callable[[], None]) -> tuple[Header | None, int]:
    """The header among the first rows of the table and the row it ends on, or (None, -1).

    A header split over two lines, such as «Nro. de» over «documento», is read as one.
    """
    if len(grid.columns) < 3:
        return None, -1
    previous: list[str] | None = None
    for position in range(min(HEADER_ROWS, len(grid.rows))):
        checkpoint()
        texts = []
        for index in range(len(grid.columns) - 1):
            crop = _cell(clean, grid, grid.columns, position, index)
            texts.append("" if _is_blank(crop) else read_cell(crop)[0])
        header = recognise(texts, fuzzy=True)
        if header is None and previous is not None:
            header = recognise([f"{above} {below}".strip() for above, below in zip(previous, texts)], fuzzy=True)
        if header is not None:
            return header, position
        previous = texts
    return None, -1


def title_table(image: np.ndarray, top: int, checkpoint: Callable[[], None]) -> str | None:
    """The table a title above the table gives to the whole page, such as «Mesa Nº 12», or None.

    The last lines above the table are read, each in stretches split where the words are far apart.
    """
    region = image[: max(0, top - 8)]
    if region.size == 0:
        return None
    ink = region < 128
    on = np.where(ink.sum(axis=1) >= 3)[0]
    if on.size == 0:
        return None
    bands = [(int(g[0]), int(g[-1]) + 1) for g in np.split(on, np.where(np.diff(on) > 2)[0] + 1)]
    bands = [(a, b) for a, b in bands if TITLE_HEIGHT[0] <= b - a <= TITLE_HEIGHT[1]][-TITLE_LINES:]
    for start, stop in bands:
        checkpoint()
        columns = np.where(ink[start:stop].any(axis=0))[0]
        pieces = np.split(columns, np.where(np.diff(columns) > TITLE_GAP)[0] + 1)
        texts = []
        for piece in pieces:
            crop = region[max(0, start - 4) : stop + 4, max(0, piece[0] - 6) : piece[-1] + 7]
            texts.append(read_cell(crop)[0])
        found = mesa_in(" ".join(texts))
        if found:
            return found
    return None


def infer_orders(rows: list[Row]) -> int:
    """Fix numbers that disagree with both neighbours, since numbering is consecutive.

    A number taken from the text of a PDF is exact and is never changed.
    """
    fixed = 0
    numbers = [row.checked("order").value for row in rows]
    for i in range(1, len(rows) - 1):
        before, after = numbers[i - 1], numbers[i + 1]
        if before is None or after is None or int(after) != int(before) + 2 or rows[i].source == "text":
            continue
        expected = str(int(before) + 1)
        if numbers[i] != expected:
            rows[i].raw["order"] = expected
            rows[i].confidence["order"] = -1.0
            numbers[i] = expected
            fixed += 1
    return fixed


def _band(rows: tuple[int, int], separators: list[int], shape: tuple[int, ...]) -> tuple[int, int, int, int]:
    """The row from its first to its last read column, kept inside the page."""
    top, bottom = rows
    height, width = shape[:2]
    return max(0, top), min(height, bottom), max(0, separators[0]), min(width, separators[-1])


def _faculty_rows(
    straight: np.ndarray, clean: np.ndarray, grid: Grid, page: int, angle: float, checkpoint: Callable[[], None]
) -> list[Row]:
    """The rows of a table laid out as the faculty's rolls: COLUMNS in this order, then the signature."""
    separators = select_separators(grid.columns)
    if separators is None or not grid.rows:
        return []
    rows = [
        Row(page=page, position=i, band=_band(grid.rows[i], separators, straight.shape), skew=angle)
        for i in range(len(grid.rows))
    ]
    cells = list(enumerate(COLUMNS))
    for row in rows:
        checkpoint()
        _read_row(straight, clean, grid, separators, row, cells)
    return [r for r in rows if not is_header(r)]


def _header_rows(
    straight: np.ndarray,
    clean: np.ndarray,
    grid: Grid,
    header: Header,
    start: int,
    page: int,
    angle: float,
    checkpoint: Callable[[], None],
) -> list[Row]:
    """The rows from `start` on of a table whose columns a header named. Columns it did not name are not read."""
    separators = grid.columns
    cells = [(i, key) for i, key in enumerate(header.keys) if key and i + 1 < len(separators)]
    rows = []
    for position in range(start, len(grid.rows)):
        checkpoint()
        band = _band(grid.rows[position], separators, straight.shape)
        row = Row(page=page, position=position, band=band, skew=angle, layout=BY_HEADER, columns=header.fields())
        _read_row(straight, clean, grid, separators, row, cells)
        join_name(row)
        rows.append(row)
    return [row for row in rows if is_person(row)]


def read_page(
    gray: np.ndarray,
    page: int,
    checkpoint: Callable[[], None] | None = None,
    header: Header | None = None,
    photo: bool = False,
) -> PageReading:
    """Read the rows of one scanned page, and the table its title gives them, if any.

    The page's own header says which column holds what. Without one, `header` (from another page of the
    same roll) does, and without either the page is read as the faculty's layout. A header that puts
    every column it names where the faculty's layout has it is read as that layout too, so those rolls
    give exactly what they gave before. A `photo` has its light evened out first. `checkpoint` runs
    before each step of the page and before each row: raising from it abandons the page.
    """
    checkpoint = checkpoint or (lambda: None)
    checkpoint()
    if photo:
        gray = even_out_light(gray)
    straight, angle = straighten(gray)
    checkpoint()
    grid, clean = find_grid(straight)
    own, start = (None, -1) if header is not None else find_header(clean, grid, checkpoint)
    chosen = header or own
    if chosen is None or (own is not None and fits_faculty(own) and select_separators(grid.columns) is not None):
        rows, found = _faculty_rows(straight, clean, grid, page, angle, checkpoint), None
    else:
        rows, found = _header_rows(straight, clean, grid, chosen, start + 1, page, angle, checkpoint), own
    if rows and grid.rows:
        mesa = title_table(clean, grid.rows[0][0], checkpoint)
        for row in rows:
            row.title_table = mesa
    return PageReading(rows, header=found, separators=len(grid.columns))


def extract_page(gray: np.ndarray, page: int, checkpoint: Callable[[], None] | None = None) -> list[Row]:
    """The rows of one scanned page (see read_page)."""
    return read_page(gray, page, checkpoint).rows


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
