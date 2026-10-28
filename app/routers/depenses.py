from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Bien, LigneDepense, UniteLocative, Utilisateur
from app.security import get_current_user
from app.services.formulaires import parser_date_optionnelle, parser_int_optionnel
from app.templating import templates

router = APIRouter(prefix="/depenses", tags=["depenses"])

CATEGORIES_SUGGEREES = [
    "Taxe foncière",
    "Assurance propriétaire",
    "Travaux",
    "Charges de copropriété",
    "Honoraires de gestion",
    "Autre",
]


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


@router.get("/nouvelle", name="depense_nouvelle_formulaire")
def depense_nouvelle_formulaire(
    request: Request,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    biens_par_id = {b.id: b for b in session.exec(select(Bien).order_by(Bien.libelle)).all()}
    unites = session.exec(select(UniteLocative)).all()

    return templates.TemplateResponse(
        request,
        "depenses/formulaire.html",
        {
            "utilisateur": utilisateur,
            "biens_par_id": biens_par_id,
            "unites": unites,
            "categories_suggerees": CATEGORIES_SUGGEREES,
            "erreur": None,
        },
    )


@router.post("", name="depense_creer")
def depense_creer(
    request: Request,
    bien_id: str = Form(...),
    unite_locative_id: str = Form(""),
    categorie: str = Form(...),
    libelle: str = Form(...),
    montant: str = Form(...),
    date: str = Form(...),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    def _reponse_erreur(message: str):
        biens_par_id = {b.id: b for b in session.exec(select(Bien).order_by(Bien.libelle)).all()}
        unites = session.exec(select(UniteLocative)).all()
        return templates.TemplateResponse(
            request,
            "depenses/formulaire.html",
            {
                "utilisateur": utilisateur,
                "biens_par_id": biens_par_id,
                "unites": unites,
                "categories_suggerees": CATEGORIES_SUGGEREES,
                "erreur": f"Données invalides : {message}",
            },
            status_code=400,
        )

    try:
        bien_id_parse = int(bien_id)
        unite_id_parse = parser_int_optionnel(unite_locative_id)
        montant_parse = float(montant)
        date_parsee = parser_date_optionnelle(date)
        if date_parsee is None:
            raise ValueError("la date est obligatoire")
    except ValueError as erreur:
        return _reponse_erreur(str(erreur))

    bien = session.get(Bien, bien_id_parse)
    if bien is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")

    if unite_id_parse is not None:
        unite = session.get(UniteLocative, unite_id_parse)
        if unite is None:
            raise HTTPException(status_code=404, detail="Unité locative introuvable")
        if unite.bien_id != bien_id_parse:
            return _reponse_erreur("cette unité n'appartient pas au bien sélectionné")

    ligne = LigneDepense(
        releve_gestion_id=None,
        unite_locative_id=unite_id_parse,
        bien_id=bien_id_parse if unite_id_parse is None else None,
        categorie=categorie,
        libelle=libelle,
        montant=montant_parse,
        date=date_parsee,
    )
    session.add(ligne)
    session.commit()

    return RedirectResponse(url=request.url_for("depenses_liste"), status_code=303)


@router.post("/{ligne_id}/supprimer", name="depense_supprimer")
def depense_supprimer(
    request: Request,
    ligne_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    ligne = session.get(LigneDepense, ligne_id)
    if ligne is None:
        raise HTTPException(status_code=404, detail="Dépense introuvable")

    if ligne.releve_gestion_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Cette dépense provient d'un relevé de gestion : supprimez ou relancez le document correspondant.",
        )

    session.delete(ligne)
    session.commit()

    return RedirectResponse(url=request.url_for("depenses_liste"), status_code=303)
