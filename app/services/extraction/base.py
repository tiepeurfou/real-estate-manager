from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Protocol

from app.models.enums import StatutPaiement


class ExtractionNonCalibreeError(Exception):
    """Levée quand aucune règle d'extraction fiable n'existe encore pour un
    gestionnaire donné (pas d'exemple réel de document pour la calibrer)."""


@dataclass
class LignePaiementExtraite:
    unite_libelle: str
    periode: date
    montant_attendu: float
    montant_percu: float
    statut: StatutPaiement


@dataclass
class LigneDepenseExtraite:
    categorie: str
    libelle: str
    montant: float
    date: date
    unite_libelle: Optional[str] = None


@dataclass
class ResultatExtraction:
    paiements: list[LignePaiementExtraite] = field(default_factory=list)
    depenses: list[LigneDepenseExtraite] = field(default_factory=list)


class AdaptateurExtraction(Protocol):
    """Contrat commun : transforme le texte brut d'un compte-rendu de gestion
    en lignes de paiement/dépense structurées, à charge pour l'appelant de
    les rattacher aux unités locatives (par libellé) et de les persister."""

    def extraire(self, texte: str) -> ResultatExtraction: ...
