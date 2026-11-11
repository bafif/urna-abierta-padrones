# How it is made

[Español](desarrollo.md)

## Tests

```sh
uv run pytest
```

They use made-up scans, PDFs with text and photos with invented people (`tests/fake_roll.py` and
`tests/fake_layouts.py`). **Never upload a real roll to the repository**: `.gitignore` leaves out `.pdf`, `.padron`
and `.jsonl` files, and `extract` refuses to write inside a git repository.

On GitHub they run on Linux, Windows and macOS (`.github/workflows/tests.yml`). The ones in `tests/test_extract.py` ask
fontconfig for Liberation Sans and are skipped where it is missing, as on Windows and macOS; the others draw with Arial
if they cannot find it.

Every document is in Spanish and in English: `X.md` and `X.en.md`, or, when the name changes with the language, two
files that name each other with a link at the top. `tests/test_docs.py` checks the pairs and that every relative link
leads to a file and a heading that exist.

## The reader's screens

They are in `src/urna_padrones/lector/ui/`. The theme and its fonts are copies from the app: see
[its README](../src/urna_padrones/lector/ui/README.en.md).

## How the reader is built

The files of each release are built by GitHub Actions (`.github/workflows/release.yml`) when a `v*` tag is pushed, each
one on a machine of the system it is for: Windows x64, macOS with an Apple chip, macOS with Intel, Linux x64 (Ubuntu
22.04) and Linux x64 with musl (an Alpine 3.24 container). They are never built on a personal computer, so they carry
nobody's paths or names. Each machine builds the reader, runs its own check without network, makes sure nothing was
downloaded and that onnxruntime's telemetry stayed off, writes the file with its SHA-256 and its attestation, and
uploads it to the release, which is published once all five are there. The same workflow can be run by hand on `main`,
from “Actions”, “Release”, “Run workflow”: it builds and checks the five the same way, without creating or publishing
any release.

To build it for your system, on your computer:

```sh
uv sync --managed-python --no-editable --group build
uv run --no-sync python packaging/build.py --self-test --start-time --archive
```

It ends up in `dist/`. On Linux it takes about 340 MB unpacked and 140 MB compressed; the Alpine one, about 580 MB and
225 MB, because its OpenCV comes from Alpine's packages, which build it with every module.

For Alpine, `packaging/alpine.sh` prepares the Python that builds it, inside a container:

```sh
podman run --rm -v "$PWD":/src -w /src docker.io/library/alpine:3.24 \
  sh -c 'sh packaging/alpine.sh && /opt/lector/bin/python packaging/build.py --self-test --archive'
```

## Decisions

- It is built with the Python that uv installs, the version in `.python-version`, never with one the machine already
  has (`--managed-python`, or `UV_PYTHON_PREFERENCE=only-managed` in the workflows).
- It uses [PyInstaller](https://pyinstaller.org) with `packaging/lector.spec`, as a folder and not as a single file: it
  starts quickly, without unpacking 300 MB on every start, and antivirus programs pay it less attention.
- Of rapidocr's models only the recognition model the reader uses goes in. Tk stays out, and so does OpenCV's video
  plugin (FFmpeg) on Windows.
- setuptools stays out too: PyInstaller needs it to build, but the reader does not use it. A test checks that the
  reader's code does not import it.
- On Intel Macs onnxruntime stays at 1.23.2, the last release with packages for them (`pyproject.toml` pins it).
  onnxruntime and OpenCV need macOS 14 on both kinds of Mac; `build.py` fails if anything asks for more.
- On Linux it leaves out the C++ runtime of the machine that builds it, which would ask for that machine's glibc: it
  uses the system's and needs glibc 2.28 or newer. `build.py` works it out on every build. On Alpine it does carry it:
  an Alpine without a desktop may not have one.
- PyPI publishes no onnxruntime and no OpenCV for musl, nor pyclipper for Alpine's Python: on Alpine those three and
  numpy come from its packages, and everything else, PyInstaller included, at the versions in `uv.lock`.
- `THIRD_PARTY_NOTICES.txt` and the `licenses/` folder are generated on every build from what actually went in
  (`packaging/notices.py`), with the license texts each package carries. They also name the libraries Python carries
  inside it (OpenSSL, SQLite, zlib and others), whose texts are in `LICENSES/python/`.
- `packaging/launcher.py` is the program's entry point: it turns onnxruntime's telemetry off before loading it, on
  macOS it sends what the program writes to a file, because the app has no terminal, and if the reading engine does not
  load it says so in words and, on Windows, with the Visual C++ link.
- The program's own check runs with an empty temp folder and fails if onnxruntime left its `.ses` file there, which
  shows up when its telemetry is on.
- `PYTHONHASHSEED` is fixed and `SOURCE_DATE_EPOCH` is the time of the last commit. On Linux, building the same commit
  twice gives the same `.tar.gz`, byte for byte. The Windows `.zip` uses fixed dates too, but whether it comes out the
  same has not been checked. The macOS `.zip` files do not come out the same: `ditto` keeps the time each file was
  built.
- The Windows and macOS icons are already made in `packaging/iconos/`, so building the reader needs nothing more. They
  are made again with `uv run python tools/hacer-iconos.py`, which draws each size from the same SVG with
  rsvg-convert.
