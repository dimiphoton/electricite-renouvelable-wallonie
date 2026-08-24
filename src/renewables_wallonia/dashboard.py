"""Données, recommandation et figures Plotly du dashboard Streamlit."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
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
BAND_ORDER = (
    "Midi (11–15 h)",
    "Soir (17–20 h)",
    "Reste de la journée",
)

SOLAR = "#D4922A"
WIND = "#3A7194"
LOAD = "#2A3035"
COVERAGE = "#2C6A4A"
STRESS = "#B03A45"
MUTED = "#C4BDB3"
INK = "#1C1917"
GRID = "#E8E4DC"
PAPER = "#FBF9F6"
SEASON_COLORS = {
    "winter": "#4A6F9A",
    "spring": "#5F8F62",
    "summer": "#D4922A",
    "autumn": "#B56A3A",
}
COVERAGE_SCALE = (
    (0.0, "#F4F0E8"),
    (0.25, "#C9D6B8"),
    (0.55, "#6E9A6A"),
    (1.0, "#1E4A32"),
)
CHART_CONFIG = {"displayModeBar": False, "responsive": True}

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


def format_period(start: date, end: date) -> str:
    """Période en français court, ex. ``sept. 2023 – août 2026``."""

    months = (
        "janv.",
        "févr.",
        "mars",
        "avr.",
        "mai",
        "juin",
        "juil.",
        "août",
        "sept.",
        "oct.",
        "nov.",
        "déc.",
    )
    return f"{months[start.month - 1]} {start.year} – {months[end.month - 1]} {end.year}"


def fig_coverage_heatmap(by_hour: pd.DataFrame) -> go.Figure:
    """Carte heure × saison du taux de couverture belge, avec les deux extrêmes."""

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
    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=list(pivot.columns),
            y=y_labels,
            colorscale=COVERAGE_SCALE,
            zmin=0,
            zmax=max(70.0, float(np.nanmax(z_values))),
            colorbar=dict(
                title=dict(text="Couverture", font=dict(size=11)),
                ticksuffix=" %",
                thickness=12,
                len=0.82,
                outlinewidth=0,
                tickfont=dict(size=11),
            ),
            hovertemplate="%{y} · %{x} h<br><b>%{z:.1f} %</b><extra></extra>",
            xgap=1,
            ygap=1,
        )
    )
    fig.update_xaxes(title="Heure (Bruxelles)", dtick=2, ticksuffix=" h")
    fig.update_yaxes(title="", autorange="reversed")
    _annotate_heatmap_extremes(fig, pivot, y_labels)
    return _style(
        fig,
        height=430,
        title="La couverture n'est pas un socle : midi d'été vs soir d'hiver",
    )


def fig_coverage_hourly_lines(by_hour: pd.DataFrame) -> go.Figure:
    """Profil journalier de couverture, une courbe par saison."""

    fig = go.Figure()
    fig.add_vrect(
        x0=15.5,
        x1=19.5,
        fillcolor=STRESS,
        opacity=0.08,
        line_width=0,
        annotation_text="16–19 h",
        annotation_position="top right",
        annotation_font=dict(size=11, color=STRESS),
    )
    for season in SEASON_ORDER:
        subset = by_hour.loc[by_hour["season"] == season].sort_values("hour")
        if subset.empty:
            continue
        width = 3.1 if season == "winter" else 2.4
        fig.add_trace(
            go.Scatter(
                x=subset["hour"],
                y=subset["mean_coverage"],
                name=SEASON_LABELS[season],
                mode="lines",
                line=dict(color=SEASON_COLORS[season], width=width, shape="spline"),
                hovertemplate=(
                    f"%{{x}} h · {SEASON_LABELS[season]}<br><b>%{{y:.0%}}</b><extra></extra>"
                ),
            )
        )
    _mark_hourly_extremes(fig, by_hour)
    fig.update_xaxes(title="Heure (Bruxelles)", dtick=2, range=[-0.4, 23.4])
    fig.update_yaxes(title="Couverture", tickformat=".0%", rangemode="tozero")
    return _style(
        fig,
        height=400,
        title="Le même trou revient chaque hiver, à la même heure",
    )


def fig_coverage_ma7(daily: pd.DataFrame) -> go.Figure:
    """Couverture journalière et moyenne mobile 7 jours."""

    frame = daily.sort_values("date_brussels")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=frame["date_brussels"],
            y=frame["coverage"],
            name="Jour par jour",
            line=dict(color=MUTED, width=0.7),
            opacity=0.55,
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1%}<extra>Journalière</extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=frame["date_brussels"],
            y=frame["coverage_ma7"],
            name="Moyenne 7 jours",
            line=dict(color=COVERAGE, width=2.6),
            fill="tozeroy",
            fillcolor="rgba(44, 106, 74, 0.12)",
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1%}<extra>MA7</extra>",
        )
    )
    fig.update_yaxes(title="Couverture", tickformat=".0%", rangemode="tozero")
    fig.update_xaxes(title="")
    return _style(
        fig,
        height=360,
        title="Sur trois ans, le mix oscille : ce n'est pas une base ferme",
    )


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
        text_auto=".0f",
    )
    fig.update_traces(
        marker_line_width=0,
        width=0.38,
        hovertemplate="%{x}<br>%{legendgroup} : <b>%{y:.0f} MW</b><extra></extra>",
        textposition="outside",
        cliponaxis=False,
    )
    fig.update_yaxes(title="MW", rangemode="tozero")
    fig.update_xaxes(title="")
    return _style(
        fig,
        height=400,
        title="Aux pics de charge d'été, c'est le solaire qui suit — pas l'éolien",
    )


def fig_summer_hourly_profiles(by_hour: pd.DataFrame) -> go.Figure:
    """Profils moyens d'été : solaire et éolien empilés face à la charge."""

    summer = by_hour.loc[by_hour["season"] == "summer"].sort_values("hour")
    fig = go.Figure()
    fig.add_vrect(
        x0=10.5,
        x1=15.5,
        fillcolor=SOLAR,
        opacity=0.10,
        line_width=0,
        annotation_text="midi",
        annotation_position="top left",
        annotation_font=dict(size=11, color=SOLAR),
    )
    fig.add_vrect(
        x0=16.5,
        x1=20.5,
        fillcolor=STRESS,
        opacity=0.08,
        line_width=0,
        annotation_text="soir",
        annotation_position="top right",
        annotation_font=dict(size=11, color=STRESS),
    )
    fig.add_trace(
        go.Scatter(
            x=summer["hour"],
            y=summer["mean_solar_mw"],
            name="Solaire",
            stackgroup="ren",
            mode="lines",
            line=dict(width=0.5, color=SOLAR, shape="spline"),
            fillcolor="rgba(212, 146, 42, 0.55)",
            hovertemplate="%{x} h<br>Solaire : <b>%{y:.0f} MW</b><extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=summer["hour"],
            y=summer["mean_wind_mw"],
            name="Éolien",
            stackgroup="ren",
            mode="lines",
            line=dict(width=0.5, color=WIND, shape="spline"),
            fillcolor="rgba(58, 113, 148, 0.45)",
            hovertemplate="%{x} h<br>Éolien : <b>%{y:.0f} MW</b><extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=summer["hour"],
            y=summer["mean_load_mw"],
            name="Charge",
            mode="lines",
            line=dict(color=LOAD, width=2.8, shape="spline"),
            hovertemplate="%{x} h<br>Charge : <b>%{y:.0f} MW</b><extra></extra>",
        )
    )
    fig.update_xaxes(title="Heure (Bruxelles)", dtick=2)
    fig.update_yaxes(title="MW", rangemode="tozero")
    return _style(
        fig,
        height=420,
        title="En été, le solaire colle au pic de midi — et s'éteint avant le soir",
    )


