"""Read a PDF page that has real text: its words, where each one is, and the table they make.

A PDF exported from a spreadsheet or a database has the text itself, not a picture of it. Its words
are taken as they are, with nothing to recognise and nothing to doubt, and the table is rebuilt from
where they are: rows by their baseline, and columns by where the names of the header are.

Text a scanner adds on top of its picture, invisible, is not taken: it is the scanner's own reading,
and the page is read from its picture like any other scan. Neither is visible text on a page that is a
picture, such as a stamp, unless it names its columns itself.
"""

import ctypes
import math
import statistics
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from .errors import RollError
from .fields import ASCII_DIGITS
from .headers import IDENTIFYING, Header, mesa_in, recognise, split_labels
from .pdf import PDFIUM_LOCK, TARGET_DPI
from .table import BY_HEADER, PageReading, Row, has_number, is_person, join_name

# A page with fewer visible letters than this has no table worth reading from its text.
MIN_CHARACTERS = 20
# Words further apart than this share of the font size are in different cells. A space is about 0.28.
CELL_GAP = 0.5
# Letters further apart than this share of the font size are different words.
WORD_GAP = 0.25
# A wrapped line this much closer to one row than to the other is surely of the closer one (see _join_wrapped).
WRAP_SURE = 0.85
# A line without a number this many rows away from the people is a title or a footer.
EDGE_ROWS = 1.5
# A page whose pictures cover this share of it is a scan.
SCAN_SHARE = 0.8
# Text this light on every channel does not show on paper.
WHITE = 245
LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})


@dataclass(frozen=True)
class Word:
    """A word and its box, in pixels of the page rendered at TARGET_DPI, counted from the top left."""

    text: str
    left: float
    right: float
    top: float
    bottom: float
    baseline: float
    size: float


@dataclass(frozen=True)
class TextPage:
    width: int
    height: int
    words: list[Word]
    # Whether pictures cover most of the page, as in a scan: its text is a stamp or a scanner's reading, and is
    # read only when it names its columns itself.
    scanned: bool = False


@dataclass(frozen=True)
class TextColumns:
    """The columns of a roll with text: each name of its header, from where to where it is, and its key."""

    spans: tuple[tuple[float, float, str | None], ...]
    header: Header


def page_text(path: Path, index: int, dpi: int = TARGET_DPI) -> TextPage | None:
    """The visible words of a page, upright as the page is shown, or None when it has too few: a scan, or a page with
    only a stamp.

    A page turned by the PDF, as a viewer saves a landscape page, has its words turned with it, like its picture.
    Text written at an angle is left out, and so is text that does not show: invisible, only a clipping path,
    white, or drawn under a picture that covers it, as some scanners leave their own reading.
    """
    scale = dpi / 72
    with PDFIUM_LOCK:
        try:
            document = pdfium.PdfDocument(path)
        except pdfium.PdfiumError as error:
            raise RollError("damaged") from error
        try:
            page = document[index]
            try:
                rotation = page.get_rotation() % 360
                crop = page.get_cropbox()
                hidden, pictures = _objects(page.raw, crop)
                textpage = page.get_textpage()
                try:
                    characters = _characters(textpage, hidden, rotation, crop)
                finally:
                    textpage.close()
            finally:
                page.close()
        except pdfium.PdfiumError as error:
            raise RollError("damaged") from error
        finally:
            document.close()
    if sum(1 for c in characters if c is not None) < MIN_CHARACTERS:
        return None
    left, bottom, right, top = crop
    width, height = (top - bottom, right - left) if rotation in (90, 270) else (right - left, top - bottom)
    words = []
    for group in _word_groups(characters):
        text = unicodedata.normalize("NFC", "".join(c[0] for c in group).translate(LIGATURES))
        size = max(c[6] for c in group)
        baseline = statistics.median(c[5] for c in group)
        words.append(
            Word(
                text=text,
                left=min(c[1] for c in group) * scale,
                right=max(c[2] for c in group) * scale,
                top=(height - max(c[4] for c in group)) * scale,
                bottom=(height - min(c[3] for c in group)) * scale,
                baseline=(height - baseline) * scale,
                size=size * scale,
            )
        )
    scanned = pictures >= SCAN_SHARE * (right - left) * (top - bottom)
    return TextPage(width=round(width * scale), height=round(height * scale), words=words, scanned=scanned)


Character = tuple[str, float, float, float, float, float, float]


