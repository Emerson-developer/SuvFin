"""
Processador MCP: Orquestra a LLM (Claude) com as tools financeiras.
Recebe mensagem do usuário → LLM decide qual tool chamar → retorna resposta.
"""

import json
from dataclasses import dataclass
from typing import Optional

import anthropic
from loguru import logger

from app.config.settings import settings
from app.config.redis_client import redis_client
from app.services.mcp.server import TOOL_DEFINITIONS, TOOL_HANDLERS
from app.services.whatsapp.media import WhatsAppMedia


@dataclass
class MCPResponse:
    """Resposta do processador MCP."""
    text: str
    media: Optional[bytes] = None
    media_type: Optional[str] = None  # image/png, application/pdf


SYSTEM_PROMPT = """Você é o SuvFin 💰, um assistente de finanças pessoais via WhatsApp.

Suas capacidades:
- Registrar gastos e receitas do usuário
- Remover e editar lançamentos
- Gerar relatórios por período e categoria
- Mostrar saldo atual
- Processar comprovantes enviados por foto (usando Vision)
- Listar categorias

Regras IMPORTANTES:
- Responda SEMPRE em português do Brasil
- Seja amigável, conciso e use emojis
- Sempre passe o user_id nas tools (ele será fornecido no contexto)
- Para remoção/edição, SEMPRE peça confirmação antes de executar
- Quando o valor for ambíguo, pergunte ao usuário
- Categorize gastos automaticamente quando possível
- Se o usuário enviar foto, use a tool processar_comprovante
- Formate valores monetários como R$ X.XXX,XX
- Use datas no formato DD/MM/YYYY nas respostas
- Se o usuário disser apenas "Oi" ou cumprimentar, responda com uma mensagem de boas-vindas
- Não invente dados, use apenas o que vem das tools

Mensagem de boas-vindas:
"Olá! Sou o SuvFin 💰, seu assistente de finanças pessoais!
Posso te ajudar a:
📝 Registrar gastos e receitas
📊 Gerar relatórios
💰 Ver seu saldo
📸 Analisar comprovantes por foto
🗑️ Remover registros

Me diga como posso ajudar!"
"""


