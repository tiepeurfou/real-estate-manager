from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from app.config import DPE_FENETRE_JOURS
from app.models import Bien, RappelDpeNotifie, UniteLocative
from app.services.notifications import ErreurNotification, envoyer_notification

DUREE_VALIDITE_DPE_ANNEES = 10


def _date_expiration(dpe_date: date) -> date:
    try:
        return date(dpe_date.year + DUREE_VALIDITE_DPE_ANNEES, dpe_date.month, dpe_date.day)
    except ValueError:
        # 29 février : l'année d'expiration n'est pas forcément bissextile.
        return date(dpe_date.year + DUREE_VALIDITE_DPE_ANNEES, dpe_date.month, 28)


def unites_dpe_a_renouveler(
    session: Session, aujourdhui: Optional[date] = None, fenetre_jours: Optional[int] = None
) -> list[tuple[UniteLocative, date]]:
    """Unités dont le DPE (valide 10 ans) expire dans `fenetre_jours` jours
    — ou a déjà expiré. N'inclut que les unités avec une `dpe_date`
    renseignée (le champ est optionnel sur `UniteLocative`)."""
    aujourdhui = aujourdhui or date.today()
    fenetre_jours = fenetre_jours if fenetre_jours is not None else DPE_FENETRE_JOURS

    unites = session.exec(select(UniteLocative).where(UniteLocative.dpe_date.is_not(None))).all()
    resultat = []
    for unite in unites:
        expiration = _date_expiration(unite.dpe_date)
        if (expiration - aujourdhui).days <= fenetre_jours:
            resultat.append((unite, expiration))
    return resultat


def notifier_dpe_a_renouveler(session: Session, aujourdhui: Optional[date] = None) -> list[UniteLocative]:
    """Envoie une notification push pour chaque unité dont le DPE approche
    de l'expiration et n'a pas déjà été notifiée pour cette `dpe_date`
    précise (une ligne `RappelDpeNotifie` par (unité, date du diagnostic) —
    si le DPE est renouvelé, la nouvelle date redémarre un cycle de
    notification). Si l'envoi échoue, l'unité n'est pas marquée notifiée :
    on retentera au prochain scan plutôt que de perdre le rappel."""
    aujourdhui = aujourdhui or date.today()
    unites_concernees = unites_dpe_a_renouveler(session, aujourdhui)

    deja_notifiees = {(r.unite_locative_id, r.dpe_date) for r in session.exec(select(RappelDpeNotifie)).all()}

    notifiees: list[UniteLocative] = []
    for unite, expiration in unites_concernees:
        if (unite.id, unite.dpe_date) in deja_notifiees:
            continue
        bien = session.get(Bien, unite.bien_id)
        bien_libelle = bien.libelle if bien else "—"
        try:
            envoyer_notification(
                titre="DPE à renouveler",
                message=(
                    f"{bien_libelle} — {unite.libelle} : DPE du {unite.dpe_date.isoformat()} "
                    f"expire le {expiration.isoformat()}"
                ),
            )
        except ErreurNotification:
            continue
        session.add(
            RappelDpeNotifie(
                unite_locative_id=unite.id,
                dpe_date=unite.dpe_date,
                date_notification=datetime.now(timezone.utc),
            )
        )
        notifiees.append(unite)

    session.commit()
    return notifiees
