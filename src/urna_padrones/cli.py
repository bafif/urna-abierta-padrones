"""Command line of the scanner. It prints counts only, never data from the roll."""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import quality
from .pdf import page_count
from .table import COLUMNS, build_vocabulary, extract_file_page, infer_orders, smooth_by_neighbours


def inside_git_repo(path: Path) -> bool:
    return any((parent / ".git").exists() for parent in path.resolve().parents)


def extract(args: argparse.Namespace) -> int:
    if inside_git_repo(args.out) and not args.allow_inside_repo:
        print("La salida tiene datos personales y queda dentro de un repo de git: elegí otra carpeta.", file=sys.stderr)
        return 2
    started = time.monotonic()
    pages = page_count(args.pdf)
    selected = range(pages) if args.pages is None else range(min(args.pages, pages))
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        per_page = list(pool.map(extract_file_page, [(args.pdf, i) for i in selected]))
    rows = [row for page in per_page for row in page]
    inferred = infer_orders(rows)
    raw_programs = [r.checked("program").value for r in rows]
    vocabulary = build_vocabulary([p or "" for p in raw_programs])
    programs = smooth_by_neighbours([vocabulary.get(p, p) for p in raw_programs])
    descriptor = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        for row, program in zip(rows, programs):
            checked = {c: row.checked(c) for c in COLUMNS}
            record = {c: checked[c].value for c in COLUMNS}
            record["program"] = program
            record.update(
                page=row.page,
                valid={c: checked[c].valid for c in COLUMNS},
                confidence=row.confidence,
                repaired_file_number=checked["file_number"].repaired,
                needs_review=row.needs_review(),
            )
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"{len(rows)} filas de {len(selected)} páginas en {time.monotonic() - started:.0f} s; "
          f"páginas sin tabla: {sum(not p for p in per_page)}; números de orden inferidos: {inferred}")
    return 0


def show_report(args: argparse.Namespace) -> int:
    print(json.dumps(quality.report(quality.load_records(args.records)), ensure_ascii=False, indent=1))
    return 0


def show_crosscheck(args: argparse.Namespace) -> int:
    result = quality.crosscheck(quality.load_records(args.first), quality.load_records(args.second))
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="urna-padrones", description=__doc__)
    commands = parser.add_subparsers(required=True)
    command = commands.add_parser("extract", help="extrae las filas de un PDF escaneado")
    command.add_argument("pdf", type=Path)
    command.add_argument("--out", type=Path, required=True)
    command.add_argument("--pages", type=int)
    command.add_argument("--workers", type=int, default=2)
    command.add_argument("--allow-inside-repo", action="store_true")
    command.set_defaults(run=extract)
    command = commands.add_parser("report", help="muestra la calidad de una extracción")
    command.add_argument("records", type=Path)
    command.set_defaults(run=show_report)
    command = commands.add_parser("crosscheck", help="compara dos extracciones que se solapan")
    command.add_argument("first", type=Path)
    command.add_argument("second", type=Path)
    command.set_defaults(run=show_crosscheck)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
