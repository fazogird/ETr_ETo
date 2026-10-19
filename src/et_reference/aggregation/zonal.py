"""Viloyat bo'yicha maydon-vaznli o'rtacha: pikselning poligon ichidagi ulushi × cos(kenglik)."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from rasterio.features import geometry_mask
from rasterio.transform import Affine

from ..output.rasters import GridSpec


def coverage_fraction(geometries: Iterable, grid: GridSpec, supersample: int = 10) -> np.ndarray:
    """Har bir pikselning poligon ichida qolgan ulushi [0..1].

    Piksel `supersample`×`supersample` mayda kataklarga bo'linib, markazi ichkarida
    bo'lganlari sanaladi (0.1° piksel uchun ~1% aniqlik). Kichik birliklar (masalan,
    Toshkent shahri) uchun ham to'g'ri ishlaydi.
    """
    t = grid.transform
    fine = Affine(t.a / supersample, t.b, t.c, t.d, t.e / supersample, t.f)  # shimol tepada tarmoq
    inside = geometry_mask(
        list(geometries),
        out_shape=(grid.height * supersample, grid.width * supersample),
        transform=fine,
        invert=True,
    )
    return inside.reshape(grid.height, supersample, grid.width, supersample).mean(axis=(1, 3))


def area_weights(latitude: np.ndarray, fraction: np.ndarray) -> np.ndarray:
    """Lat/lon pikselining nisbiy maydoni (∝ cos φ) × qoplanish ulushi."""
    return fraction * np.cos(np.deg2rad(np.asarray(latitude, dtype="float64")))[:, np.newaxis]


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    """NaN piksellarni chetlab, vaznli o'rtacha; yaroqli piksel bo'lmasa NaN."""
    valid = np.isfinite(values) & (weights > 0)
    if not valid.any():
        return float("nan")
    return float(np.sum(values[valid] * weights[valid]) / np.sum(weights[valid]))
