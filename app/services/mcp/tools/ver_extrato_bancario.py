"""Tool: Ver extrato bancário (transações importadas do Open Finance)."""

from datetime import date, timedelta

from app.services.pluggy.sync_service import PluggySyncService


async def ver_extrato_bancario(
    user_id: str,
    banco: str = None,
    periodo: str = None,
    quantidade: int = 10,
    perfil: str = None,
) -> str:
    """Mostra o extrato bancário com transações importadas via Open Finance."""

    if perfil and perfil.upper() not in ("PF", "PJ"):
        return "❌ Perfil inválido. Use 'PF' ou 'PJ'."

    profile_filter = perfil.upper() if perfil else None
    sync_service = PluggySyncService()

    # Resolver período
    date_from, date_to, periodo_label = _resolve_period(periodo)

    # Filtrar por banco se especificado
    account_id = None
    bank_label = ""
    if banco:
        item = await sync_service.get_item_by_connector_name(user_id, banco)
        if item:
            bank_label = f" — {item.connector_name}"
            accounts = await sync_service.get_user_accounts(user_id)
            bank_accounts = [
                a for a in accounts if str(a.pluggy_item_id) == str(item.id)
            ]
            # Se filtro de perfil, filtrar também as contas
            if profile_filter:
                bank_accounts = [a for a in bank_accounts if a.profile == profile_filter]
            if bank_accounts:
                account_id = str(bank_accounts[0].id)
        else:
            return f"❌ Banco \"{banco}\" não encontrado nas suas conexões."

    if profile_filter and not banco:
        # Buscar diretamente por perfil
        transactions = await sync_service.get_user_transactions_by_profile(
            user_id=user_id,
            profile=profile_filter,
            date_from=date_from,
            date_to=date_to,
            limit=quantidade,
        )
    else:
        transactions = await sync_service.get_user_transactions(
            user_id=user_id,
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            limit=quantidade,
        )

    if not transactions:
        perfil_label = f" [{profile_filter}]" if profile_filter else ""
        return (
            f"💭 Nenhuma transação encontrada{bank_label}{perfil_label} "
            f"no período ({periodo_label}).\n\n"
            f"Envie \"sincronizar banco\" para atualizar os dados."
        )

    perfil_label = f" [{profile_filter}]" if profile_filter else ""
    lines = [f"📊 Extrato bancário{bank_label}{perfil_label} ({periodo_label}):\n"]

    total_in = 0
    total_out = 0

    for tx in transactions:
        amount = float(tx.amount)
        if amount >= 0:
            emoji = "🟢"
            sign = "+"
            total_in += amount
        else:
            emoji = "🔴"
            sign = ""
            total_out += abs(amount)

        date_str = tx.date.strftime("%d/%m") if tx.date else ""
        method = f" | {tx.payment_method}" if tx.payment_method else ""
        desc = tx.description or "Sem descrição"

        lines.append(
            f"{emoji} {sign}R$ {abs(amount):,.2f}{method} | {desc} | {date_str}"
        )

    lines.append("")
    lines.append(f"📈 Entradas: R$ {total_in:,.2f}")
    lines.append(f"📉 Saídas: R$ {total_out:,.2f}")
    balance = total_in - total_out
    balance_emoji = "🟢" if balance >= 0 else "🔴"
    lines.append(f"{balance_emoji} Saldo período: R$ {balance:,.2f}")

    return "\n".join(lines)


def _resolve_period(periodo: str | None) -> tuple[str | None, str | None, str]:
    """Converte período textual em datas."""
    today = date.today()

    if not periodo:
        # Default: últimos 7 dias
        date_from = (today - timedelta(days=7)).isoformat()
        return date_from, today.isoformat(), "últimos 7 dias"

    p = periodo.lower().strip()

    if p in ("hoje", "today"):
        return today.isoformat(), today.isoformat(), "hoje"

    if p in ("semana", "esta semana", "week"):
        start = today - timedelta(days=today.weekday())
        return start.isoformat(), today.isoformat(), "esta semana"

    if p in ("mes", "mês", "este mês", "este mes", "month"):
        start = today.replace(day=1)
        return start.isoformat(), today.isoformat(), "este mês"

    if p.startswith("ultimo") or p.startswith("último"):
        # "últimos 30 dias", "últimos 15 dias"
        import re
        match = re.search(r"(\d+)", p)
        if match:
            days = int(match.group(1))
            date_from = (today - timedelta(days=days)).isoformat()
            return date_from, today.isoformat(), f"últimos {days} dias"

    # Fallback: últimos 7 dias
    date_from = (today - timedelta(days=7)).isoformat()
    return date_from, today.isoformat(), "últimos 7 dias"
