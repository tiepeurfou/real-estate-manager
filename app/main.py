from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import BASE_DIR, ROOT_PATH, SECRET_KEY, SESSION_COOKIE_HTTPS_ONLY
from app.routers import (
    auth,
    biens,
    comptes_bancaires,
    depenses,
    depenses_recurrentes,
    documents,
    gestionnaires,
    ingestion_mail,
    locataires,
    mandats,
    occupations,
    paiements,
    tableau_de_bord,
    unites,
    virements,
)

app = FastAPI(title="Real Estate Manager")

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="rem_session",
    same_site="lax",
    https_only=SESSION_COOKIE_HTTPS_ONLY,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

app.include_router(tableau_de_bord.router)
app.include_router(auth.router)
app.include_router(biens.router)
app.include_router(unites.router)
app.include_router(gestionnaires.router)
app.include_router(mandats.router)
app.include_router(comptes_bancaires.router)
app.include_router(locataires.router)
app.include_router(occupations.router)
app.include_router(virements.router)
app.include_router(depenses.router)
app.include_router(depenses_recurrentes.router)
app.include_router(paiements.router)
app.include_router(documents.router)
app.include_router(ingestion_mail.router)


@app.exception_handler(HTTPException)
async def redirection_si_non_authentifie(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url=request.url_for("login_form"), status_code=303)
    return await http_exception_handler(request, exc)


# `app` ci-dessus reste l'application "nue" (routes sans préfixe) — c'est elle
# que les tests importent et exercent directement (/login, /, ...).
#
# `app_prefixee` la monte sous ROOT_PATH : le préfixe /real-estate-manager/
# fonctionne alors nativement, en local comme en production, sans dépendre
# d'un reverse proxy qui le retirerait avant de transmettre la requête — le
# futur reverse proxy de l'autre Raspberry Pi doit au contraire transmettre
# le chemin tel quel (pas de réécriture de préfixe à configurer côté proxy).
app_prefixee = FastAPI()
app_prefixee.mount(ROOT_PATH, app)


if __name__ == "__main__":
    import uvicorn

    from app.config import APP_HOST, APP_PORT

    uvicorn.run(app_prefixee, host=APP_HOST, port=APP_PORT)
