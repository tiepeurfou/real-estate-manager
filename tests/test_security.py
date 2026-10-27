from app.security import hash_password, verify_password


def test_hash_password_ne_stocke_pas_le_mot_de_passe_en_clair():
    assert hash_password("motdepasse123") != "motdepasse123"


def test_verify_password_accepte_le_bon_mot_de_passe():
    hash_ = hash_password("motdepasse123")
    assert verify_password("motdepasse123", hash_) is True


def test_verify_password_refuse_un_mauvais_mot_de_passe():
    hash_ = hash_password("motdepasse123")
    assert verify_password("autre-mot-de-passe", hash_) is False


def test_verify_password_refuse_un_hash_invalide():
    assert verify_password("motdepasse123", "pas-un-hash-valide") is False
