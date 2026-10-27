"""Aide de test : génère un PDF minimal en mémoire (via reportlab) pour les
tests d'extraction, puisqu'aucun exemple réel de compte-rendu n'est disponible."""

from io import BytesIO

from reportlab.pdfgen import canvas


def creer_pdf_bytes(texte: str) -> bytes:
    tampon = BytesIO()
    c = canvas.Canvas(tampon)
    c.drawString(100, 700, texte)
    c.save()
    return tampon.getvalue()
