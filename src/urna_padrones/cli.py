"""Command line of the scanner. It prints counts only, never data from the roll."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import quality
from .padron import write_padron
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


def extract(args: argparse.Namespace) -> int:
    if inside_git_repo(args.out) and not args.allow_inside_repo:
        print("La salida tiene datos personales y queda dentro de un repo de git: elegí otra carpeta.", file=sys.stderr)
        return 2
    started = time.monotonic()
    shown = {"open": False}

    def progress(done: int, total: int) -> None:
        show_progress(done, total)
        shown["open"] = done != total

    try:
        reading = read_roll(args.pdf, pages=args.pages, workers=args.workers,
                            on_page=progress if sys.stderr.isatty() else None)
    except RollError as error:
        # The progress line has no newline yet: the message goes on a line of its own.
        print("\n" if shown["open"] else "", error, sep="", file=sys.stderr)
        return 1
    descriptor = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        for record in reading.records():
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = (f"{len(reading.rows)} filas de {reading.pages_read} páginas en {time.monotonic() - started:.0f} s; "
               f"páginas sin tabla: {len(reading.pages_without_table)}; "
               f"números de orden inferidos: {reading.inferred_orders}")
    if reading.pages_with_text:
        summary += f"; páginas con texto: {len(reading.pages_with_text)}"
    if reading.tables():
        summary += f"; mesas: {len(reading.tables())}"
    print(summary)
    return 0


def to_padron(args: argparse.Namespace) -> int:
    if inside_git_repo(args.out) and not args.allow_inside_repo:
        print("El padrón tiene datos personales y queda dentro de un repo de git: elegí otra carpeta.", file=sys.stderr)
        return 2
    summary = write_padron(quality.load_records(args.records), args.out, args.title)
    tables = f"; {summary['tables']} mesas" if summary.get("tables") else ""
    print(f"{summary['people']} personas; {summary['to_review']} para revisar{tables}")
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
