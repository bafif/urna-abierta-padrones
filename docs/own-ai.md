# With your own AI

[Español](ia-propia.md)

Instead of the local model, `urna-padrones extract` can send the pages to an AI service, with a key of your own. It
helps when the local model reads a roll badly, but the roll leaves your computer: read this first. It is done only
from the terminal; the reader always reads with the local model.

## Services

- `--ia mistral` uses Mistral OCR, by Mistral AI, at its European address (`https://api.eu.mistral.ai`), with the model
  `mistral-ocr-latest` unless you name another with `--ia-modelo`. It returns each page as text with tables, and each
  table is read by the names in its header, like a scan.
- `--ia openai-compatible --ia-url <address> --ia-modelo <model>` uses any service that answers like OpenAI's chat API
  and takes images, such as OVHcloud AI Endpoints, Scaleway or OpenAI. The address is the base of the API, such as
  `https://api.example.com/v1`. It is asked for strict JSON, with one object per person and the list of the columns the
  page has, which is checked before it is used: each column on that list is checked on every row, even when it could
  not be read on any. An answer with people and without that list is not used.
- A model server on your own computer works too: it is the only one that may use `http://`; the others have to use
  `https://`.

## The key

The key goes in the variable `URNA_PADRONES_IA_CLAVE`, never as an argument, so that it does not stay in the terminal's
history. To type it without it being shown or saved, in bash or zsh:
`read -rs URNA_PADRONES_IA_CLAVE && export URNA_PADRONES_IA_CLAVE`; in fish: `read -sx URNA_PADRONES_IA_CLAVE`.

A key with a space, a line break or a letter outside the common ones is refused before anything is sent, without
showing it. If the service repeats the key when it refuses a request, the message shows it covered.

```sh
uv run urna-padrones extract roll.pdf --out ~/private/roll.jsonl --ia mistral --acepto-enviar
```

Without `--acepto-enviar`, it shows a warning and sends nothing. Without `--ia`, nothing changes and nothing leaves your
computer.

## What is sent, and to whom

- The pictures of the scanned pages and of the photos go, one per request, straight from your computer to the service,
  with your key: they go through no server of the project.
- Each picture is a JPEG made again from the page: the PDF never goes, nor the pages that are not read (with
  `--pages N`, only the first N go), nor what a photo carries besides the picture, such as where it was taken.
- The pages of a PDF with text are never sent: they are read from their text, and when their text is not a list the
  program knows, such as a cover, they are read with the local model.
- The program follows no redirects: the key and the pages go only to the address you chose. If your network uses a
  proxy (`https_proxy`), the request goes through it encrypted end to end; a server on your own computer is reached
  directly, without a proxy.

Those pictures hold the names and documents of the people, and the company behind the service handles them under its
terms, not this project's. The service charges whatever it charges per page, under your plan.

**What to check in the service's terms**, before sending a roll: whether it uses what you send to train its models and
how to turn that off, how long it keeps it, in which country it processes and stores it, and whether your plan includes
a data processing agreement. It depends on the service and the plan, and it may change: the program does not check it.

## What comes back

- Every value goes through the same cleaning and review rules as what the local model reads: a row is left for review
  if a value does not have its shape. The service does not say how sure it is, so its order numbers are corrected by
  their neighbours, like a scan's.
- A value with characters a printed roll does not have, such as those that move the terminal's cursor, loses those
  characters and leaves the row for review. One of more than 200 characters, the length the app takes for a name or an
  address, is not used, and the row is left for review with that value blank.
- An answer of more than 4 MB, or with more than 400 people or table lines on one page, is not a page of a roll and is
  not used.
- Each request waits up to 120 seconds for the whole answer and is tried up to 3 times if the service is busy, fails,
  does not answer or answers something other than what was asked. A refused key or a quota that ran out is said at
  once.
- If a page cannot be read, `extract` stops, says why and writes nothing. With Ctrl+C, it stops waiting at once; a
  request that has already gone cannot be taken back.

## The `.padron` file says so

Each row of the extraction carries `external_ai` with the service and the model, and `padron` writes
`extraction.external_ai: true` and `extraction.provider` into the file (see the [format](padron-format.md)). Depending
on the election's security level, the app may refuse a roll read this way.

## Status

The tests use a fake service on the same computer; it has not been tried with the real services yet. It is not in the
reader's screens yet.
