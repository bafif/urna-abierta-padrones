# Urna Abierta: escáner de padrones

[English](README.en.md)

Convierte padrones en cualquier formato al formato abierto que lee Urna Abierta.
Se puede usar solo, sin la app.

**Todo corre en tu computadora.** Un padrón trae nombres y documentos de personas, así que el reconocimiento de texto es
local por defecto, y ningún padrón pasa por una cuenta ni un servidor del proyecto.

## Estado

Primera etapa. Hoy lee padrones escaneados en forma de tabla y mide la calidad de lo que extrae; el formato común de
salida viene en la próxima etapa.

## Uso

Hace falta [uv](https://docs.astral.sh/uv/). La primera vez baja el modelo de lectura; después anda sin internet.

```sh
uv sync
uv run urna-padrones extract padron.pdf --out ~/privado/padron.jsonl
uv run urna-padrones report ~/privado/padron.jsonl
uv run urna-padrones crosscheck ~/privado/otro.jsonl ~/privado/padron.jsonl
```

- `extract` guarda los datos con permisos solo para tu usuario, y se niega a escribirlos dentro de un repo de git.
- `report` y `crosscheck` muestran solo cantidades, nunca datos de una persona. `report` compara con la numeración del
  padrón para avisar si falta alguien.
- `crosscheck` compara dos padrones que comparten gente. Como sus errores de lectura son independientes, sirve para medir
  la calidad sin que nadie tenga que leer los datos.

## Pruebas

```sh
uv run pytest
```

Usan escaneos fabricados con personas inventadas. **Nunca subas un padrón real al repo.**

## Licencia

[AGPL-3.0-or-later](LICENSE).
