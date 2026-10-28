from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.bien import Bien
    from app.models.depense_recurrente import DepenseRecurrente
    from app.models.releve_gestion import ReleveGestion
    from app.models.unite_locative import UniteLocative


class LigneDepense(SQLModel, table=True):
    """Dépense rattachée à une unité, ou au bien entier si la dépense est
    commune (ex. ravalement d'un immeuble). Trois origines possibles :
    extraite d'un relevé de gestion (releve_gestion_id), générée depuis un
    modèle récurrent (depense_recurrente_id — ex. crédit immobilier,
    électricité des parties communes), ou saisie manuellement ponctuelle
    (les deux à None — ex. taxe foncière)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    releve_gestion_id: Optional[int] = Field(default=None, foreign_key="relevegestion.id")
    depense_recurrente_id: Optional[int] = Field(default=None, foreign_key="depenserecurrente.id")
    unite_locative_id: Optional[int] = Field(default=None, foreign_key="unitelocative.id")
    bien_id: Optional[int] = Field(default=None, foreign_key="bien.id")
    categorie: str
    libelle: str
    montant: float
    date: date

    releve_gestion: Optional["ReleveGestion"] = Relationship(back_populates="lignes_depense")
    depense_recurrente: Optional["DepenseRecurrente"] = Relationship(back_populates="lignes_generees")
    unite_locative: Optional["UniteLocative"] = Relationship(back_populates="depenses")
    bien: Optional["Bien"] = Relationship(back_populates="depenses")
