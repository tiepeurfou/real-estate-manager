from email.message import EmailMessage

import pytest

import app.services.notifications as notifications_module
from app.models import CandidatCourrielNotifie, CandidatCourrielTraite
from app.models.enums import StatutCandidatCourriel
from app.services.ingestion_mail import lister_candidats, marquer_traite, notifier_nouveaux_candidats, recuperer_piece_jointe
from app.services.mail import construire_message
from tests.aide_pdf import creer_pdf_bytes
from tests.faux_serveur_ntfy import FauxServeurNtfy


def _email_avec_pdf(nom_pdf="releve.pdf", sujet="Compte-rendu") -> bytes:
    message = EmailMessage()
    message["From"] = "quelqu-un@exemple.fr"
    message["Subject"] = sujet
    message["Date"] = "Tue, 10 Sep 2024 08:00:00 +0200"
    message.set_content("Voir document joint.")
    message.add_attachment(creer_pdf_bytes(sujet), maintype="application", subtype="pdf", filename=nom_pdf)
    return message.as_bytes()


class ClientImapFactice:
    """Implémente juste l'interface utilisée par lister_candidats/recuperer_piece_jointe,
    sans passer par le protocole réseau — le protocole lui-même est déjà testé
    dans test_client_imap.py contre le vrai faux serveur."""

    def __init__(self, messages: dict[str, bytes]):
        self._bruts = messages

    def lister_uids(self) -> list[str]:
        return list(self._bruts.keys())

    def recuperer_message(self, uid: str):
        return construire_message(uid, self._bruts[uid])


def test_lister_candidats_sans_mail(session):
    client = ClientImapFactice({})
    assert lister_candidats(client, session) == []


def test_lister_candidats_renvoie_les_pieces_jointes_pdf(session):
    client = ClientImapFactice({"1": _email_avec_pdf()})

    candidats = lister_candidats(client, session)

    assert len(candidats) == 1
    assert candidats[0].message_uid == "1"
    assert candidats[0].nom_piece_jointe == "releve.pdf"
    assert candidats[0].expediteur == "quelqu-un@exemple.fr"


def test_lister_candidats_exclut_les_deja_traites(session):
    client = ClientImapFactice({"1": _email_avec_pdf()})

    marquer_traite(session, "1", "releve.pdf", StatutCandidatCourriel.IGNORE)

    assert lister_candidats(client, session) == []


def test_lister_candidats_plusieurs_messages(session):
    client = ClientImapFactice(
        {
            "1": _email_avec_pdf("releve1.pdf", sujet="Sedan"),
            "2": _email_avec_pdf("releve2.pdf", sujet="Charleville"),
        }
    )

    candidats = lister_candidats(client, session)

    assert sorted(c.nom_piece_jointe for c in candidats) == ["releve1.pdf", "releve2.pdf"]


def test_marquer_traite_enregistre_le_statut_et_le_releve(session):
    candidat = marquer_traite(session, "1", "releve.pdf", StatutCandidatCourriel.IMPORTE, releve_gestion_id=42)

    from sqlmodel import select

    enregistre = session.exec(select(CandidatCourrielTraite).where(CandidatCourrielTraite.id == candidat.id)).first()
    assert enregistre.statut == StatutCandidatCourriel.IMPORTE
    assert enregistre.releve_gestion_id == 42


def test_recuperer_piece_jointe():
    client = ClientImapFactice({"1": _email_avec_pdf()})
    contenu = recuperer_piece_jointe(client, "1", "releve.pdf")
    assert contenu.startswith(b"%PDF")


def test_recuperer_piece_jointe_introuvable():
    client = ClientImapFactice({"1": _email_avec_pdf()})
    with pytest.raises(ValueError):
        recuperer_piece_jointe(client, "1", "inexistant.pdf")


def test_notifier_nouveaux_candidats_envoie_et_memorise(session, monkeypatch):
    client = ClientImapFactice({"1": _email_avec_pdf()})

    with FauxServeurNtfy() as serveur:
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur.url)

        nouveaux = notifier_nouveaux_candidats(client, session)

    assert len(nouveaux) == 1
    assert len(serveur.requetes) == 1
    assert "releve.pdf" in serveur.requetes[0]["json"]["message"]

    from sqlmodel import select

    enregistres = session.exec(select(CandidatCourrielNotifie)).all()
    assert len(enregistres) == 1
    assert enregistres[0].message_uid == "1"
    assert enregistres[0].nom_piece_jointe == "releve.pdf"


def test_notifier_nouveaux_candidats_ne_renotifie_pas_un_candidat_deja_notifie(session, monkeypatch):
    client = ClientImapFactice({"1": _email_avec_pdf()})

    with FauxServeurNtfy() as serveur:
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur.url)

        notifier_nouveaux_candidats(client, session)
        nouveaux_deuxieme_passage = notifier_nouveaux_candidats(client, session)

    assert nouveaux_deuxieme_passage == []
    assert len(serveur.requetes) == 1


def test_notifier_nouveaux_candidats_exclut_les_deja_traites(session, monkeypatch):
    client = ClientImapFactice({"1": _email_avec_pdf()})
    marquer_traite(session, "1", "releve.pdf", StatutCandidatCourriel.IGNORE)

    with FauxServeurNtfy() as serveur:
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur.url)

        nouveaux = notifier_nouveaux_candidats(client, session)

    assert nouveaux == []
    assert serveur.requetes == []


def test_notifier_nouveaux_candidats_sans_ntfy_configure_ne_plante_pas(session, monkeypatch):
    client = ClientImapFactice({"1": _email_avec_pdf()})
    monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "")

    nouveaux = notifier_nouveaux_candidats(client, session)

    assert len(nouveaux) == 1


def test_notifier_nouveaux_candidats_echec_d_envoi_n_est_pas_memorise(session, monkeypatch):
    # Si l'envoi échoue (ex. ntfy.sh inaccessible), le candidat ne doit pas
    # être marqué notifié : on veut retenter au prochain scan, pas perdre
    # silencieusement la notification.
    client = ClientImapFactice({"1": _email_avec_pdf()})
    monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
    monkeypatch.setattr(notifications_module, "NTFY_URL", "http://127.0.0.1:1")

    nouveaux = notifier_nouveaux_candidats(client, session)

    assert len(nouveaux) == 1

    from sqlmodel import select

    assert session.exec(select(CandidatCourrielNotifie)).all() == []
