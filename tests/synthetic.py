"""Testlar uchun sintetik ERA5-Land fayllari (yangi CDS NetCDF ko'rinishida)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

UTC_OFFSET_H = 5  # Asia/Tashkent
LATS = np.array([41.0, 40.9])
LONS = np.array([69.0, 69.1, 69.2])


def local_temperature(local_hour: np.ndarray) -> np.ndarray:
    """Mahalliy soatga bog'liq harorat [°C]: 15-da maksimum, 03-da minimum."""
    return 20.0 + 8.0 * np.sin(2.0 * np.pi * (local_hour - 9.0) / 24.0)


def hour_ending_flux_wm2(local_hour_ending: np.ndarray) -> np.ndarray:
    """Soat oxiri bo'yicha o'rtacha quyosh oqimi [W m⁻²] (06–18 mahalliy)."""
    mid = local_hour_ending - 0.5
    return np.maximum(0.0, 800.0 * np.sin(np.pi * (mid - 6.0) / 12.0))


def grid_for_area(area) -> tuple[np.ndarray, np.ndarray]:
    """CDS kabi: [N, W, S, E] hududi ichidagi 0.1° tugunlar."""
    north, west, south, east = area
    lats = np.round(np.arange(north, south - 1e-9, -0.1), 1)
    lons = np.round(np.arange(west, east + 1e-9, 0.1), 1)
    return lats, lons


def synthetic_hourly(times_utc: pd.DatetimeIndex, lats=LATS, lons=LONS) -> xr.Dataset:
    """Har kuni bir xil sutkalik sikl; ssrd ERA5-Land kabi 00 UTC dan yig'ilgan."""
    local_hour = ((times_utc.hour + UTC_OFFSET_H) % 24).to_numpy()
    local_hour_ending = (local_hour - 1) % 24 + 1
    energy = hour_ending_flux_wm2(local_hour_ending) * 3600.0  # J m⁻² soat davomida
    accumulation_day = (times_utc - pd.Timedelta(hours=1)).normalize()
    accumulated = pd.Series(energy).groupby(accumulation_day.to_numpy()).cumsum().to_numpy()

    shape = (len(times_utc), len(lats), len(lons))
    ones = np.ones(shape)
    col = (slice(None), np.newaxis, np.newaxis)
    data = {
        "t2m": local_temperature(local_hour)[col] * ones + 273.15,
        "d2m": ones * (5.0 + 273.15),
        "u10": ones * 3.0,
        "v10": ones * 4.0,
        "ssrd": accumulated[col] * ones,
        "sp": ones * 90000.0,
    }
    dims = ("valid_time", "latitude", "longitude")
    ds = xr.Dataset(
        {name: (dims, values.astype("float32")) for name, values in data.items()},
        coords={"valid_time": times_utc, "latitude": lats, "longitude": lons},
    )
    # Yangi CDS fayllaridagi ortiqcha koordinatalar
    return ds.assign_coords(number=0, expver=("valid_time", np.array(["0001"] * len(times_utc))))


def write_request_files(directory: Path, requests) -> None:
    """Uzluksiz sintetik qatorni so'ralgan hudud tarmog'ida yaratib, so'rovlar bo'yicha fayllarga bo'ladi."""
    directory.mkdir(parents=True, exist_ok=True)
    starts = [pd.Timestamp(year=r.year, month=r.month, day=r.days[0]) for r in requests]
    ends = [pd.Timestamp(year=r.year, month=r.month, day=r.days[-1], hour=23) for r in requests]
    lats, lons = grid_for_area(requests[0].area)
    full = synthetic_hourly(pd.date_range(min(starts), max(ends), freq="h"), lats, lons)
    for request, start, end in zip(requests, starts, ends):
        full.sel(valid_time=slice(start, end)).to_netcdf(directory / request.filename)
