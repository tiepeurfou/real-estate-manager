import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    Bien,
    CompteBancaire,
    ContactGestionnaire,
    Gestionnaire,
    MandatGestion,
    ReleveGestion,
    UniteLocative,
    Utilisateur,
    VirementRecu,
)
from app.models.enums import RoleMandat, TypeContact
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


def _contacts_de(session: Session, gestionnaire_id: int) -> list[ContactGestionnaire]:
    return session.exec(select(ContactGestionnaire).where(ContactGestionnaire.gestionnaire_id == gestionnaire_id)).all()


def _remplacer_contacts(
    session: Session, gestionnaire_id: int, contact_type: list[str], contact_valeur: list[str]
) -> None:
    """Remplace entièrement les contacts d'un gestionnaire par la liste
    soumise (plus simple à raisonner qu'un diff fin, et suffisant pour un
    formulaire mono-utilisateur)."""
    for contact in _contacts_de(session, gestionnaire_id):
        session.delete(contact)

    for type_brut, valeur in zip(contact_type, contact_valeur):
        valeur = valeur.strip()
        if not valeur:
            continue
        session.add(ContactGestionnaire(gestionnaire_id=gestionnaire_id, type=TypeContact(type_brut), valeur=valeur))

    session.commit()


def _contacts_json(contacts: list[ContactGestionnaire]) -> str:
    if not contacts:
        return json.dumps([{"type": "email", "valeur": ""}])
    return json.dumps([{"type": c.type.value, "valeur": c.valeur} for c in contacts])


@router.get("", name="gestionnaires_liste")
def gestionnaires_liste(
    request: Request,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    gestionnaires = session.exec(select(Gestionnaire).order_by(Gestionnaire.nom)).all()
    contacts_par_gestionnaire: dict[int, list[ContactGestionnaire]] = {}
    for contact in session.exec(select(ContactGestionnaire)).all():
        contacts_par_gestionnaire.setdefault(contact.gestionnaire_id, []).append(contact)

    return templates.TemplateResponse(
        request,
        "gestionnaires/liste.html",
        {"utilisateur": utilisateur, "gestionnaires": gestionnaires, "contacts_par_gestionnaire": contacts_par_gestionnaire},
    )


@router.get("/nouveau", name="gestionnaire_nouveau_formulaire")
def gestionnaire_nouveau_formulaire(
    request: Request,
    utilisateur: Utilisateur = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request,
        "gestionnaires/formulaire.html",
        {"utilisateur": utilisateur, "gestionnaire": None, "contacts_json": _contacts_json([]), "erreur": None},
    )


@router.post("", name="gestionnaire_creer")
def gestionnaire_creer(
    request: Request,
    nom: str = Form(...),
    contact_type: list[str] = Form([]),
    contact_valeur: list[str] = Form([]),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    gestionnaire = Gestionnaire(nom=nom)
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)

    _remplacer_contacts(session, gestionnaire.id, contact_type, contact_valeur)

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
    contacts = _contacts_de(session, gestionnaire_id)

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
            "contacts": contacts,
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
    contacts = _contacts_de(session, gestionnaire_id)
    return templates.TemplateResponse(
        request,
        "gestionnaires/formulaire.html",
        {"utilisateur": utilisateur, "gestionnaire": gestionnaire, "contacts_json": _contacts_json(contacts), "erreur": None},
    )


@router.post("/{gestionnaire_id}/modifier", name="gestionnaire_modifier")
def gestionnaire_modifier(
    request: Request,
    gestionnaire_id: int,
    nom: str = Form(...),
    contact_type: list[str] = Form([]),
    contact_valeur: list[str] = Form([]),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    gestionnaire = session.get(Gestionnaire, gestionnaire_id)
    if gestionnaire is None:
        raise HTTPException(status_code=404, detail="Gestionnaire introuvable")

    gestionnaire.nom = nom
    session.add(gestionnaire)
    session.commit()

    _remplacer_contacts(session, gestionnaire_id, contact_type, contact_valeur)

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

    for contact in _contacts_de(session, gestionnaire_id):
        session.delete(contact)
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

    # "Gestion complète" n'est pas une valeur d'enum à part (décision actée) :
    # elle crée simplement les deux mandats (mise_en_location + gestion) d'un
    # coup, plutôt que de devoir répéter l'opération manuellement deux fois.
    gestion_complete = role == "gestion_complete"

    try:
        unite_id_parse = int(unite_locative_id)
        roles_a_creer = [RoleMandat.MISE_EN_LOCATION, RoleMandat.GESTION] if gestion_complete else [RoleMandat(role)]
        date_debut_parsee = parser_date_optionnelle(date_debut)
        if date_debut_parsee is None:
            raise ValueError("la date de début est obligatoire")
        compte_bancaire_id_parse = parser_int_optionnel(compte_bancaire_id)
    except ValueError as erreur:
        return _reponse_erreur(str(erreur))

    unite = session.get(UniteLocative, unite_id_parse)
    if unite is None:
        raise HTTPException(status_code=404, detail="Unité locative introuvable")

    for role_enum in roles_a_creer:
        # La mise en location ne génère pas de versement : pas de compte dessus.
        compte_du_mandat = compte_bancaire_id_parse if role_enum == RoleMandat.GESTION else None
        session.add(
            MandatGestion(
                unite_locative_id=unite_id_parse,
                gestionnaire_id=gestionnaire_id,
                role=role_enum,
                date_debut=date_debut_parsee,
                compte_bancaire_id=compte_du_mandat,
            )
        )
    session.commit()

    return RedirectResponse(url=request.url_for("gestionnaire_detail", gestionnaire_id=gestionnaire_id), status_code=303)