def fig_summer_hour_bands(bands: pd.DataFrame) -> go.Figure:
    """Couverture d'été : midi vs soir vs reste."""

    frame = bands.copy()
    frame["creneau"] = frame["hour_band"].map(BAND_LABELS).fillna(frame["hour_band"])
    frame["creneau"] = pd.Categorical(
        frame["creneau"], categories=list(BAND_ORDER), ordered=True
    )
    frame = frame.sort_values("creneau")
    color_map = {
        BAND_LABELS["midday"]: SOLAR,
        BAND_LABELS["evening"]: STRESS,
        BAND_LABELS["other"]: MUTED,
    }
    colors = [color_map.get(str(label), MUTED) for label in frame["creneau"]]
    fig = px.bar(frame, x="creneau", y="mean_coverage", text_auto=".0%")
    fig.update_traces(
        marker_color=colors,
        marker_line_width=0,
        hovertemplate="%{x}<br><b>%{y:.0%}</b><extra></extra>",
        textposition="outside",
        cliponaxis=False,
    )
    fig.update_yaxes(
        title="Couverture", tickformat=".0%", rangemode="tozero", range=[0, 0.75]
    )
    fig.update_xaxes(title="")
    return _style(
        fig,
        height=360,
        title="Midi d'été : 60 % couverts. Début de soirée : plus que 31 %",
    )


