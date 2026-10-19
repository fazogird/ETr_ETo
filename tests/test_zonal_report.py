from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from et_reference.zonal_report import naming
from et_reference.zonal_report.calculations.units import m3_to_m3ha, mm_to_m3
from et_reference.zonal_report.calculations.weights import build_pixel_weights
from et_reference.zonal_report.calculations.zonal import (
    STATUS_FILLED, STATUS_NODATA, STATUS_OK, STATUS_PARTIAL, zonal_mean,
)
from et_reference.zonal_report.discovery import discover_rasters
from et_reference.zonal_report.pipeline import run
from et_reference.zonal_report.preprocessing.rasters import load_raster_stack
from et_reference.zonal_report.preprocessing.vector import load_fields, resolve_area_crs
from et_reference.zonal_report.settings import ZonalSettings

NODATA = -9999.0
TRANSFORM = from_origin(68.95, 41.05, 0.1, 0.1)  # 4 ustun x 3 qator, markazlari 69.0.. / 41.0..


def _write_raster(path: Path, data: np.ndarray) -> None:
    with rasterio.open(path, "w", driver="GTiff", height=3, width=4, count=1, dtype="float32",
                       crs="EPSG:4326", transform=TRANSFORM, nodata=NODATA) as dst:
        dst.write(np.where(np.isfinite(data), data, NODATA).astype("float32"), 1)


def _etr(month: int) -> np.ndarray:
    data = np.tile(np.array([10.0, 20.0, 30.0, 40.0]) * month, (3, 1))
    data[0, 3] = np.nan  # NoData: C dalasi tushadigan piksel
    data[1, 3] = np.nan  # uning pastidagi piksel ham, shunda eng yaqin yaroqli piksel yagona (30)
    return data


@pytest.fixture
def raster_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "rasters"
    folder.mkdir()
    for month in (3, 4):
        _write_raster(folder / f"Fargona_ETr_2026_{month:02d}.tif", _etr(month))
        _write_raster(folder / f"Fargona_ETo_2026_{month:02d}.tif", _etr(month) * 0.5)
    return folder


FIELDS = {
    "A": box(69.00, 40.96, 69.10, 41.00),  # col0 va col1 yarimtadan -> (10+20)/2 * oy
    "B": box(69.20, 40.96, 69.25, 41.00),  # col2 -> 30 * oy
    "C": box(69.31, 41.00, 69.34, 41.04),  # NoData pikselda -> eng yaqin yaroqli (col2: 30 * oy)
    "D": box(70.50, 41.50, 70.60, 41.60),  # raster tashqarisida -> qiymat yo'q
    "E": box(69.20, 40.96, 69.30, 41.00),  # yarmi col2, yarmi NoData -> qisman
}
CROPS = {"A": "paxta", "B": "paxta", "C": "bug'doy", "D": "bug'doy", "E": "paxta"}


@pytest.fixture
def shp_file(tmp_path: Path) -> Path:
    """Dalalar UTM 42N (EPSG:32642) da — raster esa EPSG:4326: CRS moslash tekshiriladi."""
    gdf = gpd.GeoDataFrame(
        {"id": list(FIELDS), "turi": [CROPS[k] for k in FIELDS]},
        geometry=list(FIELDS.values()), crs="EPSG:4326",
    ).to_crs("EPSG:32642")
    gdf["maydon"] = gdf.geometry.area / 10_000.0  # gektarda
    path = tmp_path / "dalalar.shp"
    gdf.to_file(path)
    return path


def test_discovery_parses_names_and_rejects_ambiguity(raster_dir, tmp_path):
    catalog = discover_rasters(raster_dir)
    assert catalog.prefix == "Fargona"
    assert catalog.months == [3, 4] and catalog.variables == ["ETo", "ETr"]
    assert catalog.missing() == []

    _write_raster(raster_dir / "Samarqand_ETr_2026_03.tif", _etr(3))
    with pytest.raises(ValueError, match="bir nechta viloyat"):
        discover_rasters(raster_dir)
    assert discover_rasters(raster_dir, viloyat="Farg'ona").prefix == "Fargona"
    with pytest.raises(FileNotFoundError):
        discover_rasters(tmp_path / "yoq")