def _turn(rotation: int, crop: tuple[float, float, float, float]):
    """From a point of the PDF page to the same point on the page as it is shown, both in points from the bottom left."""
    left, bottom, right, top = crop
    if rotation == 90:
        return lambda x, y: (y - bottom, right - x)
    if rotation == 180:
        return lambda x, y: (right - x, top - y)
    if rotation == 270:
        return lambda x, y: (top - y, x - left)
    return lambda x, y: (x - left, y - bottom)


def _characters(
    textpage: pdfium.PdfTextPage, hidden: set[int], rotation: int, crop: tuple[float, float, float, float]
) -> list[Character | None]:
    """Each character as (text, left, right, bottom, top, baseline, size) in points on the page as it is shown, or
    None for a break.

    Spaces, line ends, text that does not show, text in the objects `hidden` and text at an angle are breaks.
    """
    raw = textpage.raw
    turn = _turn(rotation, crop)
    # Upright text on a page the PDF turns clockwise runs at that angle the other way on the page itself. PDFium
    # measures angles clockwise.
    upright = math.radians((360 - rotation) % 360)
    x, y = ctypes.c_double(), ctypes.c_double()
    box = pdfium_c.FS_RECTF()
    shows: dict[int, bool] = {}
    found: list[Character | None] = []
    for index in range(pdfium_c.FPDFText_CountChars(raw)):
        code = pdfium_c.FPDFText_GetUnicode(raw, index)
        text = chr(code) if 0 < code < 0x110000 else ""
        if not text.strip() or pdfium_c.FPDFText_IsGenerated(raw, index) == 1:
            found.append(None)
            continue
        item = pdfium_c.FPDFText_GetTextObject(raw, index)
        address = _address(item)
        if address is not None and address not in shows:
            shows[address] = address not in hidden and _shows(item)
        angle = pdfium_c.FPDFText_GetCharAngle(raw, index)
        off = (angle - upright) % (2 * math.pi)
        if not shows.get(address, True) or angle < 0 or min(off, 2 * math.pi - off) > 0.02:
            found.append(None)
            continue
        if not pdfium_c.FPDFText_GetLooseCharBox(raw, index, ctypes.byref(box)):
            found.append(None)
            continue
        pdfium_c.FPDFText_GetCharOrigin(raw, index, ctypes.byref(x), ctypes.byref(y))
        size = pdfium_c.FPDFText_GetFontSize(raw, index) or (box.top - box.bottom)
        (x0, y0), (x1, y1) = turn(box.left, box.bottom), turn(box.right, box.top)
        found.append((text, min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), turn(x.value, y.value)[1], size))
    return found


def _address(item) -> int | None:
    return ctypes.cast(item, ctypes.c_void_p).value if item else None


def _bounds(item) -> tuple[float, float, float, float] | None:
    left, bottom, right, top = (ctypes.c_float() for _ in range(4))
    if not pdfium_c.FPDFPageObj_GetBounds(item, *(ctypes.byref(v) for v in (left, bottom, right, top))):
        return None
    return left.value, bottom.value, right.value, top.value


def _has_picture(form, depth: int = 0) -> bool:
    """Whether a group of drawings (a form) holds a picture, as some scanners wrap theirs."""
    for index in range(pdfium_c.FPDFFormObj_CountObjects(form)):
        item = pdfium_c.FPDFFormObj_GetObject(form, index)
        kind = pdfium_c.FPDFPageObj_GetType(item)
        if kind == pdfium_c.FPDF_PAGEOBJ_IMAGE:
            return True
        if kind == pdfium_c.FPDF_PAGEOBJ_FORM and depth < 4 and _has_picture(item, depth + 1):
            return True
    return False


def _objects(page, crop: tuple[float, float, float, float]) -> tuple[set[int], float]:
    """The text drawn under a picture that covers it, as object addresses, and how much of the page pictures cover,
    in square points. The page draws its objects in order: a later one covers an earlier one."""
    left, bottom, right, top = crop
    pictures: list[tuple[int, tuple[float, float, float, float]]] = []
    texts: list[tuple[int, int, tuple[float, float, float, float]]] = []
    for index in range(pdfium_c.FPDFPage_CountObjects(page)):
        item = pdfium_c.FPDFPage_GetObject(page, index)
        kind = pdfium_c.FPDFPageObj_GetType(item)
        bounds = _bounds(item)
        if bounds is None:
            continue
        if kind == pdfium_c.FPDF_PAGEOBJ_IMAGE or (kind == pdfium_c.FPDF_PAGEOBJ_FORM and _has_picture(item)):
            pictures.append((index, bounds))
        elif kind == pdfium_c.FPDF_PAGEOBJ_TEXT:
            texts.append((index, _address(item), bounds))
    hidden = {
        address
        for index, address, box in texts
        if any(later > index and _inside(box, cover) for later, cover in pictures)
    }
    area = sum(
        max(0.0, min(r, right) - max(l, left)) * max(0.0, min(t, top) - max(b, bottom)) for _, (l, b, r, t) in pictures
    )
    return hidden, area


