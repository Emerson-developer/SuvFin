"""Tool: Definir perfil padrão (PF ou PJ) para lançamentos futuros."""

from app.services.finance.transaction_service import TransactionService


async def definir_perfil_padrao(user_id: str, perfil: str) -> str:
    """Define o perfil padrão do usuário (PF = pessoal, PJ = empresarial).

    Todos os próximos lançamentos sem perfil explícito usarão este padrão.
    """
    if not perfil or perfil.upper() not in ("PF", "PJ"):
        return "❌ Perfil inválido. Use 'PF' para pessoal ou 'PJ' para empresarial."

    profile = perfil.upper()
    service = TransactionService()
    updated = await service.set_user_default_profile(user_id, profile)

    if not updated:
        return "❌ Usuário não encontrado."

    profile_label = "👤 Pessoal (PF)" if profile == "PF" else "🏢 Empresarial (PJ)"
    return (
        f"✅ Perfil padrão definido como *{profile_label}*!\n\n"
        f"A partir de agora, todos os lançamentos sem perfil explícito "
        f"serão registrados como {profile}.\n\n"
        f"💡 Você ainda pode especificar o perfil individualmente ao registrar "
        f"um gasto ou entrada."
    )
