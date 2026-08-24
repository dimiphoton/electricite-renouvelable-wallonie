"""Point d'entrée en ligne de commande du projet."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from renewables_wallonia.config import ConfigError, load_settings, project_root
from renewables_wallonia.data.copernicus import CopernicusIngestError, ingest_copernicus
from renewables_wallonia.data.elia import EliaIngestError, ingest_elia
from renewables_wallonia.analysis import AnalysisError, format_report, run_analysis
from renewables_wallonia.data.clean import CleanError
from renewables_wallonia.data.warehouse import WarehouseError, build_warehouse

logger = logging.getLogger(__name__)


def _configure_stdio() -> None:
    """Passe stdout/stderr en UTF-8 pour éviter les plantages cp1252 sous Windows."""
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if encoding == "utf8":
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


def build_parser() -> argparse.ArgumentParser:
    """Construit le parseur d'arguments.

    Returns
    -------
    argparse.ArgumentParser
        Parseur racine, avec sous-commandes.
    """

    parser = argparse.ArgumentParser(
        prog="renewables-wallonia",
        description=(
            "Analyse de la production renouvelable et de la charge "
            "électrique en Belgique, avec zoom Wallonie."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Fichier TOML de configuration (défaut : config/settings.toml).",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "show-config",
        help="Affiche la configuration chargée (contrôle du socle).",
    )
    ingest = subparsers.add_parser(
        "ingest-elia",
        help="Telecharge les archives Elia (charge, solaire, eolien) vers data/raw/elia/.",
    )
    ingest.add_argument(
        "--force",
        action="store_true",
        help="Retelecharge meme si le fichier CSV existe deja.",
    )
    copernicus = subparsers.add_parser(
        "ingest-copernicus",
        help="Telecharge ERA5 (Copernicus) et ecrit la serie horaire agregee.",
    )
    copernicus.add_argument(
        "--force",
        action="store_true",
        help="Retelecharge meme si les NetCDF mensuels existent deja.",
    )
    subparsers.add_parser(
        "build-warehouse",
        help="Nettoie les series et (re)cree l'entrepot DuckDB.",
    )
    subparsers.add_parser(
        "analyze",
        help="Repond aux 4 questions metier (SQL) et ecrit les tables CSV.",
    )
    return parser


def _run_show_config(config_path: Path | None) -> int:
    settings = load_settings(config_path)
    print(f"periode     : {settings.period.start} -> {settings.period.end}")
    print(f"charge      : Elia {settings.elia.load_dataset} ({settings.elia.coverage_region})")
    print(f"solaire     : Elia {settings.elia.solar_dataset} {list(settings.elia.regions.solar)}")
    print(f"eolien      : Elia {settings.elia.wind_dataset} {list(settings.elia.regions.wind)}")
    print(f"zoom        : {settings.elia.zoom_region}")
    print(f"meteo       : {settings.copernicus.dataset}")
    print(f"entrepot    : {settings.paths.warehouse}")
    print(f"affichage   : {settings.display.timezone}")
    return 0


def _run_ingest_elia(config_path: Path | None, force: bool) -> int:
    settings = load_settings(config_path)
    results = ingest_elia(settings, project_root(), force=force)
    for result in results:
        etat = "deja present" if result.skipped else f"ok ({result.bytes_written} octets)"
        print(f"{result.path.name}  {etat}")
    return 0


def _run_ingest_copernicus(config_path: Path | None, force: bool) -> int:
    settings = load_settings(config_path)
    months, csv_path = ingest_copernicus(settings, project_root(), force=force)
    sautes = sum(1 for item in months if item.skipped)
    print(f"mois ERA5     : {len(months)} ({sautes} ignores)")
    print(f"serie horaire : {csv_path}")
    return 0


def _run_build_warehouse(config_path: Path | None) -> int:
    settings = load_settings(config_path)
    db_path = build_warehouse(settings, project_root())
    print(f"entrepot : {db_path}")
    return 0


def _run_analyze(config_path: Path | None) -> int:
    settings = load_settings(config_path)
    root = project_root()
    result = run_analysis(settings, root, write=True)
    print(format_report(result))
    print(f"tables : {root / settings.paths.analysis_dir}")
    return 0


def main(argv: list[str] | None = None) -> None:
    """Point d'entrée principal du CLI.

    Parameters
    ----------
    argv
        Arguments à parser. Si ``None``, utilise ``sys.argv[1:]``.
    """

    _configure_stdio()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        raise SystemExit(0)

    try:
        if args.command == "show-config":
            raise SystemExit(_run_show_config(args.config))
        if args.command == "ingest-elia":
            raise SystemExit(_run_ingest_elia(args.config, args.force))
        if args.command == "ingest-copernicus":
            raise SystemExit(_run_ingest_copernicus(args.config, args.force))
        if args.command == "build-warehouse":
            raise SystemExit(_run_build_warehouse(args.config))
        if args.command == "analyze":
            raise SystemExit(_run_analyze(args.config))
    except ConfigError as exc:
        logger.error("%s", exc)
        raise SystemExit(2) from exc
    except (
        EliaIngestError,
        CopernicusIngestError,
        CleanError,
        WarehouseError,
        AnalysisError,
    ) as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc

    parser.error(f"commande inconnue : {args.command}")


if __name__ == "__main__":
    main()
