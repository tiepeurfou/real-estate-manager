from sqlmodel import Session, select

from app.models import Utilisateur
from app.security import hash_password


def creer_utilisateur(session: Session, email: str, password: str) -> Utilisateur:
    existant = session.exec(select(Utilisateur).where(Utilisateur.email == email)).first()
    if existant is not None:
        raise ValueError(f"Un utilisateur existe déjà avec l'email {email}")

    utilisateur = Utilisateur(email=email, mot_de_passe_hash=hash_password(password))
    session.add(utilisateur)
    session.commit()
    session.refresh(utilisateur)
    return utilisateur
