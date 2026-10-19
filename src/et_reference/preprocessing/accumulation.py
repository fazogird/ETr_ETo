"""ERA5-Land yig'ilgan (accumulated) oqimlarini soatlik qiymatlarga aylantirish.

ERA5-Land da yig'ish har kuni 00 UTC dan boshlanadi: 01 UTC dagi qiymat 00–01
soati yig'indisi, keyingi kunning 00 UTC dagi qiymati esa butun sutka yig'indisi.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import xarray as xr

log = logging.getLogger(__name__)

RESET_HOUR_UTC = 1
_ONE_HOUR = pd.Timedelta(hours=1)


def deaccumulate(accumulated: xr.DataArray, reset_hour: int = RESET_HOUR_UTC) -> xr.DataArray:
    """Soatlik qo'shimchalar: acc(t) − acc(t−1h); `reset_hour` da acc(t) ning o'zi.

    Oldingi soat yo'q bo'lsa natija NaN. Qadoqlash shovqinidan kelgan manfiy qiymatlar 0 ga tenglanadi.
    """
    da = accumulated.transpose("time", ...)
    times = da.get_index("time")
    values = da.values.astype("float64")
    expand = (slice(None),) + (np.newaxis,) * (values.ndim - 1)

    previous = np.full_like(values, np.nan)
    previous[1:] = values[:-1]
    step_ok = np.zeros(len(times), dtype=bool)
    step_ok[1:] = (times[1:] - times[:-1]) == _ONE_HOUR
    is_reset = np.asarray(times.hour == reset_hour)

    increments = np.where(
        is_reset[expand], values, np.where(step_ok[expand], values - previous, np.nan)
    )
    return da.copy(data=np.clip(increments, 0.0, None))


def looks_accumulated(
    series: xr.DataArray, reset_hour: int = RESET_HOUR_UTC, tolerance: float = 0.01
) -> bool:
    """Qator yig'ilganmi? Yig'ilgan qatorda reset soatidan tashqari kamayish deyarli bo'lmaydi."""
    da = series.transpose("time", ...)
    times = da.get_index("time")
    values = da.values.astype("float64")
    consecutive = np.asarray((times[1:] - times[:-1]) == _ONE_HOUR)
    not_reset = np.asarray(times[1:].hour != reset_hour)
    diffs = (values[1:] - values[:-1])[consecutive & not_reset]
    diffs = diffs[np.isfinite(diffs)]
    if diffs.size == 0:
        raise ValueError("Radiatsiya qatori turini aniqlash uchun ketma-ket soatlar yetarli emas")
    scale = float(np.nanmax(np.abs(values))) or 1.0
    negative_share = float(np.mean(diffs < -1e-6 * scale))
    return negative_share < tolerance


def hourly_solar_radiation(ssrd: xr.DataArray, mode: str = "auto") -> xr.DataArray:
    """ssrd [J m⁻²] -> soatlik energiya [J m⁻²], soat oxiri bo'yicha belgilangan."""
    if mode == "auto":
        mode = "accumulated" if looks_accumulated(ssrd) else "hourly"
        log.info("ssrd turi avtomatik aniqlandi: %s", mode)
    if mode == "accumulated":
        return deaccumulate(ssrd)
    if mode == "hourly":
        return ssrd.clip(min=0.0)
    raise ValueError(f"Noma'lum ssrd rejimi: {mode}")
