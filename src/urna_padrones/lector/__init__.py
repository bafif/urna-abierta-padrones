"""The desktop reader: a small server only this computer can reach, with its screens in the browser.

    python -m urna_padrones.lector [--port N] [--no-browser] [--self-test]

Heavy imports wait until main() has called freeze_support(), as a packaged program needs.
"""

import argparse
import multiprocessing
import os
import sys

from ..i18n import add_language_option, forced_language, localize_argparse, set_language, t

PORT_VARIABLE = "URNA_LECTOR_PORT"
NO_BROWSER_VARIABLE = "URNA_NO_BROWSER"
BANNER = (
    "Urna Abierta: lector de padrones / roll reader\n"
    "El lector está abierto en el navegador, en la dirección de abajo. Si cerrás esta ventana, el lector se cierra.\n"
    "The reader is open in your browser, at the address below. Closing this window closes the reader."
)


def _port(text: str) -> int:
    value = int(text)
    if not 0 <= value <= 65535:
        raise argparse.ArgumentTypeError(t("lector.port_range"))
    return value


def parse(argv: list[str] | None) -> argparse.Namespace:
    argv = sys.argv[1:] if argv is None else argv
    if forced := forced_language(argv):
        set_language(forced)
    localize_argparse()
    parser = argparse.ArgumentParser(prog="urna-padrones-lector", description=t("lector.description"))
    parser.add_argument("--port", type=_port, help=t("lector.port", variable=PORT_VARIABLE))
    parser.add_argument("--no-browser", action="store_true", help=t("lector.no_browser", variable=NO_BROWSER_VARIABLE))
    parser.add_argument("--self-test", action="store_true", help=t("lector.self_test"))
    add_language_option(parser)
    args = parser.parse_args(argv)
    if args.port is None:
        args.port = _port(os.environ.get(PORT_VARIABLE) or "0")
    args.no_browser = args.no_browser or os.environ.get(NO_BROWSER_VARIABLE, "") not in ("", "0")
    return args


def main(argv: list[str] | None = None) -> int:
    multiprocessing.freeze_support()
    args = parse(argv)
    if args.self_test:
        from .selftest import run

        if run(lambda line: print(line, file=sys.stderr)):
            print("ok")
            return 0
        return 1
    from .server import serve

    # For a person looking at a console. It goes to stderr: the address stays the first line on stdout.
    if sys.stderr is not None and sys.stderr.isatty():
        print(BANNER, file=sys.stderr, flush=True)
    return serve(port=args.port, open_in_browser=not args.no_browser)
