from datetime import date, datetime, timezone

from app.models import (
    Bien,
    Gestionnaire,
    LigneDepense,
    LignePaiement,
    MandatGestion,
    ReleveGestion,
    UniteLocative,
)
from app.models.enums import RoleMandat, StatutExtraction, StatutPaiement, TypeBien
from app.services.tableau_de_bord import calculer_par_type_pour_mois, calculer_pour_mois, libelle_mois_fr

AOUT = date(2024, 8, 1)
SEPTEMBRE = date(2024, 9, 1)


def _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan", type_bien=TypeBien.IMMEUBLE) -> tuple[Bien, UniteLocative]:
    bien = Bien(
        type=type_bien,
        libelle=libelle_bien,
        adresse_rue="1 rue Test",
        adresse_code_postal="08200",
        adresse_ville="Sedan",
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)
    unite = UniteLocative(bien_id=bien.id, libelle="Appt 1")
    session.add(unite)
    session.commit()
    session.refresh(unite)
    return bien, unite


def _creer_gestionnaire(session, nom="Locagestion") -> Gestionnaire:
    gestionnaire = Gestionnaire(nom=nom)
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    return gestionnaire


def _creer_releve(session, gestionnaire_id, bien_id, periode, statut=StatutExtraction.TRAITE_OK) -> ReleveGestion:
    releve = ReleveGestion(
        gestionnaire_id=gestionnaire_id,
        bien_id=bien_id,
        periode=periode,
        date_reception=datetime.now(timezone.utc),
        chemin_fichier_pdf="x.pdf",
        hash_fichier=f"hash-{gestionnaire_id}-{bien_id}-{periode}",
        statut_extraction=statut,
    )
    session.add(releve)
    session.commit()
    session.refresh(releve)
    return releve


def test_libelle_mois_fr():
    assert libelle_mois_fr(date(2024, 9, 1)) == "Septembre 2024"
    assert libelle_mois_fr(date(2024, 1, 15)) == "Janvier 2024"


def test_calculer_pour_mois_sans_donnees(session):
    donnees = calculer_pour_mois(session, SEPTEMBRE)

    assert donnees.periode == SEPTEMBRE
    assert donnees.loyers_attendus == 0
    assert donnees.loyers_percus == 0
    assert donnees.dettes_totales == 0
    assert donnees.depenses_totales == 0
    assert donnees.releves_recus == []
    assert donnees.gestionnaires_sans_releve == []


def test_calculer_pour_mois_filtre_les_loyers_par_periode_exacte(session):
    bien, unite = _creer_bien_avec_unite(session)
    gestionnaire = _creer_gestionnaire(session)
    releve = _creer_releve(session, gestionnaire.id, bien.id, SEPTEMBRE)

    session.add(
        LignePaiement(
            releve_gestion_id=releve.id, unite_locative_id=unite.id, periode=SEPTEMBRE,
            montant_attendu=500, montant_percu=500, statut=StatutPaiement.PAYE,
        )
    )
    session.add(
        LignePaiement(
            releve_gestion_id=releve.id, unite_locative_id=unite.id, periode=AOUT,
            montant_attendu=500, montant_percu=500, statut=StatutPaiement.PAYE,
        )
    )
    session.commit()

    donnees = calculer_pour_mois(session, SEPTEMBRE)

    assert donnees.loyers_attendus == 500
    assert donnees.loyers_percus == 500


