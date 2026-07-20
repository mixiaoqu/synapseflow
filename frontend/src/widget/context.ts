import type { WidgetPageContext } from "./client/agent-chat-api";
import type { AgentChatContext } from "./types";

function optionalString(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function normalizeAttributes(value: unknown) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? { ...(value as Record<string, unknown>) }
    : undefined;
}

export function normalizePageContext(context: AgentChatContext = {}): WidgetPageContext {
  const normalized: WidgetPageContext = {
    schema_version: 1,
    page_type:
      optionalString(context.page_type ?? context.pageType ?? context.page) ?? "external",
  };
  const optionalFields = {
    route_name: optionalString(context.route_name ?? context.routeName),
    route_path: optionalString(context.route_path ?? context.route),
    entity_type: optionalString(
      context.entity_type ?? context.entityType ?? context.resourceType,
    ),
    entity_id: optionalString(context.entity_id ?? context.entityId ?? context.resourceId),
    entity_name: optionalString(
      context.entity_name ?? context.entityName ?? context.resourceName,
    ),
    attributes: normalizeAttributes(context.attributes),
  };
  for (const [key, value] of Object.entries(optionalFields)) {
    if (value !== undefined) Object.assign(normalized, { [key]: value });
  }
  return normalized;
}

export async function resolvePageContext(
  baseContext: AgentChatContext,
  getContext?: () => AgentChatContext | Promise<AgentChatContext>,
) {
  const latest = getContext ? await getContext() : null;
  return normalizePageContext({ ...baseContext, ...(latest || {}) });
}
