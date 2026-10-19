"""Rasterlarni o'qish: NoData -> NaN, barcha rasterlar bir xil tarmoqda ekanini tekshirish."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine

from ..discovery import RasterCatalog


@dataclass(frozen=True)
class RasterGrid:
    transform: Affine
    width: int
    height: int
    crs: CRS


@dataclass(frozen=True)
class RasterStack:
    grid: RasterGrid
    arrays: dict[tuple[str, int], np.ndarray]  # (o'zgaruvchi, oy) -> (H, W) float64, NoData = NaN


def load_raster_stack(catalog: RasterCatalog, nodata: float) -> RasterStack:
    grid: RasterGrid | None = None
    arrays: dict[tuple[str, int], np.ndarray] = {}
    for ref in catalog.refs:
        with rasterio.open(ref.path) as src:
            if src.crs is None:
                raise ValueError(f"{ref.path.name}: rasterda CRS yo'q")
            current = RasterGrid(src.transform, src.width, src.height, src.crs)
            data = src.read(1, masked=True).astype("float64").filled(np.nan)
        data[~np.isfinite(data) | (data == nodata)] = np.nan  # fayl NoData'si e'lon qilinmagan bo'lsa ham
        if grid is None:
            _check_north_up(current, ref.path.name)
            grid = current
        elif not _same_grid(grid, current):
            raise ValueError(
                f"{ref.path.name}: tarmoq (CRS/o'lcham/transform) boshqa rasterlardan farq qiladi. "
                "Barcha rasterlar bir xil tarmoqda bo'lishi kerak."
            )
        arrays[(ref.variable, ref.month)] = data
    assert grid is not None
    return RasterStack(grid, arrays)


def _check_north_up(grid: RasterGrid, name: str) -> None:
    t = grid.transform
    if t.b != 0 or t.d != 0 or t.a <= 0 or t.e >= 0:
        raise ValueError(f"{name}: faqat shimol tepada, burilmagan rasterlar qo'llab-quvvatlanadi")


def _same_grid(a: RasterGrid, b: RasterGrid) -> bool:
    return (
        a.crs == b.crs
        and (a.width, a.height) == (b.width, b.height)
        and all(np.isclose(x, y, rtol=0, atol=1e-9 * max(1.0, abs(x))) for x, y in zip(a.transform, b.transform))
    )
