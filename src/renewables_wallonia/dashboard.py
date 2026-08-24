"""Données, recommandation et figures Plotly du dashboard Streamlit."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from renewables_wallonia.analysis import AnalysisError, build_headlines, run_analysis
from renewables_wallonia.config import Settings
from renewables_wallonia.data.warehouse import WarehouseError, open_warehouse

logger = logging.getLogger(__name__)

SEASON_ORDER = ("winter", "spring", "summer", "autumn")
SEASON_LABELS = {
    "winter": "Hiver",
    "spring": "Printemps",
    "summer": "Été",
    "autumn": "Automne",
}
BAND_LABELS = {
    "midday": "Midi (11–15 h)",
    "evening": "Soir (17–20 h)",
    "other": "Reste de la journée",
}
BAND_ORDER = ("Midi (11–15 h)", "Soir (17–20 h)", "Reste de la journée")

SOLAR = "#E8A317"
WIND = "#2E86AB"
LOAD = "#4A4A4A"
COVERAGE = "#1B7F4E"
STRESS = "#C0392B"
MUTED = "#B7C4B7"

REQUIRED_TABLES = (
    "coverage_overall",
    "coverage_by_season",
    "coverage_by_hour_season",
    "coverage_daily_ma7",
    "summer_peaks",
    "summer_hour_band",
    "solar_load_corr_by_season",
    "wallonia_weather",
    "wallonia_weather_by_season",
    "complementarity_overall",
    "complementarity_by_season",
    "stress_overall",
    "stress_by_season",
    "stress_by_hour",
)

_WALLONIA_HOURLY_SQL = """
WITH solar AS (
    SELECT
        date_trunc('hour', datetime_utc) AS hour_utc,
        AVG(measured_mw) AS solar_mw
    FROM fact_generation
    WHERE region = 'Wallonia' AND source = 'solar'
    GROUP BY 1
),
wind AS (
    SELECT
        date_trunc('hour', datetime_utc) AS hour_utc,
        AVG(measured_mw) AS wind_mw
    FROM fact_generation
    WHERE region = 'Wallonia' AND source = 'wind'
    GROUP BY 1
)
SELECT
    d.season,
    s.solar_mw,
    wi.wind_mw,
    w.ssrd_w_m2,
    w.wind_speed_ms
FROM fact_weather AS w
JOIN dim_datetime AS d ON d.datetime_utc = w.datetime_utc
JOIN solar AS s ON s.hour_utc = w.datetime_utc
JOIN wind AS wi ON wi.hour_utc = w.datetime_utc
WHERE w.region = 'Wallonia'
"""

WINTER_EVENING_HOURS = range(16, 20)


class DashboardError(RuntimeError):
    """Tables d'analyse absentes, incomplètes ou illisibles."""


@dataclass(frozen=True)
class Recommendation:
    """Recommandation métier chiffrée pour le bandeau du dashboard."""

    title: str
    lead: str
    bullets: tuple[str, ...]
    action: str
    winter_evening_coverage: float
    summer_midday_coverage: float
    share_stress: float
    coverage_stress: float
    share_stress_in_evening: float
    corr_solar_wind: float


@dataclass(frozen=True)
class DashboardData:
    """Paquet lu par l'app Streamlit (tables CSV plus nuage ERA5 optionnel)."""

    tables: dict[str, pd.DataFrame]
    headlines: dict[str, float | None]
    weather_hourly: pd.DataFrame | None
    period_start: date
    period_end: date


