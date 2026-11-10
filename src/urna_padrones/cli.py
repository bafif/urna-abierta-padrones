"""Command line of the scanner. It prints counts only, never data from the roll."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import external_ai, i18n, quality
from .external_ai import AIError
from .i18n import TEXTS, t
from .padron import extraction_of, write_padron
from .reading import RollError, read_roll
from .reference import SpreadsheetError, read_reference


def inside_git_repo(path: Path) -> bool:
    return any((parent / ".git").exists() for parent in path.resolve().parents)


def positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(t("cli.positive"))
    return value


def show_progress(done: int, total: int) -> None:
    line = t("cli.progress", done=done, total=total)
    print(f"\r{line}", end="\n" if done == total else "", file=sys.stderr, flush=True)


def chosen_service(args: argparse.Namespace) -> external_ai.Service | int | None:
    """The outside service the person chose, after warning them; an exit code when it cannot go on; None without one.

    Nothing is sent without both --ia and --acepto-enviar. The key comes only from the environment, never from an
    argument, so that it does not stay in the shell's history.
    """
    if args.ia is None:
        if args.ia_url or args.ia_model or args.accept_sending:
            print(t("cli.ai_alone"), file=sys.stderr)
            return 2
        return None
    try:
        service = external_ai.service(args.ia, os.environ.get(external_ai.KEY_VARIABLE, ""), args.ia_url, args.ia_model)
    except AIError as error:
        print(error, file=sys.stderr)
        return 2
    print(external_ai.warning(service), file=sys.stderr)
    if not args.accept_sending:
        print(t("cli.accept"), file=sys.stderr)
        return 2
    return service


def extract(args: argparse.Namespace) -> int:
    if inside_git_repo(args.out) and not args.allow_inside_repo:
        print(t("cli.records_in_repo"), file=sys.stderr)
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
    summary = t("cli.summary", rows=len(reading.rows), pages=reading.pages_read,
                seconds=f"{time.monotonic() - started:.0f}", without=len(reading.pages_without_table),
                inferred=reading.inferred_orders)
    if reading.pages_with_text:
        summary += t("cli.summary.text", count=len(reading.pages_with_text))
    if reading.tables():
        summary += t("cli.summary.tables", count=len(reading.tables()))
    if service is not None:
        summary += t("cli.summary.sent", service=service.shown, count=len(reading.pages_sent))
    print(summary)
    return 0


def to_padron(args: argparse.Namespace) -> int:
    if inside_git_repo(args.out) and not args.allow_inside_repo:
        print(t("cli.padron_in_repo"), file=sys.stderr)
        return 2
    records = quality.load_records(args.records)
    summary = write_padron(records, args.out, args.title)
    tables = t("cli.padron.tables", count=summary["tables"]) if summary.get("tables") else ""
    extraction = extraction_of(records)
    seen = ""
    if extraction["external_ai"]:
        seen = t("cli.padron.seen", provider=extraction.get("provider", t("cli.padron.seen.yes")))
    print(t("cli.padron", people=summary["people"], review=summary["to_review"]) + tables + seen)
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
        print(t("cli.spreadsheet", error=error), file=sys.stderr)
        return 1
    result, rows = quality.verify(quality.load_records(args.records), reference)
    result["spreadsheet"] = {said(what): count for what, count in result["spreadsheet"].items()}
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if args.rows:
        # Only row numbers of the person's own spreadsheet and what to check there, never a value.
        for row, what in rows.items():
            print(t("cli.row", row=row, what="; ".join(said(each) for each in what)))
    return 0


# quality writes what it finds in a spreadsheet as the Spanish texts of i18n: here it goes to the chosen language.
_CHECKS = {TEXTS["es"][key]: key for key in TEXTS["es"] if key.startswith("check.") and "{" not in TEXTS["es"][key]}
_FIELDS = {TEXTS["es"][key]: key for key in ("field.name", "field.document", "field.file_number")}
_DIFFERS = TEXTS["es"]["check.differs"].split("{")[0]


def said(what: str) -> str:
    """Something quality found, in the language of the messages."""
    if what in _CHECKS:
        return t(_CHECKS[what])
    if what.startswith(_DIFFERS):
        fields = what.removeprefix(_DIFFERS).split(", ")
        named = (t(_FIELDS[field]) if field in _FIELDS else field for field in fields)
        return t("check.differs", fields=", ".join(named))
    return what


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # Before the parser exists: its help is already in the language asked for.
    if forced := i18n.forced_language(argv):
        i18n.set_language(forced)
    i18n.localize_argparse()
    parser = argparse.ArgumentParser(prog="urna-padrones", description=t("cli.description"))
    i18n.add_language_option(parser)
    # Also after the command, where it is easy to add; the one before it is kept if this one is not given.
    language = {"default": argparse.SUPPRESS}
    commands = parser.add_subparsers(required=True)
    command = commands.add_parser("extract", help=t("help.extract"), description=t("help.extract"))
    command.add_argument("pdf", type=Path, metavar=t("meta.file"), help=t("help.file"))
    command.add_argument("--out", type=Path, required=True, help=t("help.out"))
    command.add_argument("--pages", type=positive, help=t("help.pages"))
    command.add_argument("--workers", type=positive, default=2, help=t("help.workers"))
    command.add_argument("--allow-inside-repo", action="store_true", help=t("help.allow_inside_repo"))
    command.add_argument("--ia", choices=external_ai.KINDS, help=t("help.ia", variable=external_ai.KEY_VARIABLE))
    command.add_argument("--ia-url", help=t("help.ia_url", url=external_ai.MISTRAL_URL))
    command.add_argument("--ia-modelo", dest="ia_model", help=t("help.ia_model", model=external_ai.MISTRAL_MODEL))
    command.add_argument("--acepto-enviar", dest="accept_sending", action="store_true", help=t("help.accept"))
    i18n.add_language_option(command, **language)
    command.set_defaults(run=extract)
    command = commands.add_parser("padron", help=t("help.padron"), description=t("help.padron"))
    command.add_argument("records", type=Path, help=t("help.records"))
    command.add_argument("--out", type=Path, required=True, help=t("help.padron_out"))
    command.add_argument("--title", help=t("help.title"))
    command.add_argument("--allow-inside-repo", action="store_true", help=t("help.allow_inside_repo"))
    i18n.add_language_option(command, **language)
    command.set_defaults(run=to_padron)
    command = commands.add_parser("report", help=t("help.report"), description=t("help.report"))
    command.add_argument("records", type=Path, help=t("help.records"))
    i18n.add_language_option(command, **language)
    command.set_defaults(run=show_report)
    command = commands.add_parser("crosscheck", help=t("help.crosscheck"), description=t("help.crosscheck"))
    command.add_argument("first", type=Path, help=t("help.first"))
    command.add_argument("second", type=Path, help=t("help.second"))
    i18n.add_language_option(command, **language)
    command.set_defaults(run=show_crosscheck)
    command = commands.add_parser("verify", help=t("help.verify"), description=t("help.verify"))
    command.add_argument("records", type=Path, help=t("help.records"))
    command.add_argument("spreadsheet", type=Path, help=t("help.spreadsheet"))
    command.add_argument("--filas", dest="rows", action="store_true", help=t("help.rows"))
    i18n.add_language_option(command, **language)
    command.set_defaults(run=show_verify)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
