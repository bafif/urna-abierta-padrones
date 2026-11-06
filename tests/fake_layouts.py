"""Rolls of invented people in other layouts than the faculty's: PDFs with text, other columns.

Every document number is in the 99.000.000 range and every name is obviously invented. The people
come from fake_roll.fake_rows, with an address and a table added.
"""

import random
import zlib
from pathlib import Path

import numpy as np

from fake_roll import fake_rows

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
