from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Bien, LignePaiement, Locataire, Occupation, OccupationLocataire, UniteLocative, Utilisateur
from app.models.enums import StatutOccupation, TypeGarantie
from app.security import get_current_user
from app.services.formulaires import parser_date_optionnelle
from app.templating import templates

router = APIRouter(prefix="/locataires", tags=["locataires"])


def _occupation_active_par_locataire(session: Session) -> dict[int, dict]:
    occupations_actives = session.exec(select(Occupation).where(Occupation.statut == StatutOccupation.ACTIVE)).all()
    unites_par_id = {u.id: u for u in session.exec(select(UniteLocative)).all()}
    biens_par_id = {b.id: b for b in session.exec(select(Bien)).all()}

    resultat: dict[int, dict] = {}
    for occupation in occupations_actives:
        unite = unites_par_id.get(occupation.unite_locative_id)
        bien = biens_par_id.get(unite.bien_id) if unite else None
        liens = session.exec(
            select(OccupationLocataire).where(OccupationLocataire.occupation_id == occupation.id)
        ).all()
        for lien in liens:
            resultat[lien.locataire_id] = {"unite": unite, "bien": bien}
    return resultat


def _locataire_a_des_donnees_liees(session: Session, locataire: Locataire) -> bool:
    if (
        session.exec(select(OccupationLocataire).where(OccupationLocataire.locataire_id == locataire.id)).first()
        is not None
    ):
        return True
    if session.exec(select(LignePaiement).where(LignePaiement.locataire_id == locataire.id)).first() is not None:
        return True
    return False


