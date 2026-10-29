from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    Bien,
    LigneDepense,
    LignePaiement,
    Locataire,
    MandatGestion,
    Occupation,
    OccupationLocataire,
    UniteLocative,
    Utilisateur,
)
from app.models.enums import DpeLettre, StatutOccupation, TypeBien
from app.security import get_current_user
from app.services.formulaires import parser_date_optionnelle, parser_float_optionnel, parser_int_optionnel
from app.templating import templates

router = APIRouter(prefix="/unites", tags=["unites"])


def _unite_a_des_donnees_liees(session: Session, unite: UniteLocative) -> bool:
    if session.exec(select(Occupation).where(Occupation.unite_locative_id == unite.id)).first() is not None:
        return True
    if session.exec(select(MandatGestion).where(MandatGestion.unite_locative_id == unite.id)).first() is not None:
        return True
    if session.exec(select(LignePaiement).where(LignePaiement.unite_locative_id == unite.id)).first() is not None:
        return True
    if session.exec(select(LigneDepense).where(LigneDepense.unite_locative_id == unite.id)).first() is not None:
        return True
    return False


@router.get("/{unite_id}/modifier", name="unite_modifier_formulaire")
def unite_modifier_formulaire(
    request: Request,
    unite_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    unite = session.get(UniteLocative, unite_id)
    if unite is None:
        raise HTTPException(status_code=404, detail="Unité locative introuvable")
    bien = session.get(Bien, unite.bien_id)

    return templates.TemplateResponse(
        request,
        "biens/unite_formulaire.html",
        {
            "utilisateur": utilisateur,
            "bien": bien,
            "unite": unite,
            "lettres_dpe": list(DpeLettre),
            "erreur": None,
        },
    )


@router.post("/{unite_id}/modifier", name="unite_modifier")
def unite_modifier(
    request: Request,
    unite_id: int,
    libelle: str = Form(...),
    etage: str = Form(""),
    surface_m2: str = Form(""),
    nb_pieces: str = Form(""),
    dpe_lettre: str = Form(""),
    dpe_date: str = Form(""),
    regime_fiscal: str = Form(""),
    numero_fiscal: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    unite = session.get(UniteLocative, unite_id)
    if unite is None:
        raise HTTPException(status_code=404, detail="Unité locative introuvable")
    bien = session.get(Bien, unite.bien_id)

    try:
        surface_m2_parsee = parser_float_optionnel(surface_m2)
        nb_pieces_parse = parser_int_optionnel(nb_pieces)
        dpe_lettre_parsee = DpeLettre(dpe_lettre) if dpe_lettre else None
        dpe_date_parsee = parser_date_optionnelle(dpe_date)
    except ValueError as erreur:
        return templates.TemplateResponse(
            request,
            "biens/unite_formulaire.html",
            {
                "utilisateur": utilisateur,
                "bien": bien,
                "unite": unite,
                "lettres_dpe": list(DpeLettre),
                "erreur": f"Données invalides : {erreur}",
            },
            status_code=400,
        )

    unite.libelle = libelle
    unite.etage = etage or None
    unite.surface_m2 = surface_m2_parsee
    unite.nb_pieces = nb_pieces_parse
    unite.dpe_lettre = dpe_lettre_parsee
    unite.dpe_date = dpe_date_parsee
    unite.regime_fiscal = regime_fiscal or None
    unite.numero_fiscal = numero_fiscal or None

    session.add(unite)
    session.commit()

    return RedirectResponse(url=request.url_for("bien_detail", bien_id=unite.bien_id), status_code=303)


@router.post("/{unite_id}/supprimer", name="unite_supprimer")
def unite_supprimer(
    request: Request,
    unite_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    unite = session.get(UniteLocative, unite_id)
    if unite is None:
        raise HTTPException(status_code=404, detail="Unité locative introuvable")
    bien = session.get(Bien, unite.bien_id)

    if bien.type == TypeBien.APPARTEMENT_ISOLE:
        raise HTTPException(status_code=409, detail="Un appartement isolé doit conserver son unique unité locative.")

    if _unite_a_des_donnees_liees(session, unite):
        raise HTTPException(
            status_code=409,
            detail="Impossible de supprimer cette unité : des occupations, mandats ou lignes financières y sont rattachés.",
        )

    bien_id = unite.bien_id
    session.delete(unite)
    session.commit()

    return RedirectResponse(url=request.url_for("bien_detail", bien_id=bien_id), status_code=303)


@router.get("/{unite_id}/occupations/nouvelle", name="occupation_nouvelle_formulaire")
def occupation_nouvelle_formulaire(
    request: Request,
    unite_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    unite = session.get(UniteLocative, unite_id)
    if unite is None:
        raise HTTPException(status_code=404, detail="Unité locative introuvable")

    occupation_active = session.exec(
        select(Occupation).where(
            Occupation.unite_locative_id == unite_id, Occupation.statut == StatutOccupation.ACTIVE
        )
    ).first()
    if occupation_active is not None:
        raise HTTPException(status_code=409, detail="Cette unité est déjà occupée.")

    locataires = session.exec(select(Locataire).order_by(Locataire.nom, Locataire.prenom)).all()

    return templates.TemplateResponse(
        request,
        "occupations/nouvelle.html",
        {"utilisateur": utilisateur, "unite": unite, "locataires": locataires, "erreur": None},
    )


@router.post("/{unite_id}/occupations", name="occupation_creer")
def occupation_creer(
    request: Request,
    unite_id: int,
    locataire_ids: list[str] = Form([]),
    date_entree: str = Form(...),
    loyer_mensuel_hc: str = Form(...),
    charges_mensuelles: str = Form("0"),
    depot_garantie: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    unite = session.get(UniteLocative, unite_id)
    if unite is None:
        raise HTTPException(status_code=404, detail="Unité locative introuvable")

    occupation_active = session.exec(
        select(Occupation).where(
            Occupation.unite_locative_id == unite_id, Occupation.statut == StatutOccupation.ACTIVE
        )
    ).first()
    if occupation_active is not None:
        raise HTTPException(status_code=409, detail="Cette unité est déjà occupée.")

    try:
        date_entree_parsee = parser_date_optionnelle(date_entree)
        if date_entree_parsee is None:
            raise ValueError("la date d'entrée est obligatoire")
        loyer_parse = float(loyer_mensuel_hc)
        charges_parsees = parser_float_optionnel(charges_mensuelles) or 0
        depot_parse = parser_float_optionnel(depot_garantie)
        if not locataire_ids:
            raise ValueError("sélectionnez au moins un locataire")
    except ValueError as erreur:
        locataires = session.exec(select(Locataire).order_by(Locataire.nom, Locataire.prenom)).all()
        return templates.TemplateResponse(
            request,
            "occupations/nouvelle.html",
            {
                "utilisateur": utilisateur,
                "unite": unite,
                "locataires": locataires,
                "erreur": f"Données invalides : {erreur}",
            },
            status_code=400,
        )

    # Valider tous les locataires avant de créer quoi que ce soit : sinon un
    # id invalide laisserait une Occupation orpheline (active, sans aucun
    # locataire lié) déjà committée, qui bloquerait silencieusement toute
    # future attribution de cette unité (409 "déjà occupée").
    locataires_selectionnes = []
    for locataire_id in locataire_ids:
        locataire = session.get(Locataire, int(locataire_id))
        if locataire is None:
            raise HTTPException(status_code=404, detail=f"Locataire {locataire_id} introuvable")
        locataires_selectionnes.append(locataire)

    occupation = Occupation(
        unite_locative_id=unite_id,
        date_entree=date_entree_parsee,
        loyer_mensuel_hc=loyer_parse,
        charges_mensuelles=charges_parsees,
        depot_garantie=depot_parse,
        statut=StatutOccupation.ACTIVE,
    )
    session.add(occupation)
    session.commit()
    session.refresh(occupation)

    for locataire in locataires_selectionnes:
        session.add(OccupationLocataire(occupation_id=occupation.id, locataire_id=locataire.id))
    session.commit()

    return RedirectResponse(url=request.url_for("bien_detail", bien_id=unite.bien_id), status_code=303)
