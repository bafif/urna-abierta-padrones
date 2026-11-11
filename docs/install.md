# Installing the reader

[Español](instalar.md)

The reader comes ready to use for Windows, macOS and Linux: there is no need to install Python or anything else.
Download the file for your computer from the [latest release](../../../releases/latest):

| Your computer | File |
|---|---|
| Windows 10 or 11 | `urna-abierta-lector-windows-x64.zip` |
| Mac with an Apple chip (M1 or later), on macOS 14 or newer | `urna-abierta-lector-macos-arm64.zip` |
| Mac with an Intel processor, on macOS 14 or newer | `urna-abierta-lector-macos-x64.zip` |
| 64-bit Linux with glibc 2.28 or newer | `urna-abierta-lector-linux-x64.tar.gz` |
| Alpine Linux (and the other 64-bit Linux with musl) | `urna-abierta-lector-linux-x64-musl.tar.gz` |

On Linux, glibc 2.28 means Debian 10, Fedora 29, Arch, Ubuntu 20.04 or newer.

To know which Mac you have: Apple menu → "About This Mac". If it says "Chip" and a name like "Apple M1", it has an
Apple chip; if it says "Processor" and a name with "Intel", it is the other one.

The program is not signed with a paid certificate, so the first time Windows and macOS warn that they do not know it.
Before opening it, it is worth [checking the file](#check-the-file).

## On Windows

1. Right-click the `.zip` and choose "Extract All". Do not open it from inside the zip.
2. In the folder you get, double-click `urna-abierta-lector.exe`.
3. If "Windows protected your PC" appears, click "More info" and then "Run anyway".
4. A black window opens with the reader's address, and the browser opens at that address by itself. Keep the window
   open while you use it: closing it closes the reader.

If instead of the reader you get a message saying the reading engine could not be loaded, install the latest
[Microsoft Visual C++ (x64)](https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist) and open it again.

## On macOS

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

## On Linux

1. Unpack the file: `tar -xzf urna-abierta-lector-linux-x64.tar.gz`.
2. Start it from a terminal: `./urna-abierta-lector-linux-x64/urna-abierta-lector`. It shows the address and opens the
   browser. It closes when you close the terminal, with Ctrl+C or with "Close the reader".

On Alpine, the file and the folder end in `-musl`: `urna-abierta-lector-linux-x64-musl/urna-abierta-lector`.

## Check the file

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

## From a copy of the repository

If the [releases page](../../../releases) has no release yet, the reader opens from a terminal. With
[uv](https://docs.astral.sh/uv/) installed, in a copy of this repository (on GitHub, "Code" → "Download ZIP"):

```sh
uv run python -m urna_padrones.lector
```

`--no-browser` does not open the browser, `--port` picks the port (otherwise a free one at random) and `--self-test`
checks, offline, that the reader works.
