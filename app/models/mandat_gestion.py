from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import RoleMandat

if TYPE_CHECKING:
    from app.models.compte_bancaire import CompteBancaire
    from app.models.gestionnaire import Gestionnaire
    from app.models.unite_locative import UniteLocative


class MandatGestion(SQLModel, table=True):
    """Lien entre une unité locative et un gestionnaire pour un rôle donné.

    Une gestion locative complète (ex. ArthurImmo) se traduit par deux lignes
    distinctes (mise_en_location + gestion) plutôt qu'une valeur d'enum à part,
    pour garder des requêtes uniformes quel que soit le découpage des rôles.

    Le compte bancaire de versement est porté par le mandat (pas par le
    gestionnaire) : un même gestionnaire peut verser sur des comptes
    différents selon le bien géré (ex. Locagestion → compte A pour Sedan,
    compte B pour Charleville-Mézières). N'a de sens que pour un mandat de
    rôle `gestion` (la mise en location ne génère pas de versement).
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    unite_locative_id: int = Field(foreign_key="unitelocative.id")
    gestionnaire_id: int = Field(foreign_key="gestionnaire.id")
    role: RoleMandat
    date_debut: date
    date_fin: Optional[date] = None
    compte_bancaire_id: Optional[int] = Field(default=None, foreign_key="comptebancaire.id")

    unite_locative: "UniteLocative" = Relationship(back_populates="mandats")
    gestionnaire: "Gestionnaire" = Relationship(back_populates="mandats")
    compte_bancaire: Optional["CompteBancaire"] = Relationship(back_populates="mandats")
