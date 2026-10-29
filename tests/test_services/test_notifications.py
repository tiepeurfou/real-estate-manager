import pytest

import app.services.notifications as notifications_module
from app.services.notifications import ErreurNotification, envoyer_notification, notifications_configurees
from tests.faux_serveur_ntfy import FauxServeurNtfy


def test_notifications_configurees_faux_si_pas_de_topic(monkeypatch):
    monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "")
    assert notifications_configurees() is False


def test_notifications_configurees_vrai_si_topic_present(monkeypatch):
    monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
    assert notifications_configurees() is True


def test_envoyer_notification_ne_fait_rien_si_pas_configuree(monkeypatch):
    monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "")
    # Ne doit lever aucune exception, même sans serveur du tout à l'adresse configurée.
    monkeypatch.setattr(notifications_module, "NTFY_URL", "http://127.0.0.1:1")
    envoyer_notification("Titre", "Message")


def test_envoyer_notification_poste_le_bon_contenu_json(monkeypatch):
    with FauxServeurNtfy() as serveur:
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic-secret")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur.url)

        envoyer_notification("Nouveau compte-rendu reçu", "arthurimmo.pdf — à trier", priorite=4)

    assert len(serveur.requetes) == 1
    requete = serveur.requetes[0]
    assert requete["content_type"] == "application/json"
    assert requete["json"] == {
        "topic": "mon-topic-secret",
        "title": "Nouveau compte-rendu reçu",
        "message": "arthurimmo.pdf — à trier",
        "priority": 4,
    }


def test_envoyer_notification_supporte_les_accents(monkeypatch):
    # Le JSON est encodé en UTF-8 sans la limitation ISO-8859-1 des en-têtes
    # HTTP classiques : les accents français doivent passer sans souci.
    with FauxServeurNtfy() as serveur:
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur.url)

        envoyer_notification("Compte-rendu reçu", "Déjà trié dans l'écran dédié")

    assert serveur.requetes[0]["json"]["message"] == "Déjà trié dans l'écran dédié"


def test_envoyer_notification_leve_si_serveur_inaccessible(monkeypatch):
    monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
    monkeypatch.setattr(notifications_module, "NTFY_URL", "http://127.0.0.1:1")

    with pytest.raises(ErreurNotification):
        envoyer_notification("Titre", "Message")
