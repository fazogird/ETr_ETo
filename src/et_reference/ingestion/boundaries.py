"""Ma'muriy chegaralar: geoBoundaries (gbOpen) yoki foydalanuvchi fayli."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
import requests

log = logging.getLogger(__name__)

GEOBOUNDARIES_API = "https://www.geoboundaries.org/api/current/gbOpen/{iso3}/{level}/"
TARGET_CRS = "EPSG:4326"


def geoboundaries_path(cache_dir: Path, iso3: str, level: str) -> Path:
    return Path(cache_dir) / f"geoBoundaries-{iso3}-{level}.geojson"


def download_geoboundaries(
    iso3: str,
    level: str,
    cache_dir: Path,
    session: requests.Session | None = None,
    timeout: float = 120.0,
) -> Path:
    """GeoJSON ni bir marta yuklab, keshga saqlaydi (manba metama'lumoti bilan)."""
    target = geoboundaries_path(cache_dir, iso3, level)
    if target.is_file():
        return target
    session = session or requests.Session()
    response = session.get(GEOBOUNDARIES_API.format(iso3=iso3, level=level), timeout=timeout)
    response.raise_for_status()
    meta = response.json()
    if isinstance(meta, list):
        meta = meta[0]
    download_url = meta["gjDownloadURL"]
    log.info("geoBoundaries yuklanmoqda: %s %s", iso3, level)
    data = session.get(download_url, timeout=timeout)
    data.raise_for_status()

    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    partial.write_bytes(data.content)
    partial.replace(target)
    target.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target


def load_boundaries(path: Path) -> gpd.GeoDataFrame:
    """Chegaralarni o'qiydi va EPSG:4326 ga keltiradi; bo'sh/yaroqsiz geometriyalarni tuzatadi."""
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        log.warning("%s da CRS ko'rsatilmagan — EPSG:4326 deb qabul qilindi", Path(path).name)
        gdf = gdf.set_crs(TARGET_CRS)
    elif gdf.crs.to_epsg() != 4326:
        log.info("Chegaralar %s dan EPSG:4326 ga o'tkazilmoqda", gdf.crs.to_string())
        gdf = gdf.to_crs(TARGET_CRS)
    gdf = gdf[~(gdf.geometry.is_empty | gdf.geometry.isna())].copy()
    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        log.warning("%d ta yaroqsiz geometriya make_valid bilan tuzatildi", int(invalid.sum()))
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].make_valid()
    if gdf.empty:
        raise ValueError(f"Chegaralar faylida geometriya yo'q: {path}")
    return gdf
