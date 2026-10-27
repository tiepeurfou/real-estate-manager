from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Occupation, OccupationLocataire, UniteLocative, Utilisateur
from app.models.enums import StatutOccupation
from app.security import get_current_user
from app.services.formulaires import parser_date_optionnelle
from app.templating import templates

router = APIRouter(prefix="/occupations", tags=["occupations"])


@router.get("/{occupation_id}/cloturer", name="occupation_cloturer_formulaire")
def occupation_cloturer_formulaire(
    request: Request,
    occupation_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    occupation = session.get(Occupation, occupation_id)
    if occupation is None:
        raise HTTPException(status_code=404, detail="Occupation introuvable")

    return templates.TemplateResponse(
        request, "occupations/cloturer.html", {"utilisateur": utilisateur, "occupation": occupation, "erreur": None}
    )


@router.post("/{occupation_id}/cloturer", name="occupation_cloturer")
def occupation_cloturer(
    request: Request,
    occupation_id: int,
    date_sortie: str = Form(...),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    occupation = session.get(Occupation, occupation_id)
    if occupation is None:
        raise HTTPException(status_code=404, detail="Occupation introuvable")

    if occupation.statut == StatutOccupation.TERMINEE:
        raise HTTPException(status_code=409, detail="Cette occupation est déjà clôturée.")

    try:
        date_sortie_parsee = parser_date_optionnelle(date_sortie)
        if date_sortie_parsee is None:
            raise ValueError("la date de sortie est obligatoire")
        if date_sortie_parsee < occupation.date_entree:
            raise ValueError("la date de sortie ne peut pas précéder la date d'entrée")
    except ValueError as erreur:
        return templates.TemplateResponse(
            request,
            "occupations/cloturer.html",
            {"utilisateur": utilisateur, "occupation": occupation, "erreur": f"Données invalides : {erreur}"},
            status_code=400,
        )

    occupation.date_sortie = date_sortie_parsee
    occupation.statut = StatutOccupation.TERMINEE
    session.add(occupation)
    session.commit()

    return RedirectResponse(
        url=request.url_for("bien_detail", bien_id=_bien_id_de_l_unite(session, occupation.unite_locative_id)),
        status_code=303,
    )


@router.post("/{occupation_id}/supprimer", name="occupation_supprimer")
def occupation_supprimer(
    request: Request,
    occupation_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    occupation = session.get(Occupation, occupation_id)
    if occupation is None:
        raise HTTPException(status_code=404, detail="Occupation introuvable")

    bien_id = _bien_id_de_l_unite(session, occupation.unite_locative_id)

    for lien in session.exec(
        select(OccupationLocataire).where(OccupationLocataire.occupation_id == occupation.id)
    ).all():
        session.delete(lien)
    session.delete(occupation)
    session.commit()

    return RedirectResponse(url=request.url_for("bien_detail", bien_id=bien_id), status_code=303)


def _bien_id_de_l_unite(session: Session, unite_locative_id: int) -> int:
    unite = session.get(UniteLocative, unite_locative_id)
    return unite.bien_id
