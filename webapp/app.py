"""Dashboard Streamlit — couverture renouvelable Belgique / Wallonie."""

from __future__ import annotations

import streamlit as st

from renewables_wallonia.config import ConfigError, load_settings, project_root
from renewables_wallonia.dashboard import (
    CHART_CONFIG,
    DashboardError,
    Recommendation,
    build_recommendation,
    fig_complementarity_corr,
    fig_coverage_heatmap,
    fig_coverage_hourly_lines,
    fig_coverage_ma7,
    fig_mix_by_season,
    fig_solar_vs_ssrd,
    fig_stress_by_hour,
    fig_summer_hour_bands,
    fig_summer_hourly_profiles,
    fig_summer_peak_bars,
    fig_weather_corr_by_season,
    fig_wind_vs_speed,
    format_pct,
    format_period,
    format_r,
    load_dashboard_data,
)

_CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: "Source Sans 3", system-ui, sans-serif;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    max-width: 1180px;
}

#MainMenu, footer, .stDeployButton {visibility: hidden;}

.hero-kicker {
    font-size: 0.78rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #7A7268;
    font-weight: 600;
    margin-bottom: 0.35rem;
}

.hero-title {
    font-size: 2.05rem;
    line-height: 1.2;
    font-weight: 700;
    color: #1C1917;
    margin: 0 0 0.7rem 0;
}

.hero-lead {
    font-size: 1.08rem;
    line-height: 1.5;
    color: #44403C;
    max-width: 46rem;
    margin: 0 0 1.1rem 0;
}

.scope-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
    margin: 0.2rem 0 1.3rem 0;
}

@media (max-width: 900px) {
    .scope-grid { grid-template-columns: 1fr; }
}

.scope-card {
    background: #FFFFFF;
    border: 1px solid #E8E4DC;
    border-radius: 12px;
    padding: 0.85rem 1rem;
}

.scope-card h3 {
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #7A7268;
    margin: 0 0 0.35rem 0;
    font-weight: 600;
}

.scope-card p {
    margin: 0;
    color: #1C1917;
    font-size: 0.95rem;
    line-height: 1.4;
}

