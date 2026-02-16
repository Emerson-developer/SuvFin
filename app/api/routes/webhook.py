"""
Rotas do Webhook do WhatsApp (Meta Cloud API).
"""

from fastapi import APIRouter, Request, Response, Query, HTTPException, BackgroundTasks
from loguru import logger

from app.config.settings import settings
from app.services.whatsapp.parser import WhatsAppParser
from app.services.whatsapp.client import WhatsAppClient
from app.services.license.license_service import LicenseService
from app.services.mcp.processor import MCPProcessor

router = APIRouter(tags=["webhook"])


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """
    Verificação do webhook da Meta (handshake).
    A Meta envia GET com hub.mode, hub.challenge e hub.verify_token.
    """
    logger.info(
        f"Webhook verification: mode={hub_mode}, token={hub_verify_token}"
    )

    if hub_mode == "subscribe" and hub_verify_token == settings.WEBHOOK_VERIFY_TOKEN:
        logger.info("Webhook verificado com sucesso ✅")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning("Webhook verification falhou ❌")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe mensagens do WhatsApp Cloud API.
    Responde 200 imediatamente e processa em background.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # A Meta espera 200 rápido — processa em background
    background_tasks.add_task(_process_webhook, payload)

    return {"status": "received"}


async def _process_webhook(payload: dict):
    """Processa o payload do webhook (executado em background)."""
    parser = WhatsAppParser()
    message = parser.extract(payload)

    if not message:
        logger.debug("Payload ignorado (sem mensagem de usuário)")
        return

    phone = message.phone
    name = message.name
    msg_type = message.type
    content = message.content
    message_id = message.message_id

    logger.info(
        f"📩 Mensagem recebida: phone={phone}, type={msg_type}, "
        f"content={content[:50] if isinstance(content, str) else content}"
    )

    client = WhatsAppClient()

    # Marcar mensagem como lida
    try:
        await client.mark_as_read(message_id)
    except Exception as e:
        logger.warning(f"Falha ao marcar como lida: {e}")

    # Verificar/criar usuário
    license_service = LicenseService()
    user, is_new_user = await license_service.get_or_create_user(phone, name)

    # Novo usuário — enviar mensagem de boas-vindas
    if is_new_user:
        display_name = name or "usuário"
        expires = user.license_expires_at
        expires_str = expires.strftime("%d/%m/%Y") if expires else "7 dias"
        welcome_msg = (
            f"Olá, {display_name}! 👋\n\n"
            f"🌟 *Bem-vindo(a) ao SuvFin!*\n\n"
            f"Sou seu assistente de finanças pessoais pelo WhatsApp. "
            f"Vou te ajudar a organizar sua vida financeira de forma simples e rápida!\n\n"
            f"🆓 Você ganhou um *período de teste grátis* até *{expires_str}*!\n\n"
            f"O que posso fazer por você:\n"
            f"📝 Registrar gastos e receitas\n"
            f"📊 Gerar relatórios por período e categoria\n"
            f"💰 Mostrar seu saldo atual\n"
            f"📸 Analisar comprovantes por foto\n"
            f"🗑️ Remover e editar lançamentos\n\n"
            f"Experimente agora! Envie algo como:\n"
            f'  _"Gastei 50 reais no almoço"_\n'
            f'  _"Qual meu saldo?"_\n'
            f'  _"Recebi 3000 de salário"_\n\n'
            f"Vamos começar? 🚀"
        )
        await client.send_text(phone, welcome_msg)
        logger.info(f"🌟 Novo usuário trial criado e boas-vindas enviada: {phone}")
        return

    if not user.is_license_valid:
        # Gerar link de pagamento PIX via AbacatePay (plano Pro como padrão)
        try:
            payment_url = await license_service.get_payment_link(phone, plan="PRO", period="MONTHLY")
            upgrade_msg = (
                "⏰ Seu período de teste expirou!\n\n"
                "Escolha um plano para continuar usando o SuvFin:\n\n"
                "⭐ *Básico* — R$ 9,90/mês\n"
                "  100 transações/mês, relatórios básicos\n\n"
                "⚡ *Pro* — R$ 19,90/mês _(mais popular!)_\n"
                "  Transações ilimitadas, relatórios detalhados, alertas\n\n"
                "👑 *Premium* — R$ 34,90/mês\n"
                "  Tudo do Pro + análise preditiva, consultoria por IA\n\n"
                "💡 _Planos anuais têm 20% de desconto!_\n\n"
                f"🔗 Assine o plano Pro agora: {payment_url}\n\n"
                "Para escolher outro plano, envie:\n"
                '  _"Quero o plano Básico"_\n'
                '  _"Quero o plano Premium"_\n'
                '  _"Quero plano anual"_'
            )
        except Exception as e:
            logger.error(f"Erro ao gerar link de pagamento: {e}")
            upgrade_msg = (
                "⏰ Seu período de teste expirou!\n\n"
                "Para continuar usando o SuvFin, escolha um plano:\n\n"
                "⭐ *Básico* — R$ 9,90/mês\n"
                "⚡ *Pro* — R$ 19,90/mês\n"
                "👑 *Premium* — R$ 34,90/mês\n\n"
                "Envie qual plano deseja para gerar o link de pagamento! 🚀"
            )

        await client.send_text(phone, upgrade_msg)
        return

    # Processar com MCP + LLM
    processor = MCPProcessor()
    response = await processor.process(
        user_id=str(user.id),
        phone=phone,
        message_type=msg_type,
        content=content,
        name=name,
    )

    # Enviar resposta
    await client.send_text(phone, response.text)

    # Se tiver mídia (gráfico, PDF), enviar
    if response.media and response.media_type:
        if "image" in response.media_type:
            await client.send_image(phone, response.media, caption="📊 Relatório")
        elif "pdf" in response.media_type:
            await client.send_document(
                phone, response.media, "relatorio_suvfin.pdf", caption="📄 Relatório"
            )

    logger.info(f"✅ Resposta enviada para {phone}")
