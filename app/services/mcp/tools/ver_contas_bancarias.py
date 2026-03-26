"""Tool: Ver contas bancárias conectadas via Open Finance."""

from app.services.pluggy.sync_service import PluggySyncService


async def ver_contas_bancarias(user_id: str) -> str:
    """Lista as contas bancárias conectadas do usuário via Open Finance."""

    sync_service = PluggySyncService()
    items = await sync_service.get_user_items(user_id)

    if not items:
        return (
            "📭 Você ainda não tem contas bancárias conectadas.\n\n"
            "Envie \"conectar banco\" para conectar via Open Finance!"
        )

    accounts = await sync_service.get_user_accounts(user_id)

    # Agrupar contas por item (banco)
    item_map = {str(i.id): i for i in items}
    banks: dict[str, list] = {}
    for acc in accounts:
        item = item_map.get(str(acc.pluggy_item_id))
        bank_name = item.connector_name if item else "Banco"
        if bank_name not in banks:
            banks[bank_name] = {"item": item, "accounts": []}
        banks[bank_name]["accounts"].append(acc)

    lines = ["🏦 Suas contas conectadas:\n"]

    for i, (bank_name, data) in enumerate(banks.items(), 1):
        item = data["item"]
        status_emoji = "🟢" if item and item.status == "UPDATED" else "🟡"

        lines.append(f"{i}. {status_emoji} **{bank_name}**")

        for acc in data["accounts"]:
            balance_str = f"R$ {acc.balance:,.2f}" if acc.balance is not None else "—"
            acc_type = _format_subtype(acc.subtype)
            lines.append(f"   💳 {acc.name or acc_type} — Saldo: {balance_str}")

        if item and item.last_sync_at:
            sync_str = item.last_sync_at.strftime("%d/%m/%Y %H:%M")
            lines.append(f"   🔄 Última sync: {sync_str}")

        lines.append("")

    config = await sync_service.get_or_create_config(user_id)
    lines.append(
        f"📊 Conexões: {config.active_connections}/{config.max_connections}"
    )

    return "\n".join(lines)


def _format_subtype(subtype: str | None) -> str:
    """Formata o subtipo da conta para exibição."""
    mapping = {
        "CHECKING_ACCOUNT": "Conta Corrente",
        "SAVINGS_ACCOUNT": "Poupança",
    }
    return mapping.get(subtype or "", subtype or "Conta")
