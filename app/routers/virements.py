import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    Bien,
    CompteBancaire,
    Gestionnaire,
    LigneDepense,
    LignePaiement,
    Locataire,
    Rapprochement,
    RapprochementLigne,
    ReleveGestion,
    UniteLocative,
    Utilisateur,
    VirementRecu,
)
from app.security import get_current_user
from app.services.formulaires import parser_date_optionnelle, parser_float_optionnel
from app.templating import templates

router = APIRouter(prefix="/virements", tags=["virements"])


def _lignes_deja_rapprochees(session: Session) -> tuple[set[int], set[int]]:
    liens = session.exec(select(RapprochementLigne)).all()
    paiement_ids = {lien.ligne_paiement_id for lien in liens if lien.ligne_paiement_id is not None}
    depense_ids = {lien.ligne_depense_id for lien in liens if lien.ligne_depense_id is not None}
    return paiement_ids, depense_ids


def _lignes_candidates(session: Session, gestionnaire_id: int) -> tuple[list[LignePaiement], list[LigneDepense]]:
    releve_ids = session.exec(select(ReleveGestion.id).where(ReleveGestion.gestionnaire_id == gestionnaire_id)).all()
    if not releve_ids:
        return [], []

    paiement_ids_exclus, depense_ids_exclus = _lignes_deja_rapprochees(session)

    paiements = session.exec(select(LignePaiement).where(LignePaiement.releve_gestion_id.in_(releve_ids))).all()
    depenses = session.exec(select(LigneDepense).where(LigneDepense.releve_gestion_id.in_(releve_ids))).all()

    paiements = [p for p in paiements if p.id not in paiement_ids_exclus]
    depenses = [d for d in depenses if d.id not in depense_ids_exclus]
    return paiements, depenses


