"""Why a roll could not be read: a code a program can act on, and a message a person can read."""

MESSAGES = {
    "not_pdf": (
        "El archivo no es un PDF ni una imagen JPG, PNG o TIFF.",
        "The file is neither a PDF nor a JPG, PNG or TIFF image.",
    ),
    "encrypted": (
        "El PDF tiene contraseña: guardalo sin contraseña y probá de nuevo.",
        "The PDF is password protected: save it without a password and try again.",
    ),
    "damaged": ("El archivo está dañado y no se puede abrir.", "The file is damaged and cannot be opened."),
    "too_many_pixels": (
        "La imagen es demasiado grande para abrirla: puede tener hasta 120 millones de píxeles. Achicala, o escaneá la "
        "hoja a 300 dpi.",
        "The picture is too large to open: it can have up to 120 million pixels. Make it smaller, or scan the page at "
        "300 dpi.",
    ),
    "empty": ("El PDF no tiene páginas.", "The PDF has no pages."),
    "unknown_layout": (
        "No encontré en ninguna página una tabla de padrón que sepa leer.",
        "No page has a roll table this program knows how to read.",
    ),
    "cancelled": ("Se canceló la lectura.", "The reading was cancelled."),
}


class RollError(Exception):
    """A roll that cannot be read. `code` is one of MESSAGES; str() gives the Spanish message."""

    def __init__(self, code: str):
        if code not in MESSAGES:
            raise ValueError(f"unknown roll error code: {code!r}")
        super().__init__(code)
        self.code = code

    @property
    def message(self) -> str:
        return MESSAGES[self.code][0]

    @property
    def message_en(self) -> str:
        return MESSAGES[self.code][1]

    def __str__(self) -> str:
        return self.message
