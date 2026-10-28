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


def test_formulaire_modifier(client_connecte, session):
    mandat = _creer_mandat(session)
    reponse = client_connecte.get(f"/mandats/{mandat.id}/modifier")
    assert reponse.status_code == 200
    assert "Modifier le mandat" in reponse.text


def test_formulaire_modifier_mandat_inexistant(client_connecte):
    assert client_connecte.get("/mandats/999/modifier").status_code == 404


def test_modifier_mandat_change_role_et_dates(client_connecte, session, engine):
    mandat = _creer_mandat(session)

    reponse = client_connecte.post(
        f"/mandats/{mandat.id}/modifier",
        data={
            "unite_locative_id": str(mandat.unite_locative_id),
            "role": "gestion",
            "date_debut": "2024-02-01",
            "date_fin": "2024-12-31",
        },
        follow_redirects=False,
    )
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith(f"/gestionnaires/{mandat.gestionnaire_id}")

    from sqlmodel import Session

    with Session(engine) as s:
        mandat_maj = s.get(MandatGestion, mandat.id)
        assert mandat_maj.role == RoleMandat.GESTION
        assert mandat_maj.date_debut == date(2024, 2, 1)
        assert mandat_maj.date_fin == date(2024, 12, 31)


def test_modifier_mandat_avec_compte_bancaire_si_role_gestion(client_connecte, session, engine):
    from app.models import CompteBancaire
    from app.models.enums import Banque

    mandat = _creer_mandat(session)
    compte = CompteBancaire(banque=Banque.SG, libelle="Compte SG")
    session.add(compte)
    session.commit()
    session.refresh(compte)

    client_connecte.post(
        f"/mandats/{mandat.id}/modifier",
        data={
            "unite_locative_id": str(mandat.unite_locative_id),
            "role": "gestion",
            "date_debut": "2024-01-01",
            "compte_bancaire_id": str(compte.id),
        },
    )

    from sqlmodel import Session

    with Session(engine) as s:
        mandat_maj = s.get(MandatGestion, mandat.id)
        assert mandat_maj.compte_bancaire_id == compte.id


def test_modifier_mandat_efface_le_compte_si_role_redevient_mise_en_location(client_connecte, session, engine):
    from app.models import CompteBancaire
    from app.models.enums import Banque

    mandat = _creer_mandat(session)
    compte = CompteBancaire(banque=Banque.SG, libelle="Compte SG")
    session.add(compte)
    session.commit()
    session.refresh(compte)
    mandat.role = RoleMandat.GESTION
    mandat.compte_bancaire_id = compte.id
    session.add(mandat)
    session.commit()

    client_connecte.post(
        f"/mandats/{mandat.id}/modifier",
        data={
            "unite_locative_id": str(mandat.unite_locative_id),
            "role": "mise_en_location",
            "date_debut": "2024-01-01",
            "compte_bancaire_id": str(compte.id),
        },
    )

    from sqlmodel import Session

    with Session(engine) as s:
        mandat_maj = s.get(MandatGestion, mandat.id)
        assert mandat_maj.compte_bancaire_id is None


def test_modifier_mandat_date_fin_avant_date_debut(client_connecte, session):
    mandat = _creer_mandat(session)

    reponse = client_connecte.post(
        f"/mandats/{mandat.id}/modifier",
        data={
            "unite_locative_id": str(mandat.unite_locative_id),
            "role": "mise_en_location",
            "date_debut": "2024-06-01",
            "date_fin": "2024-01-01",
        },
    )
    assert reponse.status_code == 400


def test_modifier_mandat_role_invalide(client_connecte, session):
    mandat = _creer_mandat(session)

    reponse = client_connecte.post(
        f"/mandats/{mandat.id}/modifier",
        data={
            "unite_locative_id": str(mandat.unite_locative_id),
            "role": "gestion_complete",
            "date_debut": "2024-01-01",
        },
    )
    assert reponse.status_code == 400


def test_modifier_mandat_unite_inexistante(client_connecte, session):
    mandat = _creer_mandat(session)

    reponse = client_connecte.post(
        f"/mandats/{mandat.id}/modifier",
        data={"unite_locative_id": "999", "role": "mise_en_location", "date_debut": "2024-01-01"},
    )
    assert reponse.status_code == 404


def test_modifier_mandat_inexistant(client_connecte):
    reponse = client_connecte.post(
        "/mandats/999/modifier",
        data={"unite_locative_id": "1", "role": "mise_en_location", "date_debut": "2024-01-01"},
    )
    assert reponse.status_code == 404


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