.reco-box {
    background: linear-gradient(180deg, #F3F7F4 0%, #EEF4F0 100%);
    border: 1px solid #C5D8CC;
    border-left: 5px solid #2C6A4A;
    border-radius: 12px;
    padding: 1.05rem 1.2rem 1.1rem 1.2rem;
    margin: 0.85rem 0 0.4rem 0;
}

.reco-kicker {
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #2C6A4A;
    font-weight: 700;
    margin-bottom: 0.25rem;
}

.reco-title {
    font-size: 1.18rem;
    font-weight: 700;
    color: #1C1917;
    margin: 0 0 0.45rem 0;
    line-height: 1.35;
}

.reco-body {
    color: #44403C;
    font-size: 0.98rem;
    line-height: 1.5;
    margin: 0;
}

.insight {
    background: #FFFFFF;
    border: 1px solid #E8E4DC;
    border-radius: 12px;
    padding: 0.9rem 1.05rem;
    margin: 0.15rem 0 0.9rem 0;
    font-size: 1.02rem;
    line-height: 1.5;
    color: #1C1917;
}

.chart-note {
    color: #7A7268;
    font-size: 0.86rem;
    margin-top: -0.35rem;
    margin-bottom: 1.05rem;
}

div[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E8E4DC;
    border-radius: 12px;
    padding: 0.75rem 0.95rem;
}

div[data-testid="stMetric"] label {
    color: #7A7268;
}

.footer-note {
    color: #7A7268;
    font-size: 0.82rem;
    margin-top: 1.6rem;
}
</style>
"""

st.set_page_config(
    page_title="Couverture renouvelable — Belgique",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner="Chargement des résultats d'analyse…")
def _cached_load():
    settings = load_settings()
    return load_dashboard_data(settings, project_root())


def _chart(fig) -> None:
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


def _insight(text: str) -> None:
    st.markdown(f'<div class="insight">{text}</div>', unsafe_allow_html=True)


def _note(text: str) -> None:
    st.markdown(f'<p class="chart-note">{text}</p>', unsafe_allow_html=True)


def _render_header(
    reco: Recommendation, headlines: dict, period: str
) -> None:
    st.markdown(
        f"""
        <p class="hero-kicker">Belgique · solaire + éolien · {period}</p>
        <h1 class="hero-title">Le solaire et l'éolien couvrent-ils
        la demande belge aux heures tendues&nbsp;?</h1>
        <p class="hero-lead">
        La question n'est pas « combien produit-on en moyenne », mais
        <strong>quand</strong> cette production arrive — et si elle est là
        au moment où le réseau en a le plus besoin.
        </p>
        <div class="scope-grid">
          <div class="scope-card">
            <h3>Ce qu'on mesure</h3>
            <p>Couverture = (PV + éolien) / charge, à chaque quart d'heure
            belge. Ce n'est pas un mix annuel : c'est une photographie horaire.</p>
          </div>
          <div class="scope-card">
            <h3>Pourquoi la Belgique</h3>
            <p>La charge Elia n'existe qu'au niveau national. La Wallonie
            entre ensuite, pour relier production locale et météo ERA5.</p>
          </div>
          <div class="scope-card">
            <h3>Période</h3>
            <p>{period}. Trois années civiles, quarts d'heure Elia
            et heures ERA5, même fuseau Europe/Brussels.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Couverture moyenne",
        format_pct(headlines.get("mean_coverage")),
        help="Tous les quarts d'heure belges de la période.",
    )
    k2.metric(
        "Midi d'été (14 h)",
        format_pct(headlines.get("coverage_summer_hour_14")),
        help="Heure la plus généreuse du mix.",
    )
    k3.metric(
        "Soir d'hiver (18 h)",
        format_pct(headlines.get("coverage_winter_hour_18")),
        help="Heure la plus tendue du mix.",
    )
    k4.metric(
        "Quarts en stress",
        format_pct(headlines.get("share_stress")),
        help="Charge au-dessus du 90e percentile et renouvelable au-dessous du 10e.",
    )

    st.markdown(
        f"""
        <div class="reco-box">
          <div class="reco-kicker">Recommandation</div>
          <p class="reco-title">{reco.title}</p>
          <p class="reco-body"><strong>{reco.action}</strong><br><br>{reco.lead}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for bullet in reco.bullets:
        st.markdown(f"- {bullet}")
    st.caption(
        "Hors périmètre : stockage, imports, autres filières. "
        "Les seuils P90/P10 sont des conventions d'analyse, pas des seuils Elia."
    )


def _tab_q1(tables: dict, headlines: dict) -> None:
    _insight(
        f"L'hiver à 18 h, solaire + éolien ne couvrent plus que "
        f"<strong>{format_pct(headlines.get('coverage_winter_hour_18'))}</strong> "
        f"de la charge belge. Le midi d'été grimpe à "
        f"<strong>{format_pct(headlines.get('coverage_summer_hour_14'))}</strong> "
        f"— l'écart saisonnier n'est pas un détail, c'est le cœur du problème."
    )
    _chart(fig_coverage_heatmap(tables["coverage_by_hour_season"]))
    _note(
        "Chaque case est une moyenne sur trois ans. Vert = le renouvelable "
        "tient une part confortable. Rouge-beige = le réseau s'appuie ailleurs."
    )
    _chart(fig_coverage_hourly_lines(tables["coverage_by_hour_season"]))
    _note(
        "La bande 16–19 h est l'heure de pointe du soir : c'est là que "
        "l'hiver décroche, pas à midi."
    )
    _chart(fig_coverage_ma7(tables["coverage_daily_ma7"]))
    _note("Moyenne mobile 7 jours : le rythme saisonnier, sans le bruit quotidien.")


def _tab_q2(tables: dict, headlines: dict) -> None:
    _insight(
        f"Les pics de charge d'été tombent en fin d'après-midi, pas à midi. "
        f"Entre 11 et 15 h on couvre encore "
        f"<strong>{format_pct(headlines.get('coverage_summer_midday'))}</strong> ; "
        f"entre 17 et 20 h, plus que "
        f"<strong>{format_pct(headlines.get('coverage_summer_evening'))}</strong>. "
        f"Le PV arrive trop tôt pour ces pics."
    )
    left, right = st.columns((1.05, 1))
    with left:
        _chart(fig_summer_hourly_profiles(tables["coverage_by_hour_season"]))
        _note(
            "Aires empilées = PV + éolien. Ligne = charge. "
            "L'écart, c'est le reste à couvrir."
        )
    with right:
        _chart(fig_summer_hour_bands(tables["summer_hour_band"]))
        _note("Même journée d'été, deux mondes : midi généreux, soir déjà à court.")
    _chart(fig_summer_peak_bars(tables["summer_peaks"]))
    _note(
        f"Aux 10 % d'heures les plus chargées de l'été, le solaire est "
        f"nettement plus haut qu'hors pic. Couverture aux pics : "
        f"{format_pct(headlines.get('coverage_summer_peak'))} "
        f"(hors pics {format_pct(headlines.get('coverage_summer_offpeak'))}). "
        f"Corrélation solaire–charge en été : r = "
        f"{format_r(headlines.get('corr_solar_load_summer'))}."
    )


def _tab_q3(tables: dict, headlines: dict, weather_hourly) -> None:
    _insight(
        "En Wallonie, le lien météo–production est net : le PV suit le "
        "rayonnement, l'éolien suit le vent. Ce n'est pas une coïncidence "
        "statistique — c'est la physique du gisement."
    )
    _chart(fig_weather_corr_by_season(tables["wallonia_weather_by_season"]))
    _note(
        f"Sur toute la période : PV vs rayonnement r = "
        f"{format_r(headlines.get('corr_solar_ssrd'))} "
        f"(heures de jour {format_r(headlines.get('corr_solar_ssrd_day'))}) ; "
        f"éolien vs vent 10 m r = {format_r(headlines.get('corr_wind_speed'))}. "
        "Diagnostic de sensibilité, pas un modèle de prévision."
    )
    if weather_hourly is None or weather_hourly.empty:
        st.info(
            "Nuages de densité indisponibles (entrepôt DuckDB absent). "
            "Les corrélations ci-dessus suffisent pour cette question."
        )
        return
    col_a, col_b = st.columns(2)
    with col_a:
        _chart(fig_solar_vs_ssrd(weather_hourly))
        _note("Chaque point = une heure. Plus le ciel est clair, plus le PV wallon produit.")
    with col_b:
        _chart(fig_wind_vs_speed(weather_hourly))
        _note("Même lecture pour l'éolien : le vent à 10 m explique déjà une grande part.")


def _tab_q4(tables: dict, headlines: dict) -> None:
    _insight(
        "PV et éolien ne se substituent pas heure par heure : leur corrélation "
        "horaire est quasi nulle, voire légèrement négative. En revanche, "
        "l'hiver le vent pèse plus, l'été le solaire — une complémentarité "
        "<em>saisonnière</em>, pas un relais intra-journalier."
    )
    left, right = st.columns(2)
    with left:
        _chart(fig_mix_by_season(tables["complementarity_by_season"]))
        _note("Part moyenne du mix renouvelable : l'éolien domine l'hiver, le solaire l'été.")
    with right:
        _chart(fig_complementarity_corr(tables["complementarity_by_season"]))
        _note(
            f"Corrélation horaire PV × éolien, Belgique entière : "
            f"r = {format_r(headlines.get('corr_solar_wind'))}."
        )
    _chart(fig_stress_by_hour(tables["stress_by_hour"]))
    _note(
        f"Les quarts d'heure « stress » (charge haute, renouvelable bas) "
        f"représentent {format_pct(headlines.get('share_stress'))} de la période "
        f"et se concentrent entre 16 et 19 h — le créneau à flexibilité, pas à PV. "
        f"En hiver {format_pct(headlines.get('share_stress_winter'))} ; "
        f"en été {format_pct(headlines.get('share_stress_summer'))}."
    )


def _sidebar(tables: dict, period: str) -> None:
    overall = tables["coverage_overall"].iloc[0]
    st.header("Méthode")
    st.markdown(
        f"""
**Période**  
{period}

**Couverture belge**  
`(solaire + éolien) / charge` à chaque quart d'heure Elia.

**Stress**  
Couverture au croisement charge P90 et renouvelable P10.

**Météo Wallonie**  
Production régionale × ERA5 (rayonnement, vent 10 m),
agrégation horaire, même fuseau.

**Hors périmètre**  
Pas de stockage, pas d'imports, pas d'autre filière.
Le « reste à couvrir » n'est pas un trou du réseau :
c'est ce que PV + éolien ne portent pas.
        """
    )
    st.divider()
    n_qh = int(overall["n_qh"])
    st.caption(f"{n_qh:,} quarts d'heure".replace(",", " "))
    st.caption("Sources : Elia Open Data · Copernicus ERA5")


def main() -> None:
    """Affiche le bandeau éditorial, puis un onglet par question métier."""

    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)

    try:
        data = _cached_load()
    except (DashboardError, ConfigError) as exc:
        st.error(str(exc))
        st.stop()

    headlines = data.headlines
    tables = data.tables
    reco = build_recommendation(tables, headlines)
    period = format_period(data.period_start, data.period_end)

    with st.sidebar:
        _sidebar(tables, period)

    _render_header(reco, headlines, period)

    tab_q1, tab_q2, tab_q3, tab_q4 = st.tabs(
        [
            "1 · Heures tendues",
            "2 · Pics d'été",
            "3 · Météo Wallonie",
            "4 · Complémentarité",
        ]
    )
    with tab_q1:
        _tab_q1(tables, headlines)
    with tab_q2:
        _tab_q2(tables, headlines)
    with tab_q3:
        _tab_q3(tables, headlines, data.weather_hourly)
    with tab_q4:
        _tab_q4(tables, headlines)

    st.markdown(
        '<p class="footer-note">Lecture d\'un décideur énergie, pas d\'un mix annuel. '
        "Les graphiques sont des moyennes 2023–2026 : ils décrivent un régime, "
        "pas un jour particulier.</p>",
        unsafe_allow_html=True,
    )


main()
