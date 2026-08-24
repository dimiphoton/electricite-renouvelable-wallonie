"""Tests de l'ingestion Elia (sans appel réseau, sauf mock)."""

from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import URLError

import pytest

from renewables_wallonia.config import load_settings
from renewables_wallonia.data.elia import (
    EliaExport,
    EliaIngestError,
    build_where_clause,
    csv_filename,
    export_csv_url,
    ingest_elia,
    period_utc_bounds,
    planned_exports,
)


def test_period_utc_bounds_bruxelles() -> None:
    """Le 1er septembre 2023 minuit belge tombe à 22:00 UTC (CEST)."""
    start, end = period_utc_bounds(date(2023, 9, 1), date(2026, 8, 31), "Europe/Brussels")
    assert start == datetime(2023, 8, 31, 22, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 31, 22, 0, tzinfo=timezone.utc)


def test_where_charge_sans_region() -> None:
    """La charge nationale n'a pas de champ region."""
    start = datetime(2023, 8, 31, 22, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 31, 22, 0, tzinfo=timezone.utc)
    clause = build_where_clause(start, end, regions=None)
    assert "region" not in clause
    assert "datetime >=" in clause
    assert "datetime <" in clause


def test_where_solaire_filtre_regions() -> None:
    """Le solaire est restreint aux mailles Belgique et Wallonie."""
    start = datetime(2023, 8, 31, 22, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 31, 22, 0, tzinfo=timezone.utc)
    clause = build_where_clause(start, end, regions=("Belgium", "Wallonia"))
    assert 'region IN ("Belgium", "Wallonia")' in clause


def test_export_url_et_nom_fichier() -> None:
    """L'URL d'export et le nom de fichier suivent le dataset."""
    export = EliaExport("load", "ods001", None)
    url = export_csv_url("https://opendata.elia.be/api/explore/v2.1", "ods001")
    assert url.endswith("/catalog/datasets/ods001/exports/csv")
    assert csv_filename(export, date(2023, 9, 1), date(2026, 8, 31)) == (
        "ods001_load_2023-09-01_2026-08-31.csv"
    )


def test_planned_exports_trois_jeux() -> None:
    """On télécharge charge, solaire et éolien, charge sans régions."""
    settings = load_settings()
    exports = planned_exports(settings)
    assert [item.kind for item in exports] == ["load", "solar", "wind"]
    assert exports[0].regions is None
    assert "Wallonia" in exports[1].regions
    assert "Wallonia" in exports[2].regions


def test_ingest_saute_fichier_deja_la(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Un CSV non vide n'est pas retéléchargé."""
    settings = load_settings()
    raw = tmp_path / "data" / "raw" / "elia"
    raw.mkdir(parents=True)
    for export in planned_exports(settings):
        dest = raw / csv_filename(export, settings.period.start, settings.period.end)
        dest.write_text("datetime,totalload\n", encoding="utf-8")

    def fail_download(url: str, dest: Path) -> int:
        raise AssertionError("ne doit pas retélécharger")

    monkeypatch.setattr("renewables_wallonia.data.elia._download_to_file", fail_download)
    results = ingest_elia(settings, tmp_path, force=False)
    assert len(results) == 3
    assert all(item.skipped for item in results)


def test_ingest_telecharge_si_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans fichier local, chaque export est écrit."""
    settings = load_settings()

    def fake_download(url: str, dest: Path) -> int:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"datetime,totalload\n2023-09-01T00:00:00+00:00,1\n")
        return dest.stat().st_size

    monkeypatch.setattr("renewables_wallonia.data.elia._download_to_file", fake_download)
    results = ingest_elia(settings, tmp_path, force=False)
    assert len(results) == 3
    assert all(not item.skipped for item in results)
    assert all(item.path.is_file() for item in results)


def test_ingest_force_retecharge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``force=True`` écrase un fichier déjà présent."""
    settings = load_settings()
    calls: list[str] = []

    def fake_download(url: str, dest: Path) -> int:
        calls.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x")
        return 1

    monkeypatch.setattr("renewables_wallonia.data.elia._download_to_file", fake_download)
    first = planned_exports(settings)[0]
    dest_dir = tmp_path / "data" / "raw" / "elia"
    dest_dir.mkdir(parents=True)
    (dest_dir / csv_filename(first, settings.period.start, settings.period.end)).write_text(
        "old", encoding="utf-8"
    )

    results = ingest_elia(settings, tmp_path, force=True)
    assert not results[0].skipped
    assert len(calls) == 3


def test_ingest_propage_erreur_reseau(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Une erreur réseau devient EliaIngestError."""

    def boom(url: str, dest: Path) -> int:
        raise URLError("offline")

    monkeypatch.setattr("renewables_wallonia.data.elia._download_to_file", boom)
    with pytest.raises(EliaIngestError, match="ods001"):
        ingest_elia(load_settings(), tmp_path, force=True)
