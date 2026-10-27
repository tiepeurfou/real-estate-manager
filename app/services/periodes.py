from datetime import date


def derniers_mois(date_reference: date, nb_mois: int) -> list[date]:
    """Renvoie les nb_mois derniers mois (premier jour de chaque mois),
    du plus ancien au plus récent, nb_mois inclus en comptant date_reference."""
    mois = []
    annee, mois_num = date_reference.year, date_reference.month
    for _ in range(nb_mois):
        mois.append(date(annee, mois_num, 1))
        mois_num -= 1
        if mois_num == 0:
            mois_num = 12
            annee -= 1
    mois.reverse()
    return mois
