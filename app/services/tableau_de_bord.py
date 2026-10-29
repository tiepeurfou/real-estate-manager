from dataclasses import dataclass, field
from datetime import date
from typing import Optional

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
from app.models.enums import RoleMandat, StatutExtraction, StatutOccupation, StatutPaiement, TypeBien


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
class DepenseParCategorie:
    categorie: str
    montant: float


@dataclass
class ReleveDuMois:
    releve_gestion_id: int
    gestionnaire_nom: str
    bien_libelle: str
    statut_extraction: StatutExtraction


@dataclass
class GestionnaireSansReleve:
    gestionnaire_nom: str
    bien_libelle: str


@dataclass
class DonneesMensuelles:
    periode: date
    bien_id: Optional[int] = None
    loyers_attendus: float = 0.0
    loyers_percus: float = 0.0
    dettes_totales: float = 0.0
    depenses_totales: float = 0.0
    depenses_par_categorie: list[DepenseParCategorie] = field(default_factory=list)
    releves_recus: list[ReleveDuMois] = field(default_factory=list)
    gestionnaires_sans_releve: list[GestionnaireSansReleve] = field(default_factory=list)


@dataclass
class DonneesMensuellesParType:
    type_bien: TypeBien
    loyers_attendus: float = 0.0
    loyers_percus: float = 0.0
    dettes_totales: float = 0.0
    depenses_totales: float = 0.0


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


NOMS_MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def libelle_mois_fr(periode: date) -> str:
    return f"{NOMS_MOIS_FR[periode.month - 1].capitalize()} {periode.year}"


def _premier_du_mois_suivant(periode: date) -> date:
    if periode.month == 12:
        return date(periode.year + 1, 1, 1)
    return date(periode.year, periode.month + 1, 1)


def calculer_pour_mois(session: Session, periode: date, bien_id: Optional[int] = None) -> DonneesMensuelles:
    """Vue rétrospective d'un mois donné (passé ou courant) : loyers,
    impayés, dépenses, et réception des comptes-rendus de gestion.

    Contrairement à `calculer()`/`calculer_pour_bien()` qui donnent la
    situation "aujourd'hui", la dette ici est calculée **en coupe à la fin
    du mois demandé** : on ne retient que les `LignePaiement` dont la
    période est <= au mois demandé avant de prendre la dernière connue par
    unité. Sans ce filtre, consulter un mois passé afficherait des impayés
    plus récents que ce mois — trompeur pour un historique.
    """
    periode = date(periode.year, periode.month, 1)
    debut_mois = periode
    fin_mois = _premier_du_mois_suivant(periode)

    if bien_id is not None:
        unite_ids = [u.id for u in session.exec(select(UniteLocative).where(UniteLocative.bien_id == bien_id)).all()]
        lignes_paiement = (
            session.exec(select(LignePaiement).where(LignePaiement.unite_locative_id.in_(unite_ids))).all()
            if unite_ids
            else []
        )
        condition_depense = LigneDepense.bien_id == bien_id
        if unite_ids:
            condition_depense = condition_depense | LigneDepense.unite_locative_id.in_(unite_ids)
        lignes_depense = session.exec(select(LigneDepense).where(condition_depense)).all()
    else:
        lignes_paiement = session.exec(select(LignePaiement)).all()
        ids_residences_principales = {
            b.id for b in session.exec(select(Bien).where(Bien.type == TypeBien.RESIDENCE_PRINCIPALE)).all()
        }
        lignes_depense = [
            d for d in session.exec(select(LigneDepense)).all() if d.bien_id not in ids_residences_principales
        ]

    lignes_du_mois = [l for l in lignes_paiement if l.periode == periode]
    lignes_jusqu_a_ce_mois = [l for l in lignes_paiement if l.periode <= periode]
    dernieres_lignes_en_coupe = _dernieres_lignes_par_unite(lignes_jusqu_a_ce_mois)

    depenses_du_mois = [d for d in lignes_depense if debut_mois <= d.date < fin_mois]
    totaux_par_categorie: dict[str, float] = {}
    for d in depenses_du_mois:
        totaux_par_categorie[d.categorie] = totaux_par_categorie.get(d.categorie, 0.0) + d.montant

    gestionnaires_par_id = {g.id: g for g in session.exec(select(Gestionnaire)).all()}
    biens_par_id = {b.id: b for b in session.exec(select(Bien)).all()}

    requete_releves = select(ReleveGestion).where(ReleveGestion.periode == periode)
    if bien_id is not None:
        requete_releves = requete_releves.where(ReleveGestion.bien_id == bien_id)
    releves_db = session.exec(requete_releves).all()

    releves_recus = [
        ReleveDuMois(
            releve_gestion_id=r.id,
            gestionnaire_nom=(gestionnaires_par_id.get(r.gestionnaire_id).nom if gestionnaires_par_id.get(r.gestionnaire_id) else "—"),
            bien_libelle=(biens_par_id.get(r.bien_id).libelle if biens_par_id.get(r.bien_id) else "—"),
            statut_extraction=r.statut_extraction,
        )
        for r in releves_db
    ]

    # Gestionnaires dont un mandat de gestion était actif à un moment de ce
    # mois (chevauchement d'intervalles), pour le bien demandé (ou tous),
    # sans compte-rendu reçu pour cette période précise sur ce bien.
    unites_par_id = {u.id: u for u in session.exec(select(UniteLocative)).all()}
    mandats_gestion_actifs = session.exec(
        select(MandatGestion).where(
            MandatGestion.role == RoleMandat.GESTION,
            MandatGestion.date_debut < fin_mois,
            (MandatGestion.date_fin.is_(None)) | (MandatGestion.date_fin >= debut_mois),
        )
    ).all()
    couples_attendus: set[tuple[int, int]] = set()
    for m in mandats_gestion_actifs:
        unite = unites_par_id.get(m.unite_locative_id)
        if unite is None or (bien_id is not None and unite.bien_id != bien_id):
            continue
        couples_attendus.add((m.gestionnaire_id, unite.bien_id))

    couples_recus = {(r.gestionnaire_id, r.bien_id) for r in releves_db}
    gestionnaires_sans_releve = [
        GestionnaireSansReleve(
            gestionnaire_nom=(gestionnaires_par_id.get(gid).nom if gestionnaires_par_id.get(gid) else "—"),
            bien_libelle=(biens_par_id.get(bid).libelle if biens_par_id.get(bid) else "—"),
        )
        for gid, bid in sorted(couples_attendus - couples_recus)
    ]

    return DonneesMensuelles(
        periode=periode,
        bien_id=bien_id,
        loyers_attendus=sum(l.montant_attendu for l in lignes_du_mois),
        loyers_percus=sum(l.montant_percu for l in lignes_du_mois),
        dettes_totales=sum(l.dette_cumulee for l in dernieres_lignes_en_coupe.values() if l.dette_cumulee > 0),
        depenses_totales=sum(d.montant for d in depenses_du_mois),
        depenses_par_categorie=[
            DepenseParCategorie(categorie=c, montant=m) for c, m in sorted(totaux_par_categorie.items())
        ],
        releves_recus=releves_recus,
        gestionnaires_sans_releve=gestionnaires_sans_releve,
    )


