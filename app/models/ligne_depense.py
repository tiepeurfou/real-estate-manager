from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.bien import Bien
    from app.models.releve_gestion import ReleveGestion
    from app.models.unite_locative import UniteLocative


class LigneDepense(SQLModel, table=True):
    """Dépense extraite d'un relevé de gestion — rattachée à une unité, ou au
    bien entier si la dépense est commune (ex. ravalement d'un immeuble)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    releve_gestion_id: int = Field(foreign_key="relevegestion.id")
    unite_locative_id: Optional[int] = Field(default=None, foreign_key="unitelocative.id")
    bien_id: Optional[int] = Field(default=None, foreign_key="bien.id")
    categorie: str
    libelle: str
    montant: float
    date: date

    releve_gestion: "ReleveGestion" = Relationship(back_populates="lignes_depense")
    unite_locative: Optional["UniteLocative"] = Relationship(back_populates="depenses")
    bien: Optional["Bien"] = Relationship(back_populates="depenses")
