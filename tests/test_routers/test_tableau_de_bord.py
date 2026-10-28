from datetime import date

from app.models import Bien, Occupation, UniteLocative
from app.models.enums import StatutOccupation, TypeBien


def test_tableau_de_bord_sans_donnees(client_connecte):
    reponse = client_connecte.get("/")
    assert reponse.status_code == 200
    assert "Tableau de bord" in reponse.text
    assert "Aucune alerte" in reponse.text


def test_acces_sans_session_redirige(client):
    reponse = client.get("/", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_tableau_de_bord_affiche_les_biens_et_alertes(client_connecte, session):
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

    unite_occupee = UniteLocative(bien_id=bien.id, libelle="Appt 1")
    unite_vacante = UniteLocative(bien_id=bien.id, libelle="Appt 2")
    session.add(unite_occupee)
    session.add(unite_vacante)
    session.commit()
    session.refresh(unite_occupee)

    session.add(
        Occupation(
            unite_locative_id=unite_occupee.id,
            date_entree=date(2024, 1, 1),
            loyer_mensuel_hc=500,
            statut=StatutOccupation.ACTIVE,
        )
    )
    session.commit()

    reponse = client_connecte.get("/")
    assert reponse.status_code == 200
    assert "Immeuble Sedan" in reponse.text
    assert "Vacant" in reponse.text
    assert "Appt 2" in reponse.text
