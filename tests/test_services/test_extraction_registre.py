import pytest

from app.services.extraction import ExtractionNonCalibreeError, obtenir_adaptateur
from app.services.extraction.arthurimmo import AdaptateurArthurImmo
from app.services.extraction.locagestion import AdaptateurLocagestion
from app.services.extraction.pergent import AdaptateurPergent


@pytest.mark.parametrize(
    "nom,type_attendu",
    [
        ("ArthurImmo", AdaptateurArthurImmo),
        ("arthurimmo", AdaptateurArthurImmo),
        ("Pergent Immobilier", AdaptateurPergent),
        ("pergentimmobilier", AdaptateurPergent),
        ("Locagestion", AdaptateurLocagestion),
        ("  locagestion  ", AdaptateurLocagestion),
    ],
)
def test_obtenir_adaptateur_resout_les_variantes_de_nom(nom, type_attendu):
    assert isinstance(obtenir_adaptateur(nom), type_attendu)


def test_obtenir_adaptateur_inconnu_leve_une_erreur():
    with pytest.raises(ExtractionNonCalibreeError):
        obtenir_adaptateur("Un gestionnaire jamais enregistré")


@pytest.mark.parametrize("adaptateur_cls", [AdaptateurArthurImmo, AdaptateurPergent, AdaptateurLocagestion])
def test_adaptateurs_non_calibres_levent_une_erreur_explicite(adaptateur_cls):
    """Aucun exemple réel de compte-rendu n'était disponible à l'écriture :
    les adaptateurs doivent échouer bruyamment plutôt que produire des
    données devinées et potentiellement fausses."""
    with pytest.raises(ExtractionNonCalibreeError):
        adaptateur_cls().extraire("un texte quelconque")
