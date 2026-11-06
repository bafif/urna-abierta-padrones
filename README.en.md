# Urna Abierta: voter roll scanner

[Español](README.md)

Turns voter rolls in any format into the open format read by
Urna Abierta. It can be used on its own, without the app.

**Everything runs on your computer.** A roll holds names and identity documents of real people, so text recognition is
local by default, and no roll ever goes through an account or a server of the project.

## Status

It reads scanned rolls laid out as tables, measures the quality of what it extracts and builds the `.padron` file that
gets uploaded to Urna Abierta. The file follows an [open format](docs/padron-format.md), public domain. It is used through
screens in the browser, with no terminal, or from a terminal.

## Without a terminal: the roll reader

The reader opens its screens in the browser and goes step by step, with one question per screen:

1. **Choose the roll:** drag the scanned PDF into the window, or find it on your computer.
2. **Read it:** the computer reads page by page. It shows which page it is on, how many people it found and roughly how
   long is left. It can be cancelled.
3. **Review:** it shows the rows that were not clear one at a time, with the image of the row on top and its data below,
   to fix them or say they are fine. The ones you do not review stay pending, to be reviewed later in the app.
4. **Save:** you get a `.padron` file. In Urna Abierta, go into the election and upload it with “Upload the roll”.

**It is private.** The PDF never leaves your computer, and the reader can only be opened from it, with the address it
shows when it starts. It keeps a copy of the PDF in a temporary folder only your user can open and deletes it when it
closes: with “Close the reader”, when its window is closed, or by itself after half an hour without use. If it is cut
off abruptly, it deletes it the next time it starts. It keeps nothing else. The `.padron` file has people's data: once it is uploaded to the app, delete it.

For now it understands rolls laid out as a ruled table. If the roll is in an Excel or CSV spreadsheet, you do not need
the reader: upload it straight into the app with “Upload the roll”.

From a checkout of this repository it opens with:

```sh
uv run python -m urna_padrones.lector
```

`--no-browser` does not open the browser, `--port` picks the port (otherwise a free one at random) and `--self-test`
checks, offline, that the reader works.

## Download

The reader comes ready to use for Windows, macOS and Linux: there is no need to install Python or anything else.
Download the file for your computer from the [latest release](../../releases/latest):

| Your computer | File |
|---|---|
| Windows 10 or 11 | `urna-abierta-lector-windows-x64.zip` |
| Mac with an Apple chip (M1 or later), on macOS 14 or newer | `urna-abierta-lector-macos-arm64.zip` |
| Mac with an Intel processor, on macOS 14 or newer | `urna-abierta-lector-macos-x64.zip` |
| 64-bit Linux with glibc 2.28 or newer (Ubuntu 20.04, Debian 10, Fedora 29 or newer) | `urna-abierta-lector-linux-x64.tar.gz` |

