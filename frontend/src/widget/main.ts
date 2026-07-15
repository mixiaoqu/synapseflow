import "element-plus/dist/index.css";
import "@/styles/index.css";
import "@/widget/styles.css";

import { createAgentChat } from "@/widget/sdk";
import type { AgentChatGlobal } from "@/widget/types";

declare global {
  interface Window {
    AgentChat?: AgentChatGlobal;
  }
}

const agentChat = createAgentChat();

window.AgentChat = agentChat;

export const init = agentChat.init;
export { createAgentChat };
export type {
  AgentChatContext,
  AgentChatGlobal,
  AgentChatInitOptions,
  AgentChatInstance,
  AgentChatTokenResponse,
  AgentChatTokenResult,
} from "@/widget/types";
