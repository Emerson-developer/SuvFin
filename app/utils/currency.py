"""
Utilitários de formatação monetária (BRL).
"""

import re


def format_brl(value: float) -> str:
    """Formata valor como moeda brasileira: R$ 1.234,56"""
    if value < 0:
        return f"-R$ {abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_brl(text: str) -> float | None:
    """
    Tenta extrair um valor monetário de um texto em português.
    Exemplos: 'R$ 1.234,56', '1234.56', '45 reais', '45,90'
    """
    text = text.strip()

    # Remover "R$" e espaços
    text = re.sub(r"R\$\s*", "", text)
    text = re.sub(r"\s*(reais|real)\s*", "", text, flags=re.IGNORECASE)

    # Formato BR: 1.234,56
    match = re.match(r"^[\d.]+,\d{2}$", text)
    if match:
        cleaned = text.replace(".", "").replace(",", ".")
        return float(cleaned)

    # Formato US/direto: 1234.56
    match = re.match(r"^\d+\.?\d*$", text)
    if match:
        return float(text)

    # Apenas números
    match = re.match(r"^\d+$", text)
    if match:
        return float(text)

    return None
