"""Tool: Últimos lançamentos."""

from app.services.finance.transaction_service import TransactionService


async def ultimos_lancamentos(
    user_id: str,
    quantidade: int = 5,
    tipo: str = None,
) -> str:
    """Lista os últimos lançamentos do usuário."""
    service = TransactionService()

    transactions = await service.get_recent(
        user_id, limit=quantidade, tx_type=tipo
    )

    if not transactions:
        return "📋 Nenhum lançamento encontrado."

    tipo_emoji = {"INCOME": "🟢", "EXPENSE": "🔴"}

    lines = [f"📋 *Últimos {len(transactions)} lançamentos:*\n"]
    for i, tx in enumerate(transactions, 1):
        emoji = tipo_emoji.get(tx["type"], "⚪")
        cat_emoji = tx.get("category_emoji", "📦")
        sign = "+" if tx["type"] == "INCOME" else "-"
        lines.append(
            f"{i}. {emoji} {sign}R$ {tx['amount']:,.2f} — "
            f"{cat_emoji} {tx.get('category_name', 'Sem cat.')}\n"
            f"   📝 {tx['description'] or 'Sem descrição'} | "
            f"📅 {tx['date'].strftime('%d/%m/%Y')}"
        )

    return "\n".join(lines)