def calculer_par_type_pour_mois(session: Session, periode: date) -> list[DonneesMensuellesParType]:
    """Agrège les mêmes métriques que `calculer_pour_mois()` mais regroupées
    par type de bien (appartement_isole / immeuble / residence_principale) —
    pour comparer par exemple les deux immeubles à l'appartement isolé sur
    un même mois sans additionner les biens à la main. Ne filtre rien par
    défaut (y compris la résidence principale, contrairement à `calculer()`
    global) puisque le classement par type la distingue déjà naturellement."""
    periode = date(periode.year, periode.month, 1)
    debut_mois = periode
    fin_mois = _premier_du_mois_suivant(periode)

    biens = session.exec(select(Bien)).all()
    types_presents = [t for t in TypeBien if any(b.type == t for b in biens)]
    resultats = {t: DonneesMensuellesParType(type_bien=t) for t in types_presents}

    unites = session.exec(select(UniteLocative)).all()
    bien_id_par_unite_id = {u.id: u.bien_id for u in unites}
    type_par_bien_id = {b.id: b.type for b in biens}

    lignes_paiement = session.exec(select(LignePaiement)).all()
    lignes_du_mois = [l for l in lignes_paiement if l.periode == periode]
    lignes_jusqu_a_ce_mois = [l for l in lignes_paiement if l.periode <= periode]
    dernieres_lignes_en_coupe = _dernieres_lignes_par_unite(lignes_jusqu_a_ce_mois)

    for ligne in lignes_du_mois:
        bien_id = bien_id_par_unite_id.get(ligne.unite_locative_id)
        type_bien = type_par_bien_id.get(bien_id)
        if type_bien not in resultats:
            continue
        resultats[type_bien].loyers_attendus += ligne.montant_attendu
        resultats[type_bien].loyers_percus += ligne.montant_percu

    for ligne in dernieres_lignes_en_coupe.values():
        if ligne.dette_cumulee <= 0:
            continue
        bien_id = bien_id_par_unite_id.get(ligne.unite_locative_id)
        type_bien = type_par_bien_id.get(bien_id)
        if type_bien not in resultats:
            continue
        resultats[type_bien].dettes_totales += ligne.dette_cumulee

    for depense in session.exec(select(LigneDepense)).all():
        if not (debut_mois <= depense.date < fin_mois):
            continue
        bien_id = depense.bien_id
        if bien_id is None and depense.unite_locative_id is not None:
            bien_id = bien_id_par_unite_id.get(depense.unite_locative_id)
        type_bien = type_par_bien_id.get(bien_id)
        if type_bien not in resultats:
            continue
        resultats[type_bien].depenses_totales += depense.montant

    return [resultats[t] for t in types_presents]


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

    # Une résidence principale n'est pas un bien locatif (pas d'unité, jamais
    # de locataire) : elle est exclue des métriques de patrimoine locatif
    # (nb_biens, tuiles, taux d'occupation) pour ne pas les fausser, même si
    # ses propres dépenses restent consultables sur sa page de détail
    # (calculer_pour_bien, qui ne fait pas cette distinction).
    tous_les_biens = session.exec(select(Bien)).all()
    biens_par_id = {b.id: b for b in tous_les_biens}
    biens = [b for b in tous_les_biens if b.type != TypeBien.RESIDENCE_PRINCIPALE]
    ids_residences_principales = {b.id for b in tous_les_biens if b.type == TypeBien.RESIDENCE_PRINCIPALE}
    unites = session.exec(select(UniteLocative)).all()

    unites_occupees_ids = {
        o.unite_locative_id for o in session.exec(select(Occupation).where(Occupation.statut == StatutOccupation.ACTIVE)).all()
    }

    toutes_lignes_paiement = session.exec(select(LignePaiement)).all()
    lignes_mois = [l for l in toutes_lignes_paiement if l.periode == periode_courante]
    dernieres_lignes = _dernieres_lignes_par_unite(toutes_lignes_paiement)

    toutes_depenses = [
        d for d in session.exec(select(LigneDepense)).all() if d.bien_id not in ids_residences_principales
    ]
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
