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


def test_creation_residence_principale_ne_cree_aucune_unite(client_connecte, engine):
    client_connecte.post(
        "/biens",
        data={
            "type": "residence_principale",
            "libelle": "Ma maison",
            "adresse_rue": "5 rue Test",
            "adresse_code_postal": "08000",
            "adresse_ville": "Charleville-Mézières",
        },
    )

    from sqlmodel import Session, select

    with Session(engine) as s:
        bien = s.exec(select(Bien).where(Bien.libelle == "Ma maison")).first()
        assert bien is not None
        unites = s.exec(select(UniteLocative).where(UniteLocative.bien_id == bien.id)).all()
        assert unites == []


def test_detail_residence_principale_sans_section_unites(client_connecte, session):
    bien = Bien(
        type=TypeBien.RESIDENCE_PRINCIPALE,
        libelle="Ma maison",
        adresse_rue="5 rue Test",
        adresse_code_postal="08000",
        adresse_ville="Charleville-Mézières",
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)

    reponse = client_connecte.get(f"/biens/{bien.id}")
    assert reponse.status_code == 200
    assert "Unités locatives" not in reponse.text
    assert "non locative" in reponse.text


def test_ajout_unite_refuse_sur_residence_principale(client_connecte, session):
    bien = Bien(
        type=TypeBien.RESIDENCE_PRINCIPALE,
        libelle="Ma maison",
        adresse_rue="5 rue Test",
        adresse_code_postal="08000",
        adresse_ville="Charleville-Mézières",
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)

    assert client_connecte.get(f"/biens/{bien.id}/unites/nouvelle").status_code == 409
    assert (
        client_connecte.post(
            f"/biens/{bien.id}/unites",
            data={"libelle": "x"},
        ).status_code
        == 409
    )


def test_suppression_residence_principale_refusee_si_depense_recurrente(client_connecte, session):
    from app.models import DepenseRecurrente
    from app.models.enums import FrequenceDepense

    bien = Bien(
        type=TypeBien.RESIDENCE_PRINCIPALE,
        libelle="Ma maison",
        adresse_rue="5 rue Test",
        adresse_code_postal="08000",
        adresse_ville="Charleville-Mézières",
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)
    session.add(
        DepenseRecurrente(
            bien_id=bien.id,
            categorie="Crédit immobilier",
            libelle="Crédit résidence principale",
            montant=900,
            frequence=FrequenceDepense.MENSUELLE,
            date_debut=date(2024, 1, 1),
        )
    )
    session.commit()

    reponse = client_connecte.post(f"/biens/{bien.id}/supprimer")
    assert reponse.status_code == 409


def test_detail_bien_affiche_les_finances_du_bien(client_connecte, session):
    from app.models import LigneDepense

    bien = _creer_bien_immeuble(session)
    unite = UniteLocative(bien_id=bien.id, libelle="Appt 1")
    session.add(unite)
    session.commit()
    session.refresh(unite)
    session.add(
        LigneDepense(bien_id=bien.id, categorie="Taxe foncière", libelle="Taxe", montant=1200, date=date.today())
    )
    session.commit()

    reponse = client_connecte.get(f"/biens/{bien.id}")
    assert reponse.status_code == 200
    assert "Finances de ce bien" in reponse.text
    assert "1200" in reponse.text


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
    assert client_connecte.get("/biens/999/modifier").status_code == 404
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


def test_formulaire_modification_bien_accessible(client_connecte, session):
    bien = _creer_bien_immeuble(session)

    reponse = client_connecte.get(f"/biens/{bien.id}/modifier")
    assert reponse.status_code == 200
    assert bien.libelle in reponse.text


def test_ajout_unite_formulaire_bien_inexistant(client_connecte):
    assert client_connecte.get("/biens/999/unites/nouvelle").status_code == 404


def test_suppression_bien_inexistant(client_connecte):
    assert client_connecte.post("/biens/999/supprimer").status_code == 404


def test_modification_bien_date_acquisition_invalide(client_connecte, session):
    bien = _creer_bien_immeuble(session)

    reponse = client_connecte.post(
        f"/biens/{bien.id}/modifier",
        data={
            "libelle": bien.libelle,
            "adresse_rue": bien.adresse_rue,
            "adresse_code_postal": bien.adresse_code_postal,
            "adresse_ville": bien.adresse_ville,
            "date_acquisition": "pas-une-date",
        },
    )
    assert reponse.status_code == 400


def test_ajout_unite_bien_inexistant(client_connecte):
    assert client_connecte.post("/biens/999/unites", data={"libelle": "x"}).status_code == 404


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


def test_suppression_bien_avec_unites_supprime_la_cascade(client_connecte, session, engine):
    bien = _creer_bien_immeuble(session)
    session.add(UniteLocative(bien_id=bien.id, libelle="Appt 1"))
    session.add(UniteLocative(bien_id=bien.id, libelle="Appt 2"))
    session.commit()

    reponse = client_connecte.post(f"/biens/{bien.id}/supprimer", follow_redirects=False)
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        assert s.get(Bien, bien.id) is None
        assert s.exec(select(UniteLocative).where(UniteLocative.bien_id == bien.id)).all() == []


def test_suppression_bien_refusee_si_ligne_depense_liee(client_connecte, session):
    from app.models import LigneDepense

    bien = _creer_bien_immeuble(session)
    session.add(
        LigneDepense(bien_id=bien.id, categorie="Taxe foncière", libelle="Taxe", montant=1200, date=date(2024, 10, 1))
    )
    session.commit()

    reponse = client_connecte.post(f"/biens/{bien.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_bien_refusee_si_mandat_gestion_lie_sans_occupation(client_connecte, session):
    from app.models import MandatGestion
    from app.models.enums import RoleMandat

    bien = _creer_bien_immeuble(session)
    unite = UniteLocative(bien_id=bien.id, libelle="Appt 1")
    session.add(unite)
    session.commit()
    session.refresh(unite)

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

    reponse = client_connecte.post(f"/biens/{bien.id}/supprimer")
    assert reponse.status_code == 409


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
