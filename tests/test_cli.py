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
