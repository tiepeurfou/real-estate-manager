from datetime import date, datetime, timezone

from app.models import Bien, Gestionnaire, Occupation, ReleveGestion, UniteLocative
from app.models.enums import StatutExtraction, StatutOccupation, TypeBien


def _creer_bien_immeuble(session, libelle="Immeuble Sedan") -> Bien:
    bien = Bien(
        type=TypeBien.IMMEUBLE,
        libelle=libelle,
        adresse_rue="1 rue Test",
        adresse_code_postal="08200",
        adresse_ville="Sedan",
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)
    return bien


def test_liste_sans_bien(client_connecte):
    reponse = client_connecte.get("/biens")
    assert reponse.status_code == 200
    assert "Aucun bien" in reponse.text


def test_acces_sans_session_redirige_vers_connexion(client):
    reponse = client.get("/biens", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_formulaire_nouveau_bien_pas_capture_par_la_route_detail(client_connecte):
    reponse = client_connecte.get("/biens/nouveau")
    assert reponse.status_code == 200
    assert "Ajouter un bien" in reponse.text


def test_creation_appartement_isole_cree_une_seule_unite_automatiquement(client_connecte, engine):
    reponse = client_connecte.post(
        "/biens",
        data={
            "type": "appartement_isole",
            "libelle": "Villiers-sur-Marne",
            "adresse_rue": "2 rue Test",
            "adresse_code_postal": "94350",
            "adresse_ville": "Villiers-sur-Marne",
        },
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        bien = s.exec(select(Bien).where(Bien.libelle == "Villiers-sur-Marne")).first()
        unites = s.exec(select(UniteLocative).where(UniteLocative.bien_id == bien.id)).all()
        assert len(unites) == 1
        assert unites[0].libelle == "Villiers-sur-Marne"


def test_creation_immeuble_ne_cree_aucune_unite(client_connecte, engine):
    client_connecte.post(
        "/biens",
        data={
            "type": "immeuble",
            "libelle": "Immeuble Test",
            "adresse_rue": "3 rue Test",
            "adresse_code_postal": "08000",
            "adresse_ville": "Charleville-Mézières",
        },
    )

    from sqlmodel import Session, select

    with Session(engine) as s:
        bien = s.exec(select(Bien).where(Bien.libelle == "Immeuble Test")).first()
        unites = s.exec(select(UniteLocative).where(UniteLocative.bien_id == bien.id)).all()
        assert unites == []


def test_creation_bien_type_invalide(client_connecte):
    reponse = client_connecte.post(
        "/biens",
        data={
            "type": "autre",
            "libelle": "X",
            "adresse_rue": "rue",
            "adresse_code_postal": "00000",
            "adresse_ville": "Ville",
        },
    )
    assert reponse.status_code == 400
    assert "invalides" in reponse.text


def test_creation_bien_date_acquisition_invalide(client_connecte):
    reponse = client_connecte.post(
        "/biens",
        data={
            "type": "immeuble",
            "libelle": "X",
            "adresse_rue": "rue",
            "adresse_code_postal": "00000",
            "adresse_ville": "Ville",
            "date_acquisition": "pas-une-date",
        },
    )
    assert reponse.status_code == 400


def test_detail_bien_inexistant(client_connecte):
    assert client_connecte.get("/biens/999").status_code == 404


def test_modification_bien(client_connecte, session):
    bien = _creer_bien_immeuble(session)

    reponse = client_connecte.post(
        f"/biens/{bien.id}/modifier",
        data={
            "libelle": "Nouveau libellé",
            "adresse_rue": "rue modifiée",
            "adresse_code_postal": "08200",
            "adresse_ville": "Sedan",
        },
        follow_redirects=False,
    )
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith(f"/biens/{bien.id}")

    detail = client_connecte.get(f"/biens/{bien.id}")
    assert "Nouveau libellé" in detail.text


def test_modification_bien_inexistant(client_connecte):
    reponse = client_connecte.post(
        "/biens/999/modifier",
        data={
            "libelle": "x",
            "adresse_rue": "x",
            "adresse_code_postal": "x",
            "adresse_ville": "x",
        },
    )
    assert reponse.status_code == 404


def test_suppression_bien_sans_donnees_liees(client_connecte, session):
    bien = _creer_bien_immeuble(session)

    reponse = client_connecte.post(f"/biens/{bien.id}/supprimer", follow_redirects=False)
    assert reponse.status_code == 303
    assert client_connecte.get(f"/biens/{bien.id}").status_code == 404


def test_suppression_bien_refusee_si_occupation_liee(client_connecte, session):
    bien = _creer_bien_immeuble(session)
    unite = UniteLocative(bien_id=bien.id, libelle="Appt 1")
    session.add(unite)
    session.commit()
    session.refresh(unite)

    occupation = Occupation(
        unite_locative_id=unite.id,
        date_entree=date(2024, 1, 1),
        loyer_mensuel_hc=500,
        statut=StatutOccupation.ACTIVE,
    )
    session.add(occupation)
    session.commit()

    reponse = client_connecte.post(f"/biens/{bien.id}/supprimer")
    assert reponse.status_code == 409
    assert client_connecte.get(f"/biens/{bien.id}").status_code == 200


def test_suppression_bien_refusee_si_releve_gestion_lie(client_connecte, session):
    bien = _creer_bien_immeuble(session)
    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)

    releve = ReleveGestion(
        gestionnaire_id=gestionnaire.id,
        bien_id=bien.id,
        periode=date(2024, 9, 1),
        date_reception=datetime.now(timezone.utc),
        chemin_fichier_pdf="data/documents/locagestion/2024-09/releve.pdf",
        hash_fichier="hash-unique-1",
        statut_extraction=StatutExtraction.TRAITE_OK,
    )
    session.add(releve)
    session.commit()

    reponse = client_connecte.post(f"/biens/{bien.id}/supprimer")
    assert reponse.status_code == 409


def test_ajout_unite_sur_immeuble(client_connecte, session):
    bien = _creer_bien_immeuble(session)

    reponse_formulaire = client_connecte.get(f"/biens/{bien.id}/unites/nouvelle")
    assert reponse_formulaire.status_code == 200

    reponse = client_connecte.post(
        f"/biens/{bien.id}/unites",
        data={"libelle": "Appt 2", "surface_m2": "45.5", "nb_pieces": "2", "dpe_lettre": "C"},
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    detail = client_connecte.get(f"/biens/{bien.id}")
    assert "Appt 2" in detail.text


def test_ajout_unite_refuse_pour_appartement_isole(client_connecte, session):
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
    session.add(UniteLocative(bien_id=bien.id, libelle="Villiers"))
    session.commit()

    assert client_connecte.get(f"/biens/{bien.id}/unites/nouvelle").status_code == 409
    assert client_connecte.post(f"/biens/{bien.id}/unites", data={"libelle": "Appt 2"}).status_code == 409


def test_ajout_unite_dpe_invalide(client_connecte, session):
    bien = _creer_bien_immeuble(session)

    reponse = client_connecte.post(
        f"/biens/{bien.id}/unites",
        data={"libelle": "Appt 2", "dpe_lettre": "Z"},
    )
    assert reponse.status_code == 400
