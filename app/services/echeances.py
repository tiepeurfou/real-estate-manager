from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from sqlmodel import Session, select

from app.models import Bien, Locataire, OccupationLocataire, UniteLocative
from app.services.dpe import unites_dpe_a_renouveler
from app.services.revision_loyer import occupations_a_reviser
from app.services.tableau_de_bord import AlerteImpaye, AlerteVirementManquant, calculer

FENETRE_JOURS_PAR_DEFAUT = 90


@dataclass
class EcheanceRevisionLoyer:
    occupation_id: int
    bien_libelle: str
    unite_libelle: str
    locataires_noms: str
    loyer_actuel: float
    date_echeance: date


@dataclass
class EcheanceDpe:
    unite_locative_id: int
    bien_libelle: str
    unite_libelle: str
    dpe_date: date
    date_expiration: date


@dataclass
class DonneesEcheances:
    revisions_loyer: list[EcheanceRevisionLoyer] = field(default_factory=list)
    dpe_a_renouveler: list[EcheanceDpe] = field(default_factory=list)
    impayes: list[AlerteImpaye] = field(default_factory=list)
    virements_manquants: list[AlerteVirementManquant] = field(default_factory=list)


def calculer_echeances(
    session: Session, aujourdhui: Optional[date] = None, fenetre_jours: int = FENETRE_JOURS_PAR_DEFAUT
) -> DonneesEcheances:
    """Vue centralisée de ce qui est déjà notifié individuellement par
    ntfy (révisions de loyer, DPE) ou déjà calculé pour le tableau de bord
    courant (impayés, virements manquants) — pour consulter ces échéances
    dans l'app sans dépendre uniquement des notifications sur le téléphone.
    `fenetre_jours` est volontairement plus large que les fenêtres de
    notification (30 jours pour le loyer, 90 pour le DPE) : la vue sert à
    anticiper sur plusieurs mois, pas seulement à réagir à une alerte
    imminente."""
    aujourdhui = aujourdhui or date.today()

    revisions = []
    for occupation, echeance, _annee in occupations_a_reviser(session, aujourdhui, fenetre_jours):
        unite = session.get(UniteLocative, occupation.unite_locative_id)
        bien = session.get(Bien, unite.bien_id) if unite else None
        liens = session.exec(
            select(OccupationLocataire).where(OccupationLocataire.occupation_id == occupation.id)
        ).all()
        locataires = [session.get(Locataire, lien.locataire_id) for lien in liens]
        noms = ", ".join(f"{l.prenom} {l.nom}" for l in locataires if l is not None)
        revisions.append(
            EcheanceRevisionLoyer(
                occupation_id=occupation.id,
                bien_libelle=bien.libelle if bien else "—",
                unite_libelle=unite.libelle if unite else "—",
                locataires_noms=noms,
                loyer_actuel=occupation.loyer_mensuel_hc,
                date_echeance=echeance,
            )
        )
    revisions.sort(key=lambda r: r.date_echeance)

    dpe_a_renouveler = []
    for unite, expiration in unites_dpe_a_renouveler(session, aujourdhui, fenetre_jours):
        bien = session.get(Bien, unite.bien_id)
        dpe_a_renouveler.append(
            EcheanceDpe(
                unite_locative_id=unite.id,
                bien_libelle=bien.libelle if bien else "—",
                unite_libelle=unite.libelle,
                dpe_date=unite.dpe_date,
                date_expiration=expiration,
            )
        )
    dpe_a_renouveler.sort(key=lambda d: d.date_expiration)

    donnees_tableau_de_bord = calculer(session, aujourdhui)

    return DonneesEcheances(
        revisions_loyer=revisions,
        dpe_a_renouveler=dpe_a_renouveler,
        impayes=donnees_tableau_de_bord.impayes,
        virements_manquants=donnees_tableau_de_bord.virements_manquants,
    )
