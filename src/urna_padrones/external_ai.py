"""Read a roll with an outside AI service, with the user's own key.

The reading is local by default (see reading.py), and nothing here runs unless a program passes a service
to read_roll. Then each page of a scan or a photo goes to that service as a JPEG made again from the page as
the reader renders it: never the PDF, never the pages that are not being read, and without what a photo
carries, such as where it was taken. The pages of a PDF with text are never sent: they are read here, from
their text or, when it is not a list this program knows, from their picture. Every value that comes back goes
through the same cleaners and review rules as one read here, and a row is never taken as surer than they
say: the service gives no confidence, and none is made up.

Two kinds of service:

- Mistral OCR, on Mistral's European endpoint. It answers each page as Markdown, and the tables in it are
  read by the names in their header, as a scan is (see headers.py).
- Any service that answers OpenAI's chat completions with images, such as OVHcloud AI Endpoints, Scaleway or
  OpenAI itself. It is asked for strict JSON, one object per person, which is checked before it is used.

Requests go straight to the address chosen: a redirect is refused, and a service on this same computer is
reached without the proxy the environment may name. Each one has a time limit for the whole answer, and is
tried again a few times when the service is busy or does not answer.
"""

import base64
import http.client
import json
import re
import socket
import ssl
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field

import cv2
import numpy as np

from .headers import Header, mesa_in, recognise
from .i18n import t
from .table import BY_HEADER, COLUMNS, FACULTY, Row, fits_faculty, is_header, is_person, join_name

KEY_VARIABLE = "URNA_PADRONES_IA_CLAVE"
MISTRAL = "mistral"
OPENAI_COMPATIBLE = "openai-compatible"
KINDS = (MISTRAL, OPENAI_COMPATIBLE)
MISTRAL_URL = "https://api.eu.mistral.ai"
MISTRAL_MODEL = "mistral-ocr-latest"
# Seconds to wait for one whole answer, and how many times a page is tried in all.
TIMEOUT = 120.0
ATTEMPTS = 3
# The longest wait before trying again, also when the service asks for a longer one.
MAX_WAIT = 30.0
JPEG_QUALITY = 90
# An answer with more people, or more lines of tables, than this for one page is not a page of a roll.
MAX_ROWS = 400
# The longest answer taken for one page, in bytes: a page of a roll is a small part of it.
MAX_ANSWER = 4_000_000
# The longest value taken, as the app takes a name or an address: a longer one is not a cell of a roll.
MAX_VALUE = 200
# How often a request being waited for asks whether the reading was cancelled, in seconds.
POLL_SECONDS = 0.1
# How a row read by a service is told from one read here ("ocr") or taken from the text of a PDF ("text").
SOURCE = "ia"
# Only a service on this same computer may be reached without encryption.
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")
# What the service is asked for, one object per person, and the value of the extraction each one goes to.
ANSWER_KEYS = {
    "order": "order",
    "name": "name",
    "document": "document",
    "legajo": "file_number",
    "program": "program",
    "status": "status",
    "table": "table",
    "address": "address",
}
PROMPT = """This image is one page of an electoral roll (padrón) from Argentina. List every person on it.
Answer only with JSON, with no other text, in this shape:
{"columns": ["order", "name", ...], "rows": [{"order": "...", "name": "...", "document": "...", "legajo": "...",
"program": "...", "status": "...", "table": "...", "address": "..."}]}
"columns" lists, with the keys below, every value the page has a column for (for table, also a title), even when
it cannot be read on some or all of the rows. One object per person, in the order of the page. Copy each value
exactly as it is printed, without correcting, completing or guessing anything. Use null for a value the page
does not have or that cannot be read.
- order: the order number (Nº, Orden).
- name: the full name as printed (Apellido y nombre). If the family name and the given names are in two
  columns, write "Family, Given".
- document: the document number (DNI, Documento), with the dots it has.
- legajo: the student number (Legajo).
- program: the degree (Carrera, Propuesta).
- status: what the status column says (Calidad, Estado, Condición).
- table: the voting table (Mesa) of the person, from its column or from a title such as "Mesa 12" above the list.
- address: the address (Domicilio, Dirección).
Leave out headers, titles, totals, signatures and anything that is not a person. If the page lists nobody,
answer {"columns": [], "rows": []}."""


