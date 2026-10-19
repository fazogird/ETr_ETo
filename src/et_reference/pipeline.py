"""Orkestrator: chegaralar → ERA5-Land → kunlik QC → ETo/ETr → oylik rasterlar va jadval."""

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
import pandas as pd
import xarray as xr

from . import __version__
from .aggregation.temporal import days_per_month, monthly_counts, monthly_totals
from .aggregation.zonal import area_weights, coverage_fraction, weighted_mean
from .calculations import DAILY_SURFACES, daily_reference_et
from .calculations.atmosphere import pressure_altitude, saturation_vapor_pressure
from .calculations.wind import wind_at_2m
from .config import Settings
from .credentials import load_cds_credentials
from .ingestion.archive import HourlyArchive
from .ingestion.boundaries import download_geoboundaries, load_boundaries
from .ingestion.era5land import CdsDownloader, Era5Request, area_from_bounds, plan_requests
from .output.rasters import GridSpec, grid_from_coords, region_mask, write_geotiff
from .output.tables import with_totals, write_table
from .preprocessing.daily import build_daily
from .preprocessing.quality import apply_wind_floor, run_quality_control
from .regions import crop_to_units, select_units, unit_label
from .timeutils import utc_day_span

log = logging.getLogger(__name__)

ERA5_WIND_HEIGHT_M = 10.0
METHOD = "ASCE-EWRI (2005) standardized Penman-Monteith, daily time step"


@dataclass(frozen=True)
class RunResult:
    rasters: list[Path]
    table_file: Path
    summary_file: Path
    table: pd.DataFrame


@dataclass(frozen=True)
class MonthlyFields:
    """Oylik maydonlar: (oy, lat, lon)."""

    totals: dict[str, xr.DataArray]  # ETo/ETr, mm/oy
    days: xr.DataArray  # oydagi kunlar soni (oy,)
    original_share: xr.DataArray  # asl (to'ldirilmagan) ma'lumotli kunlar ulushi


def load_admin_units(settings: Settings) -> gpd.GeoDataFrame:
    region = settings.region
    if region.boundaries_file is not None:
        return load_boundaries(region.boundaries_file)
    path = download_geoboundaries(region.country_iso3, region.adm_level, settings.paths.boundaries)
    return load_boundaries(path)


