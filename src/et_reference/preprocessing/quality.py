"""Kunlik kirish ma'lumotlari sifat nazorati (QC) va qisqa bo'shliqlarni to'ldirish."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import xarray as xr

from ..calculations.radiation import extraterrestrial_radiation

log = logging.getLogger(__name__)

INPUT_VARIABLES = ("tmax", "tmin", "tdew", "rs", "wind10", "sp")

# Fizik jihatdan mumkin bo'lgan diapazonlar (O'rta Osiyo uchun keng zaxira bilan)
PHYSICAL_LIMITS: dict[str, tuple[float, float]] = {
    "tmax": (-60.0, 60.0),
    "tmin": (-60.0, 60.0),
    "tdew": (-80.0, 40.0),
    "rs": (0.0, 50.0),
    "wind10": (0.0, 60.0),
    "sp": (40.0, 110.0),
}


@dataclass
class QualityReport:
    out_of_range: dict[str, int] = field(default_factory=dict)
    tmin_above_tmax: int = 0
    dewpoint_clipped: int = 0
    rs_above_ra: int = 0
    gap_filled: dict[str, int] = field(default_factory=dict)
    still_missing: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "out_of_range": self.out_of_range,
            "tmin_above_tmax": self.tmin_above_tmax,
            "dewpoint_clipped": self.dewpoint_clipped,
            "rs_above_ra": self.rs_above_ra,
            "gap_filled": self.gap_filled,
            "still_missing": self.still_missing,
        }


def apply_physical_limits(daily: xr.Dataset, report: QualityReport) -> xr.Dataset:
    """Diapazondan tashqaridagi qiymatlar NaN qilinadi."""
    daily = daily.copy()
    for name, (low, high) in PHYSICAL_LIMITS.items():
        da = daily[name]
        bad = da.notnull() & ((da < low) | (da > high))
        report.out_of_range[name] = int(bad.sum())
        daily[name] = da.where(~bad)
    return daily


def check_consistency(daily: xr.Dataset, lat_deg: np.ndarray, report: QualityReport) -> xr.Dataset:
    """Tmin ≤ Tmax, Tdew ≤ Tmax (RH ≤ 100%), Rs ≤ Ra."""
    daily = daily.transpose("time", "latitude", "longitude").copy()
    inverted = daily["tmin"] > daily["tmax"]
    report.tmin_above_tmax = int(inverted.sum())
    daily["tmin"] = daily["tmin"].where(~inverted)
    daily["tmax"] = daily["tmax"].where(~inverted)

    too_humid = daily["tdew"] > daily["tmax"]
    report.dewpoint_clipped = int(too_humid.sum())
    daily["tdew"] = xr.where(too_humid, daily["tmax"], daily["tdew"])

    doy = daily["time"].dt.dayofyear.values[:, np.newaxis, np.newaxis]
    lat_rad = np.deg2rad(np.asarray(lat_deg, dtype="float64"))[np.newaxis, :, np.newaxis]
    ra = extraterrestrial_radiation(lat_rad, doy)
    with np.errstate(invalid="ignore"):
        above = daily["rs"].values > ra
    report.rs_above_ra = int(above.sum())
    daily["rs"] = daily["rs"].where(~above)
    return daily


def fill_short_gaps(values: np.ndarray, max_gap: int) -> tuple[np.ndarray, np.ndarray]:
    """0-o'q (vaqt) bo'ylab ichki bo'shliqlarni chiziqli to'ldiradi, agar uzunligi ≤ `max_gap`.

    Qator boshi va oxiridagi bo'shliqlar to'ldirilmaydi (ekstrapolyatsiya yo'q).
    Qaytaradi: (to'ldirilgan massiv, to'ldirilgan katakchalar niqobi).
    """
    values = np.asarray(values, dtype="float64")
    n = values.shape[0]
    isnan = np.isnan(values)
    if max_gap <= 0 or not isnan.any():
        return values.copy(), np.zeros_like(isnan)

    index = np.arange(n).reshape((n,) + (1,) * (values.ndim - 1))
    index = np.broadcast_to(index, values.shape)
    prev_idx = np.maximum.accumulate(np.where(isnan, -1, index), axis=0)
    next_idx = np.flip(
        np.minimum.accumulate(np.flip(np.where(isnan, n, index), axis=0), axis=0), axis=0
    )
    interior = (prev_idx >= 0) & (next_idx < n)
    gap_length = next_idx - prev_idx - 1
    fillable = isnan & interior & (gap_length <= max_gap)

    prev_val = np.take_along_axis(values, np.clip(prev_idx, 0, n - 1), axis=0)
    next_val = np.take_along_axis(values, np.clip(next_idx, 0, n - 1), axis=0)
    span = np.where(next_idx > prev_idx, next_idx - prev_idx, 1)
    weight = (index - prev_idx) / span
    filled = np.where(fillable, prev_val + weight * (next_val - prev_val), values)
    return filled, fillable


def run_quality_control(
    daily: xr.Dataset, lat_deg: np.ndarray, max_gap_days: int
) -> tuple[xr.Dataset, xr.DataArray, QualityReport]:
    """QC -> asl yaroqli kunlar niqobi -> qisqa bo'shliqlarni to'ldirish.

    Qaytaradi: (to'ldirilgan kunlik ma'lumot, asl yaroqli niqob [vaqt, lat, lon], hisobot).
    """
    report = QualityReport()
    daily = daily[list(INPUT_VARIABLES)].transpose("time", "latitude", "longitude")
    daily = apply_physical_limits(daily, report)
    daily = check_consistency(daily, lat_deg, report)

    original_valid = xr.concat(
        [daily[name].notnull() for name in INPUT_VARIABLES], dim="variable"
    ).all("variable")

    filled = daily.copy()
    for name in INPUT_VARIABLES:
        values, mask = fill_short_gaps(daily[name].values, max_gap_days)
        filled[name] = daily[name].copy(data=values)
        report.gap_filled[name] = int(mask.sum())
        report.still_missing[name] = int(np.isnan(values).sum())

    log.info("QC: %s", report.as_dict())
    return filled, original_valid, report


def apply_wind_floor(u2: np.ndarray, minimum: float) -> np.ndarray:
    """u₂ uchun pastki chegara (FAO-56: 0.5 m s⁻¹); NaN saqlanadi."""
    return np.maximum(u2, minimum)
