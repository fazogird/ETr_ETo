"""Hisoblash yadrosi: FAO-56 misollari, RefET validatsiya qiymatlari va RefET bilan solishtirish."""

import numpy as np
import pytest

from et_reference.calculations import daily_reference_et
from et_reference.calculations.atmosphere import (
    air_pressure,
    pressure_altitude,
    saturation_vapor_pressure,
)
from et_reference.calculations.radiation import extraterrestrial_radiation
from et_reference.calculations.wind import wind_at_2m, wind_speed


def f2c(fahrenheit):
    return (fahrenheit - 32.0) * 5.0 / 9.0


# RefET testlaridagi Fallon (Nevada) AgriMet stansiyasi, 2015-07-01
FALLON = dict(
    tmin=f2c(66.65),
    tmax=f2c(102.80),
    ea=1.2206674169951346,
    rs=674.07 * 0.041868,
    u2=wind_at_2m(4.80 * 0.44704, 3.0),
    elevation=1208.5,
    lat_deg=39.4575,
    doy=182,
)


def test_air_pressure_fao56_example2():
    assert air_pressure(1800.0) == pytest.approx(81.8, abs=0.05)


def test_pressure_altitude_inverts_air_pressure():
    elevation = np.array([-30.0, 0.0, 450.0, 1208.5, 4500.0])
    np.testing.assert_allclose(pressure_altitude(air_pressure(elevation)), elevation, atol=1e-6)


def test_extraterrestrial_radiation_fao56_example8():
    # 3-sentyabr (J=246), 20° janubiy kenglik
    assert extraterrestrial_radiation(np.deg2rad(-20.0), 246) == pytest.approx(32.2, abs=0.05)


def test_wind_helpers():
    assert wind_speed(3.0, 4.0) == pytest.approx(5.0)
    assert wind_at_2m(2.0, 2.0) == pytest.approx(2.0, rel=1e-3)
    assert wind_at_2m(1.0, 10.0) == pytest.approx(0.748, abs=1e-3)


def test_eto_fao56_example18_brussels():
    tmax, tmin = 21.5, 12.3
    ea = (saturation_vapor_pressure(tmin) * 0.84 + saturation_vapor_pressure(tmax) * 0.63) / 2
    result = daily_reference_et(
        tmax=tmax, tmin=tmin, ea=ea, rs=22.07, u2=2.078, elevation=100.0, lat_deg=50.80, doy=187
    )
    assert result["ETo"] == pytest.approx(3.9, abs=0.05)


def test_fallon_matches_refet_validation_values():
    result = daily_reference_et(**FALLON)
    assert result["ETr"] == pytest.approx(10.626087665395694, abs=1e-6)
    assert result["ETo"] == pytest.approx(7.998, abs=1e-3)
    assert result["ETr"] / result["ETo"] == pytest.approx(1.33, abs=0.01)


def test_matches_refet_oracle_on_random_inputs():
    refet = pytest.importorskip("refet")
    rng = np.random.default_rng(42)
    n = 5000
    tmin = rng.uniform(-5.0, 28.0, n)
    tmax = tmin + rng.uniform(2.0, 20.0, n)
    tdew = tmin - rng.uniform(0.0, 15.0, n)
    ea = saturation_vapor_pressure(tdew)
    elevation = rng.uniform(-30.0, 3500.0, n)
    lat = rng.uniform(37.0, 46.0, n)
    doy = rng.integers(60, 274, n)
    ra = extraterrestrial_radiation(np.deg2rad(lat), doy)
    rs = ra * rng.uniform(0.25, 0.78, n)
    u10 = rng.uniform(0.7, 10.0, n)

    oracle = refet.Daily(
        tmin=tmin, tmax=tmax, ea=ea, rs=rs, uz=u10, zw=10.0, elev=elevation, lat=lat, doy=doy,
        method="asce",
    )
    ours = daily_reference_et(
        tmax=tmax, tmin=tmin, ea=ea, rs=rs, u2=wind_at_2m(u10, 10.0),
        elevation=elevation, lat_deg=lat, doy=doy,
    )
    np.testing.assert_allclose(ours["ETo"], oracle.eto(), rtol=0, atol=1e-9)
    np.testing.assert_allclose(ours["ETr"], oracle.etr(), rtol=0, atol=1e-9)


def test_broadcasting_over_time_lat_lon():
    shape = (3, 2, 4)
    tmax = np.full(shape, FALLON["tmax"])
    tmin = np.full(shape, FALLON["tmin"])
    ea = np.full(shape, FALLON["ea"])
    rs = np.full(shape, FALLON["rs"])
    u2 = np.full(shape, FALLON["u2"])
    elevation = np.full(shape[1:], FALLON["elevation"])
    lat = np.full((shape[1], 1), FALLON["lat_deg"])
    doy = np.full((shape[0], 1, 1), FALLON["doy"])
    result = daily_reference_et(
        tmax=tmax, tmin=tmin, ea=ea, rs=rs, u2=u2, elevation=elevation, lat_deg=lat, doy=doy
    )
    assert result["ETr"].shape == shape
    np.testing.assert_allclose(result["ETr"], 10.626087665395694, atol=1e-6)


def test_nan_inputs_propagate():
    result = daily_reference_et(**{**FALLON, "rs": np.nan})
    assert np.isnan(result["ETo"]) and np.isnan(result["ETr"])
