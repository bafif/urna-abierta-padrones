# Cómo está hecho

[English](development.md)

## Pruebas

```sh
uv run pytest
```

Usan escaneos, PDF con texto y fotos fabricados con personas inventadas (`tests/fake_roll.py` y
`tests/fake_layouts.py`). **Nunca subas un padrón real al repo**: `.gitignore` deja afuera los `.pdf`, `.padron` y
`.jsonl`, y `extract` se niega a escribir dentro de un repo de git.

En GitHub corren en Linux, Windows y macOS (`.github/workflows/tests.yml`). Las de `tests/test_extract.py` piden
Liberation Sans por fontconfig y se saltean donde no está, como en Windows y macOS; las demás dibujan con Arial si no
la encuentran.

Cada documento está en castellano y en inglés: `X.md` y `X.en.md`, o, si el nombre cambia con el idioma, los dos se
nombran con un enlace al principio. `tests/test_docs.py` comprueba los pares y que cada enlace relativo lleve a un
archivo y a un título que existen.

## Las pantallas del lector

Están en `src/urna_padrones/lector/ui/`. El tema y sus letras son copias de la app: ver
[su README](../src/urna_padrones/lector/ui/README.md).

## Cómo se arma el lector

Los archivos de cada versión los arma GitHub Actions (`.github/workflows/release.yml`) cuando se sube una etiqueta
`v*`, cada uno en una máquina del sistema para el que es: Windows x64, macOS con chip Apple, macOS con Intel, Linux x64
(Ubuntu 22.04) y Linux x64 con musl (un contenedor de Alpine 3.24). Nunca se arman en una computadora personal, para
que no lleven rutas ni nombres de nadie. Cada máquina arma el lector, corre su prueba propia sin red, comprueba que no
se bajó nada y que la telemetría de onnxruntime quedó apagada, escribe el archivo con su SHA-256 y su constancia, y lo
sube a la versión, que se publica cuando están los cinco. El mismo flujo se puede correr a mano sobre `main`, desde
«Actions», «Release», «Run workflow»: arma y prueba los cinco igual, sin crear ni publicar ninguna versión.

Para armarlo para tu sistema, en tu computadora:

```sh
uv sync --managed-python --no-editable --group build
uv run --no-sync python packaging/build.py --self-test --start-time --archive
```

Queda en `dist/`. En Linux ocupa unos 340 MB descomprimido y 140 MB comprimido; el de Alpine, unos 580 MB y 225 MB,
porque su OpenCV viene de los paquetes de Alpine, que lo arman con todos sus módulos.

Para Alpine, `packaging/alpine.sh` prepara el Python que lo arma, dentro de un contenedor:

```sh
podman run --rm -v "$PWD":/src -w /src docker.io/library/alpine:3.24 \
  sh -c 'sh packaging/alpine.sh && /opt/lector/bin/python packaging/build.py --self-test --archive'
```

## Decisiones

- Se arma con el Python que instala uv, en la versión de `.python-version`, nunca con uno que ya tenga la máquina
  (`--managed-python`, o `UV_PYTHON_PREFERENCE=only-managed` en los workflows).
- Usa [PyInstaller](https://pyinstaller.org) con `packaging/lector.spec`, en forma de carpeta y no de un solo archivo:
  así arranca rápido, sin desempaquetar 300 MB en cada inicio, y los antivirus lo miran menos.
- De los modelos de rapidocr va solo el de reconocimiento que usa el lector. Quedan afuera Tk y, en Windows, el
  complemento de video de OpenCV (FFmpeg).
- También queda afuera setuptools: PyInstaller lo necesita para armar, pero el lector no lo usa. Una prueba revisa que
  el código del lector no lo importe.
- En las Mac con Intel, onnxruntime queda en 1.23.2, la última versión con paquetes para ellas (lo fija
  `pyproject.toml`). onnxruntime y OpenCV piden macOS 14 en los dos tipos de Mac; `build.py` falla si algo pide más.
- En Linux no lleva el runtime de C++ de la máquina que lo arma, que pediría su glibc: usa el del sistema y pide glibc
  2.28 o más nueva. `build.py` lo calcula en cada armado. En Alpine sí lo lleva: un Alpine sin escritorio puede no
  tenerlo.
- PyPI no publica onnxruntime ni OpenCV para musl, ni pyclipper para el Python de Alpine: en Alpine, esos tres y numpy
  vienen de sus paquetes, y lo demás, PyInstaller incluido, de las versiones de `uv.lock`.
- `THIRD_PARTY_NOTICES.txt` y la carpeta `licenses/` se generan en cada armado con lo que de verdad entró
  (`packaging/notices.py`), con los textos de licencia que trae cada paquete. También nombran las bibliotecas que
  Python lleva adentro (OpenSSL, SQLite, zlib y otras), cuyos textos están en `LICENSES/python/`.
- `packaging/launcher.py` es la entrada del programa: apaga la telemetría de onnxruntime antes de cargarlo, en macOS
  manda lo que escribe a un archivo, porque la app no tiene terminal, y si el motor de lectura no carga lo dice con
  palabras y, en Windows, con el enlace a Visual C++.
- La prueba propia corre con una carpeta temporal vacía y falla si onnxruntime dejó ahí su archivo `.ses`, que aparece
  cuando su telemetría está prendida.
- `PYTHONHASHSEED` va fijo y `SOURCE_DATE_EPOCH` es la hora del último commit. En Linux, armar dos veces el mismo
  commit da el mismo `.tar.gz`, byte por byte. El `.zip` de Windows también usa fechas fijas, pero no se comprobó que
  salga igual. Los `.zip` de macOS no salen iguales: `ditto` guarda la hora en que se armó cada archivo.
- Los íconos de Windows y macOS están hechos en `packaging/iconos/`, así que armar el lector no pide nada más. Se
  rehacen con `uv run python tools/hacer-iconos.py`, que dibuja cada tamaño desde el mismo SVG con rsvg-convert.
