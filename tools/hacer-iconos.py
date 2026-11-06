"""Make the icons of the packaged reader from the mark its screens already show.

    uv run python tools/hacer-iconos.py

It takes LOGO from src/urna_padrones/lector/ui/lector.js, as it is, paints it in the colour of the mark of the
default theme, «Aula», on a transparent background, and writes packaging/iconos/lector.ico (Windows) and
packaging/iconos/lector.icns (macOS). Each size is drawn from the SVG by rsvg-convert (librsvg), which has to be
installed; Pillow, of the dev group, puts the sizes together. The files are kept in the repository, so a build
needs neither: run this again only when the mark changes.
"""

import io
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "src" / "urna_padrones" / "lector" / "ui" / "lector.js"
THEMES = ROOT / "src" / "urna_padrones" / "lector" / "ui" / "temas.js"
OUT = ROOT / "packaging" / "iconos"
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
ICNS_SIZES = [16, 32, 64, 128, 256, 512, 1024]


def logo() -> str:
    found = re.search(r"const LOGO = '(<svg .*?</svg>)';", SCRIPT.read_text(encoding="utf-8"))
    if not found:
        raise SystemExit(f"No encontré LOGO en {SCRIPT.relative_to(ROOT)}.")
    return found.group(1)


def mark_colour() -> str:
    """The colour of the mark in the light version of «Aula», the theme the reader uses."""
    text = THEMES.read_text(encoding="utf-8")
    aula = text[text.index("id: 'aula'"):]
    found = re.search(r"claro: \{.*?marca: '(#[0-9A-Fa-f]{6})'", aula, flags=re.DOTALL)
    if not found:
        raise SystemExit(f"No encontré el color de la marca de «Aula» en {THEMES.relative_to(ROOT)}.")
    return found.group(1)


def render(svg: str, size: int) -> Image.Image:
    drawn = subprocess.run(
        ["rsvg-convert", "--width", str(size), "--height", str(size), "--format", "png"],
        input=svg.encode("utf-8"),
        capture_output=True,
        check=True,
    ).stdout
    return Image.open(io.BytesIO(drawn)).convert("RGBA")


def main() -> None:
    if shutil.which("rsvg-convert") is None:
        raise SystemExit("Hace falta rsvg-convert (librsvg): por ejemplo, el paquete librsvg2-bin o librsvg.")
    svg = logo().replace('aria-hidden="true"', 'xmlns="http://www.w3.org/2000/svg"', 1)
    svg = svg.replace("currentColor", mark_colour())
    OUT.mkdir(parents=True, exist_ok=True)
    largest = render(svg, max(ICNS_SIZES))
    ico = [render(svg, size) for size in ICO_SIZES]
    ico[-1].save(OUT / "lector.ico", format="ICO", sizes=[(s, s) for s in ICO_SIZES], append_images=ico[:-1])
    icns = [render(svg, size) for size in ICNS_SIZES[:-1]]
    largest.save(OUT / "lector.icns", format="ICNS", append_images=icns)
    for path in (OUT / "lector.ico", OUT / "lector.icns"):
        print(f"{path.relative_to(ROOT)}: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
