from datetime import date

from sqlmodel import Session, select

from app.models import Bien, DepenseRecurrente, LigneDepense, UniteLocative
from app.models.enums import TypeBien


def _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan", libelle_unite="Appt 1") -> tuple[Bien, UniteLocative]:
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
    unite = UniteLocative(bien_id=bien.id, libelle=libelle_unite)
    session.add(unite)
    session.commit()
    session.refresh(unite)
    return bien, unite


def _creer_bien(session, libelle="Immeuble Sedan") -> Bien:
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


def test_liste_sans_depense_recurrente(client_connecte):
    reponse = client_connecte.get("/depenses-recurrentes")
    assert reponse.status_code == 200
    assert "Aucune dépense récurrente" in reponse.text


def test_acces_liste_sans_session_redirige(client):
    reponse = client.get("/depenses-recurrentes", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_formulaire_nouvelle_depense_recurrente_accessible(client_connecte):
    reponse = client_connecte.get("/depenses-recurrentes/nouvelle")
    assert reponse.status_code == 200
    assert "Ajouter une dépense récurrente" in reponse.text


def test_creation_depense_recurrente_pour_un_bien(client_connecte, session, engine):
    bien = _creer_bien(session)

    reponse = client_connecte.post(
        "/depenses-recurrentes",
        data={
            "bien_id": str(bien.id),
            "categorie": "Crédit immobilier",
            "libelle": "Crédit Sedan",
            "montant": "450",
            "frequence": "mensuelle",
            "date_debut": "2024-01-05",
        },
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    with Session(engine) as s:
        template = s.exec(select(DepenseRecurrente).where(DepenseRecurrente.libelle == "Crédit Sedan")).first()
        assert template is not None
        assert template.bien_id == bien.id
        assert template.unite_locative_id is None
        assert template.montant == 450.0
        assert template.date_fin is None


def test_creation_depense_recurrente_pour_une_unite(client_connecte, session, engine):
    bien, unite = _creer_bien_avec_unite(session)

    reponse = client_connecte.post(
        "/depenses-recurrentes",
        data={
            "bien_id": str(bien.id),
            "unite_locative_id": str(unite.id),
            "categorie": "Charges de copropriété",
            "libelle": "Charges Appt 1",
            "montant": "80",
            "frequence": "trimestrielle",
            "date_debut": "2024-01-01",
            "date_fin": "2025-01-01",
        },
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    with Session(engine) as s:
        template = s.exec(select(DepenseRecurrente).where(DepenseRecurrente.libelle == "Charges Appt 1")).first()
        assert template.unite_locative_id == unite.id
        assert template.date_fin == date(2025, 1, 1)


def test_creation_depense_recurrente_bien_inexistant(client_connecte):
    reponse = client_connecte.post(
        "/depenses-recurrentes",
        data={
            "bien_id": "999",
            "categorie": "Crédit immobilier",
            "libelle": "x",
            "montant": "100",
            "frequence": "mensuelle",
            "date_debut": "2024-01-01",
        },
    )
    assert reponse.status_code == 404


def test_creation_depense_recurrente_unite_n_appartient_pas_au_bien(client_connecte, session):
    bien1, _ = _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan")
    _, unite2 = _creer_bien_avec_unite(session, libelle_bien="Immeuble Charleville")

    reponse = client_connecte.post(
        "/depenses-recurrentes",
        data={
            "bien_id": str(bien1.id),
            "unite_locative_id": str(unite2.id),
            "categorie": "Crédit immobilier",
            "libelle": "x",
            "montant": "100",
            "frequence": "mensuelle",
            "date_debut": "2024-01-01",
        },
    )
    assert reponse.status_code == 400


def test_creation_depense_recurrente_date_fin_avant_date_debut(client_connecte, session):
    bien = _creer_bien(session)

    reponse = client_connecte.post(
        "/depenses-recurrentes",
        data={
            "bien_id": str(bien.id),
            "categorie": "Crédit immobilier",
            "libelle": "x",
            "montant": "100",
            "frequence": "mensuelle",
            "date_debut": "2024-06-01",
            "date_fin": "2024-01-01",
        },
    )
    assert reponse.status_code == 400


def test_creation_depense_recurrente_montant_invalide(client_connecte, session):
    bien = _creer_bien(session)

    reponse = client_connecte.post(
        "/depenses-recurrentes",
        data={
            "bien_id": str(bien.id),
            "categorie": "Crédit immobilier",
            "libelle": "x",
            "montant": "abc",
            "frequence": "mensuelle",
            "date_debut": "2024-01-01",
        },
    )
    assert reponse.status_code == 400


def test_creation_depense_recurrente_frequence_invalide(client_connecte, session):
    bien = _creer_bien(session)

    reponse = client_connecte.post(
        "/depenses-recurrentes",
        data={
            "bien_id": str(bien.id),
            "categorie": "Crédit immobilier",
            "libelle": "x",
            "montant": "100",
            "frequence": "hebdomadaire",
            "date_debut": "2024-01-01",
        },
    )
    assert reponse.status_code == 400


def test_formulaire_modifier_depense_recurrente_accessible(client_connecte, session):
    bien = _creer_bien(session)
    template = DepenseRecurrente(
        bien_id=bien.id, categorie="Crédit immobilier", libelle="Crédit Sedan", montant=450.0, frequence="mensuelle", date_debut=date(2024, 1, 5)
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    reponse = client_connecte.get(f"/depenses-recurrentes/{template.id}/modifier")
    assert reponse.status_code == 200
    assert "Crédit Sedan" in reponse.text


def test_formulaire_modifier_depense_recurrente_inexistante(client_connecte):
    assert client_connecte.get("/depenses-recurrentes/999/modifier").status_code == 404


def test_modification_depense_recurrente(client_connecte, session, engine):
    bien = _creer_bien(session)
    template = DepenseRecurrente(
        bien_id=bien.id, categorie="Crédit immobilier", libelle="Crédit Sedan", montant=450.0, frequence="mensuelle", date_debut=date(2024, 1, 5)
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    reponse = client_connecte.post(
        f"/depenses-recurrentes/{template.id}/modifier",
        data={
            "bien_id": str(bien.id),
            "categorie": "Crédit immobilier",
            "libelle": "Crédit Sedan revalorisé",
            "montant": "475",
            "frequence": "mensuelle",
            "date_debut": "2024-01-05",
        },
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    with Session(engine) as s:
        modifie = s.get(DepenseRecurrente, template.id)
        assert modifie.libelle == "Crédit Sedan revalorisé"
        assert modifie.montant == 475.0


def test_modification_depense_recurrente_inexistante(client_connecte):
    reponse = client_connecte.post(
        "/depenses-recurrentes/999/modifier",
        data={
            "bien_id": "1",
            "categorie": "Crédit immobilier",
            "libelle": "x",
            "montant": "100",
            "frequence": "mensuelle",
            "date_debut": "2024-01-01",
        },
    )
    assert reponse.status_code == 404


def test_suppression_depense_recurrente_sans_ligne_generee(client_connecte, session, engine):
    bien = _creer_bien(session)
    template = DepenseRecurrente(
        bien_id=bien.id, categorie="Crédit immobilier", libelle="Crédit Sedan", montant=450.0, frequence="mensuelle", date_debut=date(2024, 1, 5)
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    reponse = client_connecte.post(f"/depenses-recurrentes/{template.id}/supprimer", follow_redirects=False)
    assert reponse.status_code == 303

    with Session(engine) as s:
        assert s.get(DepenseRecurrente, template.id) is None


def test_suppression_depense_recurrente_refusee_si_lignes_generees(client_connecte, session):
    bien = _creer_bien(session)
    template = DepenseRecurrente(
        bien_id=bien.id, categorie="Crédit immobilier", libelle="Crédit Sedan", montant=450.0, frequence="mensuelle", date_debut=date(2024, 1, 5)
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    session.add(
        LigneDepense(
            depense_recurrente_id=template.id,
            bien_id=bien.id,
            categorie="Crédit immobilier",
            libelle="Crédit Sedan",
            montant=450.0,
            date=date(2024, 1, 5),
        )
    )
    session.commit()

    reponse = client_connecte.post(f"/depenses-recurrentes/{template.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_depense_recurrente_inexistante(client_connecte):
    assert client_connecte.post("/depenses-recurrentes/999/supprimer").status_code == 404


def test_generer_echeances_cree_les_lignes_et_redirige_vers_depenses(client_connecte, session, engine):
    bien = _creer_bien(session)
    template = DepenseRecurrente(
        bien_id=bien.id, categorie="Crédit immobilier", libelle="Crédit Sedan", montant=450.0, frequence="mensuelle", date_debut=date(2024, 1, 5)
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    reponse = client_connecte.post("/depenses-recurrentes/generer", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/depenses")

    with Session(engine) as s:
        lignes = s.exec(select(LigneDepense).where(LigneDepense.depense_recurrente_id == template.id)).all()
        assert len(lignes) >= 1


def test_generer_echeances_est_rejouable_sans_effet(client_connecte, session, engine):
    bien = _creer_bien(session)
    template = DepenseRecurrente(
        bien_id=bien.id, categorie="Crédit immobilier", libelle="Crédit Sedan", montant=450.0, frequence="mensuelle", date_debut=date(2024, 1, 5)
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    client_connecte.post("/depenses-recurrentes/generer")
    client_connecte.post("/depenses-recurrentes/generer")

    with Session(engine) as s:
        lignes = s.exec(select(LigneDepense).where(LigneDepense.depense_recurrente_id == template.id)).all()
        assert len(lignes) == len({l.date for l in lignes})


def test_liste_affiche_la_depense_recurrente(client_connecte, session):
    bien = _creer_bien(session)
    template = DepenseRecurrente(
        bien_id=bien.id, categorie="Crédit immobilier", libelle="Crédit Sedan", montant=450.0, frequence="mensuelle", date_debut=date(2024, 1, 5)
    )
    session.add(template)
    session.commit()

    reponse = client_connecte.get("/depenses-recurrentes")
    assert "Crédit Sedan" in reponse.text
    assert "450.00" in reponse.text


def test_liste_depenses_distingue_origine_recurrente(client_connecte, session):
    bien = _creer_bien(session)
    template = DepenseRecurrente(
        bien_id=bien.id, categorie="Crédit immobilier", libelle="Crédit Sedan", montant=450.0, frequence="mensuelle", date_debut=date(2024, 1, 5)
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    session.add(
        LigneDepense(
            depense_recurrente_id=template.id,
            bien_id=bien.id,
            categorie="Crédit immobilier",
            libelle="Crédit Sedan",
            montant=450.0,
            date=date(2024, 1, 5),
        )
    )
    session.commit()

    reponse = client_connecte.get("/depenses")
    assert "récurrente" in reponse.text
