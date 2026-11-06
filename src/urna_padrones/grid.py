"""Find the table grid of a scanned page and remove its ruling lines."""

from dataclasses import dataclass

import cv2
import numpy as np

MAX_SKEW_DEGREES = 3.0


@dataclass(frozen=True)
class Grid:
    columns: list[int]
    rows: list[tuple[int, int]]


def binarize(gray: np.ndarray) -> np.ndarray:
    """Return an image where ink is 255 and paper is 0."""
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


def estimate_skew(binary: np.ndarray) -> float:
    """Estimate the rotation of the page, in degrees, from its long horizontal lines."""
    runs = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((1, 40), np.uint8))
    lines = cv2.HoughLinesP(
        runs,
        rho=1,
        theta=np.pi / 3600,
        threshold=200,
        minLineLength=binary.shape[1] // 3,
        maxLineGap=25,
    )
    if lines is None:
        return 0.0
    angles = [np.degrees(np.arctan2(y2 - y1, x2 - x1)) for x1, y1, x2, y2 in lines.reshape(-1, 4)]
    angles = [a for a in angles if abs(a) <= MAX_SKEW_DEGREES]
    return float(np.median(angles)) if angles else 0.0


def rotate(gray: np.ndarray, angle: float) -> np.ndarray:
    if abs(angle) < 0.02:
        return gray
    height, width = gray.shape
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(gray, matrix, (width, height), flags=cv2.INTER_CUBIC, borderValue=255)


def line_masks(binary: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return masks with only the horizontal and only the vertical ruling lines."""
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((1, 40), np.uint8))
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((36, 1), np.uint8))
    return horizontal, vertical


def _cluster(indices: np.ndarray, weights: np.ndarray, gap: int) -> list[int]:
    if indices.size == 0:
        return []
    groups = np.split(indices, np.where(np.diff(indices) > gap)[0] + 1)
    return [int(round(np.average(g, weights=weights[g]))) for g in groups]


def separators(mask: np.ndarray, axis: int, min_fraction: float, gap: int = 8) -> list[int]:
    """Positions along `axis` where a ruling line covers at least `min_fraction` of the table."""
    projection = (mask > 0).sum(axis=axis).astype(np.float64)
    if projection.max(initial=0) == 0:
        return []
    threshold = projection.max() * min_fraction
    return _cluster(np.where(projection >= threshold)[0], projection, gap)


def drop_close(positions: list[int], minimum: int) -> list[int]:
    kept: list[int] = []
    for position in positions:
        if not kept or position - kept[-1] >= minimum:
            kept.append(position)
    return kept


def _vertical_extent(vertical: np.ndarray) -> tuple[int, int]:
    """Top and bottom of the table: the rows crossed by more than a few vertical lines."""
    crossings = (vertical > 0).sum(axis=1)
    rows = np.where(crossings >= 6)[0]
    if rows.size == 0:
        return 0, vertical.shape[0]
    return int(rows[0]), int(rows[-1])


def text_bands(ink: np.ndarray, x_ranges: list[tuple[int, int]], top: int, bottom: int) -> list[tuple[int, int]]:
    """Find the vertical span of every text row from the ink of the given columns."""
    profile = np.zeros(ink.shape[0], dtype=np.float64)
    for x0, x1 in x_ranges:
        profile += (ink[:, x0 + 6 : x1 - 6] > 0).sum(axis=1)
    profile[: top + 1] = 0
    profile[bottom:] = 0
    smooth = np.convolve(profile, np.ones(3) / 3, mode="same")
    active = smooth[smooth > 0]
    if active.size == 0:
        return []
    threshold = max(3.0, 0.08 * float(np.percentile(active, 90)))
    on = np.where(smooth >= threshold)[0]
    if on.size == 0:
        return []
    groups = np.split(on, np.where(np.diff(on) > 2)[0] + 1)
    return [(int(g[0]), int(g[-1]) + 1) for g in groups if g[-1] - g[0] >= 10]


def split_merged(bands: list[tuple[int, int]], pitch: float) -> list[tuple[int, int]]:
    """Split bands that joined two or more text rows because a row touches the next one."""
    height = float(np.median([b - a for a, b in bands]))
    result: list[tuple[int, int]] = []
    for start, stop in bands:
        count = 1 + int(round(max(0, stop - start - height) / pitch))
        if count == 1:
            result.append((start, stop))
            continue
        result.extend(
            (round(start + i * pitch), round(start + i * pitch + height)) for i in range(count)
        )
    return result


def row_lattice(bands: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Turn text bands into evenly spaced rows, interpolating the rows that left no band.

    The steps are measured locally, because a sheet feeder does not move the paper at a
    perfectly constant speed.
    """
    if len(bands) < 3:
        return bands
    starts = [a for a, _ in bands]
    pitch = float(np.median(np.diff(starts)))
    bands = split_merged(bands, pitch)
    centers = np.array([(a + b) / 2 for a, b in bands], dtype=np.float64)
    diffs = np.diff(centers)
    pitch = float(np.median(diffs))
    steps = np.maximum(1, np.round(diffs / pitch)).astype(int)
    numbers = np.concatenate(([0], np.cumsum(steps)))
    every = np.arange(numbers[-1] + 1)
    positions = np.interp(every, numbers, centers)
    half = pitch / 2
    return [(int(round(c - half)), int(round(c + half))) for c in positions]


def find_grid(gray: np.ndarray, row_columns: tuple[int, ...] = (0, 1, 4)) -> tuple[Grid, np.ndarray]:
    """Return the grid and a copy of the page without ruling lines.

    Columns come from the vertical ruling lines. Rows come from the text, because in a
    photocopy the horizontal rules are often too thin or broken to rely on. `row_columns`
    says which table columns hold text in every row.
    """
    binary = binarize(gray)
    horizontal, vertical = line_masks(binary)
    # A line that is still slightly slanted spreads over several pixel columns: widening the
    # mask gathers it again, so that it is not lost to the threshold.
    widened = cv2.dilate(vertical, np.ones((1, 9), np.uint8))
    columns = drop_close(separators(widened, axis=0, min_fraction=0.3), 20)
    lines = cv2.dilate(cv2.bitwise_or(horizontal, vertical), np.ones((3, 3), np.uint8))
    clean = gray.copy()
    clean[lines > 0] = 255
    ink = binary.copy()
    ink[lines > 0] = 0
    if len(columns) < 3:
        return Grid(columns=columns, rows=[]), clean
    top, bottom = _vertical_extent(vertical)
    ranges = [(columns[i], columns[i + 1]) for i in row_columns if i + 1 < len(columns)]
    rows = row_lattice(text_bands(ink, ranges, top, bottom))
    return Grid(columns=columns, rows=rows), clean


def even_out_light(gray: np.ndarray) -> np.ndarray:
    """A photo lit unevenly, made even like a scan: the paper turns white everywhere and the ink stays dark.

    The light on the paper is measured without the ink, taking the brightest pixel around each one over
    a window wider than any stroke and blurring that, and every pixel is divided by it.
    """
    paper = cv2.dilate(gray, np.ones((15, 15), np.uint8))
    small = cv2.resize(paper, None, fx=0.125, fy=0.125, interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), 3)
    paper = cv2.resize(small, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_LINEAR)
    return cv2.divide(gray, np.maximum(paper, 1), scale=255)


def straighten(gray: np.ndarray) -> tuple[np.ndarray, float]:
    angle = estimate_skew(binarize(gray))
    return rotate(gray, angle), angle
