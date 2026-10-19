import pytest

from et_reference.credentials import (
    DEFAULT_CDS_URL,
    CredentialsError,
    load_cds_credentials,
    parse_credentials,
)

SECRET = "0123abcd-4567-89ef-0123-456789abcdef"


def test_rc_format(tmp_path):
    path = tmp_path / ".cdsapirc"
    path.write_text(f"url: https://cds.climate.copernicus.eu/api\nkey: {SECRET}\n", encoding="utf-8")
    creds = load_cds_credentials(path)
    assert creds.key == SECRET
    assert creds.url == "https://cds.climate.copernicus.eu/api"
    assert creds.source == path


def test_bare_token_uses_default_url():
    creds = parse_credentials(f"  {SECRET}  \n")
    assert creds.key == SECRET and creds.url == DEFAULT_CDS_URL


def test_windows_bom_is_ignored(tmp_path):
    path = tmp_path / "key.txt"
    path.write_bytes(("﻿" + f"key: {SECRET}").encode("utf-8"))
    assert load_cds_credentials(path).key == SECRET


def test_directory_prefers_cdsapirc(tmp_path):
    (tmp_path / "README.txt").write_text("izoh", encoding="utf-8")
    (tmp_path / ".cdsapirc").write_text(f"key: {SECRET}", encoding="utf-8")
    assert load_cds_credentials(tmp_path).key == SECRET


def test_directory_with_single_file(tmp_path):
    (tmp_path / "mening_kalitim").write_text(SECRET, encoding="utf-8")
    assert load_cds_credentials(tmp_path).key == SECRET


def test_ambiguous_directory_raises(tmp_path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "b.txt").write_text("y", encoding="utf-8")
    with pytest.raises(CredentialsError, match="aniqlab bo'lmadi"):
        load_cds_credentials(tmp_path)


def test_missing_path_raises(tmp_path):
    with pytest.raises(CredentialsError, match="mavjud emas"):
        load_cds_credentials(tmp_path / "yoq")


def test_key_never_leaks_into_repr_or_errors(tmp_path):
    creds = parse_credentials(f"key: {SECRET}")
    assert SECRET not in repr(creds)
    bad = tmp_path / "bad"
    bad.write_text(f"birinchi qator {SECRET}\nikkinchi qator", encoding="utf-8")
    with pytest.raises(CredentialsError) as info:
        load_cds_credentials(bad)
    assert SECRET not in str(info.value)


def test_environment_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("CDSAPI_KEY", SECRET)
    monkeypatch.setenv("HOME", str(tmp_path))
    creds = load_cds_credentials(None)
    assert creds.key == SECRET and creds.source is None
