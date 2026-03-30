"""Tool: Saldo atual."""

from app.services.finance.report_service import ReportService


async def saldo_atual(user_id: str, perfil: str = None) -> str:
    """Retorna o saldo atual (entradas - saídas). Filtrável por PF ou PJ."""
    if perfil and perfil.upper() not in ("PF", "PJ"):
        return "❌ Perfil inválido. Use 'PF' ou 'PJ'."

    service = ReportService()
    profile_filter = perfil.upper() if perfil else None
    balance = await service.get_balance(user_id, profile=profile_filter)

    income = balance["total_income"]
    expense = balance["total_expense"]
    saldo = balance["balance"]

    emoji = "📈" if saldo >= 0 else "📉"
    saldo_emoji = "💰" if saldo >= 0 else "⚠️"

    perfil_label = f" ({perfil.upper()})" if perfil else ""
    lines = [
        f"{emoji} *Seu Saldo Atual{perfil_label}*\n",
        f"🟢 Total de Entradas: R$ {income:,.2f}",
        f"🔴 Total de Saídas: R$ {expense:,.2f}",
        f"{saldo_emoji} Saldo: R$ {saldo:,.2f}",
    ]

    # Breakdown PF vs PJ quando sem filtro
    if not profile_filter and balance.get("by_profile"):
        bp = balance["by_profile"]
        lines.append("")
        lines.append("📊 *Por Perfil:*")
        for prof_key, prof_label in (("PF", "👤 Pessoal (PF)"), ("PJ", "🏢 Empresa (PJ)")):
            d = bp.get(prof_key, {})
            s = d.get("balance", 0.0)
            emoji_prof = "💰" if s >= 0 else "⚠️"
            lines.append(
                f"  {prof_label}: {emoji_prof} R$ {s:,.2f}"
            )

    return "\n".join(lines)
