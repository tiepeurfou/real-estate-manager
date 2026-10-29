from datetime import date, datetime, timezone

from app.models import (
    Bien,
    Gestionnaire,
    LigneDepense,
    LignePaiement,
    Locataire,
    Occupation,
    OccupationLocataire,
    ReleveGestion,
    UniteLocative,
)
from app.models.enums import StatutExtraction, StatutOccupation, StatutPaiement, TypeBien
from app.services.tableau_de_bord import calculer_par_type_pour_annee, calculer_pour_annee


def _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan", type_bien=TypeBien.IMMEUBLE, numero_fiscal=None) -> tuple[Bien, UniteLocative]:
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
    unite = UniteLocative(bien_id=bien.id, libelle="Appt 1", numero_fiscal=numero_fiscal)
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


def _creer_releve(session, gestionnaire_id, bien_id, periode) -> ReleveGestion:
    releve = ReleveGestion(
        gestionnaire_id=gestionnaire_id,
        bien_id=bien_id,
        periode=periode,
        date_reception=datetime.now(timezone.utc),
        chemin_fichier_pdf="x.pdf",
        hash_fichier=f"hash-{gestionnaire_id}-{bien_id}-{periode}",
        statut_extraction=StatutExtraction.TRAITE_OK,
    )
    session.add(releve)
    session.commit()
    session.refresh(releve)
    return releve


def _creer_locataire(session, nom="Dupont", prenom="Jean", date_naissance=None) -> Locataire:
    locataire = Locataire(nom=nom, prenom=prenom, date_naissance=date_naissance)
    session.add(locataire)
    session.commit()
    session.refresh(locataire)
    return locataire


def _attribuer(session, unite_id, locataire_id, date_entree, date_sortie=None, statut=StatutOccupation.ACTIVE):
    occupation = Occupation(unite_locative_id=unite_id, date_entree=date_entree, date_sortie=date_sortie, loyer_mensuel_hc=500, statut=statut)
    session.add(occupation)
    session.commit()
    session.refresh(occupation)
    session.add(OccupationLocataire(occupation_id=occupation.id, locataire_id=locataire_id))
    session.commit()
    return occupation


def test_calculer_pour_annee_sans_donnees(session):
    donnees = calculer_pour_annee(session, 2024)

    assert donnees.annee == 2024
    assert donnees.loyers_attendus == 0
    assert donnees.loyers_percus == 0
    assert donnees.dettes_fin_annee == 0
    assert donnees.depenses_totales == 0
    assert donnees.locataires_actifs == []
    assert donnees.unites_concernees == []


def test_calculer_pour_annee_filtre_les_loyers_par_annee_exacte(session):
    bien, unite = _creer_bien_avec_unite(session)
    gestionnaire = _creer_gestionnaire(session)
    releve = _creer_releve(session, gestionnaire.id, bien.id, date(2024, 6, 1))

    session.add(
        LignePaiement(releve_gestion_id=releve.id, unite_locative_id=unite.id, periode=date(2024, 6, 1), montant_attendu=500, montant_percu=500, statut=StatutPaiement.PAYE)
    )
    session.add(
        LignePaiement(releve_gestion_id=releve.id, unite_locative_id=unite.id, periode=date(2023, 12, 1), montant_attendu=400, montant_percu=400, statut=StatutPaiement.PAYE)
    )
    session.commit()

    donnees = calculer_pour_annee(session, 2024)

    assert donnees.loyers_attendus == 500
    assert donnees.loyers_percus == 500


def test_calculer_pour_annee_dette_en_coupe_pour_une_annee_passee(session):
    bien, unite = _creer_bien_avec_unite(session)
    gestionnaire = _creer_gestionnaire(session)
    releve = _creer_releve(session, gestionnaire.id, bien.id, date(2024, 1, 1))

    # Impayé en 2023, régularisé en 2024 : consulter 2023 doit montrer la
    # dette telle qu'elle était alors, pas "effacée" par le paiement 2024.
    session.add(
        LignePaiement(releve_gestion_id=releve.id, unite_locative_id=unite.id, periode=date(2023, 12, 1), montant_attendu=500, montant_percu=0, statut=StatutPaiement.IMPAYE, dette_cumulee=500)
    )
    session.add(
        LignePaiement(releve_gestion_id=releve.id, unite_locative_id=unite.id, periode=date(2024, 1, 1), montant_attendu=500, montant_percu=500, statut=StatutPaiement.PAYE, dette_cumulee=0)
    )
    session.commit()

    donnees_2023 = calculer_pour_annee(session, 2023)
    donnees_2024 = calculer_pour_annee(session, 2024)

    assert donnees_2023.dettes_fin_annee == 500
    assert donnees_2024.dettes_fin_annee == 0


