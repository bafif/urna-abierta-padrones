# Urna Abierta: voter roll scanner

[Español](README.md)

Turns voter rolls in any format into the open format read by
Urna Abierta. It can be used on its own, without the app.

**Everything runs on your computer.** A roll holds names and identity documents of real people, so text recognition is
local by default, and no roll ever goes through an account or a server of the project. Only if you ask for it from the
terminal, with your own key, is it read by an external AI service: see
[With your own AI](#with-your-own-ai-from-the-terminal).

## Status

It reads rolls laid out as tables, from scanned PDFs, PDFs with text and photos, measures the quality of what it
extracts and builds the `.padron` file that gets uploaded to Urna Abierta. The file follows an
[open format](docs/padron-format.md), public domain. It is used through screens in the browser, with no terminal, or
from a terminal.

## What it reads

- **Scanned PDFs and photos of a roll laid out as a ruled table.** It looks for the header in the first rows of the
  table and reads each column by its name, in any order and even with extra columns. Names are compared without case,
  accents or dots: «Nº», «N°», «Orden» or «Número» for the order number; «Apellido y nombre», «Nombre», or «Apellido»
  and «Nombres» in two columns; «DNI», «Documento», «Nro. de documento» or «Tipo y número»; «Legajo»; «Carrera» or
  «Propuesta»; «Mesa»; «Domicilio»; «Calidad» or «Estado». It needs the name and something that tells people apart: the
  order number, the document or the student number. A column with another name is not read, even if it has data. A
  header on two lines, such as «Nro. de» over «documento», is read as one, and a long name may have one letter misread.
  A page without a header takes the header of another page of the same roll whose table has as many columns.
- **The faculty's rolls**, whether their header is recognised or not. If it finds no header it knows, it reads the
  table with the faculty's columns in their order (number, name, program, student number, document, status and
  signature). If it recognises it and it puts each column where the faculty has it, too. The output is the same as
  before, byte by byte, except when some page has a title such as «Mesa Nº 3» above it: then each row adds its table,
  and those of a page without a title are left for review (see Tables). A test compares it with a copy of the reading
  as it was. A page with a header of its own, the faculty's too, never takes another page's: one PDF may hold two
  lists laid out differently.
- **PDFs with text**, such as a listing exported from a spreadsheet or a system. It takes the text as it is, without
  recognising it: it gets no letter wrong, no row is left in doubt because of that, and it reads a page in a fraction of
  a second. It builds the rows by line and the columns by where the names of the header are, with or without ruling.
  The header may be on the first page only. A name that goes on onto a second line stays whole: a line without a
  number or a document goes with the row above or below it, whichever is closer; if both are nearly as close, the row
  is left for review. A line without numbers far from the rows, such as «Firma del presidente de mesa» at the foot, is
  not a person. A page the PDF turns, as a viewer saves it after turning it, is read upright.
- **What the PDF does not show is not used.** Invisible text that some scanners add over the picture, white text,
  text that is only a clipping path and text covered by a picture are not read. A page covered by a picture is a scan
  and is read from its picture, even with a stamp with text on it, such as «Copia fiel 05/11/2026»; its text is used
  only if it names the columns in a header of its own. One PDF can have pages of both kinds.
- **Tables (mesas).** With a «Mesa» column, or a title such as «Mesa Nº 12» above the table, each person stays at their
  table and the `.padron` file has one unit per table. A title applies to the whole page; in a PDF with text, a line
  saying only «Mesa 13» among the rows starts another table, and the table goes on onto the next page until the next
  such line. A scanned page without a title of its own does not take the table of the page before: a misread title
  cannot send anyone to another table. If the roll has tables, whoever is left without one is left for review.
- **Photos** in JPG, PNG or TIFF; a TIFF with several pages is read page by page. Each picture is brought to the size of
  an A4 page at 300 dpi, taking the page to fill the whole photo. In a phone photo it evens out the light and
  straightens up to 3 degrees, but it does not correct perspective: it works best with the page flat, well lit, without
  shadows, taken from straight above and filling the photo. A PNG with a transparent background is read on white
  paper. A picture may have up to 120 million pixels (a 108-megapixel photo, or a page scanned at 1000 dpi): the size
  is read from the first bytes of the file, before opening it, and a larger one is not opened.

In rolls other than the faculty's it also takes names without a comma («PRUEBA ANA»), the document type before the
number («DNI 99.123.456»), student numbers of other shapes (such as 12345 or 12345/6) and any word as a status. Student
numbers with the faculty's shape still go through their check digit. A row is left for review if a value does not have
its shape or the model was not sure when reading it; what comes from the text of a PDF, only for the first or because
it is not clear which row a line belongs to. In a roll with tables, also if the row was left without one.

