# Qué lee

[English](what-it-reads.md)

El escáner lee padrones hechos como tabla: PDF escaneados, PDF con texto y fotos. Lo que lee el lector y lo que lee
`urna-padrones extract` es lo mismo.

## Tablas con encabezado

En un escaneo o una foto de una tabla con líneas, busca el encabezado en las primeras filas y lee cada columna por su
nombre, en cualquier orden y aunque haya columnas de más. Los nombres se comparan sin mayúsculas, tildes ni puntos:

| Dato | Nombres que reconoce |
|---|---|
| Número de orden | «Nº», «N°», «Orden», «Número» |
| Nombre | «Apellido y nombre», «Nombre», o «Apellido» y «Nombres» en dos columnas |
| Documento | «DNI», «Documento», «Nro. de documento», «Tipo y número» |
| Legajo | «Legajo» |
| Carrera | «Carrera», «Propuesta» |
| Mesa | «Mesa» |
| Domicilio | «Domicilio» |
| Estado | «Calidad», «Estado» |

Hace falta el nombre y algo que distinga a las personas: el número de orden, el documento o el legajo. Una columna con
otro nombre no se lee, aunque tenga datos. Un encabezado en dos renglones, como «Nro. de» sobre «documento», se lee
como uno, y en un nombre largo perdona una letra mal leída. Una página sin encabezado toma el de otra página del mismo
padrón cuya tabla tenga tantas columnas. Una página con un encabezado propio nunca toma el de otra: un mismo PDF puede
traer dos listas armadas distinto.

## El formato de facultad

Un padrón con las columnas número, nombre, carrera, legajo, documento, calidad y firma, en ese orden, se lee aunque su
encabezado no se reconozca: si una página no tiene un encabezado que el escáner conozca, la tabla se lee con esas
columnas. Si alguna página tiene arriba un título como «Mesa Nº 3», cada fila suma su mesa (ver [Mesas](#mesas)).

En los legajos con la forma `A-1234/5`, el número después de la barra es un dígito verificador (módulo 11, con pesos de
2 a 7 desde la derecha; si da 10 u 11 se escribe 1). Un legajo de cuatro números que no lo cumple queda para revisar:
casi siempre es un número mal leído.

En los demás padrones acepta además nombres sin coma («PRUEBA ANA»), el tipo antes del documento («DNI 99.123.456»),
legajos con otra forma (como 12345 o 12345/6) y cualquier palabra como estado.

## PDF con texto

Un listado exportado de una planilla o de un sistema se toma tal como está, sin reconocerlo: no se equivoca de letra,
ninguna fila queda en duda por eso y una página se lee en una fracción de segundo. Arma las filas por renglón y las
columnas por dónde están los nombres del encabezado, con líneas o sin ellas. El encabezado puede estar solo en la
primera página.

- Un nombre que sigue en un segundo renglón queda entero: un renglón sin número ni documento va con la fila de arriba o
  de abajo, la que esté más cerca. Si las dos están casi igual de cerca, la fila queda para revisar.
- Un renglón sin números lejos de las filas, como «Firma del presidente de mesa» al pie, no es una persona.
- Una página girada por el PDF, como la guarda un visor después de girarla, se lee derecha.

**Lo que el PDF no muestra no se usa.** No se lee el texto invisible que algunos escáneres agregan sobre la imagen, el
texto blanco, el que es solo un recorte ni el que queda tapado por una imagen. Una página cubierta por una imagen es un
escaneo y se lee de la imagen, aunque tenga encima un sello con texto, como «Copia fiel»; su texto solo se usa si
nombra las columnas en su propio encabezado. Un mismo PDF puede tener páginas de los dos tipos.

## Mesas

Con una columna «Mesa», o un título como «Mesa Nº 12» arriba de la tabla, cada persona queda en su mesa y el archivo
`.padron` trae una unidad por mesa. El título vale para toda la página. En un PDF con texto, un renglón que dice solo
«Mesa 13» entre las filas empieza otra mesa, y la mesa sigue en la página siguiente hasta el próximo renglón así. Una
página escaneada sin título propio no toma la mesa de la anterior: un título mal leído no puede mandar a nadie a otra
mesa. Si en el padrón hay mesas, quien queda sin mesa queda para revisar.

## Fotos

JPG, PNG o TIFF; un TIFF de varias páginas se lee página por página. Cada imagen se lleva al tamaño de una hoja A4 a
300 dpi, suponiendo que la hoja ocupa toda la foto. En una foto de celular empareja la luz y endereza hasta 3 grados,
pero no corrige la perspectiva: anda mejor con la hoja plana, bien iluminada, sin sombras, sacada de frente y ocupando
toda la foto. Un PNG con el fondo transparente se lee sobre papel blanco. Una imagen de más de 120 millones de píxeles
(más que una foto de 108 megapíxeles o una hoja escaneada a 1000 dpi) no se abre.

## Cuándo una fila queda para revisar

- Si un valor no tiene su forma, como un documento que no tiene siete u ocho números o un legajo con el dígito
  verificador mal.
- Si el modelo no estaba seguro al leerlo. Lo que sale del texto de un PDF no tiene esa duda: queda para revisar solo
  por lo anterior o porque no está claro de qué fila es un renglón.
- En un padrón con mesas, si la fila quedó sin mesa.

Una fila para revisar nunca se descarta: el lector la muestra para corregirla, y en el archivo `.padron` queda marcada
para que se revise en la app.

## Lo que todavía no lee

Letra manuscrita, y tablas sin un encabezado que reconozca y sin líneas: un listado de nombres sin títulos, o un
escaneo sin líneas.
