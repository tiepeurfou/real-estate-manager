from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import CompteBancaire, MandatGestion, Utilisateur, VirementRecu
from app.models.enums import Banque
from app.security import get_current_user
from app.templating import templates

router = APIRouter(prefix="/comptes-bancaires", tags=["comptes-bancaires"])


def _compte_a_des_donnees_liees(session: Session, compte: CompteBancaire) -> bool:
    if session.exec(select(MandatGestion).where(MandatGestion.compte_bancaire_id == compte.id)).first() is not None:
        return True
    if session.exec(select(VirementRecu).where(VirementRecu.compte_bancaire_id == compte.id)).first() is not None:
        return True
    return False


@router.get("", name="comptes_bancaires_liste")
def comptes_bancaires_liste(
    request: Request,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    comptes = session.exec(select(CompteBancaire).order_by(CompteBancaire.libelle)).all()
    return templates.TemplateResponse(
        request, "comptes_bancaires/liste.html", {"utilisateur": utilisateur, "comptes": comptes}
    )


@router.get("/nouveau", name="compte_bancaire_nouveau_formulaire")
def compte_bancaire_nouveau_formulaire(request: Request, utilisateur: Utilisateur = Depends(get_current_user)):
    return templates.TemplateResponse(
        request,
        "comptes_bancaires/formulaire.html",
        {"utilisateur": utilisateur, "compte": None, "banques": list(Banque), "erreur": None},
    )


@router.post("", name="compte_bancaire_creer")
def compte_bancaire_creer(
    request: Request,
    banque: str = Form(...),
    libelle: str = Form(...),
    iban: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    try:
        banque_enum = Banque(banque)
    except ValueError as erreur:
        return templates.TemplateResponse(
            request,
            "comptes_bancaires/formulaire.html",
            {
                "utilisateur": utilisateur,
                "compte": None,
                "banques": list(Banque),
                "erreur": f"Données invalides : {erreur}",
            },
            status_code=400,
        )

    compte = CompteBancaire(banque=banque_enum, libelle=libelle, iban=iban or None)
    session.add(compte)
    session.commit()

    return RedirectResponse(url=request.url_for("comptes_bancaires_liste"), status_code=303)


@router.get("/{compte_id}/modifier", name="compte_bancaire_modifier_formulaire")
def compte_bancaire_modifier_formulaire(
    request: Request,
    compte_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    compte = session.get(CompteBancaire, compte_id)
    if compte is None:
        raise HTTPException(status_code=404, detail="Compte bancaire introuvable")
    return templates.TemplateResponse(
        request,
        "comptes_bancaires/formulaire.html",
        {"utilisateur": utilisateur, "compte": compte, "banques": list(Banque), "erreur": None},
    )


@router.post("/{compte_id}/modifier", name="compte_bancaire_modifier")
def compte_bancaire_modifier(
    request: Request,
    compte_id: int,
    libelle: str = Form(...),
    iban: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    compte = session.get(CompteBancaire, compte_id)
    if compte is None:
        raise HTTPException(status_code=404, detail="Compte bancaire introuvable")

    compte.libelle = libelle
    compte.iban = iban or None
    session.add(compte)
    session.commit()

    return RedirectResponse(url=request.url_for("comptes_bancaires_liste"), status_code=303)


@router.post("/{compte_id}/supprimer", name="compte_bancaire_supprimer")
def compte_bancaire_supprimer(
    request: Request,
    compte_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    compte = session.get(CompteBancaire, compte_id)
    if compte is None:
        raise HTTPException(status_code=404, detail="Compte bancaire introuvable")

    if _compte_a_des_donnees_liees(session, compte):
        raise HTTPException(
            status_code=409,
            detail="Impossible de supprimer ce compte : un gestionnaire ou un virement y est rattaché.",
        )

    session.delete(compte)
    session.commit()

    return RedirectResponse(url=request.url_for("comptes_bancaires_liste"), status_code=303)
