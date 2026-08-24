"""Tests du chargement de configuration."""

from datetime import date
from pathlib import Path

import pytest

from renewables_wallonia.config import ConfigError, load_settings


def test_load_default_settings() -> None:
    """Le TOML du dépôt se charge et reflète le cadrage validé."""
    settings = load_settings()

    assert settings.period.start == date(2023, 9, 1)
    assert settings.period.end == date(2026, 8, 31)
    assert settings.elia.load_dataset == "ods001"
    assert settings.elia.solar_dataset == "ods032"
    assert settings.elia.wind_dataset == "ods031"
    assert settings.elia.coverage_region == "Belgium"
    assert settings.elia.zoom_region == "Wallonia"
    assert "Wallonia" in settings.elia.regions.solar
    assert "Wallonia" in settings.elia.regions.wind
    assert settings.display.timezone == "Europe/Brussels"
    assert len(settings.copernicus.belgium_bbox) == 4


def test_invalid_period(tmp_path: Path) -> None:
    """Une période inversée est rejetée."""
    config_file = tmp_path / "bad.toml"
    config_file.write_text(
        """
[period]
start = "2026-01-01"
end = "2023-01-01"

[elia]
base_url = "https://example.test"
load_dataset = "ods001"
solar_dataset = "ods032"
wind_dataset = "ods031"
coverage_region = "Belgium"
zoom_region = "Wallonia"

[elia.regions]
solar = ["Belgium"]
wind = ["Wallonia"]

[copernicus]
dataset = "reanalysis-era5-single-levels"
variables = ["surface_solar_radiation_downwards"]
belgium_bbox = [51.55, 2.5, 49.45, 6.45]
wallonia_bbox = [50.82, 2.84, 49.45, 6.45]

[paths]
raw_dir = "data/raw"
processed_dir = "data/processed"
warehouse = "data/processed/warehouse.duckdb"

[display]
timezone = "Europe/Brussels"
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="period.start"):
        load_settings(config_file)


def test_missing_file(tmp_path: Path) -> None:
    """Un chemin inexistant lève ConfigError."""
    with pytest.raises(ConfigError, match="introuvable"):
        load_settings(tmp_path / "absent.toml")
