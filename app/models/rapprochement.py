from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.rapprochement_ligne import RapprochementLigne
    from app.models.virement_recu import VirementRecu


class Rapprochement(SQLModel, table=True):
    """Rapprochement d'un virement reçu avec les lignes de paiement/dépense
    qu'il couvre. Un virement a au plus un rapprochement."""

    id: Optional[int] = Field(default=None, primary_key=True)
    virement_recu_id: int = Field(foreign_key="virementrecu.id", unique=True)
    ecart: float = 0

    virement_recu: "VirementRecu" = Relationship(back_populates="rapprochement")
    lignes: list["RapprochementLigne"] = Relationship(back_populates="rapprochement")
