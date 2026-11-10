# The reader's screens

[Español](README.md)

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
