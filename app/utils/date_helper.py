"""
Utilitários para manipulação de datas em pt-BR.
"""

from datetime import date, datetime, timedelta
import re


MESES_PT = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
    "abril": 4, "maio": 5, "junho": 6, "julho": 7,
    "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}

MESES_NOME = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


def parse_date_pt(text: str) -> date | None:
    """
    Tenta parsear uma data em diversos formatos pt-BR.
    Exemplos: 'hoje', 'ontem', '13/02/2026', 'fevereiro 2026'
    """
    text = text.strip().lower()
    today = date.today()

    if text in ("hoje", "today"):
        return today
    if text in ("ontem", "yesterday"):
        return today - timedelta(days=1)
    if text in ("anteontem",):
        return today - timedelta(days=2)

    # DD/MM/YYYY
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", text)
    if match:
        d, m, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            return date(y, m, d)
        except ValueError:
            return None

    # DD/MM
    match = re.match(r"^(\d{1,2})/(\d{1,2})$", text)
    if match:
        d, m = int(match.group(1)), int(match.group(2))
        try:
            return date(today.year, m, d)
        except ValueError:
            return None

    # YYYY-MM-DD
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
    if match:
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None

    return None


def format_date_pt(d: date) -> str:
    """Formata data em pt-BR: 13 de Fevereiro de 2026."""
    return f"{d.day} de {MESES_NOME[d.month]} de {d.year}"


def format_date_short(d: date) -> str:
    """Formata data curta: 13/02/2026."""
    return d.strftime("%d/%m/%Y")


def get_month_name(month: int) -> str:
    """Retorna nome do mês em português."""
    return MESES_NOME.get(month, "")
