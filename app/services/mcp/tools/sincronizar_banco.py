"""Tool: Sincronizar banco (forçar resync no Pluggy)."""

from app.services.pluggy.client import PluggyClient, PluggyError
from app.services.pluggy.sync_service import PluggySyncService


async def sincronizar_banco(user_id: str, banco: str = None) -> str:
    """Força a re-sincronização das contas bancárias do usuário."""

    sync_service = PluggySyncService()
    items = await sync_service.get_user_items(user_id)

    if not items:
        return (
            "📭 Você não tem contas bancárias conectadas.\n\n"
            "Envie \"conectar banco\" para conectar via Open Finance!"
        )

    client = PluggyClient()
    synced = []
    errors = []

    for item in items:
        # Filtrar por banco se especificado
        if banco and item.connector_name:
            if banco.lower() not in item.connector_name.lower():
                continue

        try:
            await client.update_item(item.pluggy_item_id)
            synced.append(item.connector_name or "Banco")
        except PluggyError as e:
            errors.append(f"{item.connector_name or 'Banco'}: {e}")

    if not synced and not errors:
        return f"❌ Banco \"{banco}\" não encontrado nas suas conexões."

    lines = []
    if synced:
        lines.append("🔄 Sincronização iniciada:\n")
        for name in synced:
            lines.append(f"  ✅ {name}")
        lines.append("\n⏱️ Em alguns minutos seus dados serão atualizados.")

    if errors:
        lines.append("\n⚠️ Erros:")
        for err in errors:
            lines.append(f"  ❌ {err}")

    return "\n".join(lines)