def test_pixel_weights_split_field_between_two_pixels(raster_dir):
    stack = load_raster_stack(discover_rasters(raster_dir), NODATA)
    weights = build_pixel_weights(np.array([FIELDS["A"]], dtype=object), stack.grid)
    assert sorted(weights.pixel.tolist()) == [0, 1]
    assert weights.fraction == pytest.approx([0.5, 0.5])
    assert weights.total_fraction[0] == pytest.approx(1.0)


def test_zonal_mean_statuses(raster_dir):
    stack = load_raster_stack(discover_rasters(raster_dir), NODATA)
    geoms = np.array(list(FIELDS.values()), dtype=object)
    weights = build_pixel_weights(geoms, stack.grid)
    result = zonal_mean(weights, stack.arrays[("ETr", 3)], stack.grid, max_fill_pixels=2)
    assert result.mean[:3] == pytest.approx([45.0, 90.0, 90.0])  # A, B, C(to'ldirilgan); 3-oy: qiymat = ustun*10*3
    assert np.isnan(result.mean[3])
    assert result.mean[4] == pytest.approx(90.0)
    assert result.status.tolist() == [STATUS_OK, STATUS_OK, STATUS_FILLED, STATUS_NODATA, STATUS_PARTIAL]


def test_fill_respects_max_distance(raster_dir):
    stack = load_raster_stack(discover_rasters(raster_dir), NODATA)
    weights = build_pixel_weights(np.array([FIELDS["C"]], dtype=object), stack.grid)
    result = zonal_mean(weights, stack.arrays[("ETr", 3)], stack.grid, max_fill_pixels=0.5)
    assert result.status[0] == STATUS_NODATA and np.isnan(result.mean[0])


def test_unit_conversion_chain():
    mm, area = np.array([120.0, 80.0]), np.array([25_000.0, 0.0])  # 2.5 ga va maydonsiz
    m3 = mm_to_m3(mm, area)
    assert m3[0] == pytest.approx(3000.0)         # 0.12 m * 25000 m²
    m3ha = m3_to_m3ha(m3, area)
    assert m3ha[0] == pytest.approx(1200.0)       # = mm * 10
    assert np.isnan(m3ha[1])


def test_auto_area_crs_agrees_with_utm_for_fargona_sized_field():
    frame = gpd.GeoDataFrame(geometry=[box(71.6, 40.3, 71.8, 40.5)], crs="EPSG:4326")
    auto = frame.to_crs(resolve_area_crs(frame, "auto")).area.iloc[0]
    utm = frame.to_crs("EPSG:32642").area.iloc[0]
    assert auto == pytest.approx(utm, rel=2e-3)
    with pytest.raises(ValueError, match="proyeksiyalangan"):
        resolve_area_crs(frame, "EPSG:4326")


def test_load_fields_aligns_crs_and_reports_area_column(raster_dir, shp_file):
    stack = load_raster_stack(discover_rasters(raster_dir), NODATA)
    fields = load_fields(shp_file, stack.grid.crs, crop_column="TURI")  # katta-kichik harf farqi
    assert fields.notes["crs_aligned"] is True
    assert fields.frame.crs.to_epsg() == 32642  # asl shp CRS'i o'zgarmaydi
    minx, miny, maxx, maxy = fields.geometries[0].bounds
    assert (minx, maxx) == pytest.approx((69.00, 69.10), abs=1e-6)  # raster CRS'ga o'tgan
    assert fields.notes["area_column"]["interpretation"].startswith("gektar")
    assert list(fields.crop[:2]) == ["paxta", "paxta"]
    with pytest.raises(ValueError, match="ustuni shp'da yo'q"):
        load_fields(shp_file, stack.grid.crs, crop_column="ekin")


