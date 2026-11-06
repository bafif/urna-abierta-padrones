"""Scanned rolls made up here: invented people, drawn, rotated and dirtied like a photocopy.

Every document number is in the 99.000.000 range and every name is obviously invented.
"""

import hashlib
import random
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from urna_padrones.fields import file_number_check_digit

FAMILY = ["Prueba", "Ejemplo", "Modelo", "Muestra", "Núñez", "Peña", "Ibáñez", "Quiroga", "Rodríguez", "Benítez"]
GIVEN = ["Ana", "Luis", "María José", "Tomás", "Sofía", "Andrés", "Inés", "Ramiro"]
PROGRAMS = ["Ingeniería Civil", "Ingeniería Química"]
COLUMN_X = [150, 330, 1010, 1420, 1690, 1960, 2190, 2400]
KEYS = ["order", "name", "program", "file_number", "document", "status"]
HEADERS = ["Nº", "Nombre", "Propuesta", "Legajo", "Documento", "Calidad", "Firma"]
PAGE_SIZE = (2480, 3508)  # A4 at 300 dpi, the resolution the reader renders at
ROW_HEIGHT = 46
TOP = 200
FONT_SIZE = 32
# Fonts with accents that are usually present when fontconfig is not.
KNOWN_FONTS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def accent_font_path() -> str | None:
    """Liberation Sans as fontconfig finds it, or None when there is no fontconfig or no match."""
    try:
        found = subprocess.run(
            ["fc-match", "-f", "%{file}", "Liberation Sans"], capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    if found.returncode != 0 or not found.stdout:
        return None
    return found.stdout


def find_font(size: int = FONT_SIZE) -> tuple[ImageFont.ImageFont | ImageFont.FreeTypeFont, bool]:
    """A font and whether it draws accents.

    The font bundled with Pillow has no accents: it would draw boxes instead of letters, so
    whoever draws with it has to stay within plain ASCII.
    """
    for path in [accent_font_path(), *KNOWN_FONTS]:
        if path and Path(path).is_file():
            try:
                return ImageFont.truetype(path, size=size), True
            except OSError:
                continue
    return ImageFont.load_default(size=size), False


def plain(text: str) -> str:
    return text.translate(str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN"))


def fake_rows(count: int, seed: int = 3, accents: bool = True, first_order: int = 1) -> list[dict]:
    """Invented people, numbered from `first_order`, grouped by degree like a real roster."""
    rng = random.Random(seed)
    rows = []
    switch = max(15, (count * 3) // 5)
    for offset in range(count):
        legajo = "" if rng.random() < 0.2 else f"{rng.choice('ACLS')}-{rng.randint(1000, 9999)}/{rng.randint(0, 9)}"
        if legajo:  # the drawn last digit is replaced, so the same seed still gives the same people
            legajo = f"{legajo[:-1]}{file_number_check_digit(legajo[2:6])}"
        row = {
            "order": str(first_order + offset),
            "name": f"{rng.choice(FAMILY)}, {rng.choice(GIVEN)}",
            "program": PROGRAMS[0] if offset < switch else PROGRAMS[1],
            "file_number": legajo,
            "document": str(rng.randint(99_000_000, 99_999_999)),
            "status": rng.choice("AAAP"),
        }
        if not accents:
            row = {key: plain(value) for key, value in row.items()}
        rows.append(row)
    return rows


def draw_page(rows: list[dict], angle: float = 0.8, seed: int = 5, font=None) -> np.ndarray:
    """One page of the roll as a grayscale array, in the layout the reader expects."""
    font = font or find_font()[0]
    image = Image.new("L", PAGE_SIZE, 250)
    draw = ImageDraw.Draw(image)
    bottom = TOP + ROW_HEIGHT * (len(rows) + 1)
    for x in COLUMN_X:
        draw.line([(x, TOP), (x, bottom)], fill=40, width=3)
    for i in range(len(rows) + 2):
        y = TOP + i * ROW_HEIGHT
        draw.line([(COLUMN_X[0], y), (COLUMN_X[-1], y)], fill=60, width=2)
    for x, header in zip(COLUMN_X, HEADERS):
        draw.text((x + 12, TOP + 4), header, fill=20, font=font)
    for r, row in enumerate(rows, start=1):
        y = TOP + r * ROW_HEIGHT + 4
        for x, key in zip(COLUMN_X, KEYS):
            draw.text((x + 12, y), row[key], fill=25, font=font)
    image = image.rotate(angle, resample=Image.BICUBIC, fillcolor=250).filter(ImageFilter.GaussianBlur(0.6))
    pixels = np.asarray(image, dtype=np.int16)
    noise = np.random.default_rng(seed).normal(0, 6, pixels.shape)
    return np.clip(pixels + noise, 0, 255).astype(np.uint8)


def save_pdf(pages: list[np.ndarray], path: Path) -> None:
    """Save grayscale pages as a scanned PDF, at the resolution the reader renders at."""
    images = [Image.fromarray(page, mode="L") for page in pages]
    images[0].save(path, "PDF", resolution=300.0, save_all=True, append_images=images[1:])


def make_fake_roll_pdf(path: Path, pages: int = 3, rows_per_page: int = 20, seed: int = 1) -> list[dict]:
    """Draw a roll of invented people over several pages and return the rows drawn, in order.

    Each page is slightly rotated by a different angle, like a sheet feeder does. Without a
    font with accents the names are drawn without them, and the rows returned say so.
    """
    font, accents = find_font()
    rng = random.Random(seed)
    rows = fake_rows(pages * rows_per_page, seed=seed, accents=accents)
    images = []
    for page in range(pages):
        drawn = rows[page * rows_per_page : (page + 1) * rows_per_page]
        angle = rng.uniform(-1.0, 1.0)
        images.append(draw_page(drawn, angle=angle, seed=seed * 100 + page, font=font))
    save_pdf(images, Path(path))
    return rows


def make_text_pdf(path: Path, pages: int = 1) -> None:
    """A scanned letter with a few paragraphs and no table at all."""
    font = find_font()[0]
    images = []
    for page in range(pages):
        image = Image.new("L", PAGE_SIZE, 250)
        draw = ImageDraw.Draw(image)
        for line in range(12):
            draw.text((200, 300 + line * 60), f"Texto de prueba, página {page + 1}, renglón {line + 1}.", 25, font)
        images.append(np.asarray(image))
    save_pdf(images, Path(path))


# The padding string of the standard security handler, from the PDF specification.
_PADDING = bytes.fromhex("28bf4e5e4e758a4164004e56fffa01082e2e00b6d0683e802f0ca9fe6453697a")


def _rc4(key: bytes, data: bytes) -> bytes:
    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + key[i % len(key)]) % 256
        state[i], state[j] = state[j], state[i]
    out = bytearray()
    i = j = 0
    for byte in data:
        i = (i + 1) % 256
        j = (j + state[i]) % 256
        state[i], state[j] = state[j], state[i]
        out.append(byte ^ state[(state[i] + state[j]) % 256])
    return bytes(out)


def make_encrypted_pdf(path: Path, password: str) -> None:
    """A one page PDF that only opens with `password` (standard security handler, revision 2).

    The page has no content stream, so no object needs to be encrypted besides the keys.
    """
    padded = (password.encode("latin-1") + _PADDING)[:32]
    owner = _rc4(hashlib.md5(padded).digest()[:5], padded)
    permissions = -4
    file_id = hashlib.md5(b"padron de prueba").digest()
    key = hashlib.md5(padded + owner + permissions.to_bytes(4, "little", signed=True) + file_id).digest()[:5]
    user = _rc4(key, _PADDING)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>",
        b"<< /Filter /Standard /V 1 /R 2 /O <" + owner.hex().encode() + b"> /U <" + user.hex().encode()
        + b"> /P " + str(permissions).encode() + b" >>",
    ]
    body = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, content in enumerate(objects, start=1):
        offsets.append(len(body))
        body += b"%d 0 obj\n" % number + content + b"\nendobj\n"
    start = len(body)
    body += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    body += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    identifier = file_id.hex().encode()
    body += b"trailer\n<< /Size %d /Root 1 0 R /Encrypt 4 0 R /ID [<%s> <%s>] >>\n" % (
        len(objects) + 1,
        identifier,
        identifier,
    )
    body += b"startxref\n%d\n%%%%EOF\n" % start
    Path(path).write_bytes(bytes(body))