def test_calculer_pour_mois_dette_en_coupe_distincte_du_mois_courant(session):
    # Le point clé de cette fonctionnalité : la dette d'août (impayé) ne
    # doit pas être "effacée" par le paiement de septembre quand on
    # consulte août — contrairement à la dette "actuelle" (dernière ligne
    # connue tout court) qui montrerait 0 pour les deux mois.
    bien, unite = _creer_bien_avec_unite(session)
    gestionnaire = _creer_gestionnaire(session)
    releve = _creer_releve(session, gestionnaire.id, bien.id, SEPTEMBRE)

    session.add(
        LignePaiement(
            releve_gestion_id=releve.id, unite_locative_id=unite.id, periode=AOUT,
            montant_attendu=500, montant_percu=0, statut=StatutPaiement.IMPAYE, dette_cumulee=500,
        )
    )
    session.add(
        LignePaiement(
            releve_gestion_id=releve.id, unite_locative_id=unite.id, periode=SEPTEMBRE,
            montant_attendu=500, montant_percu=500, statut=StatutPaiement.PAYE, dette_cumulee=0,
        )
    )
    session.commit()

    donnees_aout = calculer_pour_mois(session, AOUT)
    donnees_septembre = calculer_pour_mois(session, SEPTEMBRE)

    assert donnees_aout.dettes_totales == 500
    assert donnees_septembre.dettes_totales == 0


def test_calculer_pour_mois_depenses_par_categorie(session):
    bien, unite = _creer_bien_avec_unite(session)

    session.add(LigneDepense(bien_id=bien.id, categorie="Travaux", libelle="A", montant=100, date=date(2024, 9, 5)))
    session.add(LigneDepense(bien_id=bien.id, categorie="Travaux", libelle="B", montant=50, date=date(2024, 9, 20)))
    session.add(LigneDepense(bien_id=bien.id, categorie="Assurance", libelle="C", montant=80, date=date(2024, 9, 10)))
    session.add(LigneDepense(bien_id=bien.id, categorie="Travaux", libelle="Hors mois", montant=999, date=AOUT))
    session.commit()

    donnees = calculer_pour_mois(session, SEPTEMBRE)

    assert donnees.depenses_totales == 230
    par_categorie = {d.categorie: d.montant for d in donnees.depenses_par_categorie}
    assert par_categorie == {"Travaux": 150, "Assurance": 80}


def test_calculer_pour_mois_releves_recus(session):
    bien, unite = _creer_bien_avec_unite(session)
    gestionnaire = _creer_gestionnaire(session, nom="ArthurImmo")
    _creer_releve(session, gestionnaire.id, bien.id, SEPTEMBRE, statut=StatutExtraction.ERREUR_EXTRACTION)
    _creer_releve(session, gestionnaire.id, bien.id, AOUT)  # autre mois, ne doit pas apparaître

    donnees = calculer_pour_mois(session, SEPTEMBRE)

    assert len(donnees.releves_recus) == 1
    assert donnees.releves_recus[0].gestionnaire_nom == "ArthurImmo"
    assert donnees.releves_recus[0].bien_libelle == bien.libelle
    assert donnees.releves_recus[0].statut_extraction == StatutExtraction.ERREUR_EXTRACTION


def test_calculer_pour_mois_gestionnaire_sans_releve_est_signale(session):
    bien, unite = _creer_bien_avec_unite(session)
    gestionnaire = _creer_gestionnaire(session)
    session.add(
        MandatGestion(unite_locative_id=unite.id, gestionnaire_id=gestionnaire.id, role=RoleMandat.GESTION, date_debut=date(2024, 1, 1))
    )
    session.commit()

    donnees = calculer_pour_mois(session, SEPTEMBRE)

    assert len(donnees.gestionnaires_sans_releve) == 1
    assert donnees.gestionnaires_sans_releve[0].gestionnaire_nom == gestionnaire.nom
    assert donnees.gestionnaires_sans_releve[0].bien_libelle == bien.libelle


def test_calculer_pour_mois_gestionnaire_avec_releve_n_est_pas_signale(session):
    bien, unite = _creer_bien_avec_unite(session)
    gestionnaire = _creer_gestionnaire(session)
    session.add(
        MandatGestion(unite_locative_id=unite.id, gestionnaire_id=gestionnaire.id, role=RoleMandat.GESTION, date_debut=date(2024, 1, 1))
    )
    session.commit()
    _creer_releve(session, gestionnaire.id, bien.id, SEPTEMBRE)

    donnees = calculer_pour_mois(session, SEPTEMBRE)

    assert donnees.gestionnaires_sans_releve == []


