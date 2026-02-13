"""
Testes para utilitários.
"""

from app.utils.currency import format_brl, parse_brl
from app.utils.date_helper import parse_date_pt, format_date_short


def test_format_brl():
    assert format_brl(1234.56) == "R$ 1.234,56"
    assert format_brl(0) == "R$ 0,00"
    assert format_brl(45) == "R$ 45,00"


def test_parse_brl():
    assert parse_brl("45") == 45.0
    assert parse_brl("1.234,56") == 1234.56
    assert parse_brl("R$ 89,90") == 89.90
    assert parse_brl("50 reais") == 50.0
    assert parse_brl("abc") is None


def test_parse_date_pt():
    from datetime import date, timedelta

    assert parse_date_pt("hoje") == date.today()
    assert parse_date_pt("ontem") == date.today() - timedelta(days=1)
    assert parse_date_pt("13/02/2026") == date(2026, 2, 13)
    assert parse_date_pt("2026-02-13") == date(2026, 2, 13)


def test_format_date_short():
    from datetime import date
    assert format_date_short(date(2026, 2, 13)) == "13/02/2026"
