import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = BASE_DIR / os.environ.get("DATABASE_PATH", "data/app.db")
ROOT_PATH = os.environ.get("ROOT_PATH", "/real-estate-manager")

# En développement uniquement : en production, SECRET_KEY doit être défini dans .env
# (générer avec `python -c "import secrets; print(secrets.token_hex(32))"`).
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-a-ne-jamais-utiliser-en-production")

# À passer à True une fois déployé derrière le reverse proxy mTLS qui termine le HTTPS
# (et qui doit alors transmettre l'en-tête X-Forwarded-Proto).
SESSION_COOKIE_HTTPS_ONLY = os.environ.get("SESSION_COOKIE_HTTPS_ONLY", "false").lower() == "true"
