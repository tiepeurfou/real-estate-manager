import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session

from app.config import INGESTION_MAIL_INTERVALLE_HEURES
from app.database import engine
from app.services.ingestion_mail import notifier_nouveaux_candidats
from app.services.mail import ErreurConnexionImap, boite_mail_configuree, nouveau_client_imap

logger = logging.getLogger(__name__)


def scanner_la_boite_mail() -> None:
    """Un cycle du scan automatique : se connecte à la boîte mail dédiée,
    notifie (ntfy) pour chaque pièce jointe candidate jamais notifiée, sans
    jamais importer automatiquement (le tri gestionnaire/bien/période reste
    manuel sur /ingestion-mail). Ne fait rien si la boîte n'est pas
    configurée ; n'importe jamais ni ne plante le process si la connexion
    IMAP échoue — juste un avertissement dans les logs, on retentera au
    prochain cycle."""
    if not boite_mail_configuree():
        return
    try:
        with nouveau_client_imap() as client:
            with Session(engine) as session:
                notifier_nouveaux_candidats(client, session)
    except ErreurConnexionImap as erreur:
        logger.warning("Scan automatique de la boîte mail impossible : %s", erreur)


def demarrer_scheduler() -> BackgroundScheduler:
    """Démarre le scan périodique en tâche de fond (thread séparé — imaplib
    est bloquant, incompatible avec un scheduler asyncio sans wrapper). Un
    premier scan est lancé immédiatement au démarrage plutôt que d'attendre
    le premier intervalle complet."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(scanner_la_boite_mail, "interval", hours=INGESTION_MAIL_INTERVALLE_HEURES)
    scheduler.start()
    scheduler.add_job(scanner_la_boite_mail)
    return scheduler
