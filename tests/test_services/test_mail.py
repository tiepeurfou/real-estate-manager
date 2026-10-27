from email.message import EmailMessage

from app.services.mail import construire_message
from tests.aide_pdf import creer_pdf_bytes


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
