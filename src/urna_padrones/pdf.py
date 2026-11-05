"""Render PDF pages to grayscale images."""

from pathlib import Path

import numpy as np
import pypdfium2 as pdfium

TARGET_DPI = 300


def page_count(path: Path) -> int:
    document = pdfium.PdfDocument(path)
    try:
        return len(document)
    finally:
        document.close()


def render_page(path: Path, index: int, dpi: int = TARGET_DPI) -> np.ndarray:
    """Return one page as a 2D uint8 array. Every scan is brought to the same resolution."""
    document = pdfium.PdfDocument(path)
    try:
        bitmap = document[index].render(scale=dpi / 72, grayscale=True)
        return np.squeeze(bitmap.to_numpy()).copy()
    finally:
        document.close()
