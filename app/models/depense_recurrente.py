from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import FrequenceDepense

if TYPE_CHECKING:
    from app.models.bien import Bien
    from app.models.ligne_depense import LigneDepense
    from app.models.unite_locative import UniteLocative


class DepenseRecurrente(SQLModel, table=True):
    """Modèle d'une dépense qui revient régulièrement (crédit immobilier,
    électricité des parties communes...) : définie une fois, elle permet de
    générer les LigneDepense dues plutôt que de les ressaisir à la main
    chaque mois. Le jour de récurrence est celui de date_debut (clampé au
    dernier jour du mois si besoin, ex. le 31 pour un mois à 30 jours).
    Pas de champ "actif" séparé : une dépense récurrente est active tant que
    date_fin est vide ou dans le futur — même convention que MandatGestion."""

    id: Optional[int] = Field(default=None, primary_key=True)
    bien_id: int = Field(foreign_key="bien.id")
    unite_locative_id: Optional[int] = Field(default=None, foreign_key="unitelocative.id")
    categorie: str
    libelle: str
    montant: float
    frequence: FrequenceDepense
    date_debut: date
    date_fin: Optional[date] = None

    bien: "Bien" = Relationship()
    unite_locative: Optional["UniteLocative"] = Relationship()
    lignes_generees: list["LigneDepense"] = Relationship(back_populates="depense_recurrente")
