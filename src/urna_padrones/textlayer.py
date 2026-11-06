"""Read a PDF page that has real text: its words, where each one is, and the table they make.

A PDF exported from a spreadsheet or a database has the text itself, not a picture of it. Its words
are taken as they are, with nothing to recognise and nothing to doubt, and the table is rebuilt from
where they are: rows by their baseline, and columns by where the names of the header are.

Text a scanner adds on top of its picture, invisible, is not taken: it is the scanner's own reading,
and the page is read from its picture like any other scan.
"""

import ctypes
import statistics
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from .errors import RollError
from .headers import Header, mesa_in, recognise, split_labels
from .pdf import PDFIUM_LOCK, TARGET_DPI
from .table import BY_HEADER, PageReading, Row, is_person, join_name

# A page with fewer visible letters than this has no table worth reading from its text.
MIN_CHARACTERS = 20
# Words further apart than this share of the font size are in different cells. A space is about 0.28.
CELL_GAP = 0.5
# Letters further apart than this share of the font size are different words.
WORD_GAP = 0.25
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


@dataclass(frozen=True)
class TextColumns:
    """The columns of a roll with text: each name of its header, from where to where it is, and its key."""

    spans: tuple[tuple[float, float, str | None], ...]
    header: Header


def page_text(path: Path, index: int, dpi: int = TARGET_DPI) -> TextPage | None:
    """The visible words of a page, or None when it has too few: a scan, or a page with only a stamp.

    A rotated page is left to the picture, which comes out upright, and so is text written at an angle.
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
                if page.get_rotation() % 360:
                    return None
                left, bottom, right, top = page.get_cropbox()
                textpage = page.get_textpage()
                try:
                    characters = _characters(textpage)
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
    words = []
    for group in _word_groups(characters):
        text = unicodedata.normalize("NFC", "".join(c[0] for c in group).translate(LIGATURES))
        size = max(c[6] for c in group)
        baseline = statistics.median(c[5] for c in group)
        words.append(
            Word(
                text=text,
                left=(min(c[1] for c in group) - left) * scale,
                right=(max(c[2] for c in group) - left) * scale,
                top=(top - max(c[4] for c in group)) * scale,
                bottom=(top - min(c[3] for c in group)) * scale,
                baseline=(top - baseline) * scale,
                size=size * scale,
            )
        )
    return TextPage(width=round((right - left) * scale), height=round((top - bottom) * scale), words=words)


Character = tuple[str, float, float, float, float, float, float]


def _characters(textpage: pdfium.PdfTextPage) -> list[Character | None]:
    """Each character as (text, left, right, bottom, top, baseline, size) in PDF points, or None for a break.

    Spaces, line ends, invisible text and text at an angle are breaks.
    """
    raw = textpage.raw
    x, y = ctypes.c_double(), ctypes.c_double()
    box = pdfium_c.FS_RECTF()
    found: list[Character | None] = []
    for index in range(pdfium_c.FPDFText_CountChars(raw)):
        code = pdfium_c.FPDFText_GetUnicode(raw, index)
        text = chr(code) if 0 < code < 0x110000 else ""
        if not text.strip() or pdfium_c.FPDFText_IsGenerated(raw, index) == 1:
            found.append(None)
            continue
        item = pdfium_c.FPDFText_GetTextObject(raw, index)
        invisible = item and pdfium_c.FPDFTextObj_GetTextRenderMode(item) == pdfium_c.FPDF_TEXTRENDERMODE_INVISIBLE
        if invisible or abs(pdfium_c.FPDFText_GetCharAngle(raw, index)) > 0.02:
            found.append(None)
            continue
        if not pdfium_c.FPDFText_GetLooseCharBox(raw, index, ctypes.byref(box)):
            found.append(None)
            continue
        pdfium_c.FPDFText_GetCharOrigin(raw, index, ctypes.byref(x), ctypes.byref(y))
        size = pdfium_c.FPDFText_GetFontSize(raw, index) or (box.top - box.bottom)
        found.append((text, box.left, box.right, box.bottom, box.top, y.value, size))
    return found


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
    return [line[i + 1].left - line[i].right <= CELL_GAP * max(line[i].size, line[i + 1].size) for i in range(len(line) - 1)]


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
    # A line with a single cell may be a title or a footer across the columns: it does not make stretches.
    stretches = sorted((word.left, word.right) for line in lines if len(_cells(line)) >= 2 for word in line)
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
    rows = []
    for line, values in zip(lines[start:], cells_of(lines[start:], chosen)):
        if len(_cells(line)) == 1 and mesa_in(_text(line)):
            table = mesa_in(_text(line))
            continue
        row = Row(page=page, position=len(rows), raw=values, layout=BY_HEADER, columns=fields, source="text")
        join_name(row)
        row.confidence = {key: 1.0 for key in row.raw}
        if not is_person(row):
            continue
        row.title_table = table
        top = min(word.top for word in line)
        bottom = max(word.bottom for word in line)
        margin = 0.3 * statistics.median(word.size for word in line)
        row.band = (
            max(0, round(top - margin)),
            min(text.height, round(bottom + margin)),
            max(0, round(min(left, line[0].left) - margin)),
            min(text.width, round(max(right, line[-1].right) + margin)),
        )
        rows.append(row)
    return PageReading(rows, text_columns=own, has_text=True)

