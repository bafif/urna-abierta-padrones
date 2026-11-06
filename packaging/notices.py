"""Write the third-party notices of the packaged reader from the distributions that went into it.

The list comes from what PyInstaller collected and the texts from each installed distribution's
own license files, so it stays true when a dependency changes. The libraries built into Python
itself are listed too, with their texts from LICENSES/python/. lector.spec calls write_notices();
on its own it prints the notices for the whole environment:

    python packaging/notices.py OUTPUT_FOLDER
"""

import hashlib
import importlib
import importlib.util
import os
import re
import shutil
import sys
import sysconfig
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = "urna-abierta-padrones"
# License texts kept in this repository, for licenses that the bundled files name but do not carry whole.
OWN_TEXTS = ROOT / "LICENSES"
LICENSE_NAME = re.compile(
    r"^(licen[cs]e|copying|notice|authors|thirdpartynotices|third_party_notices|model_licenses)", re.IGNORECASE
)


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def bundled_distributions(top_level_names: set[str]) -> list[metadata.Distribution]:
    """The installed distributions that provide any of these top-level modules or folders, but this project."""
    owners = metadata.packages_distributions()
    names = {normalized(dist) for top in top_level_names for dist in owners.get(top, [])}
    names.discard(PROJECT)
    found = {normalized(dist.metadata["Name"]): dist for dist in metadata.distributions() if dist.metadata["Name"]}
    return [found[name] for name in sorted(names) if name in found]


def runtime_distributions() -> list[metadata.Distribution]:
    """Everything this project needs to run on this computer, following the requirements."""
    from packaging.requirements import Requirement

    seen: dict[str, metadata.Distribution] = {}
    pending = [PROJECT]
    while pending:
        name = normalized(pending.pop())
        if name in seen:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        seen[name] = dist
        for text in dist.requires or []:
            requirement = Requirement(text)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
    seen.pop(PROJECT, None)
    return [seen[name] for name in sorted(seen)]