def fig_weather_corr_by_season(by_season: pd.DataFrame) -> go.Figure:
    """Corrélations Wallonie × ERA5 par saison."""

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
        title="",
    )
    fig.update_yaxes(title="r de Pearson", range=[0, 1.05])
    fig.update_xaxes(title="")
    fig.update_traces(
        marker_line_width=0,
        hovertemplate="%{x}<br>%{legendgroup} : <b>r = %{y:.2f}</b><extra></extra>",
        texttemplate="%{y:.2f}",
        textposition="outside",
        cliponaxis=False,
        width=0.36,
    )
    return _style(
        fig,
        height=400,
        title="En Wallonie, la météo ERA5 explique déjà l'essentiel de la production",
    )


def fig_solar_vs_ssrd(hourly: pd.DataFrame) -> go.Figure:
    """Densité PV wallon vs rayonnement."""

    fig = px.density_heatmap(
        hourly,
        x="ssrd_w_m2",
        y="solar_mw",
        nbinsx=42,
        nbinsy=42,
        color_continuous_scale=[
            [0.0, "#F7F5F2"],
            [0.35, "#F0D9A8"],
            [0.7, "#D4922A"],
            [1.0, "#8A5A12"],
        ],
        labels={
            "ssrd_w_m2": "Rayonnement ERA5 (W/m²)",
            "solar_mw": "PV wallon (MW)",
        },
    )
    fig.update_coloraxes(colorbar_title_text="Heures")
    return _style(
        fig,
        height=420,
        title="Plus il y a de soleil, plus le PV wallon produit — presque linéairement",
    )


def fig_wind_vs_speed(hourly: pd.DataFrame) -> go.Figure:
    """Densité éolien wallon vs vent à 10 m."""

    fig = px.density_heatmap(
        hourly,
        x="wind_speed_ms",
        y="wind_mw",
        nbinsx=42,
        nbinsy=42,
        color_continuous_scale=[
            [0.0, "#F7F5F2"],
            [0.35, "#B7D0DE"],
            [0.7, "#3A7194"],
            [1.0, "#1C3F56"],
        ],
        labels={
            "wind_speed_ms": "Vent ERA5 à 10 m (m/s)",
            "wind_mw": "Éolien wallon (MW)",
        },
    )
    fig.update_coloraxes(colorbar_title_text="Heures")
    return _style(
        fig,
        height=420,
        title="L'éolien wallon suit le vent — même mesuré à 10 m, pas au moyeu",
    )


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
        title="",
    )
    fig.update_yaxes(title="Part du renouvelable", tickformat=".0%", range=[0, 1.02])
    fig.update_xaxes(title="")
    fig.update_traces(
        marker_line_width=0,
        hovertemplate="%{x}<br>%{legendgroup} : <b>%{y:.0%}</b><extra></extra>",
        texttemplate="%{y:.0%}",
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(size=12, color="#FFFEFB"),
    )
    return _style(
        fig,
        height=380,
        title="L'hiver, l'éolien porte le mix.<br>L'été, le solaire prend le relais — trop tard le soir",
    )


def fig_complementarity_corr(by_season: pd.DataFrame) -> go.Figure:
    """Corrélation horaire solaire × éolien, une barre par saison."""

    frame = _with_season_label(by_season)
    fig = go.Figure(
        go.Bar(
            x=frame["saison"],
            y=frame["corr_solar_wind"],
            marker_color=WIND,
            marker_line_width=0,
            text=[f"{value:.2f}" for value in frame["corr_solar_wind"]],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{x}<br><b>r = %{y:.2f}</b><extra></extra>",
        )
    )
    fig.add_hline(y=0, line_width=1, line_color=INK, opacity=0.45)
    fig.update_yaxes(title="r PV × éolien", range=[-0.45, 0.12], zeroline=False)
    fig.update_xaxes(title="")
    return _style(
        fig,
        height=380,
        title="À l'heure, PV et éolien ne se relaient pas",
        showlegend=False,
    )


