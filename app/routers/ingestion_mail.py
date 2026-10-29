from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Bien, Gestionnaire, Utilisateur
from app.models.enums import StatutCandidatCourriel
from app.security import get_current_user
from app.services.formulaires import parser_date_optionnelle
from app.services.ingestion_mail import lister_candidats, marquer_traite, recuperer_piece_jointe
from app.services.mail import ErreurConnexionImap, boite_mail_configuree, nouveau_client_imap
from app.services.releves import enregistrer_releve
from app.templating import templates

router = APIRouter(prefix="/ingestion-mail", tags=["ingestion-mail"])


@router.get("", name="ingestion_mail_liste")
def ingestion_mail_liste(
    request: Request,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    if not boite_mail_configuree():
        return templates.TemplateResponse(
            request,
            "ingestion_mail/liste.html",
            {
                "utilisateur": utilisateur,
                "configure": False,
                "erreur": None,
                "candidats": [],
                "gestionnaires": [],
                "biens": [],
            },
        )

    gestionnaires = session.exec(select(Gestionnaire).order_by(Gestionnaire.nom)).all()
    biens = session.exec(select(Bien).order_by(Bien.libelle)).all()

    try:
        with nouveau_client_imap() as client:
            candidats = lister_candidats(client, session)
    except ErreurConnexionImap as erreur:
        return templates.TemplateResponse(
            request,
            "ingestion_mail/liste.html",
            {
                "utilisateur": utilisateur,
                "configure": True,
                "erreur": str(erreur),
                "candidats": [],
                "gestionnaires": gestionnaires,
                "biens": biens,
            },
        )

    return templates.TemplateResponse(
        request,
        "ingestion_mail/liste.html",
        {
            "utilisateur": utilisateur,
            "configure": True,
            "erreur": None,
            "candidats": candidats,
            "gestionnaires": gestionnaires,
            "biens": biens,
        },
    )


@router.post("/importer", name="ingestion_mail_importer")
def ingestion_mail_importer(
    request: Request,
    message_uid: str = Form(...),
    nom_piece_jointe: str = Form(...),
    gestionnaire_id: str = Form(...),
    bien_id: str = Form(...),
    periode: str = Form(...),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    try:
        gestionnaire_id_parse = int(gestionnaire_id)
        bien_id_parse = int(bien_id)
        periode_parsee = parser_date_optionnelle(periode)
        if periode_parsee is None:
            raise ValueError("la période est obligatoire")
    except ValueError as erreur:
        raise HTTPException(status_code=400, detail=f"Données invalides : {erreur}") from erreur

    gestionnaire = session.get(Gestionnaire, gestionnaire_id_parse)
    if gestionnaire is None:
        raise HTTPException(status_code=404, detail="Gestionnaire introuvable")
    bien = session.get(Bien, bien_id_parse)
    if bien is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")

    try:
        with nouveau_client_imap() as client:
            contenu = recuperer_piece_jointe(client, message_uid, nom_piece_jointe)
    except (ErreurConnexionImap, ValueError) as erreur:
        raise HTTPException(status_code=400, detail=str(erreur)) from erreur

    try:
        releve = enregistrer_releve(session, gestionnaire, bien, periode_parsee, nom_piece_jointe, contenu)
    except ValueError as erreur:
        raise HTTPException(status_code=400, detail=str(erreur)) from erreur

    marquer_traite(session, message_uid, nom_piece_jointe, StatutCandidatCourriel.IMPORTE, releve.id)

    return RedirectResponse(url=request.url_for("ingestion_mail_liste"), status_code=303)


@router.post("/ignorer", name="ingestion_mail_ignorer")
def ingestion_mail_ignorer(
    request: Request,
    message_uid: str = Form(...),
    nom_piece_jointe: str = Form(...),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    marquer_traite(session, message_uid, nom_piece_jointe, StatutCandidatCourriel.IGNORE)
    return RedirectResponse(url=request.url_for("ingestion_mail_liste"), status_code=303)
