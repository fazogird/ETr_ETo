"""`raster_path` papkasidan ETo/ETr rasterlarini topish: `Fargona_ETr_2026_03.tif` → (Fargona, ETr, 2026, 3)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from ..regions import find_unit, normalize

log = logging.getLogger("et_reference")

_NAME = re.compile(
    r"^(?:(?P<prefix>.+)_)?(?P<var>ET[or])_(?P<year>\d{4})_(?P<month>\d{1,2})$", re.IGNORECASE
)


@dataclass(frozen=True)
class RasterRef:
    path: Path
    prefix: str | None  # fayl nomidagi viloyat qismi
    variable: str       # "ETo" | "ETr"
    year: int
    month: int


@dataclass(frozen=True)
class RasterCatalog:
    refs: tuple[RasterRef, ...]

    @property
    def prefix(self) -> str | None:
        """Viloyat nomi (tanilgan bo'lsa — standart belgi, masalan "Fargona")."""
        raw = self.refs[0].prefix
        return _canonical(raw) if raw else None

    @property
    def months(self) -> list[int]:
        return sorted({ref.month for ref in self.refs})

    @property
    def variables(self) -> list[str]:
        return sorted({ref.variable for ref in self.refs})

    def missing(self) -> list[tuple[str, int]]:
        """Qaysi (o'zgaruvchi, oy) juftligi boshqa o'zgaruvchida bor-u, bunda yo'q."""
        have = {(ref.variable, ref.month) for ref in self.refs}
        return [(v, m) for v in self.variables for m in self.months if (v, m) not in have]


def _canonical(prefix: str) -> str:
    try:
        return find_unit(prefix).slug
    except ValueError:
        return prefix


def _key(prefix: str | None) -> str:
    if not prefix:
        return ""
    try:
        return find_unit(prefix).slug.lower()
    except ValueError:
        return normalize(prefix)


def discover_rasters(folder: str | Path, viloyat: str | None = None) -> RasterCatalog:
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"Raster papkasi topilmadi: {folder}")

    refs: list[RasterRef] = []
    for path in sorted(folder.rglob("*")):
        if path.suffix.lower() not in {".tif", ".tiff"}:
            continue
        match = _NAME.match(path.stem)
        month = int(match["month"]) if match else 0
        if not match or not 1 <= month <= 12:
            log.debug("Nom shablonga mos emas, o'tkazib yuborildi: %s", path.name)
            continue
        refs.append(RasterRef(path, match["prefix"], match["var"][:2].upper() + match["var"][2].lower(),
                              int(match["year"]), month))
    if not refs:
        raise FileNotFoundError(
            f"{folder} ichida '<Viloyat>_ETr_<yil>_<oy>.tif' ko'rinishidagi raster topilmadi"
        )

    keys = {_key(ref.prefix) for ref in refs}
    if viloyat:
        wanted = _key(viloyat)
        refs = [ref for ref in refs if _key(ref.prefix) == wanted]
        if not refs:
            raise ValueError(f"'{viloyat}' uchun raster topilmadi. Papkada bor viloyatlar: {sorted(keys)}")
    elif len(keys) > 1:
        raise ValueError(
            f"Papkada bir nechta viloyat rasteri bor: {sorted(keys)}. "
            "Bittasini `viloyat` sozlamasi bilan tanlang."
        )

    seen: dict[tuple[str, int], Path] = {}
    for ref in refs:
        key = (ref.variable, ref.month)
        if key in seen:
            raise ValueError(f"{ref.variable} {ref.month}-oy uchun ikkita raster: {seen[key]} va {ref.path}")
        seen[key] = ref.path

    refs.sort(key=lambda r: (r.variable, r.month))
    return RasterCatalog(tuple(refs))