**It does not read yet** handwriting, or tables without a header it recognises and without ruling: a list of names
without titles, or a scan without lines. Nor does the reader read with an external AI: with your own key it can be done
only from the terminal (see [With your own AI](#with-your-own-ai-from-the-terminal)), and the free service it will offer
has not been chosen yet. What the reader reads is read with the local model, and the `.padron` file says no external AI
saw the data.

## Without a terminal: the roll reader

The reader opens its screens in the browser and goes step by step, with one question per screen:

1. **Choose the roll:** drag the PDF or the photo of the roll into the window, or find it on your computer.
2. **Read it:** the computer reads page by page. It shows which page it is on, how many people it found and roughly how
   long is left. It can be cancelled.
3. **Review:** it shows the rows that were not clear one at a time, with the image of the row on top and its data below,
   to fix them or say they are fine. If the roll has tables or addresses, the table and the address are shown and fixed
   there too. The ones you do not review stay pending, to be reviewed later in the app.
4. **Save:** you get a `.padron` file. In Urna Abierta, go into the election and upload it with “Upload the roll”.

**It is private.** The file never leaves your computer, and the reader can only be opened from it, with the address it
shows when it starts. It keeps a copy of the file in a temporary folder only your user can open and deletes it when it
closes: with “Close the reader”, when its window is closed, or by itself after half an hour without use. If it is cut
off abruptly, it deletes it the next time it starts. It keeps nothing else. The `.padron` file has people's data: once it is uploaded to the app, delete it.

What it understands is in [What it reads](#what-it-reads). If the roll is in an Excel or CSV spreadsheet, you do not
need the reader: upload it straight into the app with “Upload the roll”.

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

- It speaks the language of the computer: Spanish if the system is in Spanish, English otherwise. `--idioma es` or
  `--idioma en` (also `--language`) sets it, for the messages and for `--help`. What it writes to its files does not
  change with the language.
- `extract` takes a PDF or a JPG, PNG or TIFF image. It saves the data with permissions for your user only, and refuses
  to write it inside a git repository. In a terminal it shows which page it is on. `--pages N` reads only the first N
  pages and `--workers N`, how many at a time. When it ends it says how many rows it read, how many pages had no table
  and, if there are any, how many it read from their text and how many tables it found. With `--ia` it reads with an
  external service (see below).
- `report`, `crosscheck` and `verify` print counts only, never data about a person. `report` compares with the
  numbering of the roll to warn if anyone is missing.
- `crosscheck` compares two rolls that share people. Since their reading errors are independent, it measures quality
  without anyone having to read the data.
- `verify` compares what was read with the same roll typed into a spreadsheet (`.xlsx` or `.csv`). From the spreadsheet
  it reads only the name, the document, the student number and the program; other columns are never opened. It says how
  many people match, how many differ, and whether the reader had marked the ones that differ as sure. It also checks the
  spreadsheet itself: repeated documents or documents of another length, and student numbers whose check digit does not
  add up. A person enrolled in more than one program appears once per program and does not count as a repeated
  document. A difference may be a reading error or a typo: `--filas` also lists the spreadsheet rows to look at and what
  to look at in each, without showing any data.

In the faculty's student numbers, the digit after the slash is a check digit (modulo 11, with weights 2 to 7 from the
right; 10 or 11 is written as 1). The reader flags a four-digit student number that does not match it: it is almost
always a misread digit.

## With your own AI (from the terminal)

Instead of the local model, `extract` can send the pages to an AI service, with a key of your own. It helps when the
local model reads a roll badly, but the roll leaves your computer: read this first.

- `--ia mistral` uses Mistral OCR, by Mistral AI, at its European address (`https://api.eu.mistral.ai`), with the model
  `mistral-ocr-latest` unless you name another with `--ia-modelo`. It returns each page as text with tables, and each
  table is read by the names in its header, like a scan.
- `--ia openai-compatible --ia-url <address> --ia-modelo <model>` uses any service that answers like OpenAI's chat API
  and takes images, such as OVHcloud AI Endpoints, Scaleway or OpenAI. The address is the base of the API, such as
  `https://api.example.com/v1`. It is asked for strict JSON, one object per person (order number, name, document,
  student number, program, status, table and address) and the list of the columns the page has, which is checked before
  it is used: a column on that list is checked on every row, even when it could not be read on any. An answer with
  people and without the list is not used. A model server on your own
  computer works too: it is the only one that may use `http://`; the others have to use `https://`.

The key goes in the variable `URNA_PADRONES_IA_CLAVE`, never as an argument, so that it does not stay in the terminal's
history. To type it without it being shown or saved, in bash or zsh:
`read -rs URNA_PADRONES_IA_CLAVE && export URNA_PADRONES_IA_CLAVE`; in fish: `read -sx URNA_PADRONES_IA_CLAVE`.
A key with a space, a line break or a letter outside the common ones, as happens when a two-line file is copied, is
refused before anything is sent, without showing it. If the service repeats the key when it refuses a request, the
message shows it covered.

```sh
uv run urna-padrones extract roll.pdf --out ~/private/roll.jsonl --ia mistral --acepto-enviar
```

Without `--acepto-enviar`, it shows a warning and sends nothing. Without `--ia`, nothing changes and nothing leaves your
computer.

**What is sent, and to whom.** The pictures of the scanned pages and of the photos go, one per request, straight from
your computer to the service, with your key: they go through no server of the project. Each picture is a JPEG made
again from the page: the PDF never goes, nor the pages that are not read (with `--pages N`, only the first N go), nor
what a photo carries besides the picture, such as where it was taken. The pages of a PDF with text are never sent: they
are read from their text, and when their text is not a list the program knows, such as a cover, they are read with the
local model, as without `--ia`. Those pictures hold the names and documents of the people, and the company behind the
service handles them under its terms, not this project's. The program follows no redirects: the key and the pages go
only to the address you chose. If your network uses a proxy (`https_proxy`), the request goes through it encrypted end
to end, because the proxy only joins the two ends; a server on your own computer is reached directly, without a proxy,
even when one is set. The service charges whatever it charges per page, under your plan.

**What to check in the service's terms**, before sending a roll: whether it uses what you send to train its models and
how to turn that off, how long it keeps it, in which country it processes and stores it, and whether your plan includes
a data processing agreement. It depends on the service and the plan, and it may change: the program does not check it.

**What comes back.** Every value goes through the same cleaning and review rules as what the local model reads: a row
is left for review if a value does not have its form. The service does not say how sure it is, so a row read by the AI
never counts as surer than that, and its order numbers are corrected by their neighbours like a scan's. A value with
characters a printed roll does not have, such as those that move the terminal's cursor or turn the text around, loses
those characters and leaves the row for review; one of more than 200 characters, the length the app takes for a name or
an address, is not used, and the row is left for review with that value blank. An answer of more than 4 MB, or with
more than 400 people or table lines on one page, is not a page of a roll, and is not used. Each request waits up to 120
seconds for the whole answer, even when it comes a little at a time, and is tried up to 3 times if the service is busy,
fails, does not answer or answers something other than what was asked. A refused key or a quota that ran out is said at
once. If a page cannot be read, `extract` stops, says why and writes nothing. With Ctrl+C, it stops waiting at once; a
request that has already gone cannot be taken back.

**The `.padron` file says so.** Each row of the extraction carries `external_ai` with the service and the model, and
`padron` writes `extraction.external_ai: true` and `extraction.provider` into the file (see the
[format](docs/padron-format.md)). Depending on the election's security level, the app may refuse a roll read this way.

**Not yet**: it is not in the reader's screens, and the free service the reader will offer has not been chosen yet. The
tests use a fake service on the same computer; it has not been tried with the real services yet.

## Tests

```sh
uv run pytest
```

They use made-up scans, PDFs with text and photos with invented people (`tests/fake_roll.py` and
`tests/fake_layouts.py`). **Never upload a real roll to the repository.**

On GitHub they run on Linux, Windows and macOS (`.github/workflows/tests.yml`). The ones in `tests/test_extract.py` ask
fontconfig for Liberation Sans and are skipped where it is missing, as on Windows and macOS; the others draw with Arial
if they cannot find it.

## How the reader is built

The files of each release are built by GitHub Actions (`.github/workflows/release.yml`) when a `v*` tag is pushed, each
one on a machine of the system it is for: Windows x64, macOS with an Apple chip, macOS with Intel and Linux x64 (Ubuntu
22.04). They are never built on a personal computer, so they carry nobody's paths or names. Each machine builds the
reader, runs its own check without network, makes sure nothing was downloaded and that onnxruntime's telemetry stayed
off, writes the file with its SHA-256 and its attestation, and uploads it to the release, which is published once all
four are there. Before the tag, the same workflow can be run by hand on `main`, from “Actions”, “Release”, “Run
workflow”: it builds and checks the four the same way, without creating or publishing any release.

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
- setuptools stays out too: it is on the build machine because PyInstaller needs it, but the reader does not use it. A
  test checks that the reader's code does not import it; of the libraries it carries, only two onnxruntime scripts that
  time Llama and Whisper name it, and the reader never runs them.
- The Windows and macOS icon is the mark of the reader's screens, in the colour of the «Aula» theme, on a transparent
  background. It is in `packaging/iconos/` and is made again with `uv run python tools/hacer-iconos.py`, which draws
  each size from the same SVG with rsvg-convert. Building the reader does not need rsvg-convert: the icons are already
  made.
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
