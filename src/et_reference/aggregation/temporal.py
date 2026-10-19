"""Kunlik ET -> oylik yig'indi [mm/oy], yaroqli kunlar ulushi qoidasi bilan."""

from __future__ import annotations

import xarray as xr

MONTH_START = "MS"


def days_per_month(daily: xr.DataArray) -> xr.DataArray:
    """Har oyda qatordagi kunlar soni (davr chegarasida chala oylar uchun ham to'g'ri)."""
    return daily["time"].resample(time=MONTH_START).count()


def monthly_totals(daily: xr.DataArray, min_valid_fraction: float) -> xr.DataArray:
    """Oylik yig'indi = o'rtacha kunlik × oydagi kunlar soni.

    Mavjud kunlar ulushi `min_valid_fraction` dan kam bo'lsa, natija NaN. Barcha
    kunlar mavjud bo'lsa, natija oddiy yig'indiga teng.
    """
    mean = daily.resample(time=MONTH_START).mean(skipna=True)
    available = daily.notnull().resample(time=MONTH_START).sum()
    n_days = days_per_month(daily)
    total = mean * n_days
    return total.where(available >= min_valid_fraction * n_days - 1e-9)


def monthly_counts(flags: xr.DataArray) -> xr.DataArray:
    """Har oyda True bo'lgan kunlar soni (masalan, asl ma'lumotli kunlar)."""
    return flags.astype("int16").resample(time=MONTH_START).sum()
