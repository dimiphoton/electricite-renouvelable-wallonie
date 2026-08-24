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
![Pandas](https://img.shields.io/badge/Pandas-data-150458?logo=pandas&logoColor=white)

*Portfolio — step 1: framing and project skeleton*

---

## The problem

Solar and wind output is weather-dependent, not steady.

A grid operator or supplier needs to know **when** that generation covers Belgian demand, and **why** it moves — especially in Wallonia.

---

## The data

Official Belgian grid figures from Elia (15-minute), plus Copernicus weather. No maps: we compare time series.

Load is published for **Belgium as a whole**. Wallonia is the production zoom, not a regional coverage ratio.

---

## The result

No dashboard yet: the project has just been framed.

Later: a dashboard that shows whether renewables track demand, plus a numbered recommendation for a decision-maker.
