"""Focus-assist metrics computed from preview JPEG frames.

The key number is a **sharpness score** (variance of the Laplacian): it rises as the image gets
crisper, so you turn the focuser to maximize it. Also returns a luminance **histogram** and a
**clipping** fraction to avoid blown highlights. Everything is plain numpy so it runs on the Pi.

The score is scene-dependent and unbounded, so we return the raw value — the frontend tracks a
rolling maximum to render a 0–100 % bar. All analysis can be restricted to a normalized ROI so the
metric reflects the exact star/edge you're focusing on.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

# Normalized rectangle (x0, y0, x1, y1) in [0, 1].
ROI = tuple[float, float, float, float]

HIST_BINS = 64
_MIN_ROI_PX = 8


def _crop(arr: np.ndarray, roi: ROI | None) -> np.ndarray:
    if roi is None:
        return arr
    h, w = arr.shape
    x0, y0, x1, y1 = roi
    px0, px1 = sorted((int(x0 * w), int(x1 * w)))
    py0, py1 = sorted((int(y0 * h), int(y1 * h)))
    px0, py0 = max(px0, 0), max(py0, 0)
    px1, py1 = min(px1, w), min(py1, h)
    if px1 - px0 < _MIN_ROI_PX or py1 - py0 < _MIN_ROI_PX:
        return arr  # ROI too small / degenerate — fall back to the whole frame
    return arr[py0:py1, px0:px1]


def _laplacian_variance(a: np.ndarray) -> float:
    """Variance of a 4-neighbour Laplacian — the classic passive autofocus sharpness measure."""
    if a.shape[0] < 3 or a.shape[1] < 3:
        return 0.0
    center = a[1:-1, 1:-1]
    lap = -4.0 * center + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
    return float(lap.var())


def analyze(jpeg: bytes, roi: ROI | None = None) -> dict:
    """Decode a preview JPEG and return focus/histogram/clipping metrics."""
    gray = np.asarray(Image.open(io.BytesIO(jpeg)).convert("L"), dtype=np.float32)
    region = _crop(gray, roi)

    score = _laplacian_variance(region)
    counts, _ = np.histogram(region, bins=HIST_BINS, range=(0.0, 255.0))
    clipping = float((region >= 254.0).mean())

    return {
        "focus_score": round(score, 2),
        "histogram": counts.astype(int).tolist(),
        "clipping": round(clipping, 4),
        "roi": list(roi) if roi else None,
    }