def load_dashboard_data(
    settings: Settings,
    root: Path,
    *,
    with_weather_hourly: bool = True,
) -> DashboardData:
    """Charge les sorties d'analyse, avec repli sur l'entrepôt DuckDB.

    Parameters
    ----------
    settings, root
        Chemins ``analysis_dir`` et entrepôt.
    with_weather_hourly
        Si vrai, tente un nuage horaire Wallonie (entrepôt requis).

    Returns
    -------
    DashboardData
        Tables, indicateurs, nuage optionnel, bornes de période.

    Raises
    ------
    DashboardError
        Ni CSV d'analyse ni entrepôt exploitable.
    """

    analysis_dir = root / settings.paths.analysis_dir
    try:
        tables = load_analysis_tables(analysis_dir)
        headlines = load_headlines(analysis_dir, tables)
    except DashboardError:
        try:
            result = run_analysis(settings, root, write=False)
        except AnalysisError as exc:
            raise DashboardError(
                "Ni tables d'analyse ni entrepôt utilisable. "
                "Lance `python -m renewables_wallonia.cli build-warehouse` "
                "puis `analyze`. "
                f"Détail : {exc}"
            ) from exc
        tables = {name: _normalize_table(frame) for name, frame in result.tables.items()}
        headlines = result.headlines

    weather_hourly = None
    if with_weather_hourly:
        weather_hourly = try_load_wallonia_hourly(settings, root)

    return DashboardData(
        tables=tables,
        headlines=headlines,
        weather_hourly=weather_hourly,
        period_start=settings.period.start,
        period_end=settings.period.end,
    )


def load_analysis_tables(analysis_dir: Path) -> dict[str, pd.DataFrame]:
    """Lit les CSV nommés produits par ``analyze``.

    Parameters
    ----------
    analysis_dir
        Dossier ``data/processed/analysis``.

    Returns
    -------
    dict of DataFrame
        Une table par fichier requis.

    Raises
    ------
    DashboardError
        Dossier absent ou table manquante.
    """

    if not analysis_dir.is_dir():
        raise DashboardError(
            f"dossier d'analyse introuvable : {analysis_dir} "
            "(lance `python -m renewables_wallonia.cli analyze`)"
        )

    tables: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for name in REQUIRED_TABLES:
        path = analysis_dir / f"{name}.csv"
        if not path.is_file():
            missing.append(name)
            continue
        tables[name] = _normalize_table(pd.read_csv(path))
    if missing:
        raise DashboardError(
            "tables manquantes dans "
            f"{analysis_dir} : {', '.join(missing)} "
            "(lance `python -m renewables_wallonia.cli analyze`)"
        )
    return tables


def load_headlines(
    analysis_dir: Path, tables: dict[str, pd.DataFrame]
) -> dict[str, float | None]:
    """Lit ``headlines.json``, ou le reconstruit depuis les tables.

    Parameters
    ----------
    analysis_dir
        Dossier d'analyse.
    tables
        Tables déjà chargées (repli).

    Returns
    -------
    dict
        Indicateurs scalaires (ratios 0-1).
    """

    path = analysis_dir / "headlines.json"
    if not path.is_file():
        return build_headlines(tables)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(key): None if value is None else float(value)
        for key, value in payload.items()
    }


def try_load_wallonia_hourly(settings: Settings, root: Path) -> pd.DataFrame | None:
    """Série horaire Wallonie x ERA5 pour les nuages de densité.

    Parameters
    ----------
    settings, root
        Entrepôt DuckDB.

    Returns
    -------
    DataFrame or None
        ``None`` si l'entrepôt est absent ou la requête échoue.
    """

    try:
        connection = open_warehouse(settings, root, read_only=True)
    except WarehouseError:
        return None
    try:
        return connection.execute(_WALLONIA_HOURLY_SQL).df()
    except Exception:
        logger.warning("nuage météo Wallonie indisponible", exc_info=True)
        return None
    finally:
        connection.close()


