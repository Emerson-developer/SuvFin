"""Tool: Editar lançamento."""

from datetime import datetime
from app.services.finance.transaction_service import TransactionService


async def editar_lancamento(
    user_id: str,
    lancamento_id: str,
    novo_valor: float = None,
    nova_categoria: str = None,
    nova_descricao: str = None,
    nova_data: str = None,
) -> str:
    """Edita um lançamento existente do usuário."""
    service = TransactionService()

    transaction = await service.get_by_id(lancamento_id, user_id)
    if not transaction:
        return "❌ Lançamento não encontrado."

    updates = {}
    changes = []

    if novo_valor is not None:
        updates["amount"] = novo_valor
        changes.append(
            f"💲 Valor: R$ {transaction['amount']:,.2f} → R$ {novo_valor:,.2f}"
        )

    if nova_categoria:
        updates["category_name"] = nova_categoria
        changes.append(
            f"🏷️ Categoria: {transaction['category_name']} → {nova_categoria}"
        )

    if nova_descricao:
        updates["description"] = nova_descricao
        changes.append(
            f"📝 Descrição: {transaction['description'] or '(vazia)'} → {nova_descricao}"
        )

    if nova_data:
        try:
            parsed_date = datetime.strptime(nova_data, "%Y-%m-%d").date()
            updates["date"] = parsed_date
            changes.append(
                f"📅 Data: {transaction['date'].strftime('%d/%m/%Y')} → "
                f"{parsed_date.strftime('%d/%m/%Y')}"
            )
        except ValueError:
            return "❌ Data inválida. Use o formato YYYY-MM-DD."

    if not updates:
        return "❌ Nenhuma alteração informada."

    await service.update(lancamento_id, user_id, updates)

    return (
        f"✏️ Lançamento atualizado!\n\n"
        f"Alterações:\n" + "\n".join(changes)
    )
