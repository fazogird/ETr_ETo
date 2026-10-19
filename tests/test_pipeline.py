"""End-to-end: sintetik ERA5-Land fayllari -> oylik GeoTIFF, natija RefET bilan mustaqil tekshiriladi."""

import json

import numpy as np
import pandas as pd
import pytest
import rasterio
import xarray as xr

from et_reference.calculations.atmosphere import pressure_altitude, saturation_vapor_pressure
from et_reference.calculations.wind import wind_at_2m
from et_reference.config import load_settings
from et_reference.pipeline import load_region, plan, run

from .synthetic import LATS, hour_ending_flux_wm2, local_temperature, write_request_files

refet = pytest.importorskip("refet")


@pytest.fixture
def settings(tmp_path, boundary_file):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    path = config_dir / "settings.yaml"
    path.write_text(
        f"""
period: {{start: 2026-03-01, end: 2026-04-30}}
region:
  boundaries_file: '{boundary_file.as_posix()}'
  timezone: Asia/Tashkent
cds: {{credentials: null}}
paths: {{root: .., cache: data/cache, output: outputs}}
""",
        encoding="utf-8",
    )
    return load_settings(path)


def expected_monthly(month_days: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    """Sintetik sutkalik sikldan kunlik kirishlarni qo'lda hisoblab, RefET bilan oylik yig'indi."""
    hours = np.arange(24)
    tmax, tmin = local_temperature(hours).max(), local_temperature(hours).min()
    rs = hour_ending_flux_wm2(np.arange(1, 25)).sum() * 3600.0 / 1e6
    ea = saturation_vapor_pressure(5.0)
    elevation = pressure_altitude(90.0)
    u2 = wind_at_2m(5.0, 10.0)
    result = {"ETo": [], "ETr": []}
    for lat in LATS:
        n = len(month_days)
        daily = refet.Daily(
            tmin=np.full(n, tmin), tmax=np.full(n, tmax), ea=np.full(n, ea), rs=np.full(n, rs),
            uz=np.full(n, u2), zw=2.0, elev=np.full(n, elevation), lat=np.full(n, lat),
            doy=month_days.dayofyear.to_numpy(), method="asce",
        )
        # zw=2 uchun RefET ko'paytuvchisi 1 emas: u2 ni aynan bir xil berish uchun qayta o'rnatamiz
        daily.u2 = np.full(n, u2)
        result["ETo"].append(daily.eto().sum())
        result["ETr"].append(daily.etr().sum())
    return {k: np.array(v) for k, v in result.items()}


def test_end_to_end_synthetic(settings):
    region = load_region(settings)
    requests = plan(settings, region)
    assert [(r.year, r.month) for r in requests] == [(2026, 2), (2026, 3), (2026, 4)]
    write_request_files(settings.paths.hourly, requests)

    # 10-mart (mahalliy) kuni bitta piksel uchun harorat yo'q -> QC to'ldiradi, valid_days = 30
    march_file = settings.paths.hourly / requests[1].filename
    with xr.open_dataset(march_file) as ds:
        damaged = ds.load()
    gap = (damaged["valid_time"] >= np.datetime64("2026-03-09T19:00")) & (
        damaged["valid_time"] <= np.datetime64("2026-03-10T18:00")
    )
    damaged["t2m"][{"latitude": 0, "longitude": 0}] = damaged["t2m"][
        {"latitude": 0, "longitude": 0}
    ].where(~gap)
    damaged.to_netcdf(march_file)

    result = run(settings, download=False)
    names = sorted(p.name for p in result.rasters)
    assert names == sorted(
        f"{v}_2026_{m:02d}.tif" for v in ("ETo", "ETr", "valid_days") for m in (3, 4)
    )

    for month, days in ((3, pd.date_range("2026-03-01", "2026-03-31")),
                        (4, pd.date_range("2026-04-01", "2026-04-30"))):
        expected = expected_monthly(days)
        for name in ("ETo", "ETr"):
            with rasterio.open(settings.paths.rasters / f"{name}_2026_{month:02d}.tif") as src:
                assert src.crs.to_epsg() == 4326
                assert src.transform.c == pytest.approx(68.95)
                band = src.read(1)
            assert (band != src.nodata).all()
            for row, value in enumerate(expected[name]):
                np.testing.assert_allclose(band[row], value, rtol=2e-5)

    with rasterio.open(settings.paths.rasters / "valid_days_2026_03.tif") as src:
        valid = src.read(1)
    assert valid[0, 0] == 30 and (valid.ravel()[1:] == 31).all()

    with rasterio.open(settings.paths.rasters / "ETr_2026_03.tif") as etr, rasterio.open(
        settings.paths.rasters / "ETo_2026_03.tif"
    ) as eto:
        ratio = etr.read(1) / eto.read(1)
    assert np.all((ratio > 1.0) & (ratio < 1.6))

    summary = json.loads(result.summary_file.read_text(encoding="utf-8"))
    assert summary["quality_control"]["gap_filled"]["tmax"] == 1
    assert summary["period"] == {"start": "2026-03-01", "end": "2026-04-30"}


def test_missing_cache_without_download_fails(settings):
    with pytest.raises(FileNotFoundError, match="skip-download"):
        run(settings, download=False)
