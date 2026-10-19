"""Zonal hisob sozlamalari (foydalanuvchi kiritadigan qiymatlar)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Teng-maydonli global CRS (EPSG:6933): maydon har qanday viloyatda ham buzilmaydi,
# shuning uchun UTM zonasini tanlash kerak emas.
AUTO_AREA_CRS = "EPSG:6933"


@dataclass(frozen=True)
class ZonalSettings:
    shp_path: Path
    raster_path: Path
    output_path: Path
    crop_column: str | None = None  # ekin turi ustuni; None bo'lsa tur bo'yicha varaqlar chiqmaydi
    area_crs: str = "auto"          # "auto" (EPSG:6933) | "utm" | istalgan proyeksiyalangan EPSG, masalan "EPSG:32642"
    viloyat: str | None = None      # rasterlar papkasida bir nechta viloyat bo'lsa, tanlash uchun
    nodata: float = -9999.0         # raster NoData va shp'dagi "qiymat yo'q" belgisi
    max_fill_pixels: float = 2.0    # NoData'ga tushgan dala uchun eng yaqin yaroqli piksel masofasi (piksel o'lchamida)

    def __post_init__(self) -> None:
        for name in ("shp_path", "raster_path", "output_path"):
            object.__setattr__(self, name, Path(getattr(self, name)).expanduser())