def test_end_to_end_outputs(raster_dir, shp_file, tmp_path):
    out = run(ZonalSettings(shp_path=shp_file, raster_path=raster_dir,
                            output_path=tmp_path / "natija", crop_column="turi"))
    assert out.viloyat == "Fargona"
    assert out.shapefile == tmp_path / "natija" / "Fargona" / "Fargona_ET_zonal.shp"

    shp = gpd.read_file(out.shapefile)
    assert shp.crs.to_epsg() == 32642 and len(shp) == 5
    assert all(len(c) <= 10 for c in shp.columns)
    for name in ("ETr3_mm", "ETr3_m3", "ETr3_m3ha", "ETo4_mm", "ETo4_m3", "ETo4_m3ha",
                 "ETr_mm", "ETr_m3", "ETr_m3ha", "area_ga", "ET_QC"):
        assert name in shp.columns, name

    a = shp.iloc[0]
    assert a["ETr3_mm"] == pytest.approx(45.0, abs=1e-3)  # (10+20)/2*3
    assert a["ETr4_mm"] == pytest.approx(60.0, abs=1e-3)  # (10+20)/2*4
    assert a["ETo3_mm"] == pytest.approx(22.5, abs=1e-3)
    assert a["ETr3_m3"] == pytest.approx(a["ETr3_mm"] / 1000 * a["area_ga"] * 10_000, rel=1e-6)
    assert a["ETr3_m3ha"] == pytest.approx(a["ETr3_mm"] * 10, rel=1e-6)
    assert a["ETr_mm"] == pytest.approx(105.0, abs=1e-3)  # 45 + 60
    ref = gpd.GeoSeries([FIELDS["A"]], crs="EPSG:4326").to_crs("EPSG:6933").area.iloc[0] / 10_000
    assert a["area_ga"] == pytest.approx(ref, rel=1e-4)

    d = shp.iloc[3]  # raster tashqarisidagi dala
    assert d["ETr3_mm"] == NODATA and d["ET_QC"] == STATUS_NODATA
    assert shp.iloc[2]["ETr3_mm"] == pytest.approx(90.0, abs=1e-3)  # to'ldirilgan
    assert shp.iloc[2]["ET_QC"] == STATUS_FILLED

    sheets = pd.read_excel(out.excel, sheet_name=None)
    assert {"ETr", "ETo", "ETr_tur", "ETo_tur", "Sifat"} <= set(sheets)
    etr = sheets["ETr"]
    assert etr["Oy"].tolist() == ["3 (Mart)", "4 (Aprel)", "JAMI"]
    row = etr.iloc[0]
    assert row["Dalalar soni"] == 5 and row["Hisobga olingan dalalar"] == 4  # D qiymatsiz
    valid = shp[shp["ETr3_mm"] != NODATA]
    assert row["ETr, m³"] == pytest.approx(valid["ETr3_m3"].sum(), rel=1e-3)
    assert row["ETr, m³/ga"] == pytest.approx(row["ETr, m³"] / valid["area_ga"].sum(), rel=1e-6)
    assert row["ETr, mm"] == pytest.approx(row["ETr, m³/ga"] / 10, rel=1e-6)
    total = etr.iloc[2]
    assert total["ETr, m³"] == pytest.approx(etr["ETr, m³"].iloc[:2].sum(), rel=1e-9)

    by_crop = sheets["ETr_tur"]
    assert set(by_crop["Tur"]) == {"paxta", "bug'doy"}
    assert by_crop.groupby("Tur")["Dalalar soni"].first().to_dict() == {"bug'doy": 2, "paxta": 3}
    qc = dict(zip(sheets["Sifat"]["Ko'rsatkich"], sheets["Sifat"]["Qiymat"]))
    assert qc["Shp CRS"] == "EPSG:32642" and qc["Raster CRS"] == "EPSG:4326"
    assert "EPSG:6933" in qc["Maydon hisoblangan CRS"]


def test_no_crop_column_means_no_crop_sheets(raster_dir, shp_file, tmp_path):
    out = run(ZonalSettings(shp_path=shp_file, raster_path=raster_dir, output_path=tmp_path / "n"))
    assert set(pd.read_excel(out.excel, sheet_name=None)) == {"ETr", "ETo", "Sifat"}


def test_column_names_follow_spec():
    assert naming.column("ETr", 3, "mm") == "ETr3_mm"
    assert naming.column("ETo", 9, "m3ha") == "ETo9_m3ha"
    assert len(naming.column("ETr", 12, "m3ha")) == 10