@router.get("", name="virements_liste")
def virements_liste(
    request: Request,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    virements = session.exec(select(VirementRecu).order_by(VirementRecu.date_reception.desc())).all()
    rapprochements_par_virement = {
        r.virement_recu_id: r for r in session.exec(select(Rapprochement)).all()
    }

    return templates.TemplateResponse(
        request,
        "virements/liste.html",
        {"utilisateur": utilisateur, "virements": virements, "rapprochements_par_virement": rapprochements_par_virement},
    )


@router.get("/nouveau", name="virement_nouveau_formulaire")
def virement_nouveau_formulaire(
    request: Request,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    gestionnaires = session.exec(select(Gestionnaire).order_by(Gestionnaire.nom)).all()
    comptes = session.exec(select(CompteBancaire).order_by(CompteBancaire.libelle)).all()
    comptes_par_gestionnaire_json = json.dumps(
        {str(g.id): (g.compte_bancaire_id or "") for g in gestionnaires}
    )

    return templates.TemplateResponse(
        request,
        "virements/formulaire.html",
        {
            "utilisateur": utilisateur,
            "gestionnaires": gestionnaires,
            "comptes": comptes,
            "comptes_par_gestionnaire_json": comptes_par_gestionnaire_json,
            "erreur": None,
        },
    )


@router.post("", name="virement_creer")
def virement_creer(
    request: Request,
    gestionnaire_id: str = Form(...),
    compte_bancaire_id: str = Form(...),
    montant: str = Form(...),
    date_reception: str = Form(...),
    periode_couverte: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    def _reponse_erreur(message: str):
        gestionnaires = session.exec(select(Gestionnaire).order_by(Gestionnaire.nom)).all()
        comptes = session.exec(select(CompteBancaire).order_by(CompteBancaire.libelle)).all()
        comptes_par_gestionnaire_json = json.dumps(
            {str(g.id): (g.compte_bancaire_id or "") for g in gestionnaires}
        )
        return templates.TemplateResponse(
            request,
            "virements/formulaire.html",
            {
                "utilisateur": utilisateur,
                "gestionnaires": gestionnaires,
                "comptes": comptes,
                "comptes_par_gestionnaire_json": comptes_par_gestionnaire_json,
                "erreur": f"Données invalides : {message}",
            },
            status_code=400,
        )

    try:
        gestionnaire_id_parse = int(gestionnaire_id)
        compte_bancaire_id_parse = int(compte_bancaire_id)
        montant_parse = float(montant)
        date_reception_parsee = parser_date_optionnelle(date_reception)
        if date_reception_parsee is None:
            raise ValueError("la date de réception est obligatoire")
        periode_couverte_parsee = parser_date_optionnelle(periode_couverte)
    except ValueError as erreur:
        return _reponse_erreur(str(erreur))

    gestionnaire = session.get(Gestionnaire, gestionnaire_id_parse)
    if gestionnaire is None:
        raise HTTPException(status_code=404, detail="Gestionnaire introuvable")
    compte = session.get(CompteBancaire, compte_bancaire_id_parse)
    if compte is None:
        raise HTTPException(status_code=404, detail="Compte bancaire introuvable")

    virement = VirementRecu(
        gestionnaire_id=gestionnaire_id_parse,
        compte_bancaire_id=compte_bancaire_id_parse,
        montant=montant_parse,
        date_reception=date_reception_parsee,
        periode_couverte=periode_couverte_parsee,
        notes=notes or None,
    )
    session.add(virement)
    session.commit()
    session.refresh(virement)

    return RedirectResponse(url=request.url_for("virement_detail", virement_id=virement.id), status_code=303)


@router.get("/{virement_id}", name="virement_detail")
def virement_detail(
    request: Request,
    virement_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    virement = session.get(VirementRecu, virement_id)
    if virement is None:
        raise HTTPException(status_code=404, detail="Virement introuvable")

    rapprochement = session.exec(select(Rapprochement).where(Rapprochement.virement_recu_id == virement_id)).first()

    if rapprochement is not None:
        liens = session.exec(
            select(RapprochementLigne).where(RapprochementLigne.rapprochement_id == rapprochement.id)
        ).all()
        paiements = [session.get(LignePaiement, lien.ligne_paiement_id) for lien in liens if lien.ligne_paiement_id]
        depenses = [session.get(LigneDepense, lien.ligne_depense_id) for lien in liens if lien.ligne_depense_id]
        return templates.TemplateResponse(
            request,
            "virements/detail.html",
            {
                "utilisateur": utilisateur,
                "virement": virement,
                "rapprochement": rapprochement,
                "paiements": paiements,
                "depenses": depenses,
            },
        )

    candidats_paiements, candidats_depenses = _lignes_candidates(session, virement.gestionnaire_id)
    unites_par_id = {u.id: u for u in session.exec(select(UniteLocative)).all()}
    biens_par_id = {b.id: b for b in session.exec(select(Bien)).all()}
    locataires_par_id = {l.id: l for l in session.exec(select(Locataire)).all()}

    return templates.TemplateResponse(
        request,
        "virements/rapprochement_formulaire.html",
        {
            "utilisateur": utilisateur,
            "virement": virement,
            "candidats_paiements": candidats_paiements,
            "candidats_depenses": candidats_depenses,
            "unites_par_id": unites_par_id,
            "biens_par_id": biens_par_id,
            "locataires_par_id": locataires_par_id,
        },
    )


@router.post("/{virement_id}/rapprocher", name="virement_rapprocher")
def virement_rapprocher(
    request: Request,
    virement_id: int,
    paiement_ids: list[str] = Form([]),
    depense_ids: list[str] = Form([]),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    virement = session.get(VirementRecu, virement_id)
    if virement is None:
        raise HTTPException(status_code=404, detail="Virement introuvable")

    if session.exec(select(Rapprochement).where(Rapprochement.virement_recu_id == virement_id)).first() is not None:
        raise HTTPException(status_code=409, detail="Ce virement est déjà rapproché.")

    try:
        paiements = [_charger_ou_404(session, LignePaiement, pid) for pid in paiement_ids]
        depenses = [_charger_ou_404(session, LigneDepense, did) for did in depense_ids]
    except ValueError as erreur:
        raise HTTPException(status_code=400, detail=f"Données invalides : {erreur}") from erreur

    total = sum(p.montant_percu for p in paiements) - sum(d.montant for d in depenses)
    ecart = virement.montant - total

    rapprochement = Rapprochement(virement_recu_id=virement_id, ecart=ecart)
    session.add(rapprochement)
    session.commit()
    session.refresh(rapprochement)

    for p in paiements:
        session.add(RapprochementLigne(rapprochement_id=rapprochement.id, ligne_paiement_id=p.id))
    for d in depenses:
        session.add(RapprochementLigne(rapprochement_id=rapprochement.id, ligne_depense_id=d.id))
    session.commit()

    return RedirectResponse(url=request.url_for("virement_detail", virement_id=virement_id), status_code=303)


def _charger_ou_404(session: Session, modele, id_str: str):
    objet = session.get(modele, int(id_str))
    if objet is None:
        raise HTTPException(status_code=404, detail=f"Ligne {id_str} introuvable")
    return objet


@router.post("/{virement_id}/rapprochement/supprimer", name="rapprochement_supprimer")
def rapprochement_supprimer(
    request: Request,
    virement_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    virement = session.get(VirementRecu, virement_id)
    if virement is None:
        raise HTTPException(status_code=404, detail="Virement introuvable")

    rapprochement = session.exec(select(Rapprochement).where(Rapprochement.virement_recu_id == virement_id)).first()
    if rapprochement is None:
        raise HTTPException(status_code=404, detail="Aucun rapprochement pour ce virement")

    for ligne in session.exec(
        select(RapprochementLigne).where(RapprochementLigne.rapprochement_id == rapprochement.id)
    ).all():
        session.delete(ligne)
    session.delete(rapprochement)
    session.commit()

    return RedirectResponse(url=request.url_for("virement_detail", virement_id=virement_id), status_code=303)


@router.post("/{virement_id}/supprimer", name="virement_supprimer")
def virement_supprimer(
    request: Request,
    virement_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    virement = session.get(VirementRecu, virement_id)
    if virement is None:
        raise HTTPException(status_code=404, detail="Virement introuvable")

    if session.exec(select(Rapprochement).where(Rapprochement.virement_recu_id == virement_id)).first() is not None:
        raise HTTPException(status_code=409, detail="Supprimez d'abord le rapprochement de ce virement.")

    session.delete(virement)
    session.commit()

    return RedirectResponse(url=request.url_for("virements_liste"), status_code=303)
