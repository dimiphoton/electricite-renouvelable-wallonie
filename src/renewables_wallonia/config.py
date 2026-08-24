"""Chargement de la configuration TOML du projet."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Configuration manquante, illisible ou incohérente."""


@dataclass(frozen=True)
class Period:
    """Bornes inclusives de la période d'analyse."""

    start: date
    end: date


@dataclass(frozen=True)
class EliaRegions:
    """Valeurs du champ ``region`` à conserver dans les exports Elia."""

    solar: tuple[str, ...]
    wind: tuple[str, ...]


@dataclass(frozen=True)
class EliaSettings:
    """Identifiants des datasets Elia et mailles géographiques."""

    base_url: str
    load_dataset: str
    solar_dataset: str
    wind_dataset: str
    coverage_region: str
    zoom_region: str
    regions: EliaRegions


@dataclass(frozen=True)
class CopernicusSettings:
    """Réanalyse ERA5 : dataset, variables et bbox (nord, ouest, sud, est)."""

    dataset: str
    variables: tuple[str, ...]
    belgium_bbox: tuple[float, float, float, float]
    wallonia_bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class PathSettings:
    """Chemins relatifs à la racine du dépôt."""

    raw_dir: str
    processed_dir: str
    warehouse: str


@dataclass(frozen=True)
class DisplaySettings:
    """Fuseau utilisé à l'affichage (le stockage restera en UTC)."""

    timezone: str


@dataclass(frozen=True)
class Settings:
    """Configuration complète lue depuis ``config/settings.toml``."""

    period: Period
    elia: EliaSettings
    copernicus: CopernicusSettings
    paths: PathSettings
    display: DisplaySettings


def project_root() -> Path:
    """Retourne la racine du dépôt (dossier qui contient ``config/settings.toml``).

    Returns
    -------
    Path
        Chemin absolu de la racine.

    Raises
    ------
    ConfigError
        Si aucun ``config/settings.toml`` n'est trouvé en remontant les
        dossiers depuis ce fichier ou depuis le répertoire courant.
    """

    start_points = (Path(__file__).resolve(), Path.cwd().resolve())
    seen: set[Path] = set()
    for start in start_points:
        for candidate in (start, *start.parents):
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / "config" / "settings.toml").is_file():
                return candidate
    raise ConfigError(
        "Impossible de trouver config/settings.toml. Lance la commande "
        "depuis la racine du dépôt, ou passe --config."
    )


def default_config_path() -> Path:
    """Chemin par défaut du fichier de configuration.

    Returns
    -------
    Path
        ``<racine>/config/settings.toml``.
    """

    return project_root() / "config" / "settings.toml"


def load_settings(path: Path | None = None) -> Settings:
    """Lit et valide le TOML de configuration.

    Parameters
    ----------
    path
        Fichier TOML à lire. Si ``None``, utilise ``default_config_path``.

    Returns
    -------
    Settings
        Configuration typée.

    Raises
    ------
    ConfigError
        Fichier absent, TOML invalide, clé manquante ou période incohérente.
    """

    config_path = path or default_config_path()
    if not config_path.is_file():
        raise ConfigError(f"Fichier de configuration introuvable : {config_path}")

    try:
        with config_path.open("rb") as handle:
            raw = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"TOML illisible ({config_path}) : {exc}") from exc

    try:
        return _settings_from_dict(raw)
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"Configuration invalide ({config_path}) : {exc}") from exc


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _bbox(values: list[Any]) -> tuple[float, float, float, float]:
    if len(values) != 4:
        raise ValueError("une bbox CDS doit avoir 4 nombres (N, W, S, E)")
    north, west, south, east = (float(item) for item in values)
    return (north, west, south, east)


def _settings_from_dict(raw: dict[str, Any]) -> Settings:
    period = Period(
        start=_parse_date(raw["period"]["start"]),
        end=_parse_date(raw["period"]["end"]),
    )
    if period.start >= period.end:
        raise ValueError("period.start doit être strictement antérieur à period.end")

    elia_raw = raw["elia"]
    regions_raw = elia_raw["regions"]
    elia = EliaSettings(
        base_url=str(elia_raw["base_url"]),
        load_dataset=str(elia_raw["load_dataset"]),
        solar_dataset=str(elia_raw["solar_dataset"]),
        wind_dataset=str(elia_raw["wind_dataset"]),
        coverage_region=str(elia_raw["coverage_region"]),
        zoom_region=str(elia_raw["zoom_region"]),
        regions=EliaRegions(
            solar=tuple(str(item) for item in regions_raw["solar"]),
            wind=tuple(str(item) for item in regions_raw["wind"]),
        ),
    )

    copernicus_raw = raw["copernicus"]
    copernicus = CopernicusSettings(
        dataset=str(copernicus_raw["dataset"]),
        variables=tuple(str(item) for item in copernicus_raw["variables"]),
        belgium_bbox=_bbox(list(copernicus_raw["belgium_bbox"])),
        wallonia_bbox=_bbox(list(copernicus_raw["wallonia_bbox"])),
    )

    paths_raw = raw["paths"]
    paths = PathSettings(
        raw_dir=str(paths_raw["raw_dir"]),
        processed_dir=str(paths_raw["processed_dir"]),
        warehouse=str(paths_raw["warehouse"]),
    )

    display = DisplaySettings(timezone=str(raw["display"]["timezone"]))

    return Settings(
        period=period,
        elia=elia,
        copernicus=copernicus,
        paths=paths,
        display=display,
    )
