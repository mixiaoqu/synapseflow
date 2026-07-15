import { createApp, defineComponent, h, nextTick, reactive, ref } from "vue";
import ElementPlus from "element-plus";

import type { WidgetPageContext } from "@/shared/api/widget";
import WidgetChatPanel from "@/widget/WidgetChatPanel.vue";
import type {
  AgentChatContext,
  AgentChatGlobal,
  AgentChatInitOptions,
  AgentChatInstance,
  AgentChatTokenResult,
} from "@/widget/types";

interface AgentChatCredential {
  token: string;
  expiresAt: number | null;
}

type WidgetChatPanelPublic = {
  sendMessage: (message: string) => Promise<void>;
};

const TOKEN_REFRESH_LEEWAY_MS = 60_000;
const PANEL_VIEWPORT_MARGIN = 16;

function resolveContainer(container?: string | HTMLElement) {
  if (container instanceof HTMLElement) {
    return container;
  }

  if (typeof container === "string") {
    const target = document.querySelector<HTMLElement>(container);
    if (!target) {
      throw new Error(`AgentChat container not found: ${container}`);
    }
    return target;
  }

  return document.body;
}

function normalizeSize(value: number | string | undefined, fallback: string) {
  if (typeof value === "number") {
    return `${value}px`;
  }
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  return fallback;
}

function normalizeCredential(
  result: AgentChatTokenResult | null | undefined,
): AgentChatCredential {
  if (typeof result === "string") {
    return { token: result.trim(), expiresAt: null };
  }
  if (!result) {
    return { token: "", expiresAt: null };
  }

  const directToken = result.access_token ?? result.accessToken ?? result.token;
  const token = directToken?.trim() ?? "";
  const expiresInSeconds = result.expires_in_seconds ?? result.expiresInSeconds;
  const expiresAt =
    typeof expiresInSeconds === "number" && Number.isFinite(expiresInSeconds)
      ? Date.now() + Math.max(0, expiresInSeconds) * 1000
      : null;

  return { token, expiresAt };
}

function optionalContextValue(value: unknown) {
  const normalized = typeof value === "string" ? value.trim() : "";
  return normalized || undefined;
}

function buildPageContext(context: AgentChatContext): WidgetPageContext {
  const pageType = String(
    context.page_type ?? context.pageType ?? context.page ?? "external",
  ).trim() || "external";

  return {
    schema_version: 1,
    page_type: pageType,
    route_name: optionalContextValue(context.route_name ?? context.routeName),
    route_path: optionalContextValue(context.route),
    entity_type: optionalContextValue(context.entity_type ?? context.entityType),
    entity_id: optionalContextValue(context.entity_id ?? context.entityId),
    entity_name: optionalContextValue(context.entity_name ?? context.entityName),
  };
}

function createHost(options: AgentChatInitOptions) {
  const container = resolveContainer(options.container);
  const host = document.createElement("div");
  host.className = "agent-chat-widget-host";
  host.style.setProperty("--agent-chat-width", normalizeSize(options.width, "420px"));
  host.style.setProperty("--agent-chat-height", normalizeSize(options.height, "680px"));
  container.appendChild(host);
  return host;
}