def test_calculer_pour_mois_mandat_termine_avant_le_mois_n_est_pas_signale(session):
    bien, unite = _creer_bien_avec_unite(session)
    gestionnaire = _creer_gestionnaire(session)
    session.add(
        MandatGestion(
            unite_locative_id=unite.id, gestionnaire_id=gestionnaire.id, role=RoleMandat.GESTION,
            date_debut=date(2023, 1, 1), date_fin=date(2024, 7, 31),
        )
    )
    session.commit()

    donnees = calculer_pour_mois(session, SEPTEMBRE)

    assert donnees.gestionnaires_sans_releve == []


def test_calculer_pour_mois_mandat_mise_en_location_seul_n_est_pas_signale(session):
    bien, unite = _creer_bien_avec_unite(session)
    gestionnaire = _creer_gestionnaire(session)
    session.add(
        MandatGestion(unite_locative_id=unite.id, gestionnaire_id=gestionnaire.id, role=RoleMandat.MISE_EN_LOCATION, date_debut=date(2024, 1, 1))
    )
    session.commit()

    donnees = calculer_pour_mois(session, SEPTEMBRE)

    assert donnees.gestionnaires_sans_releve == []


def test_calculer_pour_mois_passage_d_annee_en_decembre(session):
    bien, unite = _creer_bien_avec_unite(session)
    decembre = date(2024, 12, 1)
    janvier_suivant = date(2025, 1, 1)

    session.add(LigneDepense(bien_id=bien.id, categorie="Travaux", libelle="décembre", montant=100, date=decembre))
    session.add(LigneDepense(bien_id=bien.id, categorie="Travaux", libelle="janvier suivant", montant=999, date=janvier_suivant))
    session.commit()

    donnees = calculer_pour_mois(session, decembre)

    assert donnees.depenses_totales == 100


def test_calculer_pour_mois_mandat_sur_un_autre_bien_filtre_n_est_pas_signale(session):
    bien1, unite1 = _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan")
    bien2, unite2 = _creer_bien_avec_unite(session, libelle_bien="Immeuble Charleville")
    gestionnaire = _creer_gestionnaire(session)
    session.add(
        MandatGestion(unite_locative_id=unite2.id, gestionnaire_id=gestionnaire.id, role=RoleMandat.GESTION, date_debut=date(2024, 1, 1))
    )
    session.commit()

    donnees = calculer_pour_mois(session, SEPTEMBRE, bien_id=bien1.id)

    assert donnees.gestionnaires_sans_releve == []


def test_calculer_pour_mois_filtre_par_bien(session):
    bien1, unite1 = _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan")
    bien2, unite2 = _creer_bien_avec_unite(session, libelle_bien="Immeuble Charleville")
    gestionnaire = _creer_gestionnaire(session)
    releve1 = _creer_releve(session, gestionnaire.id, bien1.id, SEPTEMBRE)
    releve2 = _creer_releve(session, gestionnaire.id, bien2.id, SEPTEMBRE)

    session.add(
        LignePaiement(releve_gestion_id=releve1.id, unite_locative_id=unite1.id, periode=SEPTEMBRE, montant_attendu=500, montant_percu=500, statut=StatutPaiement.PAYE)
    )
    session.add(
        LignePaiement(releve_gestion_id=releve2.id, unite_locative_id=unite2.id, periode=SEPTEMBRE, montant_attendu=700, montant_percu=700, statut=StatutPaiement.PAYE)
    )
    session.commit()

    donnees = calculer_pour_mois(session, SEPTEMBRE, bien_id=bien1.id)

    assert donnees.loyers_attendus == 500
    assert len(donnees.releves_recus) == 1
    assert donnees.releves_recus[0].bien_libelle == "Immeuble Sedan"


