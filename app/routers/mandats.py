from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.database import get_session
from app.models import MandatGestion, Utilisateur
from app.security import get_current_user
from app.services.formulaires import parser_date_optionnelle
from app.templating import templates

router = APIRouter(prefix="/mandats", tags=["mandats"])


@router.get("/{mandat_id}/terminer", name="mandat_terminer_formulaire")
def mandat_terminer_formulaire(
    request: Request,
    mandat_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    mandat = session.get(MandatGestion, mandat_id)
    if mandat is None:
        raise HTTPException(status_code=404, detail="Mandat introuvable")

    return templates.TemplateResponse(
        request, "mandats/terminer.html", {"utilisateur": utilisateur, "mandat": mandat, "erreur": None}
    )


@router.post("/{mandat_id}/terminer", name="mandat_terminer")
def mandat_terminer(
    request: Request,
    mandat_id: int,
    date_fin: str = Form(...),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    mandat = session.get(MandatGestion, mandat_id)
    if mandat is None:
        raise HTTPException(status_code=404, detail="Mandat introuvable")

    try:
        date_fin_parsee = parser_date_optionnelle(date_fin)
        if date_fin_parsee is None:
            raise ValueError("la date de fin est obligatoire")
        if date_fin_parsee < mandat.date_debut:
            raise ValueError("la date de fin ne peut pas précéder la date de début")
    except ValueError as erreur:
        return templates.TemplateResponse(
            request,
            "mandats/terminer.html",
            {"utilisateur": utilisateur, "mandat": mandat, "erreur": f"Données invalides : {erreur}"},
            status_code=400,
        )

    mandat.date_fin = date_fin_parsee
    session.add(mandat)
    session.commit()

    return RedirectResponse(
        url=request.url_for("gestionnaire_detail", gestionnaire_id=mandat.gestionnaire_id), status_code=303
    )


@router.post("/{mandat_id}/supprimer", name="mandat_supprimer")
def mandat_supprimer(
    request: Request,
    mandat_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    mandat = session.get(MandatGestion, mandat_id)
    if mandat is None:
        raise HTTPException(status_code=404, detail="Mandat introuvable")

    gestionnaire_id = mandat.gestionnaire_id
    session.delete(mandat)
    session.commit()

    return RedirectResponse(url=request.url_for("gestionnaire_detail", gestionnaire_id=gestionnaire_id), status_code=303)
