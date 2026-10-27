from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import RoleMandat

if TYPE_CHECKING:
    from app.models.gestionnaire import Gestionnaire
    from app.models.unite_locative import UniteLocative


class MandatGestion(SQLModel, table=True):
    """Lien entre une unité locative et un gestionnaire pour un rôle donné.

    Une gestion locative complète (ex. ArthurImmo) se traduit par deux lignes
    distinctes (mise_en_location + gestion) plutôt qu'une valeur d'enum à part,
    pour garder des requêtes uniformes quel que soit le découpage des rôles.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    unite_locative_id: int = Field(foreign_key="unitelocative.id")
    gestionnaire_id: int = Field(foreign_key="gestionnaire.id")
    role: RoleMandat
    date_debut: date
    date_fin: Optional[date] = None

    unite_locative: "UniteLocative" = Relationship(back_populates="mandats")
    gestionnaire: "Gestionnaire" = Relationship(back_populates="mandats")
