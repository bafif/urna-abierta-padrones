"""Render PDF pages to grayscale images."""

import sys
import threading
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from .errors import RollError

TARGET_DPI = 300
# PDFium is not thread-safe: only one call at a time, across every thread and every document.
PDFIUM_LOCK = threading.RLock()
# A PDF may have some bytes before its header, but not more than this.
HEADER_WINDOW = 1024


def _encoded(path: Path) -> bytes:
    """The path as PDFium expects it, the same way pypdfium2 passes it."""
    errors = "strict" if sys.platform.startswith("win32") else "surrogateescape"
    return (str(path) + "\x00").encode("utf-8", errors=errors)


def check_pdf(path: Path) -> int:
    """Return the number of pages, or raise RollError saying why the file cannot be read.

    A missing or unreadable file raises the usual OSError. The document is opened through the
    raw API because pypdfium2 reports a document without pages as a load error, with whatever
    error code an earlier failure left behind.
    """
    with Path(path).open("rb") as handle:
        head = handle.read(HEADER_WINDOW)
    if b"%PDF-" not in head:
        raise RollError("not_pdf")
    with PDFIUM_LOCK:
        document = pdfium_c.FPDF_LoadDocument(_encoded(path), None)
        if not document:
            code = pdfium_c.FPDF_GetLastError()
            locked = code in (pdfium_c.FPDF_ERR_PASSWORD, pdfium_c.FPDF_ERR_SECURITY)
            raise RollError("encrypted" if locked else "damaged")
        try:
            pages = pdfium_c.FPDF_GetPageCount(document)
        finally:
            pdfium_c.FPDF_CloseDocument(document)
    if pages < 1:
        raise RollError("empty")
    return pages


def page_count(path: Path) -> int:
    return check_pdf(path)


def render_page(path: Path, index: int, dpi: int = TARGET_DPI) -> np.ndarray:
    """Return one page as a 2D uint8 array. Every scan is brought to the same resolution.

    Every PDFium object is closed here, inside the lock, so that no garbage collection in
    another thread ever calls PDFium at the same time.
    """
    with PDFIUM_LOCK:
        try:
            document = pdfium.PdfDocument(path)
        except pdfium.PdfiumError as error:
            raise RollError("damaged") from error
        try:
            page = document[index]
            try:
                bitmap = page.render(scale=dpi / 72, grayscale=True)
                try:
                    # Kept 2-D: a page 1 pixel high or wide is still a page, just without a table.
                    return bitmap.to_numpy().reshape(bitmap.height, bitmap.width).copy()
                finally:
                    bitmap.close()
            finally:
                page.close()
        except pdfium.PdfiumError as error:
            raise RollError("damaged") from error
        finally:
            document.close()
