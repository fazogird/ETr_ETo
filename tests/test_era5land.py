import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from et_reference.ingestion.archive import HourlyArchive, normalize_era5_dataset
from et_reference.ingestion.era5land import (
    VARIABLES,
    CdsDownloader,
    DownloadError,
    area_from_bounds,
    plan_requests,
)
from et_reference.timeutils import iter_months, utc_day_span

from .synthetic import synthetic_hourly

AREA = (45.8, 55.8, 37.0, 73.3)


def test_utc_day_span_for_tashkent():
    # Mahalliy 1-mart 00:00 = UTC 28-fevral 19:00; 30-sentabr 24:00 = UTC 30-sentabr 19:00
    assert utc_day_span(date(2026, 3, 1), date(2026, 9, 30), "Asia/Tashkent") == (
        date(2026, 2, 28),
        date(2026, 9, 30),
    )


def test_iter_months_clips_partial_months():
    months = list(iter_months(date(2026, 3, 15), date(2026, 5, 10)))
    assert months == [
        (date(2026, 3, 15), date(2026, 3, 31)),
        (date(2026, 4, 1), date(2026, 4, 30)),
        (date(2026, 5, 1), date(2026, 5, 10)),
    ]


def test_plan_requests_by_month():
    requests = plan_requests(date(2026, 2, 28), date(2026, 9, 30), AREA)
    assert [(r.year, r.month) for r in requests] == [(2026, m) for m in range(2, 10)]
    assert requests[0].days == (28,)
    assert requests[-1].days == tuple(range(1, 31))
    assert len({r.filename for r in requests}) == len(requests)

    split = plan_requests(date(2026, 2, 28), date(2026, 9, 30), AREA, split_by_variable=True)
    assert len(split) == 8 * len(VARIABLES)


def test_cds_request_payload():
    request = plan_requests(date(2026, 3, 1), date(2026, 3, 2), AREA)[0]
    payload = request.to_cds()
    assert payload["day"] == ["01", "02"]
    assert payload["time"][0] == "00:00" and payload["time"][-1] == "23:00"
    assert payload["area"] == list(AREA)
    assert payload["data_format"] == "netcdf"
    assert set(payload["variable"]) == set(VARIABLES)


def test_area_from_bounds_snaps_outward_to_grid():
    north, west, south, east = area_from_bounds((55.996, 37.184, 73.132, 45.590), buffer_deg=0.2)
    assert (north, west, south, east) == (45.8, 55.7, 36.9, 73.4)


class FakeClient:
    def __init__(self):
        self.calls = []

    def retrieve(self, dataset, request, target):
        self.calls.append((dataset, request["month"]))
        with open(target, "wb") as fh:
            fh.write(b"netcdf")


def test_downloader_skips_cached_files(tmp_path):
    requests = plan_requests(date(2026, 3, 1), date(2026, 4, 30), AREA)
    (tmp_path / requests[0].filename).write_bytes(b"cached")
    client = FakeClient()
    paths = CdsDownloader(client, "reanalysis-era5-land", tmp_path).fetch(requests)
    assert client.calls == [("reanalysis-era5-land", "04")]
    assert all(p.is_file() for p in paths)
    assert not list(tmp_path.glob("*.part"))


class ZipClient:
    """Yangi CDS kabi: lahzalik va yig'ilgan o'zgaruvchilarni ZIP ichida alohida .nc qilib beradi."""

    def __init__(self, fail_month=None):
        self.fail_month = fail_month

    def retrieve(self, dataset, request, target):
        if request["month"] == self.fail_month:
            raise RuntimeError("CDS: 400 Bad Request")
        year, month = int(request["year"]), int(request["month"])
        days = [int(d) for d in request["day"]]
        times = pd.date_range(
            pd.Timestamp(year=year, month=month, day=days[0]),
            pd.Timestamp(year=year, month=month, day=days[-1], hour=23),
            freq="h",
        )
        ds = synthetic_hourly(times)
        workdir = Path(target).parent
        instant = workdir / "data_stream-oper_stepType-instant.nc"
        accum = workdir / "data_stream-oper_stepType-accum.nc"
        ds.drop_vars("ssrd").to_netcdf(instant)
        ds[["ssrd"]].to_netcdf(accum)
        with zipfile.ZipFile(target, "w") as archive:
            archive.write(instant, instant.name)
            archive.write(accum, accum.name)
        instant.unlink()
        accum.unlink()


def test_downloader_merges_cds_zip(tmp_path):
    requests = plan_requests(date(2026, 3, 1), date(2026, 3, 2), AREA)
    (path,) = CdsDownloader(ZipClient(), "reanalysis-era5-land", tmp_path).fetch(requests)
    with xr.open_dataset(path) as ds:
        assert {"t2m", "d2m", "u10", "v10", "ssrd", "sp"} <= set(ds.data_vars)
        assert ds.sizes["valid_time"] == 48
    assert sorted(p.name for p in tmp_path.iterdir()) == [path.name]


def test_failed_month_does_not_stop_others(tmp_path):
    requests = plan_requests(date(2026, 3, 1), date(2026, 5, 31), AREA)
    downloader = CdsDownloader(ZipClient(fail_month="04"), "reanalysis-era5-land", tmp_path)
    with pytest.raises(DownloadError, match="2026-04"):
        downloader.fetch(requests)
    assert (tmp_path / requests[0].filename).is_file()
    assert not (tmp_path / requests[1].filename).exists()
    assert (tmp_path / requests[2].filename).is_file()
    assert not list(tmp_path.glob("*.part"))


def test_normalize_new_cds_layout():
    times = pd.date_range("2026-03-01", periods=3, freq="h")
    ds = synthetic_hourly(times)
    ds = ds.assign_coords(longitude=np.array([-0.1, 0.0, 0.1]) % 360).sortby("latitude")
    out = normalize_era5_dataset(ds)
    assert "time" in out.dims and "valid_time" not in out.variables
    assert "expver" not in out.variables and "number" not in out.variables
    assert np.all(np.diff(out["latitude"].values) < 0)
    np.testing.assert_allclose(out["longitude"].values, [-0.1, 0.0, 0.1], atol=1e-9)


def test_archive_reindexes_missing_hours(tmp_path):
    times = pd.date_range("2026-03-01", periods=48, freq="h")
    full = synthetic_hourly(times)
    full.isel(valid_time=slice(0, 20)).to_netcdf(tmp_path / "a.nc")
    full.isel(valid_time=slice(22, 48)).to_netcdf(tmp_path / "b.nc")
    archive = HourlyArchive([tmp_path / "a.nc", tmp_path / "b.nc"])
    loaded = archive.load(times[0], times[-1], ["t2m"])
    archive.close()
    assert loaded.sizes["time"] == 48
    assert int(loaded["t2m"].isnull().any(["latitude", "longitude"]).sum()) == 2


def test_archive_rejects_mismatched_grids(tmp_path):
    times = pd.date_range("2026-03-01", periods=2, freq="h")
    synthetic_hourly(times).to_netcdf(tmp_path / "a.nc")
    shifted = synthetic_hourly(times)
    shifted = shifted.assign_coords(longitude=shifted["longitude"] + 0.1)
    shifted.to_netcdf(tmp_path / "b.nc")
    with pytest.raises(ValueError, match="mos emas"):
        HourlyArchive([tmp_path / "a.nc", tmp_path / "b.nc"])