def _inside(box: tuple[float, float, float, float], cover: tuple[float, float, float, float]) -> bool:
    return box[0] >= cover[0] - 1 and box[1] >= cover[1] - 1 and box[2] <= cover[2] + 1 and box[3] <= cover[3] + 1


# Text render modes: which ones fill the letters and which ones stroke them. Modes 3 (invisible) and 7 (only a
# clipping path) paint nothing.
FILLED_MODES = (0, 2, 4, 6)
STROKED_MODES = (1, 2, 5, 6)


def _shows(item) -> bool:
    """Whether a text object paints its letters in a color that shows on paper."""
    mode = pdfium_c.FPDFTextObj_GetTextRenderMode(item)
    if mode < 0:
        return True
    filled = mode in FILLED_MODES and _inked(pdfium_c.FPDFPageObj_GetFillColor, item)
    stroked = mode in STROKED_MODES and _inked(pdfium_c.FPDFPageObj_GetStrokeColor, item)
    return filled or stroked


def _inked(color, item) -> bool:
    channels = [ctypes.c_uint() for _ in range(4)]
    if not color(item, *(ctypes.byref(c) for c in channels)):
        return True
    red, green, blue, alpha = (c.value for c in channels)
    return alpha > 0 and min(red, green, blue) < WHITE


def _word_groups(characters: list[Character | None]) -> list[list[Character]]:
    """Characters in the order the PDF draws them, split into words at breaks, gaps and jumps."""
    groups: list[list[Character]] = []
    current: list[Character] = []
    for character in characters:
        if character is not None and current:
            last = current[-1]
            size = max(character[6], last[6])
            jump = abs(character[5] - last[5]) > 0.4 * size
            gap = character[1] - last[2] > WORD_GAP * size or character[1] < last[1] - 0.1 * size
            if jump or gap:
                groups.append(current)
                current = []
        if character is None:
            if current:
                groups.append(current)
            current = []
        else:
            current.append(character)
    if current:
        groups.append(current)
    return groups


def lines_of(words: list[Word]) -> list[list[Word]]:
    """Words in lines, from the top of the page, each from left to right. A line is the words on one baseline."""
    if not words:
        return []
    size = statistics.median(word.size for word in words)
    lines: list[list[Word]] = []
    for word in sorted(words, key=lambda w: w.baseline):
        if lines and word.baseline - lines[-1][0].baseline <= 0.4 * size:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [sorted(line, key=lambda w: w.left) for line in lines]


def _joined(line: list[Word]) -> list[bool]:
    """Whether each word is close enough to the next one to be in the same cell."""
    return [after.left - before.right <= CELL_GAP * max(before.size, after.size) for before, after in zip(line, line[1:])]


def header_columns(line: list[Word]) -> TextColumns | None:
    """The columns a line names when it is the header of a roll, or None."""
    labels = split_labels([word.text for word in line], _joined(line))
    header = recognise([" ".join(word.text for word in line[start:stop]) for start, stop in labels])
    if header is None:
        return None
    spans = tuple((line[start].left, line[stop - 1].right, key) for (start, stop), key in zip(labels, header.keys))
    return TextColumns(spans=spans, header=header)


def _overlap(left: float, right: float, span: tuple[float, float, str | None]) -> float:
    return min(right, span[1]) - max(left, span[0])


def _distance(left: float, right: float, span: tuple[float, float, str | None]) -> float:
    return max(span[0] - right, left - span[1], 0.0)


def _column_of(left: float, right: float, spans: tuple[tuple[float, float, str | None], ...]) -> int:
    """The column a stretch of a row belongs to: the name it is under most, or else the nearest one."""
    overlaps = [_overlap(left, right, span) for span in spans]
    best = max(range(len(spans)), key=lambda i: overlaps[i])
    if overlaps[best] > 0:
        return best
    return min(range(len(spans)), key=lambda i: (_distance(left, right, spans[i]), i))


def _identified(row: Row) -> bool:
    return any(has_number(row, column) for column in IDENTIFYING if column in row.columns)


