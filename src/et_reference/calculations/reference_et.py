"""ASCE standartlashtirilgan Penman-Monteith: kunlik ETo (o't) va ETr (beda).

Barcha funksiyalar NumPy broadcasting bilan ishlaydi, masalan:
`tmax` (vaqt, lat, lon), `elevation` (lat, lon), `lat_deg` (lat, 1), `doy` (vaqt, 1, 1).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .atmosphere import (
    air_pressure,
    mean_saturation_vapor_pressure,
    psychrometric_constant,
    saturation_slope,
    vapor_pressure_deficit,
)
from .radiation import (
    clear_sky_radiation,
    cloudiness_function,
    extraterrestrial_radiation,
    net_longwave_radiation,
    net_radiation,
)


@dataclass(frozen=True)
class ReferenceSurface:
    name: str
    cn: float  # surat konstantasi [K mm s³ Mg⁻¹ d⁻¹]
    cd: float  # maxraj konstantasi [s m⁻¹]


GRASS = ReferenceSurface("ETo", cn=900.0, cd=0.34)
ALFALFA = ReferenceSurface("ETr", cn=1600.0, cd=0.38)
DAILY_SURFACES = (GRASS, ALFALFA)


def standardized_et(rn, g, tmean, u2, vpd, delta, gamma, cn, cd):
    """ET_sz [mm d⁻¹] (ASCE 1-tenglama)."""
    return (0.408 * delta * (rn - g) + gamma * cn / (tmean + 273.0) * u2 * vpd) / (
        delta + gamma * (1.0 + cd * u2)
    )


@dataclass(frozen=True)
class DailyTerms:
    """Sirt turiga bog'liq bo'lmagan oraliq kattaliklar (bir marta hisoblanadi)."""

    tmean: np.ndarray
    u2: np.ndarray
    vpd: np.ndarray
    delta: np.ndarray
    gamma: np.ndarray
    rn: np.ndarray


def daily_terms(*, tmax, tmin, ea, rs, u2, elevation, lat_deg, doy) -> DailyTerms:
    """Kunlik oraliq kattaliklar. Birliklar: °C, kPa, MJ m⁻² d⁻¹, m s⁻¹, m, °."""
    tmean = 0.5 * (tmax + tmin)
    gamma = psychrometric_constant(air_pressure(elevation))
    vpd = vapor_pressure_deficit(mean_saturation_vapor_pressure(tmax, tmin), ea)
    ra = extraterrestrial_radiation(np.deg2rad(lat_deg), doy)
    fcd = cloudiness_function(rs, clear_sky_radiation(ra, elevation))
    rn = net_radiation(rs, net_longwave_radiation(tmax, tmin, ea, fcd))
    return DailyTerms(
        tmean=tmean, u2=u2, vpd=vpd, delta=saturation_slope(tmean), gamma=gamma, rn=rn
    )


def daily_reference_et(
    *, tmax, tmin, ea, rs, u2, elevation, lat_deg, doy, surfaces=DAILY_SURFACES
) -> dict[str, np.ndarray]:
    """Har bir sirt uchun kunlik ET [mm d⁻¹]; kunlik qadamda G = 0."""
    terms = daily_terms(
        tmax=tmax, tmin=tmin, ea=ea, rs=rs, u2=u2, elevation=elevation, lat_deg=lat_deg, doy=doy
    )
    return {
        surface.name: standardized_et(
            terms.rn, 0.0, terms.tmean, terms.u2, terms.vpd, terms.delta, terms.gamma,
            surface.cn, surface.cd,
        )
        for surface in surfaces
    }
