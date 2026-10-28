from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Bien, DepenseRecurrente, LigneDepense, UniteLocative, Utilisateur
from app.models.enums import FrequenceDepense
from app.security import get_current_user
from app.services.depenses_recurrentes import generer_echeances_dues
from app.services.formulaires import parser_date_optionnelle, parser_int_optionnel
from app.templating import templates

router = APIRouter(prefix="/depenses-recurrentes", tags=["depenses-recurrentes"])

CATEGORIES_SUGGEREES = ["Crédit immobilier", "Électricité parties communes", "Assurance propriétaire", "Charges de copropriété"]


def _contexte_formulaire(session: Session) -> dict:
    return {
        "biens_par_id": {b.id: b for b in session.exec(select(Bien).order_by(Bien.libelle)).all()},
        "unites": session.exec(select(UniteLocative)).all(),
        "frequences": list(FrequenceDepense),
        "categories_suggerees": CATEGORIES_SUGGEREES,
    }


@router.get("", name="depenses_recurrentes_liste")
def depenses_recurrentes_liste(
    request: Request,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    templates_recurrents = session.exec(select(DepenseRecurrente).order_by(DepenseRecurrente.date_debut.desc())).all()
    biens_par_id = {b.id: b for b in session.exec(select(Bien)).all()}
    unites_par_id = {u.id: u for u in session.exec(select(UniteLocative)).all()}

    return templates.TemplateResponse(
        request,
        "depenses_recurrentes/liste.html",
        {
            "utilisateur": utilisateur,
            "templates_recurrents": templates_recurrents,
            "biens_par_id": biens_par_id,
            "unites_par_id": unites_par_id,
            "aujourdhui": date.today(),
        },
    )


@router.get("/nouvelle", name="depense_recurrente_nouvelle_formulaire")
def depense_recurrente_nouvelle_formulaire(
    request: Request,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request,
        "depenses_recurrentes/formulaire.html",
        {"utilisateur": utilisateur, "depense_recurrente": None, "erreur": None, **_contexte_formulaire(session)},
    )


@router.post("", name="depense_recurrente_creer")
def depense_recurrente_creer(
    request: Request,
    bien_id: str = Form(...),
    unite_locative_id: str = Form(""),
    categorie: str = Form(...),
    libelle: str = Form(...),
    montant: str = Form(...),
    frequence: str = Form(...),
    date_debut: str = Form(...),
    date_fin: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    def _reponse_erreur(message: str):
        return templates.TemplateResponse(
            request,
            "depenses_recurrentes/formulaire.html",
            {
                "utilisateur": utilisateur,
                "depense_recurrente": None,
                "erreur": f"Données invalides : {message}",
                **_contexte_formulaire(session),
            },
            status_code=400,
        )

    try:
        bien_id_parse = int(bien_id)
        unite_id_parse = parser_int_optionnel(unite_locative_id)
        montant_parse = float(montant)
        frequence_enum = FrequenceDepense(frequence)
        date_debut_parsee = parser_date_optionnelle(date_debut)
        if date_debut_parsee is None:
            raise ValueError("la date de début est obligatoire")
        date_fin_parsee = parser_date_optionnelle(date_fin)
        if date_fin_parsee is not None and date_fin_parsee < date_debut_parsee:
            raise ValueError("la date de fin ne peut pas précéder la date de début")
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

    session.add(
        DepenseRecurrente(
            bien_id=bien_id_parse,
            unite_locative_id=unite_id_parse,
            categorie=categorie,
            libelle=libelle,
            montant=montant_parse,
            frequence=frequence_enum,
            date_debut=date_debut_parsee,
            date_fin=date_fin_parsee,
        )
    )
    session.commit()

    return RedirectResponse(url=request.url_for("depenses_recurrentes_liste"), status_code=303)


@router.get("/{depense_recurrente_id}/modifier", name="depense_recurrente_modifier_formulaire")
def depense_recurrente_modifier_formulaire(
    request: Request,
    depense_recurrente_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    depense_recurrente = session.get(DepenseRecurrente, depense_recurrente_id)
    if depense_recurrente is None:
        raise HTTPException(status_code=404, detail="Dépense récurrente introuvable")

    return templates.TemplateResponse(
        request,
        "depenses_recurrentes/formulaire.html",
        {
            "utilisateur": utilisateur,
            "depense_recurrente": depense_recurrente,
            "erreur": None,
            **_contexte_formulaire(session),
        },
    )


@router.post("/{depense_recurrente_id}/modifier", name="depense_recurrente_modifier")
def depense_recurrente_modifier(
    request: Request,
    depense_recurrente_id: int,
    bien_id: str = Form(...),
    unite_locative_id: str = Form(""),
    categorie: str = Form(...),
    libelle: str = Form(...),
    montant: str = Form(...),
    frequence: str = Form(...),
    date_debut: str = Form(...),
    date_fin: str = Form(""),
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    depense_recurrente = session.get(DepenseRecurrente, depense_recurrente_id)
    if depense_recurrente is None:
        raise HTTPException(status_code=404, detail="Dépense récurrente introuvable")

    def _reponse_erreur(message: str):
        return templates.TemplateResponse(
            request,
            "depenses_recurrentes/formulaire.html",
            {
                "utilisateur": utilisateur,
                "depense_recurrente": depense_recurrente,
                "erreur": f"Données invalides : {message}",
                **_contexte_formulaire(session),
            },
            status_code=400,
        )

    try:
        bien_id_parse = int(bien_id)
        unite_id_parse = parser_int_optionnel(unite_locative_id)
        montant_parse = float(montant)
        frequence_enum = FrequenceDepense(frequence)
        date_debut_parsee = parser_date_optionnelle(date_debut)
        if date_debut_parsee is None:
            raise ValueError("la date de début est obligatoire")
        date_fin_parsee = parser_date_optionnelle(date_fin)
        if date_fin_parsee is not None and date_fin_parsee < date_debut_parsee:
            raise ValueError("la date de fin ne peut pas précéder la date de début")
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

    depense_recurrente.bien_id = bien_id_parse
    depense_recurrente.unite_locative_id = unite_id_parse
    depense_recurrente.categorie = categorie
    depense_recurrente.libelle = libelle
    depense_recurrente.montant = montant_parse
    depense_recurrente.frequence = frequence_enum
    depense_recurrente.date_debut = date_debut_parsee
    depense_recurrente.date_fin = date_fin_parsee
    session.add(depense_recurrente)
    session.commit()

    return RedirectResponse(url=request.url_for("depenses_recurrentes_liste"), status_code=303)


@router.post("/{depense_recurrente_id}/supprimer", name="depense_recurrente_supprimer")
def depense_recurrente_supprimer(
    request: Request,
    depense_recurrente_id: int,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    depense_recurrente = session.get(DepenseRecurrente, depense_recurrente_id)
    if depense_recurrente is None:
        raise HTTPException(status_code=404, detail="Dépense récurrente introuvable")

    if session.exec(select(LigneDepense).where(LigneDepense.depense_recurrente_id == depense_recurrente_id)).first() is not None:
        raise HTTPException(
            status_code=409,
            detail="Des dépenses ont déjà été générées depuis ce modèle : mettez une date de fin plutôt que de le supprimer.",
        )

    session.delete(depense_recurrente)
    session.commit()

    return RedirectResponse(url=request.url_for("depenses_recurrentes_liste"), status_code=303)


@router.post("/generer", name="depenses_recurrentes_generer")
def depenses_recurrentes_generer(
    request: Request,
    session: Session = Depends(get_session),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    generer_echeances_dues(session)
    return RedirectResponse(url=request.url_for("depenses_liste"), status_code=303)
