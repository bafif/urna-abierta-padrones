# Pantallas del lector / The reader's screens

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

---

`index.html`, `lector.js` and `lector.css` belong to the reader. They follow the Urna Abierta installer
(`apps/installer/ui/` in the app repository): one question per screen, the step rail on the left and the same
theme.

These files are copies from the app and are not edited here:

- `tema.css`, `temas.js` and `aplicar-tema.js`, from `apps/web/src/lib/`;
- `fuentes/`: only the fonts of the default theme, "Aula", with their license.

To bring them again from a checkout of the app:

```sh
uv run python tools/traer-tema.py ../urna-abierta
```