def test_calculer_pour_mois_residence_principale_visible_si_filtree_explicitement(session):
    residence = Bien(
        type=TypeBien.RESIDENCE_PRINCIPALE, libelle="Maison", adresse_rue="r", adresse_code_postal="08000", adresse_ville="V"
    )
    session.add(residence)
    session.commit()
    session.refresh(residence)
    session.add(LigneDepense(bien_id=residence.id, categorie="Crédit immobilier", libelle="x", montant=900, date=SEPTEMBRE))
    session.commit()

    donnees_globales = calculer_pour_mois(session, SEPTEMBRE)
    donnees_residence = calculer_pour_mois(session, SEPTEMBRE, bien_id=residence.id)

    assert donnees_globales.depenses_totales == 0
    assert donnees_residence.depenses_totales == 900


def test_calculer_par_type_pour_mois_agrege_par_type(session):
    bien1, unite1 = _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan", type_bien=TypeBien.IMMEUBLE)
    bien2, unite2 = _creer_bien_avec_unite(session, libelle_bien="Immeuble Charleville", type_bien=TypeBien.IMMEUBLE)
    bien3, unite3 = _creer_bien_avec_unite(session, libelle_bien="Villiers", type_bien=TypeBien.APPARTEMENT_ISOLE)
    gestionnaire = _creer_gestionnaire(session)
    for bien, unite in [(bien1, unite1), (bien2, unite2), (bien3, unite3)]:
        releve = _creer_releve(session, gestionnaire.id, bien.id, SEPTEMBRE)
        session.add(
            LignePaiement(releve_gestion_id=releve.id, unite_locative_id=unite.id, periode=SEPTEMBRE, montant_attendu=500, montant_percu=500, statut=StatutPaiement.PAYE)
        )
    session.commit()

    resultats = calculer_par_type_pour_mois(session, SEPTEMBRE)
    par_type = {r.type_bien: r for r in resultats}

    assert par_type[TypeBien.IMMEUBLE].loyers_attendus == 1000
    assert par_type[TypeBien.APPARTEMENT_ISOLE].loyers_attendus == 500


def test_calculer_par_type_pour_mois_inclut_la_residence_principale(session):
    residence = Bien(
        type=TypeBien.RESIDENCE_PRINCIPALE, libelle="Maison", adresse_rue="r", adresse_code_postal="08000", adresse_ville="V"
    )
    session.add(residence)
    session.commit()
    session.refresh(residence)
    session.add(LigneDepense(bien_id=residence.id, categorie="Crédit immobilier", libelle="x", montant=900, date=SEPTEMBRE))
    session.commit()

    resultats = calculer_par_type_pour_mois(session, SEPTEMBRE)
    par_type = {r.type_bien: r for r in resultats}

    assert TypeBien.RESIDENCE_PRINCIPALE in par_type
    assert par_type[TypeBien.RESIDENCE_PRINCIPALE].depenses_totales == 900


def test_calculer_par_type_pour_mois_depense_rattachee_a_une_unite(session):
    # Une dépense rattachée à une unité (pas directement au bien) doit
    # quand même être reclassée sous le bon type via l'unité.
    bien, unite = _creer_bien_avec_unite(session, type_bien=TypeBien.APPARTEMENT_ISOLE)
    session.add(LigneDepense(unite_locative_id=unite.id, categorie="Travaux", libelle="x", montant=75, date=SEPTEMBRE))
    session.commit()

    resultats = calculer_par_type_pour_mois(session, SEPTEMBRE)
    par_type = {r.type_bien: r for r in resultats}

    assert par_type[TypeBien.APPARTEMENT_ISOLE].depenses_totales == 75


def test_calculer_par_type_pour_mois_omet_les_types_absents(session):
    _creer_bien_avec_unite(session, type_bien=TypeBien.IMMEUBLE)

    resultats = calculer_par_type_pour_mois(session, SEPTEMBRE)
    types_presents = {r.type_bien for r in resultats}

    assert types_presents == {TypeBien.IMMEUBLE}
