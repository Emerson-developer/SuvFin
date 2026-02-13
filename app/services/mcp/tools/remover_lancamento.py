"""Tool: Remover lançamento."""

from app.services.finance.transaction_service import TransactionService


async def remover_lancamento(
    user_id: str,
    lancamento_id: str = None,
    busca: str = None,
    confirmar: bool = False,
) -> str:
    """Remove um lançamento do usuário (soft delete)."""
    service = TransactionService()

    # Se tem ID direto e confirmação → excluir
    if lancamento_id and confirmar:
        transaction = await service.get_by_id(lancamento_id, user_id)
        if not transaction:
            return "❌ Lançamento não encontrado."

        await service.soft_delete(lancamento_id, user_id)
        return (
            f"🗑️ Lançamento removido com sucesso!\n"
            f"• {transaction['description'] or 'Sem descrição'} — "
            f"R$ {transaction['amount']:,.2f}\n"
            f"• Data: {transaction['date'].strftime('%d/%m/%Y')}\n"
            f"• Categoria: {transaction['category_name'] or 'Sem categoria'}"
        )

    # Se tem ID mas sem confirmação → pedir confirmação
    if lancamento_id and not confirmar:
        transaction = await service.get_by_id(lancamento_id, user_id)
        if not transaction:
            return "❌ Lançamento não encontrado."

        return (
            f"⚠️ Deseja realmente excluir este lançamento?\n\n"
            f"🆔 ID: {transaction['id']}\n"
            f"• {transaction['description'] or 'Sem descrição'} — "
            f"R$ {transaction['amount']:,.2f}\n"
            f"• Data: {transaction['date'].strftime('%d/%m/%Y')}\n"
            f"• Categoria: {transaction['category_name'] or 'Sem categoria'}\n\n"
            f"Responda 'Sim' para confirmar a exclusão."
        )

    # Se tem busca textual → procurar candidatos
    if busca:
        candidates = await service.search(user_id, busca, limit=5)
        if not candidates:
            return "❌ Nenhum lançamento encontrado com essa descrição."

        if len(candidates) == 1:
            t = candidates[0]
            return (
                f"⚠️ Encontrei este lançamento:\n\n"
                f"🆔 ID: {t['id']}\n"
                f"• {t['description'] or 'Sem descrição'} — R$ {t['amount']:,.2f}\n"
                f"• Data: {t['date'].strftime('%d/%m/%Y')}\n"
                f"• Categoria: {t['category_name'] or 'Sem categoria'}\n\n"
                f"Deseja excluir? Responda 'Sim' para confirmar."
            )

        lines = ["🔍 Encontrei estes lançamentos:\n"]
        for i, t in enumerate(candidates, 1):
            lines.append(
                f"{i}. {t['description'] or 'Sem descrição'} — "
                f"R$ {t['amount']:,.2f} ({t['date'].strftime('%d/%m')})"
            )
        lines.append("\nQual deseja remover? Me diga o número.")
        return "\n".join(lines)

    # Sem ID e sem busca → pegar o último lançamento
    last = await service.get_last(user_id)
    if not last:
        return "❌ Você não tem nenhum lançamento registrado."

    return (
        f"⚠️ Seu último lançamento foi:\n\n"
        f"🆔 ID: {last['id']}\n"
        f"• {last['description'] or 'Sem descrição'} — R$ {last['amount']:,.2f}\n"
        f"• Data: {last['date'].strftime('%d/%m/%Y')}\n"
        f"• Categoria: {last['category_name'] or 'Sem categoria'}\n\n"
        f"Deseja excluir este? Responda 'Sim' para confirmar."
    )
