"""Regulyar lat/lon tarmog'idan EPSG:4326 GeoTIFF yozish va hudud niqobi."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import Affine

CRS = "EPSG:4326"


@dataclass(frozen=True)
class GridSpec:
    transform: Affine
    width: int
    height: int
    crs: str = CRS


def grid_from_coords(latitude: np.ndarray, longitude: np.ndarray, rtol: float = 1e-3) -> GridSpec:
    """Piksel MARKAZI koordinatalaridan affine transform (chap yuqori burchak = markaz − res/2)."""
    lat = np.asarray(latitude, dtype="float64")
    lon = np.asarray(longitude, dtype="float64")
    if lat.size < 2 or lon.size < 2:
        raise ValueError("Tarmoqda har bir o'q bo'yicha kamida 2 ta piksel bo'lishi kerak")
    dlat, dlon = np.diff(lat), np.diff(lon)
    if not (np.all(dlat < 0) and np.all(dlon > 0)):
        raise ValueError("Kenglik kamayuvchi, uzunlik o'suvchi bo'lishi kerak")
    res_y, res_x = float(-dlat.mean()), float(dlon.mean())
    if not (np.allclose(-dlat, res_y, rtol=rtol) and np.allclose(dlon, res_x, rtol=rtol)):
        raise ValueError("Tarmoq regulyar emas: piksel o'lchamlari bir xil emas")
    transform = Affine(res_x, 0.0, lon[0] - res_x / 2, 0.0, -res_y, lat[0] + res_y / 2)
    return GridSpec(transform=transform, width=lon.size, height=lat.size)


def region_mask(geometries: Iterable, grid: GridSpec, all_touched: bool = True) -> np.ndarray:
    """Hudud ichidagi piksellar uchun True."""
    return geometry_mask(
        list(geometries),
        out_shape=(grid.height, grid.width),
        transform=grid.transform,
        all_touched=all_touched,
        invert=True,
    )


def write_geotiff(
    path: Path,
    data: np.ndarray,
    grid: GridSpec,
    *,
    nodata: float,
    description: str,
    tags: Mapping[str, str] | None = None,
    dtype: str = "float32",
) -> Path:
    """Bitta qatlamli siqilgan GeoTIFF; NaN -> nodata. Avval vaqtinchalik faylga yoziladi."""
    data = np.asarray(data)
    if data.shape != (grid.height, grid.width):
        raise ValueError(f"Massiv shakli {data.shape} tarmoqqa mos emas {(grid.height, grid.width)}")
    is_float = np.issubdtype(np.dtype(dtype), np.floating)
    out = np.where(np.isfinite(data), data, nodata).astype(dtype)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    profile = {
        "driver": "GTiff",
        "height": grid.height,
        "width": grid.width,
        "count": 1,
        "dtype": dtype,
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": nodata,
        "compress": "deflate",
        "predictor": 3 if is_float else 2,
    }
    with rasterio.open(partial, "w", **profile) as dst:
        dst.write(out, 1)
        dst.set_band_description(1, description)
        if tags:
            dst.update_tags(**{k: str(v) for k, v in tags.items()})
    os.replace(partial, path)
    return path
