"""Tool: Remover categoria personalizada."""

from app.config.database import async_session
from app.services.finance.category_service import CategoryService


async def remover_categoria(
    user_id: str,
    nome: str,
) -> str:
    """Remove uma categoria personalizada do usuário."""
    service = CategoryService()

    try:
        async with async_session() as session:
            removed = await service.delete_custom(
                session=session,
                user_id=user_id,
                name=nome,
            )
            await session.commit()

        if not removed:
            return f"⚠️ Categoria personalizada *{nome}* não encontrada."

        return f"✅ Categoria *{nome}* removida com sucesso."

    except ValueError:
        return "⚠️ Categorias padrão não podem ser removidas."
    except Exception as e:
        return f"❌ Erro ao remover categoria: {str(e)}"