def test_calculer_pour_annee_courante_borne_la_dette_au_mois_actuel(session):
    bien, unite = _creer_bien_avec_unite(session)
    gestionnaire = _creer_gestionnaire(session)
    releve = _creer_releve(session, gestionnaire.id, bien.id, date(2024, 3, 1))

    annee_courante = date.today().year
    session.add(
        LignePaiement(releve_gestion_id=releve.id, unite_locative_id=unite.id, periode=date(annee_courante, 1, 1), montant_attendu=500, montant_percu=0, statut=StatutPaiement.IMPAYE, dette_cumulee=500)
    )
    session.commit()

    donnees = calculer_pour_annee(session, annee_courante)

    assert donnees.dettes_fin_annee == 500


def test_calculer_pour_annee_depenses_par_categorie(session):
    bien, unite = _creer_bien_avec_unite(session)

    session.add(LigneDepense(bien_id=bien.id, categorie="Travaux", libelle="A", montant=100, date=date(2024, 3, 5)))
    session.add(LigneDepense(bien_id=bien.id, categorie="Travaux", libelle="B", montant=50, date=date(2024, 11, 20)))
    session.add(LigneDepense(bien_id=bien.id, categorie="Assurance", libelle="C", montant=80, date=date(2024, 6, 10)))
    session.add(LigneDepense(bien_id=bien.id, categorie="Travaux", libelle="Hors année", montant=999, date=date(2023, 12, 31)))
    session.commit()

    donnees = calculer_pour_annee(session, 2024)

    assert donnees.depenses_totales == 230
    par_categorie = {d.categorie: d.montant for d in donnees.depenses_par_categorie}
    assert par_categorie == {"Travaux": 150, "Assurance": 80}


def test_calculer_pour_annee_locataire_dont_occupation_chevauche_l_annee(session):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session, date_naissance=date(1990, 1, 1))
    _attribuer(session, unite.id, locataire.id, date_entree=date(2023, 6, 1), date_sortie=date(2024, 3, 1), statut=StatutOccupation.TERMINEE)

    donnees = calculer_pour_annee(session, 2024)

    assert len(donnees.locataires_actifs) == 1
    assert donnees.locataires_actifs[0].nom == "Dupont"
    assert donnees.locataires_actifs[0].date_naissance == date(1990, 1, 1)


def test_calculer_pour_annee_locataire_toujours_actif_sans_date_sortie(session):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)
    _attribuer(session, unite.id, locataire.id, date_entree=date(2022, 1, 1))

    donnees = calculer_pour_annee(session, 2024)

    assert len(donnees.locataires_actifs) == 1


def test_calculer_pour_annee_locataire_parti_avant_l_annee_est_exclu(session):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)
    _attribuer(session, unite.id, locataire.id, date_entree=date(2022, 1, 1), date_sortie=date(2023, 6, 1), statut=StatutOccupation.TERMINEE)

    donnees = calculer_pour_annee(session, 2024)

    assert donnees.locataires_actifs == []


def test_calculer_pour_annee_locataire_arrive_apres_l_annee_est_exclu(session):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)
    _attribuer(session, unite.id, locataire.id, date_entree=date(2025, 1, 1))

    donnees = calculer_pour_annee(session, 2024)

    assert donnees.locataires_actifs == []


def test_calculer_pour_annee_unites_concernees_avec_numero_fiscal(session):
    bien, unite = _creer_bien_avec_unite(session, numero_fiscal="1234567A")
    locataire = _creer_locataire(session)
    _attribuer(session, unite.id, locataire.id, date_entree=date(2024, 1, 1))

    donnees = calculer_pour_annee(session, 2024)

    assert len(donnees.unites_concernees) == 1
    assert donnees.unites_concernees[0].numero_fiscal == "1234567A"
    assert donnees.unites_concernees[0].bien_libelle == bien.libelle


