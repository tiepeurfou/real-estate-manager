import imaplib
from dataclasses import dataclass, field
from datetime import datetime
from email import message_from_bytes
from email.message import Message
from email.utils import parsedate_to_datetime

from app.config import GMAIL_IMAP_ADRESSE, GMAIL_IMAP_HOTE, GMAIL_IMAP_MOT_DE_PASSE, GMAIL_IMAP_PORT, GMAIL_IMAP_SSL


@dataclass
class PieceJointe:
    nom: str
    contenu: bytes


@dataclass
class MessageMail:
    uid: str
    expediteur: str
    objet: str
    date: datetime
    pieces_jointes: list[PieceJointe] = field(default_factory=list)


def _est_pdf(partie: Message) -> bool:
    nom = partie.get_filename() or ""
    if nom.lower().endswith(".pdf"):
        return True
    return partie.get_content_type() == "application/pdf"


def construire_message(uid: str, donnees_brutes: bytes) -> MessageMail:
    """Parse les octets bruts (RFC 822) d'un mail et en extrait les pièces
    jointes PDF. Ne filtre jamais par expéditeur : la boîte dédiée recevant
    tout le courrier personnel transféré, le tri se fait manuellement."""
    message = message_from_bytes(donnees_brutes)

    date_brute = message.get("Date")
    try:
        date = parsedate_to_datetime(date_brute) if date_brute else datetime.now()
    except (TypeError, ValueError):
        date = datetime.now()

    pieces_jointes = []
    for partie in message.walk():
        if partie.is_multipart():
            continue
        if not _est_pdf(partie):
            continue
        contenu = partie.get_payload(decode=True)
        if contenu is None:
            continue
        nom = partie.get_filename() or f"document-{uid}.pdf"
        pieces_jointes.append(PieceJointe(nom=nom, contenu=contenu))

    return MessageMail(
        uid=uid,
        expediteur=message.get("From", ""),
        objet=message.get("Subject", ""),
        date=date,
        pieces_jointes=pieces_jointes,
    )


class ErreurConnexionImap(Exception):
    pass


def boite_mail_configuree() -> bool:
    return bool(GMAIL_IMAP_ADRESSE and GMAIL_IMAP_MOT_DE_PASSE)


def nouveau_client_imap() -> "ClientImap":
    return ClientImap(GMAIL_IMAP_HOTE, GMAIL_IMAP_PORT, GMAIL_IMAP_ADRESSE, GMAIL_IMAP_MOT_DE_PASSE, use_ssl=GMAIL_IMAP_SSL)


class ClientImap:
    """Fine enveloppe autour d'imaplib. `use_ssl=False` n'est utilisé que
    pour les tests contre le faux serveur local (tests/faux_serveur_imap.py)."""

    def __init__(self, hote: str, port: int, utilisateur: str, mot_de_passe: str, use_ssl: bool = True):
        self.hote = hote
        self.port = port
        self.utilisateur = utilisateur
        self.mot_de_passe = mot_de_passe
        self.use_ssl = use_ssl
        self._connexion: imaplib.IMAP4 | None = None

    def __enter__(self) -> "ClientImap":
        try:
            self._connexion = (
                imaplib.IMAP4_SSL(self.hote, self.port) if self.use_ssl else imaplib.IMAP4(self.hote, self.port)
            )
            self._connexion.login(self.utilisateur, self.mot_de_passe)
            self._connexion.select("INBOX")
        except (imaplib.IMAP4.error, OSError) as erreur:
            raise ErreurConnexionImap(f"Connexion IMAP impossible : {erreur}") from erreur
        return self

    def __exit__(self, *_exc) -> None:
        if self._connexion is not None:
            try:
                self._connexion.logout()
            except imaplib.IMAP4.error:
                pass

    def lister_uids(self) -> list[str]:
        statut, donnees = self._connexion.uid("search", None, "ALL")
        if statut != "OK" or not donnees or not donnees[0]:
            return []
        return donnees[0].decode().split()

    def recuperer_message(self, uid: str) -> MessageMail:
        statut, donnees = self._connexion.uid("fetch", uid, "(RFC822)")
        if statut != "OK" or not donnees or donnees[0] is None:
            raise ErreurConnexionImap(f"Impossible de récupérer le message {uid}")
        donnees_brutes = donnees[0][1]
        return construire_message(uid, donnees_brutes)
