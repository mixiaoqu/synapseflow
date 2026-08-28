export interface AgentChatTokenResponse {
  access_token?: string;
  accessToken?: string;
  token?: string;
  expires_in_seconds?: number;
  expires_in?: number;
  expiresInSeconds?: number;
}

export type AgentChatTokenResult = string | AgentChatTokenResponse;

export interface AgentChatContext {
  schemaVersion?: 1;
  schema_version?: 1;
  page?: string;
  pageType?: string;
  page_type?: string;
  route?: string;
  routeName?: string;
  route_name?: string;
  route_path?: string;
  entityType?: string;
  entity_type?: string;
  resourceType?: string;
  entityId?: string;
  entity_id?: string;
  resourceId?: string;
  entityName?: string;
  entity_name?: string;
  resourceName?: string;
  attributes?: Record<string, unknown>;
}

export interface AgentChatInitOptions {
  apiBaseUrl: string;
  container?: string | HTMLElement | ShadowRoot;
  token?: AgentChatTokenResult | null;
  getToken?: () => AgentChatTokenResult | Promise<AgentChatTokenResult>;
  context?: AgentChatContext;
  getContext?: () => AgentChatContext | Promise<AgentChatContext>;
  defaultOpen?: boolean;
  width?: number | string;
  height?: number | string;
}

export interface AgentChatInstance {
  open: () => Promise<void>;
  close: () => void;
  toggle: () => Promise<void>;
  updateContext: (context: AgentChatContext) => void;
  sendMessage: (message: string) => Promise<void>;
  refreshToken: () => Promise<string>;
  destroy: () => void;
}

export interface AgentChatGlobal {
  init: (options: AgentChatInitOptions) => AgentChatInstance;
}
