from app.services.extraction.arthurimmo import AdaptateurArthurImmo
from app.services.extraction.base import (
    AdaptateurExtraction,
    ExtractionNonCalibreeError,
    LigneDepenseExtraite,
    LignePaiementExtraite,
    ResultatExtraction,
)
from app.services.extraction.locagestion import AdaptateurLocagestion
from app.services.extraction.pergent import AdaptateurPergent

__all__ = [
    "AdaptateurExtraction",
    "ExtractionNonCalibreeError",
    "LigneDepenseExtraite",
    "LignePaiementExtraite",
    "ResultatExtraction",
    "obtenir_adaptateur",
]

_REGISTRE: dict[str, AdaptateurExtraction] = {
    "arthurimmo": AdaptateurArthurImmo(),
    "pergentimmobilier": AdaptateurPergent(),
    "locagestion": AdaptateurLocagestion(),
}


def _normaliser(nom: str) -> str:
    return nom.strip().lower().replace(" ", "")


def obtenir_adaptateur(nom_gestionnaire: str) -> AdaptateurExtraction:
    adaptateur = _REGISTRE.get(_normaliser(nom_gestionnaire))
    if adaptateur is None:
        raise ExtractionNonCalibreeError(
            f"Aucun adaptateur d'extraction enregistré pour « {nom_gestionnaire} »."
        )
    return adaptateur
