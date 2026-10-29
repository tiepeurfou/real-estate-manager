import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

DATABASE_PATH = BASE_DIR / os.environ.get("DATABASE_PATH", "data/app.db")
ROOT_PATH = os.environ.get("ROOT_PATH", "/real-estate-manager")

# 127.0.0.1 par défaut (sûr pour le dev local). En production, le reverse proxy
# qui termine le TLS tourne sur un AUTRE Raspberry Pi : APP_HOST doit alors être
# mis à 0.0.0.0 (ou l'IP LAN de ce Pi) dans .env pour être atteignable depuis le réseau.
APP_HOST = os.environ.get("APP_HOST", "127.0.0.1")
APP_PORT = int(os.environ.get("APP_PORT", "8000"))

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

# Notifications push (ntfy.sh, voir app/services/notifications.py). NTFY_TOPIC
# vide désactive silencieusement l'envoi (aucune notification, pas d'erreur) —
# pratique pour les tests et pour un déploiement où l'utilisateur n'a pas
# encore choisi de topic.
NTFY_URL = os.environ.get("NTFY_URL", "https://ntfy.sh")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

# Fréquence du scan automatique de la boîte mail (app/services/scheduler.py),
# qui notifie dès qu'un nouveau compte-rendu candidat apparaît, sans import
# automatique (le tri gestionnaire/bien/période reste manuel sur /ingestion-mail).
INGESTION_MAIL_INTERVALLE_HEURES = int(os.environ.get("INGESTION_MAIL_INTERVALLE_HEURES", "2"))

# Sauvegarde quotidienne de data/app.db vers data/backups/ (app/services/sauvegarde.py).
# Heure creuse par défaut ; nombre de jours conservés avant purge automatique
# des sauvegardes les plus anciennes (évite de remplir le disque indéfiniment).
SAUVEGARDE_DB_HEURE = int(os.environ.get("SAUVEGARDE_DB_HEURE", "3"))
SAUVEGARDE_DB_NOMBRE_JOURS_CONSERVES = int(os.environ.get("SAUVEGARDE_DB_NOMBRE_JOURS_CONSERVES", "30"))
