from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import StatutPaiement

if TYPE_CHECKING:
    from app.models.locataire import Locataire
    from app.models.releve_gestion import ReleveGestion
    from app.models.unite_locative import UniteLocative


class LignePaiement(SQLModel, table=True):
    """Ligne de loyer extraite d'un relevé de gestion pour une unité et un mois donnés."""

    id: Optional[int] = Field(default=None, primary_key=True)
    releve_gestion_id: int = Field(foreign_key="relevegestion.id")
    unite_locative_id: int = Field(foreign_key="unitelocative.id")
    locataire_id: Optional[int] = Field(default=None, foreign_key="locataire.id")
    periode: date
    montant_attendu: float
    montant_percu: float = 0
    statut: StatutPaiement
    dette_cumulee: float = 0

    releve_gestion: "ReleveGestion" = Relationship(back_populates="lignes_paiement")
    unite_locative: "UniteLocative" = Relationship(back_populates="lignes_paiement")
    locataire: Optional["Locataire"] = Relationship(back_populates="lignes_paiement")