def _text(line: list[Word]) -> str:
    return " ".join(word.text for word in line)


def _cells(line: list[Word]) -> list[list[Word]]:
    """The words of a line in cells: words close together are one cell."""
    cells: list[list[Word]] = [[line[0]]] if line else []
    for word, close in zip(line[1:], _joined(line)):
        if close:
            cells[-1].append(word)
        else:
            cells.append([word])
    return cells


def _owners(segments: list[list[float]], spans: tuple[tuple[float, float, str | None], ...]) -> list[int | None]:
    """The column of each stretch of the page that the rows fill, or None when it is under several names.

    A stretch under no name goes to the name on its left or on its right that has no stretch under it:
    numbers aligned to the right of their column often end up beside a name aligned to the left.
    """
    under = [[i for i, span in enumerate(spans) if _overlap(left, right, span) > 0] for left, right in segments]
    taken = {names[0] for names in under if len(names) == 1}
    owners: list[int | None] = []
    for (left, right), names in zip(segments, under):
        if names:
            owners.append(names[0] if len(names) == 1 else None)
            continue
        before = [i for i, span in enumerate(spans) if span[1] <= left]
        after = [i for i, span in enumerate(spans) if span[0] >= right]
        sides = ([before[-1]] if before else []) + ([after[0]] if after else [])
        free = [i for i in sides if i not in taken]
        if len(free) == 1:
            owners.append(free[0])
        else:
            owners.append(min(sides or range(len(spans)), key=lambda i: _distance(left, right, spans[i])))
    return owners


def cells_of(lines: list[list[Word]], columns: TextColumns) -> list[dict[str, str]]:
    """The values of each row: each word goes to the column whose name it is under.

    The columns are the stretches of the page that the words of the rows fill, with the gaps between
    them, and the header only names them. That way a short value under a wide name, or a number aligned
    to the right under a name aligned to the left, still goes to its column. A stretch under two names,
    or a word outside every stretch, such as a footer, goes to the name the word is under or nearest.
    """
    spans = columns.spans
    # A line with a single cell may be a title or a footer across the columns: it does not make stretches. A cell
    # makes one stretch, not one per word: the end of a long name, past the end of its name in the header, stays
    # with the rest of the name.
    stretches = sorted(
        (cell[0].left, cell[-1].right) for line in lines if len(cells := _cells(line)) >= 2 for cell in cells
    )
    segments: list[list[float]] = []
    for left, right in stretches:
        if segments and left <= segments[-1][1]:
            segments[-1][1] = max(segments[-1][1], right)
        else:
            segments.append([left, right])
    owners = _owners(segments, spans)
    found = []
    for line in lines:
        values: dict[int, list[str]] = {}
        for word in line:
            inside = [i for i, (a, b) in enumerate(segments) if a <= word.left and word.right <= b]
            owner = owners[inside[0]] if inside else None
            if owner is None:
                owner = _column_of(word.left, word.right, spans)
            values.setdefault(owner, []).append(word.text)
        found.append({spans[i][2]: " ".join(texts) for i, texts in values.items() if spans[i][2]})
    return found


def first_columns(text: TextPage) -> TextColumns | None:
    """The columns the first header line of a page names, or None."""
    return next((found for found in map(header_columns, lines_of(text.words)) if found is not None), None)


def read_text_page(text: TextPage, page: int, columns: TextColumns | None = None) -> PageReading:
    """The people on a page with text.

    The page's own header gives the columns; without one, `columns` from another page of the same roll
    does. Without either the page gives no rows, and is read from its picture.
    """
    lines = lines_of(text.words)
    own = None
    start = 0
    for index, line in enumerate(lines):
        own = header_columns(line)
        if own is not None:
            start = index + 1
            break
    chosen = own or columns
    if chosen is None:
        return PageReading([], has_text=True)
    left = min(span[0] for span in chosen.spans)
    right = max(span[1] for span in chosen.spans)
    fields = chosen.header.fields()
    # A title such as «Mesa Nº 12» above the header gives its table to the page. A line with only such a
    # title, among the rows, starts another table: a listing sorted by table often has one before each.
    above = lines[: start - 1] if own is not None else []
    table = next((found for found in (mesa_in(_text(line)) for line in above) if found), None)
    body = lines[start:]
    entries = [
        _Entry(line, values, _baseline(line), _baseline(line), mesa_in(_text(line)) if len(_cells(line)) == 1 else None)
        for line, values in zip(body, cells_of(body, chosen))
    ]
    size = statistics.median(word.size for line in body for word in line) if body else 0.0
    rows = []
    for entry in _join_wrapped(entries, size):
        if entry.mesa:
            table = entry.mesa
            continue
        row = Row(page=page, position=len(rows), raw=entry.values, layout=BY_HEADER, columns=fields, source="text")
        join_name(row)
        row.confidence = {key: 1.0 for key in row.raw}
        row.unsure = entry.unsure
        # On a page that borrows its columns, such as a cover letter in a listing, a name alone is not enough.
        if not is_person(row) or (own is None and not _identified(row)):
            continue
        row.title_table = table
        words = entry.words
        margin = 0.3 * statistics.median(word.size for word in words)
        row.band = (
            max(0, round(min(word.top for word in words) - margin)),
            min(text.height, round(max(word.bottom for word in words) + margin)),
            max(0, round(min(left, min(word.left for word in words)) - margin)),
            min(text.width, round(max(right, max(word.right for word in words)) + margin)),
        )
        rows.append(row)
    return PageReading(rows, text_columns=own, has_text=True)


