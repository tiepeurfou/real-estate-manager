from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import Banque

if TYPE_CHECKING:
    from app.models.gestionnaire import Gestionnaire
    from app.models.virement_recu import VirementRecu


class CompteBancaire(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    banque: Banque
    libelle: str
    iban: Optional[str] = None

    gestionnaires: list["Gestionnaire"] = Relationship(back_populates="compte_bancaire")
    virements: list["VirementRecu"] = Relationship(back_populates="compte_bancaire")
