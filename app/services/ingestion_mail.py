from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import CandidatCourrielNotifie, CandidatCourrielTraite
from app.models.enums import StatutCandidatCourriel
from app.services.mail import ClientImap, MessageMail
from app.services.notifications import ErreurNotification, envoyer_notification


@dataclass
class CandidatCourriel:
    message_uid: str
    nom_piece_jointe: str
    expediteur: str
    objet: str
    date: datetime


def _dejas_traites(session: Session) -> set[tuple[str, str]]:
    traites = session.exec(select(CandidatCourrielTraite)).all()
    return {(t.message_uid, t.nom_piece_jointe) for t in traites}


def lister_candidats(client: ClientImap, session: Session) -> list[CandidatCourriel]:
    """Liste les pièces jointes PDF des mails de la boîte pas encore
    triées (ni importées, ni écartées). Aucun filtre par expéditeur :
    la boîte recevant tout le courrier personnel transféré, le tri est
    manuel — voir app/services/mail.py."""
    deja_traites = _dejas_traites(session)
    candidats: list[CandidatCourriel] = []

    for uid in client.lister_uids():
        message: MessageMail = client.recuperer_message(uid)
        for piece in message.pieces_jointes:
            if (uid, piece.nom) in deja_traites:
                continue
            candidats.append(
                CandidatCourriel(
                    message_uid=uid,
                    nom_piece_jointe=piece.nom,
                    expediteur=message.expediteur,
                    objet=message.objet,
                    date=message.date,
                )
            )

    return candidats


def recuperer_piece_jointe(client: ClientImap, message_uid: str, nom_piece_jointe: str) -> bytes:
    message = client.recuperer_message(message_uid)
    for piece in message.pieces_jointes:
        if piece.nom == nom_piece_jointe:
            return piece.contenu
    raise ValueError(f"Pièce jointe « {nom_piece_jointe} » introuvable dans le message {message_uid}")


def _deja_notifies(session: Session) -> set[tuple[str, str]]:
    notifies = session.exec(select(CandidatCourrielNotifie)).all()
    return {(n.message_uid, n.nom_piece_jointe) for n in notifies}


def notifier_nouveaux_candidats(client: ClientImap, session: Session) -> list[CandidatCourriel]:
    """Envoie une notification push pour chaque candidat jamais notifié
    auparavant (ni traité, ni déjà notifié à un scan précédent), et
    mémorise l'envoi pour ne pas re-notifier au prochain scan tant qu'il
    n'est pas trié par l'utilisateur sur /ingestion-mail. Appelé par le
    scan automatique périodique (app/services/scheduler.py). Si l'envoi
    échoue pour un candidat (ex. pas de réseau), il n'est pas marqué
    notifié — on retentera au prochain scan plutôt que de le perdre."""
    candidats = lister_candidats(client, session)
    deja_notifies = _deja_notifies(session)
    nouveaux = [c for c in candidats if (c.message_uid, c.nom_piece_jointe) not in deja_notifies]

    for candidat in nouveaux:
        try:
            envoyer_notification(
                titre="Nouveau compte-rendu reçu",
                message=f"{candidat.nom_piece_jointe} — de {candidat.expediteur} — à trier dans l'app",
            )
        except ErreurNotification:
            continue
        session.add(
            CandidatCourrielNotifie(
                message_uid=candidat.message_uid,
                nom_piece_jointe=candidat.nom_piece_jointe,
                date_notification=datetime.now(timezone.utc),
            )
        )
    session.commit()
    return nouveaux


def marquer_traite(
    session: Session,
    message_uid: str,
    nom_piece_jointe: str,
    statut: StatutCandidatCourriel,
    releve_gestion_id: int | None = None,
) -> CandidatCourrielTraite:
    candidat = CandidatCourrielTraite(
        message_uid=message_uid,
        nom_piece_jointe=nom_piece_jointe,
        statut=statut,
        date_traitement=datetime.now(timezone.utc),
        releve_gestion_id=releve_gestion_id,
    )
    session.add(candidat)
    session.commit()
    session.refresh(candidat)
    return candidat
