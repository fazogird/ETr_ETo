"""CDS API kalitini lokal fayldan xavfsiz o'qish.

Kalit hech qachon log, xato xabari yoki `repr` ga chiqmaydi. Kod faqat kalit
qayerda turganini biladi, kalitning o'zi esa repozitoriyga tushmaydi.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CDS_URL = "https://cds.climate.copernicus.eu/api"
CANDIDATE_FILENAMES = (
    ".cdsapirc",
    "cdsapirc",
    ".cdsapirc.txt",
    "cdsapirc.txt",
    "key.txt",
    "api_key.txt",
)


class CredentialsError(RuntimeError):
    """Kalit topilmadi yoki uning formati noto'g'ri."""


@dataclass(frozen=True)
class CdsCredentials:
    url: str
    key: str = field(repr=False)
    source: Path | None = None

    def __repr__(self) -> str:
        return f"CdsCredentials(url={self.url!r}, key='***', source={str(self.source)!r})"


def load_cds_credentials(configured: Path | None = None) -> CdsCredentials:
    """Kalitni topadi. Tartib: sozlamadagi yo'l → CDSAPI_URL/CDSAPI_KEY → CDSAPI_RC → ~/.cdsapirc."""
    if configured is not None:
        return _read_file(_resolve_location(Path(configured)))

    env_key = os.environ.get("CDSAPI_KEY")
    if env_key:
        return CdsCredentials(
            url=os.environ.get("CDSAPI_URL", DEFAULT_CDS_URL),
            key=_validated_key(env_key, "CDSAPI_KEY"),
            source=None,
        )

    env_rc = os.environ.get("CDSAPI_RC")
    if env_rc:
        return _read_file(_resolve_location(Path(env_rc)))

    home_rc = Path.home() / ".cdsapirc"
    if home_rc.is_file():
        return _read_file(home_rc)

    raise CredentialsError(
        "CDS kaliti topilmadi: settings.yaml dagi cds.credentials yo'lini, "
        "CDSAPI_RC muhit o'zgaruvchisini yoki ~/.cdsapirc faylini tekshiring."
    )


def parse_credentials(text: str, source: Path | None = None) -> CdsCredentials:
    """`.cdsapirc` formati (url:/key:) yoki bitta qatorli tokenni o'qiydi."""
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    entries: dict[str, str] = {}
    for line in lines:
        name, sep, value = line.partition(":")
        if sep and name.strip().lower() in {"url", "key", "verify"}:
            entries[name.strip().lower()] = value.strip()

    if "key" in entries:
        url = entries.get("url") or DEFAULT_CDS_URL
        key = entries["key"]
    elif len(lines) == 1 and not entries:
        url, key = DEFAULT_CDS_URL, lines[0]
    else:
        raise CredentialsError(
            f"Kalit fayli formati tanilmadi: {source}. Kutilgan ko'rinish:\n"
            f"  url: {DEFAULT_CDS_URL}\n  key: <SIZNING-TOKENINGIZ>"
        )
    if not url.startswith("https://"):
        raise CredentialsError(f"CDS url https:// bilan boshlanishi kerak ({source})")
    return CdsCredentials(url=url, key=_validated_key(key, str(source)), source=source)


def _resolve_location(location: Path) -> Path:
    if location.is_file():
        return location
    if location.is_dir():
        for name in CANDIDATE_FILENAMES:
            candidate = location / name
            if candidate.is_file():
                return candidate
        files = sorted(p for p in location.iterdir() if p.is_file())
        if len(files) == 1:
            return files[0]
        names = ", ".join(p.name for p in files) or "bo'sh"
        raise CredentialsError(
            f"Papkada kalit faylini aniqlab bo'lmadi: {location} (fayllar: {names}). "
            f"Faylni '.cdsapirc' deb nomlang yoki papkada bitta fayl qoldiring."
        )
    raise CredentialsError(f"Kalit yo'li mavjud emas: {location}")


def _read_file(path: Path) -> CdsCredentials:
    # utf-8-sig: Windows Notepad qo'shadigan BOM belgisini olib tashlaydi.
    return parse_credentials(path.read_text(encoding="utf-8-sig"), source=path)


def _validated_key(key: str, source: str) -> str:
    key = key.strip()
    if not key or any(ch.isspace() for ch in key):
        raise CredentialsError(f"Kalit bo'sh yoki ichida bo'sh joy bor ({source})")
    return key