def fig_stress_by_hour(stress: pd.DataFrame) -> go.Figure:
    """Nombre de quarts d'heure de stress par heure de la journée."""

    frame = stress.sort_values("hour")
    in_evening = frame["hour"].isin(list(WINTER_EVENING_HOURS))
    colors = [STRESS if flag else MUTED for flag in in_evening]
    fig = go.Figure()
    fig.add_vrect(
        x0=15.5,
        x1=19.5,
        fillcolor=STRESS,
        opacity=0.07,
        line_width=0,
    )
    fig.add_trace(
        go.Bar(
            x=frame["hour"],
            y=frame["n_stress"],
            marker_color=colors,
            marker_line_width=0,
            name="Quarts d'heure de stress",
            hovertemplate="%{x} h<br><b>%{y:.0f}</b> quarts d'heure<extra></extra>",
        )
    )
    fig.update_xaxes(title="Heure (Bruxelles)", dtick=1)
    fig.update_yaxes(title="Quarts d'heure tendus", rangemode="tozero")
    fig.add_annotation(
        x=17.5,
        y=1.0,
        yref="paper",
        text="16–19 h : le gros du stress",
        showarrow=False,
        font=dict(size=11, color=STRESS),
        yanchor="bottom",
    )
    return _style(
        fig,
        height=400,
        title="Les heures vraiment tendues se concentrent en fin d'après-midi",
        showlegend=False,
    )


def _style(
    fig: go.Figure,
    *,
    height: int = 420,
    title: str | None = None,
    showlegend: bool | None = None,
) -> go.Figure:
    layout: dict = {
        "template": "plotly_white",
        "height": height,
        "margin": dict(l=52, r=24, t=72 if title else 48, b=48),
        "legend": dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12),
        ),
        "font": dict(
            family="Source Sans 3, Segoe UI, Helvetica Neue, sans-serif",
            size=13,
            color=INK,
        ),
        "title": dict(
            text=title or fig.layout.title.text,
            font=dict(size=16, color=INK, family="Source Sans 3, Segoe UI, sans-serif"),
            x=0.0,
            xanchor="left",
            pad=dict(b=8),
        ),
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": PAPER,
        "hoverlabel": dict(
            bgcolor="#FFFEFB",
            bordercolor=GRID,
            font=dict(size=12, color=INK),
        ),
        "bargap": 0.28,
        "coloraxis_colorbar": dict(outlinewidth=0, thickness=10, len=0.82),
    }
    if showlegend is not None:
        layout["showlegend"] = showlegend
    fig.update_layout(**layout)
    fig.update_xaxes(
        showgrid=False,
        linecolor=GRID,
        tickcolor=GRID,
        zeroline=False,
        title_font=dict(size=12, color="#57534E"),
        tickfont=dict(size=11, color="#57534E"),
    )
    fig.update_yaxes(
        gridcolor=GRID,
        gridwidth=1,
        zeroline=False,
        linecolor=GRID,
        title_font=dict(size=12, color="#57534E"),
        tickfont=dict(size=11, color="#57534E"),
    )
    return fig


def _annotate_heatmap_extremes(
    fig: go.Figure, pivot: pd.DataFrame, y_labels: list[str]
) -> None:
    """Marque le midi d'été et le soir d'hiver sur la heatmap."""

    mapping = dict(zip(pivot.index.astype(str), y_labels, strict=False))
    spots = (("summer", 14, "Midi d'été"), ("winter", 18, "Soir d'hiver"))
    for season, hour, label in spots:
        if season not in pivot.index or hour not in pivot.columns:
            continue
        value = pivot.loc[season, hour]
        if pd.isna(value):
            continue
        fig.add_annotation(
            x=hour,
            y=mapping.get(season, season),
            text=f"{label}<br>{100 * float(value):.0f} %",
            showarrow=True,
            arrowhead=0,
            arrowwidth=1,
            arrowcolor=INK,
            ax=0,
            ay=-36 if season == "summer" else 36,
            font=dict(size=11, color=INK),
            bgcolor="rgba(255,254,251,0.92)",
            bordercolor=GRID,
            borderwidth=1,
            borderpad=4,
        )


def _mark_hourly_extremes(fig: go.Figure, by_hour: pd.DataFrame) -> None:
    """Pose un point sur le midi d'été et le soir d'hiver."""

    spots = (("summer", 14), ("winter", 18))
    for season, hour in spots:
        subset = by_hour.loc[
            (by_hour["season"] == season) & (by_hour["hour"] == hour),
            "mean_coverage",
        ]
        if subset.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=[hour],
                y=[float(subset.iloc[0])],
                mode="markers",
                marker=dict(size=9, color=SEASON_COLORS[season], line=dict(width=0)),
                showlegend=False,
                hovertemplate=(
                    f"{SEASON_LABELS[season]} · {hour} h<br><b>%{{y:.0%}}</b><extra></extra>"
                ),
            )
        )


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
