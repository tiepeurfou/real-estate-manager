from datetime import date

import app.services.notifications as notifications_module
from app.models import Bien, RappelDpeNotifie, UniteLocative
from app.models.enums import DpeLettre, TypeBien
from app.services.dpe import _date_expiration, notifier_dpe_a_renouveler, unites_dpe_a_renouveler
from tests.faux_serveur_ntfy import FauxServeurNtfy


def _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan", dpe_date=None) -> tuple[Bien, UniteLocative]:
    bien = Bien(
        type=TypeBien.IMMEUBLE,
        libelle=libelle_bien,
        adresse_rue="1 rue Test",
        adresse_code_postal="08200",
        adresse_ville="Sedan",
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)
    unite = UniteLocative(bien_id=bien.id, libelle="Appt 1", dpe_lettre=DpeLettre.D if dpe_date else None, dpe_date=dpe_date)
    session.add(unite)
    session.commit()
    session.refresh(unite)
    return bien, unite


def test_date_expiration_ajoute_dix_ans():
    assert _date_expiration(date(2016, 8, 15)) == date(2026, 8, 15)


def test_date_expiration_clampe_le_29_fevrier():
    # 2020 est bissextile, 2030 ne l'est pas.
    assert _date_expiration(date(2020, 2, 29)) == date(2030, 2, 28)


def test_unites_dpe_a_renouveler_dans_la_fenetre(session):
    bien, unite = _creer_bien_avec_unite(session, dpe_date=date(2016, 8, 15))

    resultat = unites_dpe_a_renouveler(session, aujourdhui=date(2026, 6, 1), fenetre_jours=90)

    assert len(resultat) == 1
    assert resultat[0][0].id == unite.id
    assert resultat[0][1] == date(2026, 8, 15)


def test_unites_dpe_a_renouveler_hors_fenetre(session):
    _creer_bien_avec_unite(session, dpe_date=date(2020, 1, 1))

    resultat = unites_dpe_a_renouveler(session, aujourdhui=date(2026, 10, 29), fenetre_jours=90)

    assert resultat == []


def test_unites_dpe_a_renouveler_ignore_les_unites_sans_dpe_date(session):
    _creer_bien_avec_unite(session, dpe_date=None)

    resultat = unites_dpe_a_renouveler(session, aujourdhui=date(2026, 10, 29))

    assert resultat == []


def test_unites_dpe_a_renouveler_inclut_les_dpe_deja_expires(session):
    bien, unite = _creer_bien_avec_unite(session, dpe_date=date(2010, 1, 1))

    resultat = unites_dpe_a_renouveler(session, aujourdhui=date(2026, 10, 29), fenetre_jours=90)

    assert len(resultat) == 1


def test_notifier_dpe_a_renouveler_envoie_et_memorise(session, monkeypatch):
    bien, unite = _creer_bien_avec_unite(session, dpe_date=date(2016, 8, 15))

    with FauxServeurNtfy() as serveur:
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur.url)

        notifiees = notifier_dpe_a_renouveler(session, aujourdhui=date(2026, 6, 1))

    assert len(notifiees) == 1
    assert len(serveur.requetes) == 1
    message = serveur.requetes[0]["json"]["message"]
    assert "Appt 1" in message
    assert "2026-08-15" in message

    from sqlmodel import select

    enregistres = session.exec(select(RappelDpeNotifie)).all()
    assert len(enregistres) == 1
    assert enregistres[0].unite_locative_id == unite.id
    assert enregistres[0].dpe_date == date(2016, 8, 15)


def test_notifier_dpe_a_renouveler_ne_renotifie_pas_la_meme_echeance(session, monkeypatch):
    bien, unite = _creer_bien_avec_unite(session, dpe_date=date(2016, 8, 15))

    with FauxServeurNtfy() as serveur:
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur.url)

        notifier_dpe_a_renouveler(session, aujourdhui=date(2026, 6, 1))
        deuxieme_passage = notifier_dpe_a_renouveler(session, aujourdhui=date(2026, 6, 2))

    assert deuxieme_passage == []
    assert len(serveur.requetes) == 1


def test_notifier_dpe_a_renouveler_renotifie_si_le_dpe_est_renouvele(session, monkeypatch):
    bien, unite = _creer_bien_avec_unite(session, dpe_date=date(2016, 8, 15))

    with FauxServeurNtfy() as serveur:
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur.url)

        notifier_dpe_a_renouveler(session, aujourdhui=date(2026, 6, 1))

        # Le DPE est refait entre-temps : nouvelle dpe_date sur l'unité.
        unite.dpe_date = date(2026, 6, 1)
        session.add(unite)
        session.commit()

        nouvelles = notifier_dpe_a_renouveler(session, aujourdhui=date(2036, 4, 1))

    assert len(nouvelles) == 1
    assert len(serveur.requetes) == 2


def test_notifier_dpe_a_renouveler_echec_d_envoi_n_est_pas_memorise(session, monkeypatch):
    bien, unite = _creer_bien_avec_unite(session, dpe_date=date(2016, 8, 15))

    monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
    monkeypatch.setattr(notifications_module, "NTFY_URL", "http://127.0.0.1:1")

    notifiees = notifier_dpe_a_renouveler(session, aujourdhui=date(2026, 6, 1))

    assert notifiees == []

    from sqlmodel import select

    assert session.exec(select(RappelDpeNotifie)).all() == []
