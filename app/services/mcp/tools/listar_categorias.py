"""Tool: Listar categorias."""

from app.services.finance.category_service import CategoryService


async def listar_categorias(user_id: str) -> str:
    """Lista todas as categorias disponíveis, separando padrão das personalizadas."""
    service = CategoryService()
    categories = await service.get_all(user_id)

    if not categories:
        return "📂 Nenhuma categoria encontrada."

    defaults = [c for c in categories if c["is_default"]]
    custom = [c for c in categories if not c["is_default"]]

    lines = ["📂 *Categorias padrão:*"]
    for cat in defaults:
        lines.append(f"  {cat['emoji']} {cat['name']}")

    if custom:
        lines.append("")
        lines.append("✨ *Suas categorias:*")
        for cat in custom:
            lines.append(f"  {cat['emoji']} {cat['name']}")
    else:
        lines.append("")
        lines.append("💡 Crie categorias personalizadas digitando: *criar categoria [nome]*")

    return "\n".join(lines)

