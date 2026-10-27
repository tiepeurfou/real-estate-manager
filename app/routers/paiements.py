from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.database import get_session
from app.models import Bien, LignePaiement, UniteLocative, Utilisateur
from app.security import get_current_user
from app.services.periodes import derniers_mois
from app.templating import templates

router = APIRouter(prefix="/paiements", tags=["paiements"])


@router.get("", name="paiements_grille")
def paiements_grille(
    request: Request,
    nb_mois: int = 6,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    mois_liste = derniers_mois(date.today(), nb_mois)

    unites = session.exec(select(UniteLocative).order_by(UniteLocative.libelle)).all()
    biens_par_id = {b.id: b for b in session.exec(select(Bien)).all()}

    lignes = session.exec(select(LignePaiement)).all()
    ligne_par_unite_periode = {(ligne.unite_locative_id, ligne.periode): ligne for ligne in lignes}

    return templates.TemplateResponse(
        request,
        "paiements/grille.html",
        {
            "utilisateur": utilisateur,
            "unites": unites,
            "biens_par_id": biens_par_id,
            "mois_liste": mois_liste,
            "ligne_par_unite_periode": ligne_par_unite_periode,
            "nb_mois": nb_mois,
        },
    )
