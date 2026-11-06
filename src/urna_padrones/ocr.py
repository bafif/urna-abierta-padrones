"""Read the text of an image with a local model. Nothing leaves this computer.

Import this module before anything else imports onnxruntime: see ORT_DISABLE_TELEMETRY below.

The recognition model is the one that ships inside the rapidocr package, so reading works
without internet from the first run. URNA_PADRONES_MODELO may point at another ONNX
recognition model with its character list inside, as every rapidocr model has.
"""

import logging
import os
import threading
from importlib import resources
from pathlib import Path

# onnxruntime reports usage to Microsoft over the internet and leaves a .ses file in the temp
# folder unless this is set before it is first imported. Setting it later has no effect.
os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")

import cv2
import numpy as np
import onnxruntime
import rapidocr
from rapidocr import RapidOCR
from rapidocr.utils.download_file import DownloadFile
from rapidocr.utils.process_img import ResizeImgError

# The Windows builds can also report usage events to the system.
if hasattr(onnxruntime, "disable_telemetry_events"):
    onnxruntime.disable_telemetry_events()

# Its warnings speak of things nobody reading a roll can fix, like the devices of a virtual machine: only its errors
# are worth a line in the terminal.
onnxruntime.set_default_logger_severity(3)

MODEL_VARIABLE = "URNA_PADRONES_MODELO"
BUNDLED_MODEL = "PP-OCRv6_rec_small.onnx"
# A small image of invented cells, one above the other, made by tests/make_ocr_sample.py.
SAMPLE_IMAGE = "ocr_sample.png"
SAMPLE_TEXT = ("Prueba, Ana", "Núñez, Inés", "99001234", "A-1234/5", "Ingeniería Civil")
SAMPLE_CELL_HEIGHT = 56

logger = logging.getLogger(__name__)
_local = threading.local()


def _refuse_download(*args, **kwargs):
    raise RuntimeError(
        "El lector nunca baja nada de internet: el modelo tiene que estar en la computadora. "
        "/ The reader never downloads anything: the model has to be on this computer."
    )


# rapidocr downloads a model or a character list it cannot find. This program must never send
# or fetch anything, so its downloader refuses instead.
DownloadFile.run = staticmethod(_refuse_download)


def bundled_model() -> Path:
    """The recognition model inside the installed rapidocr package."""
    return Path(rapidocr.__file__).resolve().parent / "models" / BUNDLED_MODEL


def model_path() -> Path:
    """The model to use: URNA_PADRONES_MODELO if it is set, the bundled one otherwise."""
    override = os.environ.get(MODEL_VARIABLE, "").strip()
    path = Path(override).expanduser() if override else bundled_model()
    if not path.is_file():
        raise FileNotFoundError(f"No encuentro el modelo de lectura / The reading model is missing: {path}")
    return path


def create_engine() -> RapidOCR:
    """A new engine using one thread: pages are already read in parallel."""
    return RapidOCR(
        params={
            "Global.use_det": False,
            "Global.use_cls": False,
            "Global.log_level": "error",
            "Rec.lang_type": "es",
            "Rec.model_path": str(model_path()),
            "EngineConfig.onnxruntime.intra_op_num_threads": 1,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        }
    )


def _get_engine() -> RapidOCR:
    """One engine per thread, created the first time that thread reads a cell."""
    engine = getattr(_local, "engine", None)
    if engine is None:
        engine = _local.engine = create_engine()
    return engine


def tight_crop(image: np.ndarray, margin: int = 3) -> np.ndarray:
    """Cut the image down to its ink.

    The model scales every line to a fixed height. Without the empty space around the text,
    letters come out larger, which measurably reduces confusions such as i, l and t.
    """
    ink = image < 128
    rows = np.where(ink.sum(axis=1) >= 2)[0]
    columns = np.where(ink.sum(axis=0) >= 1)[0]
    if rows.size == 0 or columns.size == 0:
        return image
    # Specks left by the ruling lines are ignored: the text is the tallest run of rows with ink.
    line = max(np.split(rows, np.where(np.diff(rows) > 3)[0] + 1), key=len)
    top, bottom = max(0, line[0] - margin), min(image.shape[0], line[-1] + 1 + margin)
    left, right = max(0, columns[0] - margin * 2), min(image.shape[1], columns[-1] + 1 + margin * 2)
    return image[top:bottom, left:right]


def read_cell(image: np.ndarray) -> tuple[str, float]:
    """Return the text of a grayscale image holding a single line, and how sure the model is.

    An image the model cannot bring to its size, such as a speck far wider than high on a page that is not a
    table, has no text.
    """
    framed = cv2.copyMakeBorder(tight_crop(image), 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=255)
    try:
        result = _get_engine()(cv2.cvtColor(framed, cv2.COLOR_GRAY2BGR), use_det=False, use_cls=False, use_rec=True)
    except ResizeImgError:
        return "", 0.0
    if not result.txts:
        return "", 0.0
    return " ".join(result.txts), float(min(result.scores))


def sample_cells() -> list[np.ndarray]:
    """The cells of the bundled sample image, from top to bottom."""
    data = (resources.files(__package__) / SAMPLE_IMAGE).read_bytes()
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    height = SAMPLE_CELL_HEIGHT
    return [image[i * height : (i + 1) * height] for i in range(len(SAMPLE_TEXT))]


def self_test() -> bool:
    """Read the bundled image of invented cells and check the text, without any network.

    Meant for a program to check, when it starts, that the model loads and reads. Any failure,
    including a missing model, returns False and is logged.
    """
    try:
        for cell, expected in zip(sample_cells(), SAMPLE_TEXT, strict=True):
            text, _ = read_cell(cell)
            if text != expected:
                logger.error("self test: expected %r, read %r", expected, text)
                return False
    except Exception:
        logger.exception("self test failed")
        return False
    return True
