from datetime import date

import pytest

import app.services.releves as releves_module
from app.config import BASE_DIR
from app.models import (
    Bien,
    CompteBancaire,
    Gestionnaire,
    LigneDepense,
    LignePaiement,
    Rapprochement,
    RapprochementLigne,
    UniteLocative,
    VirementRecu,
)
from app.models.enums import Banque, StatutExtraction, StatutPaiement, TypeBien
from app.services.extraction.base import LigneDepenseExtraite, LignePaiementExtraite, ResultatExtraction
from app.services.releves import enregistrer_releve, releve_a_des_lignes_rapprochees
from tests.aide_pdf import creer_pdf_bytes


def _creer_bien_et_gestionnaire(session, nom_gestionnaire="ArthurImmo"):
    bien = Bien(
        type=TypeBien.APPARTEMENT_ISOLE,
        libelle="Villiers-sur-Marne",
        adresse_rue="rue",
        adresse_code_postal="94350",
        adresse_ville="Villiers-sur-Marne",
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)

    unite = UniteLocative(bien_id=bien.id, libelle="Villiers-sur-Marne")
    session.add(unite)
    session.commit()
    session.refresh(unite)

    gestionnaire = Gestionnaire(nom=nom_gestionnaire)
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)

    return bien, unite, gestionnaire


class AdaptateurFactice:
    def __init__(self, resultat: ResultatExtraction):
        self._resultat = resultat

    def extraire(self, texte: str) -> ResultatExtraction:
        return self._resultat


def test_enregistrer_releve_stocke_le_fichier_et_cree_le_releve(session, dossier_documents_temporaire):
    bien, unite, gestionnaire = _creer_bien_et_gestionnaire(session)
    contenu = creer_pdf_bytes("Compte-rendu septembre")

    releve = enregistrer_releve(session, gestionnaire, bien, date(2024, 9, 1), "releve.pdf", contenu)

    assert (BASE_DIR / releve.chemin_fichier_pdf).exists()
    assert releve.hash_fichier == releves_module.hash_fichier(contenu)


def test_enregistrer_releve_refuse_un_doublon(session, dossier_documents_temporaire):
    bien, unite, gestionnaire = _creer_bien_et_gestionnaire(session)
    contenu = creer_pdf_bytes("Compte-rendu septembre")

    enregistrer_releve(session, gestionnaire, bien, date(2024, 9, 1), "releve.pdf", contenu)

    with pytest.raises(ValueError):
        enregistrer_releve(session, gestionnaire, bien, date(2024, 9, 1), "releve-copie.pdf", contenu)


def test_traiter_extraction_adaptateur_non_calibre_marque_erreur(session, dossier_documents_temporaire):
    bien, unite, gestionnaire = _creer_bien_et_gestionnaire(session, nom_gestionnaire="ArthurImmo")
    contenu = creer_pdf_bytes("Compte-rendu")

    releve = enregistrer_releve(session, gestionnaire, bien, date(2024, 9, 1), "releve.pdf", contenu)

    assert releve.statut_extraction == StatutExtraction.ERREUR_EXTRACTION
    assert "pas encore été calibré" in releve.erreur_extraction_message


