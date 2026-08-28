import { defineAgentChatElement } from "./element";

if (typeof window !== "undefined" && window.customElements) {
  defineAgentChatElement(window.customElements);
}
