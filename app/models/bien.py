from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import TypeBien

if TYPE_CHECKING:
    from app.models.ligne_depense import LigneDepense
    from app.models.releve_gestion import ReleveGestion
    from app.models.unite_locative import UniteLocative


class Bien(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    type: TypeBien
    libelle: str
    adresse_rue: str
    adresse_code_postal: str
    adresse_ville: str
    date_acquisition: Optional[date] = None
    notes: Optional[str] = None

    unites: list["UniteLocative"] = Relationship(back_populates="bien")
    releves_gestion: list["ReleveGestion"] = Relationship(back_populates="bien")
    depenses: list["LigneDepense"] = Relationship(back_populates="bien")
