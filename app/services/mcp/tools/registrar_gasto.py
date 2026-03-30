"""Tool: Registrar gasto/despesa."""

from datetime import date, datetime
from app.services.finance.transaction_service import TransactionService
from app.models.transaction import TransactionType


async def registrar_gasto(
    user_id: str,
    valor: float,
    categoria: str = "Outros",
    descricao: str = None,
    data: str = None,
    perfil: str = None,
) -> str:
    """Registra um gasto (saída) do usuário."""
    service = TransactionService()

    tx_date = date.today()
    if data:
        try:
            tx_date = datetime.strptime(data, "%Y-%m-%d").date()
        except ValueError:
            return "❌ Data inválida. Use o formato YYYY-MM-DD."

    if valor <= 0:
        return "❌ O valor precisa ser maior que zero."

    if perfil and perfil.upper() not in ("PF", "PJ"):
        return "❌ Perfil inválido. Use 'PF' ou 'PJ'."

    transaction = await service.create(
        user_id=user_id,
        tx_type=TransactionType.EXPENSE,
        amount=valor,
        description=descricao,
        category_name=categoria,
        tx_date=tx_date,
        profile=perfil.upper() if perfil else None,
    )

    cat_name = transaction.get("category_name", categoria)
    cat_emoji = transaction.get("category_emoji", "📦")
    profile_label = "🏢 PJ" if transaction.get("profile") == "PJ" else "👤 PF"

    return (
        f"✅ Gasto registrado!"
        f" [{profile_label}]\n"
        f"{cat_emoji} {cat_name}\n"
        f"💲 R$ {valor:,.2f}\n"
        f"📅 {tx_date.strftime('%d/%m/%Y')}"
        + (f"\n📝 {descricao}" if descricao else "")
    )