def build_recommendation(
    tables: dict[str, pd.DataFrame],
    headlines: dict[str, float | None],
) -> Recommendation:
    """Formule la reco : flex sur 16-19 h l'hiver, pas du PV pour les pics d'été.

    Parameters
    ----------
    tables, headlines
        Sorties d'analyse.

    Returns
    -------
    Recommendation
        Textes et scalaires pour le bandeau.
    """

    by_hour = tables["coverage_by_hour_season"]
    winter_evening = _band_mean(by_hour, "winter", WINTER_EVENING_HOURS)
    summer_midday = headlines.get("coverage_summer_hour_14")
    if summer_midday is None:
        summer_midday = _band_mean(by_hour, "summer", (14,))

    stress_hour = tables["stress_by_hour"]
    evening_mask = stress_hour["hour"].isin(list(WINTER_EVENING_HOURS))
    n_evening = float(stress_hour.loc[evening_mask, "n_stress"].sum())
    n_total = float(stress_hour["n_stress"].sum())
    share_evening = (n_evening / n_total) if n_total else 0.0

    mean_cov = headlines.get("mean_coverage")
    cov_peak = headlines.get("coverage_summer_peak")
    share_stress = headlines.get("share_stress")
    coverage_stress = headlines.get("coverage_stress")
    corr = headlines.get("corr_solar_wind")
    solar_peak = headlines.get("solar_mw_summer_peak")
    solar_off = headlines.get("solar_mw_summer_offpeak")
    ratio = None
    if solar_peak is not None and solar_off not in (None, 0):
        ratio = solar_peak / solar_off

    ratio_txt = ""
    if ratio is not None:
        ratio_txt = f", soit {format_number(ratio, 1)} fois plus de PV qu'hors pic"

    lead = (
        f"Solaire et éolien couvrent en moyenne {format_pct(mean_cov)} de la "
        f"charge belge. Le solaire suit déjà les pics de midi en été "
        f"({format_pct(summer_midday)} à 14 h, {format_pct(cov_peak)} aux "
        f"10 % d'heures les plus chargées{ratio_txt}). Le trou opérationnel "
        f"est le créneau 16-19 h en hiver (couverture {format_pct(winter_evening)})."
    )
    bullets = (
        (
            f"Les heures de stress (charge P90 et renouvelable P10) sont rares "
            f"({format_pct(share_stress)} des quarts d'heure) mais sévères "
            f"(couverture {format_pct(coverage_stress)}) ; "
            f"{format_pct(share_evening, 0)} d'entre elles tombent entre 16 h et 19 h."
        ),
        (
            f"La complémentarité PV/éolien reste faible (r = {format_r(corr)}) : "
            f"l'éolien ne comble pas le soir d'hiver."
        ),
        (
            "En été, ce croisement charge haute / renouvelable bas n'apparait pas : "
            "ajouter du PV pour les pointes de midi n'est pas le levier prioritaire."
        ),
    )
    action = (
        "Prioriser le flex (demande, stockage, import) et la capacité disponible "
        "sur le créneau hivernal 16-19 h, plutôt qu'un surplus de solaire pour "
        "les pics d'été."
    )
    return Recommendation(
        title="Traiter le soir d'hiver, pas le midi d'été",
        lead=lead,
        bullets=bullets,
        action=action,
        winter_evening_coverage=winter_evening,
        summer_midday_coverage=_finite(summer_midday),
        share_stress=_finite(share_stress),
        coverage_stress=_finite(coverage_stress),
        share_stress_in_evening=share_evening,
        corr_solar_wind=_finite(corr),
    )


def format_pct(value: float | None, digits: int = 1) -> str:
    """Pourcentage à virgule française, ou ``n.d.``."""

    if value is None or pd.isna(value):
        return "n.d."
    return f"{format_number(100 * value, digits)} %"


def format_r(value: float | None) -> str:
    """Corrélation arrondie, ou ``n.d.``."""

    if value is None or pd.isna(value):
        return "n.d."
    return format_number(value, 2)


def format_mw(value: float | None) -> str:
    """Puissance en MW, ou ``n.d.``."""

    if value is None or pd.isna(value):
        return "n.d."
    integer = f"{value:,.0f}".replace(",", " ")
    return f"{integer} MW"


