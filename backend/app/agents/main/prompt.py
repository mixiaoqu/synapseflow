"""Prompt helpers owned by the top-level Agent response."""


def build_page_context_block(
    page_config: dict | None = None,
    page_context: dict | str | None = None,
) -> str:
    if isinstance(page_context, str):
        return page_context.strip() or "(none)"

    page_config = page_config or {}
    page_context = page_context or {}
    page_name = str(page_config.get("page_name") or "").strip()
    page_description = str(page_config.get("page_description") or "").strip()
    assistant_intro = str(page_config.get("assistant_intro") or "").strip()
    page_type = str(page_context.get("page_type") or "").strip()
    route_name = str(page_context.get("route_name") or "").strip()
    route_path = str(page_context.get("route_path") or "").strip()
    entity_type = str(page_context.get("entity_type") or "").strip()
    entity_id = str(page_context.get("entity_id") or "").strip()
    entity_name = str(page_context.get("entity_name") or "").strip()

    page_lines: list[str] = []
    if page_name:
        page_lines.append(f"页面名称：{page_name}")
    if page_type:
        page_lines.append(f"页面标识：{page_type}")
    if route_name:
        page_lines.append(f"路由名称：{route_name}")
    if route_path:
        page_lines.append(f"路由路径：{route_path}")
    if entity_type or entity_id or entity_name:
        entity_parts = [part for part in (entity_type, entity_id, entity_name) if part]
        page_lines.append(f"当前业务对象：{' / '.join(entity_parts)}")
    if page_description:
        page_lines.append(f"页面说明：{page_description}")
    if assistant_intro:
        page_lines.append(f"助手入口说明：{assistant_intro}")
    return "\n".join(page_lines) or "(none)"