def test_calculer_pour_annee_filtre_par_bien(session):
    bien1, unite1 = _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan")
    bien2, unite2 = _creer_bien_avec_unite(session, libelle_bien="Immeuble Charleville")
    gestionnaire = _creer_gestionnaire(session)
    releve1 = _creer_releve(session, gestionnaire.id, bien1.id, date(2024, 6, 1))
    releve2 = _creer_releve(session, gestionnaire.id, bien2.id, date(2024, 6, 1))

    session.add(LignePaiement(releve_gestion_id=releve1.id, unite_locative_id=unite1.id, periode=date(2024, 6, 1), montant_attendu=500, montant_percu=500, statut=StatutPaiement.PAYE))
    session.add(LignePaiement(releve_gestion_id=releve2.id, unite_locative_id=unite2.id, periode=date(2024, 6, 1), montant_attendu=700, montant_percu=700, statut=StatutPaiement.PAYE))
    session.commit()

    donnees = calculer_pour_annee(session, 2024, bien_id=bien1.id)

    assert donnees.loyers_attendus == 500


def test_calculer_pour_annee_residence_principale_visible_si_filtree(session):
    residence = Bien(type=TypeBien.RESIDENCE_PRINCIPALE, libelle="Maison", adresse_rue="r", adresse_code_postal="08000", adresse_ville="V")
    session.add(residence)
    session.commit()
    session.refresh(residence)
    session.add(LigneDepense(bien_id=residence.id, categorie="Crédit immobilier", libelle="x", montant=900, date=date(2024, 6, 1)))
    session.commit()

    donnees_globales = calculer_pour_annee(session, 2024)
    donnees_residence = calculer_pour_annee(session, 2024, bien_id=residence.id)

    assert donnees_globales.depenses_totales == 0
    assert donnees_residence.depenses_totales == 900


def test_calculer_par_type_pour_annee_agrege_par_type(session):
    bien1, unite1 = _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan", type_bien=TypeBien.IMMEUBLE)
    bien2, unite2 = _creer_bien_avec_unite(session, libelle_bien="Villiers", type_bien=TypeBien.APPARTEMENT_ISOLE)
    gestionnaire = _creer_gestionnaire(session)
    for bien, unite in [(bien1, unite1), (bien2, unite2)]:
        releve = _creer_releve(session, gestionnaire.id, bien.id, date(2024, 6, 1))
        session.add(LignePaiement(releve_gestion_id=releve.id, unite_locative_id=unite.id, periode=date(2024, 6, 1), montant_attendu=500, montant_percu=500, statut=StatutPaiement.PAYE))
    session.commit()

    resultats = calculer_par_type_pour_annee(session, 2024)
    par_type = {r.type_bien: r for r in resultats}

    assert par_type[TypeBien.IMMEUBLE].loyers_attendus == 500
    assert par_type[TypeBien.APPARTEMENT_ISOLE].loyers_attendus == 500


def test_calculer_par_type_pour_annee_inclut_la_residence_principale(session):
    residence = Bien(type=TypeBien.RESIDENCE_PRINCIPALE, libelle="Maison", adresse_rue="r", adresse_code_postal="08000", adresse_ville="V")
    session.add(residence)
    session.commit()
    session.refresh(residence)
    session.add(LigneDepense(bien_id=residence.id, categorie="Crédit immobilier", libelle="x", montant=900, date=date(2024, 6, 1)))
    session.commit()

    resultats = calculer_par_type_pour_annee(session, 2024)
    par_type = {r.type_bien: r for r in resultats}

    assert par_type[TypeBien.RESIDENCE_PRINCIPALE].depenses_totales == 900


def test_calculer_par_type_pour_annee_omet_les_types_absents(session):
    _creer_bien_avec_unite(session, type_bien=TypeBien.IMMEUBLE)

    resultats = calculer_par_type_pour_annee(session, 2024)
    types_presents = {r.type_bien for r in resultats}

    assert types_presents == {TypeBien.IMMEUBLE}
