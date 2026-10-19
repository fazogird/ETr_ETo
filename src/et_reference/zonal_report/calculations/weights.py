"""Dala ↔ piksel ulushlari: har bir dalaning har bir pikselga tushgan qismi (aniq kesishma yuzasi)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import shapely

from ..preprocessing.rasters import RasterGrid


@dataclass(frozen=True)
class PixelWeights:
    """Siyrak (dala, piksel, ulush) uchliklari. Bir marta hisoblanib, barcha rasterlar uchun ishlatiladi."""

    field: np.ndarray          # (k,) dala indeksi
    pixel: np.ndarray          # (k,) tekislangan piksel indeksi (qator * kenglik + ustun)
    fraction: np.ndarray       # (k,) dalaning shu pikselga tushgan ulushi [0..1]
    total_fraction: np.ndarray # (n_fields,) raster ichiga tushgan jami ulush
    anchors: np.ndarray        # (n_fields, 2) dala ichidagi nuqta (x, y); bo'sh geometriya uchun NaN
    n_fields: int


def build_pixel_weights(geometries: np.ndarray, grid: RasterGrid, chunk_size: int = 2_000_000) -> PixelWeights:
    """Har bir dala bbox'iga tushgan piksellar bilan aniq kesishma yuzasini hisoblaydi.

    Ulush raster CRS'dagi yuzalar nisbati (bir piksel ichida kenglik bo'yicha buzilish
    e'tiborsiz darajada kichik). Katta rasterlarda xotira uchun dalalar bo'laklarga bo'linadi.
    """
    geoms = np.asarray(geometries, dtype=object)
    n = len(geoms)
    t, width, height = grid.transform, grid.width, grid.height
    usable = ~(shapely.is_missing(geoms) | shapely.is_empty(geoms))

    bounds = np.full((n, 4), np.nan)
    bounds[usable] = shapely.bounds(geoms[usable])
    col0 = np.floor((bounds[:, 0] - t.c) / t.a)
    col1 = np.floor((bounds[:, 2] - t.c) / t.a)
    row0 = np.floor((bounds[:, 3] - t.f) / t.e)  # t.e < 0: yuqori chekka — kichik qator
    row1 = np.floor((bounds[:, 1] - t.f) / t.e)
    overlaps = usable & (col1 >= 0) & (col0 <= width - 1) & (row1 >= 0) & (row0 <= height - 1)

    def window(low, high, size):
        lo = np.where(overlaps, np.clip(low, 0, size - 1), 0).astype(np.int64)
        hi = np.where(overlaps, np.clip(high, 0, size - 1), 0).astype(np.int64)
        return lo, hi

    c0, c1 = window(col0, col1, width)
    r0, r1 = window(row0, row1, height)
    ncols = c1 - c0 + 1
    counts = np.where(overlaps, (r1 - r0 + 1) * ncols, 0)
    cumulative = np.cumsum(counts)
    areas = np.where(usable, shapely.area(np.where(usable, geoms, None)), 0.0)

    fields, pixels, fractions = [], [], []
    start = 0
    while start < n:
        base = cumulative[start - 1] if start else 0
        end = max(int(np.searchsorted(cumulative, base + chunk_size, side="right")), start + 1)
        cnt = counts[start:end]
        total = int(cnt.sum())
        if total:
            f = np.repeat(np.arange(start, end), cnt)
            first = np.cumsum(cnt) - cnt
            within = np.arange(total) - np.repeat(first, cnt)
            row = r0[f] + within // ncols[f]
            col = c0[f] + within % ncols[f]
            xmin = t.c + col * t.a
            ymax = t.f + row * t.e
            cells = shapely.box(xmin, ymax + t.e, xmin + t.a, ymax)
            with np.errstate(divide="ignore", invalid="ignore"):
                share = shapely.area(shapely.intersection(geoms[f], cells)) / areas[f]
            keep = np.isfinite(share) & (share > 1e-12)
            fields.append(f[keep])
            pixels.append((row * width + col)[keep])
            fractions.append(share[keep])
        start = end

    field = np.concatenate(fields) if fields else np.empty(0, dtype=np.int64)
    pixel = np.concatenate(pixels) if pixels else np.empty(0, dtype=np.int64)
    fraction = np.concatenate(fractions) if fractions else np.empty(0)

    anchors = np.full((n, 2), np.nan)
    anchors[usable] = shapely.get_coordinates(shapely.point_on_surface(geoms[usable]))
    return PixelWeights(
        field=field,
        pixel=pixel,
        fraction=fraction,
        total_fraction=np.bincount(field, weights=fraction, minlength=n),
        anchors=anchors,
        n_fields=n,
    )
