export const AGENT_CHAT_ELEMENT_NAME = "agent-chat";

export function registerAgentChatElement(
  registry: CustomElementRegistry,
  ElementConstructor: CustomElementConstructor,
  name = AGENT_CHAT_ELEMENT_NAME,
) {
  const existing = registry.get(name);
  if (existing) return existing;
  registry.define(name, ElementConstructor);
  return ElementConstructor;
}
