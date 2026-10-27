import pytest

from app.security import verify_password
from app.services.gestion_utilisateurs import creer_utilisateur


def test_creer_utilisateur_hash_le_mot_de_passe(session):
    utilisateur = creer_utilisateur(session, "nouveau@exemple.fr", "motdepasse123")

    assert utilisateur.mot_de_passe_hash != "motdepasse123"
    assert verify_password("motdepasse123", utilisateur.mot_de_passe_hash)


def test_creer_utilisateur_refuse_un_email_duplique(session):
    creer_utilisateur(session, "double@exemple.fr", "motdepasse123")

    with pytest.raises(ValueError):
        creer_utilisateur(session, "double@exemple.fr", "autremotdepasse")
