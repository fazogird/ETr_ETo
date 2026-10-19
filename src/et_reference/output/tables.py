"""Viloyat bo'yicha oylik jadval (CSV, Excel'da to'g'ri ochiladi)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMNS = [
    "viloyat", "oy", "kunlar", "ETo_mm", "ETr_mm", "ETo_mm_kun", "ETr_mm_kun",
    "ETr_ETo", "asl_malumot_foiz",
]


def with_totals(monthly: pd.DataFrame) -> pd.DataFrame:
    """Har bir viloyat uchun oxiriga "JAMI" (butun davr) qatorini qo'shadi."""
    parts = []
    for name, group in monthly.groupby("viloyat", sort=False):
        days = group["kunlar"].sum()
        eto, etr = group["ETo_mm"].sum(min_count=len(group)), group["ETr_mm"].sum(min_count=len(group))
        total = {
            "viloyat": name, "oy": "JAMI", "kunlar": days, "ETo_mm": eto, "ETr_mm": etr,
            "ETo_mm_kun": eto / days, "ETr_mm_kun": etr / days, "ETr_ETo": etr / eto,
            "asl_malumot_foiz": (group["asl_malumot_foiz"] * group["kunlar"]).sum() / days,
        }
        parts.extend([group, pd.DataFrame([total])])
    return pd.concat(parts, ignore_index=True)[COLUMNS]


def write_table(table: pd.DataFrame, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: Excel o'zbekcha harflarni (o', g') to'g'ri ko'rsatadi
    table.round(2).to_csv(path, index=False, encoding="utf-8-sig")
    return path
