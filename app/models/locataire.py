from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import TypeGarantie

if TYPE_CHECKING:
    from app.models.ligne_paiement import LignePaiement
    from app.models.occupation_locataire import OccupationLocataire


class Locataire(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    prenom: str
    email: Optional[str] = None
    telephone: Optional[str] = None
    type_garantie: TypeGarantie = TypeGarantie.AUCUNE
    garant_nom: Optional[str] = None
    garant_contact: Optional[str] = None

    occupations: list["OccupationLocataire"] = Relationship(back_populates="locataire")
    lignes_paiement: list["LignePaiement"] = Relationship(back_populates="locataire")