class MCPProcessor:
    """Orquestra Claude LLM + Tools para processar mensagens."""

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def process(
        self,
        user_id: str,
        phone: str,
        message_type: str,
        content: str,
        name: str = "Usuário",
    ) -> MCPResponse:
        """Processa uma mensagem e retorna a resposta."""

        # Recuperar histórico da conversa
        conversation = await self._get_conversation(phone)

        # Se for imagem, processar com Vision
        if message_type == "image":
            return await self._process_image(user_id, phone, content, conversation)

        # Texto → LLM + Tools
        return await self._process_text(user_id, phone, content, conversation, name)

    async def _process_image(
        self,
        user_id: str,
        phone: str,
        media_id: str,
        conversation: list[dict],
    ) -> MCPResponse:
        """Processa imagem usando Claude Vision diretamente."""
        media_service = WhatsAppMedia()

        try:
            image_bytes = await media_service.download(media_id)
        except Exception as e:
            logger.error(f"Erro ao baixar mídia: {e}")
            return MCPResponse(text="❌ Não consegui baixar a imagem. Tente novamente.")

        image_base64 = media_service.to_base64(image_bytes)
        media_type = media_service.detect_type(image_bytes)

        messages = conversation + [
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
                        "text": "Analise este comprovante e me diga os dados para eu registrar.",
                    },
                ],
            }
        ]

        system = (
            f"{SYSTEM_PROMPT}\n\n"
            f"User ID do usuário atual: {user_id}\n"
            f"Data de hoje: {self._today()}"
        )

        try:
            response = await self.client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2048,
                system=system,
                messages=messages,
                tools=TOOL_DEFINITIONS,
            )

            result_text = await self._handle_tool_loop(
                response, messages, system
            )
        except Exception as e:
            logger.error(f"Erro no Vision: {e}")
            result_text = "❌ Não consegui analisar a imagem. Tente novamente."

        # Salvar no histórico
        await self._save_conversation(phone, "user", "[📸 Comprovante enviado]")
        await self._save_conversation(phone, "assistant", result_text)

        return MCPResponse(text=result_text)

    async def _process_text(
        self,
        user_id: str,
        phone: str,
        text: str,
        conversation: list[dict],
        name: str,
    ) -> MCPResponse:
        """Processa mensagem de texto com LLM + Tools."""

        messages = conversation + [{"role": "user", "content": text}]

        system = (
            f"{SYSTEM_PROMPT}\n\n"
            f"User ID do usuário atual: {user_id}\n"
            f"Nome do usuário: {name}\n"
            f"Data de hoje: {self._today()}"
        )

        try:
            response = await self.client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2048,
                system=system,
                messages=messages,
                tools=TOOL_DEFINITIONS,
            )

            result_text = await self._handle_tool_loop(
                response, messages, system
            )
        except anthropic.APIError as e:
            logger.error(f"Erro na API Anthropic: {e}")
            result_text = "❌ Ops, tive um problema. Tente novamente em instantes."
        except Exception as e:
            logger.error(f"Erro inesperado no processamento: {e}")
            result_text = "❌ Algo deu errado. Tente novamente."

        # Salvar no histórico
        await self._save_conversation(phone, "user", text)
        await self._save_conversation(phone, "assistant", result_text)

        return MCPResponse(text=result_text)

    async def _handle_tool_loop(
        self,
        response,
        messages: list[dict],
        system: str,
    ) -> str:
        """Executa tools em loop até a LLM retornar texto final."""
        max_iterations = 10

        for _ in range(max_iterations):
            if response.stop_reason != "tool_use":
                break

            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    logger.info(
                        f"🔧 Tool chamada: {block.name} | Args: {block.input}"
                    )

                    handler = TOOL_HANDLERS.get(block.name)
                    if handler:
                        try:
                            result = await handler(**block.input)
                        except Exception as e:
                            logger.error(f"Erro na tool {block.name}: {e}")
                            result = f"Erro ao executar {block.name}: {str(e)}"
                    else:
                        result = f"Tool '{block.name}' não encontrada."

                    # Limpar dados pendentes internos
                    if "__PENDING_RECEIPT__:" in result:
                        result = result.split("__PENDING_RECEIPT__:")[0].strip()

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )

            # Serializar content blocks para mensagem
            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append(
                        {"type": "text", "text": block.text}
                    )
                elif block.type == "tool_use":
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

            response = await self.client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2048,
                system=system,
                messages=messages,
                tools=TOOL_DEFINITIONS,
            )

        # Extrair texto final
        return "".join(
            block.text
            for block in response.content
            if hasattr(block, "text")
        )

    # --- Gerenciamento de conversa (Redis) ---

    async def _get_conversation(self, phone: str) -> list[dict]:
        """Recupera histórico recente do Redis."""
        try:
            raw = await redis_client.lrange(f"conv:{phone}", 0, 19)
            return [json.loads(msg) for msg in raw] if raw else []
        except Exception as e:
            logger.warning(f"Erro ao ler conversa do Redis: {e}")
            return []

    async def _save_conversation(self, phone: str, role: str, content: str):
        """Salva mensagem no histórico com TTL de 2 horas."""
        try:
            key = f"conv:{phone}"
            await redis_client.rpush(
                key, json.dumps({"role": role, "content": content})
            )
            await redis_client.ltrim(key, -20, -1)  # Manter últimas 20 msgs
            await redis_client.expire(key, 7200)  # TTL 2 horas
        except Exception as e:
            logger.warning(f"Erro ao salvar conversa no Redis: {e}")

    def _today(self) -> str:
        from datetime import date
        return date.today().isoformat()
