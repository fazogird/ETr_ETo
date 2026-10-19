"""End-to-end: sintetik ERA5-Land fayllari -> oylik GeoTIFF va CSV, natija RefET bilan mustaqil tekshiriladi."""

import numpy as np
import pandas as pd
import pytest
import rasterio
import xarray as xr

from et_reference.calculations.atmosphere import pressure_altitude, saturation_vapor_pressure
from et_reference.cli import run_command
from et_reference.config import load_settings
from et_reference.pipeline import load_admin_units, plan, run

from .synthetic import hour_ending_flux_wm2, local_temperature, write_request_files

refet = pytest.importorskip("refet")

MARCH = pd.date_range("2026-03-01", "2026-03-31")
APRIL = pd.date_range("2026-04-01", "2026-04-30")
UNIT_LATS = np.array([41.0, 40.9])  # ikkala sintetik viloyat shu qatorlarda


@pytest.fixture
def config_path(tmp_path, boundary_file):
    """Mart–aprel; kesh respublika (ikkala viloyat) hududi bo'yicha sintetik fayllar bilan to'ldiriladi.

    Mahalliy 10-mart kuni (41.0 N, 69.0 E) pikselida harorat yo'q: QC uni to'ldiradi.
    """
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
    settings = load_settings(path)
    requests = plan(settings, load_admin_units(settings))
    assert [(r.year, r.month) for r in requests] == [(2026, 2), (2026, 3), (2026, 4)]
    assert requests[0].area == (41.3, 68.7, 40.6, 69.5)
    write_request_files(settings.paths.hourly, requests)

    march_file = settings.paths.hourly / requests[1].filename
    with xr.open_dataset(march_file) as ds:
        damaged = ds.load()
    gap = (damaged["valid_time"] >= np.datetime64("2026-03-09T19:00")) & (
        damaged["valid_time"] <= np.datetime64("2026-03-10T18:00")
    )
    pixel = {"latitude": 41.0, "longitude": 69.0}
    damaged["t2m"].loc[pixel] = damaged["t2m"].loc[pixel].where(~gap)
    damaged.to_netcdf(march_file)
    return path


def expected_for_lat(days: pd.DatetimeIndex, lat: float) -> dict[str, float]:
    """Sintetik sutkalik sikldan kunlik kirishlarni qo'lda hisoblab, RefET bilan oylik yig'indi."""
    hours = np.arange(24)
    n = len(days)
    daily = refet.Daily(
        tmin=np.full(n, local_temperature(hours).min()),
        tmax=np.full(n, local_temperature(hours).max()),
        ea=np.full(n, saturation_vapor_pressure(5.0)),
        rs=np.full(n, hour_ending_flux_wm2(np.arange(1, 25)).sum() * 3600.0 / 1e6),
        uz=np.full(n, 5.0), zw=10.0,
        elev=np.full(n, pressure_altitude(90.0)),
        lat=np.full(n, lat),
        doy=days.dayofyear.to_numpy(),
        method="asce",
    )
    return {"ETo": float(daily.eto().sum()), "ETr": float(daily.etr().sum())}


def area_mean(days: pd.DatetimeIndex, name: str) -> float:
    weights = np.cos(np.deg2rad(UNIT_LATS))
    values = np.array([expected_for_lat(days, lat)[name] for lat in UNIT_LATS])
    return float(np.sum(values * weights) / weights.sum())


def assert_raster_matches(path, days, name, min_valid):
    """Har bir yaroqli piksel o'z kengligi uchun kutilgan qiymatga teng."""
    with rasterio.open(path) as src:
        assert src.crs.to_epsg() == 4326
        band = src.read(1)
        valid = band != src.nodata
        rows, cols = np.nonzero(valid)
        _, lats = rasterio.transform.xy(src.transform, rows, cols)
    assert valid.sum() >= min_valid
    for row, col, lat in zip(rows, cols, np.round(lats, 1)):
        assert band[row, col] == pytest.approx(expected_for_lat(days, lat)[name], rel=2e-5)
    return band, valid


