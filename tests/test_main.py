from starlette.testclient import TestClient

from app.main import app_prefixee


def test_app_prefixee_demarre_et_arrete_le_scheduler_sans_planter():
    # GMAIL_IMAP_ADRESSE/MOT_DE_PASSE sont vides par défaut dans les tests
    # (fixture autouse de conftest.py) : le scheduler démarre bel et bien
    # (lifespan de app_prefixee, voir app/main.py) mais son premier scan ne
    # tente aucune connexion réseau — on vérifie juste que le cycle
    # démarrage/requête/arrêt se fait sans exception.
    with TestClient(app_prefixee) as client:
        reponse = client.get("/real-estate-manager/login")
        assert reponse.status_code == 200
