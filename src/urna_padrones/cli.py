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
    print(f"{len(reading.rows)} filas de {reading.pages_read} páginas en {time.monotonic() - started:.0f} s; "
          f"páginas sin tabla: {len(reading.pages_without_table)}; "
          f"números de orden inferidos: {reading.inferred_orders}")
    return 0


def to_padron(args: argparse.Namespace) -> int:
    if inside_git_repo(args.out) and not args.allow_inside_repo:
        print("El padrón tiene datos personales y queda dentro de un repo de git: elegí otra carpeta.", file=sys.stderr)
        return 2
    summary = write_padron(quality.load_records(args.records), args.out, args.title)
    print(f"{summary['people']} personas; {summary['to_review']} para revisar")
    return 0


def show_report(args: argparse.Namespace) -> int:
    print(json.dumps(quality.report(quality.load_records(args.records)), ensure_ascii=False, indent=1))
    return 0


def show_crosscheck(args: argparse.Namespace) -> int:
    result = quality.crosscheck(quality.load_records(args.first), quality.load_records(args.second))
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="urna-padrones", description=__doc__)
    commands = parser.add_subparsers(required=True)
    command = commands.add_parser("extract", help="extrae las filas de un PDF escaneado")
    command.add_argument("pdf", type=Path)
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
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
