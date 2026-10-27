import pytest
from email.message import EmailMessage

from app.services.mail import ClientImap, ErreurConnexionImap
from tests.aide_pdf import creer_pdf_bytes
from tests.faux_serveur_imap import FauxServeurImap


def _email_avec_pdf(nom_pdf="releve.pdf") -> bytes:
    message = EmailMessage()
    message["From"] = "quelqu-un@exemple.fr"
    message["Subject"] = "Compte-rendu"
    message["Date"] = "Tue, 10 Sep 2024 08:00:00 +0200"
    message.set_content("Voir document joint.")
    message.add_attachment(creer_pdf_bytes("Compte-rendu"), maintype="application", subtype="pdf", filename=nom_pdf)
    return message.as_bytes()


def test_client_imap_liste_les_uids_et_recupere_un_message():
    messages = {"1": _email_avec_pdf(), "2": _email_avec_pdf("autre.pdf")}

    with FauxServeurImap(messages, "test@exemple.fr", "motdepasse") as serveur:
        client = ClientImap("127.0.0.1", serveur.port, "test@exemple.fr", "motdepasse", use_ssl=False)
        with client as c:
            uids = sorted(c.lister_uids())
            assert uids == ["1", "2"]

            message = c.recuperer_message("1")
            assert message.uid == "1"
            assert len(message.pieces_jointes) == 1
            assert message.pieces_jointes[0].nom == "releve.pdf"


def test_client_imap_mauvais_mot_de_passe_leve_une_erreur():
    with FauxServeurImap({}, "test@exemple.fr", "motdepasse") as serveur:
        client = ClientImap("127.0.0.1", serveur.port, "test@exemple.fr", "mauvais", use_ssl=False)
        with pytest.raises(ErreurConnexionImap):
            with client:
                pass


def test_client_imap_boite_vide():
    with FauxServeurImap({}, "test@exemple.fr", "motdepasse") as serveur:
        client = ClientImap("127.0.0.1", serveur.port, "test@exemple.fr", "motdepasse", use_ssl=False)
        with client as c:
            assert c.lister_uids() == []


def test_client_imap_serveur_inaccessible_leve_une_erreur():
    client = ClientImap("127.0.0.1", 1, "test@exemple.fr", "motdepasse", use_ssl=False)
    with pytest.raises(ErreurConnexionImap):
        with client:
            pass
