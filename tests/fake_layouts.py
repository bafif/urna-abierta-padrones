"""Rolls of invented people in other layouts than the faculty's: other columns, PDFs with text, photos.

Every document number is in the 99.000.000 range and every name is obviously invented. The people
come from fake_roll.fake_rows, with an address and a table added.
"""

import io
import random
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from fake_roll import PAGE_SIZE, fake_rows, find_font

POINTS = (595.28, 841.89)  # A4 in PDF points
STREETS = ["Calle Inventada", "Avenida de Prueba", "Pasaje Ejemplo", "Calle Modelo"]


def people(count: int, seed: int = 3, accents: bool = True, tables: tuple[int, ...] = (), first_order: int = 1) -> list[dict]:
    """Invented people with an address, and with a table when `tables` says which: one after the other, in blocks."""
    rows = fake_rows(count, seed=seed, accents=accents, first_order=first_order)
    rng = random.Random(seed + 1000)
    for index, row in enumerate(rows):
        row["address"] = f"{rng.choice(STREETS)} {rng.randint(100, 2999)}"
        if tables:
            row["table"] = str(tables[index * len(tables) // count])
    return rows


def cell_text(row: dict, key: str) -> str:
    """What a roll prints in a column: «family» and «given» are the two halves of the name."""
    family, _, given = row["name"].partition(", ")
    return {"family": family, "given": given, "typed_document": f"DNI {row['document']}"}.get(key, row.get(key, ""))


# ----- Scanned tables -----


def draw_ruled_page(
    rows: list[dict],
    headers: list[str],
    keys: list[str],
    column_x: list[int],
    angle: float = 0.5,
    seed: int = 5,
    font=None,
    title: str | None = None,
    row_height: int = 46,
    top: int = 260,
) -> np.ndarray:
    """A scanned page with a ruled table: `headers[i]` over column i, which holds `keys[i]` of each row.

    `column_x` has one more line than there are columns. A key that is not a value of the rows leaves the
    column empty, like a signature column.
    """
    font = font or find_font()[0]
    image = Image.new("L", PAGE_SIZE, 250)
    draw = ImageDraw.Draw(image)
    if title:
        draw.text((column_x[0], top - 120), title, fill=20, font=font)
    bottom = top + row_height * (len(rows) + 1)
    for x in column_x:
        draw.line([(x, top), (x, bottom)], fill=40, width=3)
    for i in range(len(rows) + 2):
        y = top + i * row_height
        draw.line([(column_x[0], y), (column_x[-1], y)], fill=60, width=2)
    for x, header in zip(column_x, headers):
        draw.text((x + 12, top + 4), header, fill=20, font=font)
    for r, row in enumerate(rows, start=1):
        y = top + r * row_height + 4
        for x, key in zip(column_x, keys):
            draw.text((x + 12, y), cell_text(row, key), fill=25, font=font)
    image = image.rotate(angle, resample=Image.BICUBIC, fillcolor=250).filter(ImageFilter.GaussianBlur(0.6))
    pixels = np.asarray(image, dtype=np.int16)
    noise = np.random.default_rng(seed).normal(0, 6, pixels.shape)
    return np.clip(pixels + noise, 0, 255).astype(np.uint8)


# ----- PDFs with text -----


def _pdf_string(text: str) -> bytes:
    data = text.encode("cp1252")
    return b"(" + data.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def text_content(items: list[tuple[float, float, float, str]], lines=(), invisible: bool = False) -> bytes:
    """A page's drawing: `items` are (x, y from the top, size, text) in points, `lines` are (x0, y0, x1, y1)."""
    height = POINTS[1]
    out = bytearray()
    for x0, y0, x1, y1 in lines:
        out += b"0.6 w %.2f %.2f m %.2f %.2f l S\n" % (x0, height - y0, x1, height - y1)
    for x, y, size, text in items:
        mode = b"3 Tr " if invisible else b""
        out += b"BT /F1 %.2f Tf %s1 0 0 1 %.2f %.2f Tm %s Tj ET\n" % (size, mode, x, height - y, _pdf_string(text))
    return bytes(out)


def pdf_bytes(pages: list[dict]) -> bytes:
    """A PDF from pages given as {"content": bytes} and, for a scan, {"image": 2D uint8 array at 300 dpi}.

    The text is in Helvetica with the Windows Latin encoding, which has every Spanish letter. An image
    fills the page and the content, if any, is drawn on top of it.
    """
    width, height = POINTS
    objects: list[bytes] = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    kids = []
    for page in pages:
        content = page.get("content", b"")
        resources = b"/Font << /F1 3 0 R >>"
        if page.get("image") is not None:
            gray = page["image"]
            data = zlib.compress(np.ascontiguousarray(gray).tobytes())
            objects.append(
                b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceGray "
                b"/BitsPerComponent 8 /Filter /FlateDecode /Length %d >>\nstream\n" % (gray.shape[1], gray.shape[0], len(data))
                + data
                + b"\nendstream"
            )
            resources += b" /XObject << /Im0 %d 0 R >>" % len(objects)
            content = b"q %.2f 0 0 %.2f 0 0 cm /Im0 Do Q\n" % (width, height) + content
        objects.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
        contents = len(objects)
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f] /Resources << %s >> /Contents %d 0 R >>"
            % (width, height, resources, contents)
        )
        kids.append(len(objects))
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % k for k in kids), len(kids))
    body = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, item in enumerate(objects, start=1):
        offsets.append(len(body))
        body += b"%d 0 obj\n" % number + item + b"\nendobj\n"
    start = len(body)
    body += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    body += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    body += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, start)
    return bytes(body)


