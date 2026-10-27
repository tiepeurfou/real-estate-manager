from email.message import EmailMessage

import pytest

from app.models import CandidatCourrielTraite
from app.models.enums import StatutCandidatCourriel
from app.services.ingestion_mail import lister_candidats, marquer_traite, recuperer_piece_jointe
from app.services.mail import construire_message
from tests.aide_pdf import creer_pdf_bytes


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
