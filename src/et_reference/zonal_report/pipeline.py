"""Zonal hisobot zanjiri: rasterlarni topish → shp'ni moslash → zonal → shp + Excel."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import naming
from .calculations.field_table import compute_field_table
from .calculations.summary import summarize, summarize_by_crop
from .calculations.weights import build_pixel_weights
from .calculations.zonal import STATUS_LABELS
from .discovery import RasterCatalog, discover_rasters
from .output.excel import write_report
from .output.shapefile import write_shapefile
from .preprocessing.rasters import load_raster_stack
from .preprocessing.vector import load_fields
from .settings import ZonalSettings

log = logging.getLogger("et_reference")


@dataclass(frozen=True)
class ZonalOutputs:
    viloyat: str
    shapefile: Path
    excel: Path


def resolve_output(output_path: Path, catalog: RasterCatalog) -> tuple[str, Path]:
    """Viloyat nomi fayl nomidan; topilmasa `output_path` papkasi nomidan. Natija papkasi: `output_path/<Viloyat>`."""
    if catalog.prefix:
        return catalog.prefix, output_path / catalog.prefix
    return output_path.resolve().name, output_path


def run(settings: ZonalSettings) -> ZonalOutputs:
    catalog = discover_rasters(settings.raster_path, settings.viloyat)
    viloyat, out_dir = resolve_output(settings.output_path, catalog)
    log.info("Viloyat: %s; rasterlar: %d ta (%s), oylar: %s",
             viloyat, len(catalog.refs), "/".join(catalog.variables), catalog.months)

    stack = load_raster_stack(catalog, settings.nodata)
    log.info("Shp o'qilmoqda va CRS moslanmoqda (katta fayl bo'lsa, bir necha soniya/daqiqa)...")
    fields = load_fields(
        settings.shp_path, stack.grid.crs, area_crs=settings.area_crs, crop_column=settings.crop_column
    )
    log.info("Dala ↔ piksel ulushlari hisoblanmoqda (%d ta dala)...", len(fields.geometries))
    weights = build_pixel_weights(fields.geometries, stack.grid)
    log.info("Zonal statistika: %d ta raster...", len(stack.arrays))
    table = compute_field_table(stack, weights, fields.area_m2, settings.max_fill_pixels)

    area_ha = pd.Series(fields.area_m2 / 10_000.0)
    sheets: dict[str, pd.DataFrame] = {}
    for variable in catalog.variables:
        months = sorted(m for v, m in stack.arrays if v == variable)
        sheets[variable] = summarize(table.values, area_ha, variable, months)
    if fields.crop is not None:
        for variable in catalog.variables:
            months = sorted(m for v, m in stack.arrays if v == variable)
            sheets[f"{variable}_tur"] = summarize_by_crop(
                table.values, area_ha, fields.crop.reset_index(drop=True), variable, months
            )

    log.info("Shp va Excel yozilmoqda...")
    shp_path = write_shapefile(
        fields.frame, table, area_ha.to_numpy(), out_dir / f"{viloyat}_ET_zonal.shp", settings.nodata
    )
    excel_path = write_report(
        out_dir / f"{viloyat}_ET_hisobot.xlsx", sheets, _quality_rows(viloyat, settings, catalog, fields, table.status)
    )
    log.info("Tayyor: %s ; %s", shp_path, excel_path)
    return ZonalOutputs(viloyat, shp_path, excel_path)


def _quality_rows(viloyat, settings, catalog, fields, status) -> list[tuple[str, str]]:
    notes = fields.notes
    rows = [
        ("Viloyat", viloyat),
        ("Shp fayl", str(settings.shp_path)),
        ("Shp CRS", notes["shp_crs"]),
        ("Raster CRS", notes["raster_crs"]),
        ("CRS moslashtirildi (shp → raster)", "ha" if notes["crs_aligned"] else "yo'q, bir xil edi"),
        ("Maydon hisoblangan CRS", f"{notes['area_crs']} (teng-maydonli/proyeksiyalangan)"),
        ("Dalalar soni", str(notes["n_fields"])),
        ("Bo'sh geometriya", str(notes["n_empty"])),
        ("Hisob uchun tuzatilgan yaroqsiz geometriya", str(notes["n_repaired"])),
        ("Rasterlar", ", ".join(f"{r.variable}{r.month}" for r in catalog.refs)),
    ]
    missing = catalog.missing()
    rows.append(("Yetishmayotgan rasterlar", ", ".join(f"{v}{m}" for v, m in missing) or "yo'q"))
    if missing:
        rows.append(("Ogohlantirish", "Yetishmagan oy bor o'zgaruvchining mavsum yig'indisi (JAMI) faqat mavjud oylarni qamraydi."))
    area_col = notes.get("area_column")
    if area_col:
        rows.append((
            f"Shp'dagi '{area_col['column']}' ustuni",
            f"o'rtacha nisbat (u / bizning ga) = {area_col['median_ratio_to_ga']:.4g} → {area_col['interpretation']}",
        ))
    for code, label in STATUS_LABELS.items():
        rows.append((f"ET_QC = {code}: {label}", str(int(np.sum(status == code)))))
    rows += [
        ("Usul: zonal o'rtacha", "dala ichidagi piksellar bo'yicha, dalaning har pikselga tushgan yuza ulushi bilan vaznli"),
        ("Usul: o'tkazish", "m³ = mm/1000 × maydon(m²); m³/ga = m³ / maydon(ga) (= mm × 10)"),
        ("Usul: o'rtacha mm va m³/ga (Excel)", "jami m³ / hisobga olingan dalalar maydoni (maydon bo'yicha vaznli)"),
        ("Shp'dagi qiymati yo'q dalalar", f"{settings.nodata:g} bilan belgilangan"),
    ]
    return rows
