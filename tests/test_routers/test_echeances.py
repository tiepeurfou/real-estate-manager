from datetime import date

from app.models import Bien, Locataire, Occupation, OccupationLocataire, UniteLocative
from app.models.enums import DpeLettre, StatutOccupation, TypeBien


def _creer_bien_avec_unite(session, dpe_date=None) -> tuple[Bien, UniteLocative]:
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
    unite = UniteLocative(bien_id=bien.id, libelle="Appt 1", dpe_lettre=DpeLettre.D if dpe_date else None, dpe_date=dpe_date)
    session.add(unite)
    session.commit()
    session.refresh(unite)
    return bien, unite


def test_acces_sans_session_redirige(client):
    reponse = client.get("/echeances", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_sans_parametres_utilise_l_horizon_par_defaut(client_connecte):
    reponse = client_connecte.get("/echeances")
    assert reponse.status_code == 200
    assert "Échéances à venir" in reponse.text


def test_horizon_invalide(client_connecte):
    assert client_connecte.get("/echeances", params={"jours": 0}).status_code == 400
    assert client_connecte.get("/echeances", params={"jours": -5}).status_code == 400


def test_affiche_une_revision_de_loyer_a_venir(client_connecte, session):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = Locataire(nom="Dupont", prenom="Jean")
    session.add(locataire)
    session.commit()
    session.refresh(locataire)
    occupation = Occupation(unite_locative_id=unite.id, date_entree=date(2024, 11, 20), loyer_mensuel_hc=500, statut=StatutOccupation.ACTIVE)
    session.add(occupation)
    session.commit()
    session.refresh(occupation)
    session.add(OccupationLocataire(occupation_id=occupation.id, locataire_id=locataire.id))
    session.commit()

    reponse = client_connecte.get("/echeances")
    assert reponse.status_code == 200
    assert "Dupont" in reponse.text
    assert "500.00" in reponse.text


def test_affiche_un_dpe_a_renouveler(client_connecte, session):
    bien, unite = _creer_bien_avec_unite(session, dpe_date=date(2016, 8, 15))

    reponse = client_connecte.get("/echeances", params={"jours": 365})
    assert reponse.status_code == 200
    assert "2016-08-15" in reponse.text
    assert "2026-08-15" in reponse.text


def test_lien_depuis_la_navigation_principale(client_connecte):
    reponse = client_connecte.get("/biens")
    assert "/echeances" in reponse.text
