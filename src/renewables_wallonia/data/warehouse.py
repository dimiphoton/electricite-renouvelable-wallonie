"""Chargement du schéma étoile dans DuckDB."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

from renewables_wallonia.config import Settings
from renewables_wallonia.data.clean import clean_all

logger = logging.getLogger(__name__)


class WarehouseError(RuntimeError):
    """Échec de création ou de chargement de l'entrepôt DuckDB."""


def schema_path() -> Path:
    """Chemin de ``sql/schema.sql`` (à côté de ``src/``, pas sous data/).

    Returns
    -------
    Path
        Fichier DDL du dépôt.
    """

    return Path(__file__).resolve().parents[3] / "sql" / "schema.sql"


def warehouse_path(root: Path, settings: Settings) -> Path:
    """Fichier ``warehouse.duckdb``.

    Parameters
    ----------
    root
        Racine du dépôt.
    settings
        Chemin relatif ``paths.warehouse``.

    Returns
    -------
    Path
        Base DuckDB.
    """

    return root / settings.paths.warehouse


def open_warehouse(
    settings: Settings,
    root: Path,
    *,
    read_only: bool = True,
) -> duckdb.DuckDBPyConnection:
    """Ouvre l'entrepôt existant.

    Parameters
    ----------
    settings, root
        Chemin ``paths.warehouse``.
    read_only
        Ouverture en lecture seule (analyse).

    Returns
    -------
    duckdb.DuckDBPyConnection
        Connexion ouverte (à fermer par l'appelant).

    Raises
    ------
    WarehouseError
        Fichier absent.
    """

    db_path = warehouse_path(root, settings)
    if not db_path.is_file():
        raise WarehouseError(
            f"entrepot introuvable : {db_path} (lance build-warehouse)"
        )
    return duckdb.connect(str(db_path), read_only=read_only)


def build_warehouse(settings: Settings, root: Path) -> Path:
    """Nettoie les bruts et (re)crée l'entrepôt.

    Parameters
    ----------
    settings
        Période et chemins.
    root
        Racine du dépôt.

    Returns
    -------
    Path
        Fichier DuckDB écrit.

    Raises
    ------
    CleanError
        Bruts absents.
    WarehouseError
        Schéma SQL illisible ou chargement DuckDB.
    """

    tables = clean_all(settings, root)
    db_path = warehouse_path(root, settings)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    ddl = schema_path()
    if not ddl.is_file():
        raise WarehouseError(f"schema SQL introuvable : {ddl}")

    logger.info("chargement DuckDB -> %s", db_path)
    connection = duckdb.connect(str(db_path))
    try:
        connection.execute(ddl.read_text(encoding="utf-8"))
        _insert_dimension(connection, "dim_region", _regions(tables))
        _insert_dimension(connection, "dim_source", pd.DataFrame({"source": ["solar", "wind"]}))
        _insert_dimension(connection, "dim_datetime", tables["datetime"])
        _insert_fact(connection, "fact_load", tables["load"])
        _insert_fact(connection, "fact_generation", tables["generation"])
        _insert_fact(connection, "fact_weather", tables["weather"])
        counts = {
            "fact_load": int(connection.execute("SELECT COUNT(*) FROM fact_load").fetchone()[0]),
            "fact_generation": int(
                connection.execute("SELECT COUNT(*) FROM fact_generation").fetchone()[0]
            ),
            "fact_weather": int(
                connection.execute("SELECT COUNT(*) FROM fact_weather").fetchone()[0]
            ),
        }
    except duckdb.Error as exc:
        raise WarehouseError(f"DuckDB : {exc}") from exc
    finally:
        connection.close()

    for name, count in counts.items():
        logger.info("%s : %s lignes", name, count)
    return db_path


def _regions(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    names = pd.concat(
        [
            tables["load"]["region"],
            tables["generation"]["region"],
            tables["weather"]["region"],
        ],
        ignore_index=True,
    ).dropna().drop_duplicates().sort_values()
    return pd.DataFrame({"region": names})


def _insert_dimension(connection: duckdb.DuckDBPyConnection, table: str, frame: pd.DataFrame) -> None:
    connection.register("_dim", frame)
    connection.execute(f"INSERT INTO {table} SELECT * FROM _dim")
    connection.unregister("_dim")


def _insert_fact(connection: duckdb.DuckDBPyConnection, table: str, frame: pd.DataFrame) -> None:
    connection.register("_fact", frame)
    connection.execute(f"INSERT INTO {table} SELECT * FROM _fact")
    connection.unregister("_fact")
