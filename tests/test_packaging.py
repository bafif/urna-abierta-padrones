"""The parts of the packaged reader that can be checked without building it (packaging/)."""

import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"


def load(name: str):
    """A module of packaging/, under a name of its own (packaging/build.py is not the build package)."""
    spec = importlib.util.spec_from_file_location(f"lector_{name}", PACKAGING / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


notices = load("notices")
build = load("build")


def test_the_launcher_turns_telemetry_off_before_onnxruntime_loads(tmp_path):
    """The variable only counts if it is set before the import: a stand-in onnxruntime says what it saw."""
    fake = tmp_path / "fake"
    fake.mkdir()
    (fake / "onnxruntime.py").write_text('import os\nSEEN = os.environ.get("ORT_DISABLE_TELEMETRY")\n')
    probe = textwrap.dedent(f"""
        import sys
        sys.path[:0] = [{str(fake)!r}, {str(PACKAGING)!r}]
        import launcher
        assert launcher.reading_engine_loads()
        import onnxruntime
        print(onnxruntime.SEEN)
    """)
    env = {k: v for k, v in os.environ.items() if k != "ORT_DISABLE_TELEMETRY"}
    done = subprocess.run([sys.executable, "-c", probe], env=env, capture_output=True, text=True, check=True)
    assert done.stdout.strip() == "1"


def test_a_telemetry_file_in_the_temp_folder_fails_the_check(tmp_path, capsys):
    build.check_temp_folder(tmp_path, "self test")
    (tmp_path / "otro.txt").write_text("x")
    build.check_temp_folder(tmp_path, "self test")
    assert "otro.txt" in capsys.readouterr().out
    (tmp_path / ".ses").write_bytes(b"")
    with pytest.raises(SystemExit, match="telemetry"):
        build.check_temp_folder(tmp_path, "self test")


@pytest.mark.skipif(sys.platform == "win32", reason="the stand-in program is a script with a #! line")
@pytest.mark.parametrize("telemetry", [False, True])
def test_the_self_test_gives_the_program_a_fresh_temp_folder(tmp_path, monkeypatch, telemetry):
    """Every run gets an empty temp folder of its own, removed afterwards, and a .ses in it fails."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    seen = tmp_path / "seen.txt"
    program = bundle / "programa"
    program.write_text(
        textwrap.dedent(f"""\
            #!{sys.executable}
            import os
            from pathlib import Path
            temp = Path(os.environ["TMPDIR"])
            assert os.environ["TMP"] == os.environ["TEMP"] == str(temp)
            with open({str(seen)!r}, "a") as out:
                out.write(f"{{temp}} {{len(list(temp.iterdir()))}}\\n")
            if {telemetry!r}:
                (temp / ".ses").write_bytes(b"")
            print("ok")
        """)
    )
    program.chmod(0o755)
    monkeypatch.setattr(build, "bundle_folder", lambda: bundle)
    monkeypatch.setattr(build, "program", lambda: program)
    if telemetry:
        with pytest.raises(SystemExit, match="telemetry"):
            build.self_test()
    else:
        build.self_test()
    runs = [line.rsplit(" ", 1) for line in seen.read_text().splitlines()]
    assert len(runs) == (1 if telemetry else 2)
    assert len({folder for folder, _ in runs}) == len(runs)
    for folder, count in runs:
        assert count == "0"
        assert not Path(folder).exists()


def test_nested_license_files_keep_their_own_paths(tmp_path):
    """Libraries vendored inside a distribution keep their dist-info folder, so no text overwrites another."""
    site = tmp_path / "site"
    own = site / "herramienta-1.0.dist-info" / "licenses" / "LICENSE"
    vendored = [site / "herramienta" / "_vendor" / f"{name}.dist-info" / "licenses" / "LICENSE" for name in ("a", "b")]
    for number, path in enumerate([own, *vendored]):
        path.parent.mkdir(parents=True)
        path.write_text(f"Copyright {number}\n")
    copy = site / "herramienta" / "LICENSE"
    copy.write_text("Copyright 0\n")
    out = tmp_path / "out"
    written = notices.copy_unique([own, *vendored, copy], out, site)
    assert [Path(p).relative_to(out).as_posix() for p in written] == [
        "LICENSE",
        "herramienta/_vendor/a.dist-info/licenses/LICENSE",
        "herramienta/_vendor/b.dist-info/licenses/LICENSE",
    ]
    assert [Path(p).read_text() for p in written] == ["Copyright 0\n", "Copyright 1\n", "Copyright 2\n"]


def test_two_texts_with_the_same_path_are_both_kept(tmp_path):
    first, second = tmp_path / "uno" / "LICENSE", tmp_path / "dos" / "LICENSE"
    for path, text in ((first, "uno\n"), (second, "dos\n")):
        path.parent.mkdir()
        path.write_text(text)
    out = tmp_path / "out"
    written = notices.copy_unique([first, second], out, None)
    assert [Path(p).name for p in written] == ["LICENSE", "LICENSE-2"]
    assert [Path(p).read_text() for p in written] == ["uno\n", "dos\n"]
    # The same text again goes to the file it is already in.
    assert notices.copy_unique([first], out, None) == [written[0]]


def test_every_library_inside_python_has_its_text():
    for part in notices.PYTHON_PARTS:
        text = notices.OWN_TEXTS / part.text
        assert text.is_file(), part.name
        assert text.read_text(encoding="utf-8").strip(), part.name


def test_a_library_inside_python_is_listed_when_its_module_is_in_the_bundle(monkeypatch):
    monkeypatch.setattr(sys, "builtin_module_names", ("sys", "zlib"))
    names = [part.name for part in notices.python_parts({"_ssl", "_cv2"})]
    assert names == ["OpenSSL", "zlib"]
    assert [part.name for part in notices.python_parts(set())] == ["zlib"]


def test_the_notices_name_the_libraries_inside_python(tmp_path, monkeypatch):
    import zlib

    monkeypatch.setattr(sys, "builtin_module_names", ("sys", "zlib"))
    out = tmp_path / "notices"
    written = notices.write_notices(out, [], version="v1", extension_modules={"_ssl", "_decimal"})
    text = (out / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
    assert "  Includes: OpenSSL, zlib, mpdecimal\n" in text
    assert f"zlib {zlib.ZLIB_RUNTIME_VERSION}\n  License: Zlib\n" in text
    assert "  Text: licenses/python/zlib.txt\n  Part of: Python\n" in text
    assert "  Text: licenses/Apache-2.0.txt\n  Part of: Python\n" in text
    assert "SQLite" not in text
    files = {p.relative_to(out).as_posix() for p in written}
    assert {"licenses/python/zlib.txt", "licenses/python/mpdecimal.txt", "licenses/Apache-2.0.txt"} <= files
    assert not any(name.endswith("-2.txt") for name in files)


def test_the_icons_are_the_mark_in_every_size_each_system_asks_for():
    from PIL import Image

    spec = (PACKAGING / "lector.spec").read_text(encoding="utf-8")
    assert 'icon=str(ICONS / "lector.ico") if WINDOWS' in spec and 'icon=str(ICONS / "lector.icns")' in spec
    with Image.open(PACKAGING / "iconos" / "lector.ico") as ico:
        assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= set(ico.info["sizes"])
    with Image.open(PACKAGING / "iconos" / "lector.icns") as icns:
        assert {(512, 512, 1), (512, 512, 2)} <= set(icns.info["sizes"])
        drawn = icns.convert("RGBA")
    # Transparent corners, and the mark in the colour of «Aula».
    assert drawn.getpixel((0, 0))[3] == 0
    assert (0x17, 0x46, 0xC7, 255) in {colour for _, colour in drawn.getcolors(1 << 21)}

