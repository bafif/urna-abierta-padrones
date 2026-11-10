"""Every document in Spanish and in English, with links that lead somewhere.

The pair of a document: X.en.md next to X.md, or, when the name changes with the language (docs/formato-padron.md
and docs/padron-format.md), the one its [English] or [Español] link names at the top; the two must name each other.
CLAUDE.md, licenses and the templates in .github/, which carry both languages inside, are left out.

In every .md it also checks that each relative link leads to a file that exists, and to a heading of it when it has
an anchor, and that a document does not send its reader to the other language when there is a version in its own
(except for the link to its own pair).
"""

import posixpath
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
TOP_LINES = 8
MARKDOWN_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HTML_LINK = re.compile(r"\b(?:src|href)=\"([^\"]+)\"")
LANGUAGE_LINK = re.compile(r"\[(English|Español)\]\(([^)\s]+)\)")
EXTERNAL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:|^//")
FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def documents() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "*.md"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
        found = [p for p in out.split("\0") if p]
    except (OSError, subprocess.CalledProcessError):
        # Without git, as from a copy of the files: everything but hidden folders and what gets built.
        skip = {"build", "dist", "node_modules"}
        found = [
            p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.md")
            if not any(part.startswith(".") or part in skip for part in p.relative_to(ROOT).parts[:-1])
        ]
    return sorted(p for p in found if (ROOT / p).is_file())


def left_out(path: str) -> bool:
    name = posixpath.basename(path)
    return path.startswith(".github/") or name == "CLAUDE.md" or name.startswith(("LICENSE", "CHANGELOG"))


def prose(text: str) -> list[str]:
    """The lines where a link is a link: without code blocks and inline code."""
    lines, inside = [], False
    for line in text.split("\n"):
        if FENCE.match(line):
            inside = not inside
            lines.append("")
        else:
            lines.append("" if inside else re.sub(r"`[^`]*`", "", line))
    return lines


def slug(heading: str) -> str:
    """The anchor GitHub gives a heading."""
    text = re.sub(r"<[^>]+>", "", heading)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-")


def anchors(text: str) -> set[str]:
    seen: dict[str, int] = {}
    found, inside = set(), False
    for line in text.split("\n"):
        if FENCE.match(line):
            inside = not inside
        heading = None if inside else HEADING.match(line)
        if heading:
            base = slug(heading.group(2))
            times = seen.get(base, 0)
            seen[base] = times + 1
            found.add(f"{base}-{times}" if times else base)
    found.update(re.findall(r"\b(?:id|name)=\"([^\"]+)\"", text))
    return found


def resolve(origin: str, target: str) -> tuple[str, str]:
    """(path from the root, anchor) of a relative link in `origin`."""
    path, _, anchor = target.partition("#")
    if not path:
        return origin, unquote(anchor)
    base = "" if path.startswith("/") else posixpath.dirname(origin)
    return posixpath.normpath(posixpath.join(base, path.lstrip("/"))), unquote(anchor)


def check() -> tuple[list[str], int]:
    docs = documents()
    texts = {d: (ROOT / d).read_text(encoding="utf-8") for d in docs}
    links = {
        d: [(i, m.group(1)) for i, line in enumerate(prose(texts[d]), 1) for pattern in (MARKDOWN_LINK, HTML_LINK)
            for m in pattern.finditer(line)]
        for d in docs
    }
    problems: list[str] = []
    pair: dict[str, str] = {}
    language: dict[str, str] = {}

    for d in (d for d in docs if not left_out(d)):
        if d.endswith(".en.md"):
            pair[d], language[d] = d[: -len(".en.md")] + ".md", "en"
        elif d[:-3] + ".en.md" in texts:
            pair[d], language[d] = d[:-3] + ".en.md", "es"
        else:
            top = next((m for m in (LANGUAGE_LINK.search(line) for line in prose(texts[d])[:TOP_LINES]) if m), None)
            if not top or EXTERNAL.match(top.group(2)):
                problems.append(f"{d}: it has no version in the other language: no {posixpath.basename(d)[:-3]}.en.md "
                                "next to it, and no [English] or [Español] link at the top")
                continue
            pair[d] = resolve(d, top.group(2))[0]
            language[d] = "es" if top.group(1) == "English" else "en"

    for d, other in pair.items():
        if other not in texts:
            problems.append(f"{d}: its version in {'English' if language[d] == 'es' else 'Spanish'}, {other}, does not exist")
            continue
        if other in pair and pair[other] != d:
            problems.append(f"{d}: names {other} as its pair, but {other} names {pair[other]}")
        if language.get(other) == language[d]:
            problems.append(f"{d} and {other} are pairs, but both say they are in the same language")
        if not any(resolve(d, t)[0] == other for _, t in links[d] if not EXTERNAL.match(t)):
            problems.append(f"{d}: does not link to its version in the other language, {other}")

    cache: dict[str, set[str]] = {}
    for d in docs:
        for line, target in links[d]:
            if EXTERNAL.match(target):
                continue
            destination, anchor = resolve(d, target)
            # Climbing out of the repository leads to a page of GitHub, like ../../releases, not to a file.
            if destination == ".." or destination.startswith("../"):
                continue
            if not (ROOT / destination).exists():
                problems.append(f"{d}:{line}: {target} leads to a file that does not exist ({destination})")
                continue
            if anchor and destination.endswith(".md"):
                if destination not in cache:
                    cache[destination] = anchors(texts.get(destination) or (ROOT / destination).read_text(encoding="utf-8"))
                if anchor not in cache[destination]:
                    problems.append(f"{d}:{line}: {target} leads to #{anchor}, which is not a heading of {destination}")
            mine, theirs, translated = language.get(d), language.get(destination), pair.get(destination)
            if mine and theirs and mine != theirs and destination != pair.get(d) and translated in texts:
                problems.append(f"{d}:{line}: {target} is in the other language; this document should link to {translated}")
    return problems, sum(1 for each in language.values() if each == "es")


def test_every_document_is_in_both_languages_and_its_links_lead_somewhere():
    problems, pairs = check()
    assert pairs > 0
    assert not problems, "\n".join(problems)
