from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.compte_bancaire import CompteBancaire
    from app.models.gestionnaire import Gestionnaire
    from app.models.rapprochement import Rapprochement


class VirementRecu(SQLModel, table=True):
    """Virement déclaré manuellement par l'utilisateur (pas de connexion
    bancaire automatique — voir les décisions d'architecture du projet)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    gestionnaire_id: int = Field(foreign_key="gestionnaire.id")
    compte_bancaire_id: int = Field(foreign_key="comptebancaire.id")
    montant: float
    date_reception: date
    periode_couverte: Optional[date] = None
    notes: Optional[str] = None

    gestionnaire: "Gestionnaire" = Relationship(back_populates="virements")
    compte_bancaire: "CompteBancaire" = Relationship(back_populates="virements")
    rapprochement: Optional["Rapprochement"] = Relationship(back_populates="virement_recu")
