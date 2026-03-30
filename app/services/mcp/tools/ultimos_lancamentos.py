"""Tool: Últimos lançamentos."""

from app.services.finance.transaction_service import TransactionService


async def ultimos_lancamentos(
    user_id: str,
    quantidade: int = 5,
    tipo: str = None,
    perfil: str = None,
) -> str:
    """Lista os últimos lançamentos do usuário."""
    service = TransactionService()

    if perfil and perfil.upper() not in ("PF", "PJ"):
        return "❌ Perfil inválido. Use 'PF' ou 'PJ'."

    transactions = await service.get_recent(
        user_id, limit=quantidade, tx_type=tipo,
        profile=perfil.upper() if perfil else None,
    )

    if not transactions:
        return "📋 Nenhum lançamento encontrado."

    tipo_emoji = {"INCOME": "🟢", "EXPENSE": "🔴"}
    profile_emoji = {"PF": "👤", "PJ": "🏢"}

    perfil_label = f" | Perfil: {perfil.upper()}" if perfil else ""
    lines = [f"📋 *Últimos {len(transactions)} lançamentos{perfil_label}:*\n"]
    for i, tx in enumerate(transactions, 1):
        emoji = tipo_emoji.get(tx["type"], "⚪")
        cat_emoji = tx.get("category_emoji", "📦")
        sign = "+" if tx["type"] == "INCOME" else "-"
        prof = profile_emoji.get(tx.get("profile", "PF"), "👤")
        lines.append(
            f"{i}. {emoji} {sign}R$ {tx['amount']:,.2f} — "
            f"{cat_emoji} {tx.get('category_name', 'Sem cat.')} {prof}\n"
            f"   📝 {tx['description'] or 'Sem descrição'} | "
            f"📅 {tx['date'].strftime('%d/%m/%Y')}"
        )

    return "\n".join(lines)
