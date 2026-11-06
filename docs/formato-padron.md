# Formato abierto de padrón

[English](padron-format.md)

Versión 0.1. Esta especificación se publica bajo [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/deed.es): cualquiera la
puede implementar, sin pedir permiso y sin citar a nadie. El programa que la escribe sigue siendo AGPL.

Un padrón es un archivo ZIP, con extensión `.padron`. Trae datos de personas: tratalo como tal.

## Archivos

| Archivo | Qué tiene |
|---|---|
| `manifest.json` | Qué es el archivo y cuántas filas trae |
| `electors.jsonl` | Una persona por renglón, en JSON |
| `units.jsonl` | Opcional: mesas, escuelas o distritos, uno por renglón |

## `manifest.json`

```json
{
  "format": "padron-abierto",
  "format_version": "0.1.0",
  "title": "Centro de estudiantes 2027",
  "created_at": "2026-11-05T12:00:00+00:00",
  "extraction": { "tool": "urna-padrones", "external_ai": false },
  "levels": ["mesa"],
  "extra_fields": [{ "key": "program", "label": "Carrera" }],
  "files": {
    "electors": { "path": "electors.jsonl", "count": 3120 },
    "units": { "path": "units.jsonl", "count": 9 }
  }
}
```

- Un lector rechaza un archivo con otra versión mayor, y acepta campos que no conoce.
- `count` tiene que coincidir con las filas: así se nota un archivo cortado.
- `extraction.external_ai` dice si una IA externa vio los datos. Una elección puede no permitirlo.
- `extraction.provider` es opcional: cuando `external_ai` es `true`, qué servicio vio los datos, como
  `"api.eu.mistral.ai (mistral-ocr-latest)"`. Es un texto para mostrar a una persona, sin una forma fija. Si falta,
  no se sabe cuál.

## Una persona

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

Solo `id` y `full_name` son obligatorios.

- **`id`** tiene que ser el mismo si el padrón se vuelve a generar, para que una corrección no pierda lo ya marcado. Se recomienda
  `d-<documento>` y, sin documento, `l-<legajo>` o `f-<fila>`.
- **`table`** es el `id` de una unidad: si el archivo trae `units.jsonl`, tiene que estar ahí. Si falta, la app propone las mesas.
- **`order`** es el número en el padrón impreso, empezando en 1.
- **`review.status`** vale `pending` si algo quedó en duda. Una fila dudosa se marca y se muestra para revisar. **Nunca se descarta.**

## Una unidad

```json
{ "id": "mesa-12", "level": "mesa", "name": "Mesa 12", "parent": null, "declared_total": 350 }
```

Solo `id` y `name` son obligatorios. `declared_total` es cuántas personas dice el padrón impreso que tiene la unidad, si lo dice.

## Compatibilidad

Una versión menor solo agrega campos opcionales. Cualquier otro cambio es una versión mayor.
