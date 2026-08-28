import type { AgentChatContext, AgentChatInitOptions, AgentChatInstance } from "./types";

function notConfiguredError() {
  return new Error("Agent Chat element is not configured");
}

export function createElementController(
  createInstance: (options: AgentChatInitOptions) => AgentChatInstance,
) {
  let instance: AgentChatInstance | null = null;

  function requireInstance() {
    if (!instance) throw notConfiguredError();
    return instance;
  }

  return {
    configure(options: AgentChatInitOptions) {
      instance?.destroy();
      instance = createInstance(options);
      return instance;
    },
    open: () => requireInstance().open(),
    close: () => requireInstance().close(),
    toggle: () => requireInstance().toggle(),
    updateContext: (context: AgentChatContext) => requireInstance().updateContext(context),
    sendMessage: (message: string) => requireInstance().sendMessage(message),
    refreshToken: () => requireInstance().refreshToken(),
    destroy() {
      instance?.destroy();
      instance = null;
    },
  };
}
