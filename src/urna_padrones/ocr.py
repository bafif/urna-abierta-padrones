"""Read the text of an image with a local model. Nothing leaves this computer."""

import cv2
import numpy as np
from rapidocr import RapidOCR

_engine: RapidOCR | None = None


def _get_engine() -> RapidOCR:
    """One engine per process, using one thread: pages are already read in parallel."""
    global _engine
    if _engine is None:
        _engine = RapidOCR(
            params={
                "Global.use_det": False,
                "Global.use_cls": False,
                "Global.log_level": "error",
                "Rec.lang_type": "es",
                "EngineConfig.onnxruntime.intra_op_num_threads": 1,
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            }
        )
    return _engine


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
    """Return the text of a grayscale image holding a single line, and how sure the model is."""
    framed = cv2.copyMakeBorder(tight_crop(image), 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=255)
    result = _get_engine()(cv2.cvtColor(framed, cv2.COLOR_GRAY2BGR), use_det=False, use_cls=False, use_rec=True)
    if not result.txts:
        return "", 0.0
    return " ".join(result.txts), float(min(result.scores))
