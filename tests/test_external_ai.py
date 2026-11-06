"""Reading with an outside AI service, against a fake service on this computer: nothing here reaches the network.

The people are invented, with documents in the 99.000.000 range.
"""

import base64
import json
import socket
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest

from fake_layouts import listing_page, pdf_bytes, people, text_content
from fake_roll import draw_page, fake_rows, save_pdf
from urna_padrones import cli, external_ai
from urna_padrones.external_ai import AIError, MistralOCR, OpenAICompatible
from urna_padrones.reading import RollError, read_roll

KEY = "clave-de-prueba"
# A blank page, half the size of an A4 at 300 dpi: what the fake service answers does not depend on it.
BLANK = np.full((1754, 1240), 250, np.uint8)

MARKDOWN = """# Universidad de Prueba

Mesa Nº 12

| Nº | Apellido y nombre | DNI | Domicilio |
|----|-------------------|-----|-----------|
| 1 | Prueba, Ana | 99.000.001 | Calle Inventada 123 |
| 2 | **Ejemplo, Luis** | 99.000.0O2 | Pasaje Ejemplo 45 |
| 3 | Modelo, Inés | 99.0OO.X03 | |
"""
# The page after it, without a header of its own.
MARKDOWN_NEXT = """| 4 | Muestra, Tomás | 99.000.004 | Calle Modelo 7 |
|---|---|---|---|
| 5 | Peña, Sofía | 99.000.005 | Avenida de Prueba 900 |
"""
CHAT_ROWS = {
    "rows": [
        {"order": 1, "name": "Prueba, Ana", "document": "99.000.011", "legajo": "12345", "program": "Ingeniería Civil",
         "status": "A", "table": "Mesa 3", "address": None},
        {"order": 2, "name": "Ejemplo, Luis", "document": "99.000.0", "legajo": None, "program": "Ingeniería Civil",
         "status": "A", "table": "3"},
    ]
}


def answer(body, status: int = 200, headers: dict | None = None, delay: float = 0.0):
    return status, body, headers or {}, delay


def mistral_answer(markdown: str) -> tuple:
    return answer({"pages": [{"index": 0, "markdown": markdown, "images": []}], "model": "mistral-ocr-prueba"})


def chat_answer(content: str, finish: str = "stop") -> tuple:
    message = {"role": "assistant", "content": content}
    return answer({"choices": [{"index": 0, "message": message, "finish_reason": finish}]})


