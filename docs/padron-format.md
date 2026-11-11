# Open roll format

[Español](formato-padron.md)

Version 0.1. This specification is released under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/):
anyone can implement it, with no permission and no attribution. The program that writes it is still AGPL.

A roll is a ZIP file with the `.padron` extension. It holds people's data: treat it as such.

## Files

| File | What it holds |
|---|---|
| `manifest.json` | What the file is and how many rows it has |
| `electors.jsonl` | One person per line, as JSON |
| `units.jsonl` | Optional: tables, schools or districts, one per line |

## `manifest.json`

```json
{
  "format": "padron-abierto",
  "format_version": "0.1.0",
  "title": "Student union 2027",
  "created_at": "2026-11-05T12:00:00+00:00",
  "extraction": { "tool": "urna-padrones", "external_ai": false },
  "levels": ["mesa"],
  "extra_fields": [{ "key": "program", "label": "Program" }],
  "files": {
    "electors": { "path": "electors.jsonl", "count": 3120 },
    "units": { "path": "units.jsonl", "count": 9 }
  }
}
```

- A reader refuses a file with another major version, and accepts fields it does not know.
- `count` has to match the rows: that is how a truncated file gets noticed.
- `extraction.external_ai` says whether an external AI saw the data. An election may not allow it.
- `extraction.provider` is optional: when `external_ai` is `true`, which service saw the data, such as
  `"api.eu.mistral.ai (mistral-ocr-latest)"`. It is text to show a person, without a fixed form. When it is missing,
  which one is not known.

## A person

```json
{
  "id": "d-99000001",
  "full_name": "Prueba, Ana",
  "family_name": "Prueba",
  "given_names": "Ana",
  "table": "mesa-12",
  "order": 24,
  "identifiers": [{ "type": "DNI", "value": "99000001" }],
  "address": null,
  "birth_year": null,
  "extra": { "program": "Civil" },
  "review": { "status": "pending" }
}
```

Only `id` and `full_name` are required.

- **`id`** has to stay the same if the roll is generated again, so that a correction loses nothing already marked. The
  recommended form is `d-<document>` and, with no document, `l-<student number>` or `f-<row>`.
- **`table`** is the `id` of a unit: if the file has `units.jsonl`, it has to be there. If missing, the app proposes
  tables.
- **`order`** is the number in the printed roll, starting at 1.
- **`review.status`** is `pending` if something stayed in doubt. A doubtful row gets marked and shown for review.
  **It is never dropped.**

## A unit

```json
{ "id": "mesa-12", "level": "mesa", "name": "Mesa 12", "parent": null, "declared_total": 350 }
```

Only `id` and `name` are required. `declared_total` is how many people the printed roll says the unit has, if it says
so.

## Compatibility

A minor version only adds optional fields. Any other change is a major version.
