---
marp: true
theme: default
paginate: true
---

# Renewable electricity in Belgium
## Wallonia production zoom

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-analytics-yellow?logo=duckdb&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-red?logo=streamlit&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-charts-3F4F75?logo=plotly&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-data-150458?logo=pandas&logoColor=white)

*API pipeline → analysis → dashboard, with a numbered recommendation*

---

## The problem

Solar and wind output follows the weather. It is not a steady baseload.

A grid operator or supplier needs to know **when** that generation covers Belgian demand — and **where to put the next euro of flexibility**, rather than adding solar by default.

---

## The data

Official Belgian grid figures from Elia (15-minute), plus Copernicus weather. No maps: we compare time series.

Electricity use is published for **Belgium as a whole**. Wallonia is the production zoom, not a regional coverage ratio.

---

## The result (3 years)

Solar + wind cover **27%** of Belgian electricity use on average.

Summer midday is already well covered. The gap is **early evening in winter**.

![w:1050](../../pictures/presentations/coverage-hour-season.png)

---

## Recommendation

Put flexibility (shift demand, store, import) on the **winter 4–7 pm** slot, not extra solar panels for summer peaks.

![w:1050](../../pictures/presentations/recommendation-winter.png)

Dashboard: `python -m renewables_wallonia.cli dashboard`