def test_traiter_extraction_succes_cree_les_lignes(session, dossier_documents_temporaire, monkeypatch):
    bien, unite, gestionnaire = _creer_bien_et_gestionnaire(session, nom_gestionnaire="Locagestion")

    resultat = ResultatExtraction(
        paiements=[
            LignePaiementExtraite(
                unite_libelle=unite.libelle,
                periode=date(2024, 9, 1),
                montant_attendu=500,
                montant_percu=500,
                statut=StatutPaiement.PAYE,
            )
        ],
        depenses=[
            LigneDepenseExtraite(
                categorie="Travaux", libelle="Plomberie", montant=80, date=date(2024, 9, 15), unite_libelle=unite.libelle
            ),
            LigneDepenseExtraite(
                categorie="Honoraires de gestion", libelle="Honoraires", montant=50, date=date(2024, 9, 30), unite_libelle=None
            ),
        ],
    )
    monkeypatch.setattr(releves_module, "obtenir_adaptateur", lambda nom: AdaptateurFactice(resultat))

    contenu = creer_pdf_bytes("Compte-rendu")
    releve = enregistrer_releve(session, gestionnaire, bien, date(2024, 9, 1), "releve.pdf", contenu)

    assert releve.statut_extraction == StatutExtraction.TRAITE_OK
    assert releve.erreur_extraction_message is None

    from sqlmodel import select

    paiements = session.exec(select(LignePaiement).where(LignePaiement.releve_gestion_id == releve.id)).all()
    depenses = session.exec(select(LigneDepense).where(LigneDepense.releve_gestion_id == releve.id)).all()

    assert len(paiements) == 1
    assert paiements[0].unite_locative_id == unite.id
    assert len(depenses) == 2
    depense_avec_unite = next(d for d in depenses if d.categorie == "Travaux")
    depense_sans_unite = next(d for d in depenses if d.categorie == "Honoraires de gestion")
    assert depense_avec_unite.unite_locative_id == unite.id
    assert depense_sans_unite.unite_locative_id is None
    assert depense_sans_unite.bien_id == bien.id


def test_traiter_extraction_unite_inconnue_est_ignoree(session, dossier_documents_temporaire, monkeypatch):
    bien, unite, gestionnaire = _creer_bien_et_gestionnaire(session, nom_gestionnaire="Locagestion")

    resultat = ResultatExtraction(
        paiements=[
            LignePaiementExtraite(
                unite_libelle="Unité qui n'existe pas",
                periode=date(2024, 9, 1),
                montant_attendu=500,
                montant_percu=500,
                statut=StatutPaiement.PAYE,
            )
        ]
    )
    monkeypatch.setattr(releves_module, "obtenir_adaptateur", lambda nom: AdaptateurFactice(resultat))

    contenu = creer_pdf_bytes("Compte-rendu")
    releve = enregistrer_releve(session, gestionnaire, bien, date(2024, 9, 1), "releve.pdf", contenu)

    from sqlmodel import select

    paiements = session.exec(select(LignePaiement).where(LignePaiement.releve_gestion_id == releve.id)).all()
    assert paiements == []
    assert releve.statut_extraction == StatutExtraction.TRAITE_OK


def test_releve_a_des_lignes_rapprochees(session, dossier_documents_temporaire, monkeypatch):
    bien, unite, gestionnaire = _creer_bien_et_gestionnaire(session, nom_gestionnaire="Locagestion")

    resultat = ResultatExtraction(
        paiements=[
            LignePaiementExtraite(
                unite_libelle=unite.libelle,
                periode=date(2024, 9, 1),
                montant_attendu=500,
                montant_percu=500,
                statut=StatutPaiement.PAYE,
            )
        ]
    )
    monkeypatch.setattr(releves_module, "obtenir_adaptateur", lambda nom: AdaptateurFactice(resultat))

    contenu = creer_pdf_bytes("Compte-rendu")
    releve = enregistrer_releve(session, gestionnaire, bien, date(2024, 9, 1), "releve.pdf", contenu)

    assert releve_a_des_lignes_rapprochees(session, releve.id) is False

    from sqlmodel import select

    paiement = session.exec(select(LignePaiement).where(LignePaiement.releve_gestion_id == releve.id)).first()

    compte = CompteBancaire(banque=Banque.SG, libelle="Compte SG")
    session.add(compte)
    session.commit()
    session.refresh(compte)

    virement = VirementRecu(gestionnaire_id=gestionnaire.id, compte_bancaire_id=compte.id, montant=500, date_reception=date(2024, 10, 5))
    session.add(virement)
    session.commit()
    session.refresh(virement)

    rapprochement = Rapprochement(virement_recu_id=virement.id, ecart=0)
    session.add(rapprochement)
    session.commit()
    session.refresh(rapprochement)

    session.add(RapprochementLigne(rapprochement_id=rapprochement.id, ligne_paiement_id=paiement.id))
    session.commit()

    assert releve_a_des_lignes_rapprochees(session, releve.id) is True