export function createAgentChat(): AgentChatGlobal {
  return {
    init(options: AgentChatInitOptions): AgentChatInstance {
      const host = createHost(options);
      const isOpen = ref(Boolean(options.defaultOpen));
      const credential = ref(normalizeCredential(options.token));
      const shouldMountPanel = ref(Boolean(credential.value.token));
      const context = reactive<AgentChatContext>({ ...(options.context ?? {}) });
      const pageRef = ref<WidgetChatPanelPublic | null>(null);
      let refreshTimer: number | null = null;
      let refreshPromise: Promise<string> | null = null;
      let activePointerId: number | null = null;
      let dragStartX = 0;
      let dragStartY = 0;
      let panelStartLeft = 0;
      let panelStartTop = 0;

      function resetPanelPosition() {
        host.style.removeProperty("left");
        host.style.removeProperty("top");
      }

      function clamp(value: number, min: number, max: number) {
        return Math.min(Math.max(value, min), Math.max(min, max));
      }

      function movePanel(left: number, top: number) {
        const rect = host.getBoundingClientRect();
        const maxLeft = document.documentElement.clientWidth - rect.width - PANEL_VIEWPORT_MARGIN;
        const maxTop = document.documentElement.clientHeight - rect.height - PANEL_VIEWPORT_MARGIN;
        host.style.left = `${clamp(left, PANEL_VIEWPORT_MARGIN, maxLeft)}px`;
        host.style.top = `${clamp(top, PANEL_VIEWPORT_MARGIN, maxTop)}px`;
      }

      function handlePointerMove(event: PointerEvent) {
        if (event.pointerId !== activePointerId) {
          return;
        }
        movePanel(
          panelStartLeft + event.clientX - dragStartX,
          panelStartTop + event.clientY - dragStartY,
        );
      }

      function stopDragging(event?: PointerEvent) {
        if (event && event.pointerId !== activePointerId) {
          return;
        }
        activePointerId = null;
        host.classList.remove("agent-chat-widget-host--dragging");
        window.removeEventListener("pointermove", handlePointerMove);
        window.removeEventListener("pointerup", stopDragging);
        window.removeEventListener("pointercancel", stopDragging);
      }

      function startDragging(event: PointerEvent) {
        if (event.button !== 0 || window.innerWidth <= 640) {
          return;
        }
        event.preventDefault();
        const rect = host.getBoundingClientRect();
        host.style.left = `${rect.left}px`;
        host.style.top = `${rect.top}px`;
        dragStartX = event.clientX;
        dragStartY = event.clientY;
        panelStartLeft = rect.left;
        panelStartTop = rect.top;
        activePointerId = event.pointerId;
        host.classList.add("agent-chat-widget-host--dragging");
        window.addEventListener("pointermove", handlePointerMove);
        window.addEventListener("pointerup", stopDragging);
        window.addEventListener("pointercancel", stopDragging);
      }

      function handleViewportResize() {
        if (isOpen.value && host.style.left && host.style.top) {
          movePanel(Number.parseFloat(host.style.left), Number.parseFloat(host.style.top));
        }
      }

      function clearRefreshTimer() {
        if (refreshTimer !== null) {
          window.clearTimeout(refreshTimer);
          refreshTimer = null;
        }
      }

      function scheduleTokenRefresh() {
        clearRefreshTimer();
        if (!options.getToken || credential.value.expiresAt === null) {
          return;
        }

        const delay = Math.max(
          0,
          credential.value.expiresAt - Date.now() - TOKEN_REFRESH_LEEWAY_MS,
        );
        refreshTimer = window.setTimeout(() => {
          if (isOpen.value) {
            void refreshToken().catch(() => undefined);
          }
        }, delay);
      }

      function hasUsableToken() {
        if (!credential.value.token) {
          return false;
        }
        return (
          credential.value.expiresAt === null ||
          credential.value.expiresAt - Date.now() > TOKEN_REFRESH_LEEWAY_MS
        );
      }

      async function refreshToken() {
        if (refreshPromise) {
          return refreshPromise;
        }
        const getToken = options.getToken;
        if (!getToken) {
          if (credential.value.token) {
            return credential.value.token;
          }
          throw new Error("AgentChat token or getToken is required.");
        }

        refreshPromise = (async () => {
          const nextCredential = normalizeCredential(await getToken());
          if (!nextCredential.token) {
            throw new Error("AgentChat getToken did not return a token.");
          }
          credential.value = nextCredential;
          scheduleTokenRefresh();
          return nextCredential.token;
        })();

        try {
          return await refreshPromise;
        } finally {
          refreshPromise = null;
        }
      }

      const Root = defineComponent({
        setup() {
          return () =>
            h(
              "div",
              {
                class: [
                  "agent-chat-widget",
                  isOpen.value ? "agent-chat-widget--open" : "agent-chat-widget--closed",
                ],
              },
              shouldMountPanel.value
                ? [
                    h(WidgetChatPanel, {
                      ref: pageRef,
                      token: credential.value.token,
                      pageContext: buildPageContext(context),
                      refreshToken,
                      onClose: close,
                      onDragStart: startDragging,
                    }),
                  ]
                : [],
            );
        },
      });

      const app = createApp(Root);
      app.use(ElementPlus);
      app.mount(host);

      window.addEventListener("resize", handleViewportResize);
      scheduleTokenRefresh();
      if (isOpen.value && !hasUsableToken()) {
        void refreshToken()
          .then(() => {
            shouldMountPanel.value = true;
          })
          .catch(() => undefined);
      }

      async function open() {
        if (!hasUsableToken()) {
          await refreshToken();
        }
        shouldMountPanel.value = true;
        isOpen.value = true;
      }

      function close() {
        stopDragging();
        isOpen.value = false;
        resetPanelPosition();
      }

      return {
        open,
        close,
        async toggle() {
          if (isOpen.value) {
            close();
            return;
          }
          await open();
        },
        updateContext(nextContext: AgentChatContext) {
          (Object.keys(context) as Array<keyof AgentChatContext>).forEach((key) => {
            delete context[key];
          });
          Object.assign(context, nextContext);
        },
        async sendMessage(message: string) {
          await open();
          await nextTick();
          await pageRef.value?.sendMessage(message);
        },
        refreshToken,
        destroy() {
          stopDragging();
          clearRefreshTimer();
          window.removeEventListener("resize", handleViewportResize);
          app.unmount();
          host.remove();
        },
      };
    },
  };
}
