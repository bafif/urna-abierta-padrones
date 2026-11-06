# Urna Abierta: escáner de padrones

[English](README.en.md)

Convierte padrones en cualquier formato al formato abierto que lee Urna Abierta.
Se puede usar solo, sin la app.

**Todo corre en tu computadora.** Un padrón trae nombres y documentos de personas, así que el reconocimiento de texto es
local por defecto, y ningún padrón pasa por una cuenta ni un servidor del proyecto.

## Estado

Lee padrones escaneados en forma de tabla, mide la calidad de lo que extrae y arma el archivo `.padron` que se sube a Urna
Abierta. El archivo sigue un [formato abierto](docs/formato-padron.md), de dominio público. Se usa con pantallas en el
navegador, sin terminal, o desde una terminal.

## Sin terminal: el lector de padrones

El lector abre sus pantallas en el navegador y lleva paso a paso, con una pregunta por pantalla:

1. **Elegir el padrón:** arrastrás el PDF escaneado a la ventana, o lo buscás en la computadora.
2. **Leerlo:** la computadora lee página por página. Muestra por qué página va, cuántas personas encontró y cuánto
   falta, más o menos. Se puede cancelar.
3. **Revisar:** muestra una por una las filas que no quedaron claras, con la imagen de la fila arriba y sus datos abajo,
   para corregirlos o decir que están bien. Las que no revises quedan pendientes y se revisan después en la app.
4. **Guardar:** queda un archivo `.padron`. En Urna Abierta, entrás a la elección y lo subís con «Subir el padrón».

**Es privado.** El PDF no sale de tu computadora, y el lector solo se puede abrir desde ella, con la dirección que
muestra al arrancar. Guarda una copia del PDF en una carpeta temporal que solo tu usuario puede abrir y la borra al
cerrarse: con «Cerrar el lector», al cerrar su ventana, o solo, después de media hora sin usarlo. Si se corta de golpe,
la borra la próxima vez que arranca. No guarda nada más.
El archivo `.padron` tiene datos de personas: una vez subido a la app, conviene borrarlo.

Por ahora entiende padrones hechos como una tabla con líneas. Si el padrón está en una planilla de Excel o CSV, no
hace falta el lector: se sube directo en la app, con «Subir el padrón».

Desde una copia de este repo se abre así:

```sh
uv run python -m urna_padrones.lector
```

`--no-browser` no abre el navegador, `--port` elige el puerto (si no, uno libre al azar) y `--self-test` comprueba sin
internet que el lector funciona.

## Descargar

El lector viene armado para Windows, macOS y Linux, listo para usar: no hace falta instalar Python ni nada más. Bajá el
archivo de tu computadora de la [última versión](../../releases/latest):

| Tu computadora | Archivo |
|---|---|
| Windows 10 u 11 | `urna-abierta-lector-windows-x64.zip` |
| Mac con chip Apple (M1 o posterior), con macOS 14 o más nuevo | `urna-abierta-lector-macos-arm64.zip` |
| Mac con procesador Intel, con macOS 14 o más nuevo | `urna-abierta-lector-macos-x64.zip` |
| Linux de 64 bits con glibc 2.28 o más nueva (Ubuntu 20.04, Debian 10, Fedora 29 o más nuevos) | `urna-abierta-lector-linux-x64.tar.gz` |

