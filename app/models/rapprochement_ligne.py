from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.ligne_depense import LigneDepense
    from app.models.ligne_paiement import LignePaiement
    from app.models.rapprochement import Rapprochement


class RapprochementLigne(SQLModel, table=True):
    """Ligne de détail d'un rapprochement : pointe soit vers une ligne de
    paiement, soit vers une ligne de dépense (jamais les deux)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    rapprochement_id: int = Field(foreign_key="rapprochement.id")
    ligne_paiement_id: Optional[int] = Field(default=None, foreign_key="lignepaiement.id")
    ligne_depense_id: Optional[int] = Field(default=None, foreign_key="lignedepense.id")

    rapprochement: "Rapprochement" = Relationship(back_populates="lignes")
    ligne_paiement: Optional["LignePaiement"] = Relationship()
    ligne_depense: Optional["LigneDepense"] = Relationship()
