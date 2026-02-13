"""Tool: Listar categorias."""

from app.services.finance.category_service import CategoryService


async def listar_categorias(user_id: str) -> str:
    """Lista todas as categorias disponíveis."""
    service = CategoryService()
    categories = await service.get_all(user_id)

    if not categories:
        return "📂 Nenhuma categoria encontrada."

    lines = ["📂 *Categorias disponíveis:*\n"]
    for cat in categories:
        lines.append(f"  {cat['emoji']} {cat['name']}")

    return "\n".join(lines)
