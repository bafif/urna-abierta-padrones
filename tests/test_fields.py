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
    assert fields.clean_file_number("A-1234/3").value == "A-1234/3"
    repaired = fields.clean_file_number("A-123413")
    assert repaired.value == "A-1234/3" and repaired.valid and repaired.repaired
    assert not fields.clean_file_number("A-12").valid


def test_file_number_check_digit():
    assert fields.clean_file_number("A-1234/3").valid
    # One misread digit breaks it, so the row goes to review instead of passing as sure.
    assert not fields.clean_file_number("A-1234/5").valid
    assert not fields.clean_file_number("A-1284/3").valid
    # Remainders that would give 10 or 11 are written as 1.
    assert fields.file_number_check_digit("1009") == 1 and fields.clean_file_number("C-1009/1").valid
    assert fields.file_number_check_digit("1003") == 1 and fields.clean_file_number("C-1003/1").valid
    # A repaired slash is only trusted when the digit adds up.
    repaired = fields.clean_file_number("A-123415")
    assert repaired.value == "A-1234/5" and repaired.repaired and not repaired.valid
    # Five-digit legajos were never measured, so only their shape is checked.
    assert fields.clean_file_number("A-12345/0").valid


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


def test_an_order_is_a_number_from_1():
    assert fields.clean_order("12") == fields.Checked("12", True)
    for raw in ("0", "00", "O", "o", "Q"):
        checked = fields.clean_order(raw)
        assert checked.value is not None and not checked.valid, raw


def test_only_the_digits_0_to_9_count_and_any_other_digit_makes_it_doubtful():
    for raw in ("²", "①", "1²", "³4", "٣"):
        order = fields.clean_order(raw)
        assert not order.valid, raw
        assert order.value is None or order.value.isascii(), raw
    document = fields.clean_document("9912345⁶")
    assert document.value == "9912345" and not document.valid
