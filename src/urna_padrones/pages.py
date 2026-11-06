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

PNG = b"\x89PNG\r\n\x1a\n"
TIFF = (b"II*\x00", b"MM\x00*")
SIGNATURES = {PNG: "png", b"\xff\xd8\xff": "jpeg", TIFF[0]: "tiff", TIFF[1]: "tiff"}
# The long side of an A4 page at TARGET_DPI: a picture is taken to be a whole page.
LONG_SIDE = round(297 / 25.4 * TARGET_DPI)
# The most pages a TIFF may have: the list of pages is a chain inside the file, and a broken one may loop.
MAX_TIFF_PAGES = 5000
# The most pixels a picture may have, read from its first bytes before opening it: a photo of 108 megapixels fits,
# and so does a page scanned at 1000 dpi. A larger one would take more than a gigabyte of memory to open.
MAX_PIXELS = 120_000_000


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
    sizes = _sizes(data)
    if not sizes:
        raise RollError("damaged")
    if any(width * height > MAX_PIXELS for width, height in sizes):
        raise RollError("too_many_pixels")
    if _decode(data, 0) is None:
        raise RollError("damaged")
    return len(sizes)


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
    """Page `index` of a picture in grayscale, turned upright as its camera said, or None if it cannot be read.

    A PNG with transparency is laid on white paper: its transparent background would read as black.
    """
    buffer = np.frombuffer(data, np.uint8)
    try:
        if data[:4] in TIFF:
            ok, pages = cv2.imdecodemulti(buffer, cv2.IMREAD_GRAYSCALE, None, (index, index + 1))
            image = pages[0] if ok and pages else None
        elif index == 0 and data.startswith(PNG) and _transparent(data):
            image = _on_white(cv2.imdecode(buffer, cv2.IMREAD_UNCHANGED))
        elif index == 0:
            image = cv2.imdecode(buffer, cv2.IMREAD_GRAYSCALE)
        else:
            image = None
    except cv2.error:
        return None
    if image is None or image.ndim != 2 or image.size == 0:
        return None
    return image


def _transparent(png: bytes) -> bool:
    """Whether a PNG may have transparent pixels: an alpha channel, or a transparent color before its image data."""
    if len(png) > 25 and png[25] in (4, 6):
        return True
    data = png.find(b"IDAT")
    return b"tRNS" in png[: data if data > 0 else len(png)]


def _on_white(image: np.ndarray | None) -> np.ndarray | None:
    """A picture as it is shown on white paper, in grayscale with 8 bits."""
    if image is None or image.size == 0:
        return None
    if image.dtype == np.uint16:
        image = (image // 257).astype(np.uint8)
    if image.dtype != np.uint8:
        return None
    if image.ndim == 2:
        return image
    if image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.shape[2] != 4:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY).astype(np.uint16)
    alpha = image[:, :, 3].astype(np.uint16)
    return ((gray * alpha + 255 * (255 - alpha)) // 255).astype(np.uint8)


def _sizes(data: bytes) -> list[tuple[int, int]] | None:
    """The width and height of each page of a picture, from its first bytes, or None if they cannot be found."""
    try:
        if data[:4] in TIFF:
            return _tiff_sizes(data)
        if data.startswith(PNG):
            if data[12:16] != b"IHDR":
                return None
            return [struct.unpack_from(">II", data, 16)]
        return _jpeg_size(data)
    except struct.error:
        return None


def _jpeg_size(data: bytes) -> list[tuple[int, int]] | None:
    """The size a JPEG says in its frame header (any SOF marker), going through the markers before it."""
    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            return None
        marker = data[offset + 1]
        if marker == 0xFF:
            offset += 1
            continue
        if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
            offset += 2
            continue
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack_from(">HH", data, offset + 5)
            return [(width, height)]
        (length,) = struct.unpack_from(">H", data, offset + 2)
        offset += 2 + length
    return None


def _tiff_sizes(data: bytes) -> list[tuple[int, int]] | None:
    """The size of each page of a TIFF, from its chain of page directories, or None if the chain is broken."""
    order = "<" if data[:2] == b"II" else ">"
    (offset,) = struct.unpack_from(order + "I", data, 4)
    sizes = []
    seen = set()
    while offset:
        if offset in seen or len(seen) >= MAX_TIFF_PAGES:
            return None
        seen.add(offset)
        (entries,) = struct.unpack_from(order + "H", data, offset)
        size = {256: 0, 257: 0}  # ImageWidth and ImageLength
        for entry in range(entries):
            start = offset + 2 + 12 * entry
            tag, kind = struct.unpack_from(order + "HH", data, start)
            if tag in size:
                (size[tag],) = struct.unpack_from(order + ("H" if kind == 3 else "I"), data, start + 8)
        sizes.append((size[256], size[257]))
        (offset,) = struct.unpack_from(order + "I", data, offset + 2 + 12 * entries)
    return sizes