class AIError(Exception):
    """A reading with an outside service that cannot go on. str() gives the message in Spanish."""


class _Refused(Exception):
    """The service did not take the request, for a reason other than the key or the quota."""

    def __init__(self, status: int, detail: str):
        super().__init__(status, detail)
        self.status = status
        self.detail = detail


class _Malformed(Exception):
    """The answer came, but it is not what was asked for."""


class _TooLong(Exception):
    """The answer is longer than any page of a roll can give."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is an error: following it would send the key and the page to an address nobody chose."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass
class AITable:
    """A table as a service gave it: the names in its header, or the values of each row, and a «Mesa» title."""

    rows: list[list[str]]
    # The key of each column when the service said it, as the chat services do; None when the first row is a header.
    keys: tuple[str | None, ...] | None = None
    # The table a title above it, such as «Mesa 12», gives to its rows.
    title: str | None = None


@dataclass
class AIPage:
    """What a service gave for one page."""

    tables: list[AITable] = field(default_factory=list)


class Service:
    """A service that reads pages. read_page is called from several threads at once."""

    company = ""

    def __init__(
        self,
        key: str,
        url: str,
        model: str,
        *,
        timeout: float = TIMEOUT,
        attempts: int = ATTEMPTS,
        wait: Callable[[float], None] | None = None,
    ):
        """`wait(seconds)` makes the pause before trying again, for tests; by default the pause asks the checkpoint
        of read_page ten times a second, as the wait for an answer does."""
        if not key or not key.strip():
            raise AIError(t("ai.no_key", variable=KEY_VARIABLE))
        # A key goes in a header, which takes only plain letters, numbers and signs: anything else would stop the
        # request with an error that shows the key.
        if not _visible_ascii(key.strip()):
            raise AIError(t("ai.odd_key", variable=KEY_VARIABLE))
        if not model or not model.strip():
            raise AIError(t("ai.no_model"))
        if not _visible_ascii(url.strip()):
            raise AIError(t("ai.odd_url"))
        parts = urllib.parse.urlsplit(url.strip())
        if parts.scheme not in ("https", "http") or not parts.hostname:
            raise AIError(t("ai.bad_url"))
        if parts.username or parts.password:
            raise AIError(t("ai.url_login", variable=KEY_VARIABLE))
        if parts.scheme == "http" and parts.hostname not in LOCAL_HOSTS:
            raise AIError(t("ai.plain_http"))
        if parts.query or parts.fragment:
            raise AIError(t("ai.url_query"))
        self.key = key.strip()
        self.url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
        self.host = parts.netloc
        self.model = model.strip()
        self.timeout = timeout
        self.attempts = max(1, attempts)
        self.wait = wait
        # A proxy named by the environment (https_proxy) only tunnels an https:// request, which stays encrypted end
        # to end; a service on this computer is reached directly, so that no proxy sees what goes to it.
        handlers = [_NoRedirect()] + ([urllib.request.ProxyHandler({})] if parts.hostname in LOCAL_HOSTS else [])
        self._opener = urllib.request.build_opener(*handlers)

    @property
    def name(self) -> str:
        """What the roll file records as the service that saw the data: where it is, and which model read."""
        return f"{self.host} ({self.model})"

    @property
    def shown(self) -> str:
        """The service as a person knows it."""
        return f"{self.company} ({self.host})" if self.company else self.host

    def read_page(self, image: np.ndarray, page: int, checkpoint: Callable[[], None] | None = None) -> AIPage:
        """What the service reads on one page, given as the 2D uint8 array the reader renders.

        `checkpoint` is called before each try and ten times a second while an answer or the pause before
        trying again is waited for: raising from it abandons the page at once. Raises AIError when the page
        cannot be read.
        """
        raise NotImplementedError

    def _ask(self, path: str, body: dict, parse: Callable[[dict], AIPage], checkpoint: Callable[[], None]) -> AIPage:
        """Send one request and parse its answer, trying again while the service is busy, fails or answers wrong."""
        data = json.dumps(body).encode("utf-8")
        failure: AIError | None = None
        backoff = delay = 1.0
        for attempt in range(self.attempts):
            if attempt:
                self._pause(min(MAX_WAIT, delay), checkpoint)
                backoff *= 2
            delay = backoff
            checkpoint()
            request = urllib.request.Request(
                self.url + path,
                data=data,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "urna-padrones",
                },
            )
            try:
                payload = self._exchange(request, checkpoint)
            except urllib.error.HTTPError as error:
                status, detail = error.code, self._redact(_detail(error))
                if status in (401, 403):
                    raise AIError(t("ai.key_refused", service=self.shown, status=status)) from None
                if status == 402 or (status == 429 and "quota" in detail.lower()):
                    raise AIError(self._quota()) from None
                if status == 429 or status >= 500:
                    failure = AIError(self._quota() if status == 429 else self._broken(status))
                    delay = _retry_after(error, backoff)
                    continue
                if 300 <= status < 400:
                    raise AIError(t("ai.redirect", host=self.host, status=status)) from None
                raise _Refused(status, detail) from None
            except (TimeoutError, socket.timeout):
                failure = AIError(self._silent())
                continue
            except _TooLong:
                failure = AIError(self._malformed(t("answer.too_long", megabytes=MAX_ANSWER // 1_000_000)))
                continue
            except urllib.error.URLError as error:
                if isinstance(error.reason, ssl.SSLCertVerificationError):
                    raise AIError(t("ai.certificate", host=self.host)) from None
                timed_out = isinstance(error.reason, (TimeoutError, socket.timeout))
                failure = AIError(self._silent() if timed_out else self._unreachable())
                continue
            except (ConnectionError, http.client.HTTPException, OSError):
                failure = AIError(self._unreachable())
                continue
            except ValueError:
                # The request could not be put together, as with a header a server cannot take; what the error says
                # may hold the key, so it is not shown.
                raise AIError(t("ai.cannot_build", host=self.host)) from None
            try:
                answer = json.loads(payload)
                if not isinstance(answer, dict):
                    raise _Malformed(t("answer.not_object"))
                return parse(answer)
            # An answer of a shape nobody expected is never taken, whatever it breaks: it is not the JSON asked for.
            except (ValueError, TypeError, AttributeError, KeyError, IndexError, RecursionError, _Malformed) as error:
                detail = str(error) if isinstance(error, _Malformed) else ""
                failure = AIError(self._malformed(detail))
                continue
        assert failure is not None
        raise failure

    def _exchange(self, request: urllib.request.Request, checkpoint: Callable[[], None]) -> bytes:
        """Send a request and wait for its whole answer, for at most `timeout` seconds in all.

        The request is made on a thread of its own, which is waited for here, asking `checkpoint` ten times a
        second: a reading that is cancelled, or an answer that does not end in time, stops being waited for at
        once, also one that comes slowly, a little at a time. That thread then ends by itself, and what it gets
        is not used.
        """
        deadline = time.monotonic() + self.timeout
        outcome: dict = {}
        finished = threading.Event()

        def run() -> None:
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    outcome["payload"] = _read_answer(response, deadline)
            except Exception as error:
                outcome["error"] = error
            finally:
                finished.set()

        threading.Thread(target=run, name="urna-padrones-ia", daemon=True).start()
        while not finished.wait(POLL_SECONDS):
            checkpoint()
            if time.monotonic() > deadline:
                raise TimeoutError
        if "error" in outcome:
            raise outcome["error"]
        return outcome["payload"]

    def _pause(self, seconds: float, checkpoint: Callable[[], None]) -> None:
        if self.wait is not None:
            self.wait(seconds)
            return
        end = time.monotonic() + seconds
        while (left := end - time.monotonic()) > 0:
            checkpoint()
            time.sleep(min(POLL_SECONDS, left))

    def _redact(self, text: str) -> str:
        """What a service said, without the key, should it repeat it."""
        return re.sub(r"(?i)\b(bearer)\s+\S+", r"\1 …", text.replace(self.key, "…"))

    def _refused(self, refused: _Refused) -> AIError:
        detail = f": {refused.detail}" if refused.detail else ""
        hint = t("ai.refused.hint") if refused.status in (404, 405) else ""
        return AIError(t("ai.refused", service=self.shown, status=refused.status, detail=detail, hint=hint))

    def _quota(self) -> str:
        return t("ai.quota", service=self.shown)

    def _broken(self, status: int) -> str:
        return t("ai.broken", service=self.shown, status=status, attempts=self.attempts)

    def _silent(self) -> str:
        return t("ai.silent", host=self.host, seconds=self.timeout, attempts=self.attempts)

    def _unreachable(self) -> str:
        return t("ai.unreachable", host=self.host)

    def _malformed(self, detail: str) -> str:
        why = f" ({detail})" if detail else ""
        return t("ai.malformed", service=self.shown, why=why, attempts=self.attempts)


class MistralOCR(Service):
    """Mistral OCR: one request per page to /v1/ocr, which answers the page as Markdown."""

    company = "Mistral AI"

    def __init__(self, key: str, url: str | None = None, model: str | None = None, **options):
        url = (url or MISTRAL_URL).rstrip("/")
        super().__init__(key, url.removesuffix("/v1/ocr").removesuffix("/v1"), model or MISTRAL_MODEL, **options)

    def read_page(self, image: np.ndarray, page: int, checkpoint: Callable[[], None] | None = None) -> AIPage:
        body = {
            "model": self.model,
            "document": {"type": "image_url", "image_url": data_url(image)},
            "include_image_base64": False,
        }
        try:
            return self._ask("/v1/ocr", body, _mistral_page, checkpoint or (lambda: None))
        except _Refused as refused:
            raise self._refused(refused) from None


class OpenAICompatible(Service):
    """Any service with OpenAI's chat completions that takes images: asked for strict JSON, one object per person."""

    # Asked for when the service takes them; a service that refuses one by name is asked again without it.
    OPTIONAL = {"response_format": {"type": "json_object"}, "temperature": 0}

    def __init__(self, key: str, url: str | None = None, model: str | None = None, **options):
        if not url:
            raise AIError(t("ai.no_url"))
        super().__init__(key, url.rstrip("/").removesuffix("/chat/completions"), model or "", **options)
        self._refused_options: set[str] = set()

    def read_page(self, image: np.ndarray, page: int, checkpoint: Callable[[], None] | None = None) -> AIPage:
        content = [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": data_url(image)}},
        ]
        while True:
            body = {"model": self.model, "messages": [{"role": "user", "content": content}]}
            body.update({key: value for key, value in self.OPTIONAL.items() if key not in self._refused_options})
            try:
                return self._ask("/chat/completions", body, _chat_page, checkpoint or (lambda: None))
            except _Refused as refused:
                named = [key for key in self.OPTIONAL if key not in self._refused_options and key in refused.detail]
                if refused.status != 400 or not named:
                    raise self._refused(refused) from None
                self._refused_options.update(named)


