"""Tests des requêtes d'analyse métier."""

from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from renewables_wallonia.analysis import (
    AnalysisError,
    AnalysisResult,
    analyze_connection,
    build_headlines,
    format_report,
    run_analysis,
    split_named_queries,
    write_analysis_outputs,
)
from renewables_wallonia.config import load_settings
from renewables_wallonia.data.clean import build_datetime_dim
from renewables_wallonia.data.warehouse import schema_path


def _ts(*parts: int) -> datetime:
    return datetime(*parts, tzinfo=timezone.utc)


def _mini_connection() -> duckdb.DuckDBPyConnection:
    """Petit entrepôt en mémoire : un pic d'été, un soir d'hiver, météo linéaire."""
    connection = duckdb.connect(":memory:")
    connection.execute(schema_path().read_text(encoding="utf-8"))

    load_rows = [
        *(_qh_load(_ts(2024, 7, 15, 8, minute), 8000.0) for minute in (0, 15, 30, 45)),
        *(_qh_load(_ts(2024, 7, 15, 9, minute), 8000.0) for minute in (0, 15, 30, 45)),
        _qh_load(_ts(2024, 7, 15, 10, 0), 8000.0),
        _qh_load(_ts(2024, 7, 15, 10, 15), 12000.0),
        _qh_load(_ts(2024, 7, 15, 20, 0), 7000.0),
        _qh_load(_ts(2024, 1, 15, 17, 0), 13000.0),
    ]
    gen_rows = [
        *(_qh_gen(_ts(2024, 7, 15, 8, minute), "Belgium", "solar", 1000.0) for minute in (0, 15, 30, 45)),
        *(_qh_gen(_ts(2024, 7, 15, 8, minute), "Belgium", "wind", 800.0) for minute in (0, 15, 30, 45)),
        *(_qh_gen(_ts(2024, 7, 15, 9, minute), "Belgium", "solar", 1000.0) for minute in (0, 15, 30, 45)),
        *(_qh_gen(_ts(2024, 7, 15, 9, minute), "Belgium", "wind", 800.0) for minute in (0, 15, 30, 45)),
        _qh_gen(_ts(2024, 7, 15, 10, 0), "Belgium", "solar", 1000.0),
        _qh_gen(_ts(2024, 7, 15, 10, 0), "Belgium", "wind", 800.0),
        _qh_gen(_ts(2024, 7, 15, 10, 15), "Belgium", "solar", 6000.0),
        _qh_gen(_ts(2024, 7, 15, 10, 15), "Belgium", "wind", 400.0),
        _qh_gen(_ts(2024, 7, 15, 20, 0), "Belgium", "solar", 20.0),
        _qh_gen(_ts(2024, 7, 15, 20, 0), "Belgium", "wind", 900.0),
        _qh_gen(_ts(2024, 1, 15, 17, 0), "Belgium", "solar", 5.0),
        _qh_gen(_ts(2024, 1, 15, 17, 0), "Belgium", "wind", 80.0),
        _qh_gen(_ts(2024, 7, 15, 8, 0), "Wallonia", "solar", 10.0),
        _qh_gen(_ts(2024, 7, 15, 9, 0), "Wallonia", "solar", 20.0),
        _qh_gen(_ts(2024, 7, 15, 10, 0), "Wallonia", "solar", 30.0),
        _qh_gen(_ts(2024, 7, 15, 8, 0), "Wallonia", "wind", 10.0),
        _qh_gen(_ts(2024, 7, 15, 9, 0), "Wallonia", "wind", 20.0),
        _qh_gen(_ts(2024, 7, 15, 10, 0), "Wallonia", "wind", 30.0),
    ]
    weather_rows = [
        _hour_weather(_ts(2024, 7, 15, 8, 0), 100.0, 1.0),
        _hour_weather(_ts(2024, 7, 15, 9, 0), 200.0, 2.0),
        _hour_weather(_ts(2024, 7, 15, 10, 0), 300.0, 3.0),
    ]

    load = pd.DataFrame(load_rows)
    generation = pd.DataFrame(gen_rows)
    weather = pd.DataFrame(weather_rows)
    clock = build_datetime_dim(
        pd.concat(
            [load["datetime_utc"], generation["datetime_utc"], weather["datetime_utc"]],
            ignore_index=True,
        ),
        "Europe/Brussels",
    )
    _insert(connection, "dim_region", pd.DataFrame({"region": ["Belgium", "Wallonia"]}))
    _insert(connection, "dim_source", pd.DataFrame({"source": ["solar", "wind"]}))
    _insert(connection, "dim_datetime", clock)
    _insert(connection, "fact_load", load)
    _insert(connection, "fact_generation", generation)
    _insert(connection, "fact_weather", weather)
    return connection


