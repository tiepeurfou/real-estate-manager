from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import CandidatCourrielTraite
from app.models.enums import StatutCandidatCourriel
from app.services.mail import ClientImap, MessageMail


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
