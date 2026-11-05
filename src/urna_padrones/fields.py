"""Clean and validate the cells of a roster row."""

import re
import unicodedata
from dataclasses import dataclass

EDGE_NOISE = "|!¡[]{}()_-—–=~*+\"'“”‘’`´.,:;¿?<>«»\\/$€%&#@^ "
DOCUMENT = re.compile(r"^\d{7,8}$")
FILE_NUMBER = re.compile(r"^[A-Z]-\d{4,5}/\d$")
FILE_NUMBER_NO_SLASH = re.compile(r"^([A-Z]-\d{4,5})[1I7l|](\d)$")
DIGIT_LOOKALIKES = str.maketrans({"O": "0", "o": "0", "Q": "0", "I": "1", "l": "1"})
NAME_ALLOWED = re.compile(r"^[^\W\d_]+(?:[ '’\-.][^\W\d_]+)*\.?$", re.UNICODE)


@dataclass(frozen=True)
class Checked:
    value: str | None
    valid: bool
    repaired: bool = False


def fold(text: str) -> str:
    """Lowercase and remove accents, to compare text across scans."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _digits(raw: str) -> tuple[str, bool]:
    """Keep the digits, fixing letters that look like one. Any other letter makes it doubtful.

    Dropping a letter without saying so could turn a misread document into a valid but wrong
    number, which is the worst possible error in a roll.
    """
    text = raw.translate(DIGIT_LOOKALIKES)
    digits = "".join(c for c in text if c.isdigit())
    return digits, not any(c.isalpha() for c in text)


def clean_order(raw: str) -> Checked:
    digits, clean = _digits(raw)
    return Checked(digits or None, clean and bool(digits) and len(digits) <= 5)


def clean_document(raw: str) -> Checked:
    digits, clean = _digits(raw)
    return Checked(digits or None, clean and bool(DOCUMENT.match(digits)))


def clean_file_number(raw: str) -> Checked:
    """A roster may leave this cell blank: an empty cell is valid."""
    text = re.sub(r"\s+", "", raw).upper().strip(EDGE_NOISE)
    if not any(c.isdigit() for c in text):
        return Checked(None, True)
    text = text.replace(":", "-").replace("—", "-").replace("–", "-").replace("_", "-")
    if FILE_NUMBER.match(text):
        return Checked(text, True)
    match = FILE_NUMBER_NO_SLASH.match(text)
    if match:
        return Checked(f"{match.group(1)}/{match.group(2)}", True, repaired=True)
    return Checked(text, False)


def clean_status(raw: str) -> Checked:
    letters = [c for c in unicodedata.normalize("NFKD", raw.upper()) if "A" <= c <= "Z"]
    if len(letters) == 1:
        return Checked(letters[0], letters[0] in {"A", "P"})
    return Checked("".join(letters) or None, False)


def clean_name(raw: str) -> Checked:
    text = re.sub(r"\s+", " ", raw).strip(EDGE_NOISE)
    text = re.sub(r"\s*[;:]\s*", ", ", text, count=1) if "," not in text else text
    text = re.sub(r"\s*,\s*", ", ", text)
    parts = text.split(", ")
    valid = len(parts) == 2 and all(NAME_ALLOWED.match(p) for p in parts)
    return Checked(text or None, valid)


def clean_program(raw: str) -> Checked:
    text = re.sub(r"\s+", " ", raw).strip(EDGE_NOISE)
    return Checked(text or None, bool(text))
