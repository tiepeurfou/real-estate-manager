from calendar import monthrange
from datetime import date
from typing import Optional

from sqlmodel import Session, select

from app.models import DepenseRecurrente, LigneDepense
from app.models.enums import FrequenceDepense

PAS_PAR_FREQUENCE = {
    FrequenceDepense.MENSUELLE: 1,
    FrequenceDepense.TRIMESTRIELLE: 3,
    FrequenceDepense.ANNUELLE: 12,
}


def _ajouter_mois(reference: date, mois: int) -> date:
    total = reference.month - 1 + mois
    annee = reference.year + total // 12
    mois_resultat = total % 12 + 1
    jour_max = monthrange(annee, mois_resultat)[1]
    return date(annee, mois_resultat, min(reference.day, jour_max))


def periodes_dues(
    date_debut: date,
    date_fin: Optional[date],
    frequence: FrequenceDepense,
    aujourdhui: date,
) -> list[date]:
    """Dates d'échéance dues entre date_debut et aujourdhui (ou date_fin si
    plus tôt), au pas de la fréquence. Le jour du mois est toujours celui de
    date_debut (ex. le 31), clampé seulement pour les mois trop courts — sans
    glisser définitivement : après un février qui clampe au 28, mars revient
    bien au 31. D'où le calcul depuis date_debut à chaque échéance plutôt
    qu'en chaînant depuis la précédente."""
    limite = aujourdhui if date_fin is None else min(date_fin, aujourdhui)
    if date_debut > limite:
        return []

    pas = PAS_PAR_FREQUENCE[frequence]
    echeances = []
    n = 0
    while True:
        echeance = _ajouter_mois(date_debut, pas * n)
        if echeance > limite:
            break
        echeances.append(echeance)
        n += 1
    return echeances


def generer_echeances_dues(session: Session, aujourdhui: Optional[date] = None) -> list[LigneDepense]:
    """Crée les LigneDepense dues pour chaque dépense récurrente active, en
    évitant les doublons (comparaison par date exacte déjà générée pour ce
    modèle). Idempotent : peut être appelée autant de fois que voulu."""
    aujourdhui = aujourdhui or date.today()
    nouvelles_lignes: list[LigneDepense] = []

    templates = session.exec(select(DepenseRecurrente)).all()
    for template in templates:
        dates_deja_generees = {
            l.date
            for l in session.exec(
                select(LigneDepense).where(LigneDepense.depense_recurrente_id == template.id)
            ).all()
        }
        for echeance in periodes_dues(template.date_debut, template.date_fin, template.frequence, aujourdhui):
            if echeance in dates_deja_generees:
                continue
            ligne = LigneDepense(
                depense_recurrente_id=template.id,
                unite_locative_id=template.unite_locative_id,
                bien_id=template.bien_id if template.unite_locative_id is None else None,
                categorie=template.categorie,
                libelle=template.libelle,
                montant=template.montant,
                date=echeance,
            )
            session.add(ligne)
            nouvelles_lignes.append(ligne)

    session.commit()
    return nouvelles_lignes
