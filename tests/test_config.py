from datetime import date
from pathlib import Path

import pytest

from et_reference.config import ConfigError, load_settings

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_repository_settings():
    settings = load_settings(REPO_ROOT / "config" / "settings.yaml")
    assert settings.period.start == date(2026, 3, 1)
    assert settings.period.end == date(2026, 9, 30)
    assert settings.region.country_iso3 == "UZB"
    assert settings.region.timezone == "Asia/Tashkent"
    assert settings.paths.root == REPO_ROOT
    assert settings.paths.output == REPO_ROOT / "outputs"
    assert "cds.climate.copernicus.eu" in str(settings.cds.credentials)


def _write(tmp_path, text):
    config = tmp_path / "config"
    config.mkdir()
    path = config / "settings.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_cli_overrides_period(tmp_path):
    path = _write(tmp_path, "period: {start: 2026-03-01, end: 2026-09-30}\n")
    settings = load_settings(path, start="2026-05-01", end="2026-05-31")
    assert (settings.period.start, settings.period.end) == (date(2026, 5, 1), date(2026, 5, 31))
    assert settings.paths.root == tmp_path


@pytest.mark.parametrize(
    "text, message",
    [
        ("period: {start: 2026-09-30, end: 2026-03-01}\n", "dan oldin"),
        ("period: {start: 2026-03-01, end: 2026-09-30}\nregion: {timezone: Mars/Olympus}\n", "vaqt zonasi"),
        ("period: {start: 2026-03-01, end: 2026-09-30}\nregion: {area: [37, 56, 46, 74]}\n", "area"),
        ("period: {start: 2026-03-01, end: 2026-09-30}\nquality: {nomalum: 1}\n", "noma'lum kalitlar"),
        ("period: {start: 2026-03-01, end: 2026-09-30}\ncds: {ssrd_mode: kunlik}\n", "ssrd_mode"),
    ],
)
def test_invalid_settings(tmp_path, text, message):
    with pytest.raises(ConfigError, match=message):
        load_settings(_write(tmp_path, text))