def service(kind: str, key: str, url: str | None = None, model: str | None = None, **options) -> Service:
    """The service of `kind`, one of KINDS, with the user's key. Nothing is sent until a page is read."""
    if kind == MISTRAL:
        return MistralOCR(key, url, model, **options)
    if kind == OPENAI_COMPATIBLE:
        return OpenAICompatible(key, url, model, **options)
    raise AIError(t("ai.unknown", kind=kind, kinds=t("ai.or").join(KINDS)))


def warning(chosen: Service) -> str:
    """What a person reads before anything is sent."""
    return t("ai.warning", service=chosen.shown)


def data_url(image: np.ndarray) -> str:
    """The page as a JPEG in a data URL: made again from its pixels, so nothing else in the file goes with it."""
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        raise AIError(t("ai.image"))
    return "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")


def _visible_ascii(text: str) -> bool:
    return all("!" <= character <= "~" for character in text)


def _read_answer(response, deadline: float) -> bytes:
    """The whole body of an answer, as it comes, until `deadline` (of time.monotonic) or MAX_ANSWER bytes."""
    parts, size = [], 0
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError
        part = response.read1(65536)
        if not part:
            return b"".join(parts)
        size += len(part)
        if size > MAX_ANSWER:
            raise _TooLong
        parts.append(part)


