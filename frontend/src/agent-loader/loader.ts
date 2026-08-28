type LoaderStatus = "idle" | "opening" | "ready" | "failed";

interface PageContext {
  resourceType?: string;
  resourceId?: string;
  [key: string]: unknown;
}

interface BootstrapResponse {
  access_token: string;
  expires_in: number;
  api_base_url: string;
  widget: {
    version: string;
    protocol_version: "1";
  };
}

type BootstrapProvider = () => Promise<BootstrapResponse>;

interface AgentChatElement extends HTMLElement {
  configure(options: {
    apiBaseUrl: string;
    token: { access_token: string; expires_in: number };
    getToken: () => Promise<{ access_token: string; expires_in: number }>;
    context: PageContext;
  }): void;
  open(): Promise<void>;
  close(): void;
  updateContext(context: PageContext): void;
  destroy(): void;
}

type LoaderEvent = "ready" | "open" | "close" | "error" | "destroy";
type LoaderListener = (detail?: unknown) => void;

class LoaderRequestError extends Error {
  readonly displayMessage?: string;

  constructor(message: string, displayMessage?: string) {
    super(message);
    this.name = "LoaderRequestError";
    this.displayMessage = displayMessage;
  }
}

interface EnterpriseAgentApi {
  readonly status: LoaderStatus;
  configure(options: { getBootstrap?: BootstrapProvider }): void;
  open(options?: { context?: PageContext }): Promise<void>;
  close(): void;
  destroy(): void;
  setContext(context: PageContext): void;
  on(event: LoaderEvent, listener: LoaderListener): () => void;
}

interface EnterpriseAgentWindow extends Window {
  EnterpriseAgent?: EnterpriseAgentApi;
}

const VERSION_PATTERN = /^\d+\.\d+\.\d+$/;
const enterpriseWindow = window as EnterpriseAgentWindow;
const loaderScript = document.currentScript as HTMLScriptElement | null;

if (!loaderScript?.src) {
  throw new Error("Enterprise Agent Loader must be loaded from a script src.");
}

const assetOrigin = new URL(loaderScript.src, window.location.href).origin;
const configuredBootstrapEndpoint =
  loaderScript.dataset.bootstrapEndpoint?.trim() || "/api/agent/bootstrap";
const bootstrapUrl = new URL(configuredBootstrapEndpoint, window.location.href);

if (bootstrapUrl.origin !== window.location.origin) {
  throw new Error("Enterprise Agent bootstrap endpoint must use the business page origin.");
}

if (enterpriseWindow.EnterpriseAgent) {
  throw new Error("Enterprise Agent Loader can only be initialized once per page.");
}

let status: LoaderStatus = "idle";
let element: AgentChatElement | null = null;
let openingPromise: Promise<void> | null = null;
let pageContext: PageContext = {};
let initializedVersion = "";
let initializedApiBaseUrl = "";
let lifecycleVersion = 0;
const listeners = new Map<LoaderEvent, Set<LoaderListener>>();

function emit(event: LoaderEvent, detail?: unknown) {
  for (const listener of listeners.get(event) || []) {
    listener(detail);
  }
}

function assertBootstrap(payload: unknown): BootstrapResponse {
  if (!payload || typeof payload !== "object") {
    throw new Error("Business bootstrap returned an invalid response.");
  }
  const value = payload as Partial<BootstrapResponse>;
  if (!value.access_token || typeof value.access_token !== "string") {
    throw new Error("Business bootstrap did not return an access token.");
  }
  if (!Number.isFinite(value.expires_in) || Number(value.expires_in) <= 0) {
    throw new Error("Business bootstrap returned an invalid token lifetime.");
  }
  if (!value.api_base_url || !/^https?:\/\//.test(value.api_base_url)) {
    throw new Error("Business bootstrap returned an invalid Agent API URL.");
  }
  if (!value.widget || !VERSION_PATTERN.test(String(value.widget.version || ""))) {
    throw new Error("Business bootstrap returned an invalid Widget version.");
  }
  if (value.widget.protocol_version !== "1") {
    throw new Error("Business bootstrap returned an unsupported Widget protocol.");
  }
  return value as BootstrapResponse;
}

async function readBootstrapDisplayMessage(response: Response) {
  if (response.status < 400 || response.status >= 500) {
    return undefined;
  }
  try {
    const payload = (await response.json()) as { message?: unknown };
    const message = typeof payload?.message === "string" ? payload.message.trim() : "";
    return message && message.length <= 200 ? message : undefined;
  } catch {
    return undefined;
  }
}

