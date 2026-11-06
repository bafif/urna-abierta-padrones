"""The reader's server: only this computer can reach it, and only through the address it prints.

The address carries a random token, the Host header has to be exactly 127.0.0.1 and the port,
so that no web page can point a name of its own at it, and the screens get a strict content
security policy. Nothing is logged: a file name or a title could name a person.
"""

import atexit
import json
import os
import re
import secrets
import shutil
import signal
import socketserver
import stat
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ..errors import RollError
from .session import MAX_PDF, IncompleteUpload, NoRows, Session

IDLE_SECONDS = 30 * 60
# The private folder of each run: its name starts with this, and it holds the pid of its reader.
FOLDER_PREFIX = "urna-lector-"
PID_FILE = "pid"
MAX_JSON = 64 * 1024
CSP = "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:"
TYPES = {
    "html": "text/html; charset=utf-8",
    "js": "text/javascript; charset=utf-8",
    "css": "text/css; charset=utf-8",
    "woff2": "font/woff2",
}
ROW_IMAGE = re.compile(r"rows/(\d{1,7})/image")
ROW_EDIT = re.compile(r"rows/(\d{1,7})")
ROW_OK = re.compile(r"rows/(\d{1,7})/ok")


def load_assets() -> dict[str, bytes]:
    """The screens, read once from the package: only these names are ever served."""
    assets: dict[str, bytes] = {}

    def walk(folder: Traversable, prefix: str) -> None:
        for item in folder.iterdir():
            if item.is_dir():
                walk(item, f"{prefix}{item.name}/")
            elif item.name.rsplit(".", 1)[-1] in TYPES:
                assets[prefix + item.name] = item.read_bytes()

    walk(resources.files(__package__) / "ui", "")
    return assets


