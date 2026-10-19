import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from shapely.geometry import box

from et_reference.aggregation.zonal import area_weights, coverage_fraction, weighted_mean
from et_reference.output.rasters import grid_from_coords
from et_reference.regions import COUNTRY_LABEL, crop_to_units, find_unit, select_units, unit_iso

# geoBoundaries gbOpen UZB ADM1 dagi aniq nomlar
GEOBOUNDARIES = {
    "Andijan Region": "UZ-AN", "Namangan Region": "UZ-NG", "Fergana Region": "UZ-FA",
    "Republic of Karakalpakstan": "UZ-QR", "Xorazm Region": "UZ-XO", "Navoiy Region": "UZ-NW",
    "Surxondaryo Region": "UZ-SU", "Samarqand Region": "UZ-SA", "Tashkent Region": "UZ-TO",
    "Sirdaryo Region": "UZ-SI", "Jizzakh Region": "UZ-JI", "Bukhara Region": "UZ-BU",
    "Qashqadaryo Region": "UZ-QA", "Tashkent": "UZ-TK",
}


@pytest.mark.parametrize("name, iso", GEOBOUNDARIES.items())
def test_geoboundaries_names_resolve_without_iso_column(name, iso):
    assert unit_iso(pd.Series({"shapeName": name})) == iso


@pytest.mark.parametrize(
    "query, iso",
    [
        ("Fargona", "UZ-FA"), ("Farg'ona", "UZ-FA"), ("FARGʻONA viloyati", "UZ-FA"), ("Fergana", "UZ-FA"),
        ("Toshkent", "UZ-TK"), ("Toshkent shahri", "UZ-TK"), ("Toshkent viloyati", "UZ-TO"),
        ("toshkent vil.", "UZ-TO"), ("Qoraqalpog'iston", "UZ-QR"), ("Xorazm", "UZ-XO"),
        ("Surxondaryo", "UZ-SU"), ("uz-sa", "UZ-SA"),
    ],
)
def test_user_spellings(query, iso):
    assert find_unit(query).iso == iso


def test_unknown_name_lists_options():
    with pytest.raises(ValueError, match="Fargona"):
        find_unit("Atlantida")


def _units():
    return gpd.GeoDataFrame(
        {"shapeName": ["Fergana Region", "Tashkent"], "shapeISO": ["UZ-FA", "UZ-TK"]},
        geometry=[box(70.0, 40.0, 72.0, 41.0), box(69.1, 41.2, 69.4, 41.4)],
        crs="EPSG:4326",
    )


def test_select_units():
    units = _units()
    subset, label = select_units(units, "Farg'ona")
    assert label == "Fargona" and subset["shapeISO"].tolist() == ["UZ-FA"]
    everything, label = select_units(units, "hammasi")
    assert label == COUNTRY_LABEL and len(everything) == 2
    with pytest.raises(ValueError, match="topilmadi"):
        select_units(units, "Xorazm")


def test_crop_to_units_keeps_margin():
    lat = np.round(np.arange(45.0, 37.0, -0.1), 1)
    lon = np.round(np.arange(56.0, 73.0, 0.1), 1)
    ds = xr.Dataset({"v": (("latitude", "longitude"), np.zeros((lat.size, lon.size)))},
                    coords={"latitude": lat, "longitude": lon})
    subset, _ = select_units(_units(), "Toshkent shahri")
    cropped = crop_to_units(ds, subset)
    assert cropped["latitude"].max() == pytest.approx(41.5)
    assert cropped["latitude"].min() == pytest.approx(41.1)
    assert cropped["longitude"].min() == pytest.approx(69.0)
    assert cropped["longitude"].max() == pytest.approx(69.5)


def test_coverage_fraction_and_weighted_mean():
    lat = np.array([41.0, 40.9])
    grid = grid_from_coords(lat, np.array([69.0, 69.1, 69.2]))
    # Poligon 69.0 piksel ustunining chap yarmini (68.95–69.00) to'liq qoplaydi
    fraction = coverage_fraction([box(68.95, 40.85, 69.00, 41.05)], grid)
    np.testing.assert_allclose(fraction[:, 0], 0.5)
    np.testing.assert_allclose(fraction[:, 1:], 0.0)

    weights = area_weights(lat, np.ones((2, 3)))
    values = np.array([[1.0, 1.0, np.nan], [3.0, 3.0, 3.0]])
    expected = (2 * np.cos(np.deg2rad(41.0)) + 9 * np.cos(np.deg2rad(40.9))) / (
        2 * np.cos(np.deg2rad(41.0)) + 3 * np.cos(np.deg2rad(40.9))
    )
    assert weighted_mean(values, weights) == pytest.approx(expected)
    assert np.isnan(weighted_mean(np.full((2, 3), np.nan), weights))
