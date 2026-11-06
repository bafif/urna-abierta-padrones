"""Find the header of a roll and say which column holds what, by the names of its columns.

Names are compared without case, accents or dots: «Nº», «N°», «n.º» and «NRO.» are one. A column
whose name is not here is ignored, whatever it holds: nothing is guessed from the values.
"""

import re
from dataclasses import dataclass

from .fields import fold


def _numbered(noun: str) -> list[str]:
    """«Nº de orden», «Nro. de orden», «Número de orden»…"""
    return [f"{prefix}{joint}{noun}" for prefix in ("no", "nro", "numero", "num", "n") for joint in (" ", " de ")]


# The names the app takes from a spreadsheet, plus the ones printed rolls use.
ALIASES: dict[str, list[str]] = {
    "order": ["no", "n", "nro", "numero", "num", "orden", "order", *_numbered("orden")],
    "name": [
        "apellido y nombre", "apellido y nombres", "apellidos y nombre", "apellidos y nombres", "nombre y apellido",
        "nombres y apellidos", "nombre completo", "apellido, nombre", "apellido, nombres", "apellido/s y nombre/s",
        "nombre", "full_name", "name",
    ],
    "family": ["apellido", "apellidos", "family_name"],
    "given": ["nombres", "given_names"],
    "document": [
        "dni", "documento", "doc", "document", "tipo y numero", "tipo y nro", "tipo y no", "tipo y numero de documento",
        "tipo y nro de documento", "tipo y no de documento", "documento de identidad", "dni no", "dni nro",
        *_numbered("documento"), *_numbered("dni"), *_numbered("doc"),
    ],
    "file_number": ["legajo", "leg", *_numbered("legajo")],
    "program": ["carrera", "propuesta", "propuesta formativa", "program"],
    "table": ["mesa", "table", *_numbered("mesa")],
    "address": ["domicilio", "direccion", "address"],
    "status": ["calidad", "estado", "condicion", "status"],
}
KNOWN = {alias: key for key, aliases in ALIASES.items() for alias in aliases}
LONGEST = max(len(alias.split()) for alias in KNOWN)
# With text read from an image, a long name may have one letter misread: «Docunento» is «Documento».
FUZZY_MINIMUM = 6
# A person is found by name, and told apart by a number, a document or a legajo.
IDENTIFYING = ("order", "document", "file_number")
# The values of a row, in the order the extraction lists them.
FIELDS = ("order", "name", "program", "file_number", "document", "status", "table", "address")
MESA = re.compile(r"\bmesa\s*(?:no|nro|numero|num|n)?\s*[:#-]?\s*(\d{1,5})\b")


def header_key(text: str) -> str:
    """A column name as it is compared: lowercase, without accents, dots or stray marks, with single spaces."""
    text = fold(text).replace("°", "o").replace(".", "")
    text = re.sub(r"[\s:;|_]+", " ", text)
    return text.strip(" -*()[]")


def _close(a: str, b: str) -> bool:
    """One letter added, dropped or changed."""
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    if abs(len(a) - len(b)) > 1:
        return False
    shorter, longer = (a, b) if len(a) < len(b) else (b, a)
    return any(longer[:i] + longer[i + 1 :] == shorter for i in range(len(longer)))


def key_of(text: str, fuzzy: bool = False) -> str | None:
    """The column a name stands for, or None. `fuzzy` forgives one letter in a long name read from an image."""
    key = header_key(text)
    if key in KNOWN:
        return KNOWN[key]
    if fuzzy and len(key) >= FUZZY_MINIMUM:
        matches = {KNOWN[alias] for alias in KNOWN if len(alias) >= FUZZY_MINIMUM and _close(key, alias)}
        if len(matches) == 1:
            return matches.pop()
    return None


def mesa_in(text: str) -> str | None:
    """The table number a title such as «Mesa Nº 12» gives, without leading zeros, or None."""
    match = MESA.search(header_key(text))
    if not match or int(match.group(1)) < 1:
        return None
    return str(int(match.group(1)))


@dataclass(frozen=True)
class Header:
    """What each column holds: `keys[i]` is the key of column i, or None for a column that is ignored."""

    keys: tuple[str | None, ...]

    def fields(self) -> tuple[str, ...]:
        """The values a row of this roll has, with the name once even when it comes in two columns."""
        found = {key for key in self.keys if key}
        if found & {"family", "given"}:
            found = (found - {"family", "given"}) | {"name"}
        return tuple(key for key in FIELDS if key in found)


def recognise(texts: list[str], fuzzy: bool = False) -> Header | None:
    """The header these column names make, or None when they are not one.

    A header names who the person is (a full name, or a family name) and something that tells people apart
    (an order number, a document or a legajo). A key that comes twice counts only the first time. Next to a
    family name column, «Nombre» or «Nombres» is the given names; without one, «Nombres» is the whole name.
    """
    keys: list[str | None] = [key_of(text, fuzzy) for text in texts]
    plain = [header_key(text) for text in texts]
    if "family" in keys:
        keys = ["given" if key == "name" and word in ("nombre", "nombres") else key for key, word in zip(keys, plain)]
    else:
        keys = ["name" if key == "given" else key for key in keys]
    unique: list[str | None] = []
    for key in keys:
        unique.append(key if key not in unique else None)
    named = "name" in unique or "family" in unique
    if not named or not any(key in unique for key in IDENTIFYING):
        return None
    return Header(tuple(unique))


def split_labels(words: list[str], joined: list[bool]) -> list[tuple[int, int]]:
    """Split the words of a header line into column names, as (first word, last word + 1).

    `joined[i]` says whether word i + 1 follows word i closely enough to belong to the same name. The
    longest known name wins, so «Apellido y nombre» is one column and «Apellido» «Nombres» are two.
    Unknown words that follow each other closely make one column, which is then ignored.
    """

    def known_at(start: int) -> int | None:
        for stop in range(min(len(words), start + LONGEST), start, -1):
            if all(joined[start : stop - 1]) and header_key(" ".join(words[start:stop])) in KNOWN:
                return stop
        return None

    labels: list[tuple[int, int]] = []
    start = 0
    while start < len(words):
        stop = known_at(start)
        if stop is None:
            stop = start + 1
            while stop < len(words) and joined[stop - 1] and known_at(stop) is None:
                stop += 1
        labels.append((start, stop))
        start = stop
    return labels
