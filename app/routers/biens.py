from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    Bien,
    LigneDepense,
    Locataire,
    MandatGestion,
    Occupation,
    OccupationLocataire,
    ReleveGestion,
    UniteLocative,
    Utilisateur,
)
from app.models.enums import DpeLettre, StatutOccupation, TypeBien
from app.security import get_current_user
from app.services.formulaires import parser_date_optionnelle, parser_float_optionnel, parser_int_optionnel
from app.templating import templates

router = APIRouter(prefix="/biens", tags=["biens"])


def _bien_a_des_donnees_liees(session: Session, bien: Bien) -> bool:
    unite_ids = session.exec(select(UniteLocative.id).where(UniteLocative.bien_id == bien.id)).all()

    if session.exec(select(ReleveGestion).where(ReleveGestion.bien_id == bien.id)).first() is not None:
        return True
    if session.exec(select(LigneDepense).where(LigneDepense.bien_id == bien.id)).first() is not None:
        return True

    if unite_ids:
        if session.exec(select(Occupation).where(Occupation.unite_locative_id.in_(unite_ids))).first() is not None:
            return True
        if session.exec(select(MandatGestion).where(MandatGestion.unite_locative_id.in_(unite_ids))).first() is not None:
            return True

    return False


def _occupation_active_par_unite(session: Session, unite_ids: list[int]) -> dict[int, dict]:
    if not unite_ids:
        return {}

    occupations = session.exec(
        select(Occupation).where(
            Occupation.unite_locative_id.in_(unite_ids), Occupation.statut == StatutOccupation.ACTIVE
        )
    ).all()

    resultat: dict[int, dict] = {}
    for occupation in occupations:
        liens = session.exec(
            select(OccupationLocataire).where(OccupationLocataire.occupation_id == occupation.id)
        ).all()
        locataires = [session.get(Locataire, lien.locataire_id) for lien in liens]
        resultat[occupation.unite_locative_id] = {"occupation": occupation, "locataires": locataires}
    return resultat


