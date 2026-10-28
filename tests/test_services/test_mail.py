from email.message import EmailMessage

import pytest

from app.services.mail import ClientImap, ErreurConnexionImap, construire_message
from tests.aide_pdf import creer_pdf_bytes
from tests.faux_serveur_imap import FauxServeurImap


def _construire_email(sujet="Compte-rendu", expediteur="quelqu-un@exemple.fr", pieces_jointes=()):
    message = EmailMessage()
    message["From"] = expediteur
    message["To"] = "patrimoine.locatif@exemple.fr"
    message["Subject"] = sujet
    message["Date"] = "Tue, 10 Sep 2024 08:00:00 +0200"
    message.set_content("Voir document joint.")

    for nom, contenu, type_mime in pieces_jointes:
        maintype, subtype = type_mime.split("/")
        message.add_attachment(contenu, maintype=maintype, subtype=subtype, filename=nom)

    return message.as_bytes()


def test_construire_message_extrait_la_piece_jointe_pdf():
    contenu_pdf = creer_pdf_bytes("Compte-rendu septembre")
    donnees = _construire_email(pieces_jointes=[("releve.pdf", contenu_pdf, "application/pdf")])

    message = construire_message("1", donnees)

    assert message.uid == "1"
    assert message.objet == "Compte-rendu"
    assert "quelqu-un@exemple.fr" in message.expediteur
    assert len(message.pieces_jointes) == 1
    assert message.pieces_jointes[0].nom == "releve.pdf"
    assert message.pieces_jointes[0].contenu == contenu_pdf


def test_construire_message_ignore_les_pieces_jointes_non_pdf():
    donnees = _construire_email(pieces_jointes=[("photo.jpg", b"donnees-image", "image/jpeg")])

    message = construire_message("2", donnees)

    assert message.pieces_jointes == []


def test_construire_message_plusieurs_pieces_jointes_mixtes():
    contenu_pdf = creer_pdf_bytes("Relevé")
    donnees = _construire_email(
        pieces_jointes=[
            ("releve.pdf", contenu_pdf, "application/pdf"),
            ("photo.jpg", b"donnees-image", "image/jpeg"),
        ]
    )

    message = construire_message("3", donnees)

    assert [p.nom for p in message.pieces_jointes] == ["releve.pdf"]


def test_construire_message_sans_piece_jointe():
    donnees = _construire_email()

    message = construire_message("4", donnees)

    assert message.pieces_jointes == []
    assert message.objet == "Compte-rendu"


def test_construire_message_date_invalide_ne_plante_pas():
    message_email = EmailMessage()
    message_email["From"] = "x@exemple.fr"
    message_email["Subject"] = "Sans date valide"
    message_email["Date"] = "pas une date"
    message_email.set_content("x")

    message = construire_message("5", message_email.as_bytes())

    assert message.objet == "Sans date valide"
    assert message.date is not None


def test_construire_message_ignore_une_piece_jointe_pdf_sans_payload_decodable(monkeypatch):
    # get_payload(decode=True) peut renvoyer None (pas juste b"") dans de
    # rares cas de message mal formé (payload totalement absent) : ce cas
    # est difficile à reproduire avec un vrai RFC822 bien formé, donc on le
    # simule directement pour vérifier qu'il est bien ignoré sans planter.
    import email.message as email_message_module

    original_get_payload = email_message_module.Message.get_payload

    def get_payload_sans_decodage(self, decode=False, *args, **kwargs):
        if decode:
            return None
        return original_get_payload(self, decode=decode, *args, **kwargs)

    monkeypatch.setattr(email_message_module.Message, "get_payload", get_payload_sans_decodage)

    contenu_pdf = creer_pdf_bytes("Compte-rendu")
    donnees = _construire_email(pieces_jointes=[("releve.pdf", contenu_pdf, "application/pdf")])

    message = construire_message("6", donnees)

    assert message.pieces_jointes == []


def test_lister_uids_boite_vide_renvoie_liste_vide():
    with FauxServeurImap({}, "test@exemple.fr", "motdepasse") as serveur:
        with ClientImap("127.0.0.1", serveur.port, "test@exemple.fr", "motdepasse", use_ssl=False) as client:
            assert client.lister_uids() == []


def test_lister_uids_renvoie_tous_les_uids_de_la_boite():
    messages = {"1": _construire_email(), "2": _construire_email()}
    with FauxServeurImap(messages, "test@exemple.fr", "motdepasse") as serveur:
        with ClientImap("127.0.0.1", serveur.port, "test@exemple.fr", "motdepasse", use_ssl=False) as client:
            assert set(client.lister_uids()) == {"1", "2"}


def test_sortie_de_contexte_ignore_une_erreur_de_logout():
    import imaplib

    class ConnexionQuiRefuseLeLogout:
        def logout(self):
            raise imaplib.IMAP4.error("déjà déconnecté")

    client = ClientImap("127.0.0.1", 0, "test@exemple.fr", "motdepasse", use_ssl=False)
    client._connexion = ConnexionQuiRefuseLeLogout()

    client.__exit__(None, None, None)  # ne doit pas lever


def test_recuperer_message_leve_une_erreur_si_le_fetch_echoue():
    # Le faux serveur socket répond toujours "OK" (même pour un uid
    # inconnu, voir test_recuperer_message_uid_disparu...) : pour exercer
    # la vraie branche d'échec (un FETCH qui renvoie None, ce qu'un vrai
    # serveur IMAP peut faire), on remplace directement la connexion
    # imaplib sous-jacente par un double minimal.
    class ConnexionFactice:
        def uid(self, commande, *args):
            return "OK", [None]

    client = ClientImap("127.0.0.1", 0, "test@exemple.fr", "motdepasse", use_ssl=False)
    client._connexion = ConnexionFactice()

    with pytest.raises(ErreurConnexionImap):
        client.recuperer_message("1")


def test_recuperer_message_uid_disparu_ne_plante_pas_mais_renvoie_un_message_vide():
    # Le faux serveur répond toujours "OK" pour un FETCH, même sur un uid
    # qu'il ne connaît pas (contrairement à un vrai Gmail qui renverrait
    # probablement une absence de résultat) : le message reconstruit est
    # vide (pas de pièce jointe), ce qui fait échouer plus loin
    # recuperer_piece_jointe() avec un ValueError explicite plutôt que de
    # planter ici — voir test_ingestion_mail.py pour le scénario complet.
    with FauxServeurImap({}, "test@exemple.fr", "motdepasse") as serveur:
        with ClientImap("127.0.0.1", serveur.port, "test@exemple.fr", "motdepasse", use_ssl=False) as client:
            message = client.recuperer_message("999")
            assert message.pieces_jointes == []
