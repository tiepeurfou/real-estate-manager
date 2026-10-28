from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import TypeContact

if TYPE_CHECKING:
    from app.models.gestionnaire import Gestionnaire


class ContactGestionnaire(SQLModel, table=True):
    """Un gestionnaire peut avoir plusieurs emails/téléphones (agence,
    gestionnaire dédié, urgences...) — d'où une table à part plutôt que
    deux champs fixes sur Gestionnaire."""

    id: Optional[int] = Field(default=None, primary_key=True)
    gestionnaire_id: int = Field(foreign_key="gestionnaire.id")
    type: TypeContact
    valeur: str
    libelle: Optional[str] = None

    gestionnaire: "Gestionnaire" = Relationship(back_populates="contacts")
