from datetime import date


def parser_date_optionnelle(valeur: str | None) -> date | None:
    if not valeur:
        return None
    return date.fromisoformat(valeur)


def parser_float_optionnel(valeur: str | None) -> float | None:
    if not valeur:
        return None
    return float(valeur)


def parser_int_optionnel(valeur: str | None) -> int | None:
    if not valeur:
        return None
    return int(valeur)
