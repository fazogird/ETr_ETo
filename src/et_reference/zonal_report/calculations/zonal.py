"""Zonal o'rtacha: dala ichidagi piksellar bo'yicha ulush-vaznli, NoData uchun eng yaqin piksel bilan to'ldirish."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from ..preprocessing.rasters import RasterGrid
from .weights import PixelWeights

# Holat kodlari (kattaroq = yomonroq)
STATUS_OK = 0        # dala butunlay yaroqli piksellarga tushgan
STATUS_PARTIAL = 1   # dalaning bir qismi NoData'ga tushgan: yaroqli qismi bo'yicha o'rtacha
STATUS_FILLED = 2    # to'liq NoData: eng yaqin yaroqli pikseldan olingan
STATUS_NODATA = 3    # qiymat topilmadi
STATUS_LABELS = {
    STATUS_OK: "to'liq yaroqli",
    STATUS_PARTIAL: "qisman NoData (yaroqli qismi bo'yicha)",
    STATUS_FILLED: "NoData: eng yaqin yaroqli pikseldan to'ldirilgan",
    STATUS_NODATA: "qiymat yo'q",
}


@dataclass(frozen=True)
class ZonalResult:
    mean: np.ndarray    # (n_fields,) mm; qiymat yo'q bo'lsa NaN
    status: np.ndarray  # (n_fields,) int8


def zonal_mean(
    weights: PixelWeights, values: np.ndarray, grid: RasterGrid, max_fill_pixels: float = 2.0
) -> ZonalResult:
    n = weights.n_fields
    sampled = values.ravel()[weights.pixel]
    valid = np.isfinite(sampled)
    share = np.where(valid, weights.fraction, 0.0)
    numerator = np.bincount(weights.field, weights=share * np.where(valid, sampled, 0.0), minlength=n)
    denominator = np.bincount(weights.field, weights=share, minlength=n)

    has_value = denominator > 0
    mean = np.full(n, np.nan)
    mean[has_value] = numerator[has_value] / denominator[has_value]
    status = np.full(n, STATUS_NODATA, dtype=np.int8)
    complete = denominator >= weights.total_fraction * (1 - 1e-6)
    status[has_value] = np.where(complete[has_value], STATUS_OK, STATUS_PARTIAL)

    missing = np.flatnonzero(~has_value & np.isfinite(weights.anchors[:, 0]))
    if missing.size:
        filled, ok = _nearest_valid(values, grid, weights.anchors[missing], max_fill_pixels)
        mean[missing[ok]] = filled[ok]
        status[missing[ok]] = STATUS_FILLED
    return ZonalResult(mean, status)


def _nearest_valid(
    values: np.ndarray, grid: RasterGrid, points: np.ndarray, max_fill_pixels: float
) -> tuple[np.ndarray, np.ndarray]:
    """Har bir nuqta uchun eng yaqin yaroqli piksel qiymati va masofa chegarasiga sig'ganligi."""
    none = np.full(len(points), np.nan), np.zeros(len(points), dtype=bool)
    valid = np.isfinite(values)
    if not valid.any():
        return none
    t = grid.transform
    _, (nearest_row, nearest_col) = ndimage.distance_transform_edt(
        ~valid, sampling=(abs(t.e), t.a), return_indices=True
    )
    x, y = points[:, 0], points[:, 1]
    row = np.clip(np.floor((y - t.f) / t.e), 0, grid.height - 1).astype(np.int64)
    col = np.clip(np.floor((x - t.c) / t.a), 0, grid.width - 1).astype(np.int64)
    rr, cc = nearest_row[row, col], nearest_col[row, col]
    centre_x = t.c + (cc + 0.5) * t.a
    centre_y = t.f + (rr + 0.5) * t.e
    distance = np.hypot(centre_x - x, centre_y - y)  # haqiqiy nuqtadan, ya'ni raster tashqarisidagi dalalar uchun ham to'g'ri
    return values[rr, cc], distance <= max_fill_pixels * max(t.a, abs(t.e))