async function requestDefaultBootstrap(): Promise<BootstrapResponse> {
  const response = await fetch(bootstrapUrl, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "EnterpriseAgentLoader",
    },
    body: "{}",
  });
  if (!response.ok) {
    const displayMessage = await readBootstrapDisplayMessage(response);
    throw new LoaderRequestError(
      `Business bootstrap failed with HTTP ${response.status}.`,
      displayMessage,
    );
  }
  return assertBootstrap(await response.json());
}

let getBootstrap: BootstrapProvider = requestDefaultBootstrap;

async function resolveBootstrap() {
  return assertBootstrap(await getBootstrap());
}

async function refreshToken() {
  const bootstrap = await resolveBootstrap();
  if (
    initializedVersion &&
    (bootstrap.widget.version !== initializedVersion ||
      bootstrap.api_base_url.replace(/\/+$/, "") !== initializedApiBaseUrl)
  ) {
    throw new Error("Agent bootstrap configuration changed; destroy and reopen the Widget.");
  }
  return {
    access_token: bootstrap.access_token,
    expires_in: bootstrap.expires_in,
  };
}

function bindElementEvents(target: AgentChatElement) {
  target.addEventListener("agent-chat-open", () => emit("open"));
  target.addEventListener("agent-chat-close", () => emit("close"));
  target.addEventListener("agent-chat-error", (event) => {
    emit("error", (event as CustomEvent).detail);
  });
}

function requireElement() {
  if (!element) {
    throw new Error("Agent Widget initialization did not complete.");
  }
  return element;
}

async function initialize(currentLifecycle: number) {
  const bootstrap = await resolveBootstrap();
  const widgetUrl = new URL(
    `/agent-static/widget/${bootstrap.widget.version}/index.js`,
    assetOrigin,
  );
  await import(/* @vite-ignore */ widgetUrl.href);

  if (currentLifecycle !== lifecycleVersion) {
    return;
  }
  if (!customElements.get("agent-chat")) {
    throw new Error("Agent Widget did not register the agent-chat element.");
  }

  initializedVersion = bootstrap.widget.version;
  initializedApiBaseUrl = bootstrap.api_base_url.replace(/\/+$/, "");
  const target = document.createElement("agent-chat") as AgentChatElement;
  bindElementEvents(target);
  document.body.appendChild(target);
  target.configure({
    apiBaseUrl: initializedApiBaseUrl,
    token: {
      access_token: bootstrap.access_token,
      expires_in: bootstrap.expires_in,
    },
    getToken: refreshToken,
    context: pageContext,
  });
  element = target;
  status = "ready";
  emit("ready", { version: initializedVersion });
}

const api: EnterpriseAgentApi = {
  get status() {
    return status;
  },
  configure(options) {
    if (status !== "idle" || element || openingPromise) {
      throw new Error("Enterprise Agent must be configured before it is opened.");
    }
    if (options.getBootstrap && typeof options.getBootstrap !== "function") {
      throw new Error("Enterprise Agent getBootstrap must be a function.");
    }
    getBootstrap = options.getBootstrap || requestDefaultBootstrap;
  },
  async open(options = {}) {
    if (options.context) {
      pageContext = { ...options.context };
      element?.updateContext(pageContext);
    }
    if (element) {
      await element.open();
      return;
    }
    if (!openingPromise) {
      const currentLifecycle = lifecycleVersion;
      status = "opening";
      const currentOpening = initialize(currentLifecycle)
        .catch((error) => {
          if (currentLifecycle === lifecycleVersion) {
            status = "failed";
            emit("error", error);
          }
          throw error;
        })
        .finally(() => {
          if (openingPromise === currentOpening) {
            openingPromise = null;
          }
        });
      openingPromise = currentOpening;
    }
    const currentLifecycle = lifecycleVersion;
    await openingPromise;
    if (currentLifecycle !== lifecycleVersion) {
      return;
    }
    await requireElement().open();
  },
  close() {
    element?.close();
  },
  destroy() {
    lifecycleVersion += 1;
    element?.destroy();
    element?.remove();
    element = null;
    openingPromise = null;
    pageContext = {};
    initializedVersion = "";
    initializedApiBaseUrl = "";
    status = "idle";
    emit("destroy");
    listeners.clear();
  },
  setContext(context) {
    pageContext = { ...context };
    element?.updateContext(pageContext);
  },
  on(event, listener) {
    const eventListeners = listeners.get(event) || new Set<LoaderListener>();
    eventListeners.add(listener);
    listeners.set(event, eventListeners);
    return () => eventListeners.delete(listener);
  },
};

enterpriseWindow.EnterpriseAgent = api;

export {};
