"""Tests du module dashboard (reco, chargement CSV, figures)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from renewables_wallonia.dashboard import (
    DashboardError,
    build_recommendation,
    fig_coverage_heatmap,
    fig_stress_by_hour,
    format_pct,
    load_analysis_tables,
    load_dashboard_data,
)
from renewables_wallonia.config import load_settings


def _hour_season_frame() -> pd.DataFrame:
    rows = []
    for hour in range(24):
        winter = 0.20 if hour in (16, 17, 18, 19) else 0.28
        summer = 0.63 if hour == 14 else 0.35
        rows.append(
            {
                "season": "winter",
                "hour": hour,
                "mean_coverage": winter,
                "mean_load_mw": 11000.0,
                "mean_solar_mw": 30.0 if hour in (16, 17, 18, 19) else 200.0,
                "mean_wind_mw": 2000.0,
            }
        )
        rows.append(
            {
                "season": "summer",
                "hour": hour,
                "mean_coverage": summer,
                "mean_load_mw": 9000.0,
                "mean_solar_mw": 4500.0 if hour == 14 else 1200.0,
                "mean_wind_mw": 900.0,
            }
        )
    return pd.DataFrame(rows)


def _stress_hour_frame() -> pd.DataFrame:
    counts = [0] * 24
    counts[16] = 10
    counts[17] = 20
    counts[18] = 30
    counts[19] = 10
    return pd.DataFrame(
        {
            "hour": list(range(24)),
            "n_stress": counts,
            "mean_coverage_stress": [0.013] * 24,
        }
    )


def test_format_pct_virgule_francaise() -> None:
    """Les pourcentages s'affichent avec une virgule."""
    assert format_pct(0.274) == "27,4 %"
    assert format_pct(None) == "n.d."


def test_build_recommendation_cible_le_soir_dhiver() -> None:
    """La reco pointe le créneau hivernal 16-19 h, pas les pics d'été."""
    tables = {
        "coverage_by_hour_season": _hour_season_frame(),
        "stress_by_hour": _stress_hour_frame(),
    }
    headlines = {
        "mean_coverage": 0.274,
        "coverage_summer_hour_14": 0.629,
        "coverage_summer_peak": 0.528,
        "share_stress": 0.007,
        "coverage_stress": 0.013,
        "corr_solar_wind": -0.21,
        "solar_mw_summer_peak": 4800.0,
        "solar_mw_summer_offpeak": 1500.0,
    }
    reco = build_recommendation(tables, headlines)
    assert "hiver" in reco.title.lower()
    assert reco.share_stress_in_evening == pytest.approx(1.0)
    assert reco.winter_evening_coverage == pytest.approx(0.20)
    assert "16-19" in reco.action or "16–19" in reco.action
    assert "été" in reco.action.lower() or "pics d'été" in reco.action.lower()


def test_fig_coverage_heatmap_a_des_traces() -> None:
    """La heatmap Q1 produit une figure Plotly non vide."""
    fig = fig_coverage_heatmap(_hour_season_frame())
    assert fig.data
    assert fig.layout.title.text


def test_fig_stress_by_hour_a_des_barres() -> None:
    """Le graphique de stress a une barre par heure."""
    fig = fig_stress_by_hour(_stress_hour_frame())
    assert fig.data
    assert len(fig.data[0].x) == 24


def test_load_analysis_tables_dossier_absent(tmp_path: Path) -> None:
    """Sans CSV, message pour lancer analyze."""
    with pytest.raises(DashboardError, match="analyze"):
        load_analysis_tables(tmp_path / "missing")


def test_load_dashboard_data_sans_entrepot(tmp_path: Path) -> None:
    """Sans CSV ni DuckDB, erreur explicite."""
    settings = load_settings()
    with pytest.raises(DashboardError, match="analyze"):
        load_dashboard_data(settings, tmp_path, with_weather_hourly=False)

