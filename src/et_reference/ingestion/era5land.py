"""ERA5-Land soatlik ma'lumotlarini CDS dan oyma-oy yuklash va keshlash."""

from __future__ import annotations

import hashlib
import logging
import math
import re
import tempfile
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import xarray as xr

from ..credentials import CdsCredentials
from .archive import file_covers_area

log = logging.getLogger(__name__)

# CDS o'zgaruvchi nomi -> NetCDF dagi qisqa nom
VARIABLES: dict[str, str] = {
    "2m_temperature": "t2m",
    "2m_dewpoint_temperature": "d2m",
    "10m_u_component_of_wind": "u10",
    "10m_v_component_of_wind": "v10",
    "surface_solar_radiation_downwards": "ssrd",
    "surface_pressure": "sp",
}
GRID_STEP_DEG = 0.1


@dataclass(frozen=True)
class Era5Request:
    year: int
    month: int
    days: tuple[int, ...]
    variables: tuple[str, ...]
    area: tuple[float, float, float, float]  # N, W, S, E

    @property
    def tag(self) -> str:
        if set(self.variables) == set(VARIABLES):
            return "all"
        return "-".join(VARIABLES[v] for v in self.variables)

    @property
    def filename(self) -> str:
        area_id = hashlib.md5(repr(self.area).encode()).hexdigest()[:6]
        return (
            f"era5land_{self.year}{self.month:02d}"
            f"_d{self.days[0]:02d}-{self.days[-1]:02d}_{self.tag}_{area_id}.nc"
        )

    def to_cds(self) -> dict[str, Any]:
        return {
            "variable": list(self.variables),
            "year": f"{self.year}",
            "month": f"{self.month:02d}",
            "day": [f"{d:02d}" for d in self.days],
            "time": [f"{h:02d}:00" for h in range(24)],
            "area": list(self.area),
            "data_format": "netcdf",
            "download_format": "unarchived",
        }


def plan_requests(
    first_day: date,
    last_day: date,
    area: tuple[float, float, float, float],
    split_by_variable: bool = False,
) -> list[Era5Request]:
    """UTC kunlari oralig'ini kalendar oylar bo'yicha CDS so'rovlariga bo'ladi."""
    if last_day < first_day:
        raise ValueError("last_day first_day dan oldin")
    by_month: dict[tuple[int, int], list[int]] = {}
    day = first_day
    while day <= last_day:
        by_month.setdefault((day.year, day.month), []).append(day.day)
        day += timedelta(days=1)

    variable_groups = [(v,) for v in VARIABLES] if split_by_variable else [tuple(VARIABLES)]
    return [
        Era5Request(year, month, tuple(days), group, area)
        for (year, month), days in sorted(by_month.items())
        for group in variable_groups
    ]


def area_from_bounds(
    bounds: Sequence[float], buffer_deg: float, step: float = GRID_STEP_DEG
) -> tuple[float, float, float, float]:
    """(minx, miny, maxx, maxy) -> ERA5-Land tarmog'iga tashqariga yaxlitlangan [N, W, S, E]."""
    minx, miny, maxx, maxy = bounds
    north = math.ceil((maxy + buffer_deg) / step) * step
    south = math.floor((miny - buffer_deg) / step) * step
    west = math.floor((minx - buffer_deg) / step) * step
    east = math.ceil((maxx + buffer_deg) / step) * step
    return (
        round(min(north, 90.0), 4),
        round(max(west, -180.0), 4),
        round(max(south, -90.0), 4),
        round(min(east, 180.0), 4),
    )


class DownloadError(RuntimeError):
    """Bir yoki bir nechta CDS so'rovi bajarilmadi."""