@dataclass
class _Entry:
    """A line among the rows of a page, or the lines of one row when a cell takes more than one, with its values."""

    words: list[Word]
    values: dict[str, str]
    # The baselines of its first and last line.
    top: float
    bottom: float
    # The table a line such as «Mesa 13» starts, for a line that is only that.
    mesa: str | None = None
    unsure: bool = False


def _baseline(line: list[Word]) -> float:
    return statistics.median(word.baseline for word in line)


def _numbered(values: dict[str, str]) -> bool:
    return any(c in ASCII_DIGITS for key in IDENTIFYING for c in values.get(key, ""))


def _join_wrapped(entries: list[_Entry], size: float) -> list[_Entry]:
    """The rows of a page, with the lines of a cell that wraps joined to their row, and without titles and footers.

    A line without a number of its own (no order, document or legajo) is the rest of a cell when it is closer to
    the row above or below it than one row is to the next: a long name wraps onto a second line, below the rest
    of the row when the cells are aligned to the top and above it when they are aligned to the bottom, as a
    spreadsheet does. It goes to the closer row; when the other one is nearly as close, that row is left for review.
    Such a line further than EDGE_ROWS rows above the first person or below the last one is a title or a footer,
    such as «Firma del presidente de mesa», and is dropped. Any other line stays as it is.
    """
    people = [index for index, entry in enumerate(entries) if entry.mesa is None and _numbered(entry.values)]
    if not people:
        return entries
    gaps = [entries[b].top - entries[a].bottom for a, b in zip(people, people[1:])]
    pitch = statistics.median(gaps) if gaps else 2 * size
    reach = 0.95 * pitch
    numbered = set(people)
    dropped: set[int] = set()
    start = 0
    while start < len(entries):
        if entries[start].mesa is not None or start in numbered:
            start += 1
            continue
        stop = start
        while (
            stop + 1 < len(entries)
            and entries[stop + 1].mesa is None
            and stop + 1 not in numbered
            and entries[stop + 1].top - entries[stop].bottom <= reach
        ):
            stop += 1
        run = list(range(start, stop + 1))
        before = start - 1 if start - 1 in numbered else None
        after = stop + 1 if stop + 1 in numbered else None
        up = entries[start].top - entries[before].bottom if before is not None else math.inf
        down = entries[after].top - entries[stop].bottom if after is not None else math.inf
        if min(up, down) <= reach:
            target = before if up <= down else after
            _merge(entries[target], [entries[index] for index in run], below=target == before)
            entries[target].unsure |= min(up, down) > WRAP_SURE * max(up, down)
            dropped.update(run)
        elif stop < people[0] and entries[people[0]].top - entries[stop].bottom > EDGE_ROWS * pitch:
            dropped.update(run)
        elif start > people[-1] and entries[start].top - entries[people[-1]].bottom > EDGE_ROWS * pitch:
            dropped.update(run)
        start = stop + 1
    return [entry for index, entry in enumerate(entries) if index not in dropped]


def _merge(target: _Entry, run: list[_Entry], below: bool) -> None:
    """Join the lines of `run` to the row `target`, which they are `below` or above."""
    parts = [target, *run] if below else [*run, target]
    values: dict[str, str] = {}
    for part in parts:
        for key, text in part.values.items():
            values[key] = f"{values[key]} {text}" if key in values else text
    target.values = values
    target.words = [word for part in parts for word in part.words]
    target.top, target.bottom = parts[0].top, parts[-1].bottom

