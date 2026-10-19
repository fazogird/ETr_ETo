"""Har bir dala uchun ETr/ETo ustunlari: oylik mm, m3, m3ha va mavsum yig'indisi."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .. import naming
from ..preprocessing.rasters import RasterStack
from .units import m3_to_m3ha, mm_to_m3
from .weights import PixelWeights
from .zonal import zonal_mean


@dataclass(frozen=True)
class FieldTable:
    values: pd.DataFrame  # indeks = dala tartibi; ustunlar naming.column(...) va naming.total_column(...)
    status: np.ndarray    # dala bo'yicha eng yomon holat kodi (barcha oy va o'zgaruvchilar bo'yicha)


def compute_field_table(
    stack: RasterStack,
    weights: PixelWeights,
    area_m2: np.ndarray,
    max_fill_pixels: float,
) -> FieldTable:
    columns: dict[str, np.ndarray] = {}
    monthly: dict[tuple[str, str], list[str]] = {}  # (o'zgaruvchi, birlik) -> oylik ustunlar
    worst = np.zeros(weights.n_fields, dtype=np.int8)
    variables = [v for v in naming.VARIABLES if any(key[0] == v for key in stack.arrays)]
    for variable in variables:
        months = sorted(month for var, month in stack.arrays if var == variable)
        for month in months:
            result = zonal_mean(weights, stack.arrays[(variable, month)], stack.grid, max_fill_pixels)
            m3 = mm_to_m3(result.mean, area_m2)
            for unit, data in zip(naming.UNITS, (result.mean, m3, m3_to_m3ha(m3, area_m2))):
                name = naming.column(variable, month, unit)
                columns[name] = data
                monthly.setdefault((variable, unit), []).append(name)
            worst = np.maximum(worst, result.status)
    frame = pd.DataFrame(columns)
    for (variable, unit), parts in monthly.items():
        # mavsum yig'indisi: biror oy yetishmasa NaN (to'liq bo'lmagan yig'indi aldamchi bo'lardi)
        frame[naming.total_column(variable, unit)] = frame[parts].sum(axis=1, min_count=len(parts))
    return FieldTable(frame, worst)
