"""Which column holds what, from the names in the header of a roll."""

import pytest

from urna_padrones.headers import header_key, key_of, recognise, split_labels


@pytest.mark.parametrize(
    "text, key",
    [
        ("Nº", "order"),
        ("N°", "order"),
        ("n.º", "order"),
        ("Nro.", "order"),
        ("Número de orden", "order"),
        ("ORDEN", "order"),
        ("Apellido y Nombre", "name"),
        ("APELLIDO Y NOMBRES:", "name"),
        ("Nombre", "name"),
        ("Apellido", "family"),
        ("D.N.I.", "document"),
        ("Nro. de documento", "document"),
        ("Tipo y número", "document"),
        ("Legajo", "file_number"),
        ("Carrera", "program"),
        ("Propuesta", "program"),
        ("Mesa", "table"),
        ("Domicilio", "address"),
        ("Dirección", "address"),
        ("Calidad", "status"),
        ("Estado", "status"),
        ("Firma", None),
        ("Observaciones", None),
    ],
)
def test_a_column_name_is_compared_without_case_accents_or_dots(text, key):
    assert key_of(text) == key


def test_a_long_name_read_from_an_image_may_have_one_letter_wrong():
    assert key_of("Docunento") is None
    assert key_of("Docunento", fuzzy=True) == "document"
    assert key_of("Domicilo", fuzzy=True) == "address"
    # Short names have to be exact: «DNl» could be anything.
    assert key_of("Mesas", fuzzy=True) is None


def test_the_key_folds_the_degree_sign_and_marks():
    assert header_key(" N° de  Orden: ") == header_key("Nº DE ORDEN") == "no de orden"


def test_a_header_needs_a_name_and_something_that_tells_people_apart():
    assert recognise(["Nº", "Apellido y nombre", "DNI"]).keys == ("order", "name", "document")
    assert recognise(["Apellido y nombre", "Domicilio"]) is None
    assert recognise(["Nº", "DNI", "Firma"]) is None
    assert recognise(["Texto", "de una carta"]) is None


def test_unknown_columns_are_ignored_and_a_repeated_one_counts_once():
    header = recognise(["Orden", "DNI", "Firma", "Apellido y nombre", "Observaciones", "DNI"])
    assert header.keys == ("order", "document", None, "name", None, None)
    assert header.fields() == ("order", "name", "document")


def test_family_name_and_given_names_can_come_in_two_columns():
    assert recognise(["Apellido", "Nombres", "Documento"]).keys == ("family", "given", "document")
    assert recognise(["Apellido", "Nombre", "Documento"]).keys == ("family", "given", "document")
    assert recognise(["Nombres", "Documento"]).keys == ("name", "document")
    assert recognise(["Apellido", "Nombres", "Documento"]).fields() == ("name", "document")


def test_the_words_of_a_header_line_are_split_into_column_names():
    words = ["Nº", "Apellido", "y", "nombre", "Tipo", "y", "número", "Lugar", "de", "voto"]
    joined = [False, True, True, False, True, True, False, True, True]
    labels = split_labels(words, joined)
    assert [" ".join(words[a:b]) for a, b in labels] == ["Nº", "Apellido y nombre", "Tipo y número", "Lugar de voto"]
    # Two known names close together are still two columns.
    assert split_labels(["Apellido", "Nombres"], [True]) == [(0, 1), (1, 2)]