If the [releases page](../../releases) has no release yet, open the reader from a terminal: with
[uv](https://docs.astral.sh/uv/) installed, in a copy of this repository (on GitHub, "Code" → "Download ZIP"), run
`uv run python -m urna_padrones.lector`. More in
[Without a terminal: the roll reader](#without-a-terminal-the-roll-reader).

To know which Mac you have: Apple menu → "About This Mac". If it says "Chip" and a name like "Apple M1", it has an
Apple chip; if it says "Processor" and a name with "Intel", it is the other one.

The program is not signed with a paid certificate, so the first time Windows and macOS warn that they do not know it.
Before opening it, it is worth [checking the file](#check-the-file).

### On Windows

1. Right-click the `.zip` and choose "Extract All". Do not open it from inside the zip.
2. In the folder you get, double-click `urna-abierta-lector.exe`.
3. If "Windows protected your PC" appears, click "More info" and then "Run anyway".
4. A black window opens with the reader's address, and the browser opens at that address by itself. Keep the window
   open while you use it: closing it closes the reader.

If instead of the reader you get a message saying the reading engine could not be loaded, install the latest
[Microsoft Visual C++ (x64)](https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist) and open it again.

### On macOS

1. Double-click the `.zip`: you get `Urna Abierta Lector.app`. You can move it to Applications if you like.
2. Double-click the app. macOS says it cannot check that it is free of malware: close the message without moving the
   app to the Trash.
3. Open System Settings → Privacy & Security, scroll down to "Security" and, next to the message about
   "Urna Abierta Lector", click "Open Anyway". Confirm with your password and choose "Open".
4. This is needed only once. The reader opens in the browser and has no window of its own and no Dock icon. It closes
   with "Close the reader", or by itself half an hour after you close the tab.

If you closed the tab by mistake, open it again from the browser's history: while the reader is still open, opening
the app again does not open another tab. What the reader writes, its address included, goes to
`~/Library/Logs/Urna Abierta/lector.log`.

### On Linux

1. Unpack the file: `tar -xzf urna-abierta-lector-linux-x64.tar.gz`.
2. Start it from a terminal: `./urna-abierta-lector-linux-x64/urna-abierta-lector`. It shows the address and opens the
   browser. It closes when you close the terminal, with Ctrl+C or with "Close the reader".

### Check the file

Next to each file of the release there is another with the same name ending in `.sha256`, holding its SHA-256
fingerprint. Compute the fingerprint of the file you downloaded and make sure it is the same:

- On Windows, in PowerShell: `Get-FileHash .\urna-abierta-lector-windows-x64.zip`, and compare it with the text of the
  `.sha256` file (Windows shows it in capitals, which does not matter).
- On macOS, with both files in the same folder: `shasum -a 256 -c urna-abierta-lector-macos-arm64.zip.sha256`. It says
  `OK` when it matches.
- On Linux, also with both files in the same folder: `sha256sum -c urna-abierta-lector-linux-x64.tar.gz.sha256`.

Each file also has a GitHub attestation that it was built on GitHub's machines from the code of this repository. It is
verified with the [GitHub CLI](https://cli.github.com):
`gh attestation verify <file> --repo <owner>/urna-abierta-padrones`, with the owner shown in this repository's address.

## Usage

You need [uv](https://docs.astral.sh/uv/). The reading model ships with the program, so it works offline from the first
run and never downloads anything. To use another model, `URNA_PADRONES_MODELO` can point to an ONNX recognition model
that carries its own character list.

```sh
uv sync
uv run urna-padrones extract roll.pdf --out ~/private/roll.jsonl
uv run urna-padrones report ~/private/roll.jsonl
uv run urna-padrones padron ~/private/roll.jsonl --out ~/private/my-roll.padron
uv run urna-padrones crosscheck ~/private/other.jsonl ~/private/roll.jsonl
uv run urna-padrones verify ~/private/roll.jsonl ~/private/spreadsheet.xlsx --filas
```

- `extract` saves the data with permissions for your user only, and refuses to write it inside a git repository. In a
  terminal it shows which page it is on. `--pages N` reads only the first N pages and `--workers N`, how many at a time.
- `report`, `crosscheck` and `verify` print counts only, never data about a person. `report` compares with the
  numbering of the roll to warn if anyone is missing.
- `crosscheck` compares two rolls that share people. Since their reading errors are independent, it measures quality
  without anyone having to read the data.
- `verify` compares what was read with the same roll typed into a spreadsheet (`.xlsx` or `.csv`). From the spreadsheet
  it reads only the name, the document and the student number; other columns are never opened. It says how many people
  match, how many differ, and whether the reader had marked the ones that differ as sure. It also checks the spreadsheet
  itself: repeated documents or documents of another length, and student numbers whose check digit does not add up. A
  difference may be a reading error or a typo: `--filas` also lists the spreadsheet rows to look at and what to look at
  in each, without showing any data.

In the faculty's student numbers, the digit after the slash is a check digit (modulo 11, with weights 2 to 7 from the
right; 10 or 11 is written as 1). The reader flags a four-digit student number that does not match it: it is almost
always a misread digit.

## Tests

```sh
uv run pytest
```

They use made-up scans with invented people. **Never upload a real roll to the repository.**

## How the reader is built

The files of each release are built by GitHub Actions (`.github/workflows/release.yml`) when a `v*` tag is pushed,
each one on a machine of the system it is for: Windows x64, macOS with an Apple chip, macOS with Intel and Linux x64
(Ubuntu 22.04). They are never built on a personal computer, so they carry nobody's paths or names. Each machine builds
the reader, runs its own check without network, makes sure nothing was downloaded and that onnxruntime's telemetry
stayed off, writes the file with its SHA-256 and its attestation, and uploads it to the release, which is published
once all four are there.

To build it for your system, on your computer:

```sh
uv sync --managed-python --no-editable --group build
uv run --no-sync python packaging/build.py --self-test --start-time --archive
```

It ends up in `dist/`. Some decisions:

- It is built with the Python that uv installs, the version in `.python-version`, never with one the machine already
  has (`--managed-python`, or `UV_PYTHON_PREFERENCE=only-managed` in the workflows).
- It uses [PyInstaller](https://pyinstaller.org) with `packaging/lector.spec`, as a folder and not as a single file: it
  starts quickly, without unpacking 300 MB on every start, and antivirus programs pay it less attention.
- Of rapidocr's models only the recognition model the reader uses goes in. Tk stays out, and so does OpenCV's video
  plugin (FFmpeg) on Windows.
- On Intel Macs onnxruntime stays at 1.23.2, the last release with packages for them (`pyproject.toml` pins it).
  onnxruntime and OpenCV need macOS 14 on both kinds of Mac; `build.py` fails if anything asks for more.
- On Linux it leaves out the C++ runtime of the machine that builds it, which would ask for that machine's glibc: it
  uses the system's and needs glibc 2.28 or newer. `build.py` works it out on every build.
- `THIRD_PARTY_NOTICES.txt` and the `licenses/` folder are generated on every build from what actually went in
  (`packaging/notices.py`), with the license texts each package carries. They also name the libraries Python carries
  inside it (OpenSSL, SQLite, zlib and others), whose texts are in `LICENSES/python/`.
- `packaging/launcher.py` is the program's entry point: it turns onnxruntime's telemetry off before loading it, on
  macOS it sends what the program writes to a file, because the app has no terminal, and if the reading engine does not
  load it says so in words and, on Windows, with the Visual C++ link.
- The program's own check runs with an empty temp folder and fails if onnxruntime left its `.ses` file there, which
  shows up when its telemetry is on.
- `PYTHONHASHSEED` is fixed and `SOURCE_DATE_EPOCH` is the time of the last commit. On Linux, building
  the same commit twice gives the same `.tar.gz`, byte for byte: this has been checked. The Windows `.zip` uses fixed
  dates too, but has not been checked yet. The macOS `.zip` files do not come out the same: `ditto` keeps the time each
  file was built.

On Linux it takes about 340 MB unpacked and 140 MB compressed.

## License

[AGPL-3.0-or-later](LICENSE).
