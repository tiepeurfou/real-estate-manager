import json
import urllib.error
import urllib.request

from app.config import NTFY_TOPIC, NTFY_URL


class ErreurNotification(Exception):
    pass


def notifications_configurees() -> bool:
    return bool(NTFY_TOPIC)


def envoyer_notification(titre: str, message: str, priorite: int = 3) -> None:
    """Envoie une notification push via ntfy (https://ntfy.sh par défaut,
    ou un serveur auto-hébergé via NTFY_URL). Publié en JSON plutôt que via
    les en-têtes HTTP `Title`/`Priority` documentés par ntfy : les en-têtes
    HTTP sont limités à ISO-8859-1, ce qui casserait les accents français
    du titre/message — le corps JSON, lui, est en UTF-8 sans restriction.

    Ne fait rien si NTFY_TOPIC n'est pas configuré (pas d'erreur) : les
    notifications sont un confort, pas une fonctionnalité bloquante."""
    if not notifications_configurees():
        return

    corps = json.dumps(
        {"topic": NTFY_TOPIC, "title": titre, "message": message, "priority": priorite}
    ).encode("utf-8")
    requete = urllib.request.Request(
        NTFY_URL, data=corps, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        urllib.request.urlopen(requete, timeout=10)
    except (urllib.error.URLError, OSError) as erreur:
        raise ErreurNotification(f"Envoi de la notification ntfy impossible : {erreur}") from erreur
