"""Ingestion ERA5 (Copernicus CDS) : grilles mensuelles puis moyenne spatiale.

On télécharge la bbox Belgique (qui contient la Wallonie), un fichier NetCDF
par mois, puis on calcule une série horaire moyenne — pas de SIG, juste une
moyenne pondérée par ``cos(latitude)``.
"""

from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import xarray as xr

from renewables_wallonia.config import Settings

logger = logging.getLogger(__name__)

RetrieveFn = Callable[[str, dict[str, Any], Path], None]

_ALL_DAYS = [f"{day:02d}" for day in range(1, 32)]
_ALL_HOURS = [f"{hour:02d}:00" for hour in range(24)]

# Noms courts ERA5 vs noms longs du formulaire CDS.
_U_NAMES = ("u10", "10m_u_component_of_wind")
_V_NAMES = ("v10", "10m_v_component_of_wind")
_SSRD_NAMES = ("ssrd", "surface_solar_radiation_downwards")
_LAT_NAMES = ("latitude", "lat")
_LON_NAMES = ("longitude", "lon")
_TIME_NAMES = ("valid_time", "time", "datetime")


class CopernicusIngestError(RuntimeError):
    """Échec d'une requête CDS ou de l'agrégation ERA5."""


@dataclass(frozen=True)
class MonthDownload:
    """Un NetCDF mensuel brut."""

    path: Path
    year: int
    month: int
    skipped: bool


def months_in_period(start: date, end: date) -> tuple[tuple[int, int], ...]:
    """Liste les mois civils recouverts par ``[start, end]`` inclus.

    Parameters
    ----------
    start, end
        Bornes civiles inclusives.

    Returns
    -------
    tuple of (year, month)
        Mois dans l'ordre chronologique.

    Raises
    ------
    ValueError
        Si ``start`` n'est pas antérieur à ``end``.
    """

    if start >= end:
        raise ValueError("la date de début doit être antérieure à la date de fin")
    months: list[tuple[int, int]] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return tuple(months)


def era5_month_request(settings: Settings, year: int, month: int) -> dict[str, Any]:
    """Construit le dictionnaire de requête CDS pour un mois.

    Parameters
    ----------
    settings
        Dataset, variables, bbox Belgique.
    year, month
        Mois demandé (le calendrier CDS ignore les jours invalides, ex. 31/02).

    Returns
    -------
    dict
        Payload ``cdsapi.Client.retrieve``.
    """

    return {
        "product_type": ["reanalysis"],
        "variable": list(settings.copernicus.variables),
        "year": [str(year)],
        "month": [f"{month:02d}"],
        "day": list(_ALL_DAYS),
        "time": list(_ALL_HOURS),
        "area": list(settings.copernicus.belgium_bbox),
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def raw_copernicus_dir(root: Path, settings: Settings) -> Path:
    """Dossier des NetCDF mensuels.

    Parameters
    ----------
    root
        Racine du dépôt.
    settings
        Chemin ``raw_dir``.

    Returns
    -------
    Path
        ``<root>/data/raw/copernicus``.
    """

    return root / settings.paths.raw_dir / "copernicus"


def monthly_nc_name(year: int, month: int) -> str:
    """Nom de fichier brut mensuel.

    Parameters
    ----------
    year, month
        Mois ERA5.

    Returns
    -------
    str
        Ex. ``era5_2024-01.nc``.
    """

    return f"era5_{year:04d}-{month:02d}.nc"


def hourly_csv_path(root: Path, settings: Settings) -> Path:
    """Série horaire agrégée (Belgique + Wallonie).

    Parameters
    ----------
    root
        Racine du dépôt.
    settings
        Chemin ``processed_dir``.

    Returns
    -------
    Path
        ``data/processed/era5_hourly.csv``.
    """

    return root / settings.paths.processed_dir / "era5_hourly.csv"


def ingest_copernicus(
    settings: Settings,
    root: Path,
    *,
    force: bool = False,
    retrieve: RetrieveFn | None = None,
) -> tuple[tuple[MonthDownload, ...], Path]:
    """Télécharge les mois ERA5 puis écrit la série horaire agrégée.

    Parameters
    ----------
    settings
        Période, dataset, bbox.
    root
        Racine du dépôt.
    force
        Retélécharge les NetCDF déjà présents.
    retrieve
        Fonction de téléchargement (défaut : client ``cdsapi``). Utile aux tests.

    Returns
    -------
    months, csv_path
        Résultats mensuels et chemin du CSV agrégé.

    Raises
    ------
    CopernicusIngestError
        Requête CDS, fichier illisible, ou variable manquante.
    """

    dest_dir = raw_copernicus_dir(root, settings)
    dest_dir.mkdir(parents=True, exist_ok=True)
    retrieve_fn = retrieve or _cds_retrieve

    downloads: list[MonthDownload] = []
    for year, month in months_in_period(settings.period.start, settings.period.end):
        dest = dest_dir / monthly_nc_name(year, month)
        if dest.is_file() and dest.stat().st_size > 0 and not force:
            logger.info("deja present, ignore : %s", dest.name)
            downloads.append(MonthDownload(path=dest, year=year, month=month, skipped=True))
            continue
        request = era5_month_request(settings, year, month)
        logger.info("telechargement ERA5 %04d-%02d -> %s", year, month, dest.name)
        try:
            _download_month(
                settings.copernicus.dataset,
                request,
                dest,
                retrieve_fn,
            )
        except CopernicusIngestError:
            raise
        except Exception as exc:  # cdsapi lève des exceptions variées (licence, file d'attente…)
            raise CopernicusIngestError(f"echec ERA5 {year:04d}-{month:02d} : {exc}") from exc
        downloads.append(
            MonthDownload(path=dest, year=year, month=month, skipped=False)
        )

    csv_path = hourly_csv_path(root, settings)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame = _aggregate_months(
        tuple(item.path for item in downloads),
        settings.copernicus.belgium_bbox,
        settings.copernicus.wallonia_bbox,
        settings.period.start,
        settings.period.end,
    )
    frame.to_csv(csv_path, index=False)
    logger.info("serie horaire : %s (%s lignes)", csv_path.name, len(frame))
    return tuple(downloads), csv_path


def spatial_mean(dataset: xr.Dataset, bbox: tuple[float, float, float, float]) -> xr.Dataset:
    """Moyenne spatiale pondérée par ``cos(latitude)`` sur une bbox N,W,S,E.

    Parameters
    ----------
    dataset
        Grille ERA5.
    bbox
        Nord, ouest, sud, est en degrés.

    Returns
    -------
    xr.Dataset
        Une valeur par pas de temps, plus de dimensions lat/lon.
    """

    north, west, south, east = bbox
    lat_name = _first_name(dataset, _LAT_NAMES, what="latitude")
    lon_name = _first_name(dataset, _LON_NAMES, what="longitude")
    lat_values = dataset[lat_name]
    # ERA5 : latitudes en général du nord vers le sud.
    if lat_values[0] > lat_values[-1]:
        lat_slice = slice(north, south)
    else:
        lat_slice = slice(south, north)
    subset = dataset.sel({lat_name: lat_slice, lon_name: slice(west, east)})
    if subset.sizes.get(lat_name, 0) == 0 or subset.sizes.get(lon_name, 0) == 0:
        raise CopernicusIngestError(f"bbox {bbox} ne recouvre aucune maille ERA5")
    weights = np.cos(np.deg2rad(subset[lat_name]))
    return subset.weighted(weights).mean(dim=(lat_name, lon_name))


def _cds_retrieve(dataset: str, request: dict[str, Any], target: Path) -> None:
    import cdsapi

    client = cdsapi.Client()
    client.retrieve(dataset, request, str(target))


def _download_month(
    dataset: str,
    request: dict[str, Any],
    dest: Path,
    retrieve: RetrieveFn,
) -> None:
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        retrieve(dataset, request, tmp)
        _materialize_netcdf(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)


def _materialize_netcdf(tmp: Path, dest: Path) -> None:
    if not tmp.is_file() or tmp.stat().st_size == 0:
        raise CopernicusIngestError(f"fichier CDS vide : {tmp}")
    if zipfile.is_zipfile(tmp):
        with zipfile.ZipFile(tmp) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".nc")]
            if not names:
                raise CopernicusIngestError("archive CDS sans NetCDF")
            dest.write_bytes(archive.read(names[0]))
            return
    tmp.replace(dest)


