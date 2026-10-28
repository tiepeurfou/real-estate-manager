from datetime import date

from app.models import Bien, CompteBancaire, Gestionnaire, MandatGestion, UniteLocative, VirementRecu
from app.models.enums import Banque, RoleMandat, TypeBien


def _creer_compte(session, libelle="Compte SG Sedan") -> CompteBancaire:
    compte = CompteBancaire(banque=Banque.SG, libelle=libelle)
    session.add(compte)
    session.commit()
    session.refresh(compte)
    return compte


def test_liste_sans_compte(client_connecte):
    reponse = client_connecte.get("/comptes-bancaires")
    assert reponse.status_code == 200
    assert "Aucun compte bancaire" in reponse.text


def test_acces_sans_session_redirige(client):
    reponse = client.get("/comptes-bancaires", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_creation_compte_bancaire(client_connecte, engine):
    reponse = client_connecte.post(
        "/comptes-bancaires",
        data={"banque": "LCL", "libelle": "Compte LCL Villiers", "iban": "FR76XXXX"},
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        compte = s.exec(select(CompteBancaire).where(CompteBancaire.libelle == "Compte LCL Villiers")).first()
        assert compte is not None
        assert compte.banque == Banque.LCL
        assert compte.iban == "FR76XXXX"


def test_creation_compte_bancaire_banque_invalide(client_connecte):
    reponse = client_connecte.post(
        "/comptes-bancaires", data={"banque": "CIC", "libelle": "x"}
    )
    assert reponse.status_code == 400


def test_modification_compte_bancaire(client_connecte, session):
    compte = _creer_compte(session)

    reponse = client_connecte.post(
        f"/comptes-bancaires/{compte.id}/modifier",
        data={"libelle": "Nouveau libellé", "iban": ""},
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    liste = client_connecte.get("/comptes-bancaires")
    assert "Nouveau libellé" in liste.text


def test_modification_compte_bancaire_inexistant(client_connecte):
    assert client_connecte.get("/comptes-bancaires/999/modifier").status_code == 404
    assert client_connecte.post("/comptes-bancaires/999/modifier", data={"libelle": "x"}).status_code == 404


def test_suppression_compte_bancaire_sans_donnees_liees(client_connecte, session):
    compte = _creer_compte(session)

    reponse = client_connecte.post(f"/comptes-bancaires/{compte.id}/supprimer", follow_redirects=False)
    assert reponse.status_code == 303
    assert "Nouveau libellé" not in client_connecte.get("/comptes-bancaires").text


def test_suppression_compte_bancaire_refusee_si_mandat_lie(client_connecte, session):
    compte = _creer_compte(session)
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

    gestionnaire = Gestionnaire(nom="ArthurImmo")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)

    session.add(
        MandatGestion(
            unite_locative_id=unite.id,
            gestionnaire_id=gestionnaire.id,
            role=RoleMandat.GESTION,
            date_debut=date(2024, 1, 1),
            compte_bancaire_id=compte.id,
        )
    )
    session.commit()

    reponse = client_connecte.post(f"/comptes-bancaires/{compte.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_compte_bancaire_refusee_si_virement_lie(client_connecte, session):
    compte = _creer_compte(session)
    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)

    session.add(
        VirementRecu(
            gestionnaire_id=gestionnaire.id,
            compte_bancaire_id=compte.id,
            montant=500,
            date_reception=date(2024, 9, 5),
        )
    )
    session.commit()

    reponse = client_connecte.post(f"/comptes-bancaires/{compte.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_compte_bancaire_inexistant(client_connecte):
    assert client_connecte.post("/comptes-bancaires/999/supprimer").status_code == 404
