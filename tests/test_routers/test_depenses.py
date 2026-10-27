from datetime import date, datetime, timezone

from app.models import Bien, Gestionnaire, LigneDepense, ReleveGestion, UniteLocative
from app.models.enums import StatutExtraction, TypeBien


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