def listing_page(
    rows: list[dict],
    headers: list[str] | None,
    keys: list[str],
    column_x: list[float],
    size: float = 8.5,
    title: str | None = None,
    ruled: bool = False,
    right_aligned: tuple[str, ...] = (),
    top: float = 90,
    pitch: float = 14,
) -> bytes:
    """The drawing of one page of a digital listing, without ruling unless `ruled`.

    `column_x[i]` is where column i starts, in points, plus where the last one ends. Keys in
    `right_aligned` end at the start of the next column, like numbers in a spreadsheet.
    """
    items = []
    if title:
        items.append((column_x[0], top - 30, size + 3, title))
    y = top
    if headers:
        items.extend((x, y, size, header) for x, header in zip(column_x, headers))
        y += pitch * 1.4
    for row in rows:
        for i, key in enumerate(keys):
            text = cell_text(row, key)
            x = column_x[i]
            if key in right_aligned:
                x = column_x[i + 1] - 6 - 0.5 * size * len(text)
            items.append((x, y, size, text))
        y += pitch
    lines = []
    if ruled:
        first = top - pitch * 0.9
        last = y - pitch * 0.6
        lines = [(x, first, x, last) for x in column_x]
        lines += [(column_x[0], line_y, column_x[-1], line_y) for line_y in (first, top + pitch * 0.5, last)]
    return text_content(items, lines)


def make_listing_pdf(path: Path, pages: list[bytes]) -> None:
    Path(path).write_bytes(pdf_bytes([{"content": content} for content in pages]))


# ----- Photos and image files -----


def photo_of(page: np.ndarray, seed: int = 9, width: int = 3024) -> np.ndarray:
    """A scanned page as a phone photo: smaller, slightly turned, unevenly lit and with JPEG blur."""
    rng = np.random.default_rng(seed)
    image = Image.fromarray(page).rotate(float(rng.uniform(-1.5, 1.5)), resample=Image.BICUBIC, fillcolor=235)
    height = round(width * page.shape[0] / page.shape[1])
    image = image.resize((width, height), Image.LANCZOS)
    pixels = np.asarray(image, dtype=np.float32)
    ys, xs = np.mgrid[0:height, 0:width]
    light = 0.78 + 0.22 * (xs / width) * (1 - 0.4 * ys / height)
    pixels = np.clip(pixels * light + rng.normal(0, 4, pixels.shape), 0, 255).astype(np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, "JPEG", quality=85)
    return np.asarray(Image.open(buffer).convert("L"))


def save_image(pages: list[np.ndarray], path: Path, kind: str, dpi: int = 300) -> None:
    """Save grayscale pages as a JPEG, a PNG or a TIFF (the only one with more than one page)."""
    images = [Image.fromarray(page, mode="L") for page in pages]
    if kind == "tiff":
        images[0].save(path, "TIFF", compression="tiff_lzw", save_all=True, append_images=images[1:], dpi=(dpi, dpi))
    elif kind == "jpeg":
        images[0].save(path, "JPEG", quality=90, dpi=(dpi, dpi))
    else:
        images[0].save(path, "PNG", dpi=(dpi, dpi))
