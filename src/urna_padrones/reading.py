"""Read a whole roll: the library under the command line and the desktop program.

    reading = read_roll(Path("padron.pdf"), on_page=show_progress, cancelled=user_cancelled)
    for row in reading.rows:
        if row.needs_review:
            png = row_image(Path("padron.pdf"), row.box)

A roll is a PDF or a picture: a JPEG, a PNG or a TIFF of one or more pages. A page of a PDF with
real text is read from that text, exact; any other page is read from its picture. Pages are read
in parallel by threads, each with its own model: the model and most image operations release the
GIL, so threads read as fast as processes and need nothing special inside a packaged program.
"""

import threading
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .errors import MESSAGES, RollError
from .grid import rotate
from .pages import check_roll, kind_of, render
from .pdf import TARGET_DPI
from .headers import Header
from .table import (
    COLUMNS,
    EXTRA,
    FACULTY,
    PageReading,
    Row,
    build_vocabulary,
    cleaner,
    infer_orders,
    read_page,
    smooth_by_neighbours,
)
from .textlayer import TextColumns, first_columns, page_text, read_text_page

__all__ = [
    "COLUMNS",
    "MESSAGES",
    "TARGET_DPI",
    "ReadRow",
    "RollError",
    "RollReading",
    "RowBox",
    "read_roll",
    "row_image",
]

# How often the calling thread asks whether the reading was cancelled.
POLL_SECONDS = 0.1
# How many pages of a PDF are looked at for a header in their text before reading.
HEADER_PAGES = 10
# Straightened pages kept for row_image: one page at 300 dpi takes about 9 MB.
CACHED_PAGES = 4


@dataclass(frozen=True)
class RowBox:
    """Where a row is: its band on the page rendered at TARGET_DPI and straightened by `skew` degrees."""

    page: int
    top: int
    bottom: int
    left: int
    right: int
    skew: float


@dataclass
class ReadRow:
    """One person as read from the roll.

    `values` holds the cleaned value of each of COLUMNS, with the degree in "program" already
    made consistent with its neighbours, and "table" and "address" when the roll has them. `valid`
    says whether each value the roll has has its expected format: a roll found by its header may
    lack some of COLUMNS, and those are left out of `valid`. `confidence` has the model's score for
    each cell it read (1.0 for text taken from a PDF, -1 for an order number inferred from its
    neighbours). `layout` says how the row was read, `columns` which values its roll has. A program
    that lets a person confirm or fix the row sets `needs_review` to False afterwards (see fix() to
    change a value).
    """

    index: int
    page: int
    values: dict[str, str | None]
    valid: dict[str, bool]
    confidence: dict[str, float]
    repaired_file_number: bool
    needs_review: bool
    box: RowBox | None
    layout: str = FACULTY
    columns: tuple[str, ...] = COLUMNS

    def fix(self, column: str, text: str) -> bool:
        """Replace a value with what a person typed, cleaned like a read value. Returns whether it is valid."""
        checked = cleaner(column, self.layout)(text)
        self.values[column] = checked.value
        self.valid[column] = checked.valid
        if column == "file_number":
            self.repaired_file_number = False
        return checked.valid

    def record(self) -> dict:
        """The row as one line of the extraction (JSONL). Its "page" counts from 1, as it always has."""
        record: dict = {c: self.values.get(c) for c in COLUMNS}
        record.update({c: self.values[c] for c in EXTRA if c in self.values})
        record.update(
            page=self.page + 1,
            valid=dict(self.valid),
            confidence=dict(self.confidence),
            repaired_file_number=self.repaired_file_number,
            needs_review=self.needs_review,
        )
        return record


@dataclass
class RollReading:
    source_name: str
    pages_total: int
    pages_read: int
    pages_without_table: list[int]
    inferred_orders: int
    rows: list[ReadRow]
    # Pages read from their text instead of their picture, counted from 0.
    pages_with_text: list[int] = field(default_factory=list)

    def tables(self) -> list[str]:
        """The tables the people are at, in the order the roll first lists them."""
        return list(dict.fromkeys(row.values["table"] for row in self.rows if row.values.get("table")))

    def records(self) -> list[dict]:
        """The rows as the dicts the command line writes, one JSONL line each, and padron_bytes takes."""
        return [row.record() for row in self.rows]


