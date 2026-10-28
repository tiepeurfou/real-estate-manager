from datetime import date, datetime, timezone

from app.models import (
    Bien,
    CompteBancaire,
    Gestionnaire,
    LigneDepense,
    LignePaiement,
    MandatGestion,
    Rapprochement,
    RapprochementLigne,
    ReleveGestion,
    UniteLocative,
    VirementRecu,
)
from app.models.enums import Banque, RoleMandat, StatutExtraction, StatutPaiement, TypeBien


def _creer_contexte(session, hash_releve="hash-virement-1"):
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

    compte = CompteBancaire(banque=Banque.SG, libelle="Compte SG Sedan")
    session.add(compte)
    session.commit()
    session.refresh(compte)

    gestionnaire = Gestionnaire(nom="Locagestion")
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

    releve = ReleveGestion(
        gestionnaire_id=gestionnaire.id,
        bien_id=bien.id,
        periode=date(2024, 9, 1),
        date_reception=datetime.now(timezone.utc),
        chemin_fichier_pdf="x.pdf",
        hash_fichier=hash_releve,
        statut_extraction=StatutExtraction.TRAITE_OK,
    )
    session.add(releve)
    session.commit()
    session.refresh(releve)

    return {"bien": bien, "unite": unite, "compte": compte, "gestionnaire": gestionnaire, "releve": releve}


def test_liste_sans_virement(client_connecte):
    reponse = client_connecte.get("/virements")
    assert reponse.status_code == 200
    assert "Aucun virement" in reponse.text


