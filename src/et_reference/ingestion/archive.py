"""Yuklangan ERA5-Land NetCDF fayllarini yagona soatlik arxiv sifatida o'qish."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

_COORD_NAMES = {"valid_time": "time", "lat": "latitude", "lon": "longitude"}
_KEEP_COORDS = {"time", "latitude", "longitude"}


def normalize_era5_dataset(ds: xr.Dataset) -> xr.Dataset:
    """Koordinatalarni yagona ko'rinishga keltiradi.

    - yangi CDS dagi `valid_time` -> `time`
    - `expver` o'lchami birlashtiriladi, ortiqcha koordinatalar olib tashlanadi
    - uzunlik −180…180, kenglik kamayuvchi (shimol tepada), uzunlik o'suvchi
    """
    ds = ds.rename({k: v for k, v in _COORD_NAMES.items() if k in ds.variables})
    if "expver" in ds.dims:
        ds = _collapse_dimension(ds, "expver")
    if "number" in ds.dims:
        ds = ds.isel(number=0)
    ds = ds.drop_vars([c for c in ds.coords if c not in _KEEP_COORDS])
    missing = _KEEP_COORDS - set(ds.coords)
    if missing:
        raise ValueError(f"ERA5-Land faylida koordinatalar yo'q: {sorted(missing)}")

    lon = ds["longitude"]
    if bool((lon > 180).any()):
        ds = ds.assign_coords(longitude=((lon + 180.0) % 360.0) - 180.0)
    return ds.sortby("longitude").sortby("latitude", ascending=False)


Area = tuple[float, float, float, float]  # N, W, S, E
_COORD_TOL = 0.01  # ERA5-Land koordinatalaridagi float32 shovqini uchun zaxira, gradus


def subset_area(ds: xr.Dataset, area: Area) -> xr.Dataset:
    """Normallashtirilgan datasetdan [N, W, S, E] hududini kesib oladi."""
    north, west, south, east = area
    return ds.sel(
        latitude=slice(north + _COORD_TOL, south - _COORD_TOL),
        longitude=slice(west - _COORD_TOL, east + _COORD_TOL),
    )


def file_covers_area(path: Path, area: Area) -> bool:
    """NetCDF fayl tarmog'i [N, W, S, E] hududini to'liq qoplaydimi (faqat koordinatalar o'qiladi)."""
    with xr.open_dataset(path) as raw:
        ds = normalize_era5_dataset(raw)
        lat, lon = ds["latitude"].values, ds["longitude"].values
    north, west, south, east = area
    return bool(
        lat.max() >= north - _COORD_TOL and lat.min() <= south + _COORD_TOL
        and lon.min() <= west + _COORD_TOL and lon.max() >= east - _COORD_TOL
    )


def _collapse_dimension(ds: xr.Dataset, dim: str) -> xr.Dataset:
    """`dim` bo'ylab birinchi NaN bo'lmagan qiymatni oladi (ERA5/ERA5T aralashmasi)."""
    result = ds.isel({dim: 0})
    for i in range(1, ds.sizes[dim]):
        result = result.combine_first(ds.isel({dim: i}))
    return result


class HourlyArchive:
    """Bir nechta oylik/o'zgaruvchili fayllar ustidan vaqt oralig'ini kesib oladi.

    `area` berilsa, har bir fayl shu hududga kesiladi: shunda respublika bo'yicha
    yuklangan va viloyat bo'yicha yuklangan fayllar birga ishlatilishi mumkin.
    """

    def __init__(self, paths: Sequence[Path], area: Area | None = None) -> None:
        if not paths:
            raise FileNotFoundError("ERA5-Land fayllari berilmadi")
        datasets = [normalize_era5_dataset(xr.open_dataset(p)) for p in sorted(set(paths))]
        self._datasets = [subset_area(ds, area) for ds in datasets] if area else datasets
        self._check_same_grid()

    @property
    def latitude(self) -> np.ndarray:
        return self._datasets[0]["latitude"].values

    @property
    def longitude(self) -> np.ndarray:
        return self._datasets[0]["longitude"].values

    def load(
        self, start: pd.Timestamp, end: pd.Timestamp, variables: Iterable[str]
    ) -> xr.Dataset:
        """[start, end] (UTC, ikkala chegara ham kiradi) oralig'i soatlik to'liq indeks bilan.

        Yo'q soatlar NaN bo'lib qoladi, shuning uchun keyin to'liqlikni sanash mumkin.
        """
        variables = list(variables)
        pieces: dict[str, list[xr.DataArray]] = {v: [] for v in variables}
        for ds in self._datasets:
            subset = ds.sel(time=slice(start, end))
            if subset.sizes.get("time", 0) == 0:
                continue
            for name in variables:
                if name in subset:
                    pieces[name].append(subset[name].astype("float32").load())

        absent = [name for name, arrays in pieces.items() if not arrays]
        if absent:
            raise ValueError(f"{start}…{end} oralig'ida o'zgaruvchilar topilmadi: {absent}")

        hours = pd.date_range(start, end, freq="h")
        data = {}
        for name, arrays in pieces.items():
            da = xr.concat(arrays, dim="time") if len(arrays) > 1 else arrays[0]
            da = da.sortby("time")
            da = da.isel(time=~da.get_index("time").duplicated())
            data[name] = da.reindex(time=hours)
        return xr.Dataset(data)

    def close(self) -> None:
        for ds in self._datasets:
            ds.close()

    def _check_same_grid(self) -> None:
        ref = self._datasets[0]
        for ds in self._datasets[1:]:
            same = (
                ds.sizes["latitude"] == ref.sizes["latitude"]
                and ds.sizes["longitude"] == ref.sizes["longitude"]
                and np.allclose(ds["latitude"], ref["latitude"])
                and np.allclose(ds["longitude"], ref["longitude"])
            )
            if not same:
                raise ValueError(
                    "ERA5-Land fayllarining tarmog'i (lat/lon) mos emas. Ehtimol, "
                    "region.area o'zgargan: eski fayllarni keshdan o'chiring."
                )