Si la [página de versiones](../../releases) todavía no tiene ninguna, abrí el lector desde una terminal: con
[uv](https://docs.astral.sh/uv/) instalado, en una copia de este repo (en GitHub, «Code» → «Download ZIP»), corré
`uv run python -m urna_padrones.lector`. Más detalles en
[Sin terminal: el lector de padrones](#sin-terminal-el-lector-de-padrones).

Para saber qué Mac tenés: menú Apple → «Acerca de esta Mac». Si dice «Chip» y un nombre como «Apple M1», es la de chip
Apple; si dice «Procesador» y un nombre con «Intel», es la otra.

El programa no está firmado con un certificado pago, así que la primera vez Windows y macOS avisan que no lo conocen.
Antes de abrirlo, conviene [comprobar el archivo](#comprobar-el-archivo).

### En Windows

1. Hacé clic derecho en el `.zip` y elegí «Extraer todo». No lo abras desde adentro del zip.
2. En la carpeta que queda, hacé doble clic en `urna-abierta-lector.exe`.
3. Si aparece «Windows protegió su PC», hacé clic en «Más información» y después en «Ejecutar de todas formas».
4. Se abre una ventana negra con la dirección del lector, y el navegador se abre solo en esa dirección. Dejá la ventana
   abierta mientras lo usás: al cerrarla, se cierra el lector.

Si en vez del lector aparece un aviso de que no se pudo cargar el motor de lectura, instalá la versión más nueva de
[Microsoft Visual C++ (x64)](https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist) y abrilo de nuevo.

### En macOS

1. Hacé doble clic en el `.zip`: queda `Urna Abierta Lector.app`. Si querés, movela a Aplicaciones.
2. Hacé doble clic en la app. macOS avisa que no puede comprobar que esté libre de software malicioso: cerrá el aviso sin
   mandarla a la papelera.
3. Abrí Configuración del Sistema → Privacidad y seguridad, bajá hasta «Seguridad» y, al lado del aviso sobre
   «Urna Abierta Lector», hacé clic en «Abrir igualmente». Confirmá con tu contraseña y elegí «Abrir».
4. Eso se hace una sola vez. El lector se abre en el navegador y no tiene ventana propia ni ícono en el Dock. Se cierra
   con «Cerrar el lector», o solo, media hora después de cerrar la pestaña.

Si cerraste la pestaña sin querer, volvé a abrirla desde el historial del navegador: mientras el lector sigue abierto,
abrir la app de nuevo no abre otra pestaña. Lo que el lector escribe, con su dirección, queda en
`~/Library/Logs/Urna Abierta/lector.log`.

### En Linux

1. Descomprimí el archivo: `tar -xzf urna-abierta-lector-linux-x64.tar.gz`.
2. Abrilo desde una terminal: `./urna-abierta-lector-linux-x64/urna-abierta-lector`. Muestra la dirección y abre el
   navegador. Se cierra al cerrar la terminal, con Ctrl+C o con «Cerrar el lector».

### Comprobar el archivo

Al lado de cada archivo de la versión hay otro con el mismo nombre terminado en `.sha256`, con su huella SHA-256.
Calculá la huella del archivo que bajaste y fijate que sea la misma:

- En Windows, en PowerShell: `Get-FileHash .\urna-abierta-lector-windows-x64.zip`, y comparala con el texto del
  `.sha256` (Windows la muestra en mayúsculas: da igual).
- En macOS, con los dos archivos en la misma carpeta: `shasum -a 256 -c urna-abierta-lector-macos-arm64.zip.sha256`.
  Si coincide, dice `OK`.
- En Linux, también con los dos en la misma carpeta: `sha256sum -c urna-abierta-lector-linux-x64.tar.gz.sha256`.

Cada archivo tiene además una constancia de GitHub de que se armó en sus máquinas a partir del código de este
repositorio. Se verifica con la [CLI de GitHub](https://cli.github.com):
`gh attestation verify <archivo> --repo <dueño>/urna-abierta-padrones`, con el dueño que aparece en la dirección de
este repositorio.

## Uso

Hace falta [uv](https://docs.astral.sh/uv/). El modelo de lectura viene con el programa, así que anda sin internet desde
la primera vez y nunca baja nada. Para usar otro modelo, `URNA_PADRONES_MODELO` puede apuntar a un archivo ONNX de
reconocimiento que traiga su propia lista de caracteres.

```sh
uv sync
uv run urna-padrones extract padron.pdf --out ~/privado/padron.jsonl
uv run urna-padrones report ~/privado/padron.jsonl
uv run urna-padrones padron ~/privado/padron.jsonl --out ~/privado/mi-padron.padron
uv run urna-padrones crosscheck ~/privado/otro.jsonl ~/privado/padron.jsonl
uv run urna-padrones verify ~/privado/padron.jsonl ~/privado/planilla.xlsx --filas
```

- `extract` guarda los datos con permisos solo para tu usuario, y se niega a escribirlos dentro de un repo de git. En una
  terminal muestra por qué página va. `--pages N` lee solo las primeras N páginas y `--workers N`, cuántas a la vez.
- `report`, `crosscheck` y `verify` muestran solo cantidades, nunca datos de una persona. `report` compara con la
  numeración del padrón para avisar si falta alguien.
- `crosscheck` compara dos padrones que comparten gente. Como sus errores de lectura son independientes, sirve para medir
  la calidad sin que nadie tenga que leer los datos.
- `verify` compara lo leído con el mismo padrón tipeado en una planilla (`.xlsx` o `.csv`). De la planilla lee solo el
  nombre, el documento y el legajo; las demás columnas no se abren. Dice cuántas personas coinciden, cuántas difieren y
  si las que difieren el lector las había dado por seguras. También revisa la planilla misma: DNI repetidos o con otro
  largo, y legajos cuyo dígito verificador no corresponde. Una diferencia puede ser un error de lectura o de tipeo: con
  `--filas` lista, además, las filas de la planilla para mirar y qué mirar en cada una, sin mostrar ningún dato.

En los legajos de la facultad, el número después de la barra es un dígito verificador (módulo 11, con pesos de 2 a 7
desde la derecha; si da 10 u 11 se escribe 1). El lector marca para revisar un legajo de cuatro números que no lo
cumple: casi siempre es un número mal leído.

## Pruebas

```sh
uv run pytest
```

Usan escaneos fabricados con personas inventadas. **Nunca subas un padrón real al repo.**

## Cómo se arma el lector

Los archivos de cada versión los arma GitHub Actions (`.github/workflows/release.yml`) cuando se sube una etiqueta `v*`,
cada uno en una máquina del sistema para el que es: Windows x64, macOS con chip Apple, macOS con Intel y Linux x64
(Ubuntu 22.04). Nunca se arman en una computadora personal, para que no lleven rutas ni nombres de nadie. Cada máquina
arma el lector, corre su prueba propia sin red, comprueba que no se bajó nada y que la telemetría de onnxruntime quedó
apagada, escribe el archivo con su SHA-256 y su constancia, y lo sube a la versión, que se publica cuando están los
cuatro.

Para armarlo para tu sistema, en tu computadora:

```sh
uv sync --managed-python --no-editable --group build
uv run --no-sync python packaging/build.py --self-test --start-time --archive
```

Queda en `dist/`. Algunas decisiones:

- Se arma con el Python que instala uv, en la versión de `.python-version`, nunca con uno que ya tenga la máquina
  (`--managed-python`, o `UV_PYTHON_PREFERENCE=only-managed` en los workflows).
- Usa [PyInstaller](https://pyinstaller.org) con `packaging/lector.spec`, en forma de carpeta y no de un solo archivo:
  así arranca rápido, sin desempaquetar 300 MB en cada inicio, y los antivirus lo miran menos.
- De los modelos de rapidocr va solo el de reconocimiento que usa el lector. Quedan afuera Tk y, en Windows, el
  complemento de video de OpenCV (FFmpeg).
- En las Mac con Intel, onnxruntime queda en 1.23.2, la última versión con paquetes para ellas (lo fija
  `pyproject.toml`). onnxruntime y OpenCV piden macOS 14 en los dos tipos de Mac; `build.py` falla si algo pide más.
- En Linux no lleva el runtime de C++ de la máquina que lo arma, que pediría su glibc: usa el del sistema y pide glibc
  2.28 o más nueva. `build.py` lo calcula en cada armado.
- `THIRD_PARTY_NOTICES.txt` y la carpeta `licenses/` se generan en cada armado con lo que de verdad entró
  (`packaging/notices.py`), con los textos de licencia que trae cada paquete. También nombran las bibliotecas que
  Python lleva adentro (OpenSSL, SQLite, zlib y otras), cuyos textos están en `LICENSES/python/`.
- `packaging/launcher.py` es la entrada del programa: apaga la telemetría de onnxruntime antes de cargarlo, en macOS
  manda lo que escribe a un archivo, porque la app no tiene terminal, y si el motor de lectura no carga lo dice con
  palabras y, en Windows, con el enlace a Visual C++.
- La prueba propia corre con una carpeta temporal vacía y falla si onnxruntime dejó ahí su archivo `.ses`, que aparece
  cuando su telemetría está prendida.
- `PYTHONHASHSEED` va fijo y `SOURCE_DATE_EPOCH` es la hora del último commit. En Linux, armar dos veces el
  mismo commit da el mismo `.tar.gz`, byte por byte: está comprobado. El `.zip` de Windows también usa fechas fijas,
  pero todavía no se comprobó. Los `.zip` de macOS no salen iguales: `ditto` guarda la hora en que se armó cada
  archivo.

En Linux ocupa unos 340 MB descomprimido y 140 MB comprimido.

## Licencia

[AGPL-3.0-or-later](LICENSE).
