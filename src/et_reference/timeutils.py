"""Mahalliy vaqt va UTC o'rtasidagi kun/oy chegaralari."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

import pandas as pd


def local_midnight_utc(day: date, timezone: str) -> pd.Timestamp:
    """Mahalliy `day` kunining 00:00 vaqti UTC da (tz-siz Timestamp)."""
    return pd.Timestamp(day).tz_localize(timezone).tz_convert("UTC").tz_localize(None)


def iter_months(start: date, end: date) -> Iterator[tuple[date, date]]:
    """[start, end] oralig'ini kalendar oylarga bo'ladi: (birinchi kun, oxirgi kun)."""
    current = start
    while current <= end:
        next_month = (current.replace(day=1) + timedelta(days=32)).replace(day=1)
        last = min(end, next_month - timedelta(days=1))
        yield current, last
        current = last + timedelta(days=1)


def utc_day_span(start: date, end: date, timezone: str) -> tuple[date, date]:
    """Mahalliy [start, end] kunlarini to'liq qoplash uchun kerak bo'lgan UTC kunlari.

    Lahzalik kattaliklar mahalliy 00:00..23:00, yig'ilgan oqimlar esa soat oxiri
    bo'yicha 01:00..24:00 oralig'ida olinadi. Shu sababli oxirgi chegara
    mahalliy (end + 1 kun) 00:00 ga teng.
    """
    first = local_midnight_utc(start, timezone).date()
    last = local_midnight_utc(end + timedelta(days=1), timezone).date()
    return first, last
