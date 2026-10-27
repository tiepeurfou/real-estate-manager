from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.database import get_session
from app.models import Bien, LigneDepense, UniteLocative, Utilisateur
from app.security import get_current_user
from app.templating import templates

router = APIRouter(prefix="/depenses", tags=["depenses"])


@router.get("", name="depenses_liste")
def depenses_liste(
    request: Request,
    bien_id: str = "",
    categorie: str = "",
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    try:
        bien_id_int = int(bien_id) if bien_id else None
    except ValueError:
        bien_id_int = None

    requete = select(LigneDepense)
    if bien_id_int is not None:
        requete = requete.where(LigneDepense.bien_id == bien_id_int)
    if categorie:
        requete = requete.where(LigneDepense.categorie == categorie)

    lignes = session.exec(requete.order_by(LigneDepense.date.desc())).all()

    totaux_par_categorie: dict[str, float] = {}
    for ligne in lignes:
        totaux_par_categorie[ligne.categorie] = totaux_par_categorie.get(ligne.categorie, 0) + ligne.montant

    biens = session.exec(select(Bien).order_by(Bien.libelle)).all()
    unites_par_id = {u.id: u for u in session.exec(select(UniteLocative)).all()}
    biens_par_id = {b.id: b for b in biens}

    return templates.TemplateResponse(
        request,
        "depenses/liste.html",
        {
            "utilisateur": utilisateur,
            "lignes": lignes,
            "totaux_par_categorie": totaux_par_categorie,
            "biens": biens,
            "unites_par_id": unites_par_id,
            "biens_par_id": biens_par_id,
            "bien_id_filtre": bien_id,
            "categorie_filtre": categorie,
        },
    )
