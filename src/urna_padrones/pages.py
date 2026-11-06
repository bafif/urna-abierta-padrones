"""The pages of a roll as images, from a PDF or from a picture: a JPEG, a PNG or a TIFF of one or more pages.

What kind of file it is comes from its first bytes, never from its name. A picture is brought to the
size of a page rendered at TARGET_DPI, so the same table reads the same from a PDF and from a photo.
"""

import struct
from pathlib import Path

import cv2
import numpy as np

from .errors import RollError
from .pdf import HEADER_WINDOW, TARGET_DPI, check_pdf, render_page

SIGNATURES = {b"\x89PNG\r\n\x1a\n": "png", b"\xff\xd8\xff": "jpeg", b"II*\x00": "tiff", b"MM\x00*": "tiff"}
# The long side of an A4 page at TARGET_DPI: a picture is taken to be a whole page.
LONG_SIDE = round(297 / 25.4 * TARGET_DPI)
# The most pages a TIFF may have: the list of pages is a chain inside the file, and a broken one may loop.
MAX_TIFF_PAGES = 5000


def kind_of(path: Path) -> str:
    """"pdf" or "image". Anything else raises RollError("not_pdf"); a missing file, the usual OSError."""
    with Path(path).open("rb") as handle:
        head = handle.read(HEADER_WINDOW)
    if b"%PDF-" in head:
        return "pdf"
    if any(head.startswith(signature) for signature in SIGNATURES):
        return "image"
    raise RollError("not_pdf")


def check_roll(path: Path) -> int:
    """The number of pages of a PDF or a picture, or RollError saying why it cannot be read."""
    if kind_of(path) == "pdf":
        return check_pdf(path)
    data = Path(path).read_bytes()
    count = _tiff_pages(data) if data[:4] in (b"II*\x00", b"MM\x00*") else 1
    if count is None or count < 1 or _decode(data, 0) is None:
        raise RollError("damaged")
    return count


def render(path: Path, index: int) -> np.ndarray:
    """One page as a 2D uint8 array, at TARGET_DPI for a PDF and at the size of such a page for a picture."""
    if kind_of(path) == "pdf":
        return render_page(path, index)
    image = _decode(Path(path).read_bytes(), index)
    if image is None:
        raise RollError("damaged")
    return to_page_size(image)


def to_page_size(gray: np.ndarray) -> np.ndarray:
    """A picture scaled so that its long side is that of an A4 page at TARGET_DPI."""
    long_side = max(gray.shape[:2])
    factor = LONG_SIDE / long_side
    if abs(factor - 1) < 0.02:
        return gray
    size = (max(1, round(gray.shape[1] * factor)), max(1, round(gray.shape[0] * factor)))
    return cv2.resize(gray, size, interpolation=cv2.INTER_AREA if factor < 1 else cv2.INTER_CUBIC)


def _decode(data: bytes, index: int) -> np.ndarray | None:
    """Page `index` of a picture in grayscale, turned upright as its camera said, or None if it cannot be read."""
    buffer = np.frombuffer(data, np.uint8)
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        ok, pages = cv2.imdecodemulti(buffer, cv2.IMREAD_GRAYSCALE, None, (index, index + 1))
        image = pages[0] if ok and pages else None
    elif index == 0:
        image = cv2.imdecode(buffer, cv2.IMREAD_GRAYSCALE)
    else:
        image = None
    if image is None or image.ndim != 2 or image.size == 0:
        return None
    return image


def _tiff_pages(data: bytes) -> int | None:
    """How many pages a TIFF has, from its chain of page directories, or None if the chain is broken."""
    order = "<" if data[:2] == b"II" else ">"
    try:
        (offset,) = struct.unpack_from(order + "I", data, 4)
        seen = set()
        while offset:
            if offset in seen or len(seen) >= MAX_TIFF_PAGES:
                return None
            seen.add(offset)
            (entries,) = struct.unpack_from(order + "H", data, offset)
            (offset,) = struct.unpack_from(order + "I", data, offset + 2 + 12 * entries)
    except struct.error:
        return None
    return len(seen)
