"""Focus-assist metrics, computed on the uncompressed luma plane.

Two modes, because focusing on a detailed scene and on a lone star are different problems:

- **Scene** (Moon, planets, terrestrial): variance of the Laplacian — rises as edges get crisp, so
  you turn the focuser to *maximize* it. Unreliable on a single star against black, where shot
  noise is itself high-frequency signal.
- **Star** (night default): the brightest star's **HFD** (half-flux diameter) — the diameter that
  encloses half the star's flux. It shrinks toward focus, so you *minimize* it; it's stable and
  near-linear near focus (what SharpCap/NINA use). We also return **peak** intensity (maximize).

Analysis runs on a grayscale ``uint8`` frame. On real hardware and the mock alike it currently comes
from decoding the preview JPEG (:func:`analyze`) — libjpeg is told to emit grayscale at half size
(DCT-domain, cheap on the Pi). A dedicated uncompressed lores luma plane (CONCEPT §4) is deferred; it
destabilized the preview pipeline on hardware, so JPEG-decode is used everywhere for now. Everything
is plain numpy. All analysis can be restricted to a normalized ROI.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

# Normalized rectangle (x0, y0, x1, y1) in [0, 1].
ROI = tuple[float, float, float, float]

HIST_BINS = 64
_MIN_ROI_PX = 8
# A star must sit this far above the local background (in luma counts) to be measured — otherwise
# HFD is meaningless and we report "no star" rather than a misleadingly tiny diameter.
_STAR_MIN_PEAK = 15.0
# HFD is measured in a window around the brightest star, not over the whole ROI — otherwise a wide
# box full of faint stars inflates the diameter. Radius in pixels (covers a well-defocused star).
_STAR_WINDOW_PX = 24


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


def _star_metrics(region: np.ndarray) -> dict:
    """HFD + peak of the *brightest* star in ``region`` (background-subtracted, flux-weighted).

    The brightest pixel locates the star; HFD is then measured only in a window around it, so a wide
    ROI containing several faint stars doesn't inflate the diameter. HFD = 2·Σ(vᵢ·rᵢ) / Σ(vᵢ) — the
    flux-weighted mean radius doubled, i.e. the diameter enclosing half the flux. Returns
    ``found=False`` when nothing rises far enough above the background to trust.
    """
    if region.size == 0:
        return {"found": False, "hfd": 0.0, "peak": 0.0}
    bg = float(np.median(region))
    peak_above_bg = float(region.max()) - bg
    if peak_above_bg < _STAR_MIN_PEAK:
        return {"found": False, "hfd": 0.0, "peak": round(max(0.0, peak_above_bg), 1)}

    # Window the brightest star out of the ROI before measuring.
    py, px = np.unravel_index(int(np.argmax(region)), region.shape)
    r = _STAR_WINDOW_PX
    win = region[max(py - r, 0) : py + r + 1, max(px - r, 0) : px + r + 1]

    signal = np.clip(win - bg, 0.0, None)
    peak = float(signal.max())
    total = float(signal.sum())
    if peak < _STAR_MIN_PEAK or total <= 0.0:
        return {"found": False, "hfd": 0.0, "peak": round(peak, 1)}

    ys, xs = np.indices(signal.shape)
    cx = float((xs * signal).sum() / total)
    cy = float((ys * signal).sum() / total)
    rad = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    hfd = 2.0 * float((signal * rad).sum() / total)
    return {"found": True, "hfd": round(hfd, 2), "peak": round(peak, 1)}


def analyze_luma(luma: np.ndarray, roi: ROI | None = None, mode: str = "scene") -> dict:
    """Compute focus/histogram/clipping metrics from a grayscale (uint8) luma frame."""
    region = _crop(luma.astype(np.float32), roi)

    counts, _ = np.histogram(region, bins=HIST_BINS, range=(0.0, 255.0))
    clipping = float((region >= 254.0).mean())

    result: dict = {
        "histogram": counts.astype(int).tolist(),
        "clipping": round(clipping, 4),
        "roi": list(roi) if roi else None,
        "focus_mode": mode,
    }

    if mode == "star":
        star = _star_metrics(region)
        # HFD is the focus number (minimize); peak is the secondary "maximize" cue.
        result.update(
            {
                "focus_score": star["hfd"],
                "focus_metric": "HFD",
                "focus_direction": "lower",
                "hfd": star["hfd"],
                "peak": star["peak"],
                "star_found": star["found"],
            }
        )
    else:
        result.update(
            {
                "focus_score": round(_laplacian_variance(region), 2),
                "focus_metric": "Laplacian",
                "focus_direction": "higher",
            }
        )
    return result


def analyze(jpeg: bytes, roi: ROI | None = None, mode: str = "scene") -> dict:
    """Decode a preview JPEG to luma and analyze it.

    ``draft`` lets libjpeg emit grayscale at half resolution straight from the DCT coefficients —
    several times cheaper than a full RGB decode + convert, which matters at ``focus_hz`` on a Pi.
    The metric is scale-invariant (you minimize/maximize a trend), so the downscale is harmless.
    """
    img = Image.open(io.BytesIO(jpeg))
    img.draft("L", (img.width // 2, img.height // 2))
    luma = np.asarray(img.convert("L"))
    return analyze_luma(luma, roi, mode)
