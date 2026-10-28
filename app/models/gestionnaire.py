from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.contact_gestionnaire import ContactGestionnaire
    from app.models.mandat_gestion import MandatGestion
    from app.models.releve_gestion import ReleveGestion
    from app.models.virement_recu import VirementRecu


class Gestionnaire(SQLModel, table=True):
    """Pas de compte bancaire ici : un même gestionnaire peut verser sur des
    comptes différents selon le bien (ex. Locagestion verse sur un compte
    pour Sedan, un autre pour Charleville-Mézières) — le compte est donc
    attaché au mandat (gestionnaire + unité), voir MandatGestion.

    Pas de champ email/téléphone fixe non plus : un gestionnaire peut avoir
    plusieurs contacts (agence, gestionnaire dédié, urgences...) — voir
    ContactGestionnaire."""

    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str

    contacts: list["ContactGestionnaire"] = Relationship(back_populates="gestionnaire")
    mandats: list["MandatGestion"] = Relationship(back_populates="gestionnaire")
    releves_gestion: list["ReleveGestion"] = Relationship(back_populates="gestionnaire")
    virements: list["VirementRecu"] = Relationship(back_populates="gestionnaire")
