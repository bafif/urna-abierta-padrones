from urna_padrones import fields


def test_document_keeps_only_digits_and_checks_length():
    assert fields.clean_document("| 30.123.456 -").value == "30123456"
    assert fields.clean_document("30123456").valid
    assert fields.clean_document("1234567").valid
    assert not fields.clean_document("12345").valid
    assert not fields.clean_document("").valid


def test_a_stray_letter_in_a_document_is_never_dropped_silently():
    assert fields.clean_document("3O123456").value == "30123456"
    assert fields.clean_document("3O123456").valid
    assert not fields.clean_document("301X3456").valid


def test_file_number_may_be_blank():
    blank = fields.clean_file_number(" — ")
    assert blank.value is None and blank.valid


def test_file_number_format_and_slash_read_as_digit():
    assert fields.clean_file_number("A-1234/5").value == "A-1234/5"
    repaired = fields.clean_file_number("A-123415")
    assert repaired.value == "A-1234/5" and repaired.valid and repaired.repaired
    assert not fields.clean_file_number("A-12").valid


def test_status_accepts_a_single_known_letter():
    assert fields.clean_status("Á").value == "A"
    assert fields.clean_status("|P'").value == "P"
    assert not fields.clean_status("AA").valid
    assert not fields.clean_status("Z").valid


def test_name_needs_family_and_given_names():
    assert fields.clean_name("Núñez, María José").valid
    assert fields.clean_name("| De la Peña; Ana -").value == "De la Peña, Ana"
    assert not fields.clean_name("Solo Apellido").valid
    assert not fields.clean_name("Perez2, Ana").valid


def test_fold_removes_case_and_accents():
    assert fields.fold("NÚÑEZ") == "nunez"
