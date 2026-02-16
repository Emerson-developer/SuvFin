"""
Processador MCP: Orquestra a LLM (Claude) com as tools financeiras.
Recebe mensagem do usuário → LLM decide qual tool chamar → retorna resposta.
Inclui otimizações de custo: cache, rate limiting, roteamento de modelos,
limitação de contexto, monitoramento de tokens.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
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
    tokens_used: dict = field(default_factory=dict)  # input/output tokens tracking


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
- Seja conciso nas respostas para economizar tokens

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

# Palavras-chave que indicam intenções simples (usar Haiku)
SIMPLE_INTENTS = {
    "oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "hey", "hi",
    "hello", "e aí", "eai", "fala", "obrigado", "obrigada", "valeu",
    "tchau", "até mais", "flw", "blz", "ok", "tudo bem", "tá", "ta",
    "sim", "não", "nao", "s", "n", "show", "beleza", "top",
}

# Intenções que precisam de tool use (usar Sonnet)
TOOL_KEYWORDS = {
    "gast", "compro", "pague", "registr", "lança", "saldo", "relatório",
    "relatorio", "quanto", "comprovante", "foto", "imagem", "remov",
    "exclui", "delet", "apag", "edit", "alter", "mud",
    "categ", "receita", "entrada", "salário", "salario", "renda",
}


def _select_model(text: str) -> str:
    """Seleciona o modelo ideal baseado na complexidade da mensagem."""
    text_lower = text.strip().lower()

    # Mensagens muito curtas ou cumprimentos → Haiku
    if text_lower in SIMPLE_INTENTS or len(text_lower) <= 3:
        return settings.ANTHROPIC_MODEL_LIGHT

    # Verificar se precisa de tools → Sonnet
    for keyword in TOOL_KEYWORDS:
        if keyword in text_lower:
            return settings.ANTHROPIC_MODEL

    # Mensagens curtas sem keywords de tools → Haiku
    if len(text_lower.split()) <= 5:
        return settings.ANTHROPIC_MODEL_LIGHT

    # Default → Sonnet (para segurança)
    return settings.ANTHROPIC_MODEL


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

        # Rate limiting por usuário
        rate_check = await self._check_user_rate_limit(phone)
        if not rate_check["allowed"]:
            return MCPResponse(
                text=rate_check["message"],
                tokens_used={"input": 0, "output": 0, "blocked": True},
            )

        # Verificar cache para mensagens de texto
        if message_type == "text":
            cached = await self._get_cached_response(phone, content)
            if cached:
                logger.info(f"💾 Cache hit para {phone}: {content[:30]}")
                return MCPResponse(
                    text=cached,
                    tokens_used={"input": 0, "output": 0, "cached": True},
                )

        # Recuperar histórico da conversa (LIMITADO)
        conversation = await self._get_conversation(phone)

        # Se for imagem, processar com Vision (sempre Sonnet)
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

        # Prompt caching: system prompt como bloco cacheável
        system = self._build_system_prompt(user_id=user_id)

        try:
            response = await self.client.messages.create(
                model=settings.ANTHROPIC_MODEL,  # Vision sempre com Sonnet
                max_tokens=2048,
                system=system,
                messages=messages,
                tools=TOOL_DEFINITIONS,
            )

            # Monitorar tokens
            await self._track_tokens(phone, response)

            result_text = await self._handle_tool_loop(
                response, messages, system, phone
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

        # Roteamento de modelo: Haiku para simples, Sonnet para complexo
        model = _select_model(text)
        use_tools = model == settings.ANTHROPIC_MODEL

        # System prompt: com cache_control apenas para Sonnet
        # Haiku exige mínimo 2048 tokens para prompt caching
        system = self._build_system_prompt(
            user_id=user_id, name=name, use_cache=use_tools
        )

        # Se for Haiku, não mandar tools (economia extra)
        tools = TOOL_DEFINITIONS if use_tools else None

        try:
            create_kwargs = {
                "model": model,
                "max_tokens": 1024 if not use_tools else 2048,
                "system": system,
                "messages": messages,
            }
            if tools:
                create_kwargs["tools"] = tools

            response = await self.client.messages.create(**create_kwargs)

            # Monitorar tokens
            tokens_used = await self._track_tokens(phone, response)

        except anthropic.NotFoundError:
            # Modelo Haiku indisponível → fallback para Sonnet
            if model != settings.ANTHROPIC_MODEL:
                logger.warning(f"⚠️ Modelo {model} indisponível, usando Sonnet")
                model = settings.ANTHROPIC_MODEL
                response = await self.client.messages.create(
                    model=model,
                    max_tokens=2048,
                    system=self._build_system_prompt(user_id=user_id, name=name, use_cache=True),
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                )
                tokens_used = await self._track_tokens(phone, response)
                use_tools = True
            else:
                raise

            # Se Haiku respondeu mas precisa de tool, re-rotear para Sonnet
            first_block = response.content[0] if response.content else None
            needs_reroute = (
                not use_tools
                and response.stop_reason == "end_turn"
                and first_block
                and hasattr(first_block, "text")
                and any(
                    kw in first_block.text.lower()
                    for kw in ["não consigo", "não tenho acesso", "preciso de"]
                )
            )
            if needs_reroute:
                logger.info(f"🔄 Re-roteando para Sonnet: {text[:30]}")
                response = await self.client.messages.create(
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=2048,
                    system=system,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                )
                tokens_used = await self._track_tokens(phone, response)

            result_text = await self._handle_tool_loop(
                response, messages, system, phone
            )
        except anthropic.APIError as e:
            logger.error(f"Erro na API Anthropic: {e}")
            result_text = "❌ Ops, tive um problema. Tente novamente em instantes."
            tokens_used = {"input": 0, "output": 0, "error": True}
        except Exception as e:
            logger.error(f"Erro inesperado no processamento: {e}")
            result_text = "❌ Algo deu errado. Tente novamente."
            tokens_used = {"input": 0, "output": 0, "error": True}

        # Salvar no histórico
        await self._save_conversation(phone, "user", text)
        await self._save_conversation(phone, "assistant", result_text)

        # Salvar cache (apenas para respostas sem tool_use e sem erro)
        if not tokens_used.get("had_tool_use") and not tokens_used.get("error"):
            await self._cache_response(phone, text, result_text)

        logger.info(
            f"📊 Modelo: {model.split('/')[-1]} | "
            f"Tokens: {tokens_used.get('input', 0)}in/{tokens_used.get('output', 0)}out | "
            f"User: {phone}"
        )

        return MCPResponse(text=result_text, tokens_used=tokens_used)

    async def _handle_tool_loop(
        self,
        response,
        messages: list[dict],
        system: list[dict],
        phone: str,
    ) -> str:
        """Executa tools em loop até a LLM retornar texto final."""
        max_iterations = 5  # Reduzido de 10 para 5

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

            # Monitorar tokens de cada iteração do loop
            await self._track_tokens(phone, response)

        # Extrair texto final
        return "".join(
            block.text
            for block in response.content
            if hasattr(block, "text")
        )

    # --- Prompt Caching ---

    def _build_system_prompt(
        self, user_id: str, name: str = "Usuário", use_cache: bool = True
    ) -> list[dict]:
        """
        Constrói system prompt com suporte a prompt caching da Anthropic.
        O bloco estático é cacheado apenas para Sonnet (Haiku exige mín 2048 tokens).
        """
        static_block: dict = {"type": "text", "text": SYSTEM_PROMPT}
        if use_cache:
            static_block["cache_control"] = {"type": "ephemeral"}

        return [
            static_block,
            {
                "type": "text",
                "text": (
                    f"User ID do usuário atual: {user_id}\n"
                    f"Nome do usuário: {name}\n"
                    f"Data de hoje: {date.today().isoformat()}"
                ),
            },
        ]

    # --- Rate Limiting por Usuário ---

    async def _check_user_rate_limit(self, phone: str) -> dict:
        """Verifica rate limit por usuário (hora e dia)."""
        try:
            # Limite por hora
            key_hour = f"rl:user:hour:{phone}"
            current_hour = await redis_client.incr(key_hour)
            if current_hour == 1:
                await redis_client.expire(key_hour, 3600)

            if current_hour > settings.LLM_MAX_MESSAGES_PER_USER_HOUR:
                logger.warning(
                    f"⚠️ Rate limit/hora excedido: {phone} ({current_hour} msgs)"
                )
                return {
                    "allowed": False,
                    "message": (
                        "⏳ Você enviou muitas mensagens. "
                        "Aguarde alguns minutos e tente novamente."
                    ),
                }

            # Limite por dia
            key_day = f"rl:user:day:{phone}"
            current_day = await redis_client.incr(key_day)
            if current_day == 1:
                await redis_client.expire(key_day, 86400)

            if current_day > settings.LLM_MAX_MESSAGES_PER_USER_DAY:
                logger.warning(
                    f"⚠️ Rate limit/dia excedido: {phone} ({current_day} msgs)"
                )
                return {
                    "allowed": False,
                    "message": (
                        "⏳ Você atingiu o limite diário de mensagens. "
                        "Tente novamente amanhã! 💤"
                    ),
                }

            return {"allowed": True}

        except Exception as e:
            logger.warning(f"Rate limit check falhou: {e}")
            return {"allowed": True}  # Fail open

    # --- Cache de Respostas ---

    async def _get_cached_response(self, phone: str, text: str) -> Optional[str]:
        """Busca resposta cacheada para mensagens idênticas recentes."""
        try:
            cache_key = self._cache_key(phone, text)
            cached = await redis_client.get(cache_key)
            return cached
        except Exception:
            return None

    async def _cache_response(self, phone: str, text: str, response: str):
        """Salva resposta no cache com TTL curto."""
        try:
            cache_key = self._cache_key(phone, text)
            await redis_client.setex(
                cache_key, settings.LLM_CACHE_TTL, response
            )
        except Exception as e:
            logger.warning(f"Erro ao salvar cache: {e}")

    @staticmethod
    def _cache_key(phone: str, text: str) -> str:
        """Gera chave de cache baseada no telefone + texto normalizado."""
        normalized = text.strip().lower()
        text_hash = hashlib.md5(normalized.encode()).hexdigest()[:12]
        return f"cache:llm:{phone}:{text_hash}"

    # --- Monitoramento de Tokens ---

    async def _track_tokens(self, phone: str, response) -> dict:
        """Rastreia tokens consumidos por usuário e globalmente."""
        try:
            input_tokens = getattr(response.usage, "input_tokens", 0)
            output_tokens = getattr(response.usage, "output_tokens", 0)
            cache_read = getattr(response.usage, "cache_read_input_tokens", 0)
            cache_create = getattr(response.usage, "cache_creation_input_tokens", 0)
            had_tool_use = response.stop_reason == "tool_use"

            today = date.today().isoformat()

            # Tokens por usuário (diário)
            user_key = f"tokens:user:{phone}:{today}"
            await redis_client.hincrby(user_key, "input", input_tokens)
            await redis_client.hincrby(user_key, "output", output_tokens)
            await redis_client.hincrby(user_key, "cache_read", cache_read)
            await redis_client.hincrby(user_key, "requests", 1)
            await redis_client.expire(user_key, 172800)  # 2 dias

            # Tokens global (diário)
            global_key = f"tokens:global:{today}"
            await redis_client.hincrby(global_key, "input", input_tokens)
            await redis_client.hincrby(global_key, "output", output_tokens)
            await redis_client.hincrby(global_key, "cache_read", cache_read)
            await redis_client.hincrby(global_key, "cache_create", cache_create)
            await redis_client.hincrby(global_key, "requests", 1)
            await redis_client.expire(global_key, 604800)  # 7 dias

            # Calcular custo estimado e verificar alerta
            await self._check_cost_alert(today)

            logger.debug(
                f"📈 Tokens: {input_tokens}in/{output_tokens}out "
                f"(cache_read={cache_read}) | User: {phone}"
            )

            return {
                "input": input_tokens,
                "output": output_tokens,
                "cache_read": cache_read,
                "had_tool_use": had_tool_use,
            }

        except Exception as e:
            logger.warning(f"Erro ao rastrear tokens: {e}")
            return {"input": 0, "output": 0}

    async def _check_cost_alert(self, today: str):
        """Verifica se o custo diário ultrapassou o limite configurado."""
        try:
            global_key = f"tokens:global:{today}"
            data = await redis_client.hgetall(global_key)

            if not data:
                return

            input_tokens = int(data.get("input", 0))
            output_tokens = int(data.get("output", 0))

            # Preços Claude Sonnet 4 (estimativa conservadora)
            cost_input = (input_tokens / 1_000_000) * 3.00
            cost_output = (output_tokens / 1_000_000) * 15.00
            total_cost = cost_input + cost_output

            # Alertar apenas uma vez por dia
            alert_key = f"cost:alert:{today}"
            already_alerted = await redis_client.exists(alert_key)

            if total_cost >= settings.LLM_COST_ALERT_DAILY_USD and not already_alerted:
                logger.critical(
                    f"🚨 ALERTA DE CUSTO! Custo diário estimado: ${total_cost:.2f} "
                    f"(limite: ${settings.LLM_COST_ALERT_DAILY_USD:.2f}) | "
                    f"Input: {input_tokens:,} tokens | Output: {output_tokens:,} tokens | "
                    f"Requests: {data.get('requests', 0)}"
                )
                await redis_client.setex(alert_key, 86400, "1")

        except Exception as e:
            logger.warning(f"Erro ao verificar custo: {e}")

    # --- Gerenciamento de conversa (Redis) ---

    async def _get_conversation(self, phone: str) -> list[dict]:
        """
        Recupera histórico recente do Redis.
        LIMITADO para economizar tokens — dados financeiros permanecem
        acessíveis via tools (database).
        """
        try:
            max_msgs = settings.LLM_MAX_CONVERSATION_MESSAGES
            raw = await redis_client.lrange(f"conv:{phone}", -max_msgs, -1)
            return [json.loads(msg) for msg in raw] if raw else []
        except Exception as e:
            logger.warning(f"Erro ao ler conversa do Redis: {e}")
            return []

    async def _save_conversation(self, phone: str, role: str, content: str):
        """Salva mensagem no histórico com TTL configurável."""
        try:
            key = f"conv:{phone}"
            max_msgs = settings.LLM_MAX_CONVERSATION_MESSAGES
            await redis_client.rpush(
                key, json.dumps({"role": role, "content": content})
            )
            await redis_client.ltrim(key, -max_msgs, -1)
            await redis_client.expire(key, settings.LLM_CONVERSATION_TTL)
        except Exception as e:
            logger.warning(f"Erro ao salvar conversa no Redis: {e}")
