from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class CandidatCourrielNotifie(SQLModel, table=True):
    """Mémorise qu'une notification push (ntfy) a déjà été envoyée pour
    cette pièce jointe candidate, pour ne pas la re-notifier à chaque scan
    automatique de la boîte mail (toutes les N heures) tant qu'elle n'a pas
    été triée. Distinct de `CandidatCourrielTraite` : un candidat peut rester
    notifié plusieurs scans avant d'être importé/ignoré, mais ne doit
    déclencher qu'une seule notification."""

    id: Optional[int] = Field(default=None, primary_key=True)
    message_uid: str
    nom_piece_jointe: str
    date_notification: datetime