def open_browser(url: str) -> None:
    """The browser of this computer, without waiting for it and without a word if there is none."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(url)  # type: ignore[attr-defined]
            return
        command = ["open", url] if sys.platform == "darwin" else ["xdg-open", url]
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        pass


def _alive(pid: int) -> bool:
    """Whether a process with this pid is running. When in doubt, it is."""
    if pid == os.getpid():
        return True
    if sys.platform.startswith("win"):
        # os.kill(pid, 0) would end the process on Windows.
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() != 87  # ERROR_INVALID_PARAMETER: no such process
        try:
            code = ctypes.c_ulong()
            return not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def remove_leftovers(temp: Path | None = None) -> int:
    """Delete the private folders that earlier runs left behind, for example when they were killed.

    Only folders of this user that the reader made: their name starts with FOLDER_PREFIX and they
    hold the pid of a reader that is no longer running. Returns how many it deleted.
    """
    temp = Path(temp or tempfile.gettempdir())
    removed = 0
    try:
        candidates = [item for item in temp.iterdir() if item.name.startswith(FOLDER_PREFIX)]
    except OSError:
        return 0
    for folder in candidates:
        try:
            info = folder.lstat()
            if not stat.S_ISDIR(info.st_mode) or (hasattr(os, "getuid") and info.st_uid != os.getuid()):
                continue
            text = (folder / PID_FILE).read_text(encoding="ascii").strip()
            if not text.isdigit() or not text.isascii() or _alive(int(text)):
                continue
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        shutil.rmtree(folder, ignore_errors=True)
        removed += not folder.exists()
    return removed


def private_folder() -> Path:
    """A folder only this user can open, holding the pid of this run."""
    folder = Path(tempfile.mkdtemp(prefix=FOLDER_PREFIX))
    (folder / PID_FILE).write_text(str(os.getpid()), encoding="ascii")
    return folder


class LectorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, session: Session, port: int = 0, idle_seconds: float = IDLE_SECONDS):
        self.session = session
        self.token = secrets.token_urlsafe(18)
        self.idle_seconds = idle_seconds
        self.last_request = time.monotonic()
        self.stop = threading.Event()
        self.assets = load_assets()
        super().__init__(("127.0.0.1", port), Handler)

    def server_bind(self) -> None:
        # HTTPServer would look up the computer's name, which can take seconds on some networks.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "127.0.0.1", self.server_address[1]

    @property
    def port(self) -> int:
        return self.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/{self.token}/"

    def touch(self) -> None:
        self.last_request = time.monotonic()

    def idle(self) -> bool:
        """Nobody asked anything for a long while and nothing is being read."""
        return time.monotonic() - self.last_request > self.idle_seconds and not self.session.busy()


class Handler(BaseHTTPRequestHandler):
    server: LectorServer
    server_version = "urna-lector"
    sys_version = ""

    def log_message(self, format: str, *args) -> None:
        """Never log: a path may carry a file name or a title."""

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    # ----- Answers -----

    def _send(self, status: int, body: bytes, content_type: str, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, body: object) -> None:
        self._send(status, json.dumps(body, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _length(self) -> int | None:
        text = self.headers.get("Content-Length", "")
        return int(text) if text.isdigit() else None

    def _drain(self) -> None:
        """Read a small body left unread, so that the answer is not lost to a reset connection."""
        length = self._length()
        if length and length <= MAX_JSON:
            self.rfile.read(length)

    def _body(self) -> dict:
        length = self._length() or 0
        if length > MAX_JSON:
            raise ValueError("too large")
        data = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(data, dict):
            raise TypeError("not an object")
        return data

    # ----- Routing -----

    def _handle(self, method: str) -> None:
        try:
            port = self.server.port
            # Another site cannot point its own name at this port and talk to it.
            if self.headers.get("Host") != f"127.0.0.1:{port}":
                self._drain()
                return self._json(403, {"error": "forbidden"})
            origin = self.headers.get("Origin")
            if origin is not None and origin != f"http://127.0.0.1:{port}":
                self._drain()
                return self._json(403, {"error": "forbidden"})
            parts = urlsplit(self.path)
            segments = parts.path.split("/")
            given = segments[1] if len(segments) > 1 else ""
            if not secrets.compare_digest(given.encode(), self.server.token.encode()):
                self._drain()
                return self._json(404, {"error": "not_found"})
            # Only the screens keep the reader awake, not whoever knocks without the token.
            self.server.touch()
            if len(segments) == 2:
                # Without the final slash, the screens would ask for their files at the wrong place.
                self._drain()
                query = f"?{parts.query}" if parts.query else ""
                return self._send(308, b"", "text/plain; charset=utf-8", {"Location": f"/{given}/{query}"})
            rest = "/".join(segments[2:])
            if rest.startswith("api/"):
                return self._api(method, rest[4:], parse_qs(parts.query))
            if method != "GET":
                self._drain()
                return self._json(405, {"error": "get_only"})
            name = rest or "index.html"
            content = self.server.assets.get(name)
            if content is None:
                return self._json(404, {"error": "not_found"})
            self._send(200, content, TYPES[name.rsplit(".", 1)[-1]], {"Content-Security-Policy": CSP})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:  # noqa: BLE001 - the browser gets an answer, and nothing is logged
            try:
                self._json(500, {"error": "internal"})
            except OSError:
                pass

    def _api(self, method: str, path: str, query: dict[str, list[str]]) -> None:
        session = self.server.session
        try:
            if method == "GET":
                return self._get(path, query)
            if path == "pdf":
                return self._upload(query)
            try:
                body = self._body()
            except (ValueError, TypeError):
                return self._json(400, {"error": "bad_request"})
            if path == "read":
                return self._json(202, {"ok": True}) if session.start() else self._json(409, {"error": "nothing_to_read"})
            if path == "cancel":
                session.stop()
                return self._json(200, {"ok": True})
            if path == "reset":
                session.forget()
                return self._json(200, {"ok": True})
            if path == "quit":
                self._json(200, {"ok": True})
                self.server.stop.set()
                return None
            if match := ROW_OK.fullmatch(path):
                return self._json(200, session.confirm(int(match[1])))
            if match := ROW_EDIT.fullmatch(path):
                values = body.get("values")
                if not isinstance(values, dict):
                    return self._json(400, {"error": "bad_request"})
                return self._json(200, session.edit(int(match[1]), values, confirm=body.get("ok") is True))
            return self._json(404, {"error": "not_found"})
        except NoRows:
            return self._json(409, {"error": "no_rows"})
        except KeyError:
            return self._json(404, {"error": "not_found"})

    def _get(self, path: str, query: dict[str, list[str]]) -> None:
        session = self.server.session
        if path == "state":
            return self._json(200, session.status())
        if path == "rows":
            which = query.get("which", ["all"])[0]
            return self._json(200, {"rows": session.rows(which)})
        if match := ROW_IMAGE.fullmatch(path):
            try:
                png = session.image(int(match[1]))
            except (OSError, ValueError, RollError):
                png = None
            if png is None:
                return self._json(404, {"error": "no_image"})
            return self._send(200, png, "image/png")
        if path == "save":
            data, name = session.padron(query.get("title", [""])[0])
            return self._send(200, data, "application/octet-stream", {"Content-Disposition": f'attachment; filename="{name}"'})
        if path in ("pdf", "read", "cancel", "reset", "quit"):
            return self._json(405, {"error": "post_only"})
        return self._json(404, {"error": "not_found"})

    def _upload(self, query: dict[str, list[str]]) -> None:
        length = self._length()
        if length is None:
            self.close_connection = True
            return self._json(411, {"error": "length_required"})
        if length > MAX_PDF:
            self.close_connection = True
            return self._json(413, {"error": "too_large"})
        name = query.get("name", ["padron.pdf"])[0][:200]
        try:
            return self._json(200, self.server.session.store(self.rfile, length, name))
        except RollError as error:
            return self._json(400, {"error": error.code})
        except IncompleteUpload:
            self.close_connection = True
            return self._json(400, {"error": "incomplete"})


def serve(port: int = 0, open_in_browser: bool = True, idle_seconds: float = IDLE_SECONDS) -> int:
    """Run the reader until the person closes it, it is stopped, or nobody uses it for a while."""
    remove_leftovers()
    folder = private_folder()
    atexit.register(shutil.rmtree, folder, True)
    session = Session(folder)
    try:
        server = LectorServer(session, port=port, idle_seconds=idle_seconds)
    except OSError:
        print(f"No pude usar el puerto {port} de esta computadora: probá con otro o sin --port.", file=sys.stderr)
        shutil.rmtree(folder, ignore_errors=True)
        return 1

    def stop(signum, frame) -> None:
        server.stop.set()

    # Ctrl+C arrives as KeyboardInterrupt; these end it the same way. Only the main thread may set them.
    if threading.current_thread() is threading.main_thread():
        for name in ("SIGTERM", "SIGBREAK", "SIGHUP"):
            if hasattr(signal, name):
                signal.signal(getattr(signal, name), stop)
    threading.Thread(target=server.serve_forever, name="servidor", daemon=True).start()
    print(server.url, flush=True)
    print("Urna Abierta, lector de padrones: si el navegador no se abrió solo, abrí esa dirección.", flush=True)
    print("Dejá esta ventana abierta mientras lo usás. Para terminar, cerrala o usá «Cerrar el lector».", flush=True)
    print("Urna Abierta, roll reader: if your browser did not open, open that address.", flush=True)
    print("Keep this window open while you use it. To finish, close it or use “Close the reader”.", flush=True)
    if open_in_browser:
        open_browser(server.url)
    try:
        while not server.stop.wait(1.0):
            if server.idle():
                break
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        session.forget()
        shutil.rmtree(folder, ignore_errors=True)
    return 0
