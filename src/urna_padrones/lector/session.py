"""One roll at a time: its private copy, the reading in the background, and what a person reviewed.

The PDF or picture is copied into a folder only this user can open and is deleted as soon as it
is not needed: when another roll comes in, when the reading is cancelled, and when the reader closes.
Nothing else is written anywhere.
"""

import os
import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import BinaryIO

from ..errors import RollError
from ..padron import padron_bytes, padron_summary
from ..pages import check_roll
from ..reading import COLUMNS, ReadRow, RollReading, read_roll, row_image
from ..table import CONFIDENCE_CHECKED, SURE_CONFIDENCE

MAX_PDF = 512 * 1024 * 1024
CHUNK = 1024 * 1024
# Longest text a person may type in a field, and longest title the open format allows.
MAX_VALUE = 200
MAX_TITLE = 200
# How a row is shown for review: a little of the lines around it, at three quarters of 300 dpi.
IMAGE_MARGIN = 10
IMAGE_SCALE = 0.75
# A reading that does not stop within this long is left behind: it can no longer change anything.
JOIN_SECONDS = 15


class IncompleteUpload(Exception):
    """The browser sent fewer bytes than it announced."""


class NoRows(Exception):
    """There is no finished reading to show or save."""


def file_name_for(title: str | None) -> str:
    """A file name any system accepts, from the title: plain letters, digits and dashes."""
    plain = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^A-Za-z0-9]+", "-", plain).strip("-")[:80].strip("-")
    return f"{stem or 'padron'}.padron"


def clean_title(title: str | None) -> str | None:
    text = " ".join((title or "").split())[:MAX_TITLE].strip()
    return text or None


