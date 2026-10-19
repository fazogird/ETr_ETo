"""ERA5-Land soatlik ma'lumotlarini CDS dan oyma-oy yuklash va keshlash."""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..credentials import CdsCredentials

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
    def filename(self) -> str:
        if set(self.variables) == set(VARIABLES):
            tag = "all"
        else:
            tag = "-".join(VARIABLES[v] for v in self.variables)
        area_id = hashlib.md5(repr(self.area).encode()).hexdigest()[:6]
        return (
            f"era5land_{self.year}{self.month:02d}"
            f"_d{self.days[0]:02d}-{self.days[-1]:02d}_{tag}_{area_id}.nc"
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


class CdsDownloader:
    """So'rovlarni ketma-ket bajaradi; tayyor fayllar qayta yuklanmaydi."""

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
        paths = []
        for index, request in enumerate(requests, start=1):
            target = self._target_dir / request.filename
            paths.append(target)
            if target.is_file() and target.stat().st_size > 0:
                log.info("[%d/%d] keshda bor: %s", index, len(requests), target.name)
                continue
            log.info(
                "[%d/%d] CDS so'rovi: %d-%02d, kunlar %02d–%02d, %d ta o'zgaruvchi",
                index, len(requests), request.year, request.month,
                request.days[0], request.days[-1], len(request.variables),
            )
            partial = target.with_name(target.name + ".part")
            self._client.retrieve(self._dataset, request.to_cds(), str(partial))
            partial.replace(target)
        return paths


def cached_paths(requests: Sequence[Era5Request], target_dir: Path) -> list[Path]:
    """Yuklamasdan ishlash rejimi: kerakli fayllar keshda borligini tekshiradi."""
    paths = [Path(target_dir) / r.filename for r in requests]
    missing = [p.name for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Keshda {len(missing)} ta fayl yo'q (masalan: {missing[0]}). "
            "--skip-download siz ishga tushiring."
        )
    return paths
