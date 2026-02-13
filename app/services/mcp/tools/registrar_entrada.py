"""Tool: Registrar entrada/receita."""

from datetime import date, datetime
from app.services.finance.transaction_service import TransactionService
from app.models.transaction import TransactionType


async def registrar_entrada(
    user_id: str,
    valor: float,
    categoria: str = "Salário",
    descricao: str = None,
    data: str = None,
) -> str:
    """Registra uma entrada (receita) do usuário."""
    service = TransactionService()

    tx_date = date.today()
    if data:
        try:
            tx_date = datetime.strptime(data, "%Y-%m-%d").date()
        except ValueError:
            return "❌ Data inválida. Use o formato YYYY-MM-DD."

    if valor <= 0:
        return "❌ O valor precisa ser maior que zero."

    transaction = await service.create(
        user_id=user_id,
        tx_type=TransactionType.INCOME,
        amount=valor,
        description=descricao,
        category_name=categoria,
        tx_date=tx_date,
    )

    cat_name = transaction.get("category_name", categoria)
    cat_emoji = transaction.get("category_emoji", "💼")

    return (
        f"✅ Entrada registrada!\n"
        f"{cat_emoji} {cat_name}\n"
        f"💲 R$ {valor:,.2f}\n"
        f"📅 {tx_date.strftime('%d/%m/%Y')}"
        + (f"\n📝 {descricao}" if descricao else "")
    )