class FakeService:
    """A service on 127.0.0.1 that gives the answers it was given, in order, and the last one again once they run
    out. Each answer is (status, body, headers, seconds to wait before answering); `requests` keeps what came in."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests: list[dict] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                fake.requests.append({"path": self.path, "headers": dict(self.headers), "body": json.loads(body)})
                status, payload, headers, delay = fake.answers.pop(0) if len(fake.answers) > 1 else fake.answers[0]
                time.sleep(delay)
                data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                try:
                    self.send_response(status)
                    for name, value in headers.items():
                        self.send_header(name, value)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass  # the client stopped waiting

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.host = f"127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def fake():
    started = []

    def start(*answers) -> FakeService:
        started.append(FakeService(*answers))
        return started[-1]

    yield start
    for service in started:
        service.close()


def scan(tmp_path, pages: int = 1):
    path = tmp_path / "padron.pdf"
    save_pdf([BLANK] * pages, path)
    return path


def no_wait(seconds: float) -> None:
    pass


def test_mistral_reads_the_tables_of_only_the_pages_being_read(fake, tmp_path):
    service = fake(mistral_answer(MARKDOWN))
    reading = read_roll(scan(tmp_path, pages=2), pages=1, service=MistralOCR(KEY, service.url))

    assert len(service.requests) == 1
    sent = service.requests[0]
    assert sent["path"] == "/v1/ocr"
    assert sent["headers"]["Authorization"] == f"Bearer {KEY}"
    assert sent["body"]["model"] == external_ai.MISTRAL_MODEL
    document = sent["body"]["document"]
    assert document["type"] == "image_url" and document["image_url"].startswith("data:image/jpeg;base64,")
    # The page goes as a picture made again from its pixels, never as the PDF.
    picture = base64.b64decode(document["image_url"].split(",", 1)[1])
    assert picture.startswith(b"\xff\xd8\xff") and b"%PDF" not in picture

    found = [(r.values["order"], r.values["name"], r.values["document"], r.values["table"], r.values["address"])
             for r in reading.rows]
    assert found == [
        ("1", "Prueba, Ana", "99000001", "12", "Calle Inventada 123"),
        ("2", "Ejemplo, Luis", "99000002", "12", "Pasaje Ejemplo 45"),
        ("3", "Modelo, Inés", "9900003", "12", None),
    ]
    # A value the cleaners reject is reviewed; the service gives no confidence and none is made up.
    assert [row.needs_review for row in reading.rows] == [False, False, True]
    assert reading.rows[2].valid["document"] is False
    assert reading.pages_sent == [0] and reading.external_ai == f"{service.host} ({external_ai.MISTRAL_MODEL})"
    record = reading.records()[0]
    assert record["external_ai"] == reading.external_ai and record["confidence"] == {}


def test_a_page_without_a_header_takes_the_one_of_another_page(fake, tmp_path):
    service = fake(mistral_answer(MARKDOWN), mistral_answer(MARKDOWN_NEXT))
    reading = read_roll(scan(tmp_path, pages=2), workers=1, service=MistralOCR(KEY, service.url))
    assert [row.values["order"] for row in reading.rows] == ["1", "2", "3", "4", "5"]
    assert reading.rows[3].values["name"] == "Muestra, Tomás" and reading.rows[3].values["address"] == "Calle Modelo 7"
    # A scanned page does not take the table of the page before: a title read wrong would move people.
    assert reading.rows[3].values.get("table") is None and reading.rows[3].needs_review


def test_an_openai_compatible_service_answers_strict_json(fake, tmp_path):
    service = fake(chat_answer("```json\n" + json.dumps(CHAT_ROWS) + "\n```"))
    chosen = OpenAICompatible(KEY, service.url + "/v1", "modelo-de-prueba")
    reading = read_roll(scan(tmp_path), service=chosen)

    sent = service.requests[0]
    assert sent["path"] == "/v1/chat/completions"
    assert sent["body"]["model"] == "modelo-de-prueba"
    assert sent["body"]["response_format"] == {"type": "json_object"}
    content = sent["body"]["messages"][0]["content"]
    assert "JSON" in content[0]["text"] and content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")

    first, second = reading.rows
    assert first.values == {"order": "1", "name": "Prueba, Ana", "program": "Ingeniería Civil", "file_number": "12345",
                            "document": "99000011", "status": "A", "table": "3"}
    assert not first.needs_review
    assert second.valid["document"] is False and second.needs_review
    assert reading.external_ai == f"{service.host} (modelo-de-prueba)"


def test_a_service_that_refuses_json_mode_is_asked_again_without_it(fake, tmp_path):
    refusal = answer({"error": {"message": "response_format is not supported for this model"}}, status=400)
    service = fake(refusal, chat_answer(json.dumps(CHAT_ROWS)))
    reading = read_roll(scan(tmp_path), service=OpenAICompatible(KEY, service.url + "/v1", "modelo-de-prueba"))
    assert len(reading.rows) == 2
    assert "response_format" in service.requests[0]["body"] and "response_format" not in service.requests[1]["body"]


@pytest.mark.parametrize("kind, body", [
    ("chat", chat_answer("Acá está el padrón: Prueba, Ana, 99.000.011")),
    ("chat", chat_answer(json.dumps({"rows": [{"name": ["Prueba", "Ana"]}]}))),
    ("chat", chat_answer('{"rows": [{"name": "Prueba, Ana"', finish="length")),
    ("mistral", answer(b"<html>no es JSON</html>")),
])
def test_an_answer_that_is_not_the_json_asked_for_is_an_error(fake, tmp_path, kind, body):
    service = fake(body)
    options = {"attempts": 2, "wait": no_wait}
    chosen = (OpenAICompatible(KEY, service.url + "/v1", "modelo-de-prueba", **options) if kind == "chat"
              else MistralOCR(KEY, service.url, **options))
    with pytest.raises(AIError, match="no es el JSON pedido"):
        read_roll(scan(tmp_path), service=chosen)
    assert len(service.requests) == 2


def test_a_refused_key_is_said_at_once(fake, tmp_path):
    service = fake(answer({"message": "Unauthorized"}, status=401))
    with pytest.raises(AIError, match="rechazó la clave") as error:
        read_roll(scan(tmp_path), service=MistralOCR(KEY, service.url, wait=no_wait))
    assert len(service.requests) == 1 and KEY not in str(error.value)


def test_a_busy_service_is_asked_again_after_the_wait_it_asks_for(fake, tmp_path):
    service = fake(answer({"message": "Too many requests"}, status=429, headers={"Retry-After": "2"}),
                   mistral_answer(MARKDOWN))
    waits = []
    reading = read_roll(scan(tmp_path), service=MistralOCR(KEY, service.url, wait=waits.append))
    assert len(reading.rows) == 3 and len(service.requests) == 2 and waits == [2.0]


def test_a_quota_that_ran_out_is_said(fake, tmp_path):
    service = fake(answer({"error": {"message": "You exceeded your current quota", "code": "insufficient_quota"}},
                          status=429))
    with pytest.raises(AIError, match="cuota"):
        read_roll(scan(tmp_path), service=OpenAICompatible(KEY, service.url + "/v1", "m", wait=no_wait))
    assert len(service.requests) == 1


def test_a_service_that_does_not_answer_in_time_is_an_error(fake, tmp_path):
    service = fake(mistral_answer(MARKDOWN)[:3] + (1.5,))
    started = time.monotonic()
    with pytest.raises(AIError, match="no contestó en 0.2 segundos, en 2 intentos"):
        read_roll(scan(tmp_path), service=MistralOCR(KEY, service.url, timeout=0.2, attempts=2, wait=no_wait))
    assert len(service.requests) == 2 and time.monotonic() - started < 1.4


def test_the_service_and_its_address_are_checked_before_anything_is_sent():
    with pytest.raises(AIError, match=external_ai.KEY_VARIABLE):
        MistralOCR("")
    with pytest.raises(AIError, match="https://"):
        OpenAICompatible(KEY, "http://ejemplo.com/v1", "m")
    with pytest.raises(AIError, match="usuario ni contraseña"):
        OpenAICompatible(KEY, "https://alguien:secreto@ejemplo.com/v1", "m")
    with pytest.raises(AIError, match="--ia-url"):
        OpenAICompatible(KEY, None, "m")
    with pytest.raises(AIError, match="--ia-modelo"):
        OpenAICompatible(KEY, "https://ejemplo.com/v1", None)
    assert MistralOCR(KEY).url == external_ai.MISTRAL_URL


def test_pages_with_text_are_read_from_their_text_and_not_sent(fake, tmp_path):
    keys, headers, column_x = ["order", "document", "name"], ["Nº", "DNI", "Apellido y nombre"], [40, 80, 160, 330]
    path = tmp_path / "padron.pdf"
    path.write_bytes(pdf_bytes([{"content": listing_page(people(4), headers, keys, column_x)}, {"image": BLANK}]))
    service = fake(mistral_answer(MARKDOWN))
    reading = read_roll(path, service=MistralOCR(KEY, service.url))
    assert len(service.requests) == 1
    assert reading.pages_with_text == [0] and reading.pages_sent == [1]
    assert len(reading.rows) == 4 + 3
    # The roll as a whole was seen by the service: every row says so.
    assert {record["external_ai"] for record in reading.records()} == {reading.external_ai}


def test_the_command_line_warns_and_sends_nothing_without_both_flags(fake, tmp_path, capsys, monkeypatch):
    service = fake(mistral_answer(MARKDOWN))
    roll, out = scan(tmp_path), tmp_path / "salida.jsonl"
    command = ["extract", str(roll), "--out", str(out), "--ia", "mistral", "--ia-url", service.url]

    monkeypatch.delenv(external_ai.KEY_VARIABLE, raising=False)
    assert cli.main(command + ["--acepto-enviar"]) == 2
    assert external_ai.KEY_VARIABLE in capsys.readouterr().err

    monkeypatch.setenv(external_ai.KEY_VARIABLE, KEY)
    assert cli.main(command) == 2
    warned = capsys.readouterr().err
    assert "Mistral AI" in warned and "nombres y los documentos" in warned and "entrenar" in warned
    assert "la app puede no aceptarlo" in warned and "--acepto-enviar" in warned

    assert cli.main(["extract", str(roll), "--out", str(out), "--ia-modelo", "m", "--acepto-enviar"]) == 2
    assert "van con --ia" in capsys.readouterr().err
    assert service.requests == [] and not out.exists()


def test_the_command_line_reads_with_the_service_and_the_roll_file_says_so(fake, tmp_path, capsys, monkeypatch):
    service = fake(mistral_answer(MARKDOWN))
    out, padron = tmp_path / "salida.jsonl", tmp_path / "padron.padron"
    monkeypatch.setenv(external_ai.KEY_VARIABLE, KEY)
    command = ["extract", str(scan(tmp_path)), "--out", str(out), "--ia", "mistral", "--ia-url", service.url,
               "--acepto-enviar"]
    assert cli.main(command) == 0
    said = capsys.readouterr()
    assert "Mistral AI" in said.err and f"páginas mandadas a Mistral AI ({service.host}): 1" in said.out
    assert len(service.requests) == 1

    assert cli.main(["padron", str(out), "--out", str(padron)]) == 0
    assert "lo vio una IA externa" in capsys.readouterr().out
    with zipfile.ZipFile(padron) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["extraction"] == {"tool": "urna-padrones", "external_ai": True,
                                      "provider": f"{service.host} ({external_ai.MISTRAL_MODEL})"}


def test_without_a_service_the_reading_opens_no_socket(tmp_path, monkeypatch, capsys):
    roll = tmp_path / "padron.pdf"
    save_pdf([draw_page(fake_rows(6))], roll)
    opened = []

    def refuse(self, *args, **kwargs):
        opened.append(args)
        raise OSError("esta prueba no abre conexiones")

    monkeypatch.setattr(socket.socket, "__init__", refuse)
    assert cli.main(["extract", str(roll), "--out", str(tmp_path / "salida.jsonl")]) == 0
    assert opened == []
    assert "6 filas" in capsys.readouterr().out


def test_a_page_with_text_is_never_sent_even_when_its_text_is_not_a_list(fake, tmp_path):
    keys, column_x = ["order", "document", "name"], [40, 80, 160, 330]
    service = fake(mistral_answer(MARKDOWN))
    # A cover with a title, and then a listing read from its text.
    covered = tmp_path / "tapa.pdf"
    covered.write_bytes(pdf_bytes([
        {"content": text_content([(40, 100, 14, "Padron definitivo 2026 - Claustro estudiantes")])},
        {"content": listing_page(people(4), ["Nº", "DNI", "Apellido y nombre"], keys, column_x)},
    ]))
    reading = read_roll(covered, workers=1, service=MistralOCR(KEY, service.url))
    assert reading.pages_sent == [] and reading.pages_with_text == [1]
    # Read here as without a service, and nothing says that a service saw it.
    assert reading.records() == read_roll(covered, workers=1).records()
    assert reading.external_ai is None and "external_ai" not in reading.records()[0]
    # A listing whose header names nothing this program knows: read here from its picture, or not at all.
    unknown = tmp_path / "otro.pdf"
    unknown.write_bytes(pdf_bytes([{"content": listing_page(people(6), ["#", "Identificacion", "Elector"], keys,
                                                             column_x)}]))
    try:
        assert read_roll(unknown, service=MistralOCR(KEY, service.url)).pages_sent == []
    except RollError as error:
        assert error.code == "unknown_layout"
    assert service.requests == []
