# Instalar el lector

[English](install.md)

El lector viene armado para Windows, macOS y Linux: no hace falta instalar Python ni nada más. Bajá el archivo de tu
computadora de la [última versión](../../../releases/latest):

| Tu computadora | Archivo |
|---|---|
| Windows 10 u 11 | `urna-abierta-lector-windows-x64.zip` |
| Mac con chip Apple (M1 o posterior), con macOS 14 o más nuevo | `urna-abierta-lector-macos-arm64.zip` |
| Mac con procesador Intel, con macOS 14 o más nuevo | `urna-abierta-lector-macos-x64.zip` |
| Linux de 64 bits con glibc 2.28 o más nueva | `urna-abierta-lector-linux-x64.tar.gz` |

En Linux, glibc 2.28 quiere decir Ubuntu 20.04, Debian 10, Fedora 29 o más nuevos.

Para saber qué Mac tenés: menú Apple → «Acerca de esta Mac». Si dice «Chip» y un nombre como «Apple M1», es la de chip
Apple; si dice «Procesador» y un nombre con «Intel», es la otra.

El programa no está firmado con un certificado pago, así que la primera vez Windows y macOS avisan que no lo conocen.
Antes de abrirlo, conviene [comprobar el archivo](#comprobar-el-archivo).

## En Windows

1. Hacé clic derecho en el `.zip` y elegí «Extraer todo». No lo abras desde adentro del zip.
2. En la carpeta que queda, hacé doble clic en `urna-abierta-lector.exe`.
3. Si aparece «Windows protegió su PC», hacé clic en «Más información» y después en «Ejecutar de todas formas».
4. Se abre una ventana negra con la dirección del lector, y el navegador se abre solo en esa dirección. Dejá la ventana
   abierta mientras lo usás: al cerrarla, se cierra el lector.

Si en vez del lector aparece un aviso de que no se pudo cargar el motor de lectura, instalá la versión más nueva de
[Microsoft Visual C++ (x64)](https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist) y abrilo de nuevo.

## En macOS

1. Hacé doble clic en el `.zip`: queda `Urna Abierta Lector.app`. Si querés, movela a Aplicaciones.
2. Hacé doble clic en la app. macOS avisa que no puede comprobar que esté libre de software malicioso: cerrá el aviso
   sin mandarla a la papelera.
3. Abrí Configuración del Sistema → Privacidad y seguridad, bajá hasta «Seguridad» y, al lado del aviso sobre
   «Urna Abierta Lector», hacé clic en «Abrir igualmente». Confirmá con tu contraseña y elegí «Abrir».
4. Eso se hace una sola vez. El lector se abre en el navegador y no tiene ventana propia ni ícono en el Dock. Se cierra
   con «Cerrar el lector», o solo, media hora después de cerrar la pestaña.

Si cerraste la pestaña sin querer, volvé a abrirla desde el historial del navegador: mientras el lector sigue abierto,
abrir la app de nuevo no abre otra pestaña. Lo que el lector escribe, con su dirección, queda en
`~/Library/Logs/Urna Abierta/lector.log`.

## En Linux

1. Descomprimí el archivo: `tar -xzf urna-abierta-lector-linux-x64.tar.gz`.
2. Abrilo desde una terminal: `./urna-abierta-lector-linux-x64/urna-abierta-lector`. Muestra la dirección y abre el
   navegador. Se cierra al cerrar la terminal, con Ctrl+C o con «Cerrar el lector».

## Comprobar el archivo

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

## Desde una copia del repo

Si la [página de versiones](../../../releases) todavía no tiene ninguna, el lector se abre desde una terminal. Con
[uv](https://docs.astral.sh/uv/) instalado, en una copia de este repo (en GitHub, «Code» → «Download ZIP»):

```sh
uv run python -m urna_padrones.lector
```

`--no-browser` no abre el navegador, `--port` elige el puerto (si no, uno libre al azar) y `--self-test` comprueba sin
internet que el lector funciona.
