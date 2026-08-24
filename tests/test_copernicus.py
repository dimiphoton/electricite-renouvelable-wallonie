"""Tests de l'ingestion Copernicus (sans file d'attente CDS)."""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from renewables_wallonia.config import load_settings
from renewables_wallonia.data.copernicus import (
    CopernicusIngestError,
    era5_month_request,
    ingest_copernicus,
    months_in_period,
    monthly_nc_name,
    spatial_mean,
)


def _tiny_era5(path: Path) -> None:
    """Grille 3x3 factice : u=3, v=4 donc wind_speed=5, ssrd=100."""
    times = pd.date_range("2024-01-01", periods=2, freq="h")
    lats = np.array([51.25, 50.5, 49.75])
    lons = np.array([3.0, 4.5, 6.0])
    shape = (2, 3, 3)
    ds = xr.Dataset(
        {
            "u10": (("valid_time", "latitude", "longitude"), np.full(shape, 3.0)),
            "v10": (("valid_time", "latitude", "longitude"), np.full(shape, 4.0)),
            "ssrd": (("valid_time", "latitude", "longitude"), np.full(shape, 100.0)),
        },
        coords={"valid_time": times, "latitude": lats, "longitude": lons},
    )
    ds.to_netcdf(path)


def test_months_in_period_36_mois() -> None:
    """Sep 2023 → août 2026 = 36 mois."""
    months = months_in_period(date(2023, 9, 1), date(2026, 8, 31))
    assert len(months) == 36
    assert months[0] == (2023, 9)
    assert months[-1] == (2026, 8)


def test_era5_request_utilise_la_bbox_belgique() -> None:
    """Un seul téléchargement (bbox Belgique) ; la Wallonie est un sous-ensemble."""
    settings = load_settings()
    request = era5_month_request(settings, 2024, 1)
    assert request["area"] == list(settings.copernicus.belgium_bbox)
    assert "surface_solar_radiation_downwards" in request["variable"]
    assert request["data_format"] == "netcdf"


def test_spatial_mean_vent_et_ssrd(tmp_path: Path) -> None:
    """u=3, v=4 → vitesse 5 ; ssrd constant 100."""
    nc_path = tmp_path / "tiny.nc"
    _tiny_era5(nc_path)
    with xr.open_dataset(nc_path) as dataset:
        from renewables_wallonia.data.copernicus import _prepare_grid

        prepared = _prepare_grid(dataset)
        mean = spatial_mean(prepared, (51.55, 2.5, 49.45, 6.45))
        assert float(mean["wind_speed"].isel(valid_time=0)) == pytest.approx(5.0)
        assert float(mean["ssrd"].isel(valid_time=0)) == pytest.approx(100.0)


def test_ingest_ecrit_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans CDS : le retrieve de test copie un NetCDF miniature."""
    settings = load_settings()
    source = tmp_path / "source.nc"
    _tiny_era5(source)

    def fake_retrieve(dataset: str, request: dict, target: Path) -> None:
        target.write_bytes(source.read_bytes())

    monkeypatch.setattr(
        "renewables_wallonia.data.copernicus.months_in_period",
        lambda start, end: ((2024, 1),),
    )
    months, csv_path = ingest_copernicus(
        settings, tmp_path, force=False, retrieve=fake_retrieve
    )
    assert len(months) == 1
    assert not months[0].skipped
    frame = pd.read_csv(csv_path)
    assert set(frame["region"]) == {"Belgium", "Wallonia"}
    assert {"datetime_utc", "ssrd", "u10", "v10", "wind_speed"} <= set(frame.columns)


def test_zip_cds_fusionne_les_variables(tmp_path: Path) -> None:
    """CDS envoie souvent un zip (un NetCDF par variable) : on les fusionne."""
    import zipfile

    from renewables_wallonia.data.copernicus import _materialize_netcdf

    wind = tmp_path / "wind.nc"
    ssrd = tmp_path / "ssrd.nc"
    times = pd.date_range("2024-01-01", periods=2, freq="h")
    lats = np.array([51.25, 50.5, 49.75])
    lons = np.array([3.0, 4.5, 6.0])
    shape = (2, 3, 3)
    coords = {"valid_time": times, "latitude": lats, "longitude": lons}
    xr.Dataset(
        {
            "u10": (("valid_time", "latitude", "longitude"), np.full(shape, 3.0)),
            "v10": (("valid_time", "latitude", "longitude"), np.full(shape, 4.0)),
        },
        coords=coords,
    ).to_netcdf(wind)
    xr.Dataset(
        {"ssrd": (("valid_time", "latitude", "longitude"), np.full(shape, 100.0))},
        coords=coords,
    ).to_netcdf(ssrd)

    archive = tmp_path / "era5.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(wind, "wind.nc")
        handle.write(ssrd, "ssrd.nc")

    dest = tmp_path / "merged.nc"
    _materialize_netcdf(archive, dest)
    with xr.open_dataset(dest) as dataset:
        assert set(dataset.data_vars) == {"u10", "v10", "ssrd"}


def test_ingest_retecharge_si_ssrd_manquant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un mois déjà là mais sans rayonnement n'est pas considéré complet."""
    settings = load_settings()
    dest_dir = tmp_path / "data" / "raw" / "copernicus"
    dest_dir.mkdir(parents=True)
    incomplete = dest_dir / monthly_nc_name(2024, 1)
    times = pd.date_range("2024-01-01", periods=2, freq="h")
    xr.Dataset(
        {
            "u10": (("valid_time", "latitude", "longitude"), np.ones((2, 2, 2))),
            "v10": (("valid_time", "latitude", "longitude"), np.zeros((2, 2, 2))),
        },
        coords={
            "valid_time": times,
            "latitude": np.array([51.0, 50.0]),
            "longitude": np.array([4.0, 5.0]),
        },
    ).to_netcdf(incomplete)

    calls = {"n": 0}

    def fake_retrieve(dataset: str, request: dict, target: Path) -> None:
        calls["n"] += 1
        _tiny_era5(target)

    monkeypatch.setattr(
        "renewables_wallonia.data.copernicus.months_in_period",
        lambda start, end: ((2024, 1),),
    )
    months, _csv_path = ingest_copernicus(
        settings, tmp_path, force=False, retrieve=fake_retrieve
    )
    assert calls["n"] == 1
    assert months[0].skipped is False


def test_ingest_saute_nc_existant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Un NetCDF mensuel déjà là n'est pas retéléchargé."""
    settings = load_settings()
    dest_dir = tmp_path / "data" / "raw" / "copernicus"
    dest_dir.mkdir(parents=True)
    existing = dest_dir / monthly_nc_name(2024, 1)
    _tiny_era5(existing)

    def boom(dataset: str, request: dict, target: Path) -> None:
        raise AssertionError("ne doit pas appeler CDS")

    monkeypatch.setattr(
        "renewables_wallonia.data.copernicus.months_in_period",
        lambda start, end: ((2024, 1),),
    )
    months, csv_path = ingest_copernicus(settings, tmp_path, force=False, retrieve=boom)
    assert months[0].skipped is True
    assert csv_path.is_file()


def test_bbox_vide_leve(tmp_path: Path) -> None:
    """Une bbox hors grille doit échouer clairement."""
    nc_path = tmp_path / "tiny.nc"
    _tiny_era5(nc_path)
    with xr.open_dataset(nc_path) as dataset:
        from renewables_wallonia.data.copernicus import _prepare_grid

        prepared = _prepare_grid(dataset)
        with pytest.raises(CopernicusIngestError, match="aucune maille"):
            spatial_mean(prepared, (60.0, 10.0, 59.0, 11.0))
