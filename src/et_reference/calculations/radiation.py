"""Kunlik radiatsiya balansi (ASCE-EWRI 2005, 15–24-tenglamalar)."""

from __future__ import annotations

import numpy as np

SOLAR_CONSTANT = 4.92  # MJ m⁻² h⁻¹
STEFAN_BOLTZMANN_DAILY = 4.901e-9  # MJ K⁻⁴ m⁻² d⁻¹
ALBEDO = 0.23


def inverse_relative_distance(doy):
    """d_r — Yer–Quyosh nisbiy masofasining teskari kvadrati (ASCE 23-tenglama)."""
    return 1.0 + 0.033 * np.cos(2.0 * np.pi / 365.0 * doy)


def solar_declination(doy):
    """δ [rad] (ASCE 24-tenglama)."""
    return 0.409 * np.sin(2.0 * np.pi / 365.0 * doy - 1.39)


def sunset_hour_angle(lat, declination):
    """ω_s [rad] (ASCE 22-tenglama); `lat` radianda."""
    return np.arccos(np.clip(-np.tan(lat) * np.tan(declination), -1.0, 1.0))


def extraterrestrial_radiation(lat, doy):
    """R_a [MJ m⁻² d⁻¹] (ASCE 21-tenglama); `lat` radianda."""
    declination = solar_declination(doy)
    omega_s = sunset_hour_angle(lat, declination)
    geometry = omega_s * np.sin(lat) * np.sin(declination) + np.cos(lat) * np.cos(
        declination
    ) * np.sin(omega_s)
    return (24.0 / np.pi) * SOLAR_CONSTANT * inverse_relative_distance(doy) * geometry


def clear_sky_radiation(ra, elevation):
    """R_so [MJ m⁻² d⁻¹], soddalashtirilgan shakl (ASCE 19-tenglama)."""
    return (0.75 + 2e-5 * elevation) * ra


def cloudiness_function(rs, rso):
    """f_cd = 1.35·clip(Rs/Rso, 0.3, 1) − 0.35 (ASCE 18-tenglama).

    Rso = 0 bo'lsa f_cd = 1 (RefET kabi); NaN kirish NaN natija beradi.
    """
    rs = np.asarray(rs, dtype=float)
    rso = np.asarray(rso, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(rso > 0, rs / np.where(rso > 0, rso, 1.0), 1.0)
    ratio = np.where(np.isnan(rs) | np.isnan(rso), np.nan, ratio)
    return 1.35 * np.clip(ratio, 0.3, 1.0) - 0.35


def net_longwave_radiation(tmax, tmin, ea, fcd):
    """R_nl [MJ m⁻² d⁻¹] (ASCE 17-tenglama)."""
    blackbody = 0.5 * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4)
    return STEFAN_BOLTZMANN_DAILY * fcd * (0.34 - 0.14 * np.sqrt(ea)) * blackbody


def net_radiation(rs, rnl):
    """R_n = (1 − α)·Rs − R_nl [MJ m⁻² d⁻¹] (ASCE 15–16-tenglamalar)."""
    return (1.0 - ALBEDO) * rs - rnl
