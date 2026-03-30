"""Tool: Criar categoria personalizada."""

from app.config.database import async_session
from app.services.finance.category_service import CategoryService


async def criar_categoria(
    user_id: str,
    nome: str,
    emoji: str = None,
) -> str:
    """Cria uma categoria personalizada para o usuário."""
    service = CategoryService()

    try:
        async with async_session() as session:
            category = await service.create_custom(
                session=session,
                user_id=user_id,
                name=nome,
                emoji=emoji,
            )
            await session.commit()

        label = f"{category.emoji} {category.name}"
        return (
            f"✅ Categoria *{label}* criada com sucesso!\n\n"
            f"Agora você pode usá-la ao registrar gastos ou entradas."
        )

    except ValueError:
        return f"⚠️ Já existe uma categoria com o nome *{nome}*."
    except Exception as e:
        return f"❌ Erro ao criar categoria: {str(e)}"
