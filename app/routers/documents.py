from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlmodel import Session, select

from app.config import BASE_DIR
from app.database import get_session
from app.models import Bien, Gestionnaire, LigneDepense, LignePaiement, ReleveGestion, Utilisateur
from app.security import get_current_user
from app.services.formulaires import parser_date_optionnelle
from app.services.releves import (
    enregistrer_releve,
    releve_a_des_lignes_rapprochees,
    supprimer_lignes_du_releve,
    traiter_extraction,
)
from app.templating import templates

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", name="documents_liste")
def documents_liste(
    request: Request,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    releves = session.exec(select(ReleveGestion).order_by(ReleveGestion.date_reception.desc())).all()
    return templates.TemplateResponse(request, "documents/liste.html", {"utilisateur": utilisateur, "releves": releves})


@router.get("/nouveau", name="document_nouveau_formulaire")
def document_nouveau_formulaire(
    request: Request,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    gestionnaires = session.exec(select(Gestionnaire).order_by(Gestionnaire.nom)).all()
    biens = session.exec(select(Bien).order_by(Bien.libelle)).all()
    return templates.TemplateResponse(
        request,
        "documents/formulaire.html",
        {"utilisateur": utilisateur, "gestionnaires": gestionnaires, "biens": biens, "erreur": None},
    )


@router.post("", name="document_televerser")
async def document_televerser(
    request: Request,
    gestionnaire_id: str = Form(...),
    bien_id: str = Form(...),
    periode: str = Form(...),
    fichier: UploadFile = File(...),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    def _reponse_erreur(message: str):
        gestionnaires = session.exec(select(Gestionnaire).order_by(Gestionnaire.nom)).all()
        biens = session.exec(select(Bien).order_by(Bien.libelle)).all()
        return templates.TemplateResponse(
            request,
            "documents/formulaire.html",
            {
                "utilisateur": utilisateur,
                "gestionnaires": gestionnaires,
                "biens": biens,
                "erreur": f"Données invalides : {message}",
            },
            status_code=400,
        )

    try:
        gestionnaire_id_parse = int(gestionnaire_id)
        bien_id_parse = int(bien_id)
        periode_parsee = parser_date_optionnelle(periode)
        if periode_parsee is None:
            raise ValueError("la période est obligatoire")
    except ValueError as erreur:
        return _reponse_erreur(str(erreur))

    if not fichier.filename or not fichier.filename.lower().endswith(".pdf"):
        return _reponse_erreur("seuls les fichiers PDF sont acceptés")

    gestionnaire = session.get(Gestionnaire, gestionnaire_id_parse)
    if gestionnaire is None:
        raise HTTPException(status_code=404, detail="Gestionnaire introuvable")
    bien = session.get(Bien, bien_id_parse)
    if bien is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")

    contenu = await fichier.read()

    try:
        releve = enregistrer_releve(session, gestionnaire, bien, periode_parsee, fichier.filename, contenu)
    except ValueError as erreur:
        return _reponse_erreur(str(erreur))

    return RedirectResponse(url=request.url_for("document_detail", releve_id=releve.id), status_code=303)


@router.get("/{releve_id}", name="document_detail")
def document_detail(
    request: Request,
    releve_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    releve = session.get(ReleveGestion, releve_id)
    if releve is None:
        raise HTTPException(status_code=404, detail="Relevé introuvable")

    paiements = session.exec(select(LignePaiement).where(LignePaiement.releve_gestion_id == releve_id)).all()
    depenses = session.exec(select(LigneDepense).where(LigneDepense.releve_gestion_id == releve_id)).all()

    return templates.TemplateResponse(
        request,
        "documents/detail.html",
        {"utilisateur": utilisateur, "releve": releve, "paiements": paiements, "depenses": depenses},
    )


@router.get("/{releve_id}/fichier", name="document_fichier")
def document_fichier(
    releve_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    releve = session.get(ReleveGestion, releve_id)
    if releve is None:
        raise HTTPException(status_code=404, detail="Relevé introuvable")

    chemin = BASE_DIR / releve.chemin_fichier_pdf
    return FileResponse(chemin, media_type="application/pdf", filename=chemin.name)


@router.post("/{releve_id}/relancer", name="document_relancer")
def document_relancer(
    request: Request,
    releve_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    releve = session.get(ReleveGestion, releve_id)
    if releve is None:
        raise HTTPException(status_code=404, detail="Relevé introuvable")

    if releve_a_des_lignes_rapprochees(session, releve.id):
        raise HTTPException(
            status_code=409,
            detail="Supprimez d'abord le(s) rapprochement(s) utilisant les lignes de ce relevé avant de relancer l'extraction.",
        )

    supprimer_lignes_du_releve(session, releve.id)
    traiter_extraction(session, releve)

    return RedirectResponse(url=request.url_for("document_detail", releve_id=releve_id), status_code=303)


@router.post("/{releve_id}/supprimer", name="document_supprimer")
def document_supprimer(
    request: Request,
    releve_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    releve = session.get(ReleveGestion, releve_id)
    if releve is None:
        raise HTTPException(status_code=404, detail="Relevé introuvable")

    if releve_a_des_lignes_rapprochees(session, releve.id):
        raise HTTPException(
            status_code=409,
            detail="Supprimez d'abord le(s) rapprochement(s) utilisant les lignes de ce relevé.",
        )

    chemin_relatif = releve.chemin_fichier_pdf
    supprimer_lignes_du_releve(session, releve.id)
    session.delete(releve)
    session.commit()

    (BASE_DIR / chemin_relatif).unlink(missing_ok=True)

    return RedirectResponse(url=request.url_for("documents_liste"), status_code=303)
