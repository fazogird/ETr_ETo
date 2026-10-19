"""Atmosfera va namlik parametrlari (ASCE-EWRI 2005, 3–8-tenglamalar; FAO-56)."""

from __future__ import annotations

import numpy as np

_PRESSURE_EXPONENT = 5.26


def air_pressure(elevation):
    """Atmosfera bosimi [kPa] balandlikdan [m] (ASCE 3-tenglama)."""
    return 101.3 * ((293.0 - 0.0065 * elevation) / 293.0) ** _PRESSURE_EXPONENT


def pressure_altitude(pressure):
    """`air_pressure` ning teskarisi: bosimdan [kPa] standart balandlik [m]."""
    return (293.0 / 0.0065) * (1.0 - (pressure / 101.3) ** (1.0 / _PRESSURE_EXPONENT))


def psychrometric_constant(pressure):
    """γ [kPa °C⁻¹] (ASCE 4-tenglama)."""
    return 0.000665 * pressure


def saturation_vapor_pressure(temperature):
    """e°(T) [kPa] (ASCE 7-tenglama)."""
    return 0.6108 * np.exp(17.27 * temperature / (temperature + 237.3))


def mean_saturation_vapor_pressure(tmax, tmin):
    """Kunlik es = [e°(Tmax) + e°(Tmin)] / 2 [kPa] (ASCE 6-tenglama)."""
    return 0.5 * (saturation_vapor_pressure(tmax) + saturation_vapor_pressure(tmin))


def saturation_slope(tmean):
    """Δ [kPa °C⁻¹] (ASCE 5-tenglama)."""
    return 2503.0 * np.exp(17.27 * tmean / (tmean + 237.3)) / (tmean + 237.3) ** 2


def vapor_pressure_deficit(es, ea):
    """es − ea [kPa]; manfiy qiymatlar 0 ga tenglanadi."""
    return np.maximum(es - ea, 0.0)