def plain(text: str) -> tuple[str, bool]:
    """A value without the characters a printed roll has not got, and whether it had none.

    A control character, such as one that moves the cursor of a terminal, becomes a space; any other that does
    not show, such as one that turns the text around, is dropped. Spaces are made one.
    """
    kept = []
    clean = True
    for character in text:
        category = unicodedata.category(character)
        if category.startswith("C"):
            clean = clean and character in "\t\n\r"
            if category == "Cc":
                kept.append(" ")
            continue
        kept.append(character)
    return " ".join("".join(kept).split()), clean


def _detail(error: urllib.error.HTTPError) -> str:
    """What the service said about a request it did not take, on one short line, or ""."""
    try:
        text = error.read(4000).decode("utf-8", "replace")
    except Exception:
        return ""
    try:
        answer = json.loads(text)
    except ValueError:
        return ""
    message = answer
    for key in ("error", "message", "detail"):
        if isinstance(message, dict) and key in message:
            message = message[key]
    if isinstance(message, dict):
        message = message.get("message") or message.get("msg") or ""
    if isinstance(message, list):
        message = "; ".join(str(item.get("msg", item)) if isinstance(item, dict) else str(item) for item in message)
    return plain(str(message))[0][:200]


def _retry_after(error: urllib.error.HTTPError, otherwise: float) -> float:
    """How long the service asks to wait before trying again, in seconds, or `otherwise` when it does not say."""
    try:
        return max(0.0, float(error.headers.get("Retry-After", "")))
    except (TypeError, ValueError):
        return otherwise


