# Urna Abierta: voter roll scanner

**Turns a voter roll in PDF or in a photo into the open format Urna Abierta reads, without it leaving your
computer.**<br>
[Español](README.md) · [Download](#download) · [Usage](docs/usage.md)

Drag the PDF or the photo of a roll into the reader. It reads it page by page, shows you the rows that were not clear
so you can fix them, and leaves you a `.padron` file to upload to Urna Abierta. It also works on its own, without the
app, through screens in the browser or from the terminal.

## Why

- **The roll stays on your computer.** Text recognition runs locally, with a model that ships inside the program: it
  works offline and never downloads anything. No roll goes through an account or a server of the project. Only if you
  ask for it from the terminal, with your own key, is it read by an external AI service.
- **It reads the table by its header.** It finds each column by its name («DNI», «Apellido y nombre», «Mesa»…), in any
  order, in scanned PDFs, PDFs with text and photos.
- **Nothing doubtful is dropped.** A row with a value that does not have its shape, or that the model was not sure
  of, is left for review: the reader shows it with the image of the row above its data.
- **Everyone at their polling table.** A «Mesa» column or a title such as «Mesa Nº 12» splits the roll, and the file
  has one unit per table.
- **It measures quality without showing data.** From the terminal it compares what it read with the roll's numbering,
  with another roll or with a typed spreadsheet, and prints counts only.
- **An open format.** The `.padron` file follows a public-domain [specification](docs/padron-format.md) anyone can
  implement.

## Download

The reader comes ready for each system: there is no need to install Python or anything else. Download yours from the
[latest release](../../releases/latest):

| Your computer | File |
|---|---|
| Windows 10 or 11 | `urna-abierta-lector-windows-x64.zip` |
| Mac with an Apple chip (M1 or later), on macOS 14 or newer | `urna-abierta-lector-macos-arm64.zip` |
| Mac with an Intel processor, on macOS 14 or newer | `urna-abierta-lector-macos-x64.zip` |
| 64-bit Linux with glibc 2.28 or newer | `urna-abierta-lector-linux-x64.tar.gz` |
| Alpine Linux (and the other 64-bit Linux with musl) | `urna-abierta-lector-linux-x64-musl.tar.gz` |

The program is not signed with a paid certificate: the first time, Windows and macOS warn that they do not know it.
How to open it on each system, and how to check that the file is the one GitHub built, is in
[Install](docs/install.md).

## Usage

1. **Open the reader.** It opens in your browser, at an address that only works from your computer.
2. **Choose the roll:** drag the PDF or the photo into the window. It is read page by page, and it can be cancelled.
3. **Review** the rows that were not clear: fix them or confirm them. The ones you do not review stay pending for the
   app.
4. **Save the `.padron` file** and, in Urna Abierta, upload it with “Upload the roll”. Once it is uploaded, delete it:
   it holds people's data.

If the roll is already in an Excel or CSV spreadsheet, you do not need the reader: upload it straight into the app.
The terminal commands are in [Usage](docs/usage.md#from-the-terminal).

## Status

- **It reads** rolls laid out as tables, in scanned PDFs, PDFs with text and JPG, PNG or TIFF photos, with polling
  tables and addresses. It does not read handwriting yet, nor tables without ruling and without a header it knows.
- **The reader** is built and checked offline on GitHub's machines, for Windows, macOS, Linux and Alpine. It has not
  been tried yet on computers running Windows or macOS.
- **With your own AI**, a roll can be read only from the terminal, and this has only been tried against a fake
  service. The reader does not offer a free AI service yet.

## More documentation

- [Install](docs/install.md): each system in detail, checking the download and opening the reader from a copy of the
  repository.
- [Usage](docs/usage.md): the reader step by step and the terminal commands.
- [What it reads](docs/what-it-reads.md): which tables, PDFs, photos and polling tables it understands, and when a row
  is left for review.
- [With your own AI](docs/own-ai.md): what is sent, to whom, and what to check before sending a roll.
- [Open roll format](docs/padron-format.md): the specification of the `.padron` file.
- [How it is made](docs/development.md): the tests and how the reader is built.

## License

[AGPL-3.0-or-later](LICENSE). The format specification is in the public domain ([CC0 1.0](docs/padron-format.md)).
