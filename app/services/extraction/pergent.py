from app.services.extraction.base import ExtractionNonCalibreeError, ResultatExtraction


class AdaptateurPergent:
    """Adaptateur pour les comptes-rendus de mise en location Pergent Immobilier
    (Sedan, Charleville-Mézières).

    Pas encore calibré : aucun exemple réel de document n'était disponible
    lors de l'écriture de ce code. Voir app/services/extraction/arthurimmo.py
    pour la marche à suivre dès qu'un PDF réel sera disponible.
    """

    def extraire(self, texte: str) -> ResultatExtraction:
        raise ExtractionNonCalibreeError(
            "L'adaptateur Pergent Immobilier n'a pas encore été calibré sur un exemple réel de compte-rendu."
        )
