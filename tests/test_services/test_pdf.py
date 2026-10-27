from app.services.pdf import extraire_texte_pdf
from tests.aide_pdf import creer_pdf_bytes


def test_extraire_texte_pdf_retrouve_le_texte_ecrit(tmp_path):
    chemin = tmp_path / "test.pdf"
    chemin.write_bytes(creer_pdf_bytes("Loyer Appt 1 : 500,00 EUR"))

    texte = extraire_texte_pdf(chemin)

    assert "Loyer Appt 1" in texte
    assert "500" in texte
