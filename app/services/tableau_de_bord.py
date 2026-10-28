from dataclasses import dataclass, field
from datetime import date

from sqlmodel import Session, select

from app.models import (
    Bien,
    Gestionnaire,
    LigneDepense,
    LignePaiement,
    MandatGestion,
    Occupation,
    ReleveGestion,
    UniteLocative,
    VirementRecu,
)
from app.models.enums import RoleMandat, StatutExtraction, StatutOccupation, StatutPaiement


@dataclass
class TuileBien:
    bien_id: int
    libelle: str
    nb_unites: int
    nb_occupees: int
    en_alerte: bool


@dataclass
class AlerteUniteVacante:
    bien_libelle: str
    unite_libelle: str


@dataclass
class AlerteImpaye:
    bien_libelle: str
    unite_libelle: str
    periode: date
    montant_du: float


@dataclass
class AlerteReleveEnErreur:
    releve_gestion_id: int
    gestionnaire_nom: str
    bien_libelle: str
    message: str


@dataclass
class AlerteVirementManquant:
    gestionnaire_nom: str


@dataclass
class DonneesFinancesBien:
    bien_id: int
    loyers_attendus_mois: float = 0.0
    loyers_percus_mois: float = 0.0
    dettes_totales: float = 0.0
    depenses_mois: float = 0.0


@dataclass
class DonneesTableauDeBord:
    nb_biens: int = 0
    nb_unites: int = 0
    nb_unites_occupees: int = 0
    taux_occupation: float = 0.0
    loyers_attendus_mois: float = 0.0
    loyers_percus_mois: float = 0.0
    dettes_totales: float = 0.0
    depenses_mois: float = 0.0
    tuiles_biens: list[TuileBien] = field(default_factory=list)
    unites_vacantes: list[AlerteUniteVacante] = field(default_factory=list)
    impayes: list[AlerteImpaye] = field(default_factory=list)
    releves_en_erreur: list[AlerteReleveEnErreur] = field(default_factory=list)
    virements_manquants: list[AlerteVirementManquant] = field(default_factory=list)


def _dernieres_lignes_par_unite(lignes: list[LignePaiement]) -> dict[int, LignePaiement]:
    dernieres: dict[int, LignePaiement] = {}
    for ligne in lignes:
        actuelle = dernieres.get(ligne.unite_locative_id)
        if actuelle is None or ligne.periode > actuelle.periode:
            dernieres[ligne.unite_locative_id] = ligne
    return dernieres


def calculer_pour_bien(session: Session, bien_id: int, aujourdhui: date | None = None) -> DonneesFinancesBien:
    """Même logique que `calculer()` mais limitée aux unités d'un seul bien —
    la vision globale du tableau de bord ne dit rien de la rentabilité d'un
    bien précis, utile quand le patrimoine compte plusieurs immeubles."""
    aujourdhui = aujourdhui or date.today()
    periode_courante = date(aujourdhui.year, aujourdhui.month, 1)

    unite_ids = [
        u.id for u in session.exec(select(UniteLocative).where(UniteLocative.bien_id == bien_id)).all()
    ]

    lignes_paiement = (
        session.exec(select(LignePaiement).where(LignePaiement.unite_locative_id.in_(unite_ids))).all()
        if unite_ids
        else []
    )
    lignes_mois = [l for l in lignes_paiement if l.periode == periode_courante]
    dernieres_lignes = _dernieres_lignes_par_unite(lignes_paiement)

    condition_depense = LigneDepense.bien_id == bien_id
    if unite_ids:
        condition_depense = condition_depense | LigneDepense.unite_locative_id.in_(unite_ids)
    lignes_depense = session.exec(select(LigneDepense).where(condition_depense)).all()
    depenses_mois = [
        d for d in lignes_depense if d.date.year == periode_courante.year and d.date.month == periode_courante.month
    ]

    return DonneesFinancesBien(
        bien_id=bien_id,
        loyers_attendus_mois=sum(l.montant_attendu for l in lignes_mois),
        loyers_percus_mois=sum(l.montant_percu for l in lignes_mois),
        dettes_totales=sum(l.dette_cumulee for l in dernieres_lignes.values() if l.dette_cumulee > 0),
        depenses_mois=sum(d.montant for d in depenses_mois),
    )


