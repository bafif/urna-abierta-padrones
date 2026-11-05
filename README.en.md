# Urna Abierta: voter roll scanner

[Español](README.md)

Turns voter rolls in any format into the open format read by
Urna Abierta. It can be used on its own, without the app.

**Everything runs on your computer.** A roll holds names and identity documents of real people, so text recognition is
local by default, and no roll ever goes through an account or a server of the project.

## Status

First stage. Today it reads scanned rolls laid out as tables and measures the quality of what it extracts; the common
output format comes in the next stage.

## Usage

You need [uv](https://docs.astral.sh/uv/). The first run downloads the reading model; after that it works offline.

```sh
uv sync
uv run urna-padrones extract roll.pdf --out ~/private/roll.jsonl
uv run urna-padrones report ~/private/roll.jsonl
uv run urna-padrones crosscheck ~/private/other.jsonl ~/private/roll.jsonl
```

- `extract` saves the data with permissions for your user only, and refuses to write it inside a git repository.
- `report` and `crosscheck` print counts only, never data about a person. `report` compares with the numbering of the
  roll to warn if anyone is missing.
- `crosscheck` compares two rolls that share people. Since their reading errors are independent, it measures quality
  without anyone having to read the data.

## Tests

```sh
uv run pytest
```

They use made-up scans with invented people. **Never upload a real roll to the repository.**

## License

[AGPL-3.0-or-later](LICENSE).
