"""Buyruq qatori: `python -m et_reference check|run -c config/settings.yaml`."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from .config import ConfigError, Settings, load_settings
from .credentials import CredentialsError, load_cds_credentials

log = logging.getLogger("et_reference")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="et-reference",
        description="ERA5-Land asosida oylik ETo/ETr rasterlari (ASCE standartlashtirilgan PM).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="sozlamalar, kalit va CDS so'rovlar rejasini tekshirish")
    run = sub.add_parser("run", help="to'liq hisob: yuklash → QC → ETo/ETr → GeoTIFF")
    run.add_argument(
        "--skip-download", action="store_true", help="faqat keshdagi ERA5-Land fayllaridan foydalanish"
    )
    for command in (check, run):
        command.add_argument("-c", "--config", type=Path, default=Path("config/settings.yaml"))
        command.add_argument("--start", help="davr boshi YYYY-MM-DD (sozlamani almashtiradi)")
        command.add_argument("--end", help="davr oxiri YYYY-MM-DD (sozlamani almashtiradi)")
    args = parser.parse_args(argv)

    try:
        settings = load_settings(args.config, start=args.start, end=args.end)
    except ConfigError as exc:
        print(f"Sozlamalar xatosi: {exc}", file=sys.stderr)
        return 2

    _configure_logging(settings, to_file=args.command == "run")
    try:
        if args.command == "check":
            return _check(settings)
        from .pipeline import run as run_pipeline

        result = run_pipeline(settings, download=not args.skip_download)
        log.info("Hisobot: %s", result.summary_file)
        return 0
    except (RuntimeError, OSError, ValueError) as exc:  # kalit, yuklash, fayl va tarmoq xatolari
        log.error("%s", exc)
        return 1


def _check(settings: Settings) -> int:
    from .pipeline import load_region, plan

    log.info("Davr: %s … %s (%s)", settings.period.start, settings.period.end, settings.region.timezone)
    log.info("Kesh: %s | Natijalar: %s", settings.paths.cache, settings.paths.output)
    try:
        credentials = load_cds_credentials(settings.cds.credentials)
        log.info("CDS kaliti: topildi (%s), url=%s", credentials.source or "muhit o'zgaruvchisi", credentials.url)
    except CredentialsError as exc:
        log.warning("CDS kaliti: %s", exc)

    region = load_region(settings)
    requests = plan(settings, region)
    cached = sum((settings.paths.hourly / r.filename).is_file() for r in requests)
    log.info("Chegaralar: %d ta birlik, CRS=%s", len(region), region.crs.to_string())
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
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
