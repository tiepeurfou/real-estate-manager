from email.message import EmailMessage

import app.services.mail as mail_module
import app.services.notifications as notifications_module
import app.services.scheduler as scheduler_module
from app.models import CandidatCourrielNotifie
from app.services.scheduler import (
    demarrer_scheduler,
    sauvegarder_la_base_avec_alerte,
    scanner_la_boite_mail,
    verifier_dpe,
    verifier_revisions_loyer,
)
from tests.aide_pdf import creer_pdf_bytes
from tests.faux_serveur_imap import FauxServeurImap
from tests.faux_serveur_ntfy import FauxServeurNtfy


def _email_avec_pdf(nom_pdf="releve.pdf") -> bytes:
    message = EmailMessage()
    message["From"] = "quelqu-un@exemple.fr"
    message["Subject"] = "Compte-rendu"
    message["Date"] = "Tue, 10 Sep 2024 08:00:00 +0200"
    message.set_content("Voir document joint.")
    message.add_attachment(creer_pdf_bytes("Compte-rendu"), maintype="application", subtype="pdf", filename=nom_pdf)
    return message.as_bytes()


def _pointer_imap_vers(monkeypatch, serveur, utilisateur="test@exemple.fr", mot_de_passe="motdepasse"):
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_HOTE", "127.0.0.1")
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_PORT", serveur.port)
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_ADRESSE", utilisateur)
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_MOT_DE_PASSE", mot_de_passe)
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_SSL", False)


def test_scanner_la_boite_mail_ne_fait_rien_si_non_configuree(monkeypatch, engine):
    # GMAIL_IMAP_ADRESSE/MOT_DE_PASSE sont déjà vides par défaut dans les
    # tests (fixture autouse de conftest.py) : aucun appel réseau ne doit
    # être tenté, et la fonction ne doit pas planter.
    monkeypatch.setattr(scheduler_module, "engine", engine)
    scanner_la_boite_mail()


def test_scanner_la_boite_mail_notifie_un_nouveau_candidat(monkeypatch, engine):
    monkeypatch.setattr(scheduler_module, "engine", engine)
    messages = {"1": _email_avec_pdf()}

    with FauxServeurImap(messages, "test@exemple.fr", "motdepasse") as serveur_imap, FauxServeurNtfy() as serveur_ntfy:
        _pointer_imap_vers(monkeypatch, serveur_imap)
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur_ntfy.url)

        scanner_la_boite_mail()

    assert len(serveur_ntfy.requetes) == 1
    assert "releve.pdf" in serveur_ntfy.requetes[0]["json"]["message"]

    from sqlmodel import Session, select

    with Session(engine) as s:
        assert len(s.exec(select(CandidatCourrielNotifie)).all()) == 1


def test_scanner_la_boite_mail_erreur_connexion_ne_plante_pas(monkeypatch, engine):
    monkeypatch.setattr(scheduler_module, "engine", engine)
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_HOTE", "127.0.0.1")
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_PORT", 1)
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_ADRESSE", "test@exemple.fr")
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_MOT_DE_PASSE", "motdepasse")
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_SSL", False)

    scanner_la_boite_mail()  # ne doit lever aucune exception


def test_demarrer_scheduler_configure_le_job_et_s_arrete(monkeypatch, engine):
    monkeypatch.setattr(scheduler_module, "engine", engine)

    scheduler = demarrer_scheduler()
    try:
        jobs_periodiques = [j for j in scheduler.get_jobs() if j.trigger.__class__.__name__ == "IntervalTrigger"]
        assert len(jobs_periodiques) == 1
        jobs_quotidiens = [j for j in scheduler.get_jobs() if j.trigger.__class__.__name__ == "CronTrigger"]
        assert len(jobs_quotidiens) == 3
    finally:
        scheduler.shutdown(wait=False)


def test_sauvegarder_la_base_avec_alerte_ne_notifie_pas_en_cas_de_succes(monkeypatch, tmp_path):
    import app.services.sauvegarde as sauvegarde_module

    source = tmp_path / "app.db"
    import sqlite3

    sqlite3.connect(source).close()
    monkeypatch.setattr(sauvegarde_module, "DATABASE_PATH", source)
    monkeypatch.setattr(sauvegarde_module, "DOSSIER_SAUVEGARDES", tmp_path / "backups")

    with FauxServeurNtfy() as serveur:
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur.url)

        sauvegarder_la_base_avec_alerte()

    assert serveur.requetes == []


def test_sauvegarder_la_base_avec_alerte_notifie_en_cas_d_echec(monkeypatch):
    def _sauvegarde_qui_echoue(aujourdhui=None):
        raise OSError("disque plein")

    monkeypatch.setattr(scheduler_module, "sauvegarder_la_base", _sauvegarde_qui_echoue)

    with FauxServeurNtfy() as serveur:
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur.url)

        sauvegarder_la_base_avec_alerte()  # ne doit lever aucune exception

    assert len(serveur.requetes) == 1
    assert "disque plein" in serveur.requetes[0]["json"]["message"]


def test_sauvegarder_la_base_avec_alerte_echec_notification_n_echoue_pas_non_plus(monkeypatch):
    def _sauvegarde_qui_echoue(aujourdhui=None):
        raise OSError("disque plein")

    monkeypatch.setattr(scheduler_module, "sauvegarder_la_base", _sauvegarde_qui_echoue)
    monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
    monkeypatch.setattr(notifications_module, "NTFY_URL", "http://127.0.0.1:1")

    sauvegarder_la_base_avec_alerte()  # ne doit lever aucune exception malgré le double échec


def test_verifier_revisions_loyer_utilise_le_moteur_configure_et_ne_plante_pas(monkeypatch, engine):
    # La logique métier (fenêtre, échéances, mémorisation) est déjà testée
    # exhaustivement dans test_revision_loyer.py ; ce test-ci vérifie
    # seulement le câblage côté scheduler (bon moteur, pas de plantage même
    # sans aucune occupation en base).
    monkeypatch.setattr(scheduler_module, "engine", engine)

    verifier_revisions_loyer()


def test_verifier_dpe_utilise_le_moteur_configure_et_ne_plante_pas(monkeypatch, engine):
    # La logique métier (fenêtre, échéances, mémorisation) est déjà testée
    # exhaustivement dans test_dpe.py ; ce test-ci vérifie seulement le
    # câblage côté scheduler (bon moteur, pas de plantage même sans aucune
    # unité en base).
    monkeypatch.setattr(scheduler_module, "engine", engine)

    verifier_dpe()
