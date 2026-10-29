from datetime import date

from app.models import Bien, LigneDepense, Locataire, Occupation, OccupationLocataire, UniteLocative
from app.models.enums import StatutOccupation, TypeBien


def _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan", numero_fiscal=None) -> tuple[Bien, UniteLocative]:
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
    unite = UniteLocative(bien_id=bien.id, libelle="Appt 1", numero_fiscal=numero_fiscal)
    session.add(unite)
    session.commit()
    session.refresh(unite)
    return bien, unite


def test_acces_sans_session_redirige(client):
    reponse = client.get("/tableau-de-bord/annee", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_sans_parametres_utilise_l_annee_courante(client_connecte):
    reponse = client_connecte.get("/tableau-de-bord/annee")
    assert reponse.status_code == 200
    assert "année en cours" in reponse.text


def test_annee_passee_n_affiche_pas_le_badge_annee_en_cours(client_connecte):
    reponse = client_connecte.get("/tableau-de-bord/annee", params={"annee": 2024})
    assert reponse.status_code == 200
    assert "Année 2024" in reponse.text
    assert "année en cours" not in reponse.text


def test_annee_invalide(client_connecte):
    assert client_connecte.get("/tableau-de-bord/annee", params={"annee": 0}).status_code == 400


def test_bien_inexistant(client_connecte):
    assert client_connecte.get("/tableau-de-bord/annee", params={"bien_id": 999}).status_code == 404


def test_affiche_les_elements_de_declaration(client_connecte, session):
    bien, unite = _creer_bien_avec_unite(session, numero_fiscal="1234567A")
    locataire = Locataire(nom="Dupont", prenom="Jean", date_naissance=date(1990, 1, 1))
    session.add(locataire)
    session.commit()
    session.refresh(locataire)
    occupation = Occupation(unite_locative_id=unite.id, date_entree=date(2024, 1, 1), loyer_mensuel_hc=500, statut=StatutOccupation.ACTIVE)
    session.add(occupation)
    session.commit()
    session.refresh(occupation)
    session.add(OccupationLocataire(occupation_id=occupation.id, locataire_id=locataire.id))
    session.commit()

    reponse = client_connecte.get("/tableau-de-bord/annee", params={"annee": 2024})
    assert reponse.status_code == 200
    assert "Dupont" in reponse.text
    assert "1990-01-01" in reponse.text
    assert "1234567A" in reponse.text


def test_affiche_les_depenses_de_l_annee(client_connecte, session):
    bien, unite = _creer_bien_avec_unite(session)
    session.add(LigneDepense(bien_id=bien.id, categorie="Travaux", libelle="x", montant=150, date=date(2024, 6, 1)))
    session.commit()

    reponse = client_connecte.get("/tableau-de-bord/annee", params={"annee": 2024})
    assert reponse.status_code == 200
    assert "150.00" in reponse.text
    assert "Travaux" in reponse.text


def test_filtre_par_bien_masque_la_vue_par_type(client_connecte, session):
    bien, unite = _creer_bien_avec_unite(session)

    reponse = client_connecte.get("/tableau-de-bord/annee", params={"annee": 2024, "bien_id": bien.id})
    assert reponse.status_code == 200
    assert "Par type de bien" not in reponse.text


def test_sans_filtre_affiche_la_vue_par_type(client_connecte, session):
    _creer_bien_avec_unite(session)

    reponse = client_connecte.get("/tableau-de-bord/annee", params={"annee": 2024})
    assert reponse.status_code == 200
    assert "Par type de bien" in reponse.text


def test_lien_depuis_le_detail_du_bien(client_connecte, session):
    bien, unite = _creer_bien_avec_unite(session)

    detail = client_connecte.get(f"/biens/{bien.id}")
    assert f"/tableau-de-bord/annee?bien_id={bien.id}" in detail.text


def test_lien_depuis_le_tableau_de_bord_mensuel(client_connecte):
    reponse = client_connecte.get("/tableau-de-bord/mois")
    assert "/tableau-de-bord/annee" in reponse.text
