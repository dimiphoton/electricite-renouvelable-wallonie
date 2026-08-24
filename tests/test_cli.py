"""Tests du point d'entrée CLI."""

import pytest

from renewables_wallonia.cli import main


def test_help_affiche_la_sous_commande(capsys: pytest.CaptureFixture[str]) -> None:
    """``--help`` décrit le CLI et mentionne show-config."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])

    assert excinfo.value.code == 0
    sortie = capsys.readouterr().out
    assert "show-config" in sortie
    assert "ingest-elia" in sortie
    assert "ingest-copernicus" in sortie
    assert "Belgique" in sortie


def test_sans_commande_affiche_laide(capsys: pytest.CaptureFixture[str]) -> None:
    """Sans sous-commande, on affiche l'aide plutôt qu'une erreur."""
    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code == 0
    assert "show-config" in capsys.readouterr().out


def test_show_config(capsys: pytest.CaptureFixture[str]) -> None:
    """``show-config`` rappelle les datasets Elia et le zoom Wallonie."""
    with pytest.raises(SystemExit) as excinfo:
        main(["show-config"])

    assert excinfo.value.code == 0
    sortie = capsys.readouterr().out
    assert "ods001" in sortie
    assert "Wallonia" in sortie
    assert "warehouse.duckdb" in sortie


def test_ingest_elia_cli(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Le CLI délègue à ingest_elia et affiche le nom des fichiers."""
    from pathlib import Path

    from renewables_wallonia.data.elia import DownloadResult

    def fake_ingest(settings, root, force=False):
        dest = Path("data/raw/elia/ods001_load_2023-09-01_2026-08-31.csv")
        return (DownloadResult(path=dest, skipped=True, bytes_written=0),)

    monkeypatch.setattr("renewables_wallonia.cli.ingest_elia", fake_ingest)
    with pytest.raises(SystemExit) as excinfo:
        main(["ingest-elia"])
    assert excinfo.value.code == 0
    sortie = capsys.readouterr().out
    assert "ods001_load" in sortie
    assert "deja present" in sortie


def test_ingest_copernicus_cli(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Le CLI délègue à ingest_copernicus."""
    from pathlib import Path

    from renewables_wallonia.data.copernicus import MonthDownload

    def fake_ingest(settings, root, force=False):
        month = MonthDownload(path=Path("data/raw/copernicus/era5_2024-01.nc"), year=2024, month=1, skipped=True)
        return ((month,), Path("data/processed/era5_hourly.csv"))

    monkeypatch.setattr("renewables_wallonia.cli.ingest_copernicus", fake_ingest)
    with pytest.raises(SystemExit) as excinfo:
        main(["ingest-copernicus"])
    assert excinfo.value.code == 0
    sortie = capsys.readouterr().out
    assert "ERA5" in sortie
    assert "era5_hourly.csv" in sortie
