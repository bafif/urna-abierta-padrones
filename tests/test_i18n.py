import re
import string
from pathlib import Path

import pytest

import urna_padrones.lector
from urna_padrones import cli, errors, i18n
from urna_padrones.i18n import TEXTS

UI = Path(urna_padrones.lector.__file__).parent / "ui" / "lector.js"


def filled(text: str) -> list[str]:
    """The values a text fills in, like {count}: a translation has to fill the same ones."""
    return sorted(name for _, name, _, _ in string.Formatter().parse(text) if name)


def test_every_message_is_in_both_languages_and_fills_the_same_values():
    assert sorted(TEXTS["en"]) == sorted(TEXTS["es"])
    for key, text in TEXTS["es"].items():
        assert text.strip() and TEXTS["en"][key].strip(), key
        assert filled(TEXTS["en"][key]) == filled(text), key
    for code, (spanish, english) in errors.MESSAGES.items():
        assert spanish.strip() and english.strip(), code


def reader_texts() -> dict[str, dict[str, str]]:
    """The texts of the reader's screens, as lector.js has them."""
    script = UI.read_text(encoding="utf-8")
    block = script[script.index("const STRINGS = {"):script.index("\n  };\n")]
    texts = {}
    for language in ("es", "en"):
        part = block[block.index(f"\n    {language}: {{"):]
        part = part[:part.index("\n    },")]
        texts[language] = dict(re.findall(r"^ {6}'([\w.]+)': '((?:[^'\\]|\\.)*)',$", part, re.MULTILINE))
        assert len(texts[language]) == len(re.findall(r"^ {6}'", part, re.MULTILINE)), language
    return texts


def test_the_screens_of_the_reader_have_every_text_in_both_languages():
    texts = reader_texts()
    assert len(texts["es"]) > 50
    assert sorted(texts["en"]) == sorted(texts["es"])
    for key, text in texts["es"].items():
        assert texts["en"][key].strip(), key
        assert sorted(re.findall(r"\{(\w+)\}", texts["en"][key])) == sorted(re.findall(r"\{(\w+)\}", text)), key


def test_the_screens_of_the_reader_name_only_texts_that_exist_and_write_no_spanish_of_their_own():
    script = UI.read_text(encoding="utf-8")
    keys = reader_texts()["es"]
    code = script[script.index("\n  };\n"):]
    named = re.findall(r"\bt\('([\w.]+)'", code) + re.findall(r"\bkey: '([\w.]+)'", code)
    assert len(named) > 30
    assert [key for key in named if key not in keys] == []
    lines = [re.sub(r"(^|\s)//.*$", "", line) for line in code.splitlines()]
    assert [line.strip() for line in lines if re.search(r"[áéíóúñÁÉÍÓÚÑ¿¡]", line)] == []


@pytest.mark.parametrize(("env", "platform", "found", "expected"), [
    ({"LANG": "es_AR.UTF-8"}, "linux", None, "es"),
    ({"LANG": "en_US.UTF-8"}, "linux", None, "en"),
    ({"LC_ALL": "es_ES.UTF-8", "LANG": "en_US.UTF-8"}, "linux", None, "es"),
    ({"LC_MESSAGES": "en_GB.UTF-8", "LANG": "es_AR.UTF-8"}, "linux", None, "en"),
    ({"LANG": "en_US.UTF-8", "LANGUAGE": "en_US:es"}, "linux", None, "es"),
    ({"LANG": "C.UTF-8"}, "linux", None, "en"),
    # Windows and a program opened from the Finder have no LANG: the account says it.
    ({}, "win32", ["es_AR"], "es"),
    ({}, "win32", ["en_US"], "en"),
    ({}, "darwin", ["en-AR", "es-AR"], "es"),
    ({"LANG": "C"}, "darwin", ["pt-BR"], "en"),
])
def test_the_language_is_the_one_of_the_system(monkeypatch, env, platform, found, expected):
    monkeypatch.setattr(i18n, "_windows_languages", lambda: found)
    monkeypatch.setattr(i18n, "_mac_languages", lambda: found)
    languages = i18n.system_languages(env, platform)
    assert ("es" if any(i18n.is_spanish(tag) for tag in languages) else "en") == expected


def test_the_command_line_can_force_a_language():
    assert i18n.forced_language(["extract", "a.pdf", "--idioma", "en"]) == "en"
    assert i18n.forced_language(["--language=es", "report", "x"]) == "es"
    assert i18n.forced_language(["--idioma", "pt"]) is None
    assert i18n.forced_language(["extract", "a.pdf"]) is None


def test_the_help_comes_out_in_the_language_asked_for(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--idioma", "en", "extract", "--help"])
    english = capsys.readouterr().out
    assert "usage:" in english and "scanned PDF or PDF with text" in english and "--idioma" in english
    i18n.set_language(None)
    with pytest.raises(SystemExit):
        cli.main(["extract", "--help", "--idioma", "es"])
    spanish = capsys.readouterr().out
    assert "uso:" in spanish and "opciones" in spanish and "PDF escaneado o con texto" in spanish


def test_a_message_follows_the_language():
    assert str(errors.RollError("empty")) == "El PDF no tiene páginas."
    i18n.set_language("en")
    assert str(errors.RollError("empty")) == "The PDF has no pages."
    assert cli.said("el dígito del legajo no corresponde") == "the check digit of the legajo does not match"
    assert cli.said("distinto de la lectura: nombre, DNI") == "differs from the reading: name, DNI"
    assert cli.said("algo nuevo") == "algo nuevo"
