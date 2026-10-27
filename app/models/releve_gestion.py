from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import StatutExtraction

if TYPE_CHECKING:
    from app.models.bien import Bien
    from app.models.gestionnaire import Gestionnaire
    from app.models.ligne_depense import LigneDepense
    from app.models.ligne_paiement import LignePaiement


class ReleveGestion(SQLModel, table=True):
    """Document (PDF) reçu par mail d'un gestionnaire pour une période donnée."""

    id: Optional[int] = Field(default=None, primary_key=True)
    gestionnaire_id: int = Field(foreign_key="gestionnaire.id")
    bien_id: int = Field(foreign_key="bien.id")
    periode: date
    date_reception: datetime
    chemin_fichier_pdf: str
    email_source_id: Optional[str] = None
    hash_fichier: str = Field(unique=True)
    statut_extraction: StatutExtraction = StatutExtraction.NON_TRAITE

    gestionnaire: "Gestionnaire" = Relationship(back_populates="releves_gestion")
    bien: "Bien" = Relationship(back_populates="releves_gestion")
    lignes_paiement: list["LignePaiement"] = Relationship(back_populates="releve_gestion")
    lignes_depense: list["LigneDepense"] = Relationship(back_populates="releve_gestion")
