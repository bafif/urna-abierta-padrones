# Urna Abierta: escáner de padrones

**Pasa un padrón en PDF o en foto al formato abierto que lee Urna Abierta, sin que salga de tu computadora.**<br>
[English](README.en.md) · [Descargar](#descargar) · [Cómo se usa](docs/uso.md)

Arrastrás el PDF o la foto de un padrón al lector. Lo lee página por página, te muestra las filas que no quedaron
claras para que las corrijas y te deja un archivo `.padron` para subir a Urna Abierta. Se usa también solo, sin la app,
con pantallas en el navegador o desde la terminal.

## Por qué

- **El padrón no sale de tu computadora.** El reconocimiento de texto corre local, con un modelo que viene adentro del
  programa: anda sin internet y nunca baja nada. Ningún padrón pasa por una cuenta ni un servidor del proyecto. Solo
  si lo pedís desde la terminal, con tu propia clave, se lee con un servicio de IA externo.
- **Lee la tabla por su encabezado.** Encuentra cada columna por su nombre («DNI», «Apellido y nombre», «Mesa»…), en
  cualquier orden, en PDF escaneados, PDF con texto y fotos.
- **Nada dudoso se descarta.** Una fila con un valor que no tiene su forma, o que el modelo no leyó seguro, queda para
  revisar: el lector la muestra con la imagen de la fila arriba de sus datos.
- **Cada persona en su mesa.** Una columna «Mesa» o un título como «Mesa Nº 12» reparten el padrón, y el archivo trae
  una unidad por mesa.
- **Mide la calidad sin mostrar datos.** Desde la terminal compara lo leído con la numeración del padrón, con otro
  padrón o con una planilla tipeada, y muestra solo cantidades.
- **Un formato abierto.** El `.padron` sigue una [especificación](docs/formato-padron.md) de dominio público que
  cualquiera puede implementar.

## Descargar

El lector viene armado para cada sistema: no hace falta instalar Python ni nada más. Bajá el tuyo de la
[última versión](../../releases/latest):

| Tu computadora | Archivo |
|---|---|
| Windows 10 u 11 | `urna-abierta-lector-windows-x64.zip` |
| Mac con chip Apple (M1 o posterior), con macOS 14 o más nuevo | `urna-abierta-lector-macos-arm64.zip` |
| Mac con procesador Intel, con macOS 14 o más nuevo | `urna-abierta-lector-macos-x64.zip` |
| Linux de 64 bits con glibc 2.28 o más nueva | `urna-abierta-lector-linux-x64.tar.gz` |

El programa no está firmado con un certificado pago: la primera vez, Windows y macOS avisan que no lo conocen. Cómo
abrirlo en cada sistema y cómo comprobar que el archivo es el que armó GitHub, en [Instalar](docs/instalar.md).

## Cómo se usa

1. **Abrí el lector.** Se abre en tu navegador, en una dirección que solo funciona desde tu computadora.
2. **Elegí el padrón:** arrastrá el PDF o la foto a la ventana. Se lee página por página, y se puede cancelar.
3. **Revisá** las filas que no quedaron claras: corregilas o confirmalas. Las que no revises quedan pendientes para la
   app.
4. **Guardá el `.padron`** y, en Urna Abierta, subilo con «Subir el padrón». Una vez subido, borralo: tiene datos de
   personas.

Si el padrón ya está en una planilla de Excel o CSV, no hace falta el lector: se sube directo en la app. Los comandos
de la terminal están en [Cómo se usa](docs/uso.md#desde-la-terminal).

## Estado

- **Lee** padrones hechos como tabla, en PDF escaneados, PDF con texto y fotos JPG, PNG o TIFF, con mesas y
  domicilios. Todavía no lee letra manuscrita ni tablas sin líneas y sin un encabezado que reconozca.
- **El lector** se arma y se prueba sin red en las máquinas de GitHub, para Windows, macOS y Linux. En computadoras
  con Windows o macOS todavía no se probó.
- **Con tu propia IA** se lee solo desde la terminal, y solo se probó contra un servicio falso. El lector todavía no
  ofrece un servicio de IA gratis.

## Más documentación

- [Instalar](docs/instalar.md): cada sistema en detalle, comprobar la descarga y abrir el lector desde una copia del
  repo.
- [Cómo se usa](docs/uso.md): el lector paso a paso y los comandos de la terminal.
- [Qué lee](docs/que-lee.md): qué tablas, PDF, fotos y mesas entiende, y cuándo una fila queda para revisar.
- [Con tu propia IA](docs/ia-propia.md): qué se manda, a quién, y qué mirar antes de mandar un padrón.
- [Formato abierto de padrón](docs/formato-padron.md): la especificación del archivo `.padron`.
- [Cómo está hecho](docs/desarrollo.md): las pruebas y cómo se arma el lector.

## Licencia

[AGPL-3.0-or-later](LICENSE). La especificación del formato es de dominio público ([CC0 1.0](docs/formato-padron.md)).
