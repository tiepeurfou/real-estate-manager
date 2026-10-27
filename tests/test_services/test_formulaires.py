from datetime import date

import pytest

from app.services.formulaires import (
    parser_date_optionnelle,
    parser_float_optionnel,
    parser_int_optionnel,
)


@pytest.mark.parametrize("valeur", [None, ""])
def test_parser_date_optionnelle_vide_renvoie_none(valeur):
    assert parser_date_optionnelle(valeur) is None


def test_parser_date_optionnelle_valide():
    assert parser_date_optionnelle("2024-02-01") == date(2024, 2, 1)


def test_parser_date_optionnelle_invalide_leve_value_error():
    with pytest.raises(ValueError):
        parser_date_optionnelle("pas-une-date")


@pytest.mark.parametrize("valeur", [None, ""])
def test_parser_float_optionnel_vide_renvoie_none(valeur):
    assert parser_float_optionnel(valeur) is None


def test_parser_float_optionnel_valide():
    assert parser_float_optionnel("42.5") == 42.5


def test_parser_float_optionnel_invalide_leve_value_error():
    with pytest.raises(ValueError):
        parser_float_optionnel("abc")


@pytest.mark.parametrize("valeur", [None, ""])
def test_parser_int_optionnel_vide_renvoie_none(valeur):
    assert parser_int_optionnel(valeur) is None


def test_parser_int_optionnel_valide():
    assert parser_int_optionnel("3") == 3


def test_parser_int_optionnel_invalide_leve_value_error():
    with pytest.raises(ValueError):
        parser_int_optionnel("trois")