def plan(settings: Settings, units: gpd.GeoDataFrame) -> list[Era5Request]:
    """Respublika bo'yicha bitta kesh: istalgan viloyat va davr shu fayllardan olinadi."""
    area = settings.region.area or area_from_bounds(
        units.total_bounds, settings.region.area_buffer_deg
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


def monthly_fields(
    daily_et: dict[str, xr.DataArray], original_valid: xr.DataArray, min_valid_fraction: float
) -> MonthlyFields:
    first = next(iter(daily_et.values()))
    days = days_per_month(first)
    original = monthly_counts(original_valid & first.notnull())
    return MonthlyFields(
        totals={name: monthly_totals(da, min_valid_fraction) for name, da in daily_et.items()},
        days=days,
        original_share=original / days,
    )


def run(
    settings: Settings,
    *,
    region: str | None = None,
    download: bool = True,
    client_factory: Callable[..., Any] | None = None,
) -> RunResult:
    """`region`: viloyat nomi ("Fargona", "Toshkent shahri", ...) yoki None/"hammasi"."""
    started = datetime.now(timezone.utc)
    units = load_admin_units(settings)
    selected, label = select_units(units, region)
    log.info(
        "Hudud: %s | davr: %s … %s | vaqt zonasi: %s",
        label, settings.period.start, settings.period.end, settings.region.timezone,
    )
    requests = plan(settings, units)
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
    if len(selected) < len(units):
        daily = crop_to_units(daily, selected)

    latitude = daily["latitude"].values
    filled, original_valid, report = run_quality_control(
        daily, latitude, settings.quality.max_gap_days
    )
    daily_et = compute_daily_et(filled, settings.quality.min_wind_speed)
    fields = monthly_fields(daily_et, original_valid, settings.quality.min_valid_fraction)

    grid = grid_from_coords(latitude, daily["longitude"].values)
    if settings.output.mask_to_region:
        inside = region_mask(selected.geometry, grid, settings.output.all_touched)
    else:
        inside = np.ones((grid.height, grid.width), dtype=bool)

    rasters = write_monthly_rasters(settings, label, fields, grid, inside)
    table = regional_table(selected, grid, latitude, fields)
    table_file = write_table(table, settings.paths.output / f"{label}_ETo_ETr_oylik.csv")
    summary_file = write_summary(
        settings, label, requests, files, grid, report.as_dict(), table, rasters, started
    )
    _log_table(table)
    log.info("Tayyor: %d ta raster va jadval -> %s", len(rasters), settings.paths.output)
    return RunResult(rasters=rasters, table_file=table_file, summary_file=summary_file, table=table)


def write_monthly_rasters(
    settings: Settings, label: str, fields: MonthlyFields, grid: GridSpec, inside: np.ndarray
) -> list[Path]:
    surfaces = {s.name: s for s in DAILY_SURFACES}
    rasters: list[Path] = []
    for i, month in enumerate(fields.days["time"].values):
        stamp = np.datetime_as_string(month, unit="M")  # YYYY-MM
        for name, total in fields.totals.items():
            surface = surfaces[name]
            values = np.where(inside, total.isel(time=i).values, np.nan)
            path = settings.paths.rasters / f"{label}_{name}_{stamp.replace('-', '_')}.tif"
            write_geotiff(
                path, values, grid, nodata=settings.output.nodata,
                description=f"{name} {stamp} [mm/month]",
                tags={
                    "REGION": label,
                    "VARIABLE": name,
                    "UNITS": "mm/month",
                    "MONTH": stamp,
                    "DAYS": int(fields.days.values[i]),
                    "METHOD": METHOD,
                    "REFERENCE_SURFACE": f"Cn={surface.cn:g}, Cd={surface.cd:g}",
                    "SOURCE": "ERA5-Land hourly reanalysis (Copernicus CDS)",
                    "TIMEZONE": settings.region.timezone,
                    "SOFTWARE": f"et-reference {__version__}",
                },
            )
            rasters.append(path)
    return rasters


def regional_table(
    units: gpd.GeoDataFrame, grid: GridSpec, latitude: np.ndarray, fields: MonthlyFields
) -> pd.DataFrame:
    """Har bir birlik va oy uchun maydon-vaznli o'rtacha ETo/ETr [mm]."""
    rows = []
    for _, unit in units.iterrows():
        weights = area_weights(latitude, coverage_fraction([unit.geometry], grid))
        name = unit_label(unit)
        for i, month in enumerate(fields.days["time"].values):
            eto = weighted_mean(fields.totals["ETo"].isel(time=i).values, weights)
            etr = weighted_mean(fields.totals["ETr"].isel(time=i).values, weights)
            days = int(fields.days.values[i])
            rows.append({
                "viloyat": name,
                "oy": np.datetime_as_string(month, unit="M"),
                "kunlar": days,
                "ETo_mm": eto,
                "ETr_mm": etr,
                "ETo_mm_kun": eto / days,
                "ETr_mm_kun": etr / days,
                "ETr_ETo": etr / eto if eto else float("nan"),
                "asl_malumot_foiz": 100.0 * weighted_mean(fields.original_share.isel(time=i).values, weights),
            })
    return with_totals(pd.DataFrame(rows))


def write_summary(
    settings: Settings,
    label: str,
    requests: list[Era5Request],
    files: list[Path],
    grid: GridSpec,
    quality: dict[str, Any],
    table: pd.DataFrame,
    rasters: list[Path],
    started: datetime,
) -> Path:
    """Takrorlanuvchanlik uchun ishga tushirish haqida JSON hisobot."""
    summary = {
        "software": f"et-reference {__version__}",
        "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "region": label,
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
        "table": json.loads(table.round(3).to_json(orient="records", force_ascii=False)),
        "rasters": [p.name for p in rasters],
    }
    path = settings.paths.output / f"{label}_hisobot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _log_table(table: pd.DataFrame) -> None:
    for row in table.itertuples(index=False):
        log.info(
            "%-28s %-8s ETo = %7.1f mm   ETr = %7.1f mm   (ETr/ETo = %.2f)",
            row.viloyat, row.oy, row.ETo_mm, row.ETr_mm, row.ETr_ETo,
        )
