"""YAML sozlamalarini o'qish va tekshirish."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml


class ConfigError(ValueError):
    """Sozlamalardagi xato."""


@dataclass(frozen=True)
class Period:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ConfigError(f"period.end ({self.end}) period.start ({self.start}) dan oldin")


@dataclass(frozen=True)
class RegionSettings:
    country_iso3: str = "UZB"
    adm_level: str = "ADM1"
    boundaries_file: Path | None = None
    area: tuple[float, float, float, float] | None = None  # N, W, S, E
    area_buffer_deg: float = 0.2
    timezone: str = "Asia/Tashkent"


@dataclass(frozen=True)
class CdsSettings:
    dataset: str = "reanalysis-era5-land"
    credentials: Path | None = None
    split_by_variable: bool = False
    ssrd_mode: str = "auto"


@dataclass(frozen=True)
class QualitySettings:
    max_gap_days: int = 3
    min_valid_fraction: float = 0.9
    min_wind_speed: float = 0.5
    min_hours_per_day: int = 24


@dataclass(frozen=True)
class OutputSettings:
    nodata: float = -9999.0
    all_touched: bool = True
    mask_to_region: bool = True


@dataclass(frozen=True)
class Paths:
    root: Path
    cache: Path
    output: Path

    @property
    def hourly(self) -> Path:
        return self.cache / "era5land"

    @property
    def boundaries(self) -> Path:
        return self.cache / "boundaries"

    @property
    def rasters(self) -> Path:
        return self.output

    @property
    def logs(self) -> Path:
        return self.output / "logs"


@dataclass(frozen=True)
class Settings:
    period: Period
    region: RegionSettings
    cds: CdsSettings
    quality: QualitySettings
    output: OutputSettings
    paths: Paths


def load_settings(
    path: str | Path,
    *,
    start: str | date | None = None,
    end: str | date | None = None,
) -> Settings:
    """YAML faylni o'qiydi; `start`/`end` berilsa, fayldagi davr almashtiriladi."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Sozlamalar fayli topilmadi: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    config_dir = path.resolve().parent

    period_raw = _section(raw, "period")
    period = Period(
        start=_as_date(start if start is not None else period_raw.get("start"), "period.start"),
        end=_as_date(end if end is not None else period_raw.get("end"), "period.end"),
    )

    paths_raw = _section(raw, "paths")
    root = (config_dir / str(paths_raw.get("root", ".."))).resolve()
    paths = Paths(
        root=root,
        cache=_resolve(root, paths_raw.get("cache", "data/cache")),
        output=_resolve(root, paths_raw.get("output", "outputs")),
    )

    region = _build(RegionSettings, _section(raw, "region"))
    region = replace(
        region,
        country_iso3=str(region.country_iso3).upper(),
        boundaries_file=_resolve(root, region.boundaries_file) if region.boundaries_file else None,
        area=_as_area(region.area),
    )
    _check_timezone(region.timezone)

    cds = _build(CdsSettings, _section(raw, "cds"))
    cds = replace(cds, credentials=Path(cds.credentials) if cds.credentials else None)
    if cds.ssrd_mode not in {"auto", "accumulated", "hourly"}:
        raise ConfigError(f"cds.ssrd_mode noto'g'ri: {cds.ssrd_mode}")

    quality = _build(QualitySettings, _section(raw, "quality"))
    if quality.max_gap_days < 0:
        raise ConfigError("quality.max_gap_days manfiy bo'lmasligi kerak")
    if not 0.0 < quality.min_valid_fraction <= 1.0:
        raise ConfigError("quality.min_valid_fraction (0, 1] oralig'ida bo'lishi kerak")
    if not 1 <= quality.min_hours_per_day <= 24:
        raise ConfigError("quality.min_hours_per_day [1, 24] oralig'ida bo'lishi kerak")

    output = _build(OutputSettings, _section(raw, "output"))
    output = replace(output, nodata=float(output.nodata))

    return Settings(period, region, cds, quality, output, paths)


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name) or {}
    if not isinstance(value, dict):
        raise ConfigError(f"'{name}' bo'limi lug'at (mapping) bo'lishi kerak")
    return value


def _build(cls: type, values: dict[str, Any]):
    known = set(cls.__dataclass_fields__)
    unknown = set(values) - known
    if unknown:
        raise ConfigError(f"{cls.__name__}: noma'lum kalitlar {sorted(unknown)}")
    return cls(**values)


def _as_date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ConfigError(f"{field} sana bo'lishi kerak (YYYY-MM-DD), berilgan: {value!r}")


def _as_area(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ConfigError("region.area [N, W, S, E] ko'rinishida bo'lishi kerak")
    north, west, south, east = (float(v) for v in value)
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ConfigError(f"region.area noto'g'ri: {value}")
    return north, west, south, east


def _resolve(root: Path, value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else (root / path).resolve()


def _check_timezone(name: str) -> None:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ConfigError(f"Noma'lum vaqt zonasi: {name}") from exc
