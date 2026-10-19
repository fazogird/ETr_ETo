"""Hisobot jadvallari: oylar bo'yicha va JAMI — dalalar soni, maydon, m³, mm, m³/ga."""

from __future__ import annotations

import pandas as pd

from .. import naming
from .units import M2_PER_HA

HEADERS = ["Oy", "Dalalar soni", "Maydon, ga", "Hisobga olingan dalalar"]


def summarize(table: pd.DataFrame, area_ha: pd.Series, variable: str, months: list[int]) -> pd.DataFrame:
    """`table` — compute_field_table natijasi (faqat shu guruh dalalari), `area_ha` — ularning maydoni.

    mm va m³/ga maydon bo'yicha vaznli o'rtacha: jami m³ / hisobga olingan dalalar maydoni.
    Hisobga olinmagan (qiymati yo'q) dalalar jami m³ ga ham, maydon maxrajiga ham kirmaydi.
    """
    rows = [_row(naming.month_label(m), table[naming.column(variable, m, "m3")], area_ha, variable) for m in months]
    rows.append(_row("JAMI", table[naming.total_column(variable, "m3")], area_ha, variable))
    return pd.DataFrame(rows)


def _row(label: str, m3: pd.Series, area_ha: pd.Series, variable: str) -> dict:
    valid = m3.notna()
    used_ha = float(area_ha[valid].sum())
    total_m3 = float(m3[valid].sum())
    return {
        "Oy": label,
        "Dalalar soni": int(len(m3)),
        "Maydon, ga": float(area_ha.sum()),
        "Hisobga olingan dalalar": int(valid.sum()),
        f"{variable}, m³": total_m3,
        f"{variable}, mm": total_m3 / (used_ha * M2_PER_HA) * 1000.0 if used_ha > 0 else float("nan"),
        f"{variable}, m³/ga": total_m3 / used_ha if used_ha > 0 else float("nan"),
    }


def summarize_by_crop(
    table: pd.DataFrame, area_ha: pd.Series, crop: pd.Series, variable: str, months: list[int]
) -> pd.DataFrame:
    parts = []
    for name in sorted(crop.dropna().unique()):
        mask = (crop == name).to_numpy()
        part = summarize(table[mask], area_ha[mask], variable, months)
        part.insert(0, "Tur", name)
        parts.append(part)
    return pd.concat(parts, ignore_index=True)
