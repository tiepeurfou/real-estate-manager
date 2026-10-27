from sqlmodel import Session

from app.models import Utilisateur


def test_page_de_connexion_accessible(client):
    reponse = client.get("/login")
    assert reponse.status_code == 200
    assert "Connexion" in reponse.text


def test_connexion_reussie_redirige_vers_accueil(client, utilisateur_test):
    reponse = client.post(
        "/login",
        data={"email": "test@exemple.fr", "password": "motdepasse123"},
        follow_redirects=False,
    )
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/")


def test_session_permet_d_acceder_a_l_accueil(client, utilisateur_test):
    client.post("/login", data={"email": "test@exemple.fr", "password": "motdepasse123"})
    reponse = client.get("/")
    assert reponse.status_code == 200
    assert "test@exemple.fr" in reponse.text


def test_connexion_echoue_avec_mauvais_mot_de_passe(client, utilisateur_test):
    reponse = client.post(
        "/login",
        data={"email": "test@exemple.fr", "password": "mauvais-mot-de-passe"},
    )
    assert reponse.status_code == 401
    assert "incorrect" in reponse.text


def test_connexion_echoue_avec_email_inconnu(client, utilisateur_test):
    reponse = client.post(
        "/login",
        data={"email": "inconnu@exemple.fr", "password": "motdepasse123"},
    )
    assert reponse.status_code == 401


def test_acces_a_l_accueil_sans_session_redirige_vers_connexion(client):
    reponse = client.get("/", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")

    reponse_suivie = client.get("/")
    assert "Connexion" in reponse_suivie.text


def test_deconnexion_efface_la_session(client, utilisateur_test):
    client.post("/login", data={"email": "test@exemple.fr", "password": "motdepasse123"})
    assert client.get("/").status_code == 200

    client.get("/logout")

    reponse = client.get("/", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_connexion_met_a_jour_la_derniere_connexion(client, utilisateur_test, engine):
    client.post("/login", data={"email": "test@exemple.fr", "password": "motdepasse123"})

    with Session(engine) as s:
        utilisateur = s.get(Utilisateur, utilisateur_test.id)
        assert utilisateur.derniere_connexion is not None
