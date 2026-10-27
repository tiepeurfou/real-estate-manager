import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

DATABASE_PATH = BASE_DIR / os.environ.get("DATABASE_PATH", "data/app.db")
ROOT_PATH = os.environ.get("ROOT_PATH", "/real-estate-manager")

# En développement uniquement : en production, SECRET_KEY doit être défini dans .env
# (générer avec `python -c "import secrets; print(secrets.token_hex(32))"`).
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-a-ne-jamais-utiliser-en-production")

# À passer à True une fois déployé derrière le reverse proxy mTLS qui termine le HTTPS
# (et qui doit alors transmettre l'en-tête X-Forwarded-Proto).
SESSION_COOKIE_HTTPS_ONLY = os.environ.get("SESSION_COOKIE_HTTPS_ONLY", "false").lower() == "true"

# Boîte mail dédiée (IMAP + mot de passe d'application, pas l'API Gmail OAuth2 —
# voir CLAUDE.md). Laissés vides tant que le compte Gmail dédié n'est pas prêt :
# l'écran d'ingestion mail affiche alors un message plutôt que de planter.
GMAIL_IMAP_HOTE = os.environ.get("GMAIL_IMAP_HOTE", "imap.gmail.com")
GMAIL_IMAP_PORT = int(os.environ.get("GMAIL_IMAP_PORT", "993"))
GMAIL_IMAP_ADRESSE = os.environ.get("GMAIL_IMAP_ADRESSE", "")
GMAIL_IMAP_MOT_DE_PASSE = os.environ.get("GMAIL_IMAP_MOT_DE_PASSE", "")
# À False uniquement pour pointer les tests vers le faux serveur IMAP local (sans TLS).
GMAIL_IMAP_SSL = os.environ.get("GMAIL_IMAP_SSL", "true").lower() == "true"