@router.get("", name="locataires_liste")
def locataires_liste(
    request: Request,
    statut: str = "tous",
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    locataires = session.exec(select(Locataire).order_by(Locataire.nom, Locataire.prenom)).all()
    occupation_active_par_locataire = _occupation_active_par_locataire(session)

    if statut == "actif":
        locataires = [loc for loc in locataires if loc.id in occupation_active_par_locataire]
    elif statut == "historique":
        locataires = [loc for loc in locataires if loc.id not in occupation_active_par_locataire]

    return templates.TemplateResponse(
        request,
        "locataires/liste.html",
        {
            "utilisateur": utilisateur,
            "locataires": locataires,
            "statut": statut,
            "occupation_active_par_locataire": occupation_active_par_locataire,
        },
    )


@router.get("/nouveau", name="locataire_nouveau_formulaire")
def locataire_nouveau_formulaire(request: Request, utilisateur: Utilisateur = Depends(get_current_user)):
    return templates.TemplateResponse(
        request,
        "locataires/formulaire.html",
        {"utilisateur": utilisateur, "locataire": None, "types_garantie": list(TypeGarantie), "erreur": None},
    )


@router.post("", name="locataire_creer")
def locataire_creer(
    request: Request,
    nom: str = Form(...),
    prenom: str = Form(...),
    date_naissance: str = Form(""),
    email: str = Form(""),
    telephone: str = Form(""),
    type_garantie: str = Form(TypeGarantie.AUCUNE.value),
    garant_nom: str = Form(""),
    garant_contact: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    try:
        type_garantie_enum = TypeGarantie(type_garantie)
        date_naissance_parsee = parser_date_optionnelle(date_naissance)
    except ValueError as erreur:
        return templates.TemplateResponse(
            request,
            "locataires/formulaire.html",
            {
                "utilisateur": utilisateur,
                "locataire": None,
                "types_garantie": list(TypeGarantie),
                "erreur": f"Données invalides : {erreur}",
            },
            status_code=400,
        )

    locataire = Locataire(
        nom=nom,
        prenom=prenom,
        date_naissance=date_naissance_parsee,
        email=email or None,
        telephone=telephone or None,
        type_garantie=type_garantie_enum,
        garant_nom=garant_nom or None,
        garant_contact=garant_contact or None,
    )
    session.add(locataire)
    session.commit()
    session.refresh(locataire)

    return RedirectResponse(url=request.url_for("locataire_detail", locataire_id=locataire.id), status_code=303)


@router.get("/{locataire_id}", name="locataire_detail")
def locataire_detail(
    request: Request,
    locataire_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    locataire = session.get(Locataire, locataire_id)
    if locataire is None:
        raise HTTPException(status_code=404, detail="Locataire introuvable")

    liens = session.exec(select(OccupationLocataire).where(OccupationLocataire.locataire_id == locataire_id)).all()
    occupation_ids = [lien.occupation_id for lien in liens]
    occupations = []
    if occupation_ids:
        occupations = session.exec(select(Occupation).where(Occupation.id.in_(occupation_ids))).all()
    occupations.sort(key=lambda o: o.date_entree, reverse=True)

    unites_par_id = {u.id: u for u in session.exec(select(UniteLocative)).all()}
    biens_par_id = {b.id: b for b in session.exec(select(Bien)).all()}

    return templates.TemplateResponse(
        request,
        "locataires/detail.html",
        {
            "utilisateur": utilisateur,
            "locataire": locataire,
            "occupations": occupations,
            "unites_par_id": unites_par_id,
            "biens_par_id": biens_par_id,
        },
    )


@router.get("/{locataire_id}/modifier", name="locataire_modifier_formulaire")
def locataire_modifier_formulaire(
    request: Request,
    locataire_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    locataire = session.get(Locataire, locataire_id)
    if locataire is None:
        raise HTTPException(status_code=404, detail="Locataire introuvable")
    return templates.TemplateResponse(
        request,
        "locataires/formulaire.html",
        {"utilisateur": utilisateur, "locataire": locataire, "types_garantie": list(TypeGarantie), "erreur": None},
    )


@router.post("/{locataire_id}/modifier", name="locataire_modifier")
def locataire_modifier(
    request: Request,
    locataire_id: int,
    nom: str = Form(...),
    prenom: str = Form(...),
    date_naissance: str = Form(""),
    email: str = Form(""),
    telephone: str = Form(""),
    type_garantie: str = Form(...),
    garant_nom: str = Form(""),
    garant_contact: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    locataire = session.get(Locataire, locataire_id)
    if locataire is None:
        raise HTTPException(status_code=404, detail="Locataire introuvable")

    try:
        type_garantie_enum = TypeGarantie(type_garantie)
        date_naissance_parsee = parser_date_optionnelle(date_naissance)
    except ValueError as erreur:
        return templates.TemplateResponse(
            request,
            "locataires/formulaire.html",
            {
                "utilisateur": utilisateur,
                "locataire": locataire,
                "types_garantie": list(TypeGarantie),
                "erreur": f"Données invalides : {erreur}",
            },
            status_code=400,
        )

    locataire.nom = nom
    locataire.prenom = prenom
    locataire.date_naissance = date_naissance_parsee
    locataire.email = email or None
    locataire.telephone = telephone or None
    locataire.type_garantie = type_garantie_enum
    locataire.garant_nom = garant_nom or None
    locataire.garant_contact = garant_contact or None

    session.add(locataire)
    session.commit()

    return RedirectResponse(url=request.url_for("locataire_detail", locataire_id=locataire.id), status_code=303)


@router.post("/{locataire_id}/supprimer", name="locataire_supprimer")
def locataire_supprimer(
    request: Request,
    locataire_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    locataire = session.get(Locataire, locataire_id)
    if locataire is None:
        raise HTTPException(status_code=404, detail="Locataire introuvable")

    if _locataire_a_des_donnees_liees(session, locataire):
        raise HTTPException(
            status_code=409,
            detail="Impossible de supprimer ce locataire : des occupations ou paiements y sont rattachés.",
        )

    session.delete(locataire)
    session.commit()

    return RedirectResponse(url=request.url_for("locataires_liste"), status_code=303)