def format_number(value: float, digits: int) -> str:
    """Nombre avec virgule décimale française."""

    return f"{value:.{digits}f}".replace(".", ",")


def fig_coverage_heatmap(by_hour: pd.DataFrame) -> go.Figure:
    """Carte heure x saison du taux de couverture belge."""

    pivot = (
        by_hour.pivot_table(
            index="season", columns="hour", values="mean_coverage", aggfunc="mean"
        )
        .reindex(index=list(SEASON_ORDER))
        .reindex(columns=list(range(24)))
        .dropna(how="all")
    )
    z_values = pivot.to_numpy(dtype=float) * 100.0
    y_labels = [SEASON_LABELS.get(str(idx), str(idx)) for idx in pivot.index]
    fig = px.imshow(
        z_values,
        x=list(pivot.columns),
        y=y_labels,
        color_continuous_scale="YlGn",
        aspect="auto",
        origin="upper",
        labels={"color": "Couverture (%)"},
        title="Couverture moyenne (PV + éolien) / charge, par heure et saison",
    )
    fig.update_traces(hovertemplate="%{y} · %{x} h<br>%{z:.1f} %<extra></extra>")
    fig.update_xaxes(title="Heure (Bruxelles)", dtick=2)
    fig.update_yaxes(title="")
    return _style(fig, height=380)


