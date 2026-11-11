# Con tu propia IA

[English](own-ai.md)

En vez del modelo local, `urna-padrones extract` puede mandar las páginas a un servicio de IA, con una clave tuya.
Sirve cuando el modelo local lee mal un padrón, pero el padrón sale de tu computadora: leé esto antes. Se hace solo
desde la terminal; el lector siempre lee con el modelo local.

## Servicios

- `--ia mistral` usa Mistral OCR, de Mistral AI, en su dirección europea (`https://api.eu.mistral.ai`), con el modelo
  `mistral-ocr-latest` si no decís otro con `--ia-modelo`. Devuelve cada página como texto con tablas, y cada tabla se
  lee por los nombres de su encabezado, como un escaneo.
- `--ia openai-compatible --ia-url <dirección> --ia-modelo <modelo>` usa cualquier servicio que conteste como la API de
  chat de OpenAI y acepte imágenes, como OVHcloud AI Endpoints, Scaleway u OpenAI. La dirección es la base de la API,
  como `https://api.ejemplo.com/v1`. Se le pide un JSON estricto, con un objeto por persona y la lista de las columnas
  que tiene la página, y se comprueba antes de usarlo: cada columna de esa lista se revisa en cada fila, aunque no se
  haya podido leer en ninguna. Una respuesta con personas y sin esa lista no se usa.
- Un servidor de modelos en tu misma computadora también sirve: es el único que puede usar `http://`; los demás tienen
  que usar `https://`.

## La clave

La clave va en la variable `URNA_PADRONES_IA_CLAVE`, nunca como argumento, para que no quede en el historial de la
terminal. Para escribirla sin que se vea ni quede guardada, en bash o zsh:
`read -rs URNA_PADRONES_IA_CLAVE && export URNA_PADRONES_IA_CLAVE`; en fish: `read -sx URNA_PADRONES_IA_CLAVE`.

Una clave con un espacio, un salto de línea o una letra que no es de las comunes se rechaza antes de mandar nada, sin
mostrarla. Si el servicio repite la clave al rechazar un pedido, el mensaje la muestra tapada.

```sh
uv run urna-padrones extract padron.pdf --out ~/privado/padron.jsonl --ia mistral --acepto-enviar
```

Sin `--acepto-enviar`, muestra un aviso y no manda nada. Sin `--ia`, nada cambia y nada sale de tu computadora.

## Qué se manda y a quién

- Van las imágenes de las páginas escaneadas y de las fotos, una por pedido, directo de tu computadora al servicio, con
  tu clave: no pasan por ningún servidor del proyecto.
- Cada imagen es un JPEG armado de nuevo desde la página: nunca va el PDF, ni las páginas que no se leen (con
  `--pages N`, solo van las primeras N), ni lo que trae una foto además de la imagen, como el lugar donde se sacó.
- Las páginas de un PDF con texto nunca se mandan: se leen de su texto, y si su texto no es una lista que el programa
  conozca, como una tapa, se leen con el modelo local.
- El programa no sigue redirecciones: la clave y las páginas van solo a la dirección que elegiste. Si tu red usa un
  proxy (`https_proxy`), el pedido pasa por él cifrado de punta a punta; a un servidor en tu misma computadora se va
  directo, sin proxy.

Esas imágenes tienen los nombres y los documentos de las personas, y la empresa del servicio los trata según sus
condiciones, no las de este proyecto. El servicio te cobra lo que cobre por página, según tu plan.

**Qué mirar en las condiciones del servicio**, antes de mandar un padrón: si usa lo que le mandás para entrenar sus
modelos y cómo se apaga eso, cuánto tiempo lo guarda, en qué país lo procesa y lo guarda, y si tu plan incluye un
acuerdo de tratamiento de datos. Depende del servicio y del plan, y puede cambiar: el programa no lo comprueba.

## Qué vuelve

- Cada valor pasa por las mismas limpiezas y reglas de revisión que lo leído con el modelo local: una fila queda para
  revisar si un valor no tiene su forma. El servicio no dice qué tan seguro está, así que sus números de orden se
  corrigen por los vecinos, como los de un escaneo.
- Un valor con caracteres que un padrón impreso no tiene, como los que mueven el cursor de la terminal, pierde esos
  caracteres y deja la fila para revisar. Uno de más de 200 caracteres, el largo que la app acepta para un nombre o un
  domicilio, no se usa, y la fila queda para revisar con ese valor vacío.
- Una respuesta de más de 4 MB, o con más de 400 personas o renglones de tabla en una página, no es una página de un
  padrón y no se usa.
- Cada pedido espera hasta 120 segundos la respuesta entera y se intenta hasta 3 veces si el servicio está ocupado,
  falla, no contesta o contesta algo que no es lo pedido. Una clave rechazada o una cuota terminada se dicen enseguida.
- Si una página no se puede leer, `extract` para, dice por qué y no escribe nada. Con Ctrl+C, deja de esperar
  enseguida; un pedido que ya salió no se puede retirar.

## El archivo `.padron` lo dice

Cada fila de la extracción lleva `external_ai` con el servicio y el modelo, y `padron` escribe en el archivo
`extraction.external_ai: true` y `extraction.provider` (ver el [formato](formato-padron.md)). Según el nivel de
seguridad de la elección, la app puede no aceptar un padrón leído así.

## Estado

Las pruebas usan un servicio falso en la misma computadora; con los servicios reales todavía no se probó. Todavía no
está en las pantallas del lector.
