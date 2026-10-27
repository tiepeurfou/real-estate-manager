from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.compte_bancaire import CompteBancaire
    from app.models.mandat_gestion import MandatGestion
    from app.models.releve_gestion import ReleveGestion
    from app.models.virement_recu import VirementRecu


class Gestionnaire(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    contact_email: Optional[str] = None
    contact_tel: Optional[str] = None
    compte_bancaire_id: Optional[int] = Field(default=None, foreign_key="comptebancaire.id")

    compte_bancaire: Optional["CompteBancaire"] = Relationship(back_populates="gestionnaires")
    mandats: list["MandatGestion"] = Relationship(back_populates="gestionnaire")
    releves_gestion: list["ReleveGestion"] = Relationship(back_populates="gestionnaire")
    virements: list["VirementRecu"] = Relationship(back_populates="gestionnaire")