def _mistral_page(answer: dict) -> AIPage:
    pages = answer.get("pages")
    if not isinstance(pages, list) or not pages:
        raise _Malformed(t("answer.no_pages"))
    tables = []
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("markdown"), str):
            raise _Malformed(t("answer.page_without_text"))
        markdown = page["markdown"]
        apart = page.get("tables") or []
        if not isinstance(apart, list):
            raise _Malformed(t("answer.tables_not_list"))
        # A table the service gives apart is in the text as a link to it, such as [tbl-0.md](tbl-0.md).
        for table in apart:
            if isinstance(table, dict) and isinstance(table.get("id"), str) and isinstance(table.get("content"), str):
                markdown = markdown.replace(f"[{table['id']}]({table['id']})", "\n" + table["content"] + "\n")
        tables += markdown_tables(markdown)
    if sum(len(table.rows) for table in tables) > MAX_ROWS:
        raise _Malformed(t("answer.too_many_lines", count=MAX_ROWS))
    return AIPage(tables)


def markdown_tables(markdown: str) -> list[AITable]:
    """The tables of a page in Markdown, each with the «Mesa» title of the last line above it that has one."""
    tables: list[AITable] = []
    title = None
    current: AITable | None = None
    for line in markdown.splitlines():
        text = line.strip()
        if text.startswith("|"):
            cells = _cells(text)
            if all(re.fullmatch(r":?-+:?", cell.replace(" ", "")) for cell in cells if cell) and any(cells):
                continue
            if current is None:
                current = AITable([], title=title)
                tables.append(current)
            current.rows.append(cells)
            continue
        current = None
        found = mesa_in(text) if text else None
        if found:
            title = found
    return tables


def _cells(line: str) -> list[str]:
    """The cells of a Markdown table row, without its outer bars, its marks of emphasis or its line breaks."""
    inner = line.strip()
    inner = inner[1:] if inner.startswith("|") else inner
    inner = inner[:-1] if inner.endswith("|") and not inner.endswith("\\|") else inner
    cells = re.split(r"(?<!\\)\|", inner)
    cleaned = []
    for cell in cells:
        cell = re.sub(r"<br\s*/?>", " ", cell.replace("\\|", "|"), flags=re.IGNORECASE)
        cell = re.sub(r"(\*\*|__)(.+?)\1", r"\2", cell)
        cleaned.append(" ".join(cell.split()))
    return cleaned


def _chat_page(answer: dict) -> AIPage:
    choices = answer.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise _Malformed(t("answer.no_answer"))
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        texts = [part.get("text") for part in content if isinstance(part, dict)]
        content = "".join(text for text in texts if isinstance(text, str))
    if not isinstance(content, str) or not content.strip():
        raise _Malformed(t("answer.empty"))
    if choices[0].get("finish_reason") == "length":
        raise _Malformed(t("answer.cut"))
    text = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        parsed = json.loads(text)
    except ValueError:
        raise _Malformed(t("answer.not_json")) from None
    return AIPage([answer_table(parsed)])


