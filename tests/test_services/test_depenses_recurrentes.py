from datetime import date

from app.models import Bien, DepenseRecurrente, LigneDepense
from app.models.enums import FrequenceDepense, TypeBien
from app.services.depenses_recurrentes import generer_echeances_dues, periodes_dues


def _creer_bien(session, libelle="Immeuble Sedan") -> Bien:
    bien = Bien(
        type=TypeBien.IMMEUBLE,
        libelle=libelle,
        adresse_rue="1 rue Test",
        adresse_code_postal="08200",
        adresse_ville="Sedan",
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)
    return bien


def test_periodes_dues_mensuelle():
    echeances = periodes_dues(date(2024, 1, 15), None, FrequenceDepense.MENSUELLE, date(2024, 4, 15))
    assert echeances == [date(2024, 1, 15), date(2024, 2, 15), date(2024, 3, 15), date(2024, 4, 15)]


def test_periodes_dues_trimestrielle():
    echeances = periodes_dues(date(2024, 1, 1), None, FrequenceDepense.TRIMESTRIELLE, date(2024, 10, 1))
    assert echeances == [date(2024, 1, 1), date(2024, 4, 1), date(2024, 7, 1), date(2024, 10, 1)]


def test_periodes_dues_annuelle():
    echeances = periodes_dues(date(2022, 6, 1), None, FrequenceDepense.ANNUELLE, date(2024, 6, 1))
    assert echeances == [date(2022, 6, 1), date(2023, 6, 1), date(2024, 6, 1)]


def test_periodes_dues_respecte_date_fin():
    echeances = periodes_dues(date(2024, 1, 1), date(2024, 3, 1), FrequenceDepense.MENSUELLE, date(2024, 12, 1))
    assert echeances == [date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1)]


def test_periodes_dues_date_debut_dans_le_futur():
    assert periodes_dues(date(2025, 1, 1), None, FrequenceDepense.MENSUELLE, date(2024, 12, 1)) == []


def test_periodes_dues_aucune_echeance_encore_due_le_jour_meme():
    echeances = periodes_dues(date(2024, 1, 1), None, FrequenceDepense.MENSUELLE, date(2024, 1, 1))
    assert echeances == [date(2024, 1, 1)]


def test_periodes_dues_jour_du_mois_ne_glisse_pas_apres_fevrier():
    # Le 31 janvier doit clamper au 29 février (2024 est bissextile) mais
    # revenir au 31 mars — pas rester bloqué à 28/29 par un chaînage naïf.
    echeances = periodes_dues(date(2024, 1, 31), None, FrequenceDepense.MENSUELLE, date(2024, 4, 30))
    assert echeances == [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31), date(2024, 4, 30)]


def test_periodes_dues_jour_du_mois_ne_glisse_pas_annee_non_bissextile():
    echeances = periodes_dues(date(2023, 1, 31), None, FrequenceDepense.MENSUELLE, date(2023, 4, 30))
    assert echeances == [date(2023, 1, 31), date(2023, 2, 28), date(2023, 3, 31), date(2023, 4, 30)]


def test_generer_echeances_dues_pour_le_bien_entier(session):
    bien = _creer_bien(session)
    template = DepenseRecurrente(
        bien_id=bien.id,
        categorie="Crédit immobilier",
        libelle="Crédit Sedan",
        montant=450.0,
        frequence=FrequenceDepense.MENSUELLE,
        date_debut=date(2024, 1, 5),
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    lignes = generer_echeances_dues(session, aujourdhui=date(2024, 3, 5))
    assert len(lignes) == 3
    assert {l.date for l in lignes} == {date(2024, 1, 5), date(2024, 2, 5), date(2024, 3, 5)}
    for ligne in lignes:
        assert ligne.depense_recurrente_id == template.id
        assert ligne.bien_id == bien.id
        assert ligne.unite_locative_id is None
        assert ligne.montant == 450.0
        assert ligne.categorie == "Crédit immobilier"


def test_generer_echeances_dues_est_idempotent(session):
    bien = _creer_bien(session)
    template = DepenseRecurrente(
        bien_id=bien.id,
        categorie="Crédit immobilier",
        libelle="Crédit Sedan",
        montant=450.0,
        frequence=FrequenceDepense.MENSUELLE,
        date_debut=date(2024, 1, 5),
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    premiere_passe = generer_echeances_dues(session, aujourdhui=date(2024, 3, 5))
    assert len(premiere_passe) == 3

    deuxieme_passe = generer_echeances_dues(session, aujourdhui=date(2024, 3, 5))
    assert deuxieme_passe == []

    from sqlmodel import select

    toutes_les_lignes = session.exec(
        select(LigneDepense).where(LigneDepense.depense_recurrente_id == template.id)
    ).all()
    assert len(toutes_les_lignes) == 3


def test_generer_echeances_dues_genere_les_nouvelles_sans_dupliquer_les_anciennes(session):
    bien = _creer_bien(session)
    template = DepenseRecurrente(
        bien_id=bien.id,
        categorie="Crédit immobilier",
        libelle="Crédit Sedan",
        montant=450.0,
        frequence=FrequenceDepense.MENSUELLE,
        date_debut=date(2024, 1, 5),
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    generer_echeances_dues(session, aujourdhui=date(2024, 2, 5))
    nouvelles = generer_echeances_dues(session, aujourdhui=date(2024, 4, 5))

    assert {l.date for l in nouvelles} == {date(2024, 3, 5), date(2024, 4, 5)}


def test_generer_echeances_dues_pour_une_seule_unite(session):
    from app.models import UniteLocative

    bien = _creer_bien(session)
    unite = UniteLocative(bien_id=bien.id, libelle="Appt 1")
    session.add(unite)
    session.commit()
    session.refresh(unite)

    template = DepenseRecurrente(
        bien_id=bien.id,
        unite_locative_id=unite.id,
        categorie="Charges de copropriété",
        libelle="Charges",
        montant=80.0,
        frequence=FrequenceDepense.TRIMESTRIELLE,
        date_debut=date(2024, 1, 1),
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    lignes = generer_echeances_dues(session, aujourdhui=date(2024, 1, 1))
    assert len(lignes) == 1
    assert lignes[0].unite_locative_id == unite.id
    assert lignes[0].bien_id is None


def test_generer_echeances_dues_respecte_la_date_fin(session):
    bien = _creer_bien(session)
    template = DepenseRecurrente(
        bien_id=bien.id,
        categorie="Crédit immobilier",
        libelle="Crédit Sedan",
        montant=450.0,
        frequence=FrequenceDepense.MENSUELLE,
        date_debut=date(2024, 1, 5),
        date_fin=date(2024, 2, 5),
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    lignes = generer_echeances_dues(session, aujourdhui=date(2024, 12, 5))
    assert {l.date for l in lignes} == {date(2024, 1, 5), date(2024, 2, 5)}