def _aggregate_months(
    paths: tuple[Path, ...],
    belgium_bbox: tuple[float, float, float, float],
    wallonia_bbox: tuple[float, float, float, float],
    start: date,
    end: date,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        logger.info("agregation %s", path.name)
        with xr.open_dataset(path) as dataset:
            prepared = _prepare_grid(dataset)
            for region, bbox in (("Belgium", belgium_bbox), ("Wallonia", wallonia_bbox)):
                mean = spatial_mean(prepared, bbox)
                frames.append(_dataset_to_frame(mean, region))
    if not frames:
        raise CopernicusIngestError("aucun NetCDF a agreger")
    frame = pd.concat(frames, ignore_index=True)
    frame["datetime_utc"] = pd.to_datetime(frame["datetime_utc"], utc=True)
    start_ts = pd.Timestamp(start, tz="UTC")
    # end inclus : on garde jusqu'à 23:00 UTC du dernier jour (filtre fin plus tard en Brussels).
    end_ts = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    mask = (frame["datetime_utc"] >= start_ts) & (frame["datetime_utc"] < end_ts)
    frame = frame.loc[mask].sort_values(["region", "datetime_utc"]).reset_index(drop=True)
    return frame


def _prepare_grid(dataset: xr.Dataset) -> xr.Dataset:
    u_name = _first_var(dataset, _U_NAMES, what="vent u")
    v_name = _first_var(dataset, _V_NAMES, what="vent v")
    ssrd_name = _first_var(dataset, _SSRD_NAMES, what="rayonnement")
    # Vitesse par maille, puis moyenne spatiale (plus honnête que hypot(moyenne u, moyenne v)).
    wind_speed = np.hypot(dataset[u_name], dataset[v_name])
    return xr.Dataset(
        {
            "u10": dataset[u_name],
            "v10": dataset[v_name],
            "ssrd": dataset[ssrd_name],
            "wind_speed": wind_speed,
        }
    )


def _dataset_to_frame(mean: xr.Dataset, region: str) -> pd.DataFrame:
    time_name = _first_name(mean, _TIME_NAMES, what="temps")
    indexed = mean.reset_coords(drop=True)
    frame = indexed.to_dataframe().reset_index()
    frame = frame.rename(columns={time_name: "datetime_utc"})
    frame["region"] = region
    return frame[["datetime_utc", "region", "ssrd", "u10", "v10", "wind_speed"]]


def _first_name(dataset: xr.Dataset, candidates: tuple[str, ...], *, what: str) -> str:
    for name in candidates:
        if name in dataset.coords or name in dataset.dims or name in dataset.variables:
            return name
    raise CopernicusIngestError(
        f"coordonnee {what} introuvable parmi {candidates}, dispo={list(dataset.variables)}"
    )


def _first_var(dataset: xr.Dataset, candidates: tuple[str, ...], *, what: str) -> str:
    for name in candidates:
        if name in dataset.data_vars:
            return name
    raise CopernicusIngestError(
        f"variable {what} introuvable parmi {candidates}, dispo={list(dataset.data_vars)}"
    )
