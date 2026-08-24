"""Quatre questions métier sur l'entrepôt DuckDB (SQL + agrégats)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from renewables_wallonia.config import Settings
from renewables_wallonia.data.warehouse import WarehouseError, open_warehouse

logger = logging.getLogger(__name__)
_SQL_PARAM = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


class AnalysisError(RuntimeError):
    """Entrepôt absent, SQL illisible ou requête en échec."""


@dataclass(frozen=True)
class AnalysisResult:
    """Tables issues des requêtes nommées et indicateurs pour le CLI."""

    tables: dict[str, pd.DataFrame]
    headlines: dict[str, float | None]


def analysis_sql_dir() -> Path:
    """Dossier ``sql/analysis/`` à la racine du dépôt.

    Returns
    -------
    Path
        Répertoire des fichiers ``.sql`` nommés.
    """

    return Path(__file__).resolve().parents[2] / "sql" / "analysis"


def split_named_queries(sql_text: str) -> dict[str, str]:
    """Découpe un fichier SQL en requêtes ``-- name: identifiant``.

    Parameters
    ----------
    sql_text
        Contenu d'un fichier ``.sql``.

    Returns
    -------
    dict of str
        Nom → SQL (sans point-virgule final).
    """

    queries: dict[str, str] = {}
    current: str | None = None
    chunks: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-- name:"):
            if current is not None:
                queries[current] = _join_sql(chunks)
            current = stripped.split(":", 1)[1].strip()
            chunks = []
            continue
        chunks.append(line)
    if current is not None:
        queries[current] = _join_sql(chunks)
    return queries


def query_parameters(settings: Settings) -> dict[str, float]:
    """Valeurs bindées dans les requêtes ``$...``.

    Parameters
    ----------
    settings
        Section ``[analysis]``.

    Returns
    -------
    dict
        Noms de paramètres DuckDB.
    """

    analysis = settings.analysis
    return {
        "peak_load_quantile": analysis.peak_load_quantile,
        "daytime_ssrd_w_m2": analysis.daytime_ssrd_w_m2,
        "stress_load_quantile": analysis.stress_load_quantile,
        "stress_renewable_quantile": analysis.stress_renewable_quantile,
        "coverage_mid_threshold": analysis.coverage_mid_threshold,
        "coverage_high_threshold": analysis.coverage_high_threshold,
    }


def analyze_connection(
    connection: duckdb.DuckDBPyConnection, settings: Settings
) -> dict[str, pd.DataFrame]:
    """Exécute toutes les requêtes nommées sur une connexion ouverte.

    Parameters
    ----------
    connection
        Connexion DuckDB (fichier ou mémoire).
    settings
        Seuils d'analyse.

    Returns
    -------
    dict of DataFrame
        Une table par ``-- name:``.

    Raises
    ------
    AnalysisError
        Fichier SQL absent ou requête en échec.
    """

    sql_dir = analysis_sql_dir()
    files = sorted(sql_dir.glob("*.sql"))
    if not files:
        raise AnalysisError(f"aucune requete SQL dans {sql_dir}")

    params = query_parameters(settings)
    tables: dict[str, pd.DataFrame] = {}
    for path in files:
        named = split_named_queries(path.read_text(encoding="utf-8"))
        if not named:
            raise AnalysisError(f"aucune requete nommee dans {path.name}")
        for name, sql in named.items():
            try:
                bound = _bound_parameters(sql, params)
                if bound:
                    tables[name] = connection.execute(sql, bound).df()
                else:
                    tables[name] = connection.execute(sql).df()
            except duckdb.Error as exc:
                raise AnalysisError(f"{path.name} / {name} : {exc}") from exc
    return tables


def run_analysis(settings: Settings, root: Path, *, write: bool = True) -> AnalysisResult:
    """Lance l'analyse sur ``warehouse.duckdb`` et écrit les CSV.

    Parameters
    ----------
    settings, root
        Entrepôt et dossier ``paths.analysis_dir``.
    write
        Si vrai, écrit CSV + ``headlines.json``.

    Returns
    -------
    AnalysisResult
        Tables et indicateurs.

    Raises
    ------
    AnalysisError
        Entrepôt manquant ou SQL en échec.
    """

    try:
        connection = open_warehouse(settings, root, read_only=True)
    except WarehouseError as exc:
        raise AnalysisError(str(exc)) from exc

    try:
        tables = analyze_connection(connection, settings)
    finally:
        connection.close()

    headlines = build_headlines(tables)
    result = AnalysisResult(tables=tables, headlines=headlines)
    if write:
        output_dir = root / settings.paths.analysis_dir
        write_analysis_outputs(result, output_dir)
        logger.info("tables d'analyse -> %s", output_dir)
    return result


def build_headlines(tables: dict[str, pd.DataFrame]) -> dict[str, float | None]:
    """Indicateurs uniques pour le CLI et les présentations.

    Parameters
    ----------
    tables
        Sortie de ``analyze_connection``.

    Returns
    -------
    dict
        Scalaires (pourcentages encore en ratio 0–1).
    """

    overall = tables["coverage_overall"]
    peaks = tables["summer_peaks"]
    coincidence = tables["summer_daily_peak_coincidence"]
    weather = tables["wallonia_weather"]
    comp = tables["complementarity_overall"]
    stress = tables["stress_overall"]
    by_season = tables["coverage_by_season"]
    by_hour = tables["coverage_by_hour_season"]
    corr_season = tables["solar_load_corr_by_season"]
    stress_season = tables["stress_by_season"]
    hour_band = tables["summer_hour_band"]
    daily = tables["coverage_daily_ma7"]

    return {
        "mean_coverage": _cell(overall, "mean_coverage"),
        "median_coverage": _cell(overall, "median_coverage"),
        "p10_coverage": _cell(overall, "p10_coverage"),
        "p90_coverage": _cell(overall, "p90_coverage"),
        "max_coverage": _cell(overall, "max_coverage"),
        "share_above_mid": _cell(overall, "share_above_mid"),
        "share_above_high": _cell(overall, "share_above_high"),
        "coverage_summer": _season_cell(by_season, "summer", "mean_coverage"),
        "coverage_winter": _season_cell(by_season, "winter", "mean_coverage"),
        "coverage_summer_hour_14": _hour_cell(by_hour, "summer", 14, "mean_coverage"),
        "coverage_winter_hour_18": _hour_cell(by_hour, "winter", 18, "mean_coverage"),
        "ma7_min": _cell(daily, "coverage_ma7", how="min") if not daily.empty else None,
        "ma7_max": _cell(daily, "coverage_ma7", how="max") if not daily.empty else None,
        "solar_mw_summer_peak": _cell(peaks, "solar_mw_peak"),
        "solar_mw_summer_offpeak": _cell(peaks, "solar_mw_offpeak"),
        "solar_load_share_summer_peak": _cell(peaks, "solar_load_share_peak"),
        "coverage_summer_peak": _cell(peaks, "coverage_peak"),
        "coverage_summer_offpeak": _cell(peaks, "coverage_offpeak"),
        "corr_solar_load_summer": _season_cell(corr_season, "summer", "corr_solar_load"),
        "corr_solar_load_winter": _season_cell(corr_season, "winter", "corr_solar_load"),
        "summer_share_same_hour": _cell(coincidence, "share_same_hour"),
        "summer_mean_hour_max_load": _cell(coincidence, "mean_hour_max_load"),
        "summer_mean_hour_max_solar": _cell(coincidence, "mean_hour_max_solar"),
        "summer_median_hour_gap": _cell(coincidence, "median_abs_hour_gap"),
        "coverage_summer_midday": _band_cell(hour_band, "midday", "mean_coverage"),
        "coverage_summer_evening": _band_cell(hour_band, "evening", "mean_coverage"),
        "corr_solar_ssrd": _cell(weather, "corr_solar_ssrd"),
        "corr_solar_ssrd_day": _cell(weather, "corr_solar_ssrd_day"),
        "corr_wind_speed": _cell(weather, "corr_wind_speed"),
        "corr_solar_wind": _cell(comp, "corr_solar_wind"),
        "share_stress": _cell(stress, "share_stress"),
        "coverage_stress": _cell(stress, "mean_coverage_stress"),
        "share_stress_summer": _season_cell(stress_season, "summer", "share_stress"),
        "share_stress_winter": _season_cell(stress_season, "winter", "share_stress"),
    }


def write_analysis_outputs(result: AnalysisResult, output_dir: Path) -> None:
    """Écrit un CSV par table et ``headlines.json``.

    Parameters
    ----------
    result
        Sortie de ``run_analysis``.
    output_dir
        Dossier (créé si besoin).
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in result.tables.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False)
    payload = {key: _json_number(value) for key, value in result.headlines.items()}
    (output_dir / "headlines.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def format_report(result: AnalysisResult) -> str:
    """Résumé texte des 4 questions (sortie CLI).

    Parameters
    ----------
    result
        Indicateurs déjà calculés.

    Returns
    -------
    str
        Texte en français, une section par question.
    """

    h = result.headlines
    return "\n".join(
        [
            "Q1  Couverture Belgique (PV + éolien) / charge",
            f"    moyenne { _pct(h['mean_coverage']) }  "
            f"médiane { _pct(h['median_coverage']) }  "
            f"P10–P90 { _pct(h['p10_coverage']) }–{ _pct(h['p90_coverage']) }",
            f"    été { _pct(h['coverage_summer']) }  "
            f"hiver { _pct(h['coverage_winter']) }",
            f"    un midi d'été (14 h) { _pct(h['coverage_summer_hour_14']) }  "
            f"un soir d'hiver (18 h) { _pct(h['coverage_winter_hour_18']) }",
            "",
            "Q2  Solaire vs pics de charge d'été (P90 de la charge)",
            f"    solaire aux pics { _mw(h['solar_mw_summer_peak']) }  "
            f"hors pics { _mw(h['solar_mw_summer_offpeak']) }",
            f"    couverture aux pics { _pct(h['coverage_summer_peak']) }  "
            f"hors pics { _pct(h['coverage_summer_offpeak']) }",
            f"    corrélation solaire–charge été r={ _r(h['corr_solar_load_summer']) }  "
            f"hiver r={ _r(h['corr_solar_load_winter']) }",
            f"    pic journalier charge ~{ _hour(h['summer_mean_hour_max_load']) }  "
            f"solaire ~{ _hour(h['summer_mean_hour_max_solar']) }  "
            f"(écart médian { _hour(h['summer_median_hour_gap']) })",
            f"    créneau midi { _pct(h['coverage_summer_midday']) }  "
            f"soir { _pct(h['coverage_summer_evening']) }",
            "",
            "Q3  Météo Wallonie (ERA5, moyenne horaire)",
            f"    PV vs rayonnement r={ _r(h['corr_solar_ssrd']) }  "
            f"(jour r={ _r(h['corr_solar_ssrd_day']) })",
            f"    éolien vs vent 10 m r={ _r(h['corr_wind_speed']) }",
            "",
            "Q4  Complémentarité et creux",
            f"    corrélation solaire–éolien r={ _r(h['corr_solar_wind']) }",
            f"    stress (charge P90 et renouvelable P10) : "
            f"{ _pct(h['share_stress']) } des quarts d'heure, "
            f"couverture { _pct(h['coverage_stress']) }",
            f"    stress intra-saison : été { _pct(h['share_stress_summer']) }  "
            f"hiver { _pct(h['share_stress_winter']) }",
        ]
    )


def _join_sql(chunks: list[str]) -> str:
    text = "\n".join(chunks).strip().rstrip(";")
    return text.strip()


def _bound_parameters(sql: str, params: dict[str, float]) -> dict[str, float]:
    # $daytime_ssrd_w_m2 contient un chiffre : le motif doit accepter [0-9].
    used = set(_SQL_PARAM.findall(sql))
    return {name: params[name] for name in used if name in params}


def _cell(frame: pd.DataFrame, column: str, *, how: str = "first") -> float | None:
    if frame.empty or column not in frame.columns:
        return None
    series = frame[column].dropna()
    if series.empty:
        return None
    if how == "min":
        return float(series.min())
    if how == "max":
        return float(series.max())
    return float(series.iloc[0])


def _season_cell(frame: pd.DataFrame, season: str, column: str) -> float | None:
    if frame.empty or "season" not in frame.columns:
        return None
    subset = frame.loc[frame["season"] == season]
    return _cell(subset, column)


def _hour_cell(frame: pd.DataFrame, season: str, hour: int, column: str) -> float | None:
    if frame.empty:
        return None
    subset = frame.loc[(frame["season"] == season) & (frame["hour"] == hour)]
    return _cell(subset, column)


def _band_cell(frame: pd.DataFrame, band: str, column: str) -> float | None:
    if frame.empty or "hour_band" not in frame.columns:
        return None
    subset = frame.loc[frame["hour_band"] == band]
    return _cell(subset, column)


def _json_number(value: float | None) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n.d."
    return f"{100 * value:.1f} %"


def _mw(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n.d."
    return f"{value:.0f} MW"


def _r(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n.d."
    return f"{value:.2f}"


def _hour(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n.d."
    return f"{value:.1f} h"