def _remove(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        # On Windows a file still open elsewhere cannot go yet: the folder goes at exit.
        pass


class Session:
    def __init__(self, folder: Path, workers: int = 2):
        self.folder = folder
        self.workers = workers
        self.lock = threading.Lock()
        self.upload_lock = threading.Lock()
        self.uploads = 0
        self._clear()

    def _clear(self, error: str | None = None) -> None:
        """Back to no roll. Called with the lock held, or before any thread exists."""
        self.pdf: Path | None = None
        self.name = ""
        self.pages = 0
        self.state = "empty"  # empty, ready, reading, done or failed
        self.error = error
        self.pages_done = 0
        self.pages_reading = 0
        self.rows_found = 0
        self.started = 0.0
        self.reading: RollReading | None = None
        self.doubtful: list[int] = []
        self.reviewed: set[int] = set()
        self.edited: dict[int, set[str]] = {}
        # Each reading gets its own event: a reading left behind can tell it is no longer current.
        self.cancel = threading.Event()
        self.thread: threading.Thread | None = None

    # ----- The roll -----

    def store(self, stream: BinaryIO, length: int, name: str) -> dict:
        """Copy the uploaded PDF or picture, `length` bytes from `stream`, and check it opens. Raises RollError."""
        with self.upload_lock:
            self.forget()
            with self.lock:
                self.uploads += 1
                path = self.folder / f"padron-{self.uploads}.pdf"
            try:
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
                with os.fdopen(os.open(path, flags, 0o600), "wb") as out:
                    left = length
                    while left > 0:
                        chunk = stream.read(min(CHUNK, left))
                        if not chunk:
                            raise IncompleteUpload()
                        out.write(chunk)
                        left -= len(chunk)
                pages = check_roll(path)
            except BaseException:
                _remove(path)
                raise
            with self.lock:
                self.pdf, self.name, self.pages, self.state = path, name, pages, "ready"
            return {"pages": pages, "name": name}

    def forget(self) -> None:
        """Stop any reading and delete the roll and everything read from it."""
        with self.lock:
            thread = self.thread
            self.cancel.set()
        if thread is not None:
            thread.join(JOIN_SECONDS)
        with self.lock:
            pdf = self.pdf
            self._clear()
        _remove(pdf)

    def busy(self) -> bool:
        with self.lock:
            return self.state == "reading"

    # ----- The reading -----

    def start(self) -> bool:
        """Start reading the stored roll. False when there is nothing to start."""
        with self.lock:
            if self.state != "ready" or self.pdf is None:
                return False
            self.state, self.error = "reading", None
            self.pages_done, self.pages_reading, self.rows_found = 0, self.pages, 0
            self.started = time.monotonic()
            cancel = self.cancel
            self.thread = threading.Thread(target=self._read, args=(self.pdf, cancel), name="lector", daemon=True)
            self.thread.start()
        return True

    def stop(self) -> None:
        with self.lock:
            if self.state == "reading":
                self.cancel.set()

    def _read(self, pdf: Path, cancel: threading.Event) -> None:
        def on_page(done: int, total: int) -> None:
            with self.lock:
                if self.cancel is cancel:
                    self.pages_done, self.pages_reading = done, total

        def on_rows(found: int) -> None:
            with self.lock:
                if self.cancel is cancel:
                    self.rows_found = found

        try:
            reading = read_roll(pdf, workers=self.workers, on_page=on_page, on_rows=on_rows, cancelled=cancel.is_set)
        except RollError as error:
            self._ended(cancel, error.code)
        except Exception:  # noqa: BLE001 - whatever it was, the person sees a plain message
            self._ended(cancel, "internal")
        else:
            with self.lock:
                if self.cancel is cancel:
                    self.reading = reading
                    self.doubtful = [row.index for row in reading.rows if row.needs_review]
                    self.state = "done"

    def _ended(self, cancel: threading.Event, code: str) -> None:
        with self.lock:
            if self.cancel is not cancel:
                return
            if code == "cancelled":
                # A cancelled roll is not kept: the person starts again by choosing a file.
                pdf = self.pdf
                self._clear(error="cancelled")
            else:
                pdf = None
                self.state, self.error = "failed", code
        _remove(pdf)

    def status(self) -> dict:
        with self.lock:
            out = {
                "state": self.state,
                "error": self.error,
                "name": self.name,
                "pages_done": self.pages_done,
                "pages_total": self.pages_reading or self.pages,
                "rows_found": self.rows_found,
                "eta_seconds": None,
            }
            if self.state == "reading" and 2 <= self.pages_done < self.pages_reading:
                elapsed = time.monotonic() - self.started
                out["eta_seconds"] = round(elapsed / self.pages_done * (self.pages_reading - self.pages_done))
            if self.state == "done":
                out["summary"] = self._summary()
            return out

    def _summary(self) -> dict:
        reading = self.reading
        counts = padron_summary(reading.records())
        return {
            "people": counts["people"],
            "to_review": counts["to_review"],
            "doubtful": len(self.doubtful),
            "reviewed": len(self.reviewed & set(self.doubtful)),
            "pages_read": reading.pages_read,
            "pages_without_table": [page + 1 for page in reading.pages_without_table],
        }

    # ----- Rows -----

    def _done(self) -> RollReading:
        if self.state != "done" or self.reading is None:
            raise NoRows()
        return self.reading

    def _row(self, index: int) -> ReadRow:
        rows = self._done().rows
        if not 0 <= index < len(rows):
            raise KeyError(index)
        return rows[index]

    def _row_json(self, row: ReadRow) -> dict:
        edited = self.edited.get(row.index, set())
        unsure = [
            column
            for column in CONFIDENCE_CHECKED
            if column not in edited and row.values.get(column) and 0 <= row.confidence.get(column, 1.0) < SURE_CONFIDENCE
        ]
        return {
            "index": row.index,
            "page": row.page + 1,
            "values": {column: row.values.get(column) or "" for column in COLUMNS},
            "valid": {column: bool(row.valid.get(column, True)) for column in COLUMNS},
            "unsure": unsure,
            "repaired": row.repaired_file_number and "file_number" not in edited,
            "needs_review": row.needs_review,
            "reviewed": row.index in self.reviewed,
            "image": row.box is not None,
        }

    def rows(self, which: str = "all") -> list[dict]:
        with self.lock:
            rows = self._done().rows
            chosen = [rows[i] for i in self.doubtful] if which == "doubtful" else rows
            return [self._row_json(row) for row in chosen]

    def image(self, index: int) -> bytes | None:
        with self.lock:
            row = self._row(index)
            pdf = self.pdf
        if row.box is None or pdf is None:
            return None
        return row_image(pdf, row.box, margin=IMAGE_MARGIN, scale=IMAGE_SCALE)

    def edit(self, index: int, values: dict, confirm: bool = False) -> dict:
        """What a person typed in a row: each changed value is cleaned like a read one.

        The row counts as reviewed by that person once every value has its format, or anyway
        when `confirm` says the person looked at the warnings and wants it like this.
        """
        with self.lock:
            row = self._row(index)
            for column, text in values.items():
                if column not in COLUMNS or not isinstance(text, str):
                    continue
                text = text[:MAX_VALUE]
                if text.strip() != (row.values.get(column) or ""):
                    row.fix(column, text)
                    self.edited.setdefault(index, set()).add(column)
            if confirm or all(row.valid.get(column, True) for column in COLUMNS):
                return self._confirmed(row)
            return self._row_json(row)

    def confirm(self, index: int) -> dict:
        with self.lock:
            return self._confirmed(self._row(index))

    def _confirmed(self, row: ReadRow) -> dict:
        row.needs_review = False
        self.reviewed.add(row.index)
        return self._row_json(row)

    def padron(self, title: str | None) -> tuple[bytes, str]:
        """The .padron file and a name to save it with."""
        title = clean_title(title)
        with self.lock:
            records = self._done().records()
        return padron_bytes(records, title), file_name_for(title)
