"""
Rotas do Webhook do WhatsApp (Meta Cloud API).
"""

import re

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


def _detect_plan_selection(text: str) -> tuple[str, str] | None:
    """
    Detecta se o usuário está escolhendo um plano pelo texto da mensagem.
    Retorna (plan, period) ou None.
    """
    t = text.lower().strip()
    # Normalizar acentos comuns
    t = t.replace("á", "a").replace("é", "e").replace("í", "i")

    plan = None
    if re.search(r"\bbasico\b", t):
        plan = "BASICO"
    elif re.search(r"\bpremium\b", t):
        plan = "PREMIUM"
    elif re.search(r"\bpro\b", t):
        plan = "PRO"

    if not plan:
        return None

    period = "MONTHLY"
    if re.search(r"\banual\b|\banuais\b|\bano\b|\bannual\b", t):
        period = "ANNUAL"

    return (plan, period)


async def _send_plan_list(phone: str, client: WhatsAppClient) -> None:
    """Envia lista interativa com os planos disponíveis."""
    try:
        await client.send_interactive_list(
            to=phone,
            header_text="Escolha seu Plano",
            body_text=(
                "⏰ Seu período de teste expirou!\n\n"
                "Para continuar usando o SuvFin, escolha um plano abaixo.\n\n"
                "💡 Planos anuais têm 20% de desconto!"
            ),
            footer_text="SuvFin — Seu financeiro no WhatsApp",
            button_text="Ver Planos",
            sections=[
                {
                    "title": "Planos Mensais",
                    "rows": [
                        {
                            "id": "plan_basico_monthly",
                            "title": "Básico Mensal",
                            "description": "R$ 9,90/mês • 100 transações",
                        },
                        {
                            "id": "plan_pro_monthly",
                            "title": "Pro Mensal",
                            "description": "R$ 19,90/mês • Ilimitado",
                        },
                        {
                            "id": "plan_premium_monthly",
                            "title": "Premium Mensal",
                            "description": "R$ 34,90/mês • Tudo incluso",
                        },
                    ],
                },
                {
                    "title": "Planos Anuais (-20%)",
                    "rows": [
                        {
                            "id": "plan_basico_annual",
                            "title": "Básico Anual",
                            "description": "R$ 7,92/mês • Economia de 20%",
                        },
                        {
                            "id": "plan_pro_annual",
                            "title": "Pro Anual",
                            "description": "R$ 15,92/mês • Economia de 20%",
                        },
                        {
                            "id": "plan_premium_annual",
                            "title": "Premium Anual",
                            "description": "R$ 27,92/mês • Economia de 20%",
                        },
                    ],
                },
            ],
        )
        logger.info(f"📋 Lista de planos enviada para {phone}")
    except Exception as e:
        logger.error(f"Erro ao enviar lista interativa para {phone}: {e}")
        # Fallback: texto simples
        await client.send_text(
            phone,
            (
                "⏰ *Seu período de teste expirou!*\n\n"
                "Escolha um plano para continuar:\n\n"
                "⭐ *Básico* — R$ 9,90/mês\n"
                "⚡ *Pro* — R$ 19,90/mês _(mais popular!)_\n"
                "👑 *Premium* — R$ 34,90/mês\n\n"
                "💡 Planos anuais com 20% de desconto!\n\n"
                'Envie: _"Quero o Pro"_ ou _"Quero o Básico anual"_'
            ),
        )


async def _handle_plan_selection(phone: str, plan_id: str, client: WhatsAppClient) -> None:
    """Processa seleção de plano (via lista interativa ou texto) e gera link de pagamento."""
    # Formato do ID: plan_{tipo}_{periodo}
    parts = plan_id.replace("plan_", "").rsplit("_", 1)
    if len(parts) != 2:
        await client.send_text(phone, "❌ Opção inválida. Tente novamente.")
        return

    plan_key, period_key = parts
    plan_map = {"basico": "BASICO", "pro": "PRO", "premium": "PREMIUM"}
    period_map = {"monthly": "MONTHLY", "annual": "ANNUAL"}

    plan = plan_map.get(plan_key)
    period = period_map.get(period_key)

    if not plan or not period:
        await client.send_text(phone, "❌ Opção inválida. Tente novamente.")
        return

    plan_names = {"BASICO": "⭐ Básico", "PRO": "⚡ Pro", "PREMIUM": "👑 Premium"}
    period_label = "Mensal" if period == "MONTHLY" else "Anual"
    prices = {
        ("BASICO", "MONTHLY"): "R$ 9,90/mês",
        ("BASICO", "ANNUAL"): "R$ 7,92/mês (cobrado R$ 95,04/ano)",
        ("PRO", "MONTHLY"): "R$ 19,90/mês",
        ("PRO", "ANNUAL"): "R$ 15,92/mês (cobrado R$ 191,04/ano)",
        ("PREMIUM", "MONTHLY"): "R$ 34,90/mês",
        ("PREMIUM", "ANNUAL"): "R$ 27,92/mês (cobrado R$ 335,04/ano)",
    }
    features = {
        "BASICO": (
            "✅ Registro de despesas e receitas\n"
            "✅ Relatórios mensais básicos\n"
            "✅ Categorias automáticas\n"
            "✅ Até 100 transações/mês"
        ),
        "PRO": (
            "✅ Tudo do Básico\n"
            "✅ Transações ilimitadas\n"
            "✅ Relatórios detalhados\n"
            "✅ Alertas inteligentes\n"
            "✅ Metas financeiras\n"
            "✅ Notas fiscais e exportação"
        ),
        "PREMIUM": (
            "✅ Tudo do Pro\n"
            "✅ Análise preditiva de gastos\n"
            "✅ Consultoria financeira por IA\n"
            "✅ Múltiplas contas e cartões\n"
            "✅ Suporte prioritário 24/7"
        ),
    }

    try:
        license_service = LicenseService()
        payment_url = await license_service.get_payment_link(phone, plan=plan, period=period)

        plan_msg = (
            f"✨ *Plano {plan_names[plan]} — {period_label}*\n\n"
            f"💰 *{prices.get((plan, period), '')}*\n\n"
            f"{features.get(plan, '')}\n\n"
            f"🔗 Pague via PIX pelo link:\n{payment_url}\n\n"
            f"✅ Após o pagamento, seu plano é ativado automaticamente!"
        )
        await client.send_text(phone, plan_msg)
        logger.info(f"💳 Link gerado para {phone}: {plan} {period_label}")
    except Exception as e:
        logger.error(f"Erro ao gerar link para plano {plan}: {e}")
        await client.send_text(
            phone,
            "❌ Erro ao gerar o link de pagamento. Tente novamente em alguns instantes.",
        )


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

    # ── Seleção de plano via lista interativa ──
    # content vem com o ID (ex: "plan_basico_monthly") para msgs interativas
    if msg_type == "interactive" and isinstance(content, str) and content.startswith("plan_"):
        await _handle_plan_selection(phone, content, client)
        return

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
        # Verificar se o usuário está escolhendo um plano por texto
        if msg_type == "text" and isinstance(content, str):
            selected = _detect_plan_selection(content)
            if selected:
                plan, period = selected
                await _handle_plan_selection(phone, f"plan_{plan.lower()}_{period.lower()}", client)
                return

        # Enviar lista interativa de planos
        await _send_plan_list(phone, client)
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