def _qh_load(ts: datetime, load_mw: float) -> dict:
    return {
        "datetime_utc": ts,
        "region": "Belgium",
        "load_mw": load_mw,
        "dayahead_mw": load_mw,
    }


def _qh_gen(ts: datetime, region: str, source: str, measured_mw: float) -> dict:
    return {
        "datetime_utc": ts,
        "region": region,
        "source": source,
        "measured_mw": measured_mw,
        "dayahead_mw": measured_mw,
        "capacity_mw": 100.0,
        "load_factor": measured_mw / 100.0,
    }


def _hour_weather(ts: datetime, ssrd_w_m2: float, wind_speed_ms: float) -> dict:
    return {
        "datetime_utc": ts,
        "region": "Wallonia",
        "ssrd_j_m2": ssrd_w_m2 * 3600.0,
        "ssrd_w_m2": ssrd_w_m2,
        "u10_ms": wind_speed_ms,
        "v10_ms": 0.0,
        "wind_speed_ms": wind_speed_ms,
    }


def _insert(connection: duckdb.DuckDBPyConnection, table: str, frame: pd.DataFrame) -> None:
    connection.register("_tmp", frame)
    connection.execute(f"INSERT INTO {table} SELECT * FROM _tmp")
    connection.unregister("_tmp")


def test_split_named_queries() -> None:
    """Le marqueur ``-- name:`` sépare les requêtes."""
    named = split_named_queries(
        "-- commentaire\n-- name: alpha\nSELECT 1;\n-- name: beta\nSELECT 2\n"
    )
    assert named["alpha"] == "SELECT 1"
    assert named["beta"] == "SELECT 2"


def test_analyze_summer_peak_et_meteo() -> None:
    """Le pic d'été a plus de solaire ; la météo wallonne est linéaire."""
    connection = _mini_connection()
    try:
        tables = analyze_connection(connection, load_settings())
    finally:
        connection.close()

    peaks = tables["summer_peaks"].iloc[0]
    assert peaks["solar_mw_peak"] > peaks["solar_mw_offpeak"]
    assert peaks["coverage_peak"] > peaks["coverage_offpeak"]

    weather = tables["wallonia_weather"].iloc[0]
    assert weather["corr_solar_ssrd"] == pytest.approx(1.0)
    assert weather["corr_wind_speed"] == pytest.approx(1.0)

    stress = tables["stress_overall"].iloc[0]
    assert stress["n_stress"] >= 1
    assert stress["mean_coverage_stress"] < 0.1

    result = AnalysisResult(tables=tables, headlines=build_headlines(tables))
    report = format_report(result)
    assert "Q1" in report
    assert "Q4" in report


def test_run_analysis_sans_entrepot(tmp_path: Path) -> None:
    """Sans DuckDB, message pour lancer build-warehouse."""
    settings = load_settings()
    with pytest.raises(AnalysisError, match="build-warehouse"):
        run_analysis(settings, tmp_path, write=False)


def test_write_analysis_outputs(tmp_path: Path) -> None:
    """CSV + JSON d'indicateurs."""
    connection = _mini_connection()
    try:
        tables = analyze_connection(connection, load_settings())
    finally:
        connection.close()
    result = AnalysisResult(tables=tables, headlines=build_headlines(tables))
    dest = tmp_path / "analysis"
    write_analysis_outputs(result, dest)
    assert (dest / "coverage_overall.csv").is_file()
    assert (dest / "headlines.json").is_file()
    payload = pd.read_json(dest / "headlines.json", typ="series")
    assert payload["corr_solar_ssrd"] == pytest.approx(1.0)