def calculer(session: Session, aujourdhui: date | None = None) -> DonneesTableauDeBord:
    aujourdhui = aujourdhui or date.today()
    periode_courante = date(aujourdhui.year, aujourdhui.month, 1)

    biens = session.exec(select(Bien)).all()
    unites = session.exec(select(UniteLocative)).all()
    biens_par_id = {b.id: b for b in biens}

    unites_occupees_ids = {
        o.unite_locative_id for o in session.exec(select(Occupation).where(Occupation.statut == StatutOccupation.ACTIVE)).all()
    }

    toutes_lignes_paiement = session.exec(select(LignePaiement)).all()
    lignes_mois = [l for l in toutes_lignes_paiement if l.periode == periode_courante]
    dernieres_lignes = _dernieres_lignes_par_unite(toutes_lignes_paiement)

    toutes_depenses = session.exec(select(LigneDepense)).all()
    depenses_mois = [
        d for d in toutes_depenses if d.date.year == periode_courante.year and d.date.month == periode_courante.month
    ]

    releves_en_erreur_db = session.exec(
        select(ReleveGestion).where(ReleveGestion.statut_extraction == StatutExtraction.ERREUR_EXTRACTION)
    ).all()
    gestionnaires_par_id = {g.id: g for g in session.exec(select(Gestionnaire)).all()}

    donnees = DonneesTableauDeBord(
        nb_biens=len(biens),
        nb_unites=len(unites),
        nb_unites_occupees=len(unites_occupees_ids & {u.id for u in unites}),
        loyers_attendus_mois=sum(l.montant_attendu for l in lignes_mois),
        loyers_percus_mois=sum(l.montant_percu for l in lignes_mois),
        dettes_totales=sum(l.dette_cumulee for l in dernieres_lignes.values() if l.dette_cumulee > 0),
        depenses_mois=sum(d.montant for d in depenses_mois),
    )
    donnees.taux_occupation = donnees.nb_unites_occupees / donnees.nb_unites if donnees.nb_unites else 0.0

    for unite in unites:
        if unite.id not in unites_occupees_ids:
            bien = biens_par_id.get(unite.bien_id)
            donnees.unites_vacantes.append(
                AlerteUniteVacante(bien_libelle=bien.libelle if bien else "—", unite_libelle=unite.libelle)
            )

    for ligne in dernieres_lignes.values():
        if ligne.statut in (StatutPaiement.IMPAYE, StatutPaiement.PARTIEL) and ligne.dette_cumulee > 0:
            unite = next((u for u in unites if u.id == ligne.unite_locative_id), None)
            bien = biens_par_id.get(unite.bien_id) if unite else None
            donnees.impayes.append(
                AlerteImpaye(
                    bien_libelle=bien.libelle if bien else "—",
                    unite_libelle=unite.libelle if unite else "—",
                    periode=ligne.periode,
                    montant_du=ligne.dette_cumulee,
                )
            )

    for releve in releves_en_erreur_db:
        gestionnaire = gestionnaires_par_id.get(releve.gestionnaire_id)
        bien = biens_par_id.get(releve.bien_id)
        donnees.releves_en_erreur.append(
            AlerteReleveEnErreur(
                releve_gestion_id=releve.id,
                gestionnaire_nom=gestionnaire.nom if gestionnaire else "—",
                bien_libelle=bien.libelle if bien else "—",
                message=releve.erreur_extraction_message or "",
            )
        )

    mandats_gestion_actifs = session.exec(
        select(MandatGestion).where(
            MandatGestion.role == RoleMandat.GESTION,
            (MandatGestion.date_fin.is_(None)) | (MandatGestion.date_fin >= aujourdhui),
        )
    ).all()
    gestionnaires_a_surveiller = {m.gestionnaire_id for m in mandats_gestion_actifs}

    virements_du_mois = session.exec(select(VirementRecu)).all()
    gestionnaires_avec_virement_ce_mois = {
        v.gestionnaire_id
        for v in virements_du_mois
        if v.date_reception.year == periode_courante.year and v.date_reception.month == periode_courante.month
    }

    for gestionnaire_id in gestionnaires_a_surveiller - gestionnaires_avec_virement_ce_mois:
        gestionnaire = gestionnaires_par_id.get(gestionnaire_id)
        donnees.virements_manquants.append(AlerteVirementManquant(gestionnaire_nom=gestionnaire.nom if gestionnaire else "—"))

    unites_par_bien: dict[int, list[UniteLocative]] = {}
    for unite in unites:
        unites_par_bien.setdefault(unite.bien_id, []).append(unite)

    biens_en_alerte_impaye = {
        u.bien_id
        for u in unites
        for ligne in [dernieres_lignes.get(u.id)]
        if ligne is not None and ligne.statut in (StatutPaiement.IMPAYE, StatutPaiement.PARTIEL) and ligne.dette_cumulee > 0
    }
    biens_en_alerte_releve = {releve.bien_id for releve in releves_en_erreur_db}

    for bien in biens:
        unites_du_bien = unites_par_bien.get(bien.id, [])
        nb_occupees = sum(1 for u in unites_du_bien if u.id in unites_occupees_ids)
        en_alerte = (
            nb_occupees < len(unites_du_bien) or bien.id in biens_en_alerte_impaye or bien.id in biens_en_alerte_releve
        )
        donnees.tuiles_biens.append(
            TuileBien(
                bien_id=bien.id,
                libelle=bien.libelle,
                nb_unites=len(unites_du_bien),
                nb_occupees=nb_occupees,
                en_alerte=en_alerte,
            )
        )

    return donnees
