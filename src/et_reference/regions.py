"""O'zbekiston ma'muriy birliklari: "Fargona", "Farg'ona", "Fergana" kabi nomlardan chegarani topish."""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import xarray as xr

COUNTRY_LABEL = "Ozbekiston"
ALL_KEYWORDS = {"hammasi", "barchasi", "all", "ozbekiston", "uzbekistan", "respublika"}
_SUFFIXES = {"viloyati", "viloyat", "vil", "region", "oblast", "oblasti", "obl",
             "respublikasi", "republic", "of"}
_APOSTROPHES = "'ʻʼ’‘`´"


@dataclass(frozen=True)
class Unit:
    iso: str
    name: str  # o'zbekcha nom (jadvalda)
    slug: str  # fayl nomi uchun (faqat lotin harflari)
    aliases: tuple[str, ...]


UNITS = (
    Unit("UZ-AN", "Andijon viloyati", "Andijon", ("andijon", "andijan")),
    Unit("UZ-BU", "Buxoro viloyati", "Buxoro", ("buxoro", "bukhara", "buhoro", "bukhoro")),
    Unit("UZ-FA", "Farg'ona viloyati", "Fargona", ("fargona", "fergana", "ferghana")),
    Unit("UZ-JI", "Jizzax viloyati", "Jizzax", ("jizzax", "jizzakh", "jizzak", "djizak")),
    Unit("UZ-XO", "Xorazm viloyati", "Xorazm", ("xorazm", "khorezm", "xorezm", "khorazm")),
    Unit("UZ-NG", "Namangan viloyati", "Namangan", ("namangan",)),
    Unit("UZ-NW", "Navoiy viloyati", "Navoiy", ("navoiy", "navoi")),
    Unit("UZ-QA", "Qashqadaryo viloyati", "Qashqadaryo", ("qashqadaryo", "kashkadarya", "qashqadarya")),
    Unit("UZ-QR", "Qoraqalpog'iston Respublikasi", "Qoraqalpogiston",
         ("qoraqalpogiston", "karakalpakstan", "qoraqalpoq", "karakalpakiya")),
    Unit("UZ-SA", "Samarqand viloyati", "Samarqand", ("samarqand", "samarkand")),
    Unit("UZ-SI", "Sirdaryo viloyati", "Sirdaryo", ("sirdaryo", "syrdarya", "sirdarya")),
    Unit("UZ-SU", "Surxondaryo viloyati", "Surxondaryo", ("surxondaryo", "surkhandarya", "surxondarya")),
    Unit("UZ-TO", "Toshkent viloyati", "Toshkent_viloyati",
         ("toshkent viloyati", "toshkent viloyat", "toshkent vil", "toshkent obl",
          "tashkent region", "tashkent oblast")),
    Unit("UZ-TK", "Toshkent shahri", "Toshkent_shahri",
         ("toshkent shahri", "toshkent sh", "tashkent city", "toshkent", "tashkent")),
)
_BY_ISO = {unit.iso: unit for unit in UNITS}


def normalize(text: str) -> str:
    text = str(text).lower()
    for ch in _APOSTROPHES:
        text = text.replace(ch, "")
    for ch in "-_.,":
        text = text.replace(ch, " ")
    return " ".join(text.split())


def available_names() -> str:
    return ", ".join([unit.slug for unit in UNITS] + ["hammasi"])


def find_unit(query: str) -> Unit:
    """Foydalanuvchi yozgan nomdan birlikni topadi (avval to'liq nom, keyin qo'shimchasiz)."""
    text = normalize(query)
    for unit in UNITS:
        if text == normalize(unit.iso) or text in unit.aliases:
            return unit
    stripped = " ".join(word for word in text.split() if word not in _SUFFIXES)
    for unit in UNITS:
        if stripped in unit.aliases:
            return unit
    raise ValueError(f"'{query}' topilmadi. Mumkin bo'lgan nomlar: {available_names()}")


def unit_iso(row) -> str | None:
    """Chegaralar jadvalidagi qator uchun ISO kod (shapeISO bo'lmasa — nomidan)."""
    iso = row.get("shapeISO")
    if isinstance(iso, str) and iso in _BY_ISO:
        return iso
    for column in ("shapeName", "NAME_1", "name", "NAME"):
        if isinstance(row.get(column), str):
            try:
                return find_unit(row[column]).iso
            except ValueError:
                return None
    return None


def unit_label(row) -> str:
    iso = unit_iso(row)
    if iso:
        return _BY_ISO[iso].name
    return str(row.get("shapeName", row.name))


def select_units(boundaries: gpd.GeoDataFrame, query: str | None) -> tuple[gpd.GeoDataFrame, str]:
    """(tanlangan birliklar, fayl nomi uchun belgi). Bo'sh yoki "hammasi" — butun respublika."""
    if query is None or normalize(query) in ALL_KEYWORDS or not normalize(query):
        return boundaries, COUNTRY_LABEL
    unit = find_unit(query)
    isos = boundaries.apply(unit_iso, axis=1)
    subset = boundaries[isos == unit.iso]
    if subset.empty:
        raise ValueError(f"{unit.name} ({unit.iso}) chegaralar faylida topilmadi")
    return subset, unit.slug


def crop_to_units(ds: xr.Dataset, units: gpd.GeoDataFrame, margin_deg: float = 0.1) -> xr.Dataset:
    """Tarmoqni birliklar chegarasi atrofida kesadi (`margin_deg` zaxira bilan)."""
    minx, miny, maxx, maxy = units.total_bounds
    return ds.sel(
        latitude=slice(maxy + margin_deg, miny - margin_deg),
        longitude=slice(minx - margin_deg, maxx + margin_deg),
    )
