# Usage

[Español](uso.md)

The scanner is used in two ways: with the reader, which opens its screens in the browser and needs no terminal, or
with the `urna-padrones` command, which also measures the quality of what was read. Which rolls it understands is in
[What it reads](what-it-reads.md).

## The reader

The reader goes step by step, with one question per screen. It opens in the browser's language, Spanish or English,
and the language can be changed on any screen.

1. **Choose the roll:** drag the PDF or the photo of the roll into the window, or find it on your computer.
2. **Read it:** the computer reads page by page. It shows which page it is on, how many people it found and roughly how
   long is left. It can be cancelled.
3. **Review:** it shows the rows that were not clear one at a time, with the image of the row on top and its data below,
   to fix them or say they are fine. If the roll has polling tables or addresses, the table and the address are shown
   and fixed there too. The ones you do not review stay pending, to be reviewed later in the app.
4. **Save:** you get a `.padron` file. In Urna Abierta, go into the election and upload it with “Upload the roll”.

**It is private.** The file never leaves your computer, and the reader can only be opened from it, with the address it
shows when it starts. It keeps a copy of the file in a temporary folder only your user can open and deletes it when it
closes: with “Close the reader”, when its window is closed, or by itself after half an hour without use. If it is cut
off abruptly, it deletes it the next time it starts. It keeps nothing else. The `.padron` file holds people's data:
once it is uploaded to the app, delete it.

The reader always reads with the local model: the `.padron` file it builds says no external AI saw the data.

If the roll is in an Excel or CSV spreadsheet, you do not need the reader: upload it straight into the app with
“Upload the roll”.

## From the terminal

You need [uv](https://docs.astral.sh/uv/) and a copy of this repository. The reading model ships with the program, so
it works offline from the first run and never downloads anything.

```sh
uv sync
uv run urna-padrones extract roll.pdf --out ~/private/roll.jsonl
uv run urna-padrones report ~/private/roll.jsonl
uv run urna-padrones padron ~/private/roll.jsonl --out ~/private/my-roll.padron
uv run urna-padrones crosscheck ~/private/other.jsonl ~/private/roll.jsonl
uv run urna-padrones verify ~/private/roll.jsonl ~/private/spreadsheet.xlsx --filas
```

- `extract` reads a PDF or a JPG, PNG or TIFF image. It saves the data with permissions for your user only, and refuses
  to write it inside a git repository. In a terminal it shows which page it is on. `--pages N` reads only the first N
  pages and `--workers N`, how many at a time. When it ends it says how many rows it read, how many pages had no table
  and, if there are any, how many it read from their text and how many polling tables it found. With `--ia` it reads
  with an external service: see [With your own AI](own-ai.md).
- `padron` builds the `.padron` file that is uploaded to Urna Abierta.
- `report`, `crosscheck` and `verify` print counts only, never data about a person.
- `report` compares with the numbering of the roll to warn if anyone is missing.
- `crosscheck` compares two rolls that share people. Since their reading errors are independent, it measures quality
  without anyone having to read the data.
- `verify` compares what was read with the same roll typed into a spreadsheet (`.xlsx` or `.csv`). From the spreadsheet
  it reads only the name, the document, the student number and the program; other columns are never opened. It says how
  many people match, how many differ, and whether the reader had marked the ones that differ as sure. It also checks the
  spreadsheet itself: repeated documents or documents of another length, and student numbers whose check digit does not
  add up. A person enrolled in more than one program appears once per program and does not count as a repeated
  document. A difference may be a reading error or a typo: `--filas` also lists the spreadsheet rows to look at and what
  to look at in each, without showing any data.

It speaks the language of the computer: Spanish if the system is in Spanish, English otherwise. `--idioma es` or
`--idioma en` (also `--language`) sets it, for the messages and for `--help`. What it writes to its files does not
change with the language.

To use another reading model, `URNA_PADRONES_MODELO` can point to an ONNX recognition model that carries its own
character list.
