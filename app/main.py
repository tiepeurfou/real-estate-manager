from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import BASE_DIR, SECRET_KEY, SESSION_COOKIE_HTTPS_ONLY
from app.models import Utilisateur
from app.routers import auth, biens, comptes_bancaires, gestionnaires, mandats, unites
from app.security import get_current_user
from app.templating import templates

app = FastAPI(title="Real Estate Manager")

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="rem_session",
    same_site="lax",
    https_only=SESSION_COOKIE_HTTPS_ONLY,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

app.include_router(auth.router)
app.include_router(biens.router)
app.include_router(unites.router)
app.include_router(gestionnaires.router)
app.include_router(mandats.router)
app.include_router(comptes_bancaires.router)


@app.exception_handler(HTTPException)
async def redirection_si_non_authentifie(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url=request.url_for("login_form"), status_code=303)
    return await http_exception_handler(request, exc)


@app.get("/", name="accueil")
def accueil(request: Request, utilisateur: Utilisateur = Depends(get_current_user)):
    return templates.TemplateResponse(request, "accueil.html", {"utilisateur": utilisateur})


if __name__ == "__main__":
    import uvicorn

    from app.config import ROOT_PATH

    # --root-path informe uvicorn/Starlette du préfixe sous lequel le reverse
    # proxy (sur l'autre Raspberry Pi) expose l'application, pour que les URLs
    # générées (redirections, liens) soient correctes vues depuis l'extérieur.
    # Le reverse proxy doit lui-même retirer ce préfixe avant de transmettre
    # la requête ici.
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, root_path=ROOT_PATH)
