import hashlib
from datetime import date, datetime, timezone
from pathlib import Path

from sqlmodel import Session, select

from app.config import BASE_DIR
from app.models import Bien, Gestionnaire, LigneDepense, LignePaiement, RapprochementLigne, ReleveGestion, UniteLocative
from app.models.enums import StatutExtraction
from app.services.extraction import ExtractionNonCalibreeError, obtenir_adaptateur
from app.services.pdf import extraire_texte_pdf

DOSSIER_DOCUMENTS = BASE_DIR / "data" / "documents"


def _slug(texte: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in texte).strip("-")


def hash_fichier(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def _chemin_stockage(gestionnaire_nom: str, periode: date, nom_fichier: str) -> Path:
    dossier = DOSSIER_DOCUMENTS / _slug(gestionnaire_nom) / periode.strftime("%Y-%m")
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier / nom_fichier


def enregistrer_releve(
    session: Session,
    gestionnaire: Gestionnaire,
    bien: Bien,
    periode: date,
    nom_fichier: str,
    contenu: bytes,
) -> ReleveGestion:
    hash_ = hash_fichier(contenu)
    existant = session.exec(select(ReleveGestion).where(ReleveGestion.hash_fichier == hash_)).first()
    if existant is not None:
        raise ValueError("ce document a déjà été importé")

    chemin = _chemin_stockage(gestionnaire.nom, periode, nom_fichier)
    chemin.write_bytes(contenu)

    releve = ReleveGestion(
        gestionnaire_id=gestionnaire.id,
        bien_id=bien.id,
        periode=periode,
        date_reception=datetime.now(timezone.utc),
        chemin_fichier_pdf=str(chemin.relative_to(BASE_DIR)),
        hash_fichier=hash_,
        statut_extraction=StatutExtraction.NON_TRAITE,
    )
    session.add(releve)
    session.commit()
    session.refresh(releve)

    traiter_extraction(session, releve)
    return releve


def traiter_extraction(session: Session, releve: ReleveGestion) -> None:
    gestionnaire = session.get(Gestionnaire, releve.gestionnaire_id)

    try:
        adaptateur = obtenir_adaptateur(gestionnaire.nom)
        texte = extraire_texte_pdf(BASE_DIR / releve.chemin_fichier_pdf)
        resultat = adaptateur.extraire(texte)
    except ExtractionNonCalibreeError as erreur:
        releve.statut_extraction = StatutExtraction.ERREUR_EXTRACTION
        releve.erreur_extraction_message = str(erreur)
        session.add(releve)
        session.commit()
        return
    except Exception as erreur:  # extraction PDF/texte imprévue : on isole l'échec sur ce relevé
        releve.statut_extraction = StatutExtraction.ERREUR_EXTRACTION
        releve.erreur_extraction_message = f"Erreur inattendue lors de l'extraction : {erreur}"
        session.add(releve)
        session.commit()
        return

    unites_par_libelle = {
        u.libelle: u
        for u in session.exec(select(UniteLocative).where(UniteLocative.bien_id == releve.bien_id)).all()
    }

    for p in resultat.paiements:
        unite = unites_par_libelle.get(p.unite_libelle)
        if unite is None:
            continue
        session.add(
            LignePaiement(
                releve_gestion_id=releve.id,
                unite_locative_id=unite.id,
                periode=p.periode,
                montant_attendu=p.montant_attendu,
                montant_percu=p.montant_percu,
                statut=p.statut,
            )
        )

    for d in resultat.depenses:
        unite = unites_par_libelle.get(d.unite_libelle) if d.unite_libelle else None
        session.add(
            LigneDepense(
                releve_gestion_id=releve.id,
                unite_locative_id=unite.id if unite else None,
                bien_id=releve.bien_id if unite is None else None,
                categorie=d.categorie,
                libelle=d.libelle,
                montant=d.montant,
                date=d.date,
            )
        )

    releve.statut_extraction = StatutExtraction.TRAITE_OK
    releve.erreur_extraction_message = None
    session.add(releve)
    session.commit()


def releve_a_des_lignes_rapprochees(session: Session, releve_id: int) -> bool:
    paiement_ids = session.exec(select(LignePaiement.id).where(LignePaiement.releve_gestion_id == releve_id)).all()
    depense_ids = session.exec(select(LigneDepense.id).where(LigneDepense.releve_gestion_id == releve_id)).all()

    if paiement_ids:
        if (
            session.exec(select(RapprochementLigne).where(RapprochementLigne.ligne_paiement_id.in_(paiement_ids))).first()
            is not None
        ):
            return True
    if depense_ids:
        if (
            session.exec(select(RapprochementLigne).where(RapprochementLigne.ligne_depense_id.in_(depense_ids))).first()
            is not None
        ):
            return True
    return False


def supprimer_lignes_du_releve(session: Session, releve_id: int) -> None:
    for ligne in session.exec(select(LignePaiement).where(LignePaiement.releve_gestion_id == releve_id)).all():
        session.delete(ligne)
    for ligne in session.exec(select(LigneDepense).where(LigneDepense.releve_gestion_id == releve_id)).all():
        session.delete(ligne)
    session.commit()
