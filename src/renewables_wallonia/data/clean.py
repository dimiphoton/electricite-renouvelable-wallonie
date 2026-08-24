"""Nettoyage des séries Elia et ERA5 avant chargement DuckDB."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from renewables_wallonia.config import Settings
from renewables_wallonia.data.copernicus import hourly_csv_path
from renewables_wallonia.data.elia import (
    csv_filename,
    period_utc_bounds,
    planned_exports,
    raw_elia_dir,
)

# ERA5 ssrd est une accumulation horaire en J/m² → W/m² = J/m² / 3600 s.
_SECONDS_PER_HOUR = 3600.0


class CleanError(RuntimeError):
    """Fichier brut manquant ou colonnes inattendues."""


def clean_all(settings: Settings, root: Path) -> dict[str, pd.DataFrame]:
    """Nettoie charge, production et météo, prêts pour DuckDB.

    Parameters
    ----------
    settings
        Période, régions, chemins.
    root
        Racine du dépôt.

    Returns
    -------
    dict of DataFrame
        ``load``, ``generation``, ``weather``, ``datetime``.

    Raises
    ------
    CleanError
        CSV brut introuvable.
    """

    start_utc, end_exclusive_utc = period_utc_bounds(
        settings.period.start,
        settings.period.end,
        settings.display.timezone,
    )
    load = clean_load(settings, root, start_utc, end_exclusive_utc)
    solar = clean_solar(settings, root, start_utc, end_exclusive_utc)
    wind = clean_wind(settings, root, start_utc, end_exclusive_utc)
    generation = pd.concat([solar, wind], ignore_index=True)
    weather = clean_weather(settings, root, start_utc, end_exclusive_utc)
    clock = build_datetime_dim(
        pd.concat(
            [load["datetime_utc"], generation["datetime_utc"], weather["datetime_utc"]],
            ignore_index=True,
        ),
        settings.display.timezone,
    )
    return {
        "load": load,
        "generation": generation,
        "weather": weather,
        "datetime": clock,
    }


def clean_load(
    settings: Settings,
    root: Path,
    start_utc: datetime,
    end_exclusive_utc: datetime,
) -> pd.DataFrame:
    """Charge nationale belge au quart d'heure (les NA restent des NA).

    Parameters
    ----------
    settings, root
        Localisation du CSV Elia.
    start_utc, end_exclusive_utc
        Filtre ``[début, fin[`` UTC.

    Returns
    -------
    pd.DataFrame
        Colonnes ``datetime_utc``, ``region``, ``load_mw``, ``dayahead_mw``.
    """

    path = _elia_csv(settings, root, kind="load")
    frame = _read_elia(path)
    frame = frame.rename(columns={"totalload": "load_mw", "dayaheadforecast": "dayahead_mw"})
    frame["region"] = settings.elia.coverage_region
    frame = _filter_period(frame, start_utc, end_exclusive_utc)
    return frame[["datetime_utc", "region", "load_mw", "dayahead_mw"]].sort_values(
        "datetime_utc"
    ).reset_index(drop=True)


def clean_solar(
    settings: Settings,
    root: Path,
    start_utc: datetime,
    end_exclusive_utc: datetime,
) -> pd.DataFrame:
    """Production solaire par région Elia, sans sommer Belgique et Wallonie.

    Parameters
    ----------
    settings, root
        CSV solaire.
    start_utc, end_exclusive_utc
        Filtre UTC.

    Returns
    -------
    pd.DataFrame
        Une ligne par quart d'heure et région, ``source='solar'``.
    """

    path = _elia_csv(settings, root, kind="solar")
    frame = _read_elia(path)
    frame = frame.rename(
        columns={
            "measured": "measured_mw",
            "dayaheadforecast": "dayahead_mw",
            "monitoredcapacity": "capacity_mw",
            "loadfactor": "load_factor",
        }
    )
    frame["source"] = "solar"
    frame = _filter_period(frame, start_utc, end_exclusive_utc)
    return frame[
        [
            "datetime_utc",
            "region",
            "source",
            "measured_mw",
            "dayahead_mw",
            "capacity_mw",
            "load_factor",
        ]
    ].sort_values(["datetime_utc", "region"]).reset_index(drop=True)


def clean_wind(
    settings: Settings,
    root: Path,
    start_utc: datetime,
    end_exclusive_utc: datetime,
) -> pd.DataFrame:
    """Éolien agrégé par région (Elia+DSO), plus un total Belgique.

    Parameters
    ----------
    settings, root
        CSV éolien.
    start_utc, end_exclusive_utc
        Filtre UTC.

    Returns
    -------
    pd.DataFrame
        ``source='wind'``. Le total Belgique est la somme Federal + Flanders
        + Wallonia (pas de double compte : pas de maille Belgium dans Elia).
    """

    path = _elia_csv(settings, root, kind="wind")
    frame = _read_elia(path)
    frame = _filter_period(frame, start_utc, end_exclusive_utc)
    grouped = (
        frame.groupby(["datetime_utc", "region"], as_index=False)[
            ["measured", "dayaheadforecast", "monitoredcapacity"]
        ]
        .sum(min_count=1)
        .rename(
            columns={
                "measured": "measured_mw",
                "dayaheadforecast": "dayahead_mw",
                "monitoredcapacity": "capacity_mw",
            }
        )
    )
    grouped["load_factor"] = grouped["measured_mw"] / grouped["capacity_mw"].replace(0, pd.NA)
    grouped["source"] = "wind"

    belgium = (
        grouped.groupby("datetime_utc", as_index=False)[
            ["measured_mw", "dayahead_mw", "capacity_mw"]
        ].sum(min_count=1)
    )
    belgium["region"] = settings.elia.coverage_region
    belgium["load_factor"] = belgium["measured_mw"] / belgium["capacity_mw"].replace(0, pd.NA)
    belgium["source"] = "wind"

    out = pd.concat([grouped, belgium], ignore_index=True)
    return out[
        [
            "datetime_utc",
            "region",
            "source",
            "measured_mw",
            "dayahead_mw",
            "capacity_mw",
            "load_factor",
        ]
    ].sort_values(["datetime_utc", "region"]).reset_index(drop=True)


def clean_weather(
    settings: Settings,
    root: Path,
    start_utc: datetime,
    end_exclusive_utc: datetime,
) -> pd.DataFrame:
    """Série ERA5 horaire, rayonnement converti en W/m².

    Parameters
    ----------
    settings, root
        CSV ``era5_hourly.csv``.
    start_utc, end_exclusive_utc
        Filtre UTC.

    Returns
    -------
    pd.DataFrame
        ``ssrd_j_m2``, ``ssrd_w_m2``, vent à 10 m.
    """

    path = hourly_csv_path(root, settings)
    if not path.is_file():
        raise CleanError(f"meteo introuvable : {path} (lance ingest-copernicus)")
    frame = pd.read_csv(path)
    frame["datetime_utc"] = pd.to_datetime(frame["datetime_utc"], utc=True)
    frame = frame.rename(
        columns={
            "ssrd": "ssrd_j_m2",
            "u10": "u10_ms",
            "v10": "v10_ms",
            "wind_speed": "wind_speed_ms",
        }
    )
    frame["ssrd_w_m2"] = frame["ssrd_j_m2"] / _SECONDS_PER_HOUR
    frame = _filter_period(frame, start_utc, end_exclusive_utc)
    return frame[
        [
            "datetime_utc",
            "region",
            "ssrd_j_m2",
            "ssrd_w_m2",
            "u10_ms",
            "v10_ms",
            "wind_speed_ms",
        ]
    ].sort_values(["datetime_utc", "region"]).reset_index(drop=True)


def build_datetime_dim(timestamps: pd.Series, tz_name: str) -> pd.DataFrame:
    """Dimension temps à partir des instants UTC observés.

    Parameters
    ----------
    timestamps
        Instants (avec fuseau).
    tz_name
        Fuseau d'affichage (saison, week-end).

    Returns
    -------
    pd.DataFrame
        Une ligne par instant unique.
    """

    unique = pd.to_datetime(timestamps, utc=True).drop_duplicates().sort_values()
    unique = unique[unique.notna()]
    brussels = unique.dt.tz_convert(tz_name)
    months = brussels.dt.month
    return pd.DataFrame(
        {
            "datetime_utc": unique,
            "datetime_brussels": brussels.dt.tz_localize(None),
            "date_brussels": brussels.dt.date,
            "year": brussels.dt.year.astype(int),
            "month": months.astype(int),
            "day": brussels.dt.day.astype(int),
            "hour": brussels.dt.hour.astype(int),
            "minute": brussels.dt.minute.astype(int),
            "weekday": brussels.dt.weekday.astype(int),
            "is_weekend": brussels.dt.weekday >= 5,
            "season": months.map(_season),
        }
    ).reset_index(drop=True)


def _season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def _elia_csv(settings: Settings, root: Path, *, kind: str) -> Path:
    export = next(item for item in planned_exports(settings) if item.kind == kind)
    path = raw_elia_dir(root, settings) / csv_filename(
        export, settings.period.start, settings.period.end
    )
    if not path.is_file():
        raise CleanError(f"fichier Elia introuvable : {path} (lance ingest-elia)")
    return path


def _read_elia(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "datetime" not in frame.columns:
        raise CleanError(f"colonne datetime absente dans {path.name}")
    frame["datetime_utc"] = pd.to_datetime(frame["datetime"], utc=True)
    return frame


def _filter_period(frame: pd.DataFrame, start_utc: datetime, end_exclusive_utc: datetime) -> pd.DataFrame:
    start = pd.Timestamp(start_utc)
    end = pd.Timestamp(end_exclusive_utc)
    mask = (frame["datetime_utc"] >= start) & (frame["datetime_utc"] < end)
    return frame.loc[mask].copy()