def test_acces_sans_session_redirige(client):
    reponse = client.get("/virements", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_formulaire_nouveau_pas_capture_par_la_route_detail(client_connecte):
    reponse = client_connecte.get("/virements/nouveau")
    assert reponse.status_code == 200
    assert "Déclarer un virement" in reponse.text


def test_creation_virement(client_connecte, session, engine):
    ctx = _creer_contexte(session)

    reponse = client_connecte.post(
        "/virements",
        data={
            "gestionnaire_id": str(ctx["gestionnaire"].id),
            "compte_bancaire_id": str(ctx["compte"].id),
            "montant": "450",
            "date_reception": "2024-10-05",
        },
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        virement = s.exec(select(VirementRecu).where(VirementRecu.montant == 450)).first()
        assert virement is not None
        assert virement.gestionnaire_id == ctx["gestionnaire"].id


def test_creation_virement_gestionnaire_invalide(client_connecte, session):
    ctx = _creer_contexte(session)

    reponse = client_connecte.post(
        "/virements",
        data={
            "gestionnaire_id": "abc",
            "compte_bancaire_id": str(ctx["compte"].id),
            "montant": "450",
            "date_reception": "2024-10-05",
        },
    )
    assert reponse.status_code == 400


def test_creation_virement_gestionnaire_inexistant(client_connecte, session):
    ctx = _creer_contexte(session)

    reponse = client_connecte.post(
        "/virements",
        data={
            "gestionnaire_id": "999",
            "compte_bancaire_id": str(ctx["compte"].id),
            "montant": "450",
            "date_reception": "2024-10-05",
        },
    )
    assert reponse.status_code == 404


def test_creation_virement_compte_inexistant(client_connecte, session):
    ctx = _creer_contexte(session)

    reponse = client_connecte.post(
        "/virements",
        data={
            "gestionnaire_id": str(ctx["gestionnaire"].id),
            "compte_bancaire_id": "999",
            "montant": "450",
            "date_reception": "2024-10-05",
        },
    )
    assert reponse.status_code == 404


def test_creation_virement_date_invalide(client_connecte, session):
    ctx = _creer_contexte(session)

    reponse = client_connecte.post(
        "/virements",
        data={
            "gestionnaire_id": str(ctx["gestionnaire"].id),
            "compte_bancaire_id": str(ctx["compte"].id),
            "montant": "450",
            "date_reception": "pas-une-date",
        },
    )
    assert reponse.status_code == 400


def test_detail_virement_inexistant(client_connecte):
    assert client_connecte.get("/virements/999").status_code == 404


def test_detail_virement_sans_rapprochement_affiche_les_candidats(client_connecte, session):
    ctx = _creer_contexte(session)
    session.add(
        LignePaiement(
            releve_gestion_id=ctx["releve"].id,
            unite_locative_id=ctx["unite"].id,
            periode=date(2024, 9, 1),
            montant_attendu=500,
            montant_percu=500,
            statut=StatutPaiement.PAYE,
        )
    )
    session.commit()

    virement = VirementRecu(
        gestionnaire_id=ctx["gestionnaire"].id,
        compte_bancaire_id=ctx["compte"].id,
        montant=500,
        date_reception=date(2024, 10, 5),
    )
    session.add(virement)
    session.commit()
    session.refresh(virement)

    reponse = client_connecte.get(f"/virements/{virement.id}")
    assert reponse.status_code == 200
    assert "Appt 1" in reponse.text


def test_rapprochement_complet_sans_ecart(client_connecte, session, engine):
    ctx = _creer_contexte(session)
    paiement = LignePaiement(
        releve_gestion_id=ctx["releve"].id,
        unite_locative_id=ctx["unite"].id,
        periode=date(2024, 9, 1),
        montant_attendu=500,
        montant_percu=500,
        statut=StatutPaiement.PAYE,
    )
    depense = LigneDepense(
        releve_gestion_id=ctx["releve"].id,
        unite_locative_id=ctx["unite"].id,
        categorie="Honoraires de gestion",
        libelle="Honoraires septembre",
        montant=50,
        date=date(2024, 9, 30),
    )
    session.add(paiement)
    session.add(depense)
    session.commit()
    session.refresh(paiement)
    session.refresh(depense)

    virement = VirementRecu(
        gestionnaire_id=ctx["gestionnaire"].id,
        compte_bancaire_id=ctx["compte"].id,
        montant=450,
        date_reception=date(2024, 10, 5),
    )
    session.add(virement)
    session.commit()
    session.refresh(virement)

    reponse = client_connecte.post(
        f"/virements/{virement.id}/rapprocher",
        data={"paiement_ids": [str(paiement.id)], "depense_ids": [str(depense.id)]},
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        rapprochement = s.exec(select(Rapprochement).where(Rapprochement.virement_recu_id == virement.id)).first()
        assert rapprochement is not None
        assert rapprochement.ecart == 0
        liens = s.exec(select(RapprochementLigne).where(RapprochementLigne.rapprochement_id == rapprochement.id)).all()
        assert len(liens) == 2

    detail = client_connecte.get(f"/virements/{virement.id}")
    assert "sans écart" not in detail.text or "0.00" in detail.text


def test_rapprochement_avec_ecart(client_connecte, session, engine):
    ctx = _creer_contexte(session)
    paiement = LignePaiement(
        releve_gestion_id=ctx["releve"].id,
        unite_locative_id=ctx["unite"].id,
        periode=date(2024, 9, 1),
        montant_attendu=500,
        montant_percu=500,
        statut=StatutPaiement.PAYE,
    )
    session.add(paiement)
    session.commit()
    session.refresh(paiement)

    virement = VirementRecu(
        gestionnaire_id=ctx["gestionnaire"].id,
        compte_bancaire_id=ctx["compte"].id,
        montant=480,
        date_reception=date(2024, 10, 5),
    )
    session.add(virement)
    session.commit()
    session.refresh(virement)

    client_connecte.post(f"/virements/{virement.id}/rapprocher", data={"paiement_ids": [str(paiement.id)]})

    from sqlmodel import Session, select

    with Session(engine) as s:
        rapprochement = s.exec(select(Rapprochement).where(Rapprochement.virement_recu_id == virement.id)).first()
        assert rapprochement.ecart == -20


def test_rapprochement_refuse_si_deja_rapproche(client_connecte, session):
    ctx = _creer_contexte(session)
    virement = VirementRecu(
        gestionnaire_id=ctx["gestionnaire"].id, compte_bancaire_id=ctx["compte"].id, montant=0, date_reception=date(2024, 10, 5)
    )
    session.add(virement)
    session.commit()
    session.refresh(virement)
    session.add(Rapprochement(virement_recu_id=virement.id, ecart=0))
    session.commit()

    reponse = client_connecte.post(f"/virements/{virement.id}/rapprocher", data={})
    assert reponse.status_code == 409


def test_rapprochement_ligne_paiement_inexistante(client_connecte, session):
    ctx = _creer_contexte(session)
    virement = VirementRecu(
        gestionnaire_id=ctx["gestionnaire"].id, compte_bancaire_id=ctx["compte"].id, montant=500, date_reception=date(2024, 10, 5)
    )
    session.add(virement)
    session.commit()
    session.refresh(virement)

    reponse = client_connecte.post(f"/virements/{virement.id}/rapprocher", data={"paiement_ids": ["999"]})
    assert reponse.status_code == 404


def test_rapprochement_id_invalide(client_connecte, session):
    ctx = _creer_contexte(session)
    virement = VirementRecu(
        gestionnaire_id=ctx["gestionnaire"].id, compte_bancaire_id=ctx["compte"].id, montant=500, date_reception=date(2024, 10, 5)
    )
    session.add(virement)
    session.commit()
    session.refresh(virement)

    reponse = client_connecte.post(f"/virements/{virement.id}/rapprocher", data={"paiement_ids": ["abc"]})
    assert reponse.status_code == 400


def test_ligne_deja_rapprochee_exclue_des_candidats_d_un_autre_virement(client_connecte, session):
    ctx = _creer_contexte(session)
    paiement = LignePaiement(
        releve_gestion_id=ctx["releve"].id,
        unite_locative_id=ctx["unite"].id,
        periode=date(2024, 9, 1),
        montant_attendu=500,
        montant_percu=500,
        statut=StatutPaiement.PAYE,
    )
    session.add(paiement)
    session.commit()
    session.refresh(paiement)

    virement1 = VirementRecu(
        gestionnaire_id=ctx["gestionnaire"].id, compte_bancaire_id=ctx["compte"].id, montant=500, date_reception=date(2024, 10, 5)
    )
    session.add(virement1)
    session.commit()
    session.refresh(virement1)
    client_connecte.post(f"/virements/{virement1.id}/rapprocher", data={"paiement_ids": [str(paiement.id)]})

    virement2 = VirementRecu(
        gestionnaire_id=ctx["gestionnaire"].id, compte_bancaire_id=ctx["compte"].id, montant=0, date_reception=date(2024, 11, 5)
    )
    session.add(virement2)
    session.commit()
    session.refresh(virement2)

    reponse = client_connecte.get(f"/virements/{virement2.id}")
    assert "Appt 1" not in reponse.text


def test_suppression_rapprochement(client_connecte, session, engine):
    ctx = _creer_contexte(session)
    paiement = LignePaiement(
        releve_gestion_id=ctx["releve"].id,
        unite_locative_id=ctx["unite"].id,
        periode=date(2024, 9, 1),
        montant_attendu=500,
        montant_percu=500,
        statut=StatutPaiement.PAYE,
    )
    session.add(paiement)
    session.commit()
    session.refresh(paiement)

    virement = VirementRecu(
        gestionnaire_id=ctx["gestionnaire"].id, compte_bancaire_id=ctx["compte"].id, montant=500, date_reception=date(2024, 10, 5)
    )
    session.add(virement)
    session.commit()
    session.refresh(virement)
    client_connecte.post(f"/virements/{virement.id}/rapprocher", data={"paiement_ids": [str(paiement.id)]})

    reponse = client_connecte.post(f"/virements/{virement.id}/rapprochement/supprimer", follow_redirects=False)
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        assert s.exec(select(Rapprochement).where(Rapprochement.virement_recu_id == virement.id)).first() is None

    detail = client_connecte.get(f"/virements/{virement.id}")
    assert "Appt 1" in detail.text


def test_suppression_rapprochement_inexistant(client_connecte, session):
    ctx = _creer_contexte(session)
    virement = VirementRecu(
        gestionnaire_id=ctx["gestionnaire"].id, compte_bancaire_id=ctx["compte"].id, montant=500, date_reception=date(2024, 10, 5)
    )
    session.add(virement)
    session.commit()
    session.refresh(virement)

    reponse = client_connecte.post(f"/virements/{virement.id}/rapprochement/supprimer")
    assert reponse.status_code == 404


def test_suppression_virement_sans_rapprochement(client_connecte, session):
    ctx = _creer_contexte(session)
    virement = VirementRecu(
        gestionnaire_id=ctx["gestionnaire"].id, compte_bancaire_id=ctx["compte"].id, montant=500, date_reception=date(2024, 10, 5)
    )
    session.add(virement)
    session.commit()
    session.refresh(virement)

    reponse = client_connecte.post(f"/virements/{virement.id}/supprimer", follow_redirects=False)
    assert reponse.status_code == 303
    assert client_connecte.get(f"/virements/{virement.id}").status_code == 404


def test_suppression_virement_refusee_si_rapproche(client_connecte, session):
    ctx = _creer_contexte(session)
    virement = VirementRecu(
        gestionnaire_id=ctx["gestionnaire"].id, compte_bancaire_id=ctx["compte"].id, montant=0, date_reception=date(2024, 10, 5)
    )
    session.add(virement)
    session.commit()
    session.refresh(virement)
    session.add(Rapprochement(virement_recu_id=virement.id, ecart=0))
    session.commit()

    reponse = client_connecte.post(f"/virements/{virement.id}/supprimer")
    assert reponse.status_code == 409


def test_suppression_virement_inexistant(client_connecte):
    assert client_connecte.post("/virements/999/supprimer").status_code == 404
