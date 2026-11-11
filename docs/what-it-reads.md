# What it reads

[Español](que-lee.md)

The scanner reads rolls laid out as tables: scanned PDFs, PDFs with text and photos. The reader and
`urna-padrones extract` read the same things.

## Tables with a header

In a scan or a photo of a ruled table, it looks for the header in the first rows and reads each column by its name, in
any order and even with extra columns. Names are compared without case, accents or dots:

| Data | Names it recognises |
|---|---|
| Order number | «Nº», «N°», «Orden», «Número» |
| Name | «Apellido y nombre», «Nombre», or «Apellido» and «Nombres» in two columns |
| Document | «DNI», «Documento», «Nro. de documento», «Tipo y número» |
| Student number | «Legajo» |
| Program | «Carrera», «Propuesta» |
| Polling table | «Mesa» |
| Address | «Domicilio» |
| Status | «Calidad», «Estado» |

It needs the name and something that tells people apart: the order number, the document or the student number. A
column with another name is not read, even if it has data. A header on two lines, such as «Nro. de» over «documento»,
is read as one, and a long name may have one letter misread. A page without a header takes the header of another page
of the same roll whose table has as many columns. A page with a header of its own never takes another page's: one PDF
may hold two lists laid out differently.

## The faculty layout

A roll with the columns number, name, program, student number, document, status and signature, in that order, is read
even when its header is not recognised: if a page has no header the scanner knows, the table is read with those
columns. If some page has a title such as «Mesa Nº 3» above it, each row adds its polling table (see
[Polling tables](#polling-tables)).

In student numbers shaped like `A-1234/5`, the digit after the slash is a check digit (modulo 11, with weights 2 to 7
from the right; 10 or 11 is written as 1). A four-digit student number that does not match it is left for review: it
is almost always a misread digit.

In other rolls it also takes names without a comma («PRUEBA ANA»), the document type before the number
(«DNI 99.123.456»), student numbers of other shapes (such as 12345 or 12345/6) and any word as a status.

## PDFs with text

A listing exported from a spreadsheet or a system is taken as it is, without recognising it: it gets no letter wrong,
no row is left in doubt because of that, and a page is read in a fraction of a second. It builds the rows by line and
the columns by where the names of the header are, with or without ruling. The header may be on the first page only.

- A name that goes on onto a second line stays whole: a line without a number or a document goes with the row above or
  below it, whichever is closer. If both are nearly as close, the row is left for review.
- A line without numbers far from the rows, such as «Firma del presidente de mesa» at the foot, is not a person.
- A page the PDF turns, as a viewer saves it after turning it, is read upright.

**What the PDF does not show is not used.** Invisible text that some scanners add over the picture, white text, text
that is only a clipping path and text covered by a picture are not read. A page covered by a picture is a scan and is
read from its picture, even with a stamp with text on it, such as «Copia fiel»; its text is used only if it names the
columns in a header of its own. One PDF can have pages of both kinds.

## Polling tables

With a «Mesa» column, or a title such as «Mesa Nº 12» above the table, each person stays at their polling table and
the `.padron` file has one unit per table. A title applies to the whole page. In a PDF with text, a line saying only
«Mesa 13» among the rows starts another table, and the table goes on onto the next page until the next such line. A
scanned page without a title of its own does not take the table of the page before: a misread title cannot send anyone
to another table. If the roll has polling tables, whoever is left without one is left for review.

## Photos

JPG, PNG or TIFF; a TIFF with several pages is read page by page. Each picture is brought to the size of an A4 page at
300 dpi, taking the page to fill the whole photo. In a phone photo it evens out the light and straightens up to
3 degrees, but it does not correct perspective: it works best with the page flat, well lit, without shadows, taken from
straight above and filling the photo. A PNG with a transparent background is read on white paper. A picture of more
than 120 million pixels (more than a 108-megapixel photo or a page scanned at 1000 dpi) is not opened.

## When a row is left for review

- If a value does not have its shape, such as a document without seven or eight digits or a student number with the
  wrong check digit.
- If the model was not sure when reading it. What comes from the text of a PDF has no such doubt: it is left for
  review only for the reason above or because it is not clear which row a line belongs to.
- In a roll with polling tables, if the row was left without one.

A row left for review is never dropped: the reader shows it so it can be fixed, and in the `.padron` file it stays
marked to be reviewed in the app.

## What it does not read yet

Handwriting, and tables without a header it recognises and without ruling: a list of names without titles, or a scan
without lines.
