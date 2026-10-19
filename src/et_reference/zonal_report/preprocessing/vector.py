"""Ekin dalalari (shp): o'qish, geometriyani tuzatish, CRS moslash va maydon hisoblash."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import CRS as ProjCRS
from rasterio.crs import CRS as RasterCRS

from ..settings import AUTO_AREA_CRS

log = logging.getLogger("et_reference")

_AREA_NAMES = {"area", "maydon", "shape_area", "shape_are", "area_ga", "area_ha", "ga", "ha", "gektar", "hectare"}


@dataclass
class Fields:
    frame: gpd.GeoDataFrame            # asl shp: asl CRS, asl ustunlar (o'zgartirilmaydi)
    geometries: np.ndarray             # hisob uchun geometriya: raster CRS'da, tuzatilgan
    area_m2: np.ndarray                # teng-maydonli CRS'da hisoblangan maydon, m²
    area_crs: ProjCRS
    crop: pd.Series | None             # ekin turi (yoki None)
    notes: dict = field(default_factory=dict)  # sifat nazorati uchun


def resolve_area_crs(frame: gpd.GeoDataFrame, spec: str) -> ProjCRS:
    key = str(spec).strip().lower()
    if key == "auto":
        crs = ProjCRS.from_user_input(AUTO_AREA_CRS)
    elif key == "utm":
        crs = frame.estimate_utm_crs()
    else:
        crs = ProjCRS.from_user_input(spec)
    if not crs.is_projected:
        raise ValueError(f"Maydon CRS'i proyeksiyalangan (metrli) bo'lishi kerak, '{spec}' bunday emas")
    return crs


def load_fields(
    shp_path: Path,
    raster_crs: RasterCRS,
    *,
    area_crs: str = "auto",
    crop_column: str | None = None,
) -> Fields:
    frame = gpd.read_file(shp_path)
    if frame.crs is None:
        raise ValueError(f"{Path(shp_path).name}: CRS aniqlanmadi (.prj fayli yo'q). Avval CRS belgilang.")
    if frame.empty:
        raise ValueError(f"{Path(shp_path).name}: bironta ham obyekt yo'q")
    if not frame.geom_type.dropna().isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Shp faqat poligon (Polygon/MultiPolygon) bo'lishi kerak")
    frame = frame.reset_index(drop=True)

    raw = frame.geometry.to_numpy()
    empty = shapely.is_missing(raw) | shapely.is_empty(raw)
    fixed, n_fixed = _repair(raw, empty)

    target = ProjCRS.from_user_input(raster_crs.to_wkt())
    in_raster_crs = gpd.GeoSeries(fixed, crs=frame.crs).to_crs(target).to_numpy()  # raster o'zgarmaydi, shp moslanadi
    metric = resolve_area_crs(frame, area_crs)
    area_m2 = np.asarray(gpd.GeoSeries(fixed, crs=frame.crs).to_crs(metric).area, dtype="float64")

    crop = None
    if crop_column:
        crop = frame[_resolve_column(frame, crop_column)].astype("string").str.strip().fillna("Noma'lum")
        crop = crop.mask(crop == "", "Noma'lum")

    notes = {
        "shp_crs": frame.crs.to_string(),
        "raster_crs": raster_crs.to_string(),
        "area_crs": metric.to_string(),
        "n_fields": len(frame),
        "n_empty": int(empty.sum()),
        "n_repaired": n_fixed,
        "crs_aligned": bool(frame.crs != target),
    }
    notes["area_column"] = compare_area_column(frame, area_m2 / 10_000.0)
    log.info("Dalalar: %d ta; shp CRS=%s, raster CRS=%s, maydon CRS=%s",
             len(frame), notes["shp_crs"], notes["raster_crs"], notes["area_crs"])
    return Fields(frame, in_raster_crs, area_m2, metric, crop, notes)


def _repair(geoms: np.ndarray, empty: np.ndarray) -> tuple[np.ndarray, int]:
    """Yaroqsiz geometriyalarni tuzatadi (faqat hisob uchun; asl shp'dagi geometriya o'zgarmaydi)."""
    out = geoms.copy()
    bad = ~empty & ~shapely.is_valid(np.where(empty, None, geoms))
    for i in np.flatnonzero(bad):
        parts = [g for g in shapely.get_parts(shapely.make_valid(geoms[i]))
                 if g.geom_type in ("Polygon", "MultiPolygon")]
        out[i] = shapely.union_all(parts) if parts else shapely.Polygon()
    return out, int(bad.sum())


def _resolve_column(frame: gpd.GeoDataFrame, name: str) -> str:
    if name in frame.columns:
        return name
    lowered = {str(c).casefold(): c for c in frame.columns}
    if name.casefold() in lowered:
        return lowered[name.casefold()]
    raise ValueError(f"'{name}' ustuni shp'da yo'q. Mavjud ustunlar: {[c for c in frame.columns if c != 'geometry']}")


def compare_area_column(frame: gpd.GeoDataFrame, area_ha: np.ndarray) -> dict | None:
    """Shp'dagi tayyor maydon ustunini bizning hisobimiz bilan solishtiradi (birlik/CRS ni aniqlash uchun)."""
    for col in frame.columns:
        if str(col).casefold() in _AREA_NAMES and pd.api.types.is_numeric_dtype(frame[col]):
            given = frame[col].to_numpy(dtype="float64")
            ok = np.isfinite(given) & (given > 0) & (area_ha > 0)
            if not ok.any():
                continue
            ratio = float(np.median(given[ok] / area_ha[ok]))
            if 0.95 <= ratio <= 1.05:
                unit = "gektar (bizning hisobga mos)"
            elif 9_500 <= ratio <= 10_500:
                unit = "kvadrat metr (m²)"
            else:
                unit = "noma'lum birlik yoki boshqa CRS'da hisoblangan"
            return {"column": str(col), "median_ratio_to_ga": ratio, "interpretation": unit}
    return None
