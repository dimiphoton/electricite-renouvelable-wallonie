"""Tests de l'entrepôt DuckDB."""

from pathlib import Path

import duckdb
import pandas as pd

from renewables_wallonia.config import load_settings
from renewables_wallonia.data.elia import csv_filename, planned_exports
from renewables_wallonia.data.warehouse import build_warehouse


def _seed_bruts(tmp_path: Path) -> None:
    settings = load_settings()
    elia_dir = tmp_path / "data" / "raw" / "elia"
    elia_dir.mkdir(parents=True)
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    ts = "2023-09-01T00:00:00+00:00"

    def dest(kind: str) -> Path:
        export = next(item for item in planned_exports(settings) if item.kind == kind)
        return elia_dir / csv_filename(export, settings.period.start, settings.period.end)

    pd.DataFrame(
        {
            "datetime": [ts],
            "totalload": [8000.0],
            "dayaheadforecast": [8100.0],
        }
    ).to_csv(dest("load"), index=False)
    pd.DataFrame(
        {
            "datetime": [ts],
            "region": ["Belgium"],
            "measured": [100.0],
            "dayaheadforecast": [90.0],
            "monitoredcapacity": [1000.0],
            "loadfactor": [10.0],
        }
    ).to_csv(dest("solar"), index=False)
    pd.DataFrame(
        {
            "datetime": [ts],
            "region": ["Wallonia"],
            "measured": [50.0],
            "dayaheadforecast": [40.0],
            "monitoredcapacity": [200.0],
        }
    ).to_csv(dest("wind"), index=False)
    pd.DataFrame(
        {
            "datetime_utc": [ts],
            "region": ["Belgium"],
            "ssrd": [0.0],
            "u10": [1.0],
            "v10": [2.0],
            "wind_speed": [2.2],
        }
    ).to_csv(processed / "era5_hourly.csv", index=False)


def test_build_warehouse_vue_couverture(tmp_path: Path) -> None:
    """La vue Belgique joint charge, solaire et éolien."""
    _seed_bruts(tmp_path)
    db_path = build_warehouse(load_settings(), tmp_path)
    assert db_path.is_file()
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        row = connection.execute(
            "SELECT load_mw, solar_mw, wind_mw, coverage_ratio FROM v_belgium_qh"
        ).fetchone()
    finally:
        connection.close()
    assert row[0] == 8000.0
    assert row[1] == 100.0
    assert row[2] == 50.0
    assert row[3] == 150.0 / 8000.0
