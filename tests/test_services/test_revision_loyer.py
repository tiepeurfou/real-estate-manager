from datetime import date

import app.services.notifications as notifications_module
from app.models import Bien, Locataire, Occupation, OccupationLocataire, RappelRevisionLoyerNotifie, UniteLocative
from app.models.enums import StatutOccupation, TypeBien
from app.services.revision_loyer import _anniversaire, _prochaine_echeance, notifier_revisions_a_venir, occupations_a_reviser
from tests.faux_serveur_ntfy import FauxServeurNtfy


def _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan") -> tuple[Bien, UniteLocative]:
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
    unite = UniteLocative(bien_id=bien.id, libelle="Appt 1")
    session.add(unite)
    session.commit()
    session.refresh(unite)
    return bien, unite


def _creer_locataire(session, nom="Dupont", prenom="Jean") -> Locataire:
    locataire = Locataire(nom=nom, prenom=prenom)
    session.add(locataire)
    session.commit()
    session.refresh(locataire)
    return locataire


def _attribuer(session, unite_id, locataire_ids, date_entree, statut=StatutOccupation.ACTIVE, loyer=500) -> Occupation:
    occupation = Occupation(unite_locative_id=unite_id, date_entree=date_entree, loyer_mensuel_hc=loyer, statut=statut)
    session.add(occupation)
    session.commit()
    session.refresh(occupation)
    for locataire_id in locataire_ids:
        session.add(OccupationLocataire(occupation_id=occupation.id, locataire_id=locataire_id))
    session.commit()
    return occupation


def test_anniversaire_clampe_le_jour_pour_les_mois_courts():
    # Entrée un 30 janvier → le mois de l'anniversaire (janvier) a toujours
    # 31 jours, donc aucun clamping ; testons plutôt un cas où le mois
    # anniversaire est février (28/29 jours selon bissextilité).
    assert _anniversaire(date(2020, 2, 29), 2025) == date(2025, 2, 28)
    assert _anniversaire(date(2020, 2, 29), 2024) == date(2024, 2, 29)  # bissextile


def test_prochaine_echeance_avant_l_anniversaire_de_cette_annee():
    echeance, annee = _prochaine_echeance(date(2020, 3, 15), date(2026, 2, 20))
    assert echeance == date(2026, 3, 15)
    assert annee == 2026


def test_prochaine_echeance_apres_l_anniversaire_de_cette_annee():
    echeance, annee = _prochaine_echeance(date(2020, 3, 15), date(2026, 3, 16))
    assert echeance == date(2027, 3, 15)
    assert annee == 2027


def test_prochaine_echeance_le_jour_meme_de_l_anniversaire():
    echeance, annee = _prochaine_echeance(date(2020, 3, 15), date(2026, 3, 15))
    assert echeance == date(2026, 3, 15)
    assert annee == 2026


def test_prochaine_echeance_le_jour_de_signature_exclut_l_annee_de_signature():
    echeance, annee = _prochaine_echeance(date(2020, 3, 15), date(2020, 3, 15))
    assert echeance == date(2021, 3, 15)
    assert annee == 2021


def test_occupations_a_reviser_dans_la_fenetre(session):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)
    _attribuer(session, unite.id, [locataire.id], date_entree=date(2024, 11, 20))

    resultat = occupations_a_reviser(session, aujourdhui=date(2026, 10, 29), fenetre_jours=30)

    assert len(resultat) == 1


def test_occupations_a_reviser_hors_fenetre(session):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)
    _attribuer(session, unite.id, [locataire.id], date_entree=date(2024, 6, 1))

    resultat = occupations_a_reviser(session, aujourdhui=date(2026, 10, 29), fenetre_jours=30)

    assert resultat == []


def test_occupations_a_reviser_ignore_les_occupations_terminees(session):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)
    _attribuer(session, unite.id, [locataire.id], date_entree=date(2024, 11, 20), statut=StatutOccupation.TERMINEE)

    resultat = occupations_a_reviser(session, aujourdhui=date(2026, 10, 29), fenetre_jours=30)

    assert resultat == []


def test_notifier_revisions_a_venir_envoie_et_memorise(session, monkeypatch):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)
    occupation = _attribuer(session, unite.id, [locataire.id], date_entree=date(2024, 11, 20), loyer=500)

    with FauxServeurNtfy() as serveur:
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur.url)

        notifiees = notifier_revisions_a_venir(session, aujourdhui=date(2026, 10, 29))

    assert len(notifiees) == 1
    assert len(serveur.requetes) == 1
    message = serveur.requetes[0]["json"]["message"]
    assert "Dupont" in message
    assert "500" in message

    from sqlmodel import select

    enregistres = session.exec(select(RappelRevisionLoyerNotifie)).all()
    assert len(enregistres) == 1
    assert enregistres[0].occupation_id == occupation.id
    assert enregistres[0].annee_echeance == 2026


def test_notifier_revisions_a_venir_ne_renotifie_pas_la_meme_echeance(session, monkeypatch):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)
    _attribuer(session, unite.id, [locataire.id], date_entree=date(2024, 11, 20))

    with FauxServeurNtfy() as serveur:
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur.url)

        notifier_revisions_a_venir(session, aujourdhui=date(2026, 10, 29))
        deuxieme_passage = notifier_revisions_a_venir(session, aujourdhui=date(2026, 10, 30))

    assert deuxieme_passage == []
    assert len(serveur.requetes) == 1


def test_notifier_revisions_a_venir_renotifie_l_annee_suivante(session, monkeypatch):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)
    _attribuer(session, unite.id, [locataire.id], date_entree=date(2024, 11, 20))

    with FauxServeurNtfy() as serveur:
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur.url)

        notifier_revisions_a_venir(session, aujourdhui=date(2026, 10, 29))
        annee_suivante = notifier_revisions_a_venir(session, aujourdhui=date(2027, 10, 25))

    assert len(annee_suivante) == 1
    assert len(serveur.requetes) == 2


def test_notifier_revisions_a_venir_echec_d_envoi_n_est_pas_memorise(session, monkeypatch):
    bien, unite = _creer_bien_avec_unite(session)
    locataire = _creer_locataire(session)
    _attribuer(session, unite.id, [locataire.id], date_entree=date(2024, 11, 20))

    monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
    monkeypatch.setattr(notifications_module, "NTFY_URL", "http://127.0.0.1:1")

    notifiees = notifier_revisions_a_venir(session, aujourdhui=date(2026, 10, 29))

    assert notifiees == []

    from sqlmodel import select

    assert session.exec(select(RappelRevisionLoyerNotifie)).all() == []


def test_notifier_revisions_a_venir_colocation_liste_tous_les_noms(session, monkeypatch):
    bien, unite = _creer_bien_avec_unite(session)
    locataire1 = _creer_locataire(session, nom="Dupont", prenom="Jean")
    locataire2 = _creer_locataire(session, nom="Martin", prenom="Alice")
    _attribuer(session, unite.id, [locataire1.id, locataire2.id], date_entree=date(2024, 11, 20))

    with FauxServeurNtfy() as serveur:
        monkeypatch.setattr(notifications_module, "NTFY_TOPIC", "mon-topic")
        monkeypatch.setattr(notifications_module, "NTFY_URL", serveur.url)

        notifier_revisions_a_venir(session, aujourdhui=date(2026, 10, 29))

    message = serveur.requetes[0]["json"]["message"]
    assert "Dupont" in message
    assert "Martin" in message
