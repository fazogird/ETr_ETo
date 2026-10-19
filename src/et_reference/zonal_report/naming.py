"""Ustun va oy nomlari: shp (10 belgi limiti!) va Excel uchun yagona manba."""

from __future__ import annotations

VARIABLES = ("ETr", "ETo")  # ETr birinchi: chiqish tartibi shunday
UNITS = ("mm", "m3", "m3ha")
SHAPEFILE_NAME_LIMIT = 10

MONTH_NAMES_UZ = {
    1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel", 5: "May", 6: "Iyun",
    7: "Iyul", 8: "Avgust", 9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr",
}

AREA_COLUMN = "area_ga"
QC_COLUMN = "ET_QC"


def column(variable: str, month: int, unit: str) -> str:
    """ETr3_mm, ETr3_m3, ETr3_m3ha, ETo9_mm ..."""
    return f"{variable}{month}_{unit}"


def total_column(variable: str, unit: str) -> str:
    """Mavsum yig'indisi: ETr_mm, ETr_m3, ETr_m3ha."""
    return f"{variable}_{unit}"


def month_label(month: int) -> str:
    return f"{month} ({MONTH_NAMES_UZ[month]})"
