from datetime import date

from app.services.periodes import derniers_mois


def test_derniers_mois_sans_changement_annee():
    assert derniers_mois(date(2024, 9, 15), 3) == [date(2024, 7, 1), date(2024, 8, 1), date(2024, 9, 1)]


def test_derniers_mois_avec_changement_annee():
    assert derniers_mois(date(2024, 2, 10), 3) == [date(2023, 12, 1), date(2024, 1, 1), date(2024, 2, 1)]


def test_derniers_mois_un_seul_mois():
    assert derniers_mois(date(2024, 5, 1), 1) == [date(2024, 5, 1)]
