"""Birlik o'tkazish: mm → m³ → m³/ga."""

from __future__ import annotations

import numpy as np

M2_PER_HA = 10_000.0


def mm_to_m3(mm: np.ndarray, area_m2: np.ndarray) -> np.ndarray:
    """1 mm qatlam × 1 m² = 1 litr = 0.001 m³."""
    return mm / 1000.0 * area_m2


def m3_to_m3ha(m3: np.ndarray, area_m2: np.ndarray) -> np.ndarray:
    """Maydoni 0 (yoki noma'lum) dala uchun NaN."""
    area_ha = area_m2 / M2_PER_HA
    return np.where(area_ha > 0, m3 / np.where(area_ha > 0, area_ha, 1.0), np.nan)
