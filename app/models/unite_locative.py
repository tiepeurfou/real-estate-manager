from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import DpeLettre

if TYPE_CHECKING:
    from app.models.bien import Bien
    from app.models.ligne_depense import LigneDepense
    from app.models.ligne_paiement import LignePaiement
    from app.models.mandat_gestion import MandatGestion
    from app.models.occupation import Occupation


class UniteLocative(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    bien_id: int = Field(foreign_key="bien.id")
    libelle: str
    etage: Optional[str] = None
    surface_m2: Optional[float] = None
    nb_pieces: Optional[int] = None
    dpe_lettre: Optional[DpeLettre] = None
    dpe_date: Optional[date] = None
    regime_fiscal: Optional[str] = None

    bien: "Bien" = Relationship(back_populates="unites")
    mandats: list["MandatGestion"] = Relationship(back_populates="unite_locative")
    occupations: list["Occupation"] = Relationship(back_populates="unite_locative")
    lignes_paiement: list["LignePaiement"] = Relationship(back_populates="unite_locative")
    depenses: list["LigneDepense"] = Relationship(back_populates="unite_locative")