def finalize_download(partial: Path, target: Path) -> None:
    """Yuklangan faylni `target` ga joylaydi.

    Yangi CDS lahzalik va yig'ilgan o'zgaruvchilarni (stepType) alohida .nc fayllarga
    ajratib, ZIP qilib qaytarishi mumkin. Bunday holda ular bitta NetCDF ga birlashtiriladi.
    """
    if not zipfile.is_zipfile(partial):
        partial.replace(target)
        return
    merged_partial = target.with_name(target.name + ".merge.part")
    with zipfile.ZipFile(partial) as archive, tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        members = [name for name in archive.namelist() if name.endswith(".nc")]
        if not members:
            raise DownloadError(f"CDS arxivida .nc fayl yo'q: {archive.namelist()}")
        archive.extractall(tmp, members)
        datasets = [xr.open_dataset(Path(tmp) / name) for name in members]
        try:
            merged = xr.merge(datasets, compat="override", combine_attrs="drop_conflicts")
            merged.to_netcdf(merged_partial)
        except Exception:
            merged_partial.unlink(missing_ok=True)
            raise
        finally:
            for ds in datasets:  # Windows: vaqtinchalik papka o'chishidan oldin fayllar yopilishi shart
                ds.close()
    log.info("CDS ZIP (%d ta fayl) bitta NetCDF ga birlashtirildi", len(members))
    merged_partial.replace(target)
    partial.unlink()


class CdsDownloader:
    """So'rovlarni ketma-ket bajaradi; tayyor fayllar qayta yuklanmaydi.

    Bitta so'rov xato bersa ham qolganlari davom etadi, oxirida umumiy xato chiqariladi.
    Keyingi ishga tushirishda faqat yetishmagan oylar yuklanadi.
    """

    def __init__(self, client: Any, dataset: str, target_dir: Path) -> None:
        self._client = client
        self._dataset = dataset
        self._target_dir = Path(target_dir)

    @classmethod
    def from_credentials(
        cls,
        credentials: CdsCredentials,
        dataset: str,
        target_dir: Path,
        client_factory: Callable[..., Any] | None = None,
    ) -> CdsDownloader:
        if client_factory is None:
            import cdsapi

            client_factory = cdsapi.Client
        client = client_factory(url=credentials.url, key=credentials.key)
        return cls(client, dataset, target_dir)

    def fetch(self, requests: Sequence[Era5Request]) -> list[Path]:
        self._target_dir.mkdir(parents=True, exist_ok=True)
        paths, failed = [], []
        for index, request in enumerate(requests, start=1):
            target = self._target_dir / request.filename
            paths.append(target)
            if target.is_file() and target.stat().st_size > 0:
                log.info("[%d/%d] keshda bor: %s", index, len(requests), target.name)
                continue
            label = f"{request.year}-{request.month:02d}"
            log.info(
                "[%d/%d] CDS so'rovi: %s, kunlar %02d–%02d, %d ta o'zgaruvchi (navbat kutilmoqda...)",
                index, len(requests), label, request.days[0], request.days[-1], len(request.variables),
            )
            partial = target.with_name(target.name + ".part")
            try:
                self._client.retrieve(self._dataset, request.to_cds(), str(partial))
                finalize_download(partial, target)
            except Exception as exc:  # noqa: BLE001 — bitta oy xatosi qolganlarini to'xtatmasin
                log.error("[%d/%d] %s yuklanmadi: %s", index, len(requests), label, exc)
                failed.append(label)
                partial.unlink(missing_ok=True)
                continue
            log.info("[%d/%d] %s tayyor: %s", index, len(requests), label, target.name)
        if failed:
            raise DownloadError(
                f"{len(failed)} ta so'rov bajarilmadi ({', '.join(failed)}). "
                "Qayta ishga tushiring — tayyor oylar keshdan olinadi."
            )
        return paths


_CACHE_NAME = re.compile(r"era5land_(\d{4})(\d{2})_d(\d{2})-(\d{2})_([a-z0-9-]+)_[0-9a-f]{6}\.nc$")


def find_cached(request: Era5Request, cache_dir: Path) -> Path | None:
    """So'rovni qoplaydigan keshdagi fayl: aynan shu fayl yoki shu oy uchun kattaroq
    (ko'proq kun, ko'proq o'zgaruvchi yoki kengroq hudud) yuklangan fayl."""
    cache_dir = Path(cache_dir)
    exact = cache_dir / request.filename
    if exact.is_file():
        return exact
    for candidate in sorted(cache_dir.glob(f"era5land_{request.year}{request.month:02d}_d*.nc")):
        match = _CACHE_NAME.match(candidate.name)
        if not match:
            continue
        first_day, last_day, tag = int(match[3]), int(match[4]), match[5]
        if not (first_day <= request.days[0] and request.days[-1] <= last_day):
            continue
        if tag not in ("all", request.tag):
            continue
        if file_covers_area(candidate, request.area):
            return candidate
    return None
