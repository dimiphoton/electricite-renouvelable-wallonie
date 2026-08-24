"""Ingestion des archives Elia (charge, solaire, éolien) via l'API Open Data.

Télécharge les exports CSV (pas l'endpoint ``records``, limité en pagination)
vers ``data/raw/elia/``. Les fichiers existants non vides sont ignorés, sauf
``--force``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from renewables_wallonia.config import Settings

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 256 * 1024
_TIMEOUT_S = 300
_RETRIES = 3
_USER_AGENT = "renewables-wallonia/0.1 (portfolio)"


class EliaIngestError(RuntimeError):
    """Échec du téléchargement ou de l'écriture d'un export Elia."""


@dataclass(frozen=True)
class EliaExport:
    """Un jeu Elia à exporter, avec filtre régional éventuel."""

    kind: str
    dataset_id: str
    regions: tuple[str, ...] | None


@dataclass(frozen=True)
class DownloadResult:
    """Résultat d'un export : chemin local et s'il a été sauté."""

    path: Path
    skipped: bool
    bytes_written: int


def planned_exports(settings: Settings) -> tuple[EliaExport, ...]:
    """Liste les trois archives à télécharger (charge, solaire, éolien).

    Parameters
    ----------
    settings
        Configuration du projet.

    Returns
    -------
    tuple of EliaExport
        Charge sans filtre régional ; solaire et éolien filtrés sur
        ``settings.elia.regions``.
    """

    return (
        EliaExport("load", settings.elia.load_dataset, None),
        EliaExport("solar", settings.elia.solar_dataset, settings.elia.regions.solar),
        EliaExport("wind", settings.elia.wind_dataset, settings.elia.regions.wind),
    )


def period_utc_bounds(start: date, end: date, tz_name: str) -> tuple[datetime, datetime]:
    """Convertit des dates civiles inclusives en intervalle UTC ``[début, fin[``.

    Parameters
    ----------
    start
        Premier jour inclus (minuit dans ``tz_name``).
    end
        Dernier jour inclus.
    tz_name
        Fuseau des dates civiles (``Europe/Brussels``).

    Returns
    -------
    tuple of datetime
        Instant de début (inclus) et de fin (exclu), tous deux en UTC.

    Raises
    ------
    ValueError
        Si ``start`` n'est pas strictement avant ``end``.
    """

    if start >= end:
        raise ValueError("la date de début doit être antérieure à la date de fin")
    tz = ZoneInfo(tz_name)
    start_utc = datetime.combine(start, dt_time.min, tzinfo=tz).astimezone(timezone.utc)
    end_exclusive = datetime.combine(
        end + timedelta(days=1), dt_time.min, tzinfo=tz
    ).astimezone(timezone.utc)
    return start_utc, end_exclusive


def build_where_clause(
    start_utc: datetime,
    end_exclusive_utc: datetime,
    regions: tuple[str, ...] | None = None,
) -> str:
    """Construit le filtre ODSQL ``where`` pour un export.

    Parameters
    ----------
    start_utc, end_exclusive_utc
        Bornes UTC ``[début, fin[``.
    regions
        Valeurs du champ ``region``. ``None`` ou vide : pas de filtre
        (cas de la charge nationale).

    Returns
    -------
    str
        Clause ODSQL.
    """

    start_lit = _quote(_iso_z(start_utc))
    end_lit = _quote(_iso_z(end_exclusive_utc))
    clause = f"datetime >= {start_lit} AND datetime < {end_lit}"
    if regions:
        listed = ", ".join(_quote(region) for region in regions)
        clause += f" AND region IN ({listed})"
    return clause


def export_csv_url(base_url: str, dataset_id: str) -> str:
    """URL de l'export CSV d'un dataset Elia.

    Parameters
    ----------
    base_url
        Racine Explore API v2.1, sans slash final.
    dataset_id
        Identifiant Opendatasoft (ex. ``ods001``).

    Returns
    -------
    str
        URL sans paramètres de requête.
    """

    return f"{base_url.rstrip('/')}/catalog/datasets/{dataset_id}/exports/csv"


def raw_elia_dir(root: Path, settings: Settings) -> Path:
    """Dossier ``data/raw/elia`` sous la racine du dépôt.

    Parameters
    ----------
    root
        Racine du dépôt.
    settings
        Configuration (chemin ``raw_dir``).

    Returns
    -------
    Path
        Dossier de destination des CSV bruts.
    """

    return root / settings.paths.raw_dir / "elia"


def csv_filename(export: EliaExport, start: date, end: date) -> str:
    """Nom de fichier brut, bornes civiles incluses.

    Parameters
    ----------
    export
        Jeu à télécharger.
    start, end
        Période civile.

    Returns
    -------
    str
        Ex. ``ods001_load_2023-09-01_2026-08-31.csv``.
    """

    return f"{export.dataset_id}_{export.kind}_{start.isoformat()}_{end.isoformat()}.csv"


def ingest_elia(
    settings: Settings,
    root: Path,
    *,
    force: bool = False,
) -> tuple[DownloadResult, ...]:
    """Télécharge les trois archives Elia vers ``data/raw/elia/``.

    Parameters
    ----------
    settings
        Configuration (période, datasets, régions).
    root
        Racine du dépôt.
    force
        Si vrai, retélécharge même si le fichier existe déjà.

    Returns
    -------
    tuple of DownloadResult
        Un résultat par export.

    Raises
    ------
    EliaIngestError
        Réseau, HTTP, ou écriture disque.
    """

    start_utc, end_exclusive_utc = period_utc_bounds(
        settings.period.start,
        settings.period.end,
        settings.display.timezone,
    )
    dest_dir = raw_elia_dir(root, settings)
    dest_dir.mkdir(parents=True, exist_ok=True)

    results: list[DownloadResult] = []
    for export in planned_exports(settings):
        dest = dest_dir / csv_filename(export, settings.period.start, settings.period.end)
        if dest.is_file() and dest.stat().st_size > 0 and not force:
            logger.info("deja present, ignore : %s", dest.name)
            results.append(DownloadResult(path=dest, skipped=True, bytes_written=0))
            continue

        where = build_where_clause(start_utc, end_exclusive_utc, export.regions)
        url = export_csv_url(settings.elia.base_url, export.dataset_id)
        params = {
            "where": where,
            "timezone": "UTC",
            "delimiter": ",",
            "with_bom": "false",
        }
        full_url = f"{url}?{urlencode(params)}"
        logger.info("telechargement %s (%s) -> %s", export.dataset_id, export.kind, dest.name)
        try:
            nbytes = _download_to_file(full_url, dest)
        except (OSError, URLError) as exc:
            raise EliaIngestError(f"echec {export.dataset_id} : {exc}") from exc
        results.append(DownloadResult(path=dest, skipped=False, bytes_written=nbytes))
        logger.info("ecrit %s octets", nbytes)
    return tuple(results)


def _iso_z(instant: datetime) -> str:
    return instant.astimezone(timezone.utc).isoformat()


def _quote(value: str) -> str:
    if '"' in value:
        raise ValueError(f"valeur ODSQL invalide (guillemet) : {value!r}")
    return f'"{value}"'


def _download_to_file(url: str, dest: Path) -> int:
    """Écrit l'URL dans ``dest`` via un fichier temporaire, avec quelques retries."""
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    last_error: Exception | None = None
    for attempt in range(1, _RETRIES + 1):
        try:
            nbytes = _stream_get(url, tmp)
            tmp.replace(dest)
            return nbytes
        except HTTPError as exc:
            last_error = exc
            # 4xx : pas la peine de réessayer (filtre invalide, dataset inconnu).
            if exc.code < 500 or attempt == _RETRIES:
                _unlink_quiet(tmp)
                raise
        except URLError as exc:
            last_error = exc
            if attempt == _RETRIES:
                _unlink_quiet(tmp)
                raise
        logger.warning("tentative %s/%s echouee (%s), nouvel essai", attempt, _RETRIES, last_error)
        time.sleep(2**attempt)
    _unlink_quiet(tmp)
    raise EliaIngestError(str(last_error))


def _stream_get(url: str, dest: Path) -> int:
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    nbytes = 0
    with urlopen(request, timeout=_TIMEOUT_S) as response:
        with dest.open("wb") as handle:
            while True:
                chunk = response.read(_CHUNK_SIZE)
                if not chunk:
                    break
                handle.write(chunk)
                nbytes += len(chunk)
    if nbytes == 0:
        raise EliaIngestError(f"reponse vide : {url}")
    return nbytes


def _unlink_quiet(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.debug("impossible de supprimer %s", path)
