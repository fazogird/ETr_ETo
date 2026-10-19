import numpy as np
import pandas as pd
import pytest
import rasterio
import xarray as xr
from shapely.geometry import box

from et_reference.aggregation.temporal import monthly_counts, monthly_totals
from et_reference.output.rasters import grid_from_coords, region_mask, write_geotiff


def _daily(values, start="2026-03-01"):
    time = pd.date_range(start, periods=len(values), freq="D")
    return xr.DataArray(np.asarray(values, dtype=float), coords={"time": time}, dims="time")


def test_full_month_total_is_plain_sum():
    daily = _daily(np.arange(1, 32))
    assert float(monthly_totals(daily, 0.9)[0]) == pytest.approx(np.arange(1, 32).sum())


def test_missing_days_scaled_or_rejected():
    values = np.full(30, 4.0)
    values[:3] = np.nan  # 27/30 = 0.9 -> qabul qilinadi
    assert float(monthly_totals(_daily(values, "2026-04-01"), 0.9)[0]) == pytest.approx(120.0)
    values[3] = np.nan  # 26/30 < 0.9 -> NaN
    assert np.isnan(float(monthly_totals(_daily(values, "2026-04-01"), 0.9)[0]))


def test_partial_month_uses_days_in_period():
    daily = _daily(np.full(10, 2.0), start="2026-03-22")  # 22–31 mart
    assert float(monthly_totals(daily, 0.9)[0]) == pytest.approx(20.0)


def test_monthly_counts():
    flags = _daily([1, 1, 0, 1]).astype(bool)
    assert int(monthly_counts(flags)[0]) == 3


LAT = np.array([41.0, 40.9, 40.8])
LON = np.array([69.0, 69.1, 69.2, 69.3])


def test_grid_transform_uses_pixel_centres():
    grid = grid_from_coords(LAT, LON)
    assert (grid.width, grid.height) == (4, 3)
    assert grid.transform.c == pytest.approx(68.95)
    assert grid.transform.f == pytest.approx(41.05)
    assert grid.transform.a == pytest.approx(0.1)
    assert grid.transform.e == pytest.approx(-0.1)


def test_grid_rejects_irregular_or_flipped_axes():
    with pytest.raises(ValueError):
        grid_from_coords(LAT[::-1], LON)
    with pytest.raises(ValueError):
        grid_from_coords(LAT, np.array([69.0, 69.1, 69.3, 69.4]))


def test_region_mask_all_touched():
    grid = grid_from_coords(LAT, LON)
    # (69.1, 40.9) markazli piksel ichida (69.05–69.15, 40.85–40.95), markazni o'z ichiga olmaydi
    tiny = [box(69.06, 40.86, 69.08, 40.88)]
    assert region_mask(tiny, grid, all_touched=True).sum() == 1
    assert region_mask(tiny, grid, all_touched=False).sum() == 0


def test_write_geotiff_roundtrip(tmp_path):
    grid = grid_from_coords(LAT, LON)
    data = np.arange(12, dtype=float).reshape(3, 4)
    data[0, 0] = np.nan
    path = write_geotiff(
        tmp_path / "ETo_2026_03.tif", data, grid, nodata=-9999.0,
        description="ETo 2026-03 [mm/month]", tags={"UNITS": "mm/month"},
    )
    with rasterio.open(path) as src:
        assert src.crs.to_epsg() == 4326
        assert src.nodata == -9999.0
        assert src.descriptions[0] == "ETo 2026-03 [mm/month]"
        assert src.tags()["UNITS"] == "mm/month"
        band = src.read(1, masked=True)
    assert band.mask[0, 0]
    np.testing.assert_allclose(band.filled(np.nan)[1:], data[1:])
