"""Buyruq qatori: `python -m et_reference check|run`. Oddiy foydalanish uchun loyiha ildizidagi `run.py`."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .config import ConfigError, Settings, load_settings
from .credentials import CredentialsError, load_cds_credentials

log = logging.getLogger("et_reference")

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="et-reference",
        description="ERA5-Land asosida oylik ETo/ETr (ASCE standartlashtirilgan PM).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="sozlamalar, kalit va CDS so'rovlar rejasini tekshirish")
    run = sub.add_parser("run", help="hisob: yuklash → QC → ETo/ETr → GeoTIFF + CSV")
    run.add_argument("--viloyat", help="viloyat nomi (masalan: Fargona) yoki 'hammasi'")
    run.add_argument("--output", type=Path, help="natijalar papkasi")
    run.add_argument(
        "--skip-download", action="store_true", help="faqat keshdagi ERA5-Land fayllaridan foydalanish"
    )
    for command in (check, run):
        command.add_argument("-c", "--config", type=Path, default=DEFAULT_CONFIG)
        command.add_argument("--start", help="davr boshi YYYY-MM-DD")
        command.add_argument("--end", help="davr oxiri YYYY-MM-DD")
    args = parser.parse_args(argv)

    if args.command == "run":
        return run_command(
            config=args.config, start=args.start, end=args.end, viloyat=args.viloyat,
            output=args.output, download=not args.skip_download,
        )
    try:
        settings = load_settings(args.config, start=args.start, end=args.end)
    except ConfigError as exc:
        print(f"Sozlamalar xatosi: {exc}", file=sys.stderr)
        return 2
    _configure_logging(settings, to_file=False)
    return _check(settings)


def run_command(
    *,
    config: Path = DEFAULT_CONFIG,
    start: str | None = None,
    end: str | None = None,
    viloyat: str | None = None,
    output: str | Path | None = None,
    download: bool = True,
) -> int:
    """Bitta viloyat (yoki butun respublika) uchun to'liq hisob. Qaytaradi: chiqish kodi."""
    try:
        settings = load_settings(config, start=start, end=end)
    except ConfigError as exc:
        print(f"Sozlamalar xatosi: {exc}", file=sys.stderr)
        return 2
    if output:
        output_dir = Path(output).expanduser().resolve()
        settings = replace(settings, paths=replace(settings.paths, output=output_dir))
    _configure_logging(settings, to_file=True)

    from .pipeline import run as run_pipeline

    try:
        result = run_pipeline(settings, region=viloyat, download=download)
    except (RuntimeError, OSError, ValueError) as exc:  # kalit, yuklash, fayl va tarmoq xatolari
        log.error("%s", exc)
        return 1
    log.info("Jadval: %s", result.table_file)
    return 0


def _check(settings: Settings) -> int:
    from .pipeline import load_admin_units, plan

    log.info("Davr: %s … %s (%s)", settings.period.start, settings.period.end, settings.region.timezone)
    log.info("Kesh: %s | Natijalar: %s", settings.paths.cache, settings.paths.output)
    try:
        credentials = load_cds_credentials(settings.cds.credentials)
        log.info("CDS kaliti: topildi (%s), url=%s", credentials.source or "muhit o'zgaruvchisi", credentials.url)
    except CredentialsError as exc:
        log.warning("CDS kaliti: %s", exc)

    try:
        units = load_admin_units(settings)
    except (OSError, ValueError) as exc:
        log.error("Chegaralar: %s", exc)
        return 1
    requests = plan(settings, units)
    cached = sum((settings.paths.hourly / r.filename).is_file() for r in requests)
    log.info("Chegaralar: %d ta birlik, CRS=%s", len(units), units.crs.to_string())
    log.info("CDS hududi [N, W, S, E]: %s", list(requests[0].area))
    log.info("CDS so'rovlari: %d ta (keshda %d ta, yuklanadi %d ta)", len(requests), cached, len(requests) - cached)
    for request in requests:
        status = "kesh" if (settings.paths.hourly / request.filename).is_file() else "yuklanadi"
        log.info("  %d-%02d kunlar %02d–%02d  [%s]", request.year, request.month,
                 request.days[0], request.days[-1], status)
    return 0


def _configure_logging(settings: Settings, to_file: bool) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if to_file:
        settings.paths.logs.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        handlers.append(logging.FileHandler(settings.paths.logs / f"run_{stamp}.log", encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )
