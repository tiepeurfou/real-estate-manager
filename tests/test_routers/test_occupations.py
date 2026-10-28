from datetime import date

from app.models import Bien, Locataire, Occupation, OccupationLocataire, UniteLocative
from app.models.enums import StatutOccupation, TypeBien, TypeGarantie


def _creer_bien_avec_unite(session) -> tuple[Bien, UniteLocative]:
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

    return bien, unite


def _creer_locataire(session, nom="Dupont", prenom="Jean") -> Locataire:
    locataire = Locataire(nom=nom, prenom=prenom, type_garantie=TypeGarantie.AUCUNE)
    session.add(locataire)
    session.commit()
    session.refresh(locataire)
    return locataire


def test_formulaire_nouvelle_occupation(client_connecte, session):
    _, unite = _creer_bien_avec_unite(session)
    _creer_locataire(session)

    reponse = client_connecte.get(f"/unites/{unite.id}/occupations/nouvelle")
    assert reponse.status_code == 200
    assert "Dupont" in reponse.text


def test_formulaire_nouvelle_occupation_unite_inexistante(client_connecte):
    assert client_connecte.get("/unites/999/occupations/nouvelle").status_code == 404


def test_creation_occupation_simple(client_connecte, session, engine):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)

    reponse = client_connecte.post(
        f"/unites/{unite.id}/occupations",
        data={
            "locataire_ids": [str(locataire.id)],
            "date_entree": "2024-02-01",
            "loyer_mensuel_hc": "500",
            "charges_mensuelles": "50",
        },
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        occupation = s.exec(select(Occupation).where(Occupation.unite_locative_id == unite.id)).first()
        assert occupation is not None
        assert occupation.statut == StatutOccupation.ACTIVE
        liens = s.exec(select(OccupationLocataire).where(OccupationLocataire.occupation_id == occupation.id)).all()
        assert len(liens) == 1

    detail = client_connecte.get(f"/biens/{bien.id}")
    assert "Dupont" in detail.text
    assert "Vacant" not in detail.text


def test_creation_occupation_colocation(client_connecte, session, engine):
    _, unite = _creer_bien_avec_unite(session)
    locataire1 = _creer_locataire(session, nom="Dupont", prenom="Jean")
    locataire2 = _creer_locataire(session, nom="Martin", prenom="Alice")

    client_connecte.post(
        f"/unites/{unite.id}/occupations",
        data={
            "locataire_ids": [str(locataire1.id), str(locataire2.id)],
            "date_entree": "2024-02-01",
            "loyer_mensuel_hc": "600",
        },
    )

    from sqlmodel import Session, select

    with Session(engine) as s:
        occupation = s.exec(select(Occupation).where(Occupation.unite_locative_id == unite.id)).first()
        liens = s.exec(select(OccupationLocataire).where(OccupationLocataire.occupation_id == occupation.id)).all()
        assert len(liens) == 2


def test_creation_occupation_sans_locataire_selectionne(client_connecte, session):
    _, unite = _creer_bien_avec_unite(session)

    reponse = client_connecte.post(
        f"/unites/{unite.id}/occupations",
        data={"date_entree": "2024-02-01", "loyer_mensuel_hc": "500"},
    )
    assert reponse.status_code == 400


def test_creation_occupation_refusee_si_deja_occupee(client_connecte, session):
    _, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)

    donnees = {
        "locataire_ids": [str(locataire.id)],
        "date_entree": "2024-02-01",
        "loyer_mensuel_hc": "500",
    }
    client_connecte.post(f"/unites/{unite.id}/occupations", data=donnees)

    reponse_formulaire = client_connecte.get(f"/unites/{unite.id}/occupations/nouvelle")
    assert reponse_formulaire.status_code == 409

    reponse = client_connecte.post(f"/unites/{unite.id}/occupations", data=donnees)
    assert reponse.status_code == 409


def test_creation_occupation_date_invalide(client_connecte, session):
    _, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)

    reponse = client_connecte.post(
        f"/unites/{unite.id}/occupations",
        data={
            "locataire_ids": [str(locataire.id)],
            "date_entree": "pas-une-date",
            "loyer_mensuel_hc": "500",
        },
    )
    assert reponse.status_code == 400


