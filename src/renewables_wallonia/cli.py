"""Point d'entrée en ligne de commande du projet."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from renewables_wallonia.config import ConfigError, load_settings

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
    except ConfigError as exc:
        logger.error("%s", exc)
        raise SystemExit(2) from exc

    parser.error(f"commande inconnue : {args.command}")


if __name__ == "__main__":
    main()
