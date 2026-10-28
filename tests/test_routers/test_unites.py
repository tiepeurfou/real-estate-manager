from datetime import date

from app.models import Bien, Occupation, UniteLocative
from app.models.enums import StatutOccupation, TypeBien


def _creer_immeuble_avec_unites(session, nb_unites=2):
    bien = Bien(
        type=TypeBien.IMMEUBLE,
        libelle="Immeuble Charleville",
        adresse_rue="4 rue Test",
        adresse_code_postal="08000",
        adresse_ville="Charleville-Mézières",
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)

    unites = []
    for i in range(nb_unites):
        unite = UniteLocative(bien_id=bien.id, libelle=f"Appt {i + 1}")
        session.add(unite)
        session.commit()
        session.refresh(unite)
        unites.append(unite)

    return bien, unites


def _creer_appartement_isole(session):
    bien = Bien(
        type=TypeBien.APPARTEMENT_ISOLE,
        libelle="Villiers",
        adresse_rue="rue",
        adresse_code_postal="94350",
        adresse_ville="Villiers-sur-Marne",
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)

    unite = UniteLocative(bien_id=bien.id, libelle="Villiers")
    session.add(unite)
    session.commit()
    session.refresh(unite)

    return bien, unite


def test_formulaire_modification_affiche_les_valeurs_actuelles(client_connecte, session):
    _, unites = _creer_immeuble_avec_unites(session, nb_unites=1)
    unite = unites[0]

    reponse = client_connecte.get(f"/unites/{unite.id}/modifier")
    assert reponse.status_code == 200
    assert "Appt 1" in reponse.text


def test_modification_unite_inexistante(client_connecte):
    assert client_connecte.get("/unites/999/modifier").status_code == 404
    assert client_connecte.post("/unites/999/modifier", data={"libelle": "x"}).status_code == 404


def test_modification_unite(client_connecte, session, engine):
    bien, unites = _creer_immeuble_avec_unites(session, nb_unites=1)
    unite = unites[0]

    reponse = client_connecte.post(
        f"/unites/{unite.id}/modifier",
        data={"libelle": "Appt rénové", "surface_m2": "60", "nb_pieces": "3", "dpe_lettre": "B"},
        follow_redirects=False,
    )
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith(f"/biens/{bien.id}")

    from sqlmodel import Session

    with Session(engine) as s:
        unite_maj = s.get(UniteLocative, unite.id)
        assert unite_maj.libelle == "Appt rénové"
        assert unite_maj.surface_m2 == 60
        assert unite_maj.nb_pieces == 3


def test_modification_unite_dpe_invalide(client_connecte, session):
    _, unites = _creer_immeuble_avec_unites(session, nb_unites=1)
    unite = unites[0]

    reponse = client_connecte.post(
        f"/unites/{unite.id}/modifier",
        data={"libelle": "Appt 1", "dpe_lettre": "Z"},
    )
    assert reponse.status_code == 400


def test_suppression_unite_sur_immeuble(client_connecte, session):
    bien, unites = _creer_immeuble_avec_unites(session, nb_unites=2)

    reponse = client_connecte.post(f"/unites/{unites[0].id}/supprimer", follow_redirects=False)
    assert reponse.status_code == 303

    detail = client_connecte.get(f"/biens/{bien.id}")
    assert "Appt 1" not in detail.text
    assert "Appt 2" in detail.text


def test_suppression_unite_refusee_pour_appartement_isole(client_connecte, session):
    _, unite = _creer_appartement_isole(session)

    reponse = client_connecte.post(f"/unites/{unite.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_unite_refusee_si_occupation_liee(client_connecte, session):
    bien, unites = _creer_immeuble_avec_unites(session, nb_unites=1)
    unite = unites[0]

    occupation = Occupation(
        unite_locative_id=unite.id,
        date_entree=date(2024, 1, 1),
        loyer_mensuel_hc=500,
        statut=StatutOccupation.ACTIVE,
    )
    session.add(occupation)
    session.commit()

    reponse = client_connecte.post(f"/unites/{unite.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_unite_refusee_si_mandat_gestion_lie(client_connecte, session):
    from app.models import Gestionnaire, MandatGestion
    from app.models.enums import RoleMandat

    bien, unites = _creer_immeuble_avec_unites(session, nb_unites=1)
    unite = unites[0]

    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    session.add(
        MandatGestion(
            unite_locative_id=unite.id, gestionnaire_id=gestionnaire.id, role=RoleMandat.GESTION, date_debut=date(2024, 1, 1)
        )
    )
    session.commit()

    reponse = client_connecte.post(f"/unites/{unite.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_unite_refusee_si_ligne_paiement_liee(client_connecte, session):
    from app.models import Gestionnaire, LignePaiement, ReleveGestion
    from app.models.enums import StatutExtraction, StatutPaiement
    from datetime import datetime, timezone

    bien, unites = _creer_immeuble_avec_unites(session, nb_unites=1)
    unite = unites[0]

    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    releve = ReleveGestion(
        gestionnaire_id=gestionnaire.id,
        bien_id=bien.id,
        periode=date(2024, 9, 1),
        date_reception=datetime.now(timezone.utc),
        chemin_fichier_pdf="x.pdf",
        hash_fichier="hash-unite-test",
        statut_extraction=StatutExtraction.TRAITE_OK,
    )
    session.add(releve)
    session.commit()
    session.refresh(releve)
    session.add(
        LignePaiement(
            releve_gestion_id=releve.id,
            unite_locative_id=unite.id,
            periode=date(2024, 9, 1),
            montant_attendu=500,
            montant_percu=500,
            statut=StatutPaiement.PAYE,
        )
    )
    session.commit()

    reponse = client_connecte.post(f"/unites/{unite.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_unite_refusee_si_ligne_depense_liee(client_connecte, session):
    from app.models import LigneDepense

    bien, unites = _creer_immeuble_avec_unites(session, nb_unites=1)
    unite = unites[0]

    session.add(
        LigneDepense(unite_locative_id=unite.id, categorie="Travaux", libelle="x", montant=100, date=date(2024, 9, 1))
    )
    session.commit()

    reponse = client_connecte.post(f"/unites/{unite.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_unite_inexistante(client_connecte):
    assert client_connecte.post("/unites/999/supprimer").status_code == 404