def answer_table(parsed) -> AITable:
    """The people a chat service listed, checked: {"columns": [...], "rows": [...]}, each row an object with text,
    numbers or null.

    A value is checked on every row when the page has it: when "columns" names it, or when any row has it. Null
    is both a value the page has not got and one that cannot be read, so a column read as null on every row is
    still checked when "columns" names it, and its blank cells are reviewed.
    """
    rows = parsed.get("rows") if isinstance(parsed, dict) else None
    if not isinstance(rows, list):
        raise _Malformed(t("answer.no_rows"))
    # A page that lists nobody has no columns to check.
    named = parsed.get("columns", None if rows else [])
    if not isinstance(named, list) or not all(isinstance(name, str) for name in named):
        raise _Malformed(t("answer.no_columns"))
    if len(rows) > MAX_ROWS:
        raise _Malformed(t("answer.too_many_people", count=MAX_ROWS))
    people = []
    for row in rows:
        if not isinstance(row, dict):
            raise _Malformed(t("answer.person_not_object"))
        person = {}
        for asked, key in ANSWER_KEYS.items():
            value = row.get(asked)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                raise _Malformed(t("answer.not_text", field=asked))
            person[key] = str(value).strip()
        people.append(person)
    # Every roll has names: a person without one is reviewed. Any other value is checked only where the page has it.
    listed = {ANSWER_KEYS[name] for name in named if name in ANSWER_KEYS}
    keys = tuple(
        key
        for key in ANSWER_KEYS.values()
        if key == "name" or key in listed or any(person.get(key) for person in people)
    )
    return AITable([[person.get(key, "") for key in keys] for person in people], keys=keys)


def rows_from(pages: list[AIPage | None]) -> list[list[Row]]:
    """The people of every page, in order: a table found by its header, or by the header of another page.

    A table whose first row names its columns is read by those names, as a scan is: the faculty's layout
    when every column is where the faculty has it, and by its header otherwise. A table without a header of
    its own, as on the pages after the first, takes the first header of a table with as many columns; with
    none, a table of six or seven columns is read as the faculty's, as a scan without a header is.
    """
    headers: dict[int, Header] = {}
    for page in pages:
        for table in page.tables if page else []:
            header = recognise(table.rows[0]) if table.keys is None and table.rows else None
            if header is not None:
                headers.setdefault(len(table.rows[0]), header)
    result = []
    for index, page in enumerate(pages):
        rows: list[Row] = []
        for table in page.tables if page else []:
            rows += _table_rows(table, index, headers, len(rows))
        result.append(rows)
    return result


def _table_rows(table: AITable, page: int, headers: dict[int, Header], start: int) -> list[Row]:
    body = table.rows
    if table.keys is not None:
        header = Header(table.keys)
    else:
        if not body:
            return []
        header = recognise(body[0])
        if header is not None:
            body = body[1:]
        else:
            header = headers.get(len(body[0]))
            if header is None and len(body[0]) in (len(COLUMNS), len(COLUMNS) + 1):
                header = Header(COLUMNS + (None,) * (len(body[0]) - len(COLUMNS)))
            if header is None:
                return []
    faculty = table.keys is None and len(header.keys) >= len(COLUMNS) and fits_faculty(header)
    layout = FACULTY if faculty else BY_HEADER
    columns = COLUMNS if faculty else header.fields()
    title = table.title
    rows = []
    for cells in body:
        filled = [cell for cell in cells if cell]
        # A line with only «Mesa 13» among the rows starts another table.
        if len(filled) == 1 and mesa_in(filled[0]) and table.keys is None:
            title = mesa_in(filled[0])
            continue
        # A value with characters a printed roll has not got, or too long to be a cell of one, puts the row up for
        # review; one too long is also dropped, for the person to type it.
        raw, odd = {}, False
        for key, cell in zip(header.keys, cells):
            value, clean = plain(cell)
            if key and value:
                odd = odd or not clean or len(value) > MAX_VALUE
                if len(value) <= MAX_VALUE:
                    raw[key] = value
        row = Row(page=page, position=start + len(rows), raw=raw, layout=layout, columns=columns, source=SOURCE)
        row.unsure = odd
        if not faculty:
            join_name(row)
        # The service gives no confidence: a row is as sure as its values' formats say, never more.
        row.confidence = {}
        if (is_header(row) if faculty else not is_person(row)):
            continue
        row.title_table = title
        rows.append(row)
    return rows
