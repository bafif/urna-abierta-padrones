"""Entry point of the packaged roll reader (see lector.spec).

Before the reader starts it makes sure of these things a person who never opens a terminal needs:
- On macOS the program has no window, so what it prints goes to a log file in the user's folder.
- The reading engine loads with its telemetry off.
- If the reading engine cannot load (on Windows, usually an old Visual C++ runtime), it says so
  in plain words, with the link to fix it, instead of closing without a word.
- On Windows, closing the console window gives the reader time to delete its private copy of the PDF.
"""

import multiprocessing
import os
import sys
import traceback
from pathlib import Path

VC_RUNTIME_URL = "https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist"
WINDOWS = sys.platform.startswith("win")
MACOS = sys.platform == "darwin"


def log_folder() -> Path:
    if MACOS:
        return Path.home() / "Library" / "Logs" / "Urna Abierta"
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Urna Abierta"


def lost(stream) -> bool:
    """Output nobody can see: no stream at all, or, for a Mac app opened from the Finder, /dev/null."""
    if stream is None:
        return True
    if not MACOS:
        return False
    try:
        return os.path.samestat(os.fstat(stream.fileno()), os.stat(os.devnull))
    except (OSError, ValueError, AttributeError):
        return False


def keep_output_somewhere() -> None:
    """A program without a console writes to a log file instead, so that its address can be found.

    Libraries that write progress or colored logs also fail when sys.stderr is None.
    """
    if not lost(sys.stdout) and not lost(sys.stderr):
        return
    folder = log_folder()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        log = open(folder / "lector.log", "w", encoding="utf-8", buffering=1)  # noqa: SIM115 - open until exit
    except OSError:
        log = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if lost(sys.stdout):
        sys.stdout = log
    if lost(sys.stderr):
        sys.stderr = log


def tell(message: str) -> None:
    """Say something a person must read, and on Windows keep the window open until they do."""
    print(message, file=sys.stderr, flush=True)
    if MACOS and getattr(sys, "frozen", False):
        import subprocess

        script = f'display alert "Urna Abierta" message {json_string(message)} as critical'
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    elif WINDOWS and sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\nApretá Enter para cerrar esta ventana. / Press Enter to close this window.")
        except (EOFError, KeyboardInterrupt):
            pass


def json_string(text: str) -> str:
    """Text quoted for AppleScript, which uses the same escapes as JSON for quotes and backslashes."""
    import json

    return json.dumps(text, ensure_ascii=False)


def reading_engine_loads() -> bool:
    """Load onnxruntime first, before anything else brings an older copy of the C++ runtime."""
    # onnxruntime reports usage over the internet and leaves a .ses file in the temp folder
    # unless this is set before it is imported: urna_padrones.ocr sets it too, but too late here.
    os.environ["ORT_DISABLE_TELEMETRY"] = "1"
    try:
        import onnxruntime
    except (ImportError, OSError) as error:
        lines = [
            "El lector no puede arrancar: no se pudo cargar el motor de lectura.",
            "The reader cannot start: the reading engine could not be loaded.",
        ]
        if WINDOWS:
            lines += [
                "",
                "Casi siempre se arregla instalando la versión más nueva de Microsoft Visual C++ (x64) desde:",
                "It is almost always fixed by installing the latest Microsoft Visual C++ (x64) from:",
                f"  {VC_RUNTIME_URL}",
            ]
        lines += ["", f"({type(error).__name__}: {error})"]
        tell("\n".join(lines))
        return False
    # The Windows builds can also report usage events to the system: nothing leaves this computer.
    disable = getattr(onnxruntime, "disable_telemetry_events", None)
    if disable is not None:
        disable()
    return True


def wait_for_cleanup_on_close() -> None:
    """On Windows, closing the console ends the process as soon as the first handler returns.

    The reader deletes its private copy of the PDF when it stops. This handler asks it to stop
    the same way Ctrl+Break does, and waits a few seconds (Windows allows five) for it to finish.
    """
    import _thread
    import atexit
    import ctypes
    import signal
    import threading
    from ctypes import wintypes

    finished = threading.Event()
    atexit.register(finished.set)
    close_events = {2, 5, 6}  # CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
    def on_console_event(event: int) -> bool:
        if event not in close_events:
            return False
        try:
            _thread.interrupt_main(signal.SIGBREAK)
        except (ValueError, RuntimeError):
            return False
        finished.wait(4.5)
        return True

    # Kept alive for the whole run: Windows calls it from a thread of its own.
    wait_for_cleanup_on_close.handler = on_console_event  # type: ignore[attr-defined]
    ctypes.windll.kernel32.SetConsoleCtrlHandler(on_console_event, True)


def main() -> int:
    multiprocessing.freeze_support()
    keep_output_somewhere()
    if not reading_engine_loads():
        return 1
    from urna_padrones.lector import main as reader

    if WINDOWS:
        try:
            wait_for_cleanup_on_close()
        except (AttributeError, OSError):
            pass
    try:
        return reader()
    except KeyboardInterrupt:
        return 130
    except Exception:  # noqa: BLE001 - shown to the person instead of a window that vanishes
        tell(
            "El lector se cerró por un error inesperado. / The reader stopped because of an unexpected error.\n\n"
            + traceback.format_exc()
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