def read_roll(
    path: Path,
    *,
    pages: int | None = None,
    workers: int = 2,
    on_page: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    on_rows: Callable[[int], None] | None = None,
) -> RollReading:
    """Read every row of a roll, or its first `pages` pages.

    `on_page(pages_done, pages_total)` is called once with 0 when reading starts and then each
    time a page is done; `pages_total` is the number of pages being read. Right after each page,
    `on_rows(rows_found)` gets the number of people found so far, for a progress screen. `cancelled()` is
    asked about ten times a second; once it returns True the pages still waiting are dropped,
    the pages being read stop before their next step (straightening, finding the table) or row,
    and RollError("cancelled") is raised. Straightening a page can take some seconds, and it is
    not interrupted. Both are called from the thread that called read_roll.

    Raises RollError with code "not_pdf" (neither a PDF nor a JPEG, PNG or TIFF), "encrypted",
    "damaged", "empty", "unknown_layout" (no page has a table this reader knows) or "cancelled". A
    missing file raises OSError.
    """
    path = Path(path)
    if workers < 1:
        raise ValueError("workers must be at least 1")
    if pages is not None and pages < 1:
        raise ValueError("pages must be at least 1")
    total = check_roll(path)
    kind = kind_of(path)
    count = total if pages is None else min(pages, total)
    if cancelled is not None and cancelled():
        raise RollError("cancelled")
    if on_page is not None:
        on_page(0, count)
    columns = _text_columns(path, count) if kind == "pdf" else None
    per_page = _read_pages(path, kind, count, workers, on_page, cancelled, on_rows, columns)
    _reread_without_header(path, kind, per_page, cancelled)
    rows = [row for page in per_page for row in page.rows]
    if not rows:
        raise RollError("unknown_layout")
    inferred = infer_orders(rows)
    return RollReading(
        source_name=path.name,
        pages_total=total,
        pages_read=count,
        pages_without_table=[index for index, page in enumerate(per_page) if not page.rows],
        inferred_orders=inferred,
        rows=_finish(rows),
        pages_with_text=[index for index, page in enumerate(per_page) if page.rows and page.rows[0].source == "text"],
    )


def _text_columns(path: Path, count: int) -> TextColumns | None:
    """The columns of the first header among the first pages with text, so that the pages after it, often without
    a header of their own, are read from their text at once instead of being recognised from their picture first."""
    for index in range(min(count, HEADER_PAGES)):
        text = page_text(path, index)
        columns = first_columns(text) if text is not None else None
        if columns is not None:
            return columns
    return None


def _read_one(
    path: Path,
    kind: str,
    index: int,
    checkpoint: Callable[[], None],
    columns: TextColumns | None = None,
    lend: Callable[[dict[int, Header] | None], None] | None = None,
    borrow: Callable[[], dict[int, Header] | None] | None = None,
) -> PageReading:
    """One page: from its text when it or `columns` gives a header, from its picture otherwise."""
    text = page_text(path, index) if kind == "pdf" else None
    if text is not None:
        reading = read_text_page(text, index, columns)
        if reading.rows:
            return reading
    checkpoint()
    image = render(path, index)
    reading = read_page(image, index, checkpoint=checkpoint, photo=kind == "image", lend=lend, borrow=borrow)
    reading.has_text = text is not None
    return reading


def _reread_without_header(
    path: Path, kind: str, per_page: list[PageReading], cancelled: Callable[[], bool] | None
) -> None:
    """Read again, with the header of another page, the pages that had none of their own.

    A roll often prints its header only on the first page. A page with text takes the columns of the
    first page with text that named them; a scanned page takes the first header of a table with as many
    columns. A roll read as the faculty's layout has no header to give. A page that found a header of its own,
    the faculty's too, is not read again: one PDF may hold two lists laid out differently.
    """

    def checkpoint() -> None:
        if cancelled is not None and cancelled():
            raise RollError("cancelled")

    text_columns = next((page.text_columns for page in per_page if page.text_columns is not None), None)
    headers = {}
    for page in per_page:
        if page.header is not None:
            headers.setdefault(page.separators, page.header)
    for index, page in enumerate(per_page):
        if page.header is not None or page.text_columns is not None or page.own_header:
            continue
        if page.has_text and text_columns is not None:
            checkpoint()
            text = page_text(path, index)
            reading = read_text_page(text, index, text_columns) if text is not None else None
            if reading is not None and reading.rows:
                per_page[index] = reading
                continue
        if page.separators in headers:
            checkpoint()
            image = render(path, index)
            per_page[index] = read_page(image, index, checkpoint, header=headers[page.separators], photo=kind == "image")


def _read_pages(
    path: Path,
    kind: str,
    count: int,
    workers: int,
    on_page: Callable[[int, int], None] | None,
    cancelled: Callable[[], bool] | None,
    on_rows: Callable[[int], None] | None = None,
    columns: TextColumns | None = None,
) -> list[PageReading]:
    stop = threading.Event()

    def checkpoint() -> None:
        if stop.is_set():
            raise RollError("cancelled")

    # The first page lends its header to the scanned pages without one, which then are read once, instead of
    # as the faculty's layout first and again afterwards. They wait for it only if they get that far before it.
    lent = _Lent()

    def read(index: int) -> PageReading:
        checkpoint()
        if index:
            return _read_one(path, kind, index, checkpoint, columns, borrow=lambda: lent.take(checkpoint))
        try:
            return _read_one(path, kind, index, checkpoint, columns, lend=lent.give)
        finally:
            lent.give(None)

    results: list[PageReading] = [PageReading([]) for _ in range(count)]
    pool = ThreadPoolExecutor(max_workers=min(workers, count), thread_name_prefix="urna-padrones")
    # Submitted in order: the first page always starts before or with the others, even with one worker.
    futures = {pool.submit(read, index): index for index in range(count)}
    pending = set(futures)
    done_count = 0
    rows_found = 0
    try:
        while pending:
            timeout = POLL_SECONDS if cancelled is not None else None
            done, pending = wait(pending, timeout=timeout, return_when=FIRST_COMPLETED)
            for future in done:
                results[futures[future]] = future.result()
                done_count += 1
                rows_found += len(results[futures[future]].rows)
                if on_page is not None:
                    on_page(done_count, count)
                if on_rows is not None:
                    on_rows(rows_found)
            if pending and cancelled is not None and cancelled():
                raise RollError("cancelled")
    finally:
        # On success nothing is left; on cancellation or any error, nothing keeps running.
        stop.set()
        pool.shutdown(wait=True, cancel_futures=True)
    return results


