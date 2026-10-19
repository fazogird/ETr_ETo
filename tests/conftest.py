from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box


@pytest.fixture
def boundary_file(tmp_path: Path) -> Path:
    """Sintetik tarmoq (41.0/40.9 N; 69.0, 69.1, 69.2 E) ustida ikkita "viloyat".

    Chegaralar piksel chetlari bo'ylab o'tadi: Farg'ona 69.0 va 69.1 ustunlarini,
    Andijon esa 69.2 ustunini to'liq qoplaydi.
    """
    gdf = gpd.GeoDataFrame(
        {"shapeName": ["Fergana Region", "Andijan Region"], "shapeISO": ["UZ-FA", "UZ-AN"]},
        geometry=[box(68.95, 40.85, 69.15, 41.05), box(69.15, 40.85, 69.25, 41.05)],
        crs="EPSG:4326",
    )
    path = tmp_path / "boundaries.geojson"
    gdf.to_file(path, driver="GeoJSON")
    return path
