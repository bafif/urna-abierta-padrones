"""Read a whole scanned roll: the library under the command line and the desktop program.

    reading = read_roll(Path("padron.pdf"), on_page=show_progress, cancelled=user_cancelled)
    for row in reading.rows:
        if row.needs_review:
            png = row_image(Path("padron.pdf"), row.box)

Pages are read in parallel by threads, each with its own model: the model and most image
operations release the GIL, so threads read as fast as processes and need nothing special
inside a packaged program.
"""

import threading
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .errors import MESSAGES, RollError
from .grid import rotate
from .pdf import TARGET_DPI, check_pdf, render_page
from .table import CLEANERS, COLUMNS, Row, build_vocabulary, extract_page, infer_orders, smooth_by_neighbours

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
    made consistent with its neighbours. `valid` says whether each value has its expected
    format; `confidence` has the model's score for each cell it read (-1 for an order number
    inferred from its neighbours). A program that lets a person confirm or fix the row sets
    `needs_review` to False afterwards (see fix() to change a value).
    """

    index: int
    page: int
    values: dict[str, str | None]
    valid: dict[str, bool]
    confidence: dict[str, float]
    repaired_file_number: bool
    needs_review: bool
    box: RowBox | None

    def fix(self, column: str, text: str) -> bool:
        """Replace a value with what a person typed, cleaned like a read value. Returns whether it is valid."""
        checked = CLEANERS[column](text)
        self.values[column] = checked.value
        self.valid[column] = checked.valid
        if column == "file_number":
            self.repaired_file_number = False
        return checked.valid

    def record(self) -> dict:
        """The row as one line of the extraction (JSONL). Its "page" counts from 1, as it always has."""
        record: dict = {c: self.values.get(c) for c in COLUMNS}
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
    """Read every row of a scanned roll, or its first `pages` pages.

    `on_page(pages_done, pages_total)` is called once with 0 when reading starts and then each
    time a page is done; `pages_total` is the number of pages being read. Right after each page,
    `on_rows(rows_found)` gets the number of people found so far, for a progress screen. `cancelled()` is
    asked about ten times a second; once it returns True the pages still waiting are dropped,
    the pages being read stop before their next step (straightening, finding the table) or row,
    and RollError("cancelled") is raised. Straightening a page can take some seconds, and it is
    not interrupted. Both are called from the thread that called read_roll.

    Raises RollError with code "not_pdf", "encrypted", "damaged", "empty", "unknown_layout"
    (no page has a table this reader knows) or "cancelled". A missing file raises OSError.
    """
    path = Path(path)
    if workers < 1:
        raise ValueError("workers must be at least 1")
    if pages is not None and pages < 1:
        raise ValueError("pages must be at least 1")
    total = check_pdf(path)
    count = total if pages is None else min(pages, total)
    if cancelled is not None and cancelled():
        raise RollError("cancelled")
    if on_page is not None:
        on_page(0, count)
    per_page = _read_pages(path, count, workers, on_page, cancelled, on_rows)
    rows = [row for page in per_page for row in page]
    if not rows:
        raise RollError("unknown_layout")
    inferred = infer_orders(rows)
    return RollReading(
        source_name=path.name,
        pages_total=total,
        pages_read=count,
        pages_without_table=[index for index, page in enumerate(per_page) if not page],
        inferred_orders=inferred,
        rows=_finish(rows),
    )


def _read_pages(
    path: Path,
    count: int,
    workers: int,
    on_page: Callable[[int, int], None] | None,
    cancelled: Callable[[], bool] | None,
    on_rows: Callable[[int], None] | None = None,
) -> list[list[Row]]:
    stop = threading.Event()

    def checkpoint() -> None:
        if stop.is_set():
            raise RollError("cancelled")

    def read(index: int) -> list[Row]:
        checkpoint()
        return extract_page(render_page(path, index), index, checkpoint=checkpoint)

    results: list[list[Row]] = [[] for _ in range(count)]
    pool = ThreadPoolExecutor(max_workers=min(workers, count), thread_name_prefix="urna-padrones")
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
                rows_found += len(results[futures[future]])
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


def _finish(rows: list[Row]) -> list[ReadRow]:
    """Clean every value and make the degree consistent along the roll."""
    raw_programs = [row.checked("program").value for row in rows]
    vocabulary = build_vocabulary([program or "" for program in raw_programs])
    programs = smooth_by_neighbours([vocabulary.get(p, p) for p in raw_programs])
    finished = []
    for index, (row, program) in enumerate(zip(rows, programs)):
        checked = {c: row.checked(c) for c in COLUMNS}
        values = {c: checked[c].value for c in COLUMNS}
        values["program"] = program
        box = None
        if row.band is not None:
            top, bottom, left, right = row.band
            box = RowBox(page=row.page, top=top, bottom=bottom, left=left, right=right, skew=row.skew)
        finished.append(
            ReadRow(
                index=index,
                page=row.page,
                values=values,
                valid={c: checked[c].valid for c in COLUMNS},
                confidence=row.confidence,
                repaired_file_number=checked["file_number"].repaired,
                needs_review=row.needs_review(),
                box=box,
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
    image = rotate(render_page(resolved, page), skew)
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
