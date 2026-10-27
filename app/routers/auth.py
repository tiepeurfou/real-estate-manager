from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Utilisateur
from app.security import SESSION_USER_KEY, verify_password
from app.templating import templates

router = APIRouter()


@router.get("/login", name="login_form")
def login_form(request: Request):
    return templates.TemplateResponse(request, "auth/login.html", {"erreur": None})


@router.post("/login", name="login_submit")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    utilisateur = session.exec(select(Utilisateur).where(Utilisateur.email == email)).first()

    if utilisateur is None or not verify_password(password, utilisateur.mot_de_passe_hash):
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"erreur": "Email ou mot de passe incorrect."},
            status_code=401,
        )

    utilisateur.derniere_connexion = datetime.now(timezone.utc)
    session.add(utilisateur)
    session.commit()

    request.session[SESSION_USER_KEY] = utilisateur.id
    return RedirectResponse(url=request.url_for("accueil"), status_code=303)


@router.get("/logout", name="logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url=request.url_for("login_form"), status_code=303)
