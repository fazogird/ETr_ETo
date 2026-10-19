"""Shamol tezligi (ASCE-EWRI 2005, 33-tenglama)."""

from __future__ import annotations

import numpy as np


def wind_speed(u, v):
    """Komponentlardan tezlik [m s⁻¹]. Soatlik qadamda, o'rtachalashdan OLDIN qo'llanadi."""
    return np.hypot(u, v)


def wind_at_2m(uz, height):
    """`height` [m] balandlikdagi shamolni 2 m ga keltiradi (logarifmik profil)."""
    return uz * 4.87 / np.log(67.8 * height - 5.42)
