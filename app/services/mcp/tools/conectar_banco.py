"""Tool: Conectar banco via Open Finance (Pluggy)."""

from app.config.database import async_session
from app.models.user import User, LicenseType
from app.services.pluggy.client import PluggyClient, PluggyError
from app.services.pluggy.sync_service import PluggySyncService
from sqlalchemy import select


async def conectar_banco(user_id: str, perfil: str = "PF") -> str:
    """Gera link do Pluggy Connect para o usuário conectar sua conta bancária."""

    if perfil.upper() not in ("PF", "PJ"):
        return "❌ Perfil inválido. Use 'PF' para conta pessoal ou 'PJ' para conta empresarial."

    profile = perfil.upper()

    # Verificar se o usuário existe e tem plano pago
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return "❌ Usuário não encontrado."

    if user.license_type == LicenseType.FREE_TRIAL:
        return (
            "❌ O Open Finance está disponível apenas para assinantes.\n\n"
            "Faça upgrade do seu plano para conectar suas contas bancárias! "
            "Envie \"ver planos\" para conhecer as opções."
        )

    if not user.is_license_valid:
        return (
            "❌ Sua assinatura expirou.\n\n"
            "Renove para continuar usando o Open Finance. "
            "Envie \"ver planos\" para renovar."
        )

    # Verificar limite de conexões
    sync_service = PluggySyncService()
    config = await sync_service.get_or_create_config(user_id)

    if not config.can_create_connection:
        return (
            f"❌ Você já atingiu o limite de {config.max_connections} "
            f"conta(s) conectada(s) ({config.active_connections}/{config.max_connections}).\n\n"
            f"Desconecte uma conta existente para adicionar outra, "
            f"ou entre em contato para solicitar aumento do limite."
        )

    # Gerar connect token
    try:
        client = PluggyClient()
        token = await client.create_connect_token(client_user_id=user.phone)
    except PluggyError as e:
        return f"❌ Erro ao gerar link de conexão: {e}"

    connect_url = f"https://connect.pluggy.ai/?connect_token={token}"

    profile_label = "empresarial (PJ)" if profile == "PJ" else "pessoal (PF)"
    return (
        f"🏦 Para conectar sua conta {profile_label}, acesse o link abaixo:\n\n"
        f"{connect_url}\n\n"
        f"⏱️ O link expira em 30 minutos.\n"
        f"📱 Abra no navegador do celular, escolha seu banco e siga as instruções.\n\n"
        f"Após conectar, seus dados serão importados automaticamente "
        f"como {profile_label.upper()}!"
    )
