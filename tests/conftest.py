from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box


@pytest.fixture
def boundary_file(tmp_path: Path) -> Path:
    """Sintetik tarmoqni (41.0/40.9 N, 69.0–69.2 E) to'liq qoplaydigan bitta "viloyat"."""
    gdf = gpd.GeoDataFrame(
        {"shapeName": ["Test viloyati"]},
        geometry=[box(68.97, 40.87, 69.23, 41.03)],
        crs="EPSG:4326",
    )
    path = tmp_path / "boundaries.geojson"
    gdf.to_file(path, driver="GeoJSON")
    return path
