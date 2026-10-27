from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from app.database import get_session
from app.models import Utilisateur
from app.security import get_current_user
from app.services.tableau_de_bord import calculer
from app.templating import templates

router = APIRouter()


@router.get("/", name="accueil")
def accueil(
    request: Request,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    donnees = calculer(session)
    return templates.TemplateResponse(
        request, "tableau_de_bord.html", {"utilisateur": utilisateur, "donnees": donnees}
    )
