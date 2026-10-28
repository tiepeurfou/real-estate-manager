from datetime import date, datetime, timezone

from app.models import (
    Bien,
    CompteBancaire,
    ContactGestionnaire,
    Gestionnaire,
    MandatGestion,
    ReleveGestion,
    UniteLocative,
    VirementRecu,
)
from app.models.enums import Banque, RoleMandat, StatutExtraction, TypeBien, TypeContact


def _creer_gestionnaire(session, nom="Pergent Immobilier") -> Gestionnaire:
    gestionnaire = Gestionnaire(nom=nom)
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    return gestionnaire


def _creer_bien_avec_unite(session) -> tuple[Bien, UniteLocative]:
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

    return bien, unite


def test_liste_sans_gestionnaire(client_connecte):
    reponse = client_connecte.get("/gestionnaires")
    assert reponse.status_code == 200
    assert "Aucun gestionnaire" in reponse.text


def test_acces_sans_session_redirige(client):
    reponse = client.get("/gestionnaires", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_formulaire_nouveau_pas_capture_par_la_route_detail(client_connecte):
    reponse = client_connecte.get("/gestionnaires/nouveau")
    assert reponse.status_code == 200
    assert "Ajouter un gestionnaire" in reponse.text


def test_creation_gestionnaire_sans_contact(client_connecte, engine):
    reponse = client_connecte.post("/gestionnaires", data={"nom": "ArthurImmo"}, follow_redirects=False)
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        gestionnaire = s.exec(select(Gestionnaire).where(Gestionnaire.nom == "ArthurImmo")).first()
        assert gestionnaire is not None


def test_creation_gestionnaire_avec_plusieurs_contacts(client_connecte, engine):
    reponse = client_connecte.post(
        "/gestionnaires",
        data={
            "nom": "Locagestion",
            "contact_type": ["email", "email", "telephone"],
            "contact_valeur": ["agence@locagestion.fr", "urgences@locagestion.fr", "0102030405"],
        },
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        gestionnaire = s.exec(select(Gestionnaire).where(Gestionnaire.nom == "Locagestion")).first()
        contacts = s.exec(select(ContactGestionnaire).where(ContactGestionnaire.gestionnaire_id == gestionnaire.id)).all()
        assert len(contacts) == 3
        emails = {c.valeur for c in contacts if c.type == TypeContact.EMAIL}
        assert emails == {"agence@locagestion.fr", "urgences@locagestion.fr"}
        telephones = {c.valeur for c in contacts if c.type == TypeContact.TELEPHONE}
        assert telephones == {"0102030405"}


def test_creation_gestionnaire_ignore_les_contacts_vides(client_connecte, session, engine):
    client_connecte.post(
        "/gestionnaires",
        data={"nom": "ArthurImmo", "contact_type": ["email"], "contact_valeur": [""]},
    )

    from sqlmodel import Session, select

    with Session(engine) as s:
        gestionnaire = s.exec(select(Gestionnaire).where(Gestionnaire.nom == "ArthurImmo")).first()
        contacts = s.exec(select(ContactGestionnaire).where(ContactGestionnaire.gestionnaire_id == gestionnaire.id)).all()
        assert contacts == []


def test_modification_gestionnaire_remplace_les_contacts(client_connecte, session, engine):
    gestionnaire = _creer_gestionnaire(session)
    session.add(ContactGestionnaire(gestionnaire_id=gestionnaire.id, type=TypeContact.EMAIL, valeur="ancien@exemple.fr"))
    session.commit()

    client_connecte.post(
        f"/gestionnaires/{gestionnaire.id}/modifier",
        data={"nom": gestionnaire.nom, "contact_type": ["telephone"], "contact_valeur": ["0600000000"]},
    )

    from sqlmodel import Session, select

    with Session(engine) as s:
        contacts = s.exec(select(ContactGestionnaire).where(ContactGestionnaire.gestionnaire_id == gestionnaire.id)).all()
        assert len(contacts) == 1
        assert contacts[0].type == TypeContact.TELEPHONE
        assert contacts[0].valeur == "0600000000"


def test_suppression_gestionnaire_supprime_ses_contacts(client_connecte, session, engine):
    gestionnaire = _creer_gestionnaire(session)
    session.add(ContactGestionnaire(gestionnaire_id=gestionnaire.id, type=TypeContact.EMAIL, valeur="a@b.fr"))
    session.commit()

    reponse = client_connecte.post(f"/gestionnaires/{gestionnaire.id}/supprimer", follow_redirects=False)
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        assert s.exec(select(ContactGestionnaire)).all() == []


def test_detail_gestionnaire_inexistant(client_connecte):
    assert client_connecte.get("/gestionnaires/999").status_code == 404


def test_modification_gestionnaire(client_connecte, session):
    gestionnaire = _creer_gestionnaire(session)

    reponse = client_connecte.post(
        f"/gestionnaires/{gestionnaire.id}/modifier",
        data={"nom": "Pergent Immobilier (nouveau nom)"},
        follow_redirects=False,
    )
    assert reponse.status_code == 303
    detail = client_connecte.get(f"/gestionnaires/{gestionnaire.id}")
    assert "Pergent Immobilier (nouveau nom)" in detail.text


def test_modification_gestionnaire_inexistant(client_connecte):
    assert client_connecte.post("/gestionnaires/999/modifier", data={"nom": "x"}).status_code == 404


def test_suppression_gestionnaire_sans_donnees_liees(client_connecte, session):
    gestionnaire = _creer_gestionnaire(session)

    reponse = client_connecte.post(f"/gestionnaires/{gestionnaire.id}/supprimer", follow_redirects=False)
    assert reponse.status_code == 303
    assert client_connecte.get(f"/gestionnaires/{gestionnaire.id}").status_code == 404


def test_suppression_gestionnaire_refusee_si_mandat_lie(client_connecte, session):
    gestionnaire = _creer_gestionnaire(session)
    _, unite = _creer_bien_avec_unite(session)
    session.add(
        MandatGestion(
            unite_locative_id=unite.id,
            gestionnaire_id=gestionnaire.id,
            role=RoleMandat.GESTION,
            date_debut=date(2024, 1, 1),
        )
    )
    session.commit()

    reponse = client_connecte.post(f"/gestionnaires/{gestionnaire.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_gestionnaire_refusee_si_releve_lie(client_connecte, session):
    gestionnaire = _creer_gestionnaire(session)
    bien, _ = _creer_bien_avec_unite(session)
    session.add(
        ReleveGestion(
            gestionnaire_id=gestionnaire.id,
            bien_id=bien.id,
            periode=date(2024, 9, 1),
            date_reception=datetime.now(timezone.utc),
            chemin_fichier_pdf="x.pdf",
            hash_fichier="hash-unique-gestionnaire",
            statut_extraction=StatutExtraction.TRAITE_OK,
        )
    )
    session.commit()

    reponse = client_connecte.post(f"/gestionnaires/{gestionnaire.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_gestionnaire_refusee_si_virement_lie(client_connecte, session):
    gestionnaire = _creer_gestionnaire(session)
    compte = CompteBancaire(banque=Banque.BOURSORAMA, libelle="Compte Boursorama")
    session.add(compte)
    session.commit()
    session.refresh(compte)

    session.add(
        VirementRecu(
            gestionnaire_id=gestionnaire.id,
            compte_bancaire_id=compte.id,
            montant=1000,
            date_reception=date(2024, 9, 5),
        )
    )
    session.commit()

    reponse = client_connecte.post(f"/gestionnaires/{gestionnaire.id}/supprimer")
    assert reponse.status_code == 409


def test_creation_mandat(client_connecte, session, engine):
    gestionnaire = _creer_gestionnaire(session)
    _, unite = _creer_bien_avec_unite(session)

    reponse_formulaire = client_connecte.get(f"/gestionnaires/{gestionnaire.id}/mandats/nouveau")
    assert reponse_formulaire.status_code == 200

    reponse = client_connecte.post(
        f"/gestionnaires/{gestionnaire.id}/mandats",
        data={"unite_locative_id": str(unite.id), "role": "mise_en_location", "date_debut": "2024-01-01"},
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        mandats = s.exec(select(MandatGestion).where(MandatGestion.gestionnaire_id == gestionnaire.id)).all()
        assert len(mandats) == 1
        assert mandats[0].role == RoleMandat.MISE_EN_LOCATION


def test_creation_mandat_avec_compte_bancaire(client_connecte, session, engine):
    """Le compte de versement est propre au mandat, pas au gestionnaire : un
    même gestionnaire peut verser sur des comptes différents selon le bien
    (ex. Locagestion : un compte pour Sedan, un autre pour Charleville)."""
    gestionnaire = _creer_gestionnaire(session, nom="Locagestion")
    _, unite = _creer_bien_avec_unite(session)
    compte = CompteBancaire(banque=Banque.SG, libelle="Compte SG")
    session.add(compte)
    session.commit()
    session.refresh(compte)

    reponse = client_connecte.post(
        f"/gestionnaires/{gestionnaire.id}/mandats",
        data={
            "unite_locative_id": str(unite.id),
            "role": "gestion",
            "date_debut": "2024-01-01",
            "compte_bancaire_id": str(compte.id),
        },
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        mandat = s.exec(select(MandatGestion).where(MandatGestion.gestionnaire_id == gestionnaire.id)).first()
        assert mandat.compte_bancaire_id == compte.id


def test_meme_gestionnaire_deux_mandats_comptes_differents(client_connecte, session, engine):
    gestionnaire = _creer_gestionnaire(session, nom="Locagestion")
    bien_sedan, unite_sedan = _creer_bien_avec_unite(session)
    bien_charleville = Bien(
        type=TypeBien.IMMEUBLE,
        libelle="Immeuble Charleville",
        adresse_rue="2 rue Test",
        adresse_code_postal="08000",
        adresse_ville="Charleville-Mézières",
    )
    session.add(bien_charleville)
    session.commit()
    session.refresh(bien_charleville)
    unite_charleville = UniteLocative(bien_id=bien_charleville.id, libelle="Appt 1")
    session.add(unite_charleville)
    session.commit()
    session.refresh(unite_charleville)

    compte_sedan = CompteBancaire(banque=Banque.SG, libelle="Compte SG")
    compte_charleville = CompteBancaire(banque=Banque.LCL, libelle="Compte LCL")
    session.add(compte_sedan)
    session.add(compte_charleville)
    session.commit()
    session.refresh(compte_sedan)
    session.refresh(compte_charleville)

    client_connecte.post(
        f"/gestionnaires/{gestionnaire.id}/mandats",
        data={
            "unite_locative_id": str(unite_sedan.id),
            "role": "gestion",
            "date_debut": "2024-01-01",
            "compte_bancaire_id": str(compte_sedan.id),
        },
    )
    client_connecte.post(
        f"/gestionnaires/{gestionnaire.id}/mandats",
        data={
            "unite_locative_id": str(unite_charleville.id),
            "role": "gestion",
            "date_debut": "2024-01-01",
            "compte_bancaire_id": str(compte_charleville.id),
        },
    )

    from sqlmodel import Session, select

    with Session(engine) as s:
        mandats = s.exec(select(MandatGestion).where(MandatGestion.gestionnaire_id == gestionnaire.id)).all()
        comptes_utilises = {m.compte_bancaire_id for m in mandats}
        assert comptes_utilises == {compte_sedan.id, compte_charleville.id}


def test_creation_mandat_compte_bancaire_invalide(client_connecte, session):
    gestionnaire = _creer_gestionnaire(session)
    _, unite = _creer_bien_avec_unite(session)

    reponse = client_connecte.post(
        f"/gestionnaires/{gestionnaire.id}/mandats",
        data={
            "unite_locative_id": str(unite.id),
            "role": "gestion",
            "date_debut": "2024-01-01",
            "compte_bancaire_id": "abc",
        },
    )
    assert reponse.status_code == 400


def test_gestion_complete_se_traduit_par_deux_mandats(client_connecte, session, engine):
    """Une 'gestion locative complète' = le même gestionnaire porte les deux rôles,
    pas une valeur d'enum à part (décision d'architecture actée)."""
    gestionnaire = _creer_gestionnaire(session, nom="ArthurImmo")
    _, unite = _creer_bien_avec_unite(session)

    for role in ("mise_en_location", "gestion"):
        client_connecte.post(
            f"/gestionnaires/{gestionnaire.id}/mandats",
            data={"unite_locative_id": str(unite.id), "role": role, "date_debut": "2024-01-01"},
        )

    from sqlmodel import Session, select

    with Session(engine) as s:
        roles = {
            m.role
            for m in s.exec(select(MandatGestion).where(MandatGestion.gestionnaire_id == gestionnaire.id)).all()
        }
        assert roles == {RoleMandat.MISE_EN_LOCATION, RoleMandat.GESTION}


def test_raccourci_gestion_complete_cree_les_deux_mandats_en_une_fois(client_connecte, session, engine):
    """Le raccourci "gestion_complete" du formulaire n'est pas une 3e valeur
    de RoleMandat : il crée les deux mandats en une seule soumission."""
    gestionnaire = _creer_gestionnaire(session, nom="ArthurImmo")
    _, unite = _creer_bien_avec_unite(session)
    compte = CompteBancaire(banque=Banque.SG, libelle="Compte SG")
    session.add(compte)
    session.commit()
    session.refresh(compte)

    reponse = client_connecte.post(
        f"/gestionnaires/{gestionnaire.id}/mandats",
        data={
            "unite_locative_id": str(unite.id),
            "role": "gestion_complete",
            "date_debut": "2024-01-01",
            "compte_bancaire_id": str(compte.id),
        },
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        mandats = s.exec(select(MandatGestion).where(MandatGestion.gestionnaire_id == gestionnaire.id)).all()
        assert len(mandats) == 2
        roles = {m.role for m in mandats}
        assert roles == {RoleMandat.MISE_EN_LOCATION, RoleMandat.GESTION}

        mandat_gestion = next(m for m in mandats if m.role == RoleMandat.GESTION)
        mandat_mise_en_location = next(m for m in mandats if m.role == RoleMandat.MISE_EN_LOCATION)
        assert mandat_gestion.compte_bancaire_id == compte.id
        assert mandat_mise_en_location.compte_bancaire_id is None


def test_creation_mandat_gestionnaire_inexistant(client_connecte, session):
    _, unite = _creer_bien_avec_unite(session)

    reponse = client_connecte.post(
        "/gestionnaires/999/mandats",
        data={"unite_locative_id": str(unite.id), "role": "gestion", "date_debut": "2024-01-01"},
    )
    assert reponse.status_code == 404


def test_creation_mandat_unite_inexistante(client_connecte, session):
    gestionnaire = _creer_gestionnaire(session)

    reponse = client_connecte.post(
        f"/gestionnaires/{gestionnaire.id}/mandats",
        data={"unite_locative_id": "999", "role": "gestion", "date_debut": "2024-01-01"},
    )
    assert reponse.status_code == 404


def test_creation_mandat_role_invalide(client_connecte, session):
    gestionnaire = _creer_gestionnaire(session)
    _, unite = _creer_bien_avec_unite(session)

    reponse = client_connecte.post(
        f"/gestionnaires/{gestionnaire.id}/mandats",
        data={"unite_locative_id": str(unite.id), "role": "mise_en_vente", "date_debut": "2024-01-01"},
    )
    assert reponse.status_code == 400


def test_creation_mandat_date_invalide(client_connecte, session):
    gestionnaire = _creer_gestionnaire(session)
    _, unite = _creer_bien_avec_unite(session)

    reponse = client_connecte.post(
        f"/gestionnaires/{gestionnaire.id}/mandats",
        data={"unite_locative_id": str(unite.id), "role": "gestion", "date_debut": "pas-une-date"},
    )
    assert reponse.status_code == 400