def test_creation_occupation_date_vide_est_rejetee_proprement(client_connecte, session):
    # "date_entree" est un champ Form(...) requis : une valeur vide est
    # traitée par Starlette comme un champ absent (422 natif FastAPI).
    _, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)

    reponse = client_connecte.post(
        f"/unites/{unite.id}/occupations",
        data={"locataire_ids": [str(locataire.id)], "date_entree": "", "loyer_mensuel_hc": "500"},
    )
    assert reponse.status_code == 422


def test_creation_occupation_locataire_inexistant(client_connecte, session, engine):
    _, unite = _creer_bien_avec_unite(session)

    reponse = client_connecte.post(
        f"/unites/{unite.id}/occupations",
        data={"locataire_ids": ["999"], "date_entree": "2024-02-01", "loyer_mensuel_hc": "500"},
    )
    assert reponse.status_code == 404

    from sqlmodel import Session, select

    # Un locataire invalide ne doit laisser aucune occupation orpheline
    # derrière lui : sinon la ré-attribution de cette unité serait bloquée
    # par un faux 409 "déjà occupée".
    with Session(engine) as s:
        assert s.exec(select(Occupation).where(Occupation.unite_locative_id == unite.id)).all() == []


def test_creation_occupation_unite_inexistante(client_connecte, session):
    locataire = _creer_locataire(session)

    reponse = client_connecte.post(
        "/unites/999/occupations",
        data={"locataire_ids": [str(locataire.id)], "date_entree": "2024-02-01", "loyer_mensuel_hc": "500"},
    )
    assert reponse.status_code == 404


def test_cloture_occupation(client_connecte, session, engine):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)

    occupation = Occupation(
        unite_locative_id=unite.id, date_entree=date(2024, 1, 1), loyer_mensuel_hc=500, statut=StatutOccupation.ACTIVE
    )
    session.add(occupation)
    session.commit()
    session.refresh(occupation)
    session.add(OccupationLocataire(occupation_id=occupation.id, locataire_id=locataire.id))
    session.commit()

    assert client_connecte.get(f"/occupations/{occupation.id}/cloturer").status_code == 200

    reponse = client_connecte.post(
        f"/occupations/{occupation.id}/cloturer", data={"date_sortie": "2024-06-30"}, follow_redirects=False
    )
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith(f"/biens/{bien.id}")

    from sqlmodel import Session

    with Session(engine) as s:
        occupation_maj = s.get(Occupation, occupation.id)
        assert occupation_maj.statut == StatutOccupation.TERMINEE
        assert occupation_maj.date_sortie == date(2024, 6, 30)

    detail = client_connecte.get(f"/biens/{bien.id}")
    assert "Vacant" in detail.text


def test_cloture_occupation_deja_cloturee(client_connecte, session):
    _, unite = _creer_bien_avec_unite(session)
    occupation = Occupation(
        unite_locative_id=unite.id,
        date_entree=date(2024, 1, 1),
        date_sortie=date(2024, 6, 30),
        loyer_mensuel_hc=500,
        statut=StatutOccupation.TERMINEE,
    )
    session.add(occupation)
    session.commit()
    session.refresh(occupation)

    reponse = client_connecte.post(f"/occupations/{occupation.id}/cloturer", data={"date_sortie": "2024-07-01"})
    assert reponse.status_code == 409


def test_cloture_occupation_date_sortie_avant_entree(client_connecte, session):
    _, unite = _creer_bien_avec_unite(session)
    occupation = Occupation(
        unite_locative_id=unite.id, date_entree=date(2024, 1, 1), loyer_mensuel_hc=500, statut=StatutOccupation.ACTIVE
    )
    session.add(occupation)
    session.commit()
    session.refresh(occupation)

    reponse = client_connecte.post(f"/occupations/{occupation.id}/cloturer", data={"date_sortie": "2023-12-31"})
    assert reponse.status_code == 400


def test_cloture_occupation_inexistante(client_connecte):
    assert client_connecte.get("/occupations/999/cloturer").status_code == 404
    assert client_connecte.post("/occupations/999/cloturer", data={"date_sortie": "2024-01-01"}).status_code == 404