def license_of(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    expression = meta.get("License-Expression")
    if expression:
        return expression
    text = (meta.get("License") or "").strip()
    if text and "\n" not in text and len(text) < 80:
        return text
    classifiers = [c.split(" :: ")[-1] for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    return ", ".join(classifiers) or "see its license files"


def home_of(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    urls = dict(item.split(", ", 1) for item in meta.get_all("Project-URL") or [] if ", " in item)
    for key in ("homepage", "home", "source", "source code", "code", "repository", "documentation"):
        for label, url in urls.items():
            if label.lower() == key:
                return url
    return meta.get("Home-page") or (next(iter(urls.values())) if urls else "")


def license_files(dist: metadata.Distribution) -> list[Path]:
    """Its license and notice files: those its metadata declares and those it carries in the package."""
    files = []
    for item in dist.files or []:
        parts = item.parts
        in_metadata = parts[0].endswith(".dist-info")
        declared = in_metadata and len(parts) > 2 and parts[1] == "licenses"
        if declared or LICENSE_NAME.match(item.name):
            if item.suffix in (".py", ".pyc", ".pyi"):
                continue
            path = Path(dist.locate_file(item))
            if path.is_file():
                files.append(path)
    return files


def python_license() -> Path | None:
    for folder in (Path(sysconfig.get_paths()["stdlib"]), Path(sys.base_prefix)):
        for name in ("LICENSE.txt", "LICENSE"):
            if (folder / name).is_file():
                return folder / name
    return None


@dataclass(frozen=True)
class PythonPart:
    """A library that Python carries inside it, or next to its own modules on Windows."""

    name: str
    # The Python modules built with it: it is in the bundle when one of them is.
    modules: tuple[str, ...]
    license: str
    # Below LICENSES/.
    text: str
    home: str
    # The module and attribute that say its version, when Python tells it.
    version_from: tuple[str, str] | None = None


# The Python that uv installs (python-build-standalone) links these libraries in, and its install
# carries no license files for them. Their texts are kept in LICENSES/, each copied from the
# project's own license file. Tcl/Tk is not here: lector.spec leaves it out of the bundle.
PYTHON_PARTS = (
    PythonPart("OpenSSL", ("_ssl", "_hashlib"), "Apache-2.0", "Apache-2.0.txt", "https://openssl-library.org",
               ("ssl", "OPENSSL_VERSION")),
    PythonPart("SQLite", ("_sqlite3",), "blessing", "python/sqlite.txt", "https://sqlite.org",
               ("sqlite3", "sqlite_version")),
    PythonPart("zlib", ("zlib",), "Zlib", "python/zlib.txt", "https://zlib.net", ("zlib", "ZLIB_RUNTIME_VERSION")),
    PythonPart("bzip2", ("_bz2",), "bzip2-1.0.6", "python/bzip2.txt", "https://sourceware.org/bzip2/"),
    PythonPart("XZ Utils (liblzma)", ("_lzma",), "0BSD", "python/xz.txt", "https://tukaani.org/xz/"),
    PythonPart("libffi", ("_ctypes",), "MIT", "python/libffi.txt", "https://sourceware.org/libffi/"),
    PythonPart("Expat", ("pyexpat", "_elementtree"), "MIT", "python/expat.txt", "https://libexpat.github.io",
               ("pyexpat", "EXPAT_VERSION")),
    PythonPart("mpdecimal", ("_decimal",), "BSD-2-Clause", "python/mpdecimal.txt",
               "https://www.bytereef.org/mpdecimal/", ("decimal", "__libmpdec_version__")),
    PythonPart("libedit", ("readline",), "BSD-3-Clause", "python/libedit.txt", "https://thrysoee.dk/editline/"),
    PythonPart("ncurses", ("_curses", "readline"), "X11-distribute-modifications-variant", "python/ncurses.txt",
               "https://invisible-island.net/ncurses/", ("curses", "ncurses_version")),
    PythonPart("libuuid (util-linux)", ("_uuid",), "BSD-3-Clause", "python/libuuid.txt",
               "https://github.com/util-linux/util-linux"),
)  # fmt: skip


def readline_backend() -> str:
    """Which library Python's readline module is built with: "editline", "readline", or "" without one."""
    try:
        import readline
    except ImportError:
        return ""
    return getattr(readline, "backend", "editline" if "libedit" in (readline.__doc__ or "") else "readline")


def python_parts(extension_modules: set[str] | None = None) -> list[PythonPart]:
    """The libraries inside Python that are in the bundle.

    One is in when any of its modules is built into the interpreter or is among extension_modules,
    the extension modules of Python that went into the bundle (None: every one this Python has).
    """

    def present(module: str) -> bool:
        if module in sys.builtin_module_names:
            return True
        if extension_modules is None:
            return importlib.util.find_spec(module) is not None
        return module in extension_modules

    parts = [part for part in PYTHON_PARTS if any(present(module) for module in part.modules)]
    if any(part.name == "libedit" for part in parts) and readline_backend() == "readline":
        raise SystemExit("This Python's readline is GNU Readline, not libedit: add its license to notices.py")
    return parts


def part_version(part: PythonPart) -> str:
    """Its version as Python reports it, or "" when it does not."""
    if part.version_from is None:
        return ""
    module, attribute = part.version_from
    try:
        value = getattr(importlib.import_module(module), attribute)
    except Exception:  # noqa: BLE001 - without its version it is still listed
        return ""
    if isinstance(value, tuple):
        return ".".join(str(number) for number in value[:2])
    found = re.search(r"\d+(\.\d+)+", str(value))
    return found.group(0) if found else ""


def copy_unique(sources: list[Path], folder: Path, base: Path | None) -> list[str]:
    """Copy the files into folder, once per content, keeping their path below base. Returns their new paths.

    Two different texts never end up in the same file: the second one gets a number.
    """
    written, seen = [], set()
    for source in sources:
        text = source.read_bytes()
        digest = hashlib.sha256(text).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        try:
            relative = source.relative_to(base) if base else Path(source.name)
        except ValueError:
            relative = Path(source.name)
        # In the distribution's own dist-info only the part after "licenses" says anything. The
        # dist-info folders of the libraries it carries inside (setuptools/_vendor/zipp-3.19.dist-info/...)
        # stay, so that each library keeps its own text.
        parts = list(relative.parts)
        if len(parts) > 1 and parts[0].endswith(".dist-info"):
            parts = parts[1:]
            if len(parts) > 1 and parts[0] == "licenses":
                parts = parts[1:]
        first = target = folder.joinpath(*parts)
        number = 2
        while target.exists() and target.read_bytes() != text:
            target = first.with_name(f"{first.stem}-{number}{first.suffix}")
            number += 1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text)
        written.append(target.as_posix())
    return written


def write_notices(
    output: Path,
    dists: list[metadata.Distribution],
    version: str = "",
    source_url: str = "",
    ffmpeg: bool = False,
    extension_modules: set[str] | None = None,
) -> list[Path]:
    """Write THIRD_PARTY_NOTICES.txt and licenses/ into output. Returns every file written.

    ffmpeg says that OpenCV's FFmpeg libraries are in the bundle, which their license asks to say.
    extension_modules are the names of Python's own extension modules in the bundle (see python_parts).
    """
    if output.exists():
        shutil.rmtree(output)
    licenses = output / "licenses"
    licenses.mkdir(parents=True)
    entries = []

    def add(name: str, version_text: str, license_text: str, home: str, files: list[str], extra=()) -> None:
        relative = [Path(f).relative_to(output).as_posix() for f in files]
        entries.append((name, version_text, license_text, home, relative, list(extra)))

    for dist in dists:
        name, dist_version = dist.metadata["Name"], dist.version
        folder = licenses / f"{normalized(name)}-{dist_version}"
        base = Path(dist.locate_file(""))
        written = copy_unique(license_files(dist), folder, base)
        add(name, dist_version, license_of(dist), home_of(dist), written)

    own = sorted(OWN_TEXTS.glob("*.txt")) if OWN_TEXTS.is_dir() else []
    common = copy_unique(own, licenses, None)

    python_text = python_license()
    parts = python_parts(extension_modules)
    add(
        "Python",
        sys.version.split()[0],
        "PSF-2.0",
        "https://www.python.org",
        copy_unique([python_text], licenses / "python", None) if python_text else [],
        [f"Includes: {', '.join(part.name for part in parts)}"] if parts else [],
    )
    for part in parts:
        text = OWN_TEXTS / part.text
        written = copy_unique([text], (licenses / part.text).parent, None)
        add(part.name, part_version(part), part.license, part.home, written, ["Part of: Python"])
    try:
        pyinstaller = metadata.distribution("pyinstaller")
        add(
            "PyInstaller (bootloader)",
            pyinstaller.version,
            "GPL-2.0-or-later WITH Bootloader-exception",
            "https://pyinstaller.org",
            copy_unique(
                license_files(pyinstaller),
                licenses / f"pyinstaller-{pyinstaller.version}",
                Path(pyinstaller.locate_file("")),
            ),
        )
    except metadata.PackageNotFoundError:
        pass

    lines = [
        f"Urna Abierta, lector de padrones {version}".rstrip(),
        "Software de terceros que trae este programa / Third-party software included in this program",
        "",
        "El lector es software libre bajo la licencia AGPL-3.0-or-later (LICENSE.txt).",
        "The reader is free software under the AGPL-3.0-or-later license (LICENSE.txt).",
    ]
    if source_url:
        lines += [f"Código fuente / Source code: {source_url}"]
    lines += [
        "",
        "Trae los componentes de abajo, cada uno con su licencia. Los textos completos están en la carpeta licenses/.",
        "It carries the components below, each under its own license. The full texts are in the licenses/ folder.",
        "",
        "El modelo de reconocimiento de texto (PP-OCR, de PaddleOCR) viene dentro de rapidocr, bajo Apache-2.0;",
        "sus términos están en licenses/rapidocr-*/MODEL_LICENSES.md.",
        "The text recognition model (PP-OCR, from PaddleOCR) ships inside rapidocr under Apache-2.0;",
        "its terms are in licenses/rapidocr-*/MODEL_LICENSES.md.",
        "",
    ]
    if ffmpeg:
        lines += [
            "OpenCV trae las bibliotecas de FFmpeg (https://ffmpeg.org), bajo LGPL-2.1-or-later, como bibliotecas",
            "compartidas que se pueden reemplazar. Su licencia y la forma de obtener su código están en",
            "licenses/opencv-python-headless-*/LICENSE-3RD-PARTY.txt y en https://github.com/opencv/opencv-python.",
            "OpenCV carries the FFmpeg libraries (https://ffmpeg.org) under LGPL-2.1-or-later, as shared libraries",
            "that can be replaced. Their license and how to get their source code are in",
            "licenses/opencv-python-headless-*/LICENSE-3RD-PARTY.txt and at https://github.com/opencv/opencv-python.",
            "",
        ]
    for name, version_text, license_text, home, files, extra in entries:
        lines.append(f"{name} {version_text}".rstrip())
        lines.append(f"  License: {license_text}")
        if home:
            lines.append(f"  Home: {home}")
        for file in files:
            lines.append(f"  Text: {file}")
        lines += [f"  {line}" for line in extra]
        lines.append("")
    if common:
        lines.append("License texts named above / Textos de licencias nombradas arriba:")
        lines += [f"  {Path(f).relative_to(output).as_posix()}" for f in common]
        lines.append("")
    notices = output / "THIRD_PARTY_NOTICES.txt"
    notices.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return sorted(p for p in output.rglob("*") if p.is_file())


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("notices")
    write_notices(
        target, runtime_distributions(), os.environ.get("URNA_VERSION", ""), os.environ.get("URNA_SOURCE_URL", "")
    )
    print((target / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8"))
