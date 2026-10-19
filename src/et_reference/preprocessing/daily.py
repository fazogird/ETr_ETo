"""Soatlik UTC ma'lumotlardan mahalliy kun (masalan, Asia/Tashkent) bo'yicha kunlik agregatlar."""

from __future__ import annotations

import logging
from datetime import timedelta

import numpy as np
import pandas as pd
import xarray as xr

from ..calculations.wind import wind_speed
from ..config import Period
from ..ingestion.archive import HourlyArchive
from ..timeutils import iter_months, local_midnight_utc
from .accumulation import hourly_solar_radiation

log = logging.getLogger(__name__)

HOURLY_VARIABLES = ("t2m", "d2m", "u10", "v10", "ssrd", "sp")
KELVIN = 273.15


def local_days(times_utc: pd.DatetimeIndex, timezone: str, hour_ending: bool) -> pd.DatetimeIndex:
    """Har bir UTC vaqt belgisi qaysi mahalliy kunga tegishli.

    Lahzalik qiymatlar: mahalliy 00:00..23:00 -> shu kun.
    Soat oxiri bo'yicha belgilangan oqimlar: mahalliy 01:00..24:00 -> shu kun.
    """
    local = times_utc.tz_localize("UTC").tz_convert(timezone).tz_localize(None)
    if hour_ending:
        local = local - pd.Timedelta(hours=1)
    return local.normalize()


def _reduce_daily(da: xr.DataArray, days: pd.DatetimeIndex, how: str, min_count: int) -> xr.DataArray:
    labelled = da.assign_coords(day=("time", days))
    reduced = getattr(labelled.groupby("day"), how)(skipna=True)
    counts = labelled.notnull().groupby("day").sum()
    return reduced.where(counts >= min_count).rename(day="time")


def aggregate_daily(
    hourly: xr.Dataset, rs_hourly: xr.DataArray, timezone: str, min_hours: int
) -> xr.Dataset:
    """Kunlik: tmax, tmin, tdew [°C], wind10 [m s⁻¹], sp [kPa], rs [MJ m⁻² d⁻¹]."""
    instant = local_days(hourly.get_index("time"), timezone, hour_ending=False)
    flux = local_days(rs_hourly.get_index("time"), timezone, hour_ending=True)

    t2m = hourly["t2m"] - KELVIN
    speed = wind_speed(hourly["u10"], hourly["v10"])  # avval soatlik tezlik, keyin o'rtacha
    daily = xr.Dataset(
        {
            "tmax": _reduce_daily(t2m, instant, "max", min_hours),
            "tmin": _reduce_daily(t2m, instant, "min", min_hours),
            "tdew": _reduce_daily(hourly["d2m"] - KELVIN, instant, "mean", min_hours),
            "wind10": _reduce_daily(speed, instant, "mean", min_hours),
            "sp": _reduce_daily(hourly["sp"] / 1000.0, instant, "mean", min_hours),
            "rs": _reduce_daily(rs_hourly / 1e6, flux, "sum", min_hours),
        }
    )
    units = {"tmax": "degC", "tmin": "degC", "tdew": "degC", "wind10": "m s-1",
             "sp": "kPa", "rs": "MJ m-2 d-1"}
    for name, unit in units.items():
        daily[name].attrs["units"] = unit
    return daily


def build_daily(
    archive: HourlyArchive,
    period: Period,
    timezone: str,
    *,
    ssrd_mode: str = "auto",
    min_hours: int = 24,
) -> xr.Dataset:
    """Butun davr uchun kunlik ma'lumotlar; xotirani tejash uchun oyma-oy hisoblanadi."""
    parts = []
    for month_start, month_end in iter_months(period.start, period.end):
        utc_start = local_midnight_utc(month_start, timezone)
        utc_end = local_midnight_utc(month_end + timedelta(days=1), timezone)
        hourly = archive.load(utc_start, utc_end, HOURLY_VARIABLES)
        rs_hourly = hourly_solar_radiation(hourly["ssrd"], ssrd_mode)
        daily = aggregate_daily(hourly, rs_hourly, timezone, min_hours)
        days = pd.date_range(month_start, month_end, freq="D")
        parts.append(daily.reindex(time=days))
        complete = float(np.isfinite(parts[-1]["rs"]).mean() * 100)
        log.info("%s: kunlik agregatlar tayyor (Rs to'liqligi %.1f%%)", month_start.strftime("%Y-%m"), complete)
    return xr.concat(parts, dim="time")