def test_suppression_occupation(client_connecte, session, engine):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)

    occupation = Occupation(
        unite_locative_id=unite.id, date_entree=date(2024, 1, 1), loyer_mensuel_hc=500, statut=StatutOccupation.ACTIVE
    )
    session.add(occupation)
    session.commit()
    session.refresh(occupation)
    session.add(OccupationLocataire(occupation_id=occupation.id, locataire_id=locataire.id))
    session.commit()

    reponse = client_connecte.post(f"/occupations/{occupation.id}/supprimer", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith(f"/biens/{bien.id}")

    from sqlmodel import Session

    with Session(engine) as s:
        assert s.get(Occupation, occupation.id) is None


def test_suppression_occupation_inexistante(client_connecte):
    assert client_connecte.post("/occupations/999/supprimer").status_code == 404


def test_formulaire_modification_occupation(client_connecte, session):
    _, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)
    occupation = Occupation(
        unite_locative_id=unite.id, date_entree=date(2024, 1, 1), loyer_mensuel_hc=500, statut=StatutOccupation.ACTIVE
    )
    session.add(occupation)
    session.commit()
    session.refresh(occupation)
    session.add(OccupationLocataire(occupation_id=occupation.id, locataire_id=locataire.id))
    session.commit()

    reponse = client_connecte.get(f"/occupations/{occupation.id}/modifier")
    assert reponse.status_code == 200
    assert "Dupont" in reponse.text


def test_formulaire_modification_occupation_inexistante(client_connecte):
    assert client_connecte.get("/occupations/999/modifier").status_code == 404


def test_modification_occupation_revision_de_loyer(client_connecte, session, engine):
    """Cas d'usage principal : la révision annuelle du loyer."""
    _, unite = _creer_bien_avec_unite(session)
    occupation = Occupation(
        unite_locative_id=unite.id,
        date_entree=date(2024, 1, 1),
        loyer_mensuel_hc=500,
        charges_mensuelles=50,
        statut=StatutOccupation.ACTIVE,
    )
    session.add(occupation)
    session.commit()
    session.refresh(occupation)

    reponse = client_connecte.post(
        f"/occupations/{occupation.id}/modifier",
        data={"date_entree": "2024-01-01", "loyer_mensuel_hc": "515", "charges_mensuelles": "55"},
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    from sqlmodel import Session

    with Session(engine) as s:
        occupation_maj = s.get(Occupation, occupation.id)
        assert occupation_maj.loyer_mensuel_hc == 515
        assert occupation_maj.charges_mensuelles == 55


def test_modification_occupation_corrige_la_date_d_entree(client_connecte, session, engine):
    _, unite = _creer_bien_avec_unite(session)
    occupation = Occupation(
        unite_locative_id=unite.id, date_entree=date(2024, 1, 1), loyer_mensuel_hc=500, statut=StatutOccupation.ACTIVE
    )
    session.add(occupation)
    session.commit()
    session.refresh(occupation)

    client_connecte.post(
        f"/occupations/{occupation.id}/modifier",
        data={"date_entree": "2024-02-01", "loyer_mensuel_hc": "500"},
    )

    from sqlmodel import Session

    with Session(engine) as s:
        assert s.get(Occupation, occupation.id).date_entree == date(2024, 2, 1)


def test_modification_occupation_terminee_reste_coherente_avec_la_date_de_sortie(client_connecte, session):
    _, unite = _creer_bien_avec_unite(session)
    occupation = Occupation(
        unite_locative_id=unite.id,
        date_entree=date(2024, 1, 1),
        date_sortie=date(2024, 6, 30),
        loyer_mensuel_hc=500,
        statut=StatutOccupation.TERMINEE,
    )
    session.add(occupation)
    session.commit()
    session.refresh(occupation)

    reponse = client_connecte.post(
        f"/occupations/{occupation.id}/modifier",
        data={"date_entree": "2024-07-01", "loyer_mensuel_hc": "500"},
    )
    assert reponse.status_code == 400


def test_modification_occupation_montant_invalide(client_connecte, session):
    _, unite = _creer_bien_avec_unite(session)
    occupation = Occupation(
        unite_locative_id=unite.id, date_entree=date(2024, 1, 1), loyer_mensuel_hc=500, statut=StatutOccupation.ACTIVE
    )
    session.add(occupation)
    session.commit()
    session.refresh(occupation)

    reponse = client_connecte.post(
        f"/occupations/{occupation.id}/modifier",
        data={"date_entree": "2024-01-01", "loyer_mensuel_hc": "abc"},
    )
    assert reponse.status_code == 400


def test_modification_occupation_inexistante(client_connecte):
    assert client_connecte.post("/occupations/999/modifier", data={"date_entree": "2024-01-01", "loyer_mensuel_hc": "500"}).status_code == 404
