# Pantallas del lector

[English](README.en.md)

`index.html`, `lector.js` y `lector.css` son propios del lector. Siguen el instalador de Urna Abierta
(`apps/installer/ui/` en el repo de la app): una pregunta por pantalla, el riel de pasos a la izquierda y el
mismo tema.

Estos archivos son copias de la app y no se editan acá:

- `tema.css`, `temas.js` y `aplicar-tema.js`, de `apps/web/src/lib/`;
- `fuentes/`: solo las letras del tema por defecto, «Aula», con su licencia.

Para traerlas de nuevo desde una copia de la app:

```sh
uv run python tools/traer-tema.py ../urna-abierta
```
