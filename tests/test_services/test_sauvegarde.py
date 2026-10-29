import sqlite3
from datetime import date

import app.services.sauvegarde as sauvegarde_module
from app.services.sauvegarde import sauvegarder_la_base


def _creer_base_source(chemin) -> None:
    connexion = sqlite3.connect(chemin)
    connexion.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, valeur TEXT)")
    connexion.execute("INSERT INTO test (valeur) VALUES ('bonjour')")
    connexion.commit()
    connexion.close()


def test_sauvegarder_la_base_cree_une_copie_coherente(tmp_path, monkeypatch):
    source = tmp_path / "app.db"
    _creer_base_source(source)
    dossier_sauvegardes = tmp_path / "backups"

    monkeypatch.setattr(sauvegarde_module, "DATABASE_PATH", source)
    monkeypatch.setattr(sauvegarde_module, "DOSSIER_SAUVEGARDES", dossier_sauvegardes)

    destination = sauvegarder_la_base(aujourdhui=date(2024, 9, 15))

    assert destination == dossier_sauvegardes / "app-2024-09-15.db"
    assert destination.exists()

    connexion = sqlite3.connect(destination)
    valeurs = connexion.execute("SELECT valeur FROM test").fetchall()
    connexion.close()
    assert valeurs == [("bonjour",)]


def test_sauvegarder_la_base_relancee_le_meme_jour_n_echoue_pas(tmp_path, monkeypatch):
    source = tmp_path / "app.db"
    _creer_base_source(source)
    dossier_sauvegardes = tmp_path / "backups"

    monkeypatch.setattr(sauvegarde_module, "DATABASE_PATH", source)
    monkeypatch.setattr(sauvegarde_module, "DOSSIER_SAUVEGARDES", dossier_sauvegardes)

    sauvegarder_la_base(aujourdhui=date(2024, 9, 15))
    sauvegarder_la_base(aujourdhui=date(2024, 9, 15))

    fichiers = list(dossier_sauvegardes.glob("app-*.db"))
    assert len(fichiers) == 1


def test_sauvegarder_la_base_purge_les_sauvegardes_trop_anciennes(tmp_path, monkeypatch):
    source = tmp_path / "app.db"
    _creer_base_source(source)
    dossier_sauvegardes = tmp_path / "backups"
    dossier_sauvegardes.mkdir()

    monkeypatch.setattr(sauvegarde_module, "DATABASE_PATH", source)
    monkeypatch.setattr(sauvegarde_module, "DOSSIER_SAUVEGARDES", dossier_sauvegardes)
    monkeypatch.setattr(sauvegarde_module, "SAUVEGARDE_DB_NOMBRE_JOURS_CONSERVES", 30)

    ancienne = dossier_sauvegardes / "app-2024-01-01.db"
    ancienne.touch()
    recente = dossier_sauvegardes / "app-2024-09-01.db"
    recente.touch()

    sauvegarder_la_base(aujourdhui=date(2024, 9, 15))

    assert not ancienne.exists()
    assert recente.exists()


def test_sauvegarder_la_base_ignore_les_fichiers_mal_nommes(tmp_path, monkeypatch):
    source = tmp_path / "app.db"
    _creer_base_source(source)
    dossier_sauvegardes = tmp_path / "backups"
    dossier_sauvegardes.mkdir()

    monkeypatch.setattr(sauvegarde_module, "DATABASE_PATH", source)
    monkeypatch.setattr(sauvegarde_module, "DOSSIER_SAUVEGARDES", dossier_sauvegardes)

    fichier_etrange = dossier_sauvegardes / "app-pas-une-date.db"
    fichier_etrange.touch()

    sauvegarder_la_base(aujourdhui=date(2024, 9, 15))  # ne doit pas planter

    assert fichier_etrange.exists()
