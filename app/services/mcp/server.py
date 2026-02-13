"""
Definição das tools MCP e registro no dicionário de handlers.
"""

from app.services.mcp.tools.registrar_gasto import registrar_gasto
from app.services.mcp.tools.registrar_entrada import registrar_entrada
from app.services.mcp.tools.remover_lancamento import remover_lancamento
from app.services.mcp.tools.editar_lancamento import editar_lancamento
from app.services.mcp.tools.relatorio_periodo import relatorio_periodo
from app.services.mcp.tools.relatorio_categoria import relatorio_categoria
from app.services.mcp.tools.saldo_atual import saldo_atual
from app.services.mcp.tools.ultimos_lancamentos import ultimos_lancamentos
from app.services.mcp.tools.listar_categorias import listar_categorias
from app.services.mcp.tools.processar_comprovante import processar_comprovante


# Definição das tools para o Anthropic API (tool_use)
TOOL_DEFINITIONS = [
    {
        "name": "registrar_gasto",
        "description": (
            "Registra um gasto/despesa do usuário. Use quando ele disser que gastou, "
            "pagou, comprou algo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "valor": {"type": "number", "description": "Valor em reais"},
                "categoria": {
                    "type": "string",
                    "description": "Ex: alimentação, transporte, lazer, saúde",
                },
                "descricao": {
                    "type": "string",
                    "description": "Descrição breve do gasto",
                },
                "data": {
                    "type": "string",
                    "description": "Data no formato YYYY-MM-DD. Se não informada, usar hoje.",
                },
            },
            "required": ["user_id", "valor"],
        },
    },
    {
        "name": "registrar_entrada",
        "description": "Registra uma receita/entrada de dinheiro.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "valor": {"type": "number"},
                "categoria": {"type": "string"},
                "descricao": {"type": "string"},
                "data": {"type": "string"},
            },
            "required": ["user_id", "valor"],
        },
    },
    {
        "name": "remover_lancamento",
        "description": (
            "Remove/exclui um lançamento (gasto ou entrada). "
            "O usuário pode pedir por ID, por descrição recente ou pelo último registro. "
            "Se ambíguo, liste os candidatos e peça confirmação."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "lancamento_id": {
                    "type": "string",
                    "description": "ID do lançamento a remover",
                },
                "busca": {
                    "type": "string",
                    "description": "Texto para buscar o lançamento (ex: 'mercado ontem')",
                },
                "confirmar": {
                    "type": "boolean",
                    "description": "Se True, confirma a exclusão",
                },
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "editar_lancamento",
        "description": "Edita um lançamento existente (valor, categoria, descrição ou data).",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "lancamento_id": {"type": "string"},
                "novo_valor": {"type": "number"},
                "nova_categoria": {"type": "string"},
                "nova_descricao": {"type": "string"},
                "nova_data": {"type": "string"},
            },
            "required": ["user_id", "lancamento_id"],
        },
    },
    {
        "name": "relatorio_periodo",
        "description": "Gera relatório financeiro por período (semana, mês, ano, ou datas específicas).",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "periodo": {
                    "type": "string",
                    "description": "Ex: 'esta semana', 'janeiro 2026', 'últimos 30 dias'",
                },
                "data_inicio": {"type": "string"},
                "data_fim": {"type": "string"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "relatorio_categoria",
        "description": "Gera relatório agrupado por categoria.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "categoria": {
                    "type": "string",
                    "description": "Filtrar por categoria específica (opcional)",
                },
                "periodo": {"type": "string"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "saldo_atual",
        "description": "Retorna o saldo atual do usuário (total de entradas - total de saídas).",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "ultimos_lancamentos",
        "description": "Lista os últimos lançamentos do usuário.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "quantidade": {"type": "integer", "default": 5},
                "tipo": {
                    "type": "string",
                    "description": "INCOME, EXPENSE ou ambos",
                },
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "listar_categorias",
        "description": "Lista todas as categorias disponíveis para o usuário.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "processar_comprovante",
        "description": (
            "Processa uma imagem de comprovante enviada pelo usuário. "
            "Extrai valor, estabelecimento, data e categoria usando IA Vision."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "media_id": {
                    "type": "string",
                    "description": "ID da mídia no WhatsApp",
                },
            },
            "required": ["user_id", "media_id"],
        },
    },
]


# Mapeamento nome → handler
TOOL_HANDLERS = {
    "registrar_gasto": registrar_gasto,
    "registrar_entrada": registrar_entrada,
    "remover_lancamento": remover_lancamento,
    "editar_lancamento": editar_lancamento,
    "relatorio_periodo": relatorio_periodo,
    "relatorio_categoria": relatorio_categoria,
    "saldo_atual": saldo_atual,
    "ultimos_lancamentos": ultimos_lancamentos,
    "listar_categorias": listar_categorias,
    "processar_comprovante": processar_comprovante,
}
