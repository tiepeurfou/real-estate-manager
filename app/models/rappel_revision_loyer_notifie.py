from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class RappelRevisionLoyerNotifie(SQLModel, table=True):
    """Mémorise qu'une notification push (ntfy) a déjà été envoyée pour
    l'échéance annuelle de révision de loyer d'une occupation donnée, pour
    ne pas la re-notifier à chaque scan automatique (quotidien) tant qu'on
    est dans la fenêtre précédant la date anniversaire. Une ligne par
    (occupation, année d'échéance) : la même occupation génère une nouvelle
    échéance chaque année tant qu'elle reste active."""

    id: Optional[int] = Field(default=None, primary_key=True)
    occupation_id: int = Field(foreign_key="occupation.id")
    annee_echeance: int
    date_notification: datetime
