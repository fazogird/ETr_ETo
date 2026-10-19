"""Natijani shp'ga yozish: asl ustunlar + ETr/ETo ustunlari (asl fayl o'zgarmaydi)."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np

from .. import naming
from ..calculations.field_table import FieldTable

DBF_FIELD_LIMIT = 255


def write_shapefile(
    frame: gpd.GeoDataFrame,
    table: FieldTable,
    area_ha: np.ndarray,
    path: Path,
    nodata: float,
) -> Path:
    """Asl CRS va geometriya saqlanadi. Qiymati yo'q dalalar `nodata` bilan to'ldiriladi (shp NaN'ni yaxshi saqlamaydi)."""
    new = table.values.round(3).fillna(nodata)
    new[naming.AREA_COLUMN] = np.round(area_ha, 4)
    new[naming.QC_COLUMN] = table.status.astype("int16")

    too_long = [c for c in new.columns if len(c) > naming.SHAPEFILE_NAME_LIMIT]
    if too_long:
        raise ValueError(f"Shp ustun nomlari {naming.SHAPEFILE_NAME_LIMIT} belgidan oshdi: {too_long}")
    out = frame.drop(columns=[c for c in new.columns if c in frame.columns]).join(new)
    if len(out.columns) > DBF_FIELD_LIMIT:
        raise ValueError(f"Shp'da {len(out.columns)} ustun bo'ladi, limit {DBF_FIELD_LIMIT}")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_file(path, driver="ESRI Shapefile", encoding="utf-8")
    return path
