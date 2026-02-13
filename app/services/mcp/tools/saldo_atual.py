"""Tool: Saldo atual."""

from app.services.finance.report_service import ReportService


async def saldo_atual(user_id: str) -> str:
    """Retorna o saldo atual (entradas - saídas)."""
    service = ReportService()
    balance = await service.get_balance(user_id)

    income = balance["total_income"]
    expense = balance["total_expense"]
    saldo = balance["balance"]

    emoji = "📈" if saldo >= 0 else "📉"
    saldo_emoji = "💰" if saldo >= 0 else "⚠️"

    return (
        f"{emoji} *Seu Saldo Atual*\n\n"
        f"🟢 Total de Entradas: R$ {income:,.2f}\n"
        f"🔴 Total de Saídas: R$ {expense:,.2f}\n"
        f"{saldo_emoji} Saldo: R$ {saldo:,.2f}"
    )
