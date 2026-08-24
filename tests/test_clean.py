"""Tests de nettoyage Elia / ERA5."""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from renewables_wallonia.config import load_settings
from renewables_wallonia.data.clean import (
    build_datetime_dim,
    clean_load,
    clean_solar,
    clean_weather,
    clean_wind,
)
from renewables_wallonia.data.elia import csv_filename, planned_exports


def _start_end():
    start = datetime(2023, 8, 31, 22, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 31, 22, 0, tzinfo=timezone.utc)
    return start, end


def _write_elia(tmp_path: Path, kind: str, frame: pd.DataFrame) -> None:
    settings = load_settings()
    export = next(item for item in planned_exports(settings) if item.kind == kind)
    dest_dir = tmp_path / "data" / "raw" / "elia"
    dest_dir.mkdir(parents=True)
    dest = dest_dir / csv_filename(export, settings.period.start, settings.period.end)
    frame.to_csv(dest, index=False)


def test_clean_load_garde_les_na(tmp_path: Path) -> None:
    """Un totalload manquant reste manquant."""
    _write_elia(
        tmp_path,
        "load",
        pd.DataFrame(
            {
                "datetime": ["2023-09-01T00:00:00+00:00", "2023-09-01T00:15:00+00:00"],
                "totalload": [8000.0, None],
                "dayaheadforecast": [8100.0, 8050.0],
            }
        ),
    )
    start, end = _start_end()
    frame = clean_load(load_settings(), tmp_path, start, end)
    assert frame.loc[1, "load_mw"] != frame.loc[1, "load_mw"]  # NaN
    assert frame.loc[0, "region"] == "Belgium"


def test_clean_wind_somme_elia_dso_et_belgique(tmp_path: Path) -> None:
    """Elia+DSO par région, puis total Belgique."""
    ts = "2023-09-01T00:00:00+00:00"
    _write_elia(
        tmp_path,
        "wind",
        pd.DataFrame(
            {
                "datetime": [ts, ts, ts],
                "region": ["Wallonia", "Wallonia", "Flanders"],
                "gridconnectiontype": ["Elia", "Dso", "Elia"],
                "measured": [10.0, 5.0, 20.0],
                "dayaheadforecast": [11.0, 6.0, 21.0],
                "monitoredcapacity": [100.0, 50.0, 200.0],
            }
        ),
    )
    start, end = _start_end()
    frame = clean_wind(load_settings(), tmp_path, start, end)
    wallonia = frame.loc[frame["region"] == "Wallonia"].iloc[0]
    belgium = frame.loc[frame["region"] == "Belgium"].iloc[0]
    assert wallonia["measured_mw"] == 15.0
    assert belgium["measured_mw"] == 35.0
    assert set(frame["source"]) == {"wind"}


def test_clean_solar_ne_somme_pas_les_regions(tmp_path: Path) -> None:
    """Belgique et Wallonie restent deux mailles distinctes."""
    ts = "2023-09-01T00:00:00+00:00"
    _write_elia(
        tmp_path,
        "solar",
        pd.DataFrame(
            {
                "datetime": [ts, ts],
                "region": ["Belgium", "Wallonia"],
                "measured": [100.0, 30.0],
                "dayaheadforecast": [90.0, 25.0],
                "monitoredcapacity": [1000.0, 400.0],
                "loadfactor": [10.0, 7.5],
            }
        ),
    )
    start, end = _start_end()
    frame = clean_solar(load_settings(), tmp_path, start, end)
    assert len(frame) == 2
    assert set(frame["region"]) == {"Belgium", "Wallonia"}


def test_clean_weather_convertit_ssrd(tmp_path: Path) -> None:
    """J/m² par heure → W/m²."""
    settings = load_settings()
    dest = tmp_path / "data" / "processed"
    dest.mkdir(parents=True)
    pd.DataFrame(
        {
            "datetime_utc": ["2023-09-01T12:00:00+00:00"],
            "region": ["Belgium"],
            "ssrd": [3600.0],
            "u10": [1.0],
            "v10": [0.0],
            "wind_speed": [1.0],
        }
    ).to_csv(dest / "era5_hourly.csv", index=False)
    start, end = _start_end()
    frame = clean_weather(settings, tmp_path, start, end)
    assert frame.loc[0, "ssrd_w_m2"] == 1.0


def test_datetime_dim_saison_bruxelles() -> None:
    """Un samedi de juillet à Bruxelles est un week-end d'été."""
    ts = pd.Series([pd.Timestamp("2024-07-06 10:00", tz="UTC")])
    dim = build_datetime_dim(ts, "Europe/Brussels")
    assert bool(dim.loc[0, "is_weekend"]) is True
    assert dim.loc[0, "season"] == "summer"
    assert dim.loc[0, "hour"] == 12  # CEST = UTC+2
