from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    Bien,
    CompteBancaire,
    Gestionnaire,
    MandatGestion,
    ReleveGestion,
    UniteLocative,
    Utilisateur,
    VirementRecu,
)
from app.models.enums import RoleMandat
from app.security import get_current_user
from app.services.formulaires import parser_date_optionnelle, parser_int_optionnel
from app.templating import templates

router = APIRouter(prefix="/gestionnaires", tags=["gestionnaires"])


def _gestionnaire_a_des_donnees_liees(session: Session, gestionnaire: Gestionnaire) -> bool:
    if session.exec(select(MandatGestion).where(MandatGestion.gestionnaire_id == gestionnaire.id)).first() is not None:
        return True
    if session.exec(select(ReleveGestion).where(ReleveGestion.gestionnaire_id == gestionnaire.id)).first() is not None:
        return True
    if session.exec(select(VirementRecu).where(VirementRecu.gestionnaire_id == gestionnaire.id)).first() is not None:
        return True
    return False


@router.get("", name="gestionnaires_liste")
def gestionnaires_liste(
    request: Request,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    gestionnaires = session.exec(select(Gestionnaire).order_by(Gestionnaire.nom)).all()
    return templates.TemplateResponse(
        request, "gestionnaires/liste.html", {"utilisateur": utilisateur, "gestionnaires": gestionnaires}
    )


@router.get("/nouveau", name="gestionnaire_nouveau_formulaire")
def gestionnaire_nouveau_formulaire(
    request: Request,
    utilisateur: Utilisateur = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request,
        "gestionnaires/formulaire.html",
        {"utilisateur": utilisateur, "gestionnaire": None, "erreur": None},
    )


@router.post("", name="gestionnaire_creer")
def gestionnaire_creer(
    request: Request,
    nom: str = Form(...),
    contact_email: str = Form(""),
    contact_tel: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    gestionnaire = Gestionnaire(
        nom=nom,
        contact_email=contact_email or None,
        contact_tel=contact_tel or None,
    )
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)

    return RedirectResponse(url=request.url_for("gestionnaire_detail", gestionnaire_id=gestionnaire.id), status_code=303)


@router.get("/{gestionnaire_id}", name="gestionnaire_detail")
def gestionnaire_detail(
    request: Request,
    gestionnaire_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    gestionnaire = session.get(Gestionnaire, gestionnaire_id)
    if gestionnaire is None:
        raise HTTPException(status_code=404, detail="Gestionnaire introuvable")

    mandats = session.exec(
        select(MandatGestion).where(MandatGestion.gestionnaire_id == gestionnaire_id).order_by(MandatGestion.date_debut.desc())
    ).all()
    unites_par_id = {u.id: u for u in session.exec(select(UniteLocative)).all()}
    biens_par_id = {b.id: b for b in session.exec(select(Bien)).all()}
    comptes_par_id = {c.id: c for c in session.exec(select(CompteBancaire)).all()}

    return templates.TemplateResponse(
        request,
        "gestionnaires/detail.html",
        {
            "utilisateur": utilisateur,
            "gestionnaire": gestionnaire,
            "mandats": mandats,
            "unites_par_id": unites_par_id,
            "biens_par_id": biens_par_id,
            "comptes_par_id": comptes_par_id,
        },
    )


@router.get("/{gestionnaire_id}/modifier", name="gestionnaire_modifier_formulaire")
def gestionnaire_modifier_formulaire(
    request: Request,
    gestionnaire_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    gestionnaire = session.get(Gestionnaire, gestionnaire_id)
    if gestionnaire is None:
        raise HTTPException(status_code=404, detail="Gestionnaire introuvable")
    return templates.TemplateResponse(
        request,
        "gestionnaires/formulaire.html",
        {"utilisateur": utilisateur, "gestionnaire": gestionnaire, "erreur": None},
    )


@router.post("/{gestionnaire_id}/modifier", name="gestionnaire_modifier")
def gestionnaire_modifier(
    request: Request,
    gestionnaire_id: int,
    nom: str = Form(...),
    contact_email: str = Form(""),
    contact_tel: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    gestionnaire = session.get(Gestionnaire, gestionnaire_id)
    if gestionnaire is None:
        raise HTTPException(status_code=404, detail="Gestionnaire introuvable")

    gestionnaire.nom = nom
    gestionnaire.contact_email = contact_email or None
    gestionnaire.contact_tel = contact_tel or None

    session.add(gestionnaire)
    session.commit()

    return RedirectResponse(url=request.url_for("gestionnaire_detail", gestionnaire_id=gestionnaire.id), status_code=303)


@router.post("/{gestionnaire_id}/supprimer", name="gestionnaire_supprimer")
def gestionnaire_supprimer(
    request: Request,
    gestionnaire_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    gestionnaire = session.get(Gestionnaire, gestionnaire_id)
    if gestionnaire is None:
        raise HTTPException(status_code=404, detail="Gestionnaire introuvable")

    if _gestionnaire_a_des_donnees_liees(session, gestionnaire):
        raise HTTPException(
            status_code=409,
            detail="Impossible de supprimer ce gestionnaire : des mandats, relevés ou virements y sont rattachés.",
        )

    session.delete(gestionnaire)
    session.commit()

    return RedirectResponse(url=request.url_for("gestionnaires_liste"), status_code=303)


@router.get("/{gestionnaire_id}/mandats/nouveau", name="mandat_nouveau_formulaire")
def mandat_nouveau_formulaire(
    request: Request,
    gestionnaire_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    gestionnaire = session.get(Gestionnaire, gestionnaire_id)
    if gestionnaire is None:
        raise HTTPException(status_code=404, detail="Gestionnaire introuvable")

    biens_par_id = {b.id: b for b in session.exec(select(Bien)).all()}
    unites = session.exec(select(UniteLocative)).all()
    comptes = session.exec(select(CompteBancaire).order_by(CompteBancaire.libelle)).all()

    return templates.TemplateResponse(
        request,
        "gestionnaires/mandat_formulaire.html",
        {
            "utilisateur": utilisateur,
            "gestionnaire": gestionnaire,
            "unites": unites,
            "biens_par_id": biens_par_id,
            "comptes": comptes,
            "roles": list(RoleMandat),
            "erreur": None,
        },
    )


@router.post("/{gestionnaire_id}/mandats", name="mandat_creer")
def mandat_creer(
    request: Request,
    gestionnaire_id: int,
    unite_locative_id: str = Form(...),
    role: str = Form(...),
    date_debut: str = Form(...),
    compte_bancaire_id: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    gestionnaire = session.get(Gestionnaire, gestionnaire_id)
    if gestionnaire is None:
        raise HTTPException(status_code=404, detail="Gestionnaire introuvable")

    def _reponse_erreur(message: str):
        biens_par_id = {b.id: b for b in session.exec(select(Bien)).all()}
        unites = session.exec(select(UniteLocative)).all()
        comptes = session.exec(select(CompteBancaire).order_by(CompteBancaire.libelle)).all()
        return templates.TemplateResponse(
            request,
            "gestionnaires/mandat_formulaire.html",
            {
                "utilisateur": utilisateur,
                "gestionnaire": gestionnaire,
                "unites": unites,
                "biens_par_id": biens_par_id,
                "comptes": comptes,
                "roles": list(RoleMandat),
                "erreur": f"Données invalides : {message}",
            },
            status_code=400,
        )

    try:
        unite_id_parse = int(unite_locative_id)
        role_enum = RoleMandat(role)
        date_debut_parsee = parser_date_optionnelle(date_debut)
        if date_debut_parsee is None:
            raise ValueError("la date de début est obligatoire")
        compte_bancaire_id_parse = parser_int_optionnel(compte_bancaire_id)
    except ValueError as erreur:
        return _reponse_erreur(str(erreur))

    unite = session.get(UniteLocative, unite_id_parse)
    if unite is None:
        raise HTTPException(status_code=404, detail="Unité locative introuvable")

    mandat = MandatGestion(
        unite_locative_id=unite_id_parse,
        gestionnaire_id=gestionnaire_id,
        role=role_enum,
        date_debut=date_debut_parsee,
        compte_bancaire_id=compte_bancaire_id_parse,
    )
    session.add(mandat)
    session.commit()

    return RedirectResponse(url=request.url_for("gestionnaire_detail", gestionnaire_id=gestionnaire_id), status_code=303)