@router.get("", name="biens_liste")
def biens_liste(
    request: Request,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    biens = session.exec(select(Bien).order_by(Bien.libelle)).all()
    return templates.TemplateResponse(request, "biens/liste.html", {"utilisateur": utilisateur, "biens": biens})


@router.get("/nouveau", name="bien_nouveau_formulaire")
def bien_nouveau_formulaire(request: Request, utilisateur: Utilisateur = Depends(get_current_user)):
    return templates.TemplateResponse(
        request,
        "biens/formulaire.html",
        {"utilisateur": utilisateur, "bien": None, "types_bien": list(TypeBien), "erreur": None},
    )


@router.post("", name="bien_creer")
def bien_creer(
    request: Request,
    type: str = Form(...),
    libelle: str = Form(...),
    adresse_rue: str = Form(...),
    adresse_code_postal: str = Form(...),
    adresse_ville: str = Form(...),
    date_acquisition: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    try:
        type_bien = TypeBien(type)
        date_acquisition_parsee = parser_date_optionnelle(date_acquisition)
    except ValueError as erreur:
        return templates.TemplateResponse(
            request,
            "biens/formulaire.html",
            {
                "utilisateur": utilisateur,
                "bien": None,
                "types_bien": list(TypeBien),
                "erreur": f"Données invalides : {erreur}",
            },
            status_code=400,
        )

    bien = Bien(
        type=type_bien,
        libelle=libelle,
        adresse_rue=adresse_rue,
        adresse_code_postal=adresse_code_postal,
        adresse_ville=adresse_ville,
        date_acquisition=date_acquisition_parsee,
        notes=notes or None,
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)

    if type_bien == TypeBien.APPARTEMENT_ISOLE:
        session.add(UniteLocative(bien_id=bien.id, libelle=libelle))
        session.commit()

    return RedirectResponse(url=request.url_for("bien_detail", bien_id=bien.id), status_code=303)


@router.get("/{bien_id}", name="bien_detail")
def bien_detail(
    request: Request,
    bien_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    bien = session.get(Bien, bien_id)
    if bien is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")

    unites = session.exec(
        select(UniteLocative).where(UniteLocative.bien_id == bien_id).order_by(UniteLocative.libelle)
    ).all()

    occupation_par_unite = _occupation_active_par_unite(session, [u.id for u in unites])

    return templates.TemplateResponse(
        request,
        "biens/detail.html",
        {
            "utilisateur": utilisateur,
            "bien": bien,
            "unites": unites,
            "occupation_par_unite": occupation_par_unite,
        },
    )


@router.get("/{bien_id}/modifier", name="bien_modifier_formulaire")
def bien_modifier_formulaire(
    request: Request,
    bien_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    bien = session.get(Bien, bien_id)
    if bien is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")
    return templates.TemplateResponse(
        request,
        "biens/formulaire.html",
        {"utilisateur": utilisateur, "bien": bien, "types_bien": list(TypeBien), "erreur": None},
    )


@router.post("/{bien_id}/modifier", name="bien_modifier")
def bien_modifier(
    request: Request,
    bien_id: int,
    libelle: str = Form(...),
    adresse_rue: str = Form(...),
    adresse_code_postal: str = Form(...),
    adresse_ville: str = Form(...),
    date_acquisition: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    bien = session.get(Bien, bien_id)
    if bien is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")

    try:
        date_acquisition_parsee = parser_date_optionnelle(date_acquisition)
    except ValueError as erreur:
        return templates.TemplateResponse(
            request,
            "biens/formulaire.html",
            {
                "utilisateur": utilisateur,
                "bien": bien,
                "types_bien": list(TypeBien),
                "erreur": f"Données invalides : {erreur}",
            },
            status_code=400,
        )

    bien.libelle = libelle
    bien.adresse_rue = adresse_rue
    bien.adresse_code_postal = adresse_code_postal
    bien.adresse_ville = adresse_ville
    bien.date_acquisition = date_acquisition_parsee
    bien.notes = notes or None

    session.add(bien)
    session.commit()

    return RedirectResponse(url=request.url_for("bien_detail", bien_id=bien.id), status_code=303)


@router.post("/{bien_id}/supprimer", name="bien_supprimer")
def bien_supprimer(
    request: Request,
    bien_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    bien = session.get(Bien, bien_id)
    if bien is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")

    if _bien_a_des_donnees_liees(session, bien):
        raise HTTPException(
            status_code=409,
            detail="Impossible de supprimer ce bien : des occupations, mandats ou relevés y sont rattachés.",
        )

    for unite in session.exec(select(UniteLocative).where(UniteLocative.bien_id == bien.id)).all():
        session.delete(unite)
    session.delete(bien)
    session.commit()

    return RedirectResponse(url=request.url_for("biens_liste"), status_code=303)


@router.get("/{bien_id}/unites/nouvelle", name="unite_nouvelle_formulaire")
def unite_nouvelle_formulaire(
    request: Request,
    bien_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    bien = session.get(Bien, bien_id)
    if bien is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")
    if bien.type == TypeBien.APPARTEMENT_ISOLE:
        raise HTTPException(status_code=409, detail="Un appartement isolé ne peut avoir qu'une seule unité locative.")

    return templates.TemplateResponse(
        request,
        "biens/unite_formulaire.html",
        {
            "utilisateur": utilisateur,
            "bien": bien,
            "unite": None,
            "lettres_dpe": list(DpeLettre),
            "erreur": None,
        },
    )


@router.post("/{bien_id}/unites", name="unite_creer")
def unite_creer(
    request: Request,
    bien_id: int,
    libelle: str = Form(...),
    etage: str = Form(""),
    surface_m2: str = Form(""),
    nb_pieces: str = Form(""),
    dpe_lettre: str = Form(""),
    dpe_date: str = Form(""),
    regime_fiscal: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    bien = session.get(Bien, bien_id)
    if bien is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")
    if bien.type == TypeBien.APPARTEMENT_ISOLE:
        raise HTTPException(status_code=409, detail="Un appartement isolé ne peut avoir qu'une seule unité locative.")

    try:
        unite = UniteLocative(
            bien_id=bien_id,
            libelle=libelle,
            etage=etage or None,
            surface_m2=parser_float_optionnel(surface_m2),
            nb_pieces=parser_int_optionnel(nb_pieces),
            dpe_lettre=DpeLettre(dpe_lettre) if dpe_lettre else None,
            dpe_date=parser_date_optionnelle(dpe_date),
            regime_fiscal=regime_fiscal or None,
        )
    except ValueError as erreur:
        return templates.TemplateResponse(
            request,
            "biens/unite_formulaire.html",
            {
                "utilisateur": utilisateur,
                "bien": bien,
                "unite": None,
                "lettres_dpe": list(DpeLettre),
                "erreur": f"Données invalides : {erreur}",
            },
            status_code=400,
        )

    session.add(unite)
    session.commit()

    return RedirectResponse(url=request.url_for("bien_detail", bien_id=bien_id), status_code=303)
