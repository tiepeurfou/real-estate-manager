from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Utilisateur(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True)
    mot_de_passe_hash: str
    derniere_connexion: Optional[datetime] = None
