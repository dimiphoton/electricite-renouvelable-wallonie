"""Dashboard Streamlit : une visualisation par question métier, plus la reco."""

from __future__ import annotations

import streamlit as st

from renewables_wallonia.config import ConfigError, load_settings, project_root
from renewables_wallonia.dashboard import (
    DashboardError,
    build_recommendation,
    fig_coverage_heatmap,
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
    format_r,
    load_dashboard_data,
)

st.set_page_config(
    page_title="Couverture renouvelable Belgique",
    page_icon="⚡",
    layout="wide",
)


@st.cache_data(show_spinner="Chargement des résultats d'analyse…")
def _cached_load():
    settings = load_settings()
    return load_dashboard_data(settings, project_root())


def main() -> None:
    """Affiche le bandeau de recommandation puis un onglet par question."""

    st.title("Solaire et éolien face à la charge belge")
    st.caption(
        "Couverture nationale (PV + éolien / charge Elia). "
        "Zoom météo : production wallonne × ERA5. Pas de taux de couverture wallon : "
        "la charge Elia n'existe qu'à l'échelle Belgique."
    )

    try:
        data = _cached_load()
    except (DashboardError, ConfigError) as exc:
        st.error(str(exc))
        st.stop()

    headlines = data.headlines
    tables = data.tables
    reco = build_recommendation(tables, headlines)

    st.sidebar.header("Périmètre")
    st.sidebar.markdown(f"**{data.period_start} → {data.period_end}**")
    st.sidebar.markdown("Couverture : **Belgique** (charge nationale Elia).")
    st.sidebar.markdown("Zoom météo : production **Wallonie** × ERA5.")
    st.sidebar.caption(
        "Sources : Elia Open Data (ods001, ods032, ods031) et Copernicus ERA5. "
        "Les seuils P90/P10 sont des conventions d'analyse, pas des seuils réseau Elia."
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Couverture moyenne", format_pct(headlines.get("mean_coverage")))
    k2.metric("Midi d'été (14 h)", format_pct(headlines.get("coverage_summer_hour_14")))
    k3.metric("Soir d'hiver (18 h)", format_pct(headlines.get("coverage_winter_hour_18")))
    k4.metric("Heures de stress", format_pct(headlines.get("share_stress")))

    st.subheader(reco.title)
    st.success(reco.action)
    st.write(reco.lead)
    for bullet in reco.bullets:
        st.markdown(f"- {bullet}")

    tab_q1, tab_q2, tab_q3, tab_q4 = st.tabs(
        [
            "Q1 · Couverture",
            "Q2 · Pics d'été",
            "Q3 · Météo Wallonie",
            "Q4 · Complémentarité",
        ]
    )

    with tab_q1:
        st.markdown(
            "**Question.** Comment le taux de couverture belge (PV + éolien / charge) "
            "varie-t-il selon l'heure et la saison ?"
        )
        st.plotly_chart(
            fig_coverage_heatmap(tables["coverage_by_hour_season"]),
            use_container_width=True,
        )
        st.caption(
            f"Un midi d'été (14 h) atteint {format_pct(headlines.get('coverage_summer_hour_14'))} ; "
            f"un soir d'hiver (18 h) tombe à {format_pct(headlines.get('coverage_winter_hour_18'))}."
        )
        st.plotly_chart(
            fig_coverage_ma7(tables["coverage_daily_ma7"]),
            use_container_width=True,
        )
        st.caption(
            "La moyenne mobile 7 jours oscille fortement : le mix n'est pas un socle stable."
        )

    with tab_q2:
        st.markdown(
            "**Question.** Le solaire coïncide-t-il avec les pics de charge d'été ?"
        )
        st.plotly_chart(
            fig_summer_peak_bars(tables["summer_peaks"]),
            use_container_width=True,
        )
        st.caption(
            f"Oui pour le midi : aux 10 % d'heures les plus chargées, le solaire "
            f"est nettement plus élevé. Couverture aux pics : "
            f"{format_pct(headlines.get('coverage_summer_peak'))} "
            f"(hors pics {format_pct(headlines.get('coverage_summer_offpeak'))}). "
            f"Corrélation solaire–charge en été : r = "
            f"{format_r(headlines.get('corr_solar_load_summer'))}."
        )
        left, right = st.columns(2)
        with left:
            st.plotly_chart(
                fig_summer_hourly_profiles(tables["coverage_by_hour_season"]),
                use_container_width=True,
            )
        with right:
            st.plotly_chart(
                fig_summer_hour_bands(tables["summer_hour_band"]),
                use_container_width=True,
            )
        st.caption(
            f"Le créneau 11–15 h affiche {format_pct(headlines.get('coverage_summer_midday'))} ; "
            f"le 17–20 h seulement {format_pct(headlines.get('coverage_summer_evening'))}. "
            "Le PV aide le pic de midi, pas la pointe de début de soirée."
        )

    with tab_q3:
        st.markdown(
            "**Question.** Quels facteurs météo expliquent le mieux la production wallonne ?"
        )
        st.plotly_chart(
            fig_weather_corr_by_season(tables["wallonia_weather_by_season"]),
            use_container_width=True,
        )
        st.caption(
            f"Sur l'ensemble de la période : PV vs rayonnement r = "
            f"{format_r(headlines.get('corr_solar_ssrd'))} "
            f"(jour {format_r(headlines.get('corr_solar_ssrd_day'))}) ; "
            f"éolien vs vent 10 m r = {format_r(headlines.get('corr_wind_speed'))}. "
            "Diagnostic de sensibilité, pas un modèle de prévision."
        )
        hourly = data.weather_hourly
        if hourly is None or hourly.empty:
            st.info(
                "Nuages de densité indisponibles (entrepôt DuckDB absent). "
                "Les corrélations ci-dessus suffisent pour Q3."
            )
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(fig_solar_vs_ssrd(hourly), use_container_width=True)
            with c2:
                st.plotly_chart(fig_wind_vs_speed(hourly), use_container_width=True)

    with tab_q4:
        st.markdown(
            "**Question.** Solaire et éolien se complètent-ils, et où sont les creux ?"
        )
        st.plotly_chart(
            fig_mix_by_season(tables["complementarity_by_season"]),
            use_container_width=True,
        )
        st.caption(
            f"Complémentarité faible (r = {format_r(headlines.get('corr_solar_wind'))}). "
            "L'éolien pèse surtout l'hiver, le solaire l'été."
        )
        st.plotly_chart(
            fig_stress_by_hour(tables["stress_by_hour"]),
            use_container_width=True,
        )
        st.caption(
            f"Stress (charge P90 et renouvelable P10) : "
            f"{format_pct(headlines.get('share_stress'))} des quarts d'heure, "
            f"couverture {format_pct(headlines.get('coverage_stress'))}. "
            f"En hiver {format_pct(headlines.get('share_stress_winter'))} ; "
            f"en été {format_pct(headlines.get('share_stress_summer'))} "
            "(jamais, avec un classement intra-saison)."
        )


if __name__ == "__main__":
    main()
else:
    main()

