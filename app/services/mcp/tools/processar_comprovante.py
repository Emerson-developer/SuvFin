"""
Tool: Processar comprovante usando Claude Vision (IA).
Substitui OCR tradicional — mais preciso, entende contexto e layouts variados.
"""

import json
import anthropic
from loguru import logger
from app.config.settings import settings
from app.services.whatsapp.media import WhatsAppMedia


async def processar_comprovante(user_id: str, media_id: str) -> str:
    """Processa imagem de comprovante usando Claude Vision."""

    # 1. Baixar imagem do WhatsApp
    media_service = WhatsAppMedia()
    try:
        image_bytes = await media_service.download(media_id)
    except Exception as e:
        logger.error(f"Erro ao baixar mídia {media_id}: {e}")
        return "❌ Não consegui baixar a imagem. Tente enviar novamente."

    image_base64 = media_service.to_base64(image_bytes)
    media_type = media_service.detect_type(image_bytes)

    # 2. Enviar para Claude Vision
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    try:
        response = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": """Analise esta imagem de comprovante financeiro (pode ser cupom fiscal, 
comprovante Pix, transferência bancária, boleto, nota fiscal, recibo, extrato, etc).

Extraia as seguintes informações e retorne APENAS um JSON válido, sem markdown:

{
    "valor": 0.00,
    "estabelecimento": "Nome da loja/pessoa",
    "data": "YYYY-MM-DD",
    "categoria_sugerida": "alimentação|transporte|saúde|lazer|educação|moradia|serviços|vestuário|outros",
    "tipo": "EXPENSE|INCOME",
    "descricao": "Breve descrição do que se trata",
    "confianca": "alta|media|baixa"
}

Regras:
- Se não conseguir identificar algum campo, use null
- "confianca" indica quão certo você está da extração
- Se for recebimento (Pix recebido, depósito, salário), tipo = "INCOME"
- Se for pagamento/compra, tipo = "EXPENSE"
- Valor sempre como número decimal (sem R$, sem pontos de milhar)
- Data no formato YYYY-MM-DD""",
                        },
                    ],
                }
            ],
        )
    except Exception as e:
        logger.error(f"Erro ao processar imagem com Claude Vision: {e}")
        return (
            "❌ Não consegui analisar a imagem no momento. "
            "Tente novamente ou me diga o valor manualmente."
        )

    # 3. Parsear resposta da LLM
    raw_text = response.content[0].text
    try:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning(f"JSON inválido do Vision: {raw_text}")
        return (
            "❌ Não consegui interpretar este comprovante. "
            "Tente enviar uma foto mais nítida ou me diga o valor manualmente."
        )

    # 4. Formatar resposta
    confianca_emoji = {"alta": "🟢", "media": "🟡", "baixa": "🔴"}

    valor = data.get("valor")
    if not valor:
        return (
            "🤔 Consegui ver a imagem mas não identifiquei o valor. "
            "Pode me dizer quanto foi?"
        )

    emoji = confianca_emoji.get(data.get("confianca", "baixa"), "🔴")
    tipo_label = "💸 Gasto" if data.get("tipo") == "EXPENSE" else "💰 Entrada"

    lines = [
        f"📸 Comprovante analisado! {emoji}",
        "",
        tipo_label,
        f"💲 Valor: R$ {valor:,.2f}",
    ]

    if data.get("estabelecimento"):
        lines.append(f"🏪 Local: {data['estabelecimento']}")
    if data.get("data"):
        from datetime import datetime
        try:
            dt = datetime.strptime(data["data"], "%Y-%m-%d")
            lines.append(f"📅 Data: {dt.strftime('%d/%m/%Y')}")
        except ValueError:
            pass
    if data.get("categoria_sugerida"):
        lines.append(f"🏷️ Categoria: {data['categoria_sugerida'].title()}")
    if data.get("descricao"):
        lines.append(f"📝 {data['descricao']}")

    lines.extend([
        "",
        "✅ Confirma o registro? (Sim/Não)",
        "✏️ Ou me diga o que corrigir.",
    ])

    # Retorna dados JSON embutidos para o processor usar na confirmação
    result = "\n".join(lines)
    pending = json.dumps(data, ensure_ascii=False)

    return f"{result}\n\n__PENDING_RECEIPT__:{pending}"