def fig_coverage_ma7(daily: pd.DataFrame) -> go.Figure:
    """Couverture journalière et moyenne mobile 7 jours."""

    frame = daily.sort_values("date_brussels")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=frame["date_brussels"],
            y=frame["coverage"],
            name="Journalière",
            line=dict(color=MUTED, width=1),
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1%}<extra>Journalière</extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=frame["date_brussels"],
            y=frame["coverage_ma7"],
            name="Moyenne mobile 7 jours",
            line=dict(color=COVERAGE, width=2.2),
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1%}<extra>MA7</extra>",
        )
    )
    fig.update_yaxes(title="Couverture", tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(title="")
    fig.update_layout(title="Couverture journalière belge (moyenne mobile 7 jours)")
    return _style(fig)


def fig_summer_peak_bars(peaks: pd.DataFrame) -> go.Figure:
    """Solaire et éolien aux pics de charge d'été vs hors pics."""

    row = peaks.iloc[0]
    frame = pd.DataFrame(
        {
            "période": ["Pics de charge (P90)", "Hors pics"] * 2,
            "filière": ["Solaire", "Solaire", "Éolien", "Éolien"],
            "MW": [
                row["solar_mw_peak"],
                row["solar_mw_offpeak"],
                row["wind_mw_peak"],
                row["wind_mw_offpeak"],
            ],
        }
    )
    fig = px.bar(
        frame,
        x="période",
        y="MW",
        color="filière",
        barmode="group",
        color_discrete_map={"Solaire": SOLAR, "Éolien": WIND},
        title="Production moyenne aux pics d'été (P90 de la charge) vs hors pics",
    )
    fig.update_traces(hovertemplate="%{x}<br>%{legendgroup} : %{y:.0f} MW<extra></extra>")
    fig.update_yaxes(title="MW")
    fig.update_xaxes(title="")
    return _style(fig, height=380)


def fig_summer_hourly_profiles(by_hour: pd.DataFrame) -> go.Figure:
    """Profils moyens d'été : charge, solaire, éolien."""

    summer = by_hour.loc[by_hour["season"] == "summer"].sort_values("hour")
    fig = go.Figure()
    fig.add_vrect(
        x0=10.5,
        x1=15.5,
        fillcolor=SOLAR,
        opacity=0.12,
        line_width=0,
        annotation_text="midi",
        annotation_position="top left",
    )
    fig.add_vrect(
        x0=16.5,
        x1=20.5,
        fillcolor=STRESS,
        opacity=0.10,
        line_width=0,
        annotation_text="soir",
        annotation_position="top right",
    )
    fig.add_trace(
        go.Scatter(
            x=summer["hour"],
            y=summer["mean_load_mw"],
            name="Charge",
            line=dict(color=LOAD, width=2.4),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=summer["hour"],
            y=summer["mean_solar_mw"],
            name="Solaire",
            line=dict(color=SOLAR, width=2.2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=summer["hour"],
            y=summer["mean_wind_mw"],
            name="Éolien",
            line=dict(color=WIND, width=2.2),
        )
    )
    fig.update_xaxes(title="Heure (Bruxelles)", dtick=2)
    fig.update_yaxes(title="MW")
    fig.update_layout(title="Profils moyens d'été en Belgique")
    fig.update_traces(hovertemplate="%{x} h<br>%{y:.0f} MW<extra>%{fullData.name}</extra>")
    return _style(fig)


def fig_summer_hour_bands(bands: pd.DataFrame) -> go.Figure:
    """Couverture d'été : midi vs soir vs reste."""

    frame = bands.copy()
    frame["creneau"] = frame["hour_band"].map(BAND_LABELS).fillna(frame["hour_band"])
    frame["creneau"] = pd.Categorical(
        frame["creneau"], categories=list(BAND_ORDER), ordered=True
    )
    frame = frame.sort_values("creneau")
    color_map = {
        "Midi (11–15 h)": SOLAR,
        "Soir (17–20 h)": STRESS,
        "Reste de la journée": MUTED,
    }
    colors = [color_map.get(str(label), MUTED) for label in frame["creneau"]]
    fig = px.bar(
        frame,
        x="creneau",
        y="mean_coverage",
        title="Couverture d'été selon le créneau horaire",
    )
    fig.update_traces(
        marker_color=colors,
        hovertemplate="%{x}<br>%{y:.1%}<extra></extra>",
    )
    fig.update_yaxes(title="Couverture", tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(title="")
    return _style(fig, height=360)


def fig_weather_corr_by_season(by_season: pd.DataFrame) -> go.Figure:
    """Corrélations Wallonie x ERA5 par saison."""

    frame = _with_season_label(by_season)
    long = frame.melt(
        id_vars=["saison"],
        value_vars=["corr_solar_ssrd", "corr_wind_speed"],
        var_name="paire",
        value_name="r",
    )
    long["paire"] = long["paire"].map(
        {
            "corr_solar_ssrd": "PV vs rayonnement",
            "corr_wind_speed": "Éolien vs vent 10 m",
        }
    )
    fig = px.bar(
        long,
        x="saison",
        y="r",
        color="paire",
        barmode="group",
        color_discrete_map={
            "PV vs rayonnement": SOLAR,
            "Éolien vs vent 10 m": WIND,
        },
        title="Corrélation production wallonne x météo ERA5",
    )
    fig.update_yaxes(title="r de Pearson", range=[0, 1])
    fig.update_xaxes(title="")
    fig.update_traces(hovertemplate="%{x}<br>%{legendgroup} : r = %{y:.2f}<extra></extra>")
    return _style(fig, height=380)


def fig_solar_vs_ssrd(hourly: pd.DataFrame) -> go.Figure:
    """Densité PV wallon vs rayonnement."""

    fig = px.density_heatmap(
        hourly,
        x="ssrd_w_m2",
        y="solar_mw",
        nbinsx=40,
        nbinsy=40,
        color_continuous_scale="YlOrRd",
        labels={
            "ssrd_w_m2": "Rayonnement ERA5 (W/m²)",
            "solar_mw": "PV wallon (MW)",
        },
        title="PV wallon vs rayonnement descendant (densité horaire)",
    )
    return _style(fig, height=400)


def fig_wind_vs_speed(hourly: pd.DataFrame) -> go.Figure:
    """Densité éolien wallon vs vent à 10 m."""

    fig = px.density_heatmap(
        hourly,
        x="wind_speed_ms",
        y="wind_mw",
        nbinsx=40,
        nbinsy=40,
        color_continuous_scale="Blues",
        labels={
            "wind_speed_ms": "Vent ERA5 à 10 m (m/s)",
            "wind_mw": "Éolien wallon (MW)",
        },
        title="Éolien wallon vs vent à 10 m (densité horaire)",
    )
    return _style(fig, height=400)


def fig_mix_by_season(by_season: pd.DataFrame) -> go.Figure:
    """Part solaire / éolien du renouvelable belge, par saison."""

    frame = _with_season_label(by_season)
    long = frame.melt(
        id_vars=["saison"],
        value_vars=["solar_share_of_renewable", "wind_share_of_renewable"],
        var_name="filiere",
        value_name="part",
    )
    long["filiere"] = long["filiere"].map(
        {
            "solar_share_of_renewable": "Solaire",
            "wind_share_of_renewable": "Éolien",
        }
    )
    fig = px.bar(
        long,
        x="saison",
        y="part",
        color="filiere",
        barmode="stack",
        color_discrete_map={"Solaire": SOLAR, "Éolien": WIND},
        title="Mix renouvelable belge : part solaire vs éolien",
    )
    fig.update_yaxes(title="Part du renouvelable", tickformat=".0%", range=[0, 1])
    fig.update_xaxes(title="")
    fig.update_traces(hovertemplate="%{x}<br>%{legendgroup} : %{y:.0%}<extra></extra>")
    return _style(fig, height=380)


def fig_stress_by_hour(stress: pd.DataFrame) -> go.Figure:
    """Nombre de quarts d'heure de stress par heure de la journée."""

    frame = stress.sort_values("hour")
    fig = go.Figure()
    fig.add_vrect(
        x0=15.5,
        x1=19.5,
        fillcolor=STRESS,
        opacity=0.12,
        line_width=0,
        annotation_text="16-19 h",
        annotation_position="top left",
    )
    fig.add_trace(
        go.Bar(
            x=frame["hour"],
            y=frame["n_stress"],
            marker_color=STRESS,
            name="Quarts d'heure de stress",
            hovertemplate="%{x} h<br>%{y:.0f} QH<extra></extra>",
        )
    )
    fig.update_xaxes(title="Heure (Bruxelles)", dtick=1)
    fig.update_yaxes(title="Nombre de quarts d'heure")
    fig.update_layout(
        title="Heures tendues : charge haute (P90) et renouvelable bas (P10)"
    )
    return _style(fig)


def _style(fig: go.Figure, *, height: int = 420) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=48, r=28, t=60, b=44),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        font=dict(size=13, color="#1A1A1A"),
        title=dict(font=dict(size=16)),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return fig


def _with_season_label(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["saison"] = out["season"].map(SEASON_LABELS).fillna(out["season"])
    labels = [SEASON_LABELS[name] for name in SEASON_ORDER]
    present = [label for label in labels if label in set(out["saison"].astype(str))]
    out["saison"] = pd.Categorical(out["saison"], categories=present, ordered=True)
    return out.sort_values("saison")


def _normalize_table(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if "hour" in out.columns:
        out["hour"] = out["hour"].astype(int)
    if "date_brussels" in out.columns:
        out["date_brussels"] = pd.to_datetime(out["date_brussels"])
    return out


def _band_mean(
    by_hour: pd.DataFrame, season: str, hours: range | tuple[int, ...]
) -> float:
    hour_set = set(hours)
    subset = by_hour.loc[
        (by_hour["season"] == season) & (by_hour["hour"].isin(hour_set)),
        "mean_coverage",
    ]
    if subset.empty:
        return float("nan")
    return float(subset.mean())


def _finite(value: float | None) -> float:
    if value is None or pd.isna(value):
        return float("nan")
    return float(value)

