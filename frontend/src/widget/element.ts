import "element-plus/es/components/icon/style/css";
import "./styles.css";

import { createChatRuntime } from "./create-agent-chat";
import { createElementController } from "./element-controller";
import { registerAgentChatElement } from "./register-element";
import { AGENT_CHAT_CSS } from "./shadow-style";
import type {
  AgentChatContext,
  AgentChatInitOptions,
} from "./types";

export interface AgentChatElement extends HTMLElement {
  configure(options: AgentChatInitOptions): void;
  open(): Promise<void>;
  close(): void;
  toggle(): Promise<void>;
  updateContext(context: AgentChatContext): void;
  sendMessage(message: string): Promise<void>;
  refreshToken(): Promise<string>;
  destroy(): void;
}

function emit(element: HTMLElement, name: string, detail?: unknown) {
  element.dispatchEvent(
    new CustomEvent(name, {
      bubbles: true,
      composed: true,
      detail,
    }),
  );
}

function createElementClass(): CustomElementConstructor {
  return class AgentChatCustomElement extends HTMLElement implements AgentChatElement {
    private readonly controller;

    constructor() {
      super();
      const shadowRoot = this.attachShadow({ mode: "open" });
      const style = document.createElement("style");
      style.textContent = AGENT_CHAT_CSS;
      shadowRoot.appendChild(style);
      this.controller = createElementController((options: AgentChatInitOptions) =>
        createChatRuntime().init({ ...options, container: shadowRoot }),
      );
    }

    configure(options: AgentChatInitOptions) {
      this.controller.configure(options);
      emit(this, "agent-chat-ready");
    }

    async open() {
      try {
        await this.controller.open();
        emit(this, "agent-chat-open");
      } catch (error) {
        emit(this, "agent-chat-error", error);
        throw error;
      }
    }

    close() {
      this.controller.close();
      emit(this, "agent-chat-close");
    }

    toggle() {
      return this.controller.toggle();
    }

    updateContext(context: AgentChatContext) {
      this.controller.updateContext(context);
    }

    sendMessage(message: string) {
      return this.controller.sendMessage(message);
    }

    refreshToken() {
      return this.controller.refreshToken();
    }

    destroy() {
      this.controller.destroy();
    }

    disconnectedCallback() {
      this.destroy();
    }
  };
}

export function defineAgentChatElement(
  registry: CustomElementRegistry = customElements,
): CustomElementConstructor {
  const existing = registry.get("agent-chat");
  if (existing) return existing;
  return registerAgentChatElement(registry, createElementClass());
}

export function createAgentChatElement(
  options: AgentChatInitOptions,
  container: HTMLElement = document.body,
): AgentChatElement {
  defineAgentChatElement();
  const element = document.createElement("agent-chat") as AgentChatElement;
  container.appendChild(element);
  element.configure(options);
  return element;
}
