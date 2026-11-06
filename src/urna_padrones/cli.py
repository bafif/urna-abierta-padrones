"""Command line of the scanner. It prints counts only, never data from the roll."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import external_ai, quality
from .external_ai import AIError
from .padron import extraction_of, write_padron
from .reading import RollError, read_roll
from .reference import SpreadsheetError, read_reference


def inside_git_repo(path: Path) -> bool:
    return any((parent / ".git").exists() for parent in path.resolve().parents)


def positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("tiene que ser 1 o más")
    return value


def show_progress(done: int, total: int) -> None:
    print(f"\rpágina {done} de {total}", end="\n" if done == total else "", file=sys.stderr, flush=True)


def chosen_service(args: argparse.Namespace) -> external_ai.Service | int | None:
    """The outside service the person chose, after warning them; an exit code when it cannot go on; None without one.

    Nothing is sent without both --ia and --acepto-enviar. The key comes only from the environment, never from an
    argument, so that it does not stay in the shell's history.
    """
    if args.ia is None:
        if args.ia_url or args.ia_model or args.accept_sending:
            print("--ia-url, --ia-modelo y --acepto-enviar van con --ia.", file=sys.stderr)
            return 2
        return None
    try:
        service = external_ai.service(args.ia, os.environ.get(external_ai.KEY_VARIABLE, ""), args.ia_url, args.ia_model)
    except AIError as error:
        print(error, file=sys.stderr)
        return 2
    print(external_ai.warning(service), file=sys.stderr)
    if not args.accept_sending:
        print("Para seguir, agregá --acepto-enviar. No se mandó nada.", file=sys.stderr)
        return 2
    return service


def extract(args: argparse.Namespace) -> int:
    if inside_git_repo(args.out) and not args.allow_inside_repo:
        print("La salida tiene datos personales y queda dentro de un repo de git: elegí otra carpeta.", file=sys.stderr)
        return 2
    service = chosen_service(args)
    if isinstance(service, int):
        return service
    started = time.monotonic()
    shown = {"open": False}

    def progress(done: int, total: int) -> None:
        show_progress(done, total)
        shown["open"] = done != total

    try:
        reading = read_roll(args.pdf, pages=args.pages, workers=args.workers,
                            on_page=progress if sys.stderr.isatty() else None, service=service)
    except (RollError, AIError) as error:
        # The progress line has no newline yet: the message goes on a line of its own.
        print("\n" if shown["open"] else "", error, sep="", file=sys.stderr)
        return 1
    descriptor = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    # The same bytes on every system: a JSONL line ends in \n, also on Windows.
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        for record in reading.records():
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = (f"{len(reading.rows)} filas de {reading.pages_read} páginas en {time.monotonic() - started:.0f} s; "
               f"páginas sin tabla: {len(reading.pages_without_table)}; "
               f"números de orden inferidos: {reading.inferred_orders}")
    if reading.pages_with_text:
        summary += f"; páginas con texto: {len(reading.pages_with_text)}"
    if reading.tables():
        summary += f"; mesas: {len(reading.tables())}"
    if service is not None:
        summary += f"; páginas mandadas a {service.shown}: {len(reading.pages_sent)}"
    print(summary)
    return 0


def to_padron(args: argparse.Namespace) -> int:
    if inside_git_repo(args.out) and not args.allow_inside_repo:
        print("El padrón tiene datos personales y queda dentro de un repo de git: elegí otra carpeta.", file=sys.stderr)
        return 2
    records = quality.load_records(args.records)
    summary = write_padron(records, args.out, args.title)
    tables = f"; {summary['tables']} mesas" if summary.get("tables") else ""
    extraction = extraction_of(records)
    seen = f"; lo vio una IA externa: {extraction.get('provider', 'sí')}" if extraction["external_ai"] else ""
    print(f"{summary['people']} personas; {summary['to_review']} para revisar{tables}{seen}")
    return 0


def show_report(args: argparse.Namespace) -> int:
    print(json.dumps(quality.report(quality.load_records(args.records)), ensure_ascii=False, indent=1))
    return 0


def show_crosscheck(args: argparse.Namespace) -> int:
    result = quality.crosscheck(quality.load_records(args.first), quality.load_records(args.second))
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


def show_verify(args: argparse.Namespace) -> int:
    try:
        reference = read_reference(args.spreadsheet)
    except (SpreadsheetError, OSError, ValueError) as error:
        print(f"No se pudo leer la planilla: {error}", file=sys.stderr)
        return 1
    result, rows = quality.verify(quality.load_records(args.records), reference)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if args.rows:
        # Only row numbers of the person's own spreadsheet and what to check there, never a value.
        for row, what in rows.items():
            print(f"fila {row}: {'; '.join(what)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="urna-padrones", description=__doc__)
    commands = parser.add_subparsers(required=True)
    command = commands.add_parser("extract", help="extrae las filas de un padrón en PDF o en fotos")
    command.add_argument("pdf", type=Path, metavar="archivo", help="PDF escaneado o con texto, o imagen JPG, PNG o TIFF")
    command.add_argument("--out", type=Path, required=True)
    command.add_argument("--pages", type=positive)
    command.add_argument("--workers", type=positive, default=2)
    command.add_argument("--allow-inside-repo", action="store_true")
    command.add_argument("--ia", choices=external_ai.KINDS,
                         help="lee las páginas con un servicio de IA externo, con tu clave en "
                              f"{external_ai.KEY_VARIABLE} (sin esto, todo se lee en tu computadora)")
    command.add_argument("--ia-url", help="dirección del servicio, como https://api.ejemplo.com/v1 (para mistral, "
                                          f"si no se dice, {external_ai.MISTRAL_URL})")
    command.add_argument("--ia-modelo", dest="ia_model",
                         help=f"modelo del servicio (para mistral, si no se dice, {external_ai.MISTRAL_MODEL})")
    command.add_argument("--acepto-enviar", dest="accept_sending", action="store_true",
                         help="confirma que el padrón se manda a ese servicio, después de leer el aviso")
    command.set_defaults(run=extract)
    command = commands.add_parser("padron", help="arma el archivo .padron que se sube a Urna Abierta")
    command.add_argument("records", type=Path)
    command.add_argument("--out", type=Path, required=True)
    command.add_argument("--title")
    command.add_argument("--allow-inside-repo", action="store_true")
    command.set_defaults(run=to_padron)
    command = commands.add_parser("report", help="muestra la calidad de una extracción")
    command.add_argument("records", type=Path)
    command.set_defaults(run=show_report)
    command = commands.add_parser("crosscheck", help="compara dos extracciones que se solapan")
    command.add_argument("first", type=Path)
    command.add_argument("second", type=Path)
    command.set_defaults(run=show_crosscheck)
    command = commands.add_parser("verify", help="compara una extracción con el padrón tipeado en una planilla")
    command.add_argument("records", type=Path)
    command.add_argument("spreadsheet", type=Path, help="planilla .xlsx o .csv con nombre, documento y legajo")
    command.add_argument("--filas", dest="rows", action="store_true",
                         help="además, lista las filas de la planilla para revisar (sin mostrar los datos)")
    command.set_defaults(run=show_verify)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
