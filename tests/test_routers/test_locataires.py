from datetime import date, datetime, timezone

from app.models import (
    Bien,
    Gestionnaire,
    LignePaiement,
    Locataire,
    Occupation,
    OccupationLocataire,
    ReleveGestion,
    UniteLocative,
)
from app.models.enums import StatutExtraction, StatutOccupation, StatutPaiement, TypeBien, TypeGarantie


def _creer_locataire(session, nom="Dupont", prenom="Jean") -> Locataire:
    locataire = Locataire(nom=nom, prenom=prenom, type_garantie=TypeGarantie.VISALE)
    session.add(locataire)
    session.commit()
    session.refresh(locataire)
    return locataire


def _creer_bien_avec_unite(session) -> tuple[Bien, UniteLocative]:
    bien = Bien(
        type=TypeBien.IMMEUBLE,
        libelle="Immeuble Sedan",
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


def test_liste_sans_locataire(client_connecte):
    reponse = client_connecte.get("/locataires")
    assert reponse.status_code == 200
    assert "Aucun locataire" in reponse.text


def test_acces_sans_session_redirige(client):
    reponse = client.get("/locataires", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_formulaire_nouveau_pas_capture_par_la_route_detail(client_connecte):
    reponse = client_connecte.get("/locataires/nouveau")
    assert reponse.status_code == 200
    assert "Ajouter un locataire" in reponse.text


def test_creation_locataire(client_connecte, engine):
    reponse = client_connecte.post(
        "/locataires",
        data={"nom": "Dupont", "prenom": "Jean", "type_garantie": "visale"},
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        locataire = s.exec(select(Locataire).where(Locataire.nom == "Dupont")).first()
        assert locataire is not None
        assert locataire.type_garantie == TypeGarantie.VISALE


def test_creation_locataire_garantie_invalide(client_connecte):
    reponse = client_connecte.post(
        "/locataires", data={"nom": "X", "prenom": "Y", "type_garantie": "caution_solidaire"}
    )
    assert reponse.status_code == 400


def test_detail_locataire_inexistant(client_connecte):
    assert client_connecte.get("/locataires/999").status_code == 404


def test_modification_locataire(client_connecte, session):
    locataire = _creer_locataire(session)

    reponse = client_connecte.post(
        f"/locataires/{locataire.id}/modifier",
        data={"nom": "Durand", "prenom": "Jean", "type_garantie": "aucune"},
        follow_redirects=False,
    )
    assert reponse.status_code == 303
    detail = client_connecte.get(f"/locataires/{locataire.id}")
    assert "Durand" in detail.text


def test_modification_locataire_inexistant(client_connecte):
    reponse = client_connecte.post(
        "/locataires/999/modifier", data={"nom": "x", "prenom": "y", "type_garantie": "aucune"}
    )
    assert reponse.status_code == 404


def test_suppression_locataire_sans_donnees_liees(client_connecte, session):
    locataire = _creer_locataire(session)

    reponse = client_connecte.post(f"/locataires/{locataire.id}/supprimer", follow_redirects=False)
    assert reponse.status_code == 303
    assert client_connecte.get(f"/locataires/{locataire.id}").status_code == 404


def test_suppression_locataire_refusee_si_occupation_liee(client_connecte, session):
    locataire = _creer_locataire(session)
    _, unite = _creer_bien_avec_unite(session)

    occupation = Occupation(
        unite_locative_id=unite.id,
        date_entree=date(2024, 1, 1),
        loyer_mensuel_hc=500,
        statut=StatutOccupation.ACTIVE,
    )
    session.add(occupation)
    session.commit()
    session.refresh(occupation)
    session.add(OccupationLocataire(occupation_id=occupation.id, locataire_id=locataire.id))
    session.commit()

    reponse = client_connecte.post(f"/locataires/{locataire.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_locataire_refusee_si_ligne_paiement_liee(client_connecte, session):
    locataire = _creer_locataire(session)
    bien, unite = _creer_bien_avec_unite(session)
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
        hash_fichier="hash-paiement-locataire",
        statut_extraction=StatutExtraction.TRAITE_OK,
    )
    session.add(releve)
    session.commit()
    session.refresh(releve)

    session.add(
        LignePaiement(
            releve_gestion_id=releve.id,
            unite_locative_id=unite.id,
            locataire_id=locataire.id,
            periode=date(2024, 9, 1),
            montant_attendu=500,
            montant_percu=500,
            statut=StatutPaiement.PAYE,
        )
    )
    session.commit()

    reponse = client_connecte.post(f"/locataires/{locataire.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_locataire_inexistant(client_connecte):
    assert client_connecte.post("/locataires/999/supprimer").status_code == 404


def test_filtre_statut_actif_et_historique(client_connecte, session):
    locataire_actif = _creer_locataire(session, nom="Lenormand", prenom="Alice")
    _creer_locataire(session, nom="Fontaine", prenom="Paul")
    _, unite = _creer_bien_avec_unite(session)

    occupation = Occupation(
        unite_locative_id=unite.id,
        date_entree=date(2024, 1, 1),
        loyer_mensuel_hc=500,
        statut=StatutOccupation.ACTIVE,
    )
    session.add(occupation)
    session.commit()
    session.refresh(occupation)
    session.add(OccupationLocataire(occupation_id=occupation.id, locataire_id=locataire_actif.id))
    session.commit()

    reponse_actifs = client_connecte.get("/locataires", params={"statut": "actif"})
    assert "Lenormand" in reponse_actifs.text
    assert "Fontaine" not in reponse_actifs.text

    reponse_historique = client_connecte.get("/locataires", params={"statut": "historique"})
    assert "Fontaine" in reponse_historique.text
    assert "Lenormand" not in reponse_historique.text