class _Lent:
    """What the first page lends to the others, given once, and waited for by those that need it."""

    def __init__(self) -> None:
        self._given = threading.Event()
        self._value: dict[int, Header] | None = None

    def give(self, value: dict[int, Header] | None) -> None:
        if not self._given.is_set():
            self._value = value
            self._given.set()

    def take(self, checkpoint: Callable[[], None]) -> dict[int, Header] | None:
        while not self._given.wait(POLL_SECONDS):
            checkpoint()
        return self._value


def _finish(rows: list[Row]) -> list[ReadRow]:
    """Clean every value and make the degree read from pictures consistent along the roll.

    A degree taken from the text of a PDF is exact and stays as it is.
    """
    programs = [row.checked("program").value for row in rows]
    read = [index for index, row in enumerate(rows) if row.source != "text"]
    raw_programs = [programs[index] for index in read]
    vocabulary = build_vocabulary([program or "" for program in raw_programs])
    smoothed = smooth_by_neighbours([vocabulary.get(p, p) for p in raw_programs])
    for index, program in zip(read, smoothed):
        programs[index] = program
    finished = []
    for index, (row, program) in enumerate(zip(rows, programs)):
        checked = {c: row.checked(c) for c in COLUMNS}
        values = {c: checked[c].value for c in COLUMNS}
        values["program"] = program
        valid = {c: checked[c].valid for c in COLUMNS if c in row.columns}
        for column in EXTRA:
            if column in row.columns:
                extra = row.checked(column)
                values[column], valid[column] = extra.value, extra.valid
        if values.get("table") is None and row.title_table:
            values["table"] = row.title_table
        box = None
        if row.band is not None:
            top, bottom, left, right = row.band
            box = RowBox(page=row.page, top=top, bottom=bottom, left=left, right=right, skew=row.skew)
        finished.append(
            ReadRow(
                index=index,
                page=row.page,
                values=values,
                valid=valid,
                confidence=row.confidence,
                repaired_file_number=checked["file_number"].repaired,
                needs_review=row.needs_review(),
                box=box,
                layout=row.layout,
                columns=row.columns,
            )
        )
    return finished


_pages: OrderedDict[tuple, np.ndarray] = OrderedDict()
_pages_lock = threading.Lock()


def _straight_page(path: Path, page: int, skew: float) -> np.ndarray:
    """The page straightened as during the reading, from a small cache of recent pages."""
    resolved = path.resolve()
    stat = resolved.stat()
    key = (str(resolved), stat.st_mtime_ns, stat.st_size, page, skew)
    with _pages_lock:
        image = _pages.get(key)
        if image is not None:
            _pages.move_to_end(key)
            return image
    image = rotate(render(resolved, page), skew)
    with _pages_lock:
        _pages[key] = image
        while len(_pages) > CACHED_PAGES:
            _pages.popitem(last=False)
    return image


def row_image(path: Path, box: RowBox, *, margin: int = 12, scale: float = 0.5) -> bytes:
    """A PNG of the row band plus `margin` pixels around it, scaled by `scale`.

    The page is rendered and straightened again exactly as during the reading, so the image
    shows what the reader saw. Safe to call from any thread, also while read_roll runs.
    """
    if margin < 0 or scale <= 0:
        raise ValueError("margin must not be negative and scale must be positive")
    image = _straight_page(Path(path), box.page, box.skew)
    height, width = image.shape[:2]
    top, bottom = max(0, box.top - margin), min(height, box.bottom + margin)
    left, right = max(0, box.left - margin), min(width, box.right + margin)
    crop = image[top:bottom, left:right]
    if crop.size == 0:
        raise ValueError("the box is outside the page")
    if scale != 1.0:
        size = (max(1, round(crop.shape[1] * scale)), max(1, round(crop.shape[0] * scale)))
        crop = cv2.resize(crop, size, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    ok, encoded = cv2.imencode(".png", crop)
    if not ok:
        raise ValueError("the row could not be encoded as PNG")
    return encoded.tobytes()
