"""Refresh the reader's copy of the app's look from a checkout of Urna Abierta.

    uv run python tools/traer-tema.py ../urna-abierta

Copies tema.css, temas.js and aplicar-tema.js from apps/web/src/lib/, and from its fuentes/
only the fonts the default theme ("aula") uses, each with its license. Other fonts that were
copied before are removed.
"""

import re
import shutil
import sys
from pathlib import Path

DEFAULT_THEME = "aula"
SCRIPTS = ["tema.css", "temas.js", "aplicar-tema.js"]
UI = Path(__file__).resolve().parent.parent / "src" / "urna_padrones" / "lector" / "ui"


def theme_families(temas: str, theme: str) -> set[str]:
    """The font families of one theme in temas.js, as written there between quotes."""
    start = temas.index(f"id: '{theme}'")
    following = temas.find("id: '", start + 1)
    block = temas[start : following if following != -1 else len(temas)]
    fonts = re.search(r"fuentes:\s*\{(.*?)\}", block, re.DOTALL)
    if not fonts:
        raise SystemExit(f"No encuentro las letras del tema {theme} en temas.js.")
    return set(re.findall(r"\"'([^']+)'\"", fonts[1]))


def font_files(css: str, families: set[str]) -> list[str]:
    """The files tema.css loads for those families."""
    faces = re.findall(r"@font-face\s*\{\s*font-family:\s*'([^']+)';\s*src:\s*url\('\./fuentes/([^']+)'\)", css)
    files = [name for family, name in faces if family in families]
    if not files:
        raise SystemExit("tema.css no carga ninguna letra de ese tema.")
    return files


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    lib = Path(argv[0]).expanduser().resolve() / "apps" / "web" / "src" / "lib"
    if not (lib / "temas.js").is_file():
        print(f"No es una copia de Urna Abierta: falta {lib / 'temas.js'}", file=sys.stderr)
        return 1
    for name in SCRIPTS:
        shutil.copyfile(lib / name, UI / name)
    families = theme_families((lib / "temas.js").read_text(encoding="utf-8"), DEFAULT_THEME)
    fonts = font_files((lib / "tema.css").read_text(encoding="utf-8"), families)
    licenses = [p.name for p in (lib / "fuentes").glob("*.LICENSE.txt") if any(f.startswith(p.name.removesuffix(".LICENSE.txt") + "-") for f in fonts)]
    wanted = set(fonts) | set(licenses)
    target = UI / "fuentes"
    target.mkdir(exist_ok=True)
    for old in target.iterdir():
        if old.name not in wanted:
            old.unlink()
    for name in sorted(wanted):
        shutil.copyfile(lib / "fuentes" / name, target / name)
    print("Copiados:", ", ".join(SCRIPTS + sorted(f"fuentes/{name}" for name in wanted)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
