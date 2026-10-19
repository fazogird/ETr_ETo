"""Orkestrator: chegaralar → ERA5-Land → kunlik QC → ETo/ETr → oylik rasterlar."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import xarray as xr

from . import __version__
from .aggregation.temporal import days_per_month, monthly_counts, monthly_totals
from .calculations import DAILY_SURFACES, daily_reference_et
from .calculations.atmosphere import pressure_altitude, saturation_vapor_pressure
from .calculations.wind import wind_at_2m
from .config import Settings
from .credentials import load_cds_credentials
from .ingestion.archive import HourlyArchive
from .ingestion.boundaries import download_geoboundaries, load_boundaries
from .ingestion.era5land import CdsDownloader, Era5Request, area_from_bounds, plan_requests
from .output.rasters import GridSpec, grid_from_coords, region_mask, write_geotiff
from .preprocessing.daily import build_daily
from .preprocessing.quality import apply_wind_floor, run_quality_control
from .timeutils import utc_day_span

log = logging.getLogger(__name__)

ERA5_WIND_HEIGHT_M = 10.0
METHOD = "ASCE-EWRI (2005) standardized Penman-Monteith, daily time step"


@dataclass(frozen=True)
class RunResult:
    rasters: list[Path]
    summary_file: Path


def load_region(settings: Settings) -> gpd.GeoDataFrame:
    region = settings.region
    if region.boundaries_file is not None:
        return load_boundaries(region.boundaries_file)
    path = download_geoboundaries(region.country_iso3, region.adm_level, settings.paths.boundaries)
    return load_boundaries(path)


def plan(settings: Settings, region: gpd.GeoDataFrame) -> list[Era5Request]:
    area = settings.region.area or area_from_bounds(
        region.total_bounds, settings.region.area_buffer_deg
    )
    first_day, last_day = utc_day_span(
        settings.period.start, settings.period.end, settings.region.timezone
    )
    return plan_requests(first_day, last_day, area, settings.cds.split_by_variable)


def obtain_hourly_files(
    settings: Settings,
    requests: list[Era5Request],
    *,
    download: bool,
    client_factory: Callable[..., Any] | None = None,
) -> list[Path]:
    """Keshdagi fayllarni qaytaradi; yetishmaganlarini (ruxsat bo'lsa) CDS dan yuklaydi."""
    target_dir = settings.paths.hourly
    missing = [r for r in requests if not (target_dir / r.filename).is_file()]
    if missing:
        if not download:
            raise FileNotFoundError(
                f"Keshda {len(missing)} ta ERA5-Land fayli yo'q (masalan: {missing[0].filename}). "
                "--skip-download siz ishga tushiring."
            )
        credentials = load_cds_credentials(settings.cds.credentials)
        log.info("CDS kaliti topildi: %s", credentials.source or "muhit o'zgaruvchisi")
        downloader = CdsDownloader.from_credentials(
            credentials, settings.cds.dataset, target_dir, client_factory
        )
        downloader.fetch(missing)
    return [target_dir / r.filename for r in requests]


def compute_daily_et(daily: xr.Dataset, min_wind_speed: float) -> dict[str, xr.DataArray]:
    """Har bir piksel-kun uchun ETo va ETr [mm d⁻¹]; manfiy qiymatlar 0 ga tenglanadi."""
    daily = daily.transpose("time", "latitude", "longitude")
    # Balandlik ERA5-Land ning o'z sirt bosimidan (bosim balandligi) olinadi, shuning uchun
    # harorat maydonlari bilan bir xil model relyefiga mos keladi.
    elevation = pressure_altitude(daily["sp"].mean("time", skipna=True).values)
    u2 = apply_wind_floor(wind_at_2m(daily["wind10"].values, ERA5_WIND_HEIGHT_M), min_wind_speed)
    values = daily_reference_et(
        tmax=daily["tmax"].values,
        tmin=daily["tmin"].values,
        ea=saturation_vapor_pressure(daily["tdew"].values),
        rs=daily["rs"].values,
        u2=u2,
        elevation=elevation,
        lat_deg=daily["latitude"].values[:, np.newaxis],
        doy=daily["time"].dt.dayofyear.values[:, np.newaxis, np.newaxis],
    )
    template = daily["tmax"]
    return {
        name: template.copy(data=np.maximum(et, 0.0)).assign_attrs(units="mm d-1", long_name=name)
        for name, et in values.items()
    }


def run(
    settings: Settings,
    *,
    download: bool = True,
    client_factory: Callable[..., Any] | None = None,
) -> RunResult:
    started = datetime.now(timezone.utc)
    log.info(
        "Davr: %s … %s | vaqt zonasi: %s",
        settings.period.start, settings.period.end, settings.region.timezone,
    )
    region = load_region(settings)
    requests = plan(settings, region)
    log.info("Hudud: %d ta birlik; CDS hududi [N, W, S, E] = %s", len(region), list(requests[0].area))

    files = obtain_hourly_files(settings, requests, download=download, client_factory=client_factory)
    archive = HourlyArchive(files)
    try:
        daily = build_daily(
            archive,
            settings.period,
            settings.region.timezone,
            ssrd_mode=settings.cds.ssrd_mode,
            min_hours=settings.quality.min_hours_per_day,
        )
    finally:
        archive.close()

    latitude = daily["latitude"].values
    filled, original_valid, report = run_quality_control(
        daily, latitude, settings.quality.max_gap_days
    )
    daily_et = compute_daily_et(filled, settings.quality.min_wind_speed)

    grid = grid_from_coords(latitude, daily["longitude"].values)
    if settings.output.mask_to_region:
        inside = region_mask(region.geometry, grid, settings.output.all_touched)
    else:
        inside = np.ones((grid.height, grid.width), dtype=bool)

    rasters, monthly_stats = write_monthly_rasters(
        settings, daily_et, original_valid, grid, inside
    )
    summary_file = write_summary(
        settings, requests, files, grid, report.as_dict(), monthly_stats, rasters, started
    )
    log.info("Tayyor: %d ta raster -> %s", len(rasters), settings.paths.rasters)
    return RunResult(rasters=rasters, summary_file=summary_file)


def write_monthly_rasters(
    settings: Settings,
    daily_et: dict[str, xr.DataArray],
    original_valid: xr.DataArray,
    grid: GridSpec,
    inside: np.ndarray,
) -> tuple[list[Path], list[dict[str, Any]]]:
    nodata = settings.output.nodata
    min_fraction = settings.quality.min_valid_fraction
    totals = {name: monthly_totals(da, min_fraction) for name, da in daily_et.items()}
    first = next(iter(daily_et.values()))
    valid_days = monthly_counts(original_valid & first.notnull())
    n_days = days_per_month(first)
    surfaces = {s.name: s for s in DAILY_SURFACES}

    rasters: list[Path] = []
    stats: list[dict[str, Any]] = []
    for i, month in enumerate(valid_days["time"].values):
        stamp = np.datetime_as_string(month, unit="M")  # YYYY-MM
        suffix = stamp.replace("-", "_")
        common_tags = {
            "MONTH": stamp,
            "DAYS_IN_MONTH": int(n_days.values[i]),
            "SOURCE": "ERA5-Land hourly reanalysis (Copernicus CDS)",
            "TIMEZONE": settings.region.timezone,
            "SOFTWARE": f"et-reference {__version__}",
        }
        month_stats: dict[str, Any] = {"month": stamp}
        for name, total in totals.items():
            surface = surfaces[name]
            values = np.where(inside, total.isel(time=i).values, np.nan)
            path = settings.paths.rasters / f"{name}_{suffix}.tif"
            write_geotiff(
                path, values, grid, nodata=nodata,
                description=f"{name} {stamp} [mm/month]",
                tags={
                    **common_tags,
                    "VARIABLE": name,
                    "UNITS": "mm/month",
                    "METHOD": METHOD,
                    "REFERENCE_SURFACE": f"Cn={surface.cn:g}, Cd={surface.cd:g}",
                },
            )
            rasters.append(path)
            month_stats[f"{name}_mean_mm"] = _nanmean(values)

        days = np.where(inside, valid_days.isel(time=i).values, np.nan)
        path = settings.paths.rasters / f"valid_days_{suffix}.tif"
        write_geotiff(
            path, days, grid, nodata=nodata, dtype="int16",
            description=f"valid days {stamp}",
            tags={**common_tags, "VARIABLE": "valid_days", "UNITS": "days"},
        )
        rasters.append(path)

        if month_stats.get("ETo_mean_mm"):
            month_stats["ETr_to_ETo"] = round(month_stats["ETr_mean_mm"] / month_stats["ETo_mean_mm"], 3)
        stats.append(month_stats)
        log.info(
            "%s: hudud piksellari o'rtachasi ETo = %s mm, ETr = %s mm",
            stamp, month_stats.get("ETo_mean_mm"), month_stats.get("ETr_mean_mm"),
        )
    return rasters, stats


def write_summary(
    settings: Settings,
    requests: list[Era5Request],
    files: list[Path],
    grid: GridSpec,
    quality: dict[str, Any],
    monthly_stats: list[dict[str, Any]],
    rasters: list[Path],
    started: datetime,
) -> Path:
    """Takrorlanuvchanlik uchun ishga tushirish haqida JSON hisobot."""
    summary = {
        "software": f"et-reference {__version__}",
        "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "period": {"start": str(settings.period.start), "end": str(settings.period.end)},
        "timezone": settings.region.timezone,
        "method": METHOD,
        "cds_area_NWSE": list(requests[0].area),
        "grid": {
            "crs": grid.crs,
            "width": grid.width,
            "height": grid.height,
            "transform": list(grid.transform)[:6],
        },
        "era5land_files": [p.name for p in files],
        "quality_control": quality,
        "monthly_region_pixel_means": monthly_stats,
        "rasters": [p.name for p in rasters],
    }
    path = settings.paths.output / "run_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _nanmean(values: np.ndarray) -> float | None:
    finite = values[np.isfinite(values)]
    return round(float(finite.mean()), 2) if finite.size else None
