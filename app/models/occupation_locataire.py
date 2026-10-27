from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.locataire import Locataire
    from app.models.occupation import Occupation


class OccupationLocataire(SQLModel, table=True):
    """Liaison N:N entre Occupation et Locataire — permet la colocation
    (plusieurs locataires sur une même occupation d'une unité)."""

    occupation_id: Optional[int] = Field(default=None, foreign_key="occupation.id", primary_key=True)
    locataire_id: Optional[int] = Field(default=None, foreign_key="locataire.id", primary_key=True)

    occupation: "Occupation" = Relationship(back_populates="locataires")
    locataire: "Locataire" = Relationship(back_populates="occupations")
