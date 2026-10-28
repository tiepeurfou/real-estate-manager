from datetime import date, datetime, timezone

from app.models import Bien, Gestionnaire, LigneDepense, ReleveGestion, UniteLocative
from app.models.enums import StatutExtraction, TypeBien


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


def _creer_releve(session, bien) -> ReleveGestion:
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
        hash_fichier=f"hash-{bien.id}",
        statut_extraction=StatutExtraction.TRAITE_OK,
    )
    session.add(releve)
    session.commit()
    session.refresh(releve)
    return releve


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


def test_liste_sans_depense(client_connecte):
    reponse = client_connecte.get("/depenses")
    assert reponse.status_code == 200
    assert "Aucune dépense" in reponse.text


def test_acces_sans_session_redirige(client):
    reponse = client.get("/depenses", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_totaux_par_categorie(client_connecte, session):
    bien = _creer_bien(session)
    releve = _creer_releve(session, bien)

    session.add(
        LigneDepense(
            releve_gestion_id=releve.id, bien_id=bien.id, categorie="Travaux", libelle="Plomberie", montant=200, date=date(2024, 9, 10)
        )
    )
    session.add(
        LigneDepense(
            releve_gestion_id=releve.id, bien_id=bien.id, categorie="Travaux", libelle="Peinture", montant=100, date=date(2024, 9, 15)
        )
    )
    session.add(
        LigneDepense(
            releve_gestion_id=releve.id,
            bien_id=bien.id,
            categorie="Honoraires de gestion",
            libelle="Honoraires",
            montant=50,
            date=date(2024, 9, 30),
        )
    )
    session.commit()

    reponse = client_connecte.get("/depenses")
    assert "Travaux : 300.00" in reponse.text
    assert "Honoraires de gestion : 50.00" in reponse.text


def test_filtre_par_bien(client_connecte, session):
    bien1 = _creer_bien(session, libelle="Immeuble Sedan")
    bien2 = _creer_bien(session, libelle="Immeuble Charleville")
    releve1 = _creer_releve(session, bien1)
    releve2 = _creer_releve(session, bien2)

    session.add(
        LigneDepense(releve_gestion_id=releve1.id, bien_id=bien1.id, categorie="Travaux", libelle="A", montant=100, date=date(2024, 9, 1))
    )
    session.add(
        LigneDepense(releve_gestion_id=releve2.id, bien_id=bien2.id, categorie="Travaux", libelle="B", montant=200, date=date(2024, 9, 1))
    )
    session.commit()

    reponse = client_connecte.get("/depenses", params={"bien_id": str(bien1.id)})
    assert "100.00" in reponse.text
    assert "200.00" not in reponse.text


def test_filtre_par_categorie(client_connecte, session):
    bien = _creer_bien(session)
    releve = _creer_releve(session, bien)

    session.add(
        LigneDepense(releve_gestion_id=releve.id, bien_id=bien.id, categorie="Travaux", libelle="A", montant=100, date=date(2024, 9, 1))
    )
    session.add(
        LigneDepense(
            releve_gestion_id=releve.id, bien_id=bien.id, categorie="Assurance", libelle="B", montant=80, date=date(2024, 9, 1)
        )
    )
    session.commit()

    reponse = client_connecte.get("/depenses", params={"categorie": "Assurance"})
    assert "80.00" in reponse.text
    assert "100.00" not in reponse.text


def test_filtre_bien_invalide_est_ignore(client_connecte, session):
    bien = _creer_bien(session)
    releve = _creer_releve(session, bien)
    session.add(
        LigneDepense(releve_gestion_id=releve.id, bien_id=bien.id, categorie="Travaux", libelle="A", montant=100, date=date(2024, 9, 1))
    )
    session.commit()

    reponse = client_connecte.get("/depenses", params={"bien_id": "abc"})
    assert reponse.status_code == 200
    assert "100.00" in reponse.text


def test_formulaire_nouvelle_depense_accessible(client_connecte):
    reponse = client_connecte.get("/depenses/nouvelle")
    assert reponse.status_code == 200
    assert "Ajouter une dépense" in reponse.text


def test_acces_formulaire_sans_session_redirige(client):
    reponse = client.get("/depenses/nouvelle", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_creation_depense_manuelle_pour_un_bien(client_connecte, session, engine):
    bien, _ = _creer_bien_avec_unite(session)

    reponse = client_connecte.post(
        "/depenses",
        data={
            "bien_id": str(bien.id),
            "categorie": "Taxe foncière",
            "libelle": "Taxe foncière 2024",
            "montant": "1200",
            "date": "2024-10-15",
        },
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        ligne = s.exec(select(LigneDepense).where(LigneDepense.libelle == "Taxe foncière 2024")).first()
        assert ligne is not None
        assert ligne.releve_gestion_id is None
        assert ligne.bien_id == bien.id
        assert ligne.unite_locative_id is None
        assert ligne.montant == 1200


def test_creation_depense_manuelle_pour_une_unite(client_connecte, session, engine):
    bien, unite = _creer_bien_avec_unite(session)

    reponse = client_connecte.post(
        "/depenses",
        data={
            "bien_id": str(bien.id),
            "unite_locative_id": str(unite.id),
            "categorie": "Travaux",
            "libelle": "Remplacement chaudière",
            "montant": "800",
            "date": "2024-10-15",
        },
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        ligne = s.exec(select(LigneDepense).where(LigneDepense.libelle == "Remplacement chaudière")).first()
        assert ligne.unite_locative_id == unite.id
        assert ligne.bien_id is None


def test_creation_depense_bien_inexistant(client_connecte):
    reponse = client_connecte.post(
        "/depenses",
        data={"bien_id": "999", "categorie": "Travaux", "libelle": "x", "montant": "100", "date": "2024-10-15"},
    )
    assert reponse.status_code == 404


def test_creation_depense_unite_inexistante(client_connecte, session):
    bien, _ = _creer_bien_avec_unite(session)

    reponse = client_connecte.post(
        "/depenses",
        data={
            "bien_id": str(bien.id),
            "unite_locative_id": "999",
            "categorie": "Travaux",
            "libelle": "x",
            "montant": "100",
            "date": "2024-10-15",
        },
    )
    assert reponse.status_code == 404


def test_creation_depense_unite_n_appartient_pas_au_bien(client_connecte, session):
    bien1, _ = _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan")
    _, unite2 = _creer_bien_avec_unite(session, libelle_bien="Immeuble Charleville")

    reponse = client_connecte.post(
        "/depenses",
        data={
            "bien_id": str(bien1.id),
            "unite_locative_id": str(unite2.id),
            "categorie": "Travaux",
            "libelle": "x",
            "montant": "100",
            "date": "2024-10-15",
        },
    )
    assert reponse.status_code == 400


def test_creation_depense_montant_invalide(client_connecte, session):
    bien, _ = _creer_bien_avec_unite(session)

    reponse = client_connecte.post(
        "/depenses",
        data={"bien_id": str(bien.id), "categorie": "Travaux", "libelle": "x", "montant": "abc", "date": "2024-10-15"},
    )
    assert reponse.status_code == 400


def test_creation_depense_date_invalide(client_connecte, session):
    bien, _ = _creer_bien_avec_unite(session)

    reponse = client_connecte.post(
        "/depenses",
        data={"bien_id": str(bien.id), "categorie": "Travaux", "libelle": "x", "montant": "100", "date": "pas-une-date"},
    )
    assert reponse.status_code == 400


def test_suppression_depense_manuelle(client_connecte, session, engine):
    bien, _ = _creer_bien_avec_unite(session)
    ligne = LigneDepense(
        releve_gestion_id=None, bien_id=bien.id, categorie="Taxe foncière", libelle="x", montant=100, date=date(2024, 10, 1)
    )
    session.add(ligne)
    session.commit()
    session.refresh(ligne)

    reponse = client_connecte.post(f"/depenses/{ligne.id}/supprimer", follow_redirects=False)
    assert reponse.status_code == 303

    from sqlmodel import Session

    with Session(engine) as s:
        assert s.get(LigneDepense, ligne.id) is None


def test_suppression_depense_refusee_si_issue_d_un_releve(client_connecte, session):
    bien = _creer_bien(session)
    releve = _creer_releve(session, bien)
    ligne = LigneDepense(
        releve_gestion_id=releve.id, bien_id=bien.id, categorie="Travaux", libelle="x", montant=100, date=date(2024, 9, 1)
    )
    session.add(ligne)
    session.commit()
    session.refresh(ligne)

    reponse = client_connecte.post(f"/depenses/{ligne.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_depense_inexistante(client_connecte):
    assert client_connecte.post("/depenses/999/supprimer").status_code == 404


def test_liste_distingue_origine_manuelle_et_releve(client_connecte, session):
    bien = _creer_bien(session)
    releve = _creer_releve(session, bien)
    session.add(
        LigneDepense(releve_gestion_id=releve.id, bien_id=bien.id, categorie="Travaux", libelle="Issue relevé", montant=100, date=date(2024, 9, 1))
    )
    session.add(
        LigneDepense(releve_gestion_id=None, bien_id=bien.id, categorie="Taxe foncière", libelle="Saisie manuelle", montant=1200, date=date(2024, 10, 1))
    )
    session.commit()

    reponse = client_connecte.get("/depenses")
    assert "manuelle" in reponse.text
    assert "relevé" in reponse.text
    assert "Supprimer" in reponse.text
