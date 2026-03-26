"""Tool: Desconectar banco do Open Finance."""

from app.services.pluggy.client import PluggyClient, PluggyError
from app.services.pluggy.sync_service import PluggySyncService


async def desconectar_banco(
    user_id: str,
    banco: str = None,
    confirmar: bool = False,
) -> str:
    """Desconecta uma conta bancária do Open Finance."""

    sync_service = PluggySyncService()
    items = await sync_service.get_user_items(user_id)

    if not items:
        return "📭 Você não tem contas bancárias conectadas."

    # Se apenas 1 item, usá-lo direto
    if len(items) == 1 and not banco:
        target_item = items[0]
    elif banco:
        target_item = await sync_service.get_item_by_connector_name(user_id, banco)
        if not target_item:
            banks = ", ".join(i.connector_name or "?" for i in items)
            return (
                f"❌ Banco \"{banco}\" não encontrado.\n\n"
                f"Suas conexões ativas: {banks}"
            )
    else:
        # Múltiplos bancos, precisa especificar
        banks = "\n".join(
            f"  • {i.connector_name or '?'}" for i in items
        )
        return (
            f"Você tem múltiplas contas conectadas:\n{banks}\n\n"
            f"Qual banco deseja desconectar?"
        )

    bank_name = target_item.connector_name or "banco"

    if not confirmar:
        return (
            f"⚠️ Tem certeza que deseja desconectar o **{bank_name}**?\n\n"
            f"Todas as transações importadas deste banco serão removidas.\n\n"
            f"Confirme para prosseguir."
        )

    # Confirmar: deletar no Pluggy e desregistrar localmente
    client = PluggyClient()
    try:
        await client.delete_item(target_item.pluggy_item_id)
    except PluggyError:
        pass  # Continua limpeza local

    await sync_service.unregister_connection(user_id, target_item.pluggy_item_id)

    return (
        f"✅ **{bank_name}** desconectado com sucesso!\n\n"
        f"As transações importadas foram removidas.\n"
        f"Você pode reconectar a qualquer momento enviando \"conectar banco\"."
    )
