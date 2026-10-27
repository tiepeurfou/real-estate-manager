from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import StatutOccupation

if TYPE_CHECKING:
    from app.models.occupation_locataire import OccupationLocataire
    from app.models.unite_locative import UniteLocative


class Occupation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    unite_locative_id: int = Field(foreign_key="unitelocative.id")
    date_entree: date
    date_sortie: Optional[date] = None
    loyer_mensuel_hc: float
    charges_mensuelles: float = 0
    depot_garantie: Optional[float] = None
    statut: StatutOccupation = StatutOccupation.ACTIVE

    unite_locative: "UniteLocative" = Relationship(back_populates="occupations")
    locataires: list["OccupationLocataire"] = Relationship(back_populates="occupation")
