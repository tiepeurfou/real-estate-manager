from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class RappelDpeNotifie(SQLModel, table=True):
    """Mémorise qu'une notification push (ntfy) a déjà été envoyée pour
    l'expiration du DPE d'une unité, pour ne pas la re-notifier à chaque
    scan automatique (quotidien) tant qu'on est dans la fenêtre précédant
    l'expiration. La clé inclut `dpe_date` (pas seulement l'unité) : si le
    DPE est renouvelé (nouvelle date saisie sur l'unité), un nouveau cycle
    de notification redémarre naturellement pour cette nouvelle échéance."""

    id: Optional[int] = Field(default=None, primary_key=True)
    unite_locative_id: int = Field(foreign_key="unitelocative.id")
    dpe_date: date
    date_notification: datetime
