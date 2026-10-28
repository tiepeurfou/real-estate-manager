from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Bien, CompteBancaire, MandatGestion, UniteLocative, Utilisateur
from app.models.enums import RoleMandat
from app.security import get_current_user
from app.services.formulaires import parser_date_optionnelle, parser_int_optionnel
from app.templating import templates

router = APIRouter(prefix="/mandats", tags=["mandats"])


def _contexte_formulaire_modification(session: Session) -> dict:
    return {
        "biens_par_id": {b.id: b for b in session.exec(select(Bien)).all()},
        "unites": session.exec(select(UniteLocative)).all(),
        "comptes": session.exec(select(CompteBancaire).order_by(CompteBancaire.libelle)).all(),
        "roles": list(RoleMandat),
    }


@router.get("/{mandat_id}/modifier", name="mandat_modifier_formulaire")
def mandat_modifier_formulaire(
    request: Request,
    mandat_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    mandat = session.get(MandatGestion, mandat_id)
    if mandat is None:
        raise HTTPException(status_code=404, detail="Mandat introuvable")

    return templates.TemplateResponse(
        request,
        "mandats/modifier.html",
        {"utilisateur": utilisateur, "mandat": mandat, "erreur": None, **_contexte_formulaire_modification(session)},
    )


@router.post("/{mandat_id}/modifier", name="mandat_modifier")
def mandat_modifier(
    request: Request,
    mandat_id: int,
    unite_locative_id: str = Form(...),
    role: str = Form(...),
    date_debut: str = Form(...),
    date_fin: str = Form(""),
    compte_bancaire_id: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    mandat = session.get(MandatGestion, mandat_id)
    if mandat is None:
        raise HTTPException(status_code=404, detail="Mandat introuvable")

    def _reponse_erreur(message: str):
        return templates.TemplateResponse(
            request,
            "mandats/modifier.html",
            {
                "utilisateur": utilisateur,
                "mandat": mandat,
                "erreur": f"Données invalides : {message}",
                **_contexte_formulaire_modification(session),
            },
            status_code=400,
        )

    try:
        unite_id_parse = int(unite_locative_id)
        role_enum = RoleMandat(role)
        date_debut_parsee = parser_date_optionnelle(date_debut)
        if date_debut_parsee is None:
            raise ValueError("la date de début est obligatoire")
        date_fin_parsee = parser_date_optionnelle(date_fin)
        if date_fin_parsee is not None and date_fin_parsee < date_debut_parsee:
            raise ValueError("la date de fin ne peut pas précéder la date de début")
        compte_bancaire_id_parse = parser_int_optionnel(compte_bancaire_id)
    except ValueError as erreur:
        return _reponse_erreur(str(erreur))

    unite = session.get(UniteLocative, unite_id_parse)
    if unite is None:
        raise HTTPException(status_code=404, detail="Unité locative introuvable")

    mandat.unite_locative_id = unite_id_parse
    mandat.role = role_enum
    mandat.date_debut = date_debut_parsee
    mandat.date_fin = date_fin_parsee
    # La mise en location ne génère pas de versement : pas de compte dessus.
    mandat.compte_bancaire_id = compte_bancaire_id_parse if role_enum == RoleMandat.GESTION else None
    session.add(mandat)
    session.commit()

    return RedirectResponse(
        url=request.url_for("gestionnaire_detail", gestionnaire_id=mandat.gestionnaire_id), status_code=303
    )


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
