"""What the scanner says to a person, in Spanish and in English.

It speaks the language of the computer: Spanish when any of the languages the system prefers is Spanish, English
otherwise. `--idioma` forces one. The files it writes never change with the language: their columns and values are a
format that the app reads.
"""

import argparse
import functools
import locale
import os
import subprocess
import sys

LANGUAGES = ("es", "en")
_chosen: str | None = None


def is_spanish(tag: str) -> bool:
    """es, es-AR, es_AR.UTF-8, es-419…"""
    return tag.strip().lower().replace("-", "_").split(".")[0].split("_")[0] == "es"


def _set(value: str | None) -> bool:
    return bool(value) and value.split(".")[0] not in ("C", "POSIX")


def _windows_languages() -> list[str]:
    """The language of the person's Windows account, as es_AR or en_US."""
    try:
        import ctypes

        return [locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "")]
    except (ImportError, AttributeError, OSError):
        return []


def _mac_languages() -> list[str]:
    """The languages of the macOS account, in its order. A program opened from the Finder has no LANG."""
    try:
        listed = subprocess.run(
            ["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True, timeout=3, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [part.strip().strip('"') for part in listed.stdout.strip("()\n ").split(",") if part.strip()]


def system_languages(env: dict[str, str] | None = None, platform: str | None = None) -> list[str]:
    """The languages the system prefers, first the one it uses.

    LC_ALL, LC_MESSAGES and LANG, in that order, say the language of messages on Linux and macOS, and LANGUAGE can
    add more. Where none is set, as on Windows or in a program opened from the macOS Finder, the account says it.
    """
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if _set(env.get(name)):
            return [env[name], *filter(None, env.get("LANGUAGE", "").split(":"))]
    if platform == "win32":
        return _windows_languages()
    if platform == "darwin":
        return _mac_languages()
    return []


@functools.cache
def system_language() -> str:
    return "es" if any(is_spanish(tag) for tag in system_languages()) else "en"


def language() -> str:
    return _chosen or system_language()


def set_language(value: str | None) -> None:
    """The language to use from now on; None goes back to the system's."""
    global _chosen
    if value is not None and value not in LANGUAGES:
        raise ValueError(f"unknown language: {value!r}")
    _chosen = value


def forced_language(argv: list[str]) -> str | None:
    """The language the command line asks for, before reading it: its help has to come out in that language."""
    for index, word in enumerate(argv):
        for option in ("--idioma", "--language"):
            if word == option and index + 1 < len(argv):
                return argv[index + 1] if argv[index + 1] in LANGUAGES else None
            if word.startswith(option + "="):
                value = word.split("=", 1)[1]
                return value if value in LANGUAGES else None
    return None


def t(key: str, **values) -> str:
    return TEXTS[language()][key].format(**values)


def add_language_option(parser: argparse.ArgumentParser, **options) -> None:
    parser.add_argument(
        "--idioma", "--language", dest="language", choices=LANGUAGES, help=t("help.language"), **options
    )


# What argparse itself says, which Python only has in English.
_ARGPARSE_ES = {
    "usage: ": "uso: ",
    "positional arguments": "argumentos",
    "options": "opciones",
    "show this help message and exit": "muestra esta ayuda y termina",
    "the following arguments are required: %s": "faltan estos argumentos: %s",
    "unrecognized arguments: %s": "argumentos que no conozco: %s",
    "expected one argument": "espera un valor",
    "invalid choice: %(value)r (choose from %(choices)s)": "%(value)r no es una opción (puede ser %(choices)s)",
    "invalid choice: %(value)r, choose from %(choices)s": "%(value)r no es una opción (puede ser %(choices)s)",
    "invalid %(type)s value: %(value)r": "valor inválido: %(value)r",
    "argument %(argument_name)s: %(message)s": "argumento %(argument_name)s: %(message)s",
    "%(prog)s: error: %(message)s\n": "%(prog)s: error: %(message)s\n",
}


def localize_argparse() -> None:
    """argparse asks gettext for its own words, which has no Spanish here: in Spanish, they come from this table."""
    argparse._ = lambda text: _ARGPARSE_ES.get(text, text) if language() == "es" else text  # type: ignore[attr-defined]


TEXTS: dict[str, dict[str, str]] = {
    "es": {
        "help.language": "idioma de los mensajes: es o en (si no, el de la computadora)",
        "cli.description": "Lee un padrón en PDF o en fotos y arma el archivo que se sube a Urna Abierta. Muestra solo "
        "cantidades, nunca datos del padrón.",
        "help.extract": "extrae las filas de un padrón en PDF o en fotos",
        "help.file": "PDF escaneado o con texto, o imagen JPG, PNG o TIFF",
        "meta.file": "archivo",
        "help.out": "archivo donde se guardan las filas leídas",
        "help.pages": "lee solo las primeras páginas",
        "help.workers": "cuántas páginas se leen a la vez (2 si no se dice)",
        "help.allow_inside_repo": "deja guardar la salida dentro de un repo de git",
        "help.ia": "lee las páginas con un servicio de IA externo, con tu clave en {variable} (sin esto, todo se lee "
        "en tu computadora)",
        "help.ia_url": "dirección del servicio, como https://api.ejemplo.com/v1 (para mistral, si no se dice, {url})",
        "help.ia_model": "modelo del servicio (para mistral, si no se dice, {model})",
        "help.accept": "confirma que el padrón se manda a ese servicio, después de leer el aviso",
        "help.padron": "arma el archivo .padron que se sube a Urna Abierta",
        "help.records": "las filas que guardó extract",
        "help.padron_out": "archivo .padron que se arma",
        "help.title": "título del padrón, como lo va a ver la app",
        "help.report": "muestra la calidad de una extracción",
        "help.crosscheck": "compara dos extracciones que se solapan",
        "help.first": "la primera extracción",
        "help.second": "la segunda extracción",
        "help.verify": "compara una extracción con el padrón tipeado en una planilla",
        "help.spreadsheet": "planilla .xlsx o .csv con nombre, documento y legajo",
        "help.rows": "además, lista las filas de la planilla para revisar (sin mostrar los datos)",
        "cli.positive": "tiene que ser 1 o más",
        "cli.progress": "página {done} de {total}",
        "cli.ai_alone": "--ia-url, --ia-modelo y --acepto-enviar van con --ia.",
        "cli.accept": "Para seguir, agregá --acepto-enviar. No se mandó nada.",
        "cli.records_in_repo": "La salida tiene datos personales y queda dentro de un repo de git: elegí otra carpeta.",
        "cli.padron_in_repo": "El padrón tiene datos personales y queda dentro de un repo de git: elegí otra carpeta.",
        "cli.summary": "{rows} filas de {pages} páginas en {seconds} s; páginas sin tabla: {without}; números de orden "
        "inferidos: {inferred}",
        "cli.summary.text": "; páginas con texto: {count}",
        "cli.summary.tables": "; mesas: {count}",
        "cli.summary.sent": "; páginas mandadas a {service}: {count}",
        "cli.padron": "{people} personas; {review} para revisar",
        "cli.padron.tables": "; {count} mesas",
        "cli.padron.seen": "; lo vio una IA externa: {provider}",
        "cli.padron.seen.yes": "sí",
        "cli.spreadsheet": "No se pudo leer la planilla: {error}",
        "cli.row": "fila {row}: {what}",
        "check.no_document": "sin DNI",
        "check.bad_document": "el DNI no tiene 7 u 8 números",
        "check.bad_file_number": "el legajo no tiene la forma A-1234/3",
        "check.file_number_digit": "el dígito del legajo no corresponde",
        "check.document_other_name": "DNI repetido con otro nombre",
        "check.file_number_other_name": "legajo repetido con otro nombre",
        "check.file_number_other_document": "legajo repetido con otro DNI",
        "check.repeated_row": "fila repetida",
        "check.same_person": "misma persona en más de una carrera",
        "check.not_read": "no está en la lectura",
        "check.differs": "distinto de la lectura: {fields}",
        "field.name": "nombre",
        "field.document": "DNI",
        "field.file_number": "legajo",
        "sheet.no_name": "No encontré una columna con el nombre en las primeras filas.",
        "sheet.not_xlsx": "El archivo no es una planilla .xlsx.",
        "sheet.too_large": "La planilla es demasiado grande para leerla.",
        "sheet.no_sheets": "La planilla no tiene hojas.",
        "sheet.kind": "La planilla tiene que ser .xlsx o .csv.",
        "sheet.empty": "La planilla está vacía.",
        "ai.no_key": "Falta la clave del servicio: guardala en la variable {variable}. No va como argumento, para que "
        "no quede en el historial de la terminal.",
        "ai.odd_key": "La clave de {variable} tiene espacios, saltos de línea o letras que una clave no lleva: guardá "
        "solo la clave, en una línea.",
        "ai.no_model": "Falta el modelo: decí cuál con --ia-modelo, con el nombre que le da el servicio.",
        "ai.odd_url": "La dirección del servicio tiene espacios o letras que una dirección no lleva.",
        "ai.bad_url": "La dirección del servicio tiene que ser como https://api.ejemplo.com/v1.",
        "ai.url_login": "La dirección no puede llevar usuario ni contraseña: la clave va en {variable}.",
        "ai.plain_http": "La dirección tiene que empezar con https://: con http:// el padrón viajaría sin cifrar. Solo "
        "un servicio en esta misma computadora puede usar http://.",
        "ai.url_query": "La dirección del servicio no lleva nada después de un «?» ni de un «#».",
        "ai.no_url": "Falta la dirección del servicio: decí cuál con --ia-url, como https://api.ejemplo.com/v1.",
        "ai.unknown": "No conozco el servicio «{kind}»: puede ser {kinds}.",
        "ai.or": " o ",
        "ai.key_refused": "{service} rechazó la clave ({status}): fijate que sea de ese servicio y que siga activa.",
        "ai.redirect": "{host} manda a otra dirección ({status}): poné en --ia-url la dirección final.",
        "ai.certificate": "No se pudo comprobar el certificado de {host}: no se mandó nada. Revisá la dirección.",
        "ai.cannot_build": "No se pudo armar el pedido a {host}: revisá la dirección y la clave.",
        "ai.refused": "{service} no aceptó el pedido ({status}){detail}.{hint}",
        "ai.refused.hint": " Revisá --ia-url y --ia-modelo.",
        "ai.quota": "{service} dice que se terminó la cuota de tu clave o que hubo demasiados pedidos seguidos: esperá "
        "un rato, o revisá tu plan en el servicio.",
        "ai.broken": "{service} tuvo un problema ({status}) en {attempts} intentos: probá más tarde.",
        "ai.silent": "{host} no contestó en {seconds:g} segundos, en {attempts} intentos: probá más tarde.",
        "ai.unreachable": "No se pudo llegar a {host}: revisá la conexión a internet y la dirección del servicio.",
        "ai.malformed": "La respuesta de {service} no es el JSON pedido{why}, en {attempts} intentos: no se usó nada "
        "de esa página.",
        "ai.image": "No se pudo armar la imagen de la página para mandarla.",
        "ai.warning": "Con --ia, el padrón se lee con {service}, con tu clave:\n"
        "- Van las imágenes de las páginas escaneadas o fotografiadas, con los nombres y los documentos de las\n"
        "  personas. Las páginas de un PDF con texto no se mandan: se leen en tu computadora.\n"
        "- Esa empresa los trata según sus condiciones: fijate si los usa para entrenar, cuánto tiempo los guarda y\n"
        "  en qué país.\n"
        "- El archivo .padron va a decir que una IA externa vio los datos. Según el nivel de seguridad de la\n"
        "  elección, la app puede no aceptarlo.",
        "answer.too_long": "pasa de {megabytes} MB",
        "answer.not_object": "no es un objeto",
        "answer.no_pages": "no trae páginas",
        "answer.page_without_text": "una página no trae su texto",
        "answer.tables_not_list": "las tablas de una página no son una lista",
        "answer.too_many_lines": "trae más de {count} renglones de tablas en una página",
        "answer.no_answer": "no trae una respuesta",
        "answer.empty": "vino vacía",
        "answer.cut": "se cortó antes de terminar",
        "answer.not_json": "no es JSON",
        "answer.no_rows": "falta la lista «rows»",
        "answer.no_columns": "falta la lista «columns»",
        "answer.too_many_people": "trae más de {count} personas en una página",
        "answer.person_not_object": "una persona no es un objeto",
        "answer.not_text": "«{field}» no es texto ni número",
        "lector.description": "Lector de padrones escaneados, con sus pantallas en el navegador. Nada sale de esta "
        "computadora.",
        "lector.port": "puerto en 127.0.0.1 (o {variable}; si no, uno libre al azar)",
        "lector.no_browser": "no abrir el navegador (o {variable}=1)",
        "lector.self_test": "comprobar que el lector funciona, sin red, y salir",
        "lector.port_range": "tiene que estar entre 0 y 65535",
        "lector.port_busy": "No pude usar el puerto {port} de esta computadora: probá con otro o sin --port.",
    },
    "en": {
        "help.language": "language of the messages: es or en (otherwise, the computer's)",
        "cli.description": "Reads a roll from a PDF or from photos and makes the file you upload to Urna Abierta. It "
        "shows counts only, never data from the roll.",
        "help.extract": "extracts the rows of a roll from a PDF or from photos",
        "help.file": "scanned PDF or PDF with text, or a JPG, PNG or TIFF image",
        "meta.file": "file",
        "help.out": "file where the rows read are saved",
        "help.pages": "reads only the first pages",
        "help.workers": "how many pages are read at once (2 if not said)",
        "help.allow_inside_repo": "lets the output be saved inside a git repository",
        "help.ia": "reads the pages with an external AI service, with your key in {variable} (without it, everything "
        "is read on your computer)",
        "help.ia_url": "address of the service, such as https://api.example.com/v1 (for mistral, if not said, {url})",
        "help.ia_model": "model of the service (for mistral, if not said, {model})",
        "help.accept": "confirms that the roll is sent to that service, after reading the warning",
        "help.padron": "makes the .padron file you upload to Urna Abierta",
        "help.records": "the rows that extract saved",
        "help.padron_out": ".padron file to make",
        "help.title": "title of the roll, as the app will show it",
        "help.report": "shows the quality of an extraction",
        "help.crosscheck": "compares two extractions that overlap",
        "help.first": "the first extraction",
        "help.second": "the second extraction",
        "help.verify": "compares an extraction with the roll typed into a spreadsheet",
        "help.spreadsheet": ".xlsx or .csv spreadsheet with name, document and legajo",
        "help.rows": "also lists the rows of the spreadsheet to check (without showing their data)",
        "cli.positive": "has to be 1 or more",
        "cli.progress": "page {done} of {total}",
        "cli.ai_alone": "--ia-url, --ia-modelo and --acepto-enviar go with --ia.",
        "cli.accept": "To go on, add --acepto-enviar. Nothing was sent.",
        "cli.records_in_repo": "The output has personal data and would be inside a git repository: choose another "
        "folder.",
        "cli.padron_in_repo": "The roll has personal data and would be inside a git repository: choose another folder.",
        "cli.summary": "{rows} rows from {pages} pages in {seconds} s; pages without a table: {without}; order numbers "
        "inferred: {inferred}",
        "cli.summary.text": "; pages with text: {count}",
        "cli.summary.tables": "; tables: {count}",
        "cli.summary.sent": "; pages sent to {service}: {count}",
        "cli.padron": "{people} people; {review} to review",
        "cli.padron.tables": "; {count} tables",
        "cli.padron.seen": "; an external AI saw it: {provider}",
        "cli.padron.seen.yes": "yes",
        "cli.spreadsheet": "The spreadsheet could not be read: {error}",
        "cli.row": "row {row}: {what}",
        "check.no_document": "no DNI",
        "check.bad_document": "the DNI does not have 7 or 8 digits",
        "check.bad_file_number": "the legajo is not shaped like A-1234/3",
        "check.file_number_digit": "the check digit of the legajo does not match",
        "check.document_other_name": "DNI repeated with another name",
        "check.file_number_other_name": "legajo repeated with another name",
        "check.file_number_other_document": "legajo repeated with another DNI",
        "check.repeated_row": "repeated row",
        "check.same_person": "same person in more than one degree",
        "check.not_read": "not in the reading",
        "check.differs": "differs from the reading: {fields}",
        "field.name": "name",
        "field.document": "DNI",
        "field.file_number": "legajo",
        "sheet.no_name": "No column with the name was found in the first rows.",
        "sheet.not_xlsx": "The file is not an .xlsx spreadsheet.",
        "sheet.too_large": "The spreadsheet is too large to read.",
        "sheet.no_sheets": "The spreadsheet has no sheets.",
        "sheet.kind": "The spreadsheet has to be .xlsx or .csv.",
        "sheet.empty": "The spreadsheet is empty.",
        "ai.no_key": "The key of the service is missing: keep it in the variable {variable}. It does not go as an "
        "argument, so that it does not stay in the terminal's history.",
        "ai.odd_key": "The key in {variable} has spaces, line breaks or characters a key does not have: keep only the "
        "key, on one line.",
        "ai.no_model": "The model is missing: say which with --ia-modelo, with the name the service gives it.",
        "ai.odd_url": "The address of the service has spaces or characters an address does not have.",
        "ai.bad_url": "The address of the service has to look like https://api.example.com/v1.",
        "ai.url_login": "The address cannot carry a user or a password: the key goes in {variable}.",
        "ai.plain_http": "The address has to start with https://: with http:// the roll would travel unencrypted. Only "
        "a service on this same computer can use http://.",
        "ai.url_query": "The address of the service takes nothing after a “?” or a “#”.",
        "ai.no_url": "The address of the service is missing: say which with --ia-url, such as "
        "https://api.example.com/v1.",
        "ai.unknown": "I do not know the service “{kind}”: it can be {kinds}.",
        "ai.or": " or ",
        "ai.key_refused": "{service} refused the key ({status}): check that it is for that service and still active.",
        "ai.redirect": "{host} sends to another address ({status}): put the final address in --ia-url.",
        "ai.certificate": "The certificate of {host} could not be verified: nothing was sent. Check the address.",
        "ai.cannot_build": "The request to {host} could not be put together: check the address and the key.",
        "ai.refused": "{service} did not accept the request ({status}){detail}.{hint}",
        "ai.refused.hint": " Check --ia-url and --ia-modelo.",
        "ai.quota": "{service} says the quota of your key ran out or there were too many requests in a row: wait a "
        "while, or check your plan with the service.",
        "ai.broken": "{service} had a problem ({status}) in {attempts} attempts: try again later.",
        "ai.silent": "{host} did not answer in {seconds:g} seconds, in {attempts} attempts: try again later.",
        "ai.unreachable": "{host} could not be reached: check the internet connection and the address of the service.",
        "ai.malformed": "The answer of {service} is not the JSON asked for{why}, in {attempts} attempts: nothing of "
        "that page was used.",
        "ai.image": "The image of the page could not be made to send it.",
        "ai.warning": "With --ia, the roll is read by {service}, with your key:\n"
        "- The images of the scanned or photographed pages go, with the names and documents of the people.\n"
        "  The pages of a PDF with text are not sent: they are read on your computer.\n"
        "- That company handles them under its own terms: check whether it trains on them, how long it keeps\n"
        "  them and in which country.\n"
        "- The .padron file will say that an external AI saw the data. Depending on the security level of the\n"
        "  election, the app may not accept it.",
        "answer.too_long": "goes over {megabytes} MB",
        "answer.not_object": "it is not an object",
        "answer.no_pages": "it has no pages",
        "answer.page_without_text": "a page comes without its text",
        "answer.tables_not_list": "the tables of a page are not a list",
        "answer.too_many_lines": "it has more than {count} lines of tables on one page",
        "answer.no_answer": "it has no answer",
        "answer.empty": "it came empty",
        "answer.cut": "it was cut before the end",
        "answer.not_json": "it is not JSON",
        "answer.no_rows": "the list “rows” is missing",
        "answer.no_columns": "the list “columns” is missing",
        "answer.too_many_people": "it has more than {count} people on one page",
        "answer.person_not_object": "a person is not an object",
        "answer.not_text": "“{field}” is neither text nor a number",
        "lector.description": "Reader of scanned rolls, with its screens in the browser. Nothing leaves this computer.",
        "lector.port": "port on 127.0.0.1 (or {variable}; otherwise a random free one)",
        "lector.no_browser": "do not open the browser (or {variable}=1)",
        "lector.self_test": "check that the reader works, without network, and quit",
        "lector.port_range": "has to be between 0 and 65535",
        "lector.port_busy": "I could not use port {port} of this computer: try another one or leave out --port.",
    },
}
