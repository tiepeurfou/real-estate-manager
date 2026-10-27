from datetime import date

import app.services.releves as releves_module
from app.models import Bien, Gestionnaire, LignePaiement, RapprochementLigne, ReleveGestion, UniteLocative
from app.models.enums import StatutExtraction, StatutPaiement, TypeBien
from app.services.extraction.base import LignePaiementExtraite, ResultatExtraction
from tests.aide_pdf import creer_pdf_bytes


def _creer_bien(session, libelle="Villiers-sur-Marne") -> Bien:
    bien = Bien(
        type=TypeBien.APPARTEMENT_ISOLE,
        libelle=libelle,
        adresse_rue="rue",
        adresse_code_postal="94350",
        adresse_ville="Villiers-sur-Marne",
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)
    session.add(UniteLocative(bien_id=bien.id, libelle=libelle))
    session.commit()
    return bien


def _creer_gestionnaire(session, nom="ArthurImmo") -> Gestionnaire:
    gestionnaire = Gestionnaire(nom=nom)
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    return gestionnaire


def test_liste_sans_document(client_connecte):
    reponse = client_connecte.get("/documents")
    assert reponse.status_code == 200
    assert "Aucun document" in reponse.text


def test_acces_sans_session_redirige(client):
    reponse = client.get("/documents", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_formulaire_nouveau_pas_capture_par_la_route_detail(client_connecte):
    reponse = client_connecte.get("/documents/nouveau")
    assert reponse.status_code == 200
    assert "Importer un compte-rendu" in reponse.text


def test_televersement_pdf_adaptateur_non_calibre(client_connecte, session, dossier_documents_temporaire, engine):
    bien = _creer_bien(session)
    gestionnaire = _creer_gestionnaire(session)
    contenu = creer_pdf_bytes("Compte-rendu ArthurImmo septembre 2024")

    reponse = client_connecte.post(
        "/documents",
        data={"gestionnaire_id": str(gestionnaire.id), "bien_id": str(bien.id), "periode": "2024-09-01"},
        files={"fichier": ("releve.pdf", contenu, "application/pdf")},
        follow_redirects=False,
    )
    assert reponse.status_code == 303

    from sqlmodel import Session, select

    with Session(engine) as s:
        releve = s.exec(select(ReleveGestion)).first()
        assert releve is not None
        assert releve.statut_extraction == StatutExtraction.ERREUR_EXTRACTION
        assert releve.erreur_extraction_message is not None


def test_televersement_refuse_un_fichier_non_pdf(client_connecte, session, dossier_documents_temporaire):
    bien = _creer_bien(session)
    gestionnaire = _creer_gestionnaire(session)

    reponse = client_connecte.post(
        "/documents",
        data={"gestionnaire_id": str(gestionnaire.id), "bien_id": str(bien.id), "periode": "2024-09-01"},
        files={"fichier": ("releve.txt", b"pas un pdf", "text/plain")},
    )
    assert reponse.status_code == 400


def test_televersement_refuse_un_doublon(client_connecte, session, dossier_documents_temporaire, engine):
    bien = _creer_bien(session)
    gestionnaire = _creer_gestionnaire(session)
    contenu = creer_pdf_bytes("Même contenu")

    donnees = {"gestionnaire_id": str(gestionnaire.id), "bien_id": str(bien.id), "periode": "2024-09-01"}
    client_connecte.post("/documents", data=donnees, files={"fichier": ("releve.pdf", contenu, "application/pdf")})
    reponse = client_connecte.post(
        "/documents", data=donnees, files={"fichier": ("releve-bis.pdf", contenu, "application/pdf")}
    )
    assert reponse.status_code == 400

    from sqlmodel import Session, select

    with Session(engine) as s:
        assert len(s.exec(select(ReleveGestion)).all()) == 1


def test_televersement_gestionnaire_inexistant(client_connecte, session, dossier_documents_temporaire):
    bien = _creer_bien(session)
    contenu = creer_pdf_bytes("x")

    reponse = client_connecte.post(
        "/documents",
        data={"gestionnaire_id": "999", "bien_id": str(bien.id), "periode": "2024-09-01"},
        files={"fichier": ("releve.pdf", contenu, "application/pdf")},
    )
    assert reponse.status_code == 404


def test_televersement_bien_inexistant(client_connecte, session, dossier_documents_temporaire):
    gestionnaire = _creer_gestionnaire(session)
    contenu = creer_pdf_bytes("x")

    reponse = client_connecte.post(
        "/documents",
        data={"gestionnaire_id": str(gestionnaire.id), "bien_id": "999", "periode": "2024-09-01"},
        files={"fichier": ("releve.pdf", contenu, "application/pdf")},
    )
    assert reponse.status_code == 404


def test_televersement_periode_invalide(client_connecte, session, dossier_documents_temporaire):
    bien = _creer_bien(session)
    gestionnaire = _creer_gestionnaire(session)
    contenu = creer_pdf_bytes("x")

    reponse = client_connecte.post(
        "/documents",
        data={"gestionnaire_id": str(gestionnaire.id), "bien_id": str(bien.id), "periode": "pas-une-date"},
        files={"fichier": ("releve.pdf", contenu, "application/pdf")},
    )
    assert reponse.status_code == 400


def test_detail_document_inexistant(client_connecte):
    assert client_connecte.get("/documents/999").status_code == 404


def test_voir_le_fichier_pdf(client_connecte, session, dossier_documents_temporaire):
    bien = _creer_bien(session)
    gestionnaire = _creer_gestionnaire(session)
    contenu = creer_pdf_bytes("Contenu du PDF")

    client_connecte.post(
        "/documents",
        data={"gestionnaire_id": str(gestionnaire.id), "bien_id": str(bien.id), "periode": "2024-09-01"},
        files={"fichier": ("releve.pdf", contenu, "application/pdf")},
    )

    reponse = client_connecte.get("/documents/1/fichier")
    assert reponse.status_code == 200
    assert reponse.headers["content-type"] == "application/pdf"


def test_voir_le_fichier_document_inexistant(client_connecte):
    assert client_connecte.get("/documents/999/fichier").status_code == 404


def test_relancer_extraction(client_connecte, session, dossier_documents_temporaire):
    bien = _creer_bien(session)
    gestionnaire = _creer_gestionnaire(session)
    contenu = creer_pdf_bytes("Compte-rendu")

    client_connecte.post(
        "/documents",
        data={"gestionnaire_id": str(gestionnaire.id), "bien_id": str(bien.id), "periode": "2024-09-01"},
        files={"fichier": ("releve.pdf", contenu, "application/pdf")},
    )

    reponse = client_connecte.post("/documents/1/relancer", follow_redirects=False)
    assert reponse.status_code == 303

    detail = client_connecte.get("/documents/1")
    assert "pas encore été calibré" in detail.text


def test_relancer_extraction_document_inexistant(client_connecte):
    assert client_connecte.post("/documents/999/relancer").status_code == 404


def test_relancer_extraction_refusee_si_lignes_rapprochees(
    client_connecte, session, dossier_documents_temporaire, monkeypatch, engine
):
    bien = _creer_bien(session)
    gestionnaire = _creer_gestionnaire(session, nom="Locagestion")

    def adaptateur_factice(nom):
        class A:
            def extraire(self, texte):
                return ResultatExtraction(
                    paiements=[
                        LignePaiementExtraite(
                            unite_libelle="Villiers-sur-Marne",
                            periode=date(2024, 9, 1),
                            montant_attendu=500,
                            montant_percu=500,
                            statut=StatutPaiement.PAYE,
                        )
                    ]
                )

        return A()

    monkeypatch.setattr(releves_module, "obtenir_adaptateur", adaptateur_factice)

    contenu = creer_pdf_bytes("Compte-rendu")
    client_connecte.post(
        "/documents",
        data={"gestionnaire_id": str(gestionnaire.id), "bien_id": str(bien.id), "periode": "2024-09-01"},
        files={"fichier": ("releve.pdf", contenu, "application/pdf")},
    )

    from sqlmodel import Session, select
    from app.models import CompteBancaire, Rapprochement, VirementRecu
    from app.models.enums import Banque

    with Session(engine) as s:
        paiement = s.exec(select(LignePaiement)).first()
        compte = CompteBancaire(banque=Banque.SG, libelle="Compte SG")
        s.add(compte)
        s.commit()
        s.refresh(compte)
        virement = VirementRecu(gestionnaire_id=gestionnaire.id, compte_bancaire_id=compte.id, montant=500, date_reception=date(2024, 10, 5))
        s.add(virement)
        s.commit()
        s.refresh(virement)
        rapprochement = Rapprochement(virement_recu_id=virement.id, ecart=0)
        s.add(rapprochement)
        s.commit()
        s.refresh(rapprochement)
        s.add(RapprochementLigne(rapprochement_id=rapprochement.id, ligne_paiement_id=paiement.id))
        s.commit()

    reponse = client_connecte.post("/documents/1/relancer")
    assert reponse.status_code == 409


def test_suppression_document_sans_lignes_rapprochees(client_connecte, session, dossier_documents_temporaire):
    bien = _creer_bien(session)
    gestionnaire = _creer_gestionnaire(session)
    contenu = creer_pdf_bytes("Compte-rendu")

    client_connecte.post(
        "/documents",
        data={"gestionnaire_id": str(gestionnaire.id), "bien_id": str(bien.id), "periode": "2024-09-01"},
        files={"fichier": ("releve.pdf", contenu, "application/pdf")},
    )

    chemin_pdf = dossier_documents_temporaire
    fichiers_avant = list(chemin_pdf.rglob("*.pdf")) if chemin_pdf.exists() else []
    assert len(fichiers_avant) == 1

    reponse = client_connecte.post("/documents/1/supprimer", follow_redirects=False)
    assert reponse.status_code == 303
    assert client_connecte.get("/documents/1").status_code == 404

    fichiers_apres = list(chemin_pdf.rglob("*.pdf")) if chemin_pdf.exists() else []
    assert fichiers_apres == []


def test_suppression_document_inexistant(client_connecte):
    assert client_connecte.post("/documents/999/supprimer").status_code == 404
