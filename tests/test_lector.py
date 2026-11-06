"""The desktop reader, driven through its API as its screens do, on a roll of invented people."""

import http.client
import io
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pytest
from fake_roll import PAGE_SIZE, draw_page, fake_rows, find_font, save_pdf

from urna_padrones.lector.server import CSP, FOLDER_PREFIX, PID_FILE, LectorServer, remove_leftovers
from urna_padrones.lector.session import Session, clean_title, file_name_for

ROWS_PER_PAGE = 12
# A document with nine digits cannot be right: that row is always one to review.
BAD_ROW = 4
BAD_DOCUMENT = "990012345"
FIXED_DOCUMENT = "99012345"


def start_reader(tmp: Path, *args: str) -> tuple[subprocess.Popen, str]:
    """The reader as a person starts it, with its private folder inside `tmp`."""
    env = {**os.environ, "TMPDIR": str(tmp), "TEMP": str(tmp), "TMP": str(tmp), "URNA_NO_BROWSER": "1"}
    process = subprocess.Popen(
        [sys.executable, "-m", "urna_padrones.lector", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    first = process.stdout.readline().strip()
    assert first.startswith("http://127.0.0.1:"), first
    return process, first


def private_folders(tmp: Path) -> list[Path]:
    return sorted(tmp.glob("urna-lector-*"))


def copies(folder: Path) -> list[Path]:
    """What the reader keeps in its private folder, besides the pid of its run."""
    return sorted(item for item in folder.iterdir() if item.name != PID_FILE)


def request(url: str, data: bytes | None = None, headers: dict | None = None, method: str | None = None):
    """Status, headers and body, also for answers that are not 200."""
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()


def api(base: str, path: str, body: dict | None = None, method: str | None = None):
    data = None if body is None else json.dumps(body).encode()
    status, _, content = request(base + "api/" + path, data, {"Content-Type": "application/json"}, method)
    return status, json.loads(content)


def wait_for(base: str, condition, seconds: float = 240) -> dict:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        _, state = api(base, "state")
        if condition(state):
            return state
        time.sleep(0.25)
    raise AssertionError(f"the reader did not get there in time: {state}")


@pytest.fixture(scope="module")
def roll_pdf(tmp_path_factory) -> tuple[Path, list[dict]]:
    """Two pages of invented people, one of them misread on purpose, and a last page without a table."""
    font, accents = find_font()
    rows = fake_rows(2 * ROWS_PER_PAGE, seed=7, accents=accents)
    rows[BAD_ROW]["document"] = BAD_DOCUMENT
    pages = [
        draw_page(rows[:ROWS_PER_PAGE], angle=0.5, seed=11, font=font),
        draw_page(rows[ROWS_PER_PAGE:], angle=-0.4, seed=12, font=font),
        np.full((PAGE_SIZE[1], PAGE_SIZE[0]), 250, dtype=np.uint8),
    ]
    path = tmp_path_factory.mktemp("roll") / "padron de prueba.pdf"
    save_pdf(pages, path)
    return path, rows


@pytest.fixture(scope="module")
def reader(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("reader")
    process, url = start_reader(tmp)
    yield url, tmp
    process.terminate()
    process.wait(timeout=30)


def upload(base: str, path: Path, name: str | None = None):
    query = urllib.parse.quote(name or path.name)
    status, _, content = request(f"{base}api/pdf?name={query}", path.read_bytes(), {"Content-Type": "application/pdf"})
    return status, json.loads(content)


def test_screens_come_with_a_strict_policy(reader):
    base, _ = reader
    status, headers, content = request(base)
    assert status == 200
    assert headers["Content-Security-Policy"] == CSP
    assert b"lector.js" in content
    for name in ("lector.js", "lector.css", "tema.css", "temas.js", "aplicar-tema.js"):
        assert request(base + name)[0] == 200
    assert request(base + "fuentes/atkinson-hyperlegible-next-latin-wght-normal.woff2")[0] == 200
    for name in ("README.md", "../server.py", "fuentes/atkinson-hyperlegible-next.LICENSE.txt", "muestra.png"):
        assert request(base + name)[0] == 404


def test_only_its_own_address_and_name_get_in(reader):
    base, _ = reader
    origin = base.split("/", 3)[:3]
    root = "/".join(origin)
    port = root.rsplit(":", 1)[1]
    assert request(base + "api/state", headers={"Host": f"localhost:{port}"})[0] == 403
    assert request(base + "api/state", headers={"Host": "padron.example"})[0] == 403
    assert request(f"{root}/")[0] == 404
    assert request(f"{root}/otro/api/state")[0] == 404
    assert request(f"{root}/otro/")[0] == 404
    status, _, _ = request(base + "api/reset", b"{}", {"Origin": "http://padron.example"})
    assert status == 403
    assert request(base + "api/quit")[0] == 405


def test_the_address_without_its_final_slash_leads_to_the_screens(reader):
    base, _ = reader
    port, token = base.split(":")[2].split("/")[:2]
    connection = http.client.HTTPConnection("127.0.0.1", int(port), timeout=30)
    connection.request("GET", f"/{token}")
    answer = connection.getresponse()
    assert (answer.status, answer.getheader("Location")) == (308, f"/{token}/")
    connection.close()
    status, _, content = request(base.rstrip("/"))
    assert status == 200 and b"lector.js" in content


def test_a_file_that_is_not_a_pdf_is_refused_and_not_kept(reader, tmp_path):
    base, tmp = reader
    letter = tmp_path / "carta.pdf"
    letter.write_bytes(b"Hola, esto no es un PDF.")
    status, body = upload(base, letter)
    assert (status, body) == (400, {"error": "not_pdf"})
    (folder,) = private_folders(tmp)
    assert copies(folder) == []


def test_reads_reviews_and_saves(reader, roll_pdf):
    base, tmp = reader
    path, drawn = roll_pdf
    status, body = upload(base, path)
    assert (status, body) == (200, {"pages": 3, "name": "padron de prueba.pdf"})
    (folder,) = private_folders(tmp)
    (copy,) = copies(folder)
    assert copy.read_bytes() == path.read_bytes()
    if os.name == "posix":
        assert folder.stat().st_mode & 0o077 == 0
        assert copy.stat().st_mode & 0o077 == 0

    assert api(base, "rows")[0] == 409
    assert api(base, "read", {}) == (202, {"ok": True})
    assert api(base, "read", {})[0] == 409
    seen = []
    state = wait_for(base, lambda s: seen.append(s) or s["state"] != "reading")
    assert state["state"] == "done", state
    reading = [s for s in seen if s["state"] == "reading"]
    assert all(s["pages_total"] == 3 for s in reading)
    assert [s["pages_done"] for s in reading] == sorted(s["pages_done"] for s in reading)
    assert state["rows_found"] == len(drawn)
    summary = state["summary"]
    assert summary["people"] == len(drawn)
    assert summary["pages_read"] == 3
    assert summary["pages_without_table"] == [3]
    assert summary["doubtful"] >= 1 and summary["reviewed"] == 0

    _, everything = api(base, "rows")
    assert len(everything["rows"]) == len(drawn)
    _, doubtful = api(base, "rows?which=doubtful")
    assert len(doubtful["rows"]) == summary["doubtful"]
    bad = everything["rows"][BAD_ROW]
    assert bad["values"]["document"] == BAD_DOCUMENT
    assert bad["valid"]["document"] is False and bad["needs_review"] is True
    assert bad["page"] == 1
    assert bad["index"] in [row["index"] for row in doubtful["rows"]]

    status, headers, png = request(f"{base}api/rows/{BAD_ROW}/image")
    assert status == 200 and headers["Content-Type"] == "image/png"
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert request(f"{base}api/rows/999/image")[0] == 404

    # A change that still breaks the format waits for the person to confirm it.
    status, still = api(base, f"rows/{BAD_ROW}", {"values": {"document": "123"}})
    assert status == 200
    assert still["valid"]["document"] is False
    assert still["needs_review"] is True and still["reviewed"] is False
    status, edited = api(base, f"rows/{BAD_ROW}", {"values": {"document": f" {FIXED_DOCUMENT} ", "order": bad["values"]["order"]}})
    assert status == 200
    assert edited["values"]["document"] == FIXED_DOCUMENT
    assert edited["valid"]["document"] is True
    assert edited["needs_review"] is False and edited["reviewed"] is True
    assert api(base, f"rows/{BAD_ROW}", {"values": "no"})[0] == 400
    assert api(base, "rows/999/ok", {})[0] == 404

    last = len(drawn) - 1
    status, kept = api(base, f"rows/{last}", {"values": {"status": "X"}, "ok": True})
    assert status == 200 and kept["valid"]["status"] is False and kept["reviewed"] is True
    # A digit such as ² is not a number of the roll: it is not taken, and nothing breaks.
    status, odd = api(base, f"rows/{last}", {"values": {"order": "²"}, "ok": True})
    assert status == 200 and odd["valid"]["order"] is False
    assert api(base, "state")[0] == 200
    assert request(base + "api/save")[0] == 200
    others = [row for row in doubtful["rows"] if row["index"] not in (BAD_ROW, last)]
    for row in others[:1]:
        status, confirmed = api(base, f"rows/{row['index']}/ok", {})
        assert status == 200 and confirmed["reviewed"] is True and confirmed["needs_review"] is False
    _, state = api(base, "state")
    _, doubtful = api(base, "rows?which=doubtful")
    assert state["summary"]["reviewed"] == sum(row["reviewed"] for row in doubtful["rows"]) >= 1

    status, headers, data = request(base + "api/save?title=" + urllib.parse.quote("Padrón de prueba / 2026"))
    assert status == 200
    assert headers["Content-Disposition"] == 'attachment; filename="Padron-de-prueba-2026.padron"'
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        electors = [json.loads(line) for line in archive.read("electors.jsonl").decode().splitlines()]
    assert manifest["format"] == "padron-abierto"
    assert manifest["title"] == "Padrón de prueba / 2026"
    assert manifest["extraction"]["external_ai"] is False
    assert manifest["files"]["electors"] == {"path": "electors.jsonl", "count": len(drawn)}
    assert len(electors) == len(drawn)
    fixed = electors[BAD_ROW]
    assert {"type": "DNI", "value": FIXED_DOCUMENT} in fixed["identifiers"]
    assert fixed["id"] == f"d-{FIXED_DOCUMENT}"
    assert fixed["review"] == {"status": "ok"}
    assert electors[last]["extra"]["status"] == "X"
    assert "order" not in electors[last]
    pending = sum(e["review"]["status"] == "pending" for e in electors)
    assert pending == state["summary"]["to_review"]

    assert api(base, "reset", {}) == (200, {"ok": True})
    assert copies(folder) == []
    assert api(base, "state")[1]["state"] == "empty"


def test_a_cancelled_reading_forgets_the_file(reader, roll_pdf):
    base, tmp = reader
    path, _ = roll_pdf
    assert upload(base, path)[0] == 200
    assert api(base, "read", {})[0] == 202
    assert api(base, "cancel", {}) == (200, {"ok": True})
    state = wait_for(base, lambda s: s["state"] != "reading", seconds=30)
    assert (state["state"], state["error"]) == ("empty", "cancelled")
    (folder,) = private_folders(tmp)
    assert copies(folder) == []


def test_quit_deletes_the_private_folder(tmp_path, roll_pdf):
    process, base = start_reader(tmp_path)
    try:
        assert upload(base, roll_pdf[0])[0] == 200
        (folder,) = private_folders(tmp_path)
        assert (folder / PID_FILE).read_text() == str(process.pid)
        assert api(base, "quit", {}) == (200, {"ok": True})
        assert process.wait(timeout=30) == 0
    finally:
        process.kill()
    assert private_folders(tmp_path) == []
    help_lines = process.stdout.read().splitlines()
    assert help_lines[0].startswith("Urna Abierta, lector de padrones:")
    assert help_lines[2].startswith("Urna Abierta, roll reader:") and "Close the reader" in help_lines[3]


def leftover(tmp: Path, name: str, pid: str | None) -> Path:
    folder = tmp / name
    folder.mkdir()
    (folder / "padron-1.pdf").write_bytes(b"%PDF-1.4 inventado")
    if pid is not None:
        (folder / PID_FILE).write_text(pid)
    return folder


def finished_pid() -> int:
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()
    return process.pid


def test_folders_left_by_a_run_that_died_are_deleted_on_start(tmp_path):
    dead = leftover(tmp_path, f"{FOLDER_PREFIX}muerto", str(finished_pid()))
    alive = leftover(tmp_path, f"{FOLDER_PREFIX}vivo", str(os.getpid()))
    unknown = leftover(tmp_path, f"{FOLDER_PREFIX}sin-pid", None)
    odd = leftover(tmp_path, f"{FOLDER_PREFIX}raro", "no es un número")
    other = leftover(tmp_path, "otra-cosa", str(finished_pid()))
    assert remove_leftovers(tmp_path) == 1
    assert not dead.exists()
    assert all(folder.exists() for folder in (alive, unknown, odd, other))


def test_the_reader_cleans_up_after_a_run_that_died(tmp_path):
    dead = leftover(tmp_path, f"{FOLDER_PREFIX}muerto", str(finished_pid()))
    process, base = start_reader(tmp_path)
    try:
        assert not dead.exists()
        assert len(private_folders(tmp_path)) == 1
        assert api(base, "quit", {}) == (200, {"ok": True})
        assert process.wait(timeout=30) == 0
    finally:
        process.kill()
    assert private_folders(tmp_path) == []


@pytest.mark.skipif(os.name != "posix", reason="signals as on Linux and macOS")
@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
def test_a_signal_deletes_the_private_folder(tmp_path, roll_pdf, signum):
    process, base = start_reader(tmp_path)
    try:
        assert upload(base, roll_pdf[0])[0] == 200
        process.send_signal(signum)
        assert process.wait(timeout=30) == 0
    finally:
        process.kill()
    assert private_folders(tmp_path) == []
    assert process.stderr.read() == ""


def test_it_is_idle_only_when_nothing_is_being_read(tmp_path):
    session = Session(tmp_path)
    server = LectorServer(session, idle_seconds=0.05)
    try:
        assert not server.idle()
        time.sleep(0.1)
        assert server.idle()
        session.state = "reading"
        assert not server.idle()
        session.state = "done"
        server.touch()
        assert not server.idle()
    finally:
        server.server_close()


def test_file_names_and_titles_are_safe():
    assert file_name_for("Padrón Ingeniería 2026") == "Padron-Ingenieria-2026.padron"
    assert file_name_for("../../etc/passwd") == "etc-passwd.padron"
    assert file_name_for("") == "padron.padron"
    assert file_name_for(None) == "padron.padron"
    assert file_name_for("ñññ") == "nnn.padron"
    assert len(file_name_for("a" * 500)) <= 80 + len(".padron")
    assert clean_title("  Padrón \n de   prueba ") == "Padrón de prueba"
    assert clean_title("   ") is None
    assert len(clean_title("x" * 500)) == 200


def test_self_test_works_without_network():
    done = subprocess.run(
        [sys.executable, "-m", "urna_padrones.lector", "--self-test"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert (done.returncode, done.stdout) == (0, "ok\n"), done.stderr


def test_self_test_fails_without_the_model(tmp_path):
    env = {**os.environ, "URNA_PADRONES_MODELO": str(tmp_path / "no-hay-modelo.onnx")}
    done = subprocess.run(
        [sys.executable, "-m", "urna_padrones.lector", "--self-test"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=env,
    )
    assert done.returncode == 1 and done.stdout == ""
