"""The invented rolls the other tests read."""

import pypdfium2 as pdfium

import fake_roll


def test_draws_a_roll_of_invented_people(tmp_path):
    path = tmp_path / "padron.pdf"
    rows = fake_roll.make_fake_roll_pdf(path, pages=2, rows_per_page=5)
    assert [row["order"] for row in rows] == [str(n) for n in range(1, 11)]
    assert all(row["document"].startswith("99") and len(row["document"]) == 8 for row in rows)
    document = pdfium.PdfDocument(path)
    assert len(document) == 2
    width, height = document[0].get_size()
    document.close()
    assert (round(width * 300 / 72), round(height * 300 / 72)) == fake_roll.PAGE_SIZE


def test_without_a_font_with_accents_it_draws_plain_letters(monkeypatch, tmp_path):
    monkeypatch.setattr(fake_roll, "accent_font_path", lambda: None)
    monkeypatch.setattr(fake_roll, "KNOWN_FONTS", [])
    rows = fake_roll.make_fake_roll_pdf(tmp_path / "padron.pdf", pages=1, rows_per_page=5)
    assert len(rows) == 5
    assert all(value.isascii() for row in rows for value in row.values())
