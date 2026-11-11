# Cómo se usa

[English](usage.md)

El escáner se usa de dos formas: con el lector, que abre sus pantallas en el navegador y no pide terminal, o con el
comando `urna-padrones`, que además mide la calidad de lo leído. Qué padrones entiende está en [Qué lee](que-lee.md).

## El lector

El lector lleva paso a paso, con una pregunta por pantalla. Arranca en el idioma del navegador, castellano o inglés, y
se puede cambiar en cualquier pantalla.

1. **Elegir el padrón:** arrastrás el PDF o la foto del padrón a la ventana, o lo buscás en la computadora.
2. **Leerlo:** la computadora lee página por página. Muestra por qué página va, cuántas personas encontró y cuánto
   falta, más o menos. Se puede cancelar.
3. **Revisar:** muestra una por una las filas que no quedaron claras, con la imagen de la fila arriba y sus datos abajo,
   para corregirlos o decir que están bien. Si el padrón tiene mesas o domicilios, la mesa y el domicilio también se
   muestran y se corrigen ahí. Las que no revises quedan pendientes y se revisan después en la app.
4. **Guardar:** queda un archivo `.padron`. En Urna Abierta, entrás a la elección y lo subís con «Subir el padrón».

**Es privado.** El archivo no sale de tu computadora, y el lector solo se puede abrir desde ella, con la dirección que
muestra al arrancar. Guarda una copia del archivo en una carpeta temporal que solo tu usuario puede abrir y la borra al
cerrarse: con «Cerrar el lector», al cerrar su ventana, o solo, después de media hora sin usarlo. Si se corta de golpe,
la borra la próxima vez que arranca. No guarda nada más. El archivo `.padron` tiene datos de personas: una vez subido a
la app, borralo.

El lector siempre lee con el modelo local: el archivo `.padron` que arma dice que ninguna IA externa vio los datos.

Si el padrón está en una planilla de Excel o CSV, no hace falta el lector: se sube directo en la app, con «Subir el
padrón».

## Desde la terminal

Hace falta [uv](https://docs.astral.sh/uv/) y una copia de este repo. El modelo de lectura viene con el programa, así
que anda sin internet desde la primera vez y nunca baja nada.

```sh
uv sync
uv run urna-padrones extract padron.pdf --out ~/privado/padron.jsonl
uv run urna-padrones report ~/privado/padron.jsonl
uv run urna-padrones padron ~/privado/padron.jsonl --out ~/privado/mi-padron.padron
uv run urna-padrones crosscheck ~/privado/otro.jsonl ~/privado/padron.jsonl
uv run urna-padrones verify ~/privado/padron.jsonl ~/privado/planilla.xlsx --filas
```

- `extract` lee un PDF o una imagen JPG, PNG o TIFF. Guarda los datos con permisos solo para tu usuario, y se niega a
  escribirlos dentro de un repo de git. En una terminal muestra por qué página va. `--pages N` lee solo las primeras N
  páginas y `--workers N`, cuántas a la vez. Al terminar dice cuántas filas leyó, cuántas páginas no tenían tabla y, si
  las hay, cuántas leyó de su texto y cuántas mesas encontró. Con `--ia` lee con un servicio externo: ver
  [Con tu propia IA](ia-propia.md).
- `padron` arma el archivo `.padron` que se sube a Urna Abierta.
- `report`, `crosscheck` y `verify` muestran solo cantidades, nunca datos de una persona.
- `report` compara con la numeración del padrón para avisar si falta alguien.
- `crosscheck` compara dos padrones que comparten gente. Como sus errores de lectura son independientes, mide la calidad
  sin que nadie tenga que leer los datos.
- `verify` compara lo leído con el mismo padrón tipeado en una planilla (`.xlsx` o `.csv`). De la planilla lee solo el
  nombre, el documento, el legajo y la carrera; las demás columnas no se abren. Dice cuántas personas coinciden, cuántas
  difieren y si las que difieren el lector las había dado por seguras. También revisa la planilla misma: DNI repetidos o
  con otro largo, y legajos cuyo dígito verificador no corresponde. Una persona anotada en más de una carrera aparece
  una vez por carrera y no cuenta como DNI repetido. Una diferencia puede ser un error de lectura o de tipeo: con
  `--filas` lista, además, las filas de la planilla para mirar y qué mirar en cada una, sin mostrar ningún dato.

Habla en el idioma de la computadora: castellano si el sistema está en castellano, inglés si no. `--idioma es` o
`--idioma en` (también `--language`) lo fija, para los mensajes y para `--help`. Lo que escribe en los archivos no
cambia con el idioma.

Para usar otro modelo de lectura, `URNA_PADRONES_MODELO` puede apuntar a un archivo ONNX de reconocimiento que traiga
su propia lista de caracteres.
