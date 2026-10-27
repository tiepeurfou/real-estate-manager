from datetime import date

from app.models import Bien, Gestionnaire, MandatGestion, UniteLocative
from app.models.enums import RoleMandat, TypeBien


def _creer_mandat(session) -> MandatGestion:
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

    unite = UniteLocative(bien_id=bien.id, libelle="Appt 1")
    session.add(unite)
    session.commit()
    session.refresh(unite)

    gestionnaire = Gestionnaire(nom="Pergent Immobilier")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)

    mandat = MandatGestion(
        unite_locative_id=unite.id,
        gestionnaire_id=gestionnaire.id,
        role=RoleMandat.MISE_EN_LOCATION,
        date_debut=date(2024, 1, 1),
    )
    session.add(mandat)
    session.commit()
    session.refresh(mandat)
    return mandat


def test_formulaire_terminer(client_connecte, session):
    mandat = _creer_mandat(session)
    assert client_connecte.get(f"/mandats/{mandat.id}/terminer").status_code == 200


def test_formulaire_terminer_mandat_inexistant(client_connecte):
    assert client_connecte.get("/mandats/999/terminer").status_code == 404


def test_terminer_mandat(client_connecte, session, engine):
    mandat = _creer_mandat(session)

    reponse = client_connecte.post(
        f"/mandats/{mandat.id}/terminer", data={"date_fin": "2024-06-30"}, follow_redirects=False
    )
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith(f"/gestionnaires/{mandat.gestionnaire_id}")

    from sqlmodel import Session

    with Session(engine) as s:
        mandat_maj = s.get(MandatGestion, mandat.id)
        assert mandat_maj.date_fin == date(2024, 6, 30)


def test_terminer_mandat_date_fin_avant_date_debut(client_connecte, session):
    mandat = _creer_mandat(session)

    reponse = client_connecte.post(f"/mandats/{mandat.id}/terminer", data={"date_fin": "2023-12-31"})
    assert reponse.status_code == 400


def test_terminer_mandat_inexistant(client_connecte):
    assert client_connecte.post("/mandats/999/terminer", data={"date_fin": "2024-01-01"}).status_code == 404


def test_supprimer_mandat(client_connecte, session, engine):
    mandat = _creer_mandat(session)

    reponse = client_connecte.post(f"/mandats/{mandat.id}/supprimer", follow_redirects=False)
    assert reponse.status_code == 303

    from sqlmodel import Session

    with Session(engine) as s:
        assert s.get(MandatGestion, mandat.id) is None


def test_supprimer_mandat_inexistant(client_connecte):
    assert client_connecte.post("/mandats/999/supprimer").status_code == 404
