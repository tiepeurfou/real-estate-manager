from calendar import monthrange
from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from app.config import REVISION_LOYER_FENETRE_JOURS
from app.models import Bien, Locataire, Occupation, OccupationLocataire, RappelRevisionLoyerNotifie, UniteLocative
from app.models.enums import StatutOccupation
from app.services.notifications import ErreurNotification, envoyer_notification


def _anniversaire(date_entree: date, annee: int) -> date:
    jour_max = monthrange(annee, date_entree.month)[1]
    return date(annee, date_entree.month, min(date_entree.day, jour_max))


def _prochaine_echeance(date_entree: date, aujourdhui: date) -> tuple[date, int]:
    """La prochaine date anniversaire du bail à partir d'aujourd'hui — jamais
    celle de l'année de signature elle-même, qui n'est pas une révision."""
    annee = max(aujourdhui.year, date_entree.year + 1)
    echeance = _anniversaire(date_entree, annee)
    if echeance < aujourdhui:
        annee += 1
        echeance = _anniversaire(date_entree, annee)
    return echeance, annee


def occupations_a_reviser(
    session: Session, aujourdhui: Optional[date] = None, fenetre_jours: Optional[int] = None
) -> list[tuple[Occupation, date, int]]:
    """Occupations actives dont la prochaine date anniversaire du bail tombe
    dans les `fenetre_jours` jours à venir. Seul repère disponible pour un
    rappel de révision annuelle (IRL) : il n'existe pas d'historique des
    révisions déjà effectuées (`Occupation.loyer_mensuel_hc` ne garde que la
    valeur actuelle) — la révision se fait de toute façon toujours à date
    anniversaire du bail, qu'une révision ait ou non déjà eu lieu entre
    deux anniversaires."""
    aujourdhui = aujourdhui or date.today()
    fenetre_jours = fenetre_jours if fenetre_jours is not None else REVISION_LOYER_FENETRE_JOURS

    occupations = session.exec(select(Occupation).where(Occupation.statut == StatutOccupation.ACTIVE)).all()
    resultat = []
    for occupation in occupations:
        echeance, annee_echeance = _prochaine_echeance(occupation.date_entree, aujourdhui)
        if (echeance - aujourdhui).days <= fenetre_jours:
            resultat.append((occupation, echeance, annee_echeance))
    return resultat


def _description_occupation(session: Session, occupation: Occupation) -> str:
    unite = session.get(UniteLocative, occupation.unite_locative_id)
    bien = session.get(Bien, unite.bien_id) if unite else None
    liens = session.exec(
        select(OccupationLocataire).where(OccupationLocataire.occupation_id == occupation.id)
    ).all()
    locataires = [session.get(Locataire, lien.locataire_id) for lien in liens]
    noms = ", ".join(f"{l.prenom} {l.nom}" for l in locataires if l is not None)
    bien_libelle = bien.libelle if bien else "—"
    unite_libelle = unite.libelle if unite else "—"
    base = f"{bien_libelle} — {unite_libelle}"
    return f"{base} ({noms})" if noms else base


def notifier_revisions_a_venir(session: Session, aujourdhui: Optional[date] = None) -> list[Occupation]:
    """Envoie une notification push pour chaque occupation dont la date
    anniversaire approche et n'a pas déjà été notifiée pour cette échéance
    précise (une ligne `RappelRevisionLoyerNotifie` par (occupation, année) —
    une même occupation génère une nouvelle échéance chaque année). Si
    l'envoi échoue, l'occupation n'est pas marquée notifiée : on retentera
    au prochain scan plutôt que de perdre silencieusement le rappel."""
    aujourdhui = aujourdhui or date.today()
    occupations_concernees = occupations_a_reviser(session, aujourdhui)

    deja_notifiees = {
        (r.occupation_id, r.annee_echeance) for r in session.exec(select(RappelRevisionLoyerNotifie)).all()
    }

    notifiees: list[Occupation] = []
    for occupation, echeance, annee_echeance in occupations_concernees:
        if (occupation.id, annee_echeance) in deja_notifiees:
            continue
        description = _description_occupation(session, occupation)
        try:
            envoyer_notification(
                titre="Révision de loyer à prévoir",
                message=(
                    f"{description} : loyer actuel {occupation.loyer_mensuel_hc:.0f} € HC, "
                    f"anniversaire du bail le {echeance.isoformat()}"
                ),
            )
        except ErreurNotification:
            continue
        session.add(
            RappelRevisionLoyerNotifie(
                occupation_id=occupation.id,
                annee_echeance=annee_echeance,
                date_notification=datetime.now(timezone.utc),
            )
        )
        notifiees.append(occupation)

    session.commit()
    return notifiees
