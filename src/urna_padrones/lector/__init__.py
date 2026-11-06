"""The desktop reader: a small server only this computer can reach, with its screens in the browser.

    python -m urna_padrones.lector [--port N] [--no-browser] [--self-test]

Heavy imports wait until main() has called freeze_support(), as a packaged program needs.
"""

import argparse
import multiprocessing
import os
import sys

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
        raise argparse.ArgumentTypeError("tiene que estar entre 0 y 65535")
    return value


def parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="urna-padrones-lector",
        description="Lector de padrones escaneados, con sus pantallas en el navegador. Nada sale de esta computadora.",
    )
    parser.add_argument("--port", type=_port, help=f"puerto en 127.0.0.1 (o {PORT_VARIABLE}; si no, uno libre al azar)")
    parser.add_argument("--no-browser", action="store_true", help=f"no abrir el navegador (o {NO_BROWSER_VARIABLE}=1)")
    parser.add_argument("--self-test", action="store_true", help="comprobar que el lector funciona, sin red, y salir")
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
