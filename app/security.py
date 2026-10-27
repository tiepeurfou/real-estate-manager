from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash
from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from app.database import get_session
from app.models import Utilisateur

SESSION_USER_KEY = "user_id"

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


def get_current_user(request: Request, session: Session = Depends(get_session)) -> Utilisateur:
    user_id = request.session.get(SESSION_USER_KEY)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentification requise")

    user = session.get(Utilisateur, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentification requise")

    return user
