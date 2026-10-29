from datetime import date, datetime, timezone

from app.models import (
    Bien,
    Gestionnaire,
    LignePaiement,
    Locataire,
    MandatGestion,
    Occupation,
    OccupationLocataire,
    ReleveGestion,
    UniteLocative,
)
from app.models.enums import DpeLettre, RoleMandat, StatutExtraction, StatutOccupation, StatutPaiement, TypeBien
from app.services.echeances import calculer_echeances


def _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan", dpe_date=None) -> tuple[Bien, UniteLocative]:
    bien = Bien(
        type=TypeBien.IMMEUBLE,
        libelle=libelle_bien,
        adresse_rue="1 rue Test",
        adresse_code_postal="08200",
        adresse_ville="Sedan",
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)
    unite = UniteLocative(bien_id=bien.id, libelle="Appt 1", dpe_lettre=DpeLettre.D if dpe_date else None, dpe_date=dpe_date)
    session.add(unite)
    session.commit()
    session.refresh(unite)
    return bien, unite


def _creer_locataire(session, nom="Dupont", prenom="Jean") -> Locataire:
    locataire = Locataire(nom=nom, prenom=prenom)
    session.add(locataire)
    session.commit()
    session.refresh(locataire)
    return locataire


def _attribuer(session, unite_id, locataire_id, date_entree, loyer=500) -> Occupation:
    occupation = Occupation(unite_locative_id=unite_id, date_entree=date_entree, loyer_mensuel_hc=loyer, statut=StatutOccupation.ACTIVE)
    session.add(occupation)
    session.commit()
    session.refresh(occupation)
    session.add(OccupationLocataire(occupation_id=occupation.id, locataire_id=locataire_id))
    session.commit()
    return occupation


def test_calculer_echeances_sans_donnees(session):
    donnees = calculer_echeances(session, aujourdhui=date(2026, 10, 29))

    assert donnees.revisions_loyer == []
    assert donnees.dpe_a_renouveler == []
    assert donnees.impayes == []
    assert donnees.virements_manquants == []


def test_calculer_echeances_inclut_une_revision_de_loyer_proche(session):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)
    _attribuer(session, unite.id, locataire.id, date_entree=date(2024, 11, 20), loyer=500)

    donnees = calculer_echeances(session, aujourdhui=date(2026, 10, 29), fenetre_jours=90)

    assert len(donnees.revisions_loyer) == 1
    revision = donnees.revisions_loyer[0]
    assert revision.bien_libelle == bien.libelle
    assert revision.locataires_noms == "Jean Dupont"
    assert revision.loyer_actuel == 500
    assert revision.date_echeance == date(2026, 11, 20)


def test_calculer_echeances_exclut_une_revision_hors_fenetre(session):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)
    _attribuer(session, unite.id, locataire.id, date_entree=date(2024, 6, 1))

    donnees = calculer_echeances(session, aujourdhui=date(2026, 10, 29), fenetre_jours=30)

    assert donnees.revisions_loyer == []


def test_calculer_echeances_inclut_un_dpe_a_renouveler(session):
    bien, unite = _creer_bien_avec_unite(session, dpe_date=date(2016, 8, 15))

    donnees = calculer_echeances(session, aujourdhui=date(2026, 6, 1), fenetre_jours=90)

    assert len(donnees.dpe_a_renouveler) == 1
    dpe = donnees.dpe_a_renouveler[0]
    assert dpe.bien_libelle == bien.libelle
    assert dpe.dpe_date == date(2016, 8, 15)
    assert dpe.date_expiration == date(2026, 8, 15)


def test_calculer_echeances_tri_les_revisions_par_date(session):
    bien1, unite1 = _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan")
    bien2, unite2 = _creer_bien_avec_unite(session, libelle_bien="Immeuble Charleville")
    locataire1 = _creer_locataire(session, nom="Dupont")
    locataire2 = _creer_locataire(session, nom="Martin")
    _attribuer(session, unite1.id, locataire1.id, date_entree=date(2024, 12, 15))  # échéance 2026-12-15
    _attribuer(session, unite2.id, locataire2.id, date_entree=date(2024, 11, 1))  # échéance 2026-11-01

    donnees = calculer_echeances(session, aujourdhui=date(2026, 10, 29), fenetre_jours=90)

    assert [r.date_echeance for r in donnees.revisions_loyer] == [date(2026, 11, 1), date(2026, 12, 15)]


def test_calculer_echeances_inclut_les_impayes_du_tableau_de_bord(session):
    bien, unite = _creer_bien_avec_unite(session)
    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    releve = ReleveGestion(
        gestionnaire_id=gestionnaire.id, bien_id=bien.id, periode=date(2026, 10, 1),
        date_reception=datetime.now(timezone.utc), chemin_fichier_pdf="x.pdf", hash_fichier="h1",
        statut_extraction=StatutExtraction.TRAITE_OK,
    )
    session.add(releve)
    session.commit()
    session.refresh(releve)
    session.add(
        LignePaiement(releve_gestion_id=releve.id, unite_locative_id=unite.id, periode=date(2026, 10, 1), montant_attendu=500, montant_percu=200, statut=StatutPaiement.PARTIEL, dette_cumulee=300)
    )
    session.commit()

    donnees = calculer_echeances(session, aujourdhui=date(2026, 10, 29))

    assert len(donnees.impayes) == 1
    assert donnees.impayes[0].montant_du == 300


def test_calculer_echeances_inclut_les_virements_manquants_du_tableau_de_bord(session):
    bien, unite = _creer_bien_avec_unite(session)
    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    session.add(
        MandatGestion(unite_locative_id=unite.id, gestionnaire_id=gestionnaire.id, role=RoleMandat.GESTION, date_debut=date(2024, 1, 1))
    )
    session.commit()

    donnees = calculer_echeances(session, aujourdhui=date(2026, 10, 29))

    assert len(donnees.virements_manquants) == 1
    assert donnees.virements_manquants[0].gestionnaire_nom == "Locagestion"
