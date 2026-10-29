from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.database import get_session
from app.models import Bien, Utilisateur
from app.security import get_current_user
from app.services.tableau_de_bord import (
    calculer,
    calculer_par_type_pour_annee,
    calculer_par_type_pour_mois,
    calculer_pour_annee,
    calculer_pour_mois,
    libelle_mois_fr,
)
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


@router.get("/tableau-de-bord/mois", name="tableau_de_bord_mensuel")
def tableau_de_bord_mensuel(
    request: Request,
    annee: Optional[int] = None,
    mois: Optional[int] = None,
    bien_id: Optional[int] = None,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    aujourdhui = date.today()
    if annee is None:
        annee = aujourdhui.year
    if mois is None:
        mois = aujourdhui.month
    if not (1 <= mois <= 12):
        raise HTTPException(status_code=400, detail="Mois invalide")
    try:
        periode = date(annee, mois, 1)
    except ValueError as erreur:
        raise HTTPException(status_code=400, detail=f"Date invalide : {erreur}") from erreur

    if bien_id is not None and session.get(Bien, bien_id) is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")

    donnees = calculer_pour_mois(session, periode, bien_id=bien_id)
    donnees_par_type = calculer_par_type_pour_mois(session, periode) if bien_id is None else []
    biens = session.exec(select(Bien).order_by(Bien.libelle)).all()

    mois_precedent, annee_precedente = (12, periode.year - 1) if periode.month == 1 else (periode.month - 1, periode.year)
    mois_suivant, annee_suivante = (1, periode.year + 1) if periode.month == 12 else (periode.month + 1, periode.year)

    return templates.TemplateResponse(
        request,
        "tableau_de_bord_mensuel.html",
        {
            "utilisateur": utilisateur,
            "donnees": donnees,
            "donnees_par_type": donnees_par_type,
            "biens": biens,
            "bien_id_filtre": bien_id,
            "libelle_periode": libelle_mois_fr(periode),
            "annee_precedente": annee_precedente,
            "mois_precedent": mois_precedent,
            "annee_suivante": annee_suivante,
            "mois_suivant": mois_suivant,
            "est_mois_courant": periode.year == aujourdhui.year and periode.month == aujourdhui.month,
        },
    )


@router.get("/tableau-de-bord/annee", name="tableau_de_bord_annuel")
def tableau_de_bord_annuel(
    request: Request,
    annee: Optional[int] = None,
    bien_id: Optional[int] = None,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    aujourdhui = date.today()
    if annee is None:
        annee = aujourdhui.year
    try:
        date(annee, 1, 1)
    except ValueError as erreur:
        raise HTTPException(status_code=400, detail=f"Année invalide : {erreur}") from erreur

    if bien_id is not None and session.get(Bien, bien_id) is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")

    donnees = calculer_pour_annee(session, annee, bien_id=bien_id)
    donnees_par_type = calculer_par_type_pour_annee(session, annee) if bien_id is None else []
    biens = session.exec(select(Bien).order_by(Bien.libelle)).all()

    return templates.TemplateResponse(
        request,
        "tableau_de_bord_annuel.html",
        {
            "utilisateur": utilisateur,
            "donnees": donnees,
            "donnees_par_type": donnees_par_type,
            "biens": biens,
            "bien_id_filtre": bien_id,
            "annee_precedente": annee - 1,
            "annee_suivante": annee + 1,
            "est_annee_courante": annee == aujourdhui.year,
        },
    )
