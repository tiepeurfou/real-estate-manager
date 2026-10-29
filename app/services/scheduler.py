import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session

from app.config import DPE_HEURE, INGESTION_MAIL_INTERVALLE_HEURES, REVISION_LOYER_HEURE, SAUVEGARDE_DB_HEURE
from app.database import engine
from app.services.dpe import notifier_dpe_a_renouveler
from app.services.ingestion_mail import notifier_nouveaux_candidats
from app.services.mail import ErreurConnexionImap, boite_mail_configuree, nouveau_client_imap
from app.services.notifications import ErreurNotification, envoyer_notification
from app.services.revision_loyer import notifier_revisions_a_venir
from app.services.sauvegarde import sauvegarder_la_base

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


def sauvegarder_la_base_avec_alerte() -> None:
    """Sauvegarde quotidienne de la base. N'importe jamais, ne plante jamais
    le process : une sauvegarde qui échoue silencieusement serait pire que
    pas de sauvegarde du tout, d'où la notification push en cas d'échec —
    contrairement au scan mail (qui échoue souvent pour des raisons
    transitoires de réseau), un échec de sauvegarde (disque plein,
    permissions) mérite d'être vu rapidement."""
    try:
        sauvegarder_la_base()
    except OSError as erreur:
        logger.warning("Sauvegarde automatique de la base impossible : %s", erreur)
        try:
            envoyer_notification(
                titre="Sauvegarde de la base échouée",
                message=f"La sauvegarde automatique de data/app.db a échoué : {erreur}",
                priorite=5,
            )
        except ErreurNotification:
            pass


def verifier_revisions_loyer() -> None:
    """Un cycle du rappel quotidien de révision de loyer : notifie (ntfy)
    pour chaque occupation active approchant de sa date anniversaire de
    bail, sans jamais modifier le loyer automatiquement — l'ajustement
    reste manuel sur /occupations/{id}/modifier."""
    with Session(engine) as session:
        notifier_revisions_a_venir(session)


def verifier_dpe() -> None:
    """Un cycle du rappel quotidien d'expiration de DPE : notifie (ntfy)
    pour chaque unité dont le DPE (valide 10 ans) approche de l'expiration,
    sans jamais planifier de diagnostic automatiquement — reste à faire
    manuellement auprès d'un diagnostiqueur."""
    with Session(engine) as session:
        notifier_dpe_a_renouveler(session)


def demarrer_scheduler() -> BackgroundScheduler:
    """Démarre les tâches de fond (thread séparé — imaplib est bloquant,
    incompatible avec un scheduler asyncio sans wrapper). Un premier scan de
    la boîte mail est lancé immédiatement au démarrage plutôt que d'attendre
    le premier intervalle complet ; la sauvegarde, le rappel de révision de
    loyer et le rappel DPE, eux, n'ont pas besoin de tourner immédiatement
    (pas aussi urgents, et éviter de les déclencher à chaque redémarrage du
    service)."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(scanner_la_boite_mail, "interval", hours=INGESTION_MAIL_INTERVALLE_HEURES)
    scheduler.add_job(sauvegarder_la_base_avec_alerte, "cron", hour=SAUVEGARDE_DB_HEURE, minute=0)
    scheduler.add_job(verifier_revisions_loyer, "cron", hour=REVISION_LOYER_HEURE, minute=0)
    scheduler.add_job(verifier_dpe, "cron", hour=DPE_HEURE, minute=0)
    scheduler.start()
    scheduler.add_job(scanner_la_boite_mail)
    return scheduler
