from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import StatutCandidatCourriel


class CandidatCourrielTraite(SQLModel, table=True):
    """Marque une pièce jointe PDF d'un mail de la boîte dédiée comme déjà
    traitée (importée ou écartée), pour ne pas la re-proposer à chaque
    triage. La boîte recevant tout le courrier personnel transféré, le tri
    se fait manuellement — pas de classification automatique par expéditeur."""

    id: Optional[int] = Field(default=None, primary_key=True)
    message_uid: str
    nom_piece_jointe: str
    statut: StatutCandidatCourriel
    date_traitement: datetime
    releve_gestion_id: Optional[int] = Field(default=None, foreign_key="relevegestion.id")
