import numpy as np
import pandas as pd
import pytest
import xarray as xr

from et_reference.ingestion.archive import normalize_era5_dataset
from et_reference.preprocessing.accumulation import deaccumulate, looks_accumulated
from et_reference.preprocessing.daily import aggregate_daily, local_days
from et_reference.preprocessing.quality import fill_short_gaps, run_quality_control

from .synthetic import hour_ending_flux_wm2, local_temperature, synthetic_hourly


@pytest.fixture
def three_days():
    times = pd.date_range("2026-03-01 00:00", "2026-03-03 23:00", freq="h")
    return normalize_era5_dataset(synthetic_hourly(times))


def test_deaccumulate_recovers_hourly_energy(three_days):
    hourly = deaccumulate(three_days["ssrd"])
    times = hourly.get_index("time")
    local_hour_ending = (times.hour + 5 - 1) % 24 + 1
    expected = hour_ending_flux_wm2(np.asarray(local_hour_ending)) * 3600.0
    got = hourly.isel(latitude=0, longitude=0).values
    # Birinchi qadamning oldingi soati yo'q -> NaN; qolganlari aniq tiklanadi
    assert np.isnan(got[0])
    np.testing.assert_allclose(got[1:], expected[1:], rtol=1e-5, atol=1.0)


def test_accumulation_detection(three_days):
    assert looks_accumulated(three_days["ssrd"])
    assert not looks_accumulated(deaccumulate(three_days["ssrd"]).isel(time=slice(1, None)))


def test_local_days_instant_and_hour_ending():
    times = pd.DatetimeIndex(["2026-03-01 18:00", "2026-03-01 19:00"])
    instant = local_days(times, "Asia/Tashkent", hour_ending=False)
    flux = local_days(times, "Asia/Tashkent", hour_ending=True)
    # UTC 18:00 = mahalliy 23:00 (1-mart); UTC 19:00 = mahalliy 00:00 (2-mart)
    assert list(instant.day) == [1, 2]
    # Soat oxiri bo'yicha mahalliy 24:00 hali 1-martga tegishli
    assert list(flux.day) == [1, 1]


def test_aggregate_daily_matches_synthetic_truth(three_days):
    rs_hourly = deaccumulate(three_days["ssrd"])
    daily = aggregate_daily(three_days, rs_hourly, "Asia/Tashkent", min_hours=24)
    middle = daily.sel(time="2026-03-02").isel(latitude=0, longitude=0)

    hours = np.arange(24)
    assert float(middle["tmax"]) == pytest.approx(local_temperature(hours).max(), abs=1e-4)
    assert float(middle["tmin"]) == pytest.approx(local_temperature(hours).min(), abs=1e-4)
    assert float(middle["tdew"]) == pytest.approx(5.0, abs=1e-4)
    assert float(middle["wind10"]) == pytest.approx(5.0, abs=1e-5)  # √(3² + 4²)
    assert float(middle["sp"]) == pytest.approx(90.0, abs=1e-4)
    expected_rs = hour_ending_flux_wm2(np.arange(1, 25)).sum() * 3600.0 / 1e6
    assert float(middle["rs"]) == pytest.approx(expected_rs, rel=1e-5)
    # 1-mart mahalliy kunining birinchi soatlari faylda yo'q -> to'liq bo'lmagan kun
    assert np.isnan(float(daily.sel(time="2026-03-01")["tmax"].isel(latitude=0, longitude=0)))


def test_fill_short_gaps_rules():
    series = np.array([1.0, np.nan, np.nan, 4.0, np.nan, np.nan, np.nan, np.nan, 9.0, np.nan])
    filled, mask = fill_short_gaps(series[:, np.newaxis], max_gap=3)
    np.testing.assert_allclose(filled[:4, 0], [1.0, 2.0, 3.0, 4.0])
    assert np.isnan(filled[4:8, 0]).all()  # 4 kunlik bo'shliq > 3
    assert np.isnan(filled[9, 0])  # qator oxiri ekstrapolyatsiya qilinmaydi
    assert mask[:, 0].sum() == 2


def _daily_dataset(**overrides):
    time = pd.date_range("2026-06-01", periods=5, freq="D")
    base = {"tmax": 35.0, "tmin": 20.0, "tdew": 10.0, "rs": 25.0, "wind10": 3.0, "sp": 98.0}
    base.update(overrides)
    shape = (5, 1, 1)
    coords = {"time": time, "latitude": [41.0], "longitude": [69.0]}
    dims = ("time", "latitude", "longitude")
    return xr.Dataset({k: (dims, np.full(shape, v, dtype=float)) for k, v in base.items()}, coords=coords)


def test_quality_control_rules():
    daily = _daily_dataset()
    daily["tdew"][1] = 40.0  # Tdew > Tmax -> Tmax ga tenglanadi
    daily["tmax"][2] = 75.0  # fizik chegaradan tashqari -> NaN -> to'ldiriladi
    daily["rs"][3] = 49.0  # Ra dan katta -> NaN -> to'ldiriladi
    filled, original, report = run_quality_control(daily, np.array([41.0]), max_gap_days=3)

    assert filled["tdew"].values[1, 0, 0] == pytest.approx(35.0)
    assert report.dewpoint_clipped == 1
    assert report.out_of_range["tmax"] == 1
    assert report.rs_above_ra == 1
    assert filled["tmax"].values[2, 0, 0] == pytest.approx(35.0)
    assert filled["rs"].values[3, 0, 0] == pytest.approx(25.0)
    assert original.values[:, 0, 0].tolist() == [True, True, False, False, True]
