"""The check the packaged reader runs with --self-test: the model reads, and a tiny scanned page is read whole.

The page is a picture inside the package, muestra.png (the repository keeps no PDF at all, so
that no real roll gets in by mistake). It is wrapped in a one page PDF in a temporary folder
that is deleted right after, so the check also goes through PDFium. Nothing touches the network.
"""

import tempfile
import zlib
from importlib import resources
from pathlib import Path

SAMPLE_IMAGE = "muestra.png"
SAMPLE_DPI = 300
# The invented people drawn on muestra.png by tools/hacer-muestra.py.
SAMPLE_ROWS = [
    {"order": "1", "name": "Prueba, Ana", "program": "Ingeniería Civil", "file_number": "A-1234/5", "document": "99001234", "status": "A"},
    {"order": "2", "name": "Ejemplo, Luis", "program": "Ingeniería Civil", "file_number": "", "document": "99005678", "status": "P"},
    {"order": "3", "name": "Muestra, Inés", "program": "Ingeniería Civil", "file_number": "C-4321/0", "document": "99009012", "status": "A"},
    {"order": "4", "name": "Modelo, Tomás", "program": "Ingeniería Civil", "file_number": "S-5678/9", "document": "99003456", "status": "A"},
]


def pdf_with_image(gray, dpi: int = SAMPLE_DPI) -> bytes:
    """A one page PDF showing a grayscale image (a 2D uint8 array) at `dpi`."""
    height, width = gray.shape
    data = zlib.compress(gray.tobytes())
    page_width, page_height = width * 72 / dpi, height * 72 / dpi
    content = f"q {page_width:.3f} 0 0 {page_height:.3f} 0 0 cm /Im0 Do Q".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width:.3f} {page_height:.3f}] "
            "/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>"
        ).encode(),
        (
            f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /DeviceGray "
            f"/BitsPerComponent 8 /Filter /FlateDecode /Length {len(data)} >>\nstream\n"
        ).encode()
        + data
        + b"\nendstream",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
    ]
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


def run(report=print) -> bool:
    """True when the model reads its sample and the sample page gives back its people."""
    import cv2
    import numpy as np

    from .. import ocr
    from ..reading import read_roll

    if not ocr.self_test():
        report("el modelo de lectura no funciona / the reading model does not work")
        return False
    try:
        png = (resources.files(__package__) / SAMPLE_IMAGE).read_bytes()
        gray = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
        with tempfile.TemporaryDirectory(prefix="urna-lector-prueba-") as folder:
            path = Path(folder) / "muestra.pdf"
            path.write_bytes(pdf_with_image(gray))
            reading = read_roll(path, workers=1)
    except Exception as error:  # noqa: BLE001 - any failure is a failed check, said in one line
        report(f"no se pudo leer la página de prueba / the sample page could not be read: {type(error).__name__}")
        return False
    documents = [row.values["document"] for row in reading.rows]
    if documents != [row["document"] for row in SAMPLE_ROWS]:
        report(f"la página de prueba se leyó mal / the sample page was misread ({len(documents)} filas)")
        return False
    return True
