from app.services.extraction.base import ExtractionNonCalibreeError, ResultatExtraction


class AdaptateurArthurImmo:
    """Adaptateur pour les comptes-rendus de gestion ArthurImmo (Villiers-sur-Marne).

    Pas encore calibré : aucun exemple réel de document n'était disponible
    lors de l'écriture de ce code. Pour l'implémenter : fournir un PDF réel
    de compte-rendu ArthurImmo, identifier les motifs de ligne (locataire,
    période, montants, statut) et compléter `extraire()` en conséquence,
    en respectant le contrat `ResultatExtraction` défini dans base.py.
    """

    def extraire(self, texte: str) -> ResultatExtraction:
        raise ExtractionNonCalibreeError(
            "L'adaptateur ArthurImmo n'a pas encore été calibré sur un exemple réel de compte-rendu."
        )