def test_whole_country(config_path):
    settings = load_settings(config_path)
    result = run(settings, download=False)

    assert sorted(p.name for p in result.rasters) == sorted(
        f"Ozbekiston_{v}_2026_{m:02d}.tif" for v in ("ETo", "ETr") for m in (3, 4)
    )
    for month, days in ((3, MARCH), (4, APRIL)):
        for name in ("ETo", "ETr"):
            # ikkala viloyatning 6 pikseli albatta ichkarida
            assert_raster_matches(
                settings.paths.output / f"Ozbekiston_{name}_2026_{month:02d}.tif", days, name, min_valid=6
            )

    table = pd.read_csv(result.table_file, encoding="utf-8-sig")
    assert table["viloyat"].tolist() == ["Farg'ona viloyati"] * 3 + ["Andijon viloyati"] * 3
    assert table["oy"].tolist() == ["2026-03", "2026-04", "JAMI"] * 2
    fargona = table[table["viloyat"] == "Farg'ona viloyati"].set_index("oy")
    assert fargona.loc["2026-03", "ETo_mm"] == pytest.approx(area_mean(MARCH, "ETo"), abs=0.01)
    assert fargona.loc["JAMI", "ETo_mm"] == pytest.approx(
        fargona.loc["2026-03", "ETo_mm"] + fargona.loc["2026-04", "ETo_mm"], abs=0.02
    )
    assert fargona.loc["JAMI", "kunlar"] == 61
    assert 1.0 < fargona.loc["JAMI", "ETr_ETo"] < 1.6
    # Farg'onaning 4 pikselidan birida 1 kun to'ldirilgan; Andijonda hammasi asl ma'lumot
    assert 98.0 < fargona.loc["2026-03", "asl_malumot_foiz"] < 100.0
    andijon = table[table["viloyat"] == "Andijon viloyati"].set_index("oy")
    assert andijon.loc["2026-03", "asl_malumot_foiz"] == pytest.approx(100.0)
    assert result.summary_file.is_file()


def test_single_region_reuses_country_cache(config_path, tmp_path):
    output = tmp_path / "ET_natijalar"
    # download=False: Farg'ona hududi respublika keshidan olinishi shart, aks holda xato bo'lardi
    code = run_command(
        config=config_path, viloyat="Farg'ona", start="2026-03-01", end="2026-03-31",
        output=output, download=False,
    )
    assert code == 0
    assert sorted(p.name for p in output.glob("*.tif")) == ["Fargona_ETo_2026_03.tif", "Fargona_ETr_2026_03.tif"]
    table = pd.read_csv(output / "Fargona_ETo_ETr_oylik.csv", encoding="utf-8-sig")
    assert table["oy"].tolist() == ["2026-03", "JAMI"]
    assert table.loc[0, "ETr_mm"] == pytest.approx(area_mean(MARCH, "ETr"), abs=0.01)

    band, valid = assert_raster_matches(output / "Fargona_ETo_2026_03.tif", MARCH, "ETo", min_valid=4)
    assert band.shape == (4, 4)  # viloyat chegarasi ± 1 piksel bo'yicha kesilgan
    assert valid.sum() == 4  # faqat Farg'ona pikselleri, qo'shni Andijon NoData


def test_unknown_region_is_reported(config_path, tmp_path):
    assert run_command(config=config_path, viloyat="Atlantida", output=tmp_path / "x", download=False) == 1


def test_missing_cache_without_download_fails(tmp_path, boundary_file):
    config_dir = tmp_path / "bosh" / "config"
    config_dir.mkdir(parents=True)
    path = config_dir / "settings.yaml"
    path.write_text(
        f"period: {{start: 2026-03-01, end: 2026-03-31}}\n"
        f"region: {{boundaries_file: '{boundary_file.as_posix()}'}}\n",
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError, match="skip-download"):
        run(load_settings(path), download=False)
