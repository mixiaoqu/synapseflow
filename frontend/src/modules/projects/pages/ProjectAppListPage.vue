<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import {
  Collection,
  Connection,
  CopyDocument,
  Cpu,
  Delete,
  EditPen,
  Grid,
  Link,
  MoreFilled,
  Plus,
  RefreshRight,
  Search,
  Setting,
} from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import {
  createProjectAppAccess,
  enableProjectAppAccess,
  getProjectAppAccess,
  listAgentTools,
  listProjectAppToolGrants,
  replaceProjectAppToolGrants,
  resetProjectAppAccessSecret,
  revokeProjectAppAccess,
  updateProjectAppAccess,
} from "@/shared/api/agent-integrations";
import { API_BASE_URL } from "@/shared/api/config";
import { listAssistants } from "@/shared/api/assistants";
import { listDocumentCategoriesTree } from "@/shared/api/document-categories";
import { listKnowledgeBases } from "@/shared/api/knowledge-bases";
import {
  createProjectApp,
  deleteProjectApp,
  getProject,
  listProjectApps,
  updateProjectApp,
} from "@/shared/api/projects";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import { AppRequestError, isForbiddenError } from "@/shared/utils/error";
import type { AssistantSummary } from "@/shared/types/assistant";
import type {
  AgentTool,
  AgentToolGrant,
  ProjectAppAccessCredential,
} from "@/shared/types/agent-integration";
import type { DocumentCategoryTreeNode } from "@/shared/types/document-category";
import type { KnowledgeBaseListItem } from "@/shared/types/knowledge-base";
import {
  PROJECT_APP_TERMINAL_TYPE_LABELS,
  type ProjectAppSummary,
  type ProjectAppTerminalType,
  type ProjectAppUpsertPayload,
  type ProjectSummary,
} from "@/shared/types/project";

const route = useRoute();
const project = ref<ProjectSummary | null>(null);
const apps = ref<ProjectAppSummary[]>([]);
const assistants = ref<AssistantSummary[]>([]);
const availableTools = ref<AgentTool[]>([]);
const toolGrants = ref<AgentToolGrant[]>([]);
const knowledgeBases = ref<KnowledgeBaseListItem[]>([]);
const categoryTree = ref<DocumentCategoryTreeNode[]>([]);
const categoryPath = ref<number[]>([]);
const loading = ref(false);
const loadError = ref<unknown>(null);
const hasLoadedData = ref(false);
const activeAppId = ref<number | null>(null);
const searchKeyword = ref("");
const typeFilter = ref<"all" | ProjectAppTerminalType>("all");
const statusFilter = ref<"all" | "active" | "inactive">("all");
const statusLoadingId = ref<number | null>(null);
const deletingAppId = ref<number | null>(null);

const appDialogVisible = ref(false);
const appDialogSaving = ref(false);
const editingApp = ref<ProjectAppSummary | null>(null);
const categoryLoading = ref(false);
const appForm = reactive({
  name: "",
  code: "",
  description: "",
  terminal_type: "api" as ProjectAppTerminalType,
  knowledge_base_id: null as number | null,
  category_id: null as number | null,
  default_assistant_id: null as number | null,
});

const integrationDialogVisible = ref(false);
const integrationApp = ref<ProjectAppSummary | null>(null);
const accessCredential = ref<ProjectAppAccessCredential | null>(null);
const issuedClientSecret = ref("");
const allowedOriginsText = ref("");
const accessLoading = ref(false);
const accessSavingAction = ref<"" | "create" | "update" | "enable" | "reset" | "revoke">("");

const toolGrantDialogVisible = ref(false);
const toolGrantSaving = ref(false);
const toolGrantLoading = ref(false);
const toolGrantKeyword = ref("");
const toolGrantSelectedOnly = ref(false);
const draftToolGrantIds = ref<number[]>([]);
let toolGrantRequestSequence = 0;

const categoryCascaderProps = {
  value: "id",
  label: "name",
  children: "children",
  checkStrictly: true,
  emitPath: true,
};

const projectId = computed(() => {
  const raw = Number(route.params.projectId);
  return Number.isInteger(raw) && raw > 0 ? raw : null;
});
const isForbidden = computed(() => Boolean(loadError.value) && isForbiddenError(loadError.value));
const activeApp = computed(() => apps.value.find((item) => item.id === activeAppId.value) ?? null);
const appDialogTitle = computed(() => (editingApp.value ? "编辑应用端" : "创建应用端"));
const appDialogSubmitText = computed(() => (editingApp.value ? "保存修改" : "创建应用端"));
const filteredApps = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase();
  return apps.value.filter((app) => {
    const matchesKeyword = !keyword || [app.name, app.code, app.description, app.knowledge_base_name]
      .some((value) => String(value || "").toLowerCase().includes(keyword));
    const matchesType = typeFilter.value === "all" || app.terminal_type === typeFilter.value;
    const matchesStatus = statusFilter.value === "all"
      || (statusFilter.value === "active" ? app.is_active : !app.is_active);
    return matchesKeyword && matchesType && matchesStatus;
  });
});
const grantedToolIdSet = computed(() => new Set(toolGrants.value.map((grant) => grant.agent_tool_id)));
const toolGrantHasChanges = computed(() => {
  const saved = [...grantedToolIdSet.value].sort((a, b) => a - b);
  const draft = [...new Set(draftToolGrantIds.value)].sort((a, b) => a - b);
  return saved.length !== draft.length || saved.some((id, index) => id !== draft[index]);
});
const groupedAvailableTools = computed(() => {
  const keyword = toolGrantKeyword.value.trim().toLowerCase();
  const selectedIds = new Set(draftToolGrantIds.value);
  const groups = new Map<number, { providerId: number; providerName: string; tools: AgentTool[] }>();
  for (const tool of availableTools.value) {
    const matchesSelected = !toolGrantSelectedOnly.value || selectedIds.has(tool.id);
    const matchesKeyword = !keyword || [
      tool.name,
      tool.tool_key,
      tool.provider_name,
      tool.agent_description,
      tool.external_description,
    ].some((value) => String(value || "").toLowerCase().includes(keyword));
    if (!matchesSelected || !matchesKeyword) continue;
    const group = groups.get(tool.provider_id) ?? {
      providerId: tool.provider_id,
      providerName: tool.provider_name,
      tools: [],
    };
    group.tools.push(tool);
    groups.set(tool.provider_id, group);
  }
  return [...groups.values()];
});
const isMcpIntegration = computed(() => integrationApp.value?.terminal_type === "mcp");
const agentPublicOrigin = new URL(API_BASE_URL, window.location.origin).origin;
const apiEndpoint = computed(() => `${agentPublicOrigin}/api/v1`);
const mcpEndpoint = computed(() => `${agentPublicOrigin}/mcp/`);
const mcpConfigCode = computed(() => JSON.stringify({
  mcpServers: {
    "synapseflow-agent": {
      url: mcpEndpoint.value,
      headers: {
        Authorization: `Bearer ${accessCredential.value?.client_id || "<client_id>"}.${issuedClientSecret.value || "<client_secret>"}`,
      },
    },
  },
}, null, 2));
const bootstrapEnvironmentCode = computed(() => `AGENT_BASE_URL=${apiEndpoint.value}
AGENT_CLIENT_ID=${accessCredential.value?.client_id || "<启用后生成>"}
AGENT_CLIENT_SECRET=${issuedClientSecret.value || "<仅在启用或重置后显示>"}`);
const widgetLoaderCode = computed(() => `<script
  src="${agentPublicOrigin}/agent-static/loader/v1/loader.js"
  data-bootstrap-endpoint="/api/agent/bootstrap"
  defer
>` + "<" + "/script>");

function formatTerminalType(value: ProjectAppTerminalType) {
  return PROJECT_APP_TERMINAL_TYPE_LABELS[value] ?? "未知类型";
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function getTerminalIcon(value: ProjectAppTerminalType) {
  return value === "api" ? Connection : Link;
}

function getTerminalIconClass(value: ProjectAppTerminalType) {
  return `project-app-workspace-page__terminal-icon--${value}`;
}

function normalizeCode(value: string) {
  return value.trim().toLowerCase().replace(/[\s-]+/g, "_").replace(/[^a-z0-9_]/g, "")
    .replace(/^_+|_+$/g, "").slice(0, 120);
}

function generateAppCode(name: string) {
  return normalizeCode(name) || `app_${Date.now()}`;
}

function buildUpdatePayload(app: ProjectAppSummary, overrides: Partial<ProjectAppUpsertPayload> = {}) {
  return {
    code: app.code,
    name: app.name,
    description: app.description,
    terminal_type: app.terminal_type,
    knowledge_base_id: app.knowledge_base_id,
    category_id: app.category_id,
    default_assistant_id: app.default_assistant_id,
    widget_version: app.widget_version,
    is_active: app.is_active,
    ...overrides,
  } satisfies ProjectAppUpsertPayload;
}

function resetAppForm() {
  appForm.name = "";
  appForm.code = "";
  appForm.description = "";
  appForm.terminal_type = "api";
  appForm.knowledge_base_id = null;
  appForm.category_id = null;
  appForm.default_assistant_id = null;
  categoryPath.value = [];
  editingApp.value = null;
}

function findCategoryPath(
  nodes: DocumentCategoryTreeNode[],
  targetId: number,
  parentPath: number[] = [],
): number[] {
  for (const node of nodes) {
    const path = [...parentPath, node.id];
    if (node.id === targetId) return path;
    const childPath = findCategoryPath(node.children || [], targetId, path);
    if (childPath.length > 0) return childPath;
  }
  return [];
}

async function loadCategories(knowledgeBaseId: number | null, categoryId: number | null = null) {
  categoryTree.value = [];
  categoryPath.value = [];
  if (!knowledgeBaseId) return;
  categoryLoading.value = true;
  try {
    categoryTree.value = await listDocumentCategoriesTree(knowledgeBaseId);
    if (categoryId) categoryPath.value = findCategoryPath(categoryTree.value, categoryId);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载知识库分类失败，请稍后重试。");
  } finally {
    categoryLoading.value = false;
  }
}

async function listAllPublishedTools(teamId: number) {
  const items: AgentTool[] = [];
  let page = 1;
  let total = 0;
  do {
    const response = await listAgentTools({
      team_id: teamId,
      publish_status: "published",
      sync_status: "active",
      page,
      page_size: 100,
    });
    items.push(...response.items);
    total = response.total;
    page += 1;
    if (!response.items.length) break;
  } while (items.length < total);
  return items;
}

async function loadOptionData(projectResponse: ProjectSummary) {
  const [assistantResponse, knowledgeBaseResponse, toolResponse] = await Promise.all([
    listAssistants({ team_id: projectResponse.team_id, active_only: true, page: 1, page_size: 100 }),
    listKnowledgeBases({ team_id: projectResponse.team_id, active_only: true, page: 1, page_size: 100 }),
    listAllPublishedTools(projectResponse.team_id),
  ]);
  assistants.value = assistantResponse.items;
  knowledgeBases.value = knowledgeBaseResponse.items;
  availableTools.value = toolResponse;
}

async function loadToolGrants(appId: number | null) {
  const requestSequence = ++toolGrantRequestSequence;
  toolGrants.value = [];
  if (!projectId.value || !appId) return;
  toolGrantLoading.value = true;
  try {
    const response = await listProjectAppToolGrants(projectId.value, appId);
    if (requestSequence === toolGrantRequestSequence) toolGrants.value = response.items;
  } catch (error) {
    if (requestSequence === toolGrantRequestSequence) {
      ElMessage.error(error instanceof Error ? error.message : "加载工具授权失败，请稍后重试。");
    }
  } finally {
    if (requestSequence === toolGrantRequestSequence) toolGrantLoading.value = false;
  }
}

async function loadPage() {
  if (!projectId.value || loading.value) return;
  loading.value = true;
  loadError.value = null;
  try {
    const projectResponse = await getProject(projectId.value);
    const [appResponse] = await Promise.all([
      listProjectApps(projectId.value, { status: "all", page: 1, page_size: 100 }),
      loadOptionData(projectResponse),
    ]);
    project.value = projectResponse;
    apps.value = appResponse.items;
    const requestedAppId = Number(route.query.appId);
    activeAppId.value = Number.isInteger(requestedAppId) && apps.value.some((item) => item.id === requestedAppId)
      ? requestedAppId
      : apps.value[0]?.id ?? null;
    await loadToolGrants(activeAppId.value);
    hasLoadedData.value = true;
  } catch (error) {
    if (hasLoadedData.value) ElMessage.error(error instanceof Error ? error.message : "应用端刷新失败，请稍后重试。");
    else loadError.value = error;
  } finally {
    loading.value = false;
  }
}

function openCreateApp() {
  resetAppForm();
  appDialogVisible.value = true;
}

function openEditApp(app: ProjectAppSummary) {
  editingApp.value = app;
  appForm.name = app.name;
  appForm.code = app.code;
  appForm.description = app.description ?? "";
  appForm.terminal_type = app.terminal_type;
  appForm.knowledge_base_id = app.knowledge_base_id;
  appForm.category_id = app.category_id;
  appForm.default_assistant_id = app.default_assistant_id;
  void loadCategories(app.knowledge_base_id, app.category_id);
  appDialogVisible.value = true;
}

function openEditResources() {
  const app = integrationApp.value;
  if (!app) return;
  integrationDialogVisible.value = false;
  openEditApp(app);
}

async function handleAppKnowledgeBaseChange(value: number | string | null) {
  const knowledgeBaseId = Number(value);
  appForm.knowledge_base_id = Number.isInteger(knowledgeBaseId) && knowledgeBaseId > 0 ? knowledgeBaseId : null;
  appForm.category_id = null;
  categoryPath.value = [];
  await loadCategories(appForm.knowledge_base_id);
}

function handleAppCategoryPathChange(value: unknown) {
  const selectedPath = Array.isArray(value)
    ? value.map((item) => Number(item)).filter((item) => Number.isInteger(item) && item > 0)
    : [];
  categoryPath.value = selectedPath;
  appForm.category_id = selectedPath.length > 0 ? selectedPath[selectedPath.length - 1] : null;
}

async function handleSaveApp() {
  if (!projectId.value || appDialogSaving.value) return;
  const name = appForm.name.trim();
  if (!name) {
    ElMessage.warning("请填写应用端名称。");
    return;
  }
  if (appForm.terminal_type === "mcp" && !appForm.knowledge_base_id) {
    ElMessage.warning("MCP 应用端至少需要绑定一个知识库。");
    return;
  }
  const code = normalizeCode(appForm.code) || generateAppCode(name);
  appDialogSaving.value = true;
  try {
    if (editingApp.value) {
      const updated = await updateProjectApp(projectId.value, editingApp.value.id, buildUpdatePayload(editingApp.value, {
        name,
        code,
        description: appForm.description.trim() || null,
        knowledge_base_id: appForm.knowledge_base_id,
        category_id: appForm.category_id,
        default_assistant_id: appForm.default_assistant_id,
      }));
      const index = apps.value.findIndex((item) => item.id === updated.id);
      if (index >= 0) apps.value[index] = updated;
      appDialogVisible.value = false;
      ElMessage.success(`已保存应用端“${updated.name}”。`);
      void openIntegration(updated);
      return;
    }
    const created = await createProjectApp(projectId.value, {
      name,
      code,
      description: appForm.description.trim() || null,
      terminal_type: appForm.terminal_type,
      knowledge_base_id: appForm.knowledge_base_id,
      category_id: appForm.category_id,
      default_assistant_id: appForm.default_assistant_id,
      widget_version: "1.0.0",
      is_active: true,
    });
    apps.value = [created, ...apps.value];
    activeAppId.value = created.id;
    appDialogVisible.value = false;
    ElMessage.success(`已创建应用端“${created.name}”。`);
    void openIntegration(created);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存应用端失败，请稍后重试。");
  } finally {
    appDialogSaving.value = false;
  }
}

function handleAppDialogClosed() {
  if (!appDialogSaving.value) resetAppForm();
}

async function handleToggleStatus(app: ProjectAppSummary, nextValue = !app.is_active) {
  if (!projectId.value || statusLoadingId.value) return;
  statusLoadingId.value = app.id;
  try {
    const updated = await updateProjectApp(projectId.value, app.id, buildUpdatePayload(app, { is_active: nextValue }));
    const index = apps.value.findIndex((item) => item.id === updated.id);
    if (index >= 0) apps.value[index] = updated;
    if (integrationApp.value?.id === updated.id) integrationApp.value = updated;
    ElMessage.success(`已${updated.is_active ? "启用" : "停用"}应用端“${updated.name}”。`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "更新应用端状态失败，请稍后重试。");
  } finally {
    statusLoadingId.value = null;
  }
}

async function handleDeleteApp(app: ProjectAppSummary) {
  if (!projectId.value || deletingAppId.value) return;
  try {
    await ElMessageBox.confirm(`确定删除应用端“${app.name}”吗？删除后该应用的接入凭证也会失效。`, "删除应用端", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  deletingAppId.value = app.id;
  try {
    await deleteProjectApp(projectId.value, app.id);
    apps.value = apps.value.filter((item) => item.id !== app.id);
    activeAppId.value = apps.value[0]?.id ?? null;
    await loadToolGrants(activeAppId.value);
    ElMessage.success(`已删除应用端“${app.name}”。`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "删除应用端失败，请稍后重试。");
  } finally {
    deletingAppId.value = null;
  }
}

async function handleAppAction(app: ProjectAppSummary, command: string | number | object) {
  const action = String(command);
  if (action === "access") void openIntegration(app);
  else if (action === "edit") openEditApp(app);
  else if (action === "tools") {
    activeAppId.value = app.id;
    await loadToolGrants(app.id);
    draftToolGrantIds.value = [...grantedToolIdSet.value];
    toolGrantDialogVisible.value = true;
  } else if (action === "toggle") void handleToggleStatus(app);
  else if (action === "delete") void handleDeleteApp(app);
}

async function openIntegration(app: ProjectAppSummary) {
  activeAppId.value = app.id;
  integrationDialogVisible.value = true;
  integrationApp.value = app;
  accessCredential.value = null;
  issuedClientSecret.value = "";
  allowedOriginsText.value = app.terminal_type === "api" ? "https://your-business.example.com" : "";
  accessLoading.value = true;
  try {
    const credential = await getProjectAppAccess(projectId.value as number, app.id);
    accessCredential.value = credential;
    allowedOriginsText.value = credential.allowed_origins.join("\n");
  } catch (error) {
    if (!(error instanceof AppRequestError) || error.status !== 404) {
      ElMessage.error(error instanceof Error ? error.message : "加载应用接入凭证失败。");
    }
  } finally {
    accessLoading.value = false;
  }
}

function getAllowedOrigins() {
  return [...new Set(allowedOriginsText.value.split(/[\n,]/).map((item) => item.trim().replace(/\/+$/, "")).filter(Boolean))];
}

function validateAllowedOrigins() {
  const origins = getAllowedOrigins();
  const invalid = origins.some((origin) => {
    try {
      const parsed = new URL(origin);
      return !["http:", "https:"].includes(parsed.protocol) || parsed.origin !== origin;
    } catch {
      return true;
    }
  });
  if (!origins.length || invalid) {
    ElMessage.warning("请填写不含路径的完整 HTTP 或 HTTPS Origin。");
    return null;
  }
  return origins;
}

async function handleCreateAccess() {
  if (!projectId.value || !integrationApp.value || accessSavingAction.value) return;
  const allowedOrigins = integrationApp.value.terminal_type === "api" ? validateAllowedOrigins() : [];
  if (allowedOrigins === null) return;
  accessSavingAction.value = "create";
  try {
    const issued = await createProjectAppAccess(projectId.value, integrationApp.value.id, { allowed_origins: allowedOrigins });
    accessCredential.value = issued;
    issuedClientSecret.value = issued.client_secret;
    allowedOriginsText.value = issued.allowed_origins.join("\n");
    ElMessage.success(`${integrationApp.value.terminal_type === "mcp" ? "MCP" : "API"} 接入已启用，请立即保存 Client Secret。`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "启用应用接入失败。");
  } finally {
    accessSavingAction.value = "";
  }
}

async function handleUpdateAccess() {
  if (!projectId.value || !integrationApp.value || !accessCredential.value || accessSavingAction.value) return;
  const allowedOrigins = validateAllowedOrigins();
  if (!allowedOrigins) return;
  accessSavingAction.value = "update";
  try {
    accessCredential.value = await updateProjectAppAccess(projectId.value, integrationApp.value.id, { allowed_origins: allowedOrigins });
    allowedOriginsText.value = accessCredential.value.allowed_origins.join("\n");
    ElMessage.success("允许的 Origin 已保存。");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存 Origin 失败。");
  } finally {
    accessSavingAction.value = "";
  }
}

async function handleEnableExistingAccess() {
  if (!projectId.value || !integrationApp.value || !accessCredential.value || accessSavingAction.value) return;
  accessSavingAction.value = "enable";
  try {
    accessCredential.value = await enableProjectAppAccess(projectId.value, integrationApp.value.id);
    ElMessage.success("应用接入已重新启用。");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "重新启用应用接入失败。");
  } finally {
    accessSavingAction.value = "";
  }
}

async function handleResetAccessSecret() {
  if (!projectId.value || !integrationApp.value || accessSavingAction.value) return;
  try {
    await ElMessageBox.confirm("重置后旧 Client Secret 将立即失效，确定继续吗？", "重置 Secret", {
      type: "warning",
      confirmButtonText: "重置",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  accessSavingAction.value = "reset";
  try {
    const issued = await resetProjectAppAccessSecret(projectId.value, integrationApp.value.id);
    accessCredential.value = issued;
    issuedClientSecret.value = issued.client_secret;
    ElMessage.success("Client Secret 已重置，请立即保存新值。");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "重置 Client Secret 失败。");
  } finally {
    accessSavingAction.value = "";
  }
}

async function handleRevokeAccess() {
  if (!projectId.value || !integrationApp.value || accessSavingAction.value) return;
  try {
    await ElMessageBox.confirm("吊销后当前应用的接入凭证将失效，确定继续吗？", "吊销应用接入", {
      type: "warning",
      confirmButtonText: "吊销",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  accessSavingAction.value = "revoke";
  try {
    accessCredential.value = await revokeProjectAppAccess(projectId.value, integrationApp.value.id);
    issuedClientSecret.value = "";
    ElMessage.success("应用接入已吊销。");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "吊销应用接入失败。");
  } finally {
    accessSavingAction.value = "";
  }
}

async function copyText(value: string, successMessage: string) {
  try {
    await navigator.clipboard.writeText(value);
    ElMessage.success(successMessage);
  } catch {
    ElMessage.error("复制失败，请手动复制。");
  }
}

function openToolGrantManager() {
  draftToolGrantIds.value = [...grantedToolIdSet.value];
  toolGrantKeyword.value = "";
  toolGrantSelectedOnly.value = false;
  toolGrantDialogVisible.value = true;
}

function isProviderFullySelected(tools: AgentTool[]) {
  const selected = new Set(draftToolGrantIds.value);
  return tools.length > 0 && tools.every((tool) => selected.has(tool.id));
}

function isProviderPartiallySelected(tools: AgentTool[]) {
  const selectedCount = tools.filter((tool) => draftToolGrantIds.value.includes(tool.id)).length;
  return selectedCount > 0 && selectedCount < tools.length;
}

function handleProviderSelection(tools: AgentTool[], selected: boolean | string | number) {
  const nextIds = new Set(draftToolGrantIds.value);
  for (const tool of tools) selected === true ? nextIds.add(tool.id) : nextIds.delete(tool.id);
  draftToolGrantIds.value = [...nextIds].sort((a, b) => a - b);
}

function handleToolSelection(toolId: number, selected: boolean | string | number) {
  const nextIds = new Set(draftToolGrantIds.value);
  selected === true ? nextIds.add(toolId) : nextIds.delete(toolId);
  draftToolGrantIds.value = [...nextIds].sort((a, b) => a - b);
}

async function handleSaveToolGrants() {
  if (!projectId.value || !activeApp.value || toolGrantSaving.value || !toolGrantHasChanges.value) return;
  toolGrantSaving.value = true;
  try {
    const response = await replaceProjectAppToolGrants(projectId.value, activeApp.value.id, [...new Set(draftToolGrantIds.value)].sort((a, b) => a - b));
    toolGrantRequestSequence += 1;
    toolGrants.value = response.items;
    toolGrantDialogVisible.value = false;
    ElMessage.success("工具授权已保存。");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存工具授权失败，请稍后重试。");
  } finally {
    toolGrantSaving.value = false;
  }
}

onMounted(() => void loadPage());

watch(() => route.params.projectId, () => {
  activeAppId.value = null;
  void loadPage();
});

watch(integrationDialogVisible, (visible) => {
  if (!visible) {
    issuedClientSecret.value = "";
    accessCredential.value = null;
    integrationApp.value = null;
  }
});
</script>

<template>
  <section class="project-app-workspace-page">
    <AppLoading
      v-if="loading && !hasLoadedData"
      title="应用端加载中"
      description="正在获取当前项目下的应用端配置，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="loadError && !isForbidden && !hasLoadedData"
      title="应用端加载失败"
      description="暂时无法获取当前项目的应用端，请稍后重试。"
      :error="loadError"
      @retry="loadPage"
    />

    <AppError
      v-else-if="isForbidden && !hasLoadedData"
      title="无权查看应用端"
      description="当前账号没有访问该项目应用端配置的权限。"
      :error="loadError"
      :show-retry="false"
    />

    <AdminListPanel v-else class="project-app-workspace-page__panel">
      <div class="project-app-workspace-page__list-header">
        <div>
          <p class="project-app-workspace-page__eyebrow">{{ project?.name || "项目" }}</p>
          <h2>应用端管理</h2>
          <p>管理当前项目下 API 与远程 MCP 应用端的接入与使用。</p>
        </div>
        <el-button type="primary" class="project-app-workspace-page__create-button" @click="openCreateApp">
          <el-icon><Plus /></el-icon>
          创建应用端
        </el-button>
      </div>

      <div v-if="apps.length > 0" class="project-app-workspace-page__toolbar">
        <el-input v-model="searchKeyword" clearable placeholder="搜索应用名称、编码或知识库">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="typeFilter" clearable placeholder="全部类型">
          <el-option label="全部类型" value="all" />
          <el-option label="API" value="api" />
          <el-option label="远程 MCP" value="mcp" />
        </el-select>
        <el-select v-model="statusFilter" clearable placeholder="全部状态">
          <el-option label="全部状态" value="all" />
          <el-option label="已启用" value="active" />
          <el-option label="已停用" value="inactive" />
        </el-select>
      </div>

      <AppEmpty
        v-if="apps.length === 0"
        title="当前项目暂无应用端"
        description="创建一个应用端，并在创建时绑定知识库、分类和默认助手。"
      >
        <el-button type="primary" @click="openCreateApp">
          <el-icon><Plus /></el-icon>
          创建应用端
        </el-button>
      </AppEmpty>

      <div v-else-if="filteredApps.length > 0" class="project-app-workspace-page__table-wrap">
        <div class="project-app-workspace-page__table-head">
          <span>应用端名称</span><span>类型</span><span>绑定知识库</span><span>默认助手</span>
          <span>状态</span><span>更新时间</span><span>操作</span>
        </div>
        <button
          v-for="app in filteredApps"
          :key="app.id"
          type="button"
          :class="['project-app-workspace-page__table-row', activeAppId === app.id ? 'is-selected' : '']"
          @click="openIntegration(app)"
        >
          <span class="project-app-workspace-page__app-cell">
            <span class="project-app-workspace-page__app-icon" :class="getTerminalIconClass(app.terminal_type)">
              <el-icon><component :is="getTerminalIcon(app.terminal_type)" /></el-icon>
            </span>
            <span><strong>{{ app.name }}</strong><small>{{ app.description || app.code }}</small></span>
          </span>
          <span><el-tag size="small" effect="plain">{{ formatTerminalType(app.terminal_type) }}</el-tag></span>
          <span>{{ app.knowledge_base_name || "—" }}</span>
          <span>{{ app.default_assistant_name || "—" }}</span>
          <span :class="['project-app-workspace-page__status', app.is_active ? 'is-active' : 'is-inactive']"><i />{{ app.is_active ? "已启用" : "已停用" }}</span>
          <span>{{ formatDateTime(app.updated_at) }}</span>
          <span class="project-app-workspace-page__row-actions" @click.stop>
            <el-dropdown trigger="click" @command="handleAppAction(app, $event)">
              <el-button text class="project-app-workspace-page__more-button" title="更多操作"><el-icon><MoreFilled /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="access"><el-icon><Link /></el-icon>查看接入方式</el-dropdown-item>
                  <el-dropdown-item command="edit"><el-icon><EditPen /></el-icon>编辑运行资源</el-dropdown-item>
                  <el-dropdown-item command="tools"><el-icon><Setting /></el-icon>管理工具授权</el-dropdown-item>
                  <el-dropdown-item command="toggle"><el-icon><Connection /></el-icon>{{ app.is_active ? "停用应用端" : "启用应用端" }}</el-dropdown-item>
                  <el-dropdown-item command="delete" divided><el-icon><Delete /></el-icon>删除应用端</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </span>
        </button>
      </div>

      <AppEmpty v-else title="没有匹配的应用端" description="请调整搜索关键词或筛选条件。" />
    </AdminListPanel>

    <el-drawer v-model="integrationDialogVisible" class="project-app-workspace-page__drawer" size="520px" :with-header="true">
      <template #header>
        <div class="project-app-workspace-page__drawer-heading">
          <div>
            <p>应用接入</p>
            <h3>{{ integrationApp?.name || "应用端" }}</h3>
          </div>
          <el-tag v-if="integrationApp" size="small" effect="plain">{{ formatTerminalType(integrationApp.terminal_type) }}</el-tag>
        </div>
      </template>
      <div v-loading="accessLoading" class="project-app-workspace-page__drawer-body">
        <div v-if="integrationApp" class="project-app-workspace-page__drawer-app-meta">
          <span class="project-app-workspace-page__app-icon" :class="getTerminalIconClass(integrationApp.terminal_type)"><el-icon><component :is="getTerminalIcon(integrationApp.terminal_type)" /></el-icon></span>
          <div><strong>{{ integrationApp.name }}</strong><span>{{ integrationApp.is_active ? "已启用" : "已停用" }}</span></div>
          <el-button text @click="openEditResources"><el-icon><EditPen /></el-icon>编辑资源</el-button>
        </div>

        <section v-if="integrationApp" class="project-app-workspace-page__drawer-section">
          <div class="project-app-workspace-page__section-title"><h4>运行资源</h4></div>
          <div class="project-app-workspace-page__resource-list">
            <div><span><el-icon><Collection /></el-icon>知识库</span><strong>{{ integrationApp.knowledge_base_name || "未绑定" }}</strong></div>
            <div><span><el-icon><Grid /></el-icon>分类</span><strong>{{ integrationApp.category_name || "不限制分类" }}</strong></div>
            <div><span><el-icon><Cpu /></el-icon>默认助手</span><strong>{{ integrationApp.default_assistant_name || "主 Agent 默认配置" }}</strong></div>
          </div>
        </section>

        <section class="project-app-workspace-page__drawer-section">
          <div class="project-app-workspace-page__section-title"><div><h4>连接信息</h4><p>使用以下信息连接当前应用端。</p></div></div>
          <div class="project-app-workspace-page__credential-list">
            <div><span>{{ isMcpIntegration ? "服务端点" : "API 地址" }}</span><code>{{ isMcpIntegration ? mcpEndpoint : apiEndpoint }}</code><el-button text @click="copyText(isMcpIntegration ? mcpEndpoint : apiEndpoint, '地址已复制。')"><el-icon><CopyDocument /></el-icon></el-button></div>
            <div><span>Client ID</span><code>{{ accessCredential?.client_id || "尚未生成" }}</code><el-button v-if="accessCredential" text @click="copyText(accessCredential.client_id, 'Client ID 已复制。')"><el-icon><CopyDocument /></el-icon></el-button></div>
            <div><span>Client Secret</span><code>{{ issuedClientSecret || (accessCredential ? `••••••••••••${accessCredential.client_secret_last_four}` : "尚未生成") }}</code><el-button v-if="issuedClientSecret" text @click="copyText(issuedClientSecret, 'Client Secret 已复制。')"><el-icon><CopyDocument /></el-icon></el-button></div>
          </div>
          <el-alert v-if="issuedClientSecret" class="project-app-workspace-page__secret-alert" title="Client Secret 只显示这一次，请立即保存。" type="warning" :closable="false" show-icon />
          <div v-if="!accessCredential" class="project-app-workspace-page__drawer-empty"><p>当前应用端尚未生成接入凭证。</p><el-button type="primary" :loading="accessSavingAction === 'create'" @click="handleCreateAccess">生成接入凭证</el-button></div>
          <div v-else class="project-app-workspace-page__drawer-actions">
            <el-button :loading="accessSavingAction === 'reset'" @click="handleResetAccessSecret"><el-icon><RefreshRight /></el-icon>重置 Secret</el-button>
            <el-button v-if="!accessCredential.enabled" type="primary" :loading="accessSavingAction === 'enable'" @click="handleEnableExistingAccess">重新启用</el-button>
            <el-button v-else type="danger" plain :loading="accessSavingAction === 'revoke'" @click="handleRevokeAccess">吊销接入</el-button>
          </div>
        </section>

        <section v-if="integrationApp?.terminal_type === 'mcp' && accessCredential" class="project-app-workspace-page__drawer-section">
          <div class="project-app-workspace-page__section-title"><div><h4>客户端配置</h4><p>复制到支持远程 MCP 的客户端配置文件中。</p></div></div>
          <div class="project-app-workspace-page__code-block"><pre>{{ mcpConfigCode }}</pre></div>
          <el-button type="primary" class="project-app-workspace-page__copy-config" @click="copyText(mcpConfigCode, 'MCP 配置 JSON 已复制。')"><el-icon><CopyDocument /></el-icon>复制配置 JSON</el-button>
        </section>

        <section v-if="integrationApp?.terminal_type === 'api' && accessCredential" class="project-app-workspace-page__drawer-section">
          <div class="project-app-workspace-page__section-title"><div><h4>服务端配置</h4><p>业务后端可使用这组凭证调用 Agent API。</p></div></div>
          <div class="project-app-workspace-page__code-block"><pre>{{ bootstrapEnvironmentCode }}</pre></div>
          <el-button text class="project-app-workspace-page__section-action" @click="copyText(bootstrapEnvironmentCode, '环境变量模板已复制。')">复制环境变量</el-button>
        </section>

        <section v-if="integrationApp?.terminal_type === 'api'" class="project-app-workspace-page__drawer-section">
          <div class="project-app-workspace-page__section-title">
            <div><h4>Widget 聊天窗口</h4><p>业务前端通过 Loader 加载聊天窗口，长期 Client Secret 只保留在业务后端。</p></div>
          </div>
          <div class="project-app-workspace-page__widget-meta">
            <span>Widget 版本 <strong>{{ integrationApp.widget_version }}</strong></span>
            <span>Bootstrap <code>/api/agent/bootstrap</code></span>
          </div>
          <template v-if="accessCredential">
            <div class="project-app-workspace-page__widget-origin">
              <div class="project-app-workspace-page__section-title"><div><h4>允许的 Origin</h4><p>限制哪些业务网站可以加载并使用聊天窗口。</p></div></div>
              <el-input v-model="allowedOriginsText" type="textarea" :rows="3" placeholder="https://your-business.example.com" />
              <el-button class="project-app-workspace-page__section-action" :loading="accessSavingAction === 'update'" @click="handleUpdateAccess">保存 Origin</el-button>
            </div>
            <div class="project-app-workspace-page__code-block"><pre>{{ widgetLoaderCode }}</pre></div>
            <el-button type="primary" plain class="project-app-workspace-page__copy-config" @click="copyText(widgetLoaderCode, 'Widget Loader 代码已复制。')"><el-icon><CopyDocument /></el-icon>复制嵌入代码</el-button>
          </template>
          <div v-else class="project-app-workspace-page__widget-empty">生成应用接入凭证后，才能复制 Widget 嵌入代码并连接聊天服务。</div>
        </section>
      </div>
    </el-drawer>

    <el-drawer v-model="appDialogVisible" class="project-app-workspace-page__drawer" size="460px" :show-close="!appDialogSaving" :close-on-press-escape="!appDialogSaving" @closed="handleAppDialogClosed">
      <template #header><div class="project-app-workspace-page__drawer-heading"><div><p>应用端管理</p><h3>{{ appDialogTitle }}</h3></div></div></template>
      <el-form label-position="top" class="project-app-workspace-page__create-form">
        <el-form-item label="应用端名称" required><el-input v-model="appForm.name" maxlength="100" placeholder="例如：客服助手 MCP" /></el-form-item>
        <el-form-item label="接入方式" required>
          <div class="project-app-workspace-page__type-grid">
            <button type="button" :class="['project-app-workspace-page__type-option', appForm.terminal_type === 'api' ? 'is-selected' : '']" :disabled="Boolean(editingApp)" @click="appForm.terminal_type = 'api'">
              <el-icon><Connection /></el-icon><span><strong>API</strong><small>适用于后台服务调用</small></span>
            </button>
            <button type="button" :class="['project-app-workspace-page__type-option', appForm.terminal_type === 'mcp' ? 'is-selected' : '']" :disabled="Boolean(editingApp)" @click="appForm.terminal_type = 'mcp'">
              <el-icon><Link /></el-icon><span><strong>远程 MCP</strong><small>适用于外部 MCP 客户端</small></span>
            </button>
          </div>
        </el-form-item>
        <el-form-item label="绑定知识库" :required="appForm.terminal_type === 'mcp'"><el-select v-model="appForm.knowledge_base_id" class="project-app-workspace-page__full-control" clearable filterable placeholder="请选择知识库" @change="handleAppKnowledgeBaseChange"><el-option v-for="knowledgeBase in knowledgeBases" :key="knowledgeBase.id" :label="knowledgeBase.name" :value="knowledgeBase.id" /></el-select></el-form-item>
        <el-form-item label="所属分类（可选）"><el-cascader v-model="categoryPath" class="project-app-workspace-page__full-control" :options="categoryTree" :props="categoryCascaderProps" clearable filterable :disabled="!appForm.knowledge_base_id" :loading="categoryLoading" placeholder="不限制分类" @change="handleAppCategoryPathChange"><template #default="{ data }"><div class="project-app-workspace-page__category-option"><span>{{ data.name }}</span><small>{{ data.document_count }} 篇</small></div></template></el-cascader></el-form-item>
        <el-form-item label="默认助手（可选）"><el-select v-model="appForm.default_assistant_id" class="project-app-workspace-page__full-control" clearable filterable placeholder="使用主 Agent 默认配置"><el-option v-for="assistant in assistants" :key="assistant.id" :label="assistant.name" :value="assistant.id" /></el-select></el-form-item>
        <el-form-item label="描述说明（可选）"><el-input v-model="appForm.description" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="简要描述该应用端的使用场景" /></el-form-item>
        <div class="project-app-workspace-page__form-note">应用编码和接入凭证由系统自动生成。创建成功后，可在接入抽屉中复制 API 或 MCP 配置。</div>
      </el-form>
      <template #footer><div class="project-app-workspace-page__drawer-footer"><el-button :disabled="appDialogSaving" @click="appDialogVisible = false">取消</el-button><el-button type="primary" :loading="appDialogSaving" @click="handleSaveApp">{{ appDialogSubmitText }}</el-button></div></template>
    </el-drawer>

    <el-drawer v-model="toolGrantDialogVisible" class="project-app-workspace-page__drawer" size="620px" :show-close="!toolGrantSaving">
      <template #header><div class="project-app-workspace-page__drawer-heading"><div><p>应用能力</p><h3>管理工具授权</h3></div><span class="project-app-workspace-page__drawer-caption">{{ activeApp?.name }}</span></div></template>
      <div v-loading="toolGrantLoading" class="project-app-workspace-page__tool-body">
        <div class="project-app-workspace-page__tool-toolbar"><el-input v-model="toolGrantKeyword" clearable placeholder="搜索工具名称、标识或提供方"><template #prefix><el-icon><Search /></el-icon></template></el-input><el-checkbox v-model="toolGrantSelectedOnly">仅看已授权</el-checkbox></div>
        <section v-for="group in groupedAvailableTools" :key="group.providerId" class="project-app-workspace-page__tool-group">
          <div class="project-app-workspace-page__tool-group-header"><strong>{{ group.providerName }}</strong><el-checkbox :model-value="isProviderFullySelected(group.tools)" :indeterminate="isProviderPartiallySelected(group.tools)" @change="handleProviderSelection(group.tools, $event)">全选</el-checkbox></div>
          <label v-for="tool in group.tools" :key="tool.id" class="project-app-workspace-page__tool-option"><el-checkbox :model-value="draftToolGrantIds.includes(tool.id)" @change="handleToolSelection(tool.id, $event)" /><span><strong>{{ tool.name }}</strong><small>{{ tool.agent_description || tool.external_description || "暂无工具说明" }}</small><code>{{ tool.tool_key }}</code></span></label>
        </section>
        <AppEmpty v-if="groupedAvailableTools.length === 0" title="没有匹配的工具" description="请调整搜索词或关闭仅看已授权。" />
      </div>
      <template #footer><div class="project-app-workspace-page__drawer-footer"><span>已选择 {{ draftToolGrantIds.length }} 个工具</span><div><el-button :disabled="toolGrantSaving" @click="toolGrantDialogVisible = false">取消</el-button><el-button type="primary" :loading="toolGrantSaving" :disabled="!toolGrantHasChanges" @click="handleSaveToolGrants">保存授权</el-button></div></div></template>
    </el-drawer>
  </section>
</template>

<style scoped>
.project-app-workspace-page {
  --app-border: #e5eaf2;
  --app-muted: #64748b;
  --app-text: #172033;
  --app-primary: #2563eb;
  --app-soft: #eff6ff;
  min-height: 100%;
  padding: 24px;
}

.project-app-workspace-page__panel {
  overflow: hidden;
  border: 1px solid var(--app-border);
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.04);
}

.project-app-workspace-page__list-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 30px 22px;
}

.project-app-workspace-page__eyebrow,
.project-app-workspace-page__list-header p,
.project-app-workspace-page__drawer-heading p {
  margin: 0;
  color: var(--app-muted);
  font-size: 13px;
}

.project-app-workspace-page__list-header h2,
.project-app-workspace-page__drawer-heading h3 {
  margin: 4px 0 0;
  color: var(--app-text);
  font-size: 22px;
  font-weight: 750;
}

.project-app-workspace-page__list-header h2 + p { margin-top: 8px; }
.project-app-workspace-page__create-button { border-radius: 8px; padding: 0 18px; }

.project-app-workspace-page__toolbar {
  display: flex;
  gap: 10px;
  border-top: 1px solid var(--app-border);
  border-bottom: 1px solid var(--app-border);
  background: #fbfcfe;
  padding: 14px 30px;
}

.project-app-workspace-page__toolbar .el-input { width: min(360px, 100%); }
.project-app-workspace-page__toolbar .el-select { width: 140px; }

.project-app-workspace-page__table-wrap { overflow-x: auto; }
.project-app-workspace-page__table-head,
.project-app-workspace-page__table-row {
  display: grid;
  grid-template-columns: minmax(220px, 1.55fr) 100px minmax(140px, 1fr) minmax(140px, 1fr) 100px 150px 52px;
  align-items: center;
  gap: 16px;
  min-width: 980px;
  padding: 0 30px;
  text-align: left;
}

.project-app-workspace-page__table-head {
  min-height: 44px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}

.project-app-workspace-page__table-row {
  width: 100%;
  min-height: 76px;
  border: 0;
  border-bottom: 1px solid #edf1f6;
  background: #fff;
  color: #475569;
  cursor: pointer;
  font: inherit;
  transition: background 0.18s ease, box-shadow 0.18s ease;
}

.project-app-workspace-page__table-row:hover,
.project-app-workspace-page__table-row.is-selected { background: #f8fbff; }
.project-app-workspace-page__table-row.is-selected { box-shadow: inset 3px 0 0 var(--app-primary); }
.project-app-workspace-page__app-cell { display: flex; min-width: 0; align-items: center; gap: 12px; }
.project-app-workspace-page__app-cell > span:last-child { display: grid; min-width: 0; gap: 4px; }
.project-app-workspace-page__app-cell strong { overflow: hidden; color: var(--app-text); font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.project-app-workspace-page__app-cell small { overflow: hidden; color: var(--app-muted); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }

.project-app-workspace-page__app-icon {
  display: inline-flex;
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  font-size: 18px;
}

.project-app-workspace-page__terminal-icon--api { background: #ecfdf5; color: #047857; }
.project-app-workspace-page__terminal-icon--mcp { background: #eff6ff; color: #2563eb; }
.project-app-workspace-page__status { display: inline-flex; align-items: center; gap: 7px; font-size: 13px; white-space: nowrap; }
.project-app-workspace-page__status i { width: 7px; height: 7px; border-radius: 50%; background: #94a3b8; }
.project-app-workspace-page__status.is-active { color: #059669; }
.project-app-workspace-page__status.is-active i { background: #10b981; }
.project-app-workspace-page__status.is-inactive { color: #64748b; }
.project-app-workspace-page__row-actions { display: flex; justify-content: flex-end; }
.project-app-workspace-page__more-button { color: #64748b; }
.project-app-workspace-page__more-button:hover { color: var(--app-primary); background: var(--app-soft); }

.project-app-workspace-page__drawer :deep(.el-drawer__header) { margin-bottom: 0; border-bottom: 1px solid var(--app-border); padding: 20px 24px; }
.project-app-workspace-page__drawer :deep(.el-drawer__body) { padding: 0; }
.project-app-workspace-page__drawer :deep(.el-drawer__footer) { border-top: 1px solid var(--app-border); padding: 14px 24px; }
.project-app-workspace-page__drawer-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; width: 100%; }
.project-app-workspace-page__drawer-body { padding: 22px 24px 28px; }
.project-app-workspace-page__drawer-app-meta { display: flex; align-items: center; gap: 12px; padding-bottom: 22px; }
.project-app-workspace-page__drawer-app-meta > div { display: grid; min-width: 0; flex: 1; gap: 4px; }
.project-app-workspace-page__drawer-app-meta strong { color: var(--app-text); font-size: 15px; }
.project-app-workspace-page__drawer-app-meta span:not(.project-app-workspace-page__app-icon) { color: #059669; font-size: 12px; }
.project-app-workspace-page__drawer-app-meta .el-button { flex-shrink: 0; color: var(--app-primary); }
.project-app-workspace-page__drawer-section { border-top: 1px solid var(--app-border); padding: 20px 0; }
.project-app-workspace-page__section-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.project-app-workspace-page__section-title h4 { margin: 0; color: var(--app-text); font-size: 15px; font-weight: 750; }
.project-app-workspace-page__section-title p { margin: 5px 0 0; color: var(--app-muted); font-size: 12px; line-height: 1.5; }
.project-app-workspace-page__resource-list,
.project-app-workspace-page__credential-list { overflow: hidden; border: 1px solid var(--app-border); border-radius: 8px; background: #fff; }
.project-app-workspace-page__resource-list > div,
.project-app-workspace-page__credential-list > div { display: flex; min-width: 0; align-items: center; gap: 12px; min-height: 48px; border-bottom: 1px solid #edf1f6; padding: 10px 12px; }
.project-app-workspace-page__resource-list > div:last-child,
.project-app-workspace-page__credential-list > div:last-child { border-bottom: 0; }
.project-app-workspace-page__resource-list span { display: inline-flex; width: 96px; flex: 0 0 auto; align-items: center; gap: 7px; color: var(--app-muted); font-size: 12px; }
.project-app-workspace-page__resource-list strong { overflow: hidden; color: var(--app-text); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.project-app-workspace-page__credential-list span { width: 86px; flex: 0 0 auto; color: var(--app-muted); font-size: 12px; }
.project-app-workspace-page__credential-list code { min-width: 0; flex: 1; overflow: hidden; color: #334155; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.project-app-workspace-page__credential-list .el-button { flex: 0 0 auto; color: var(--app-primary); }
.project-app-workspace-page__secret-alert { margin-top: 12px; }
.project-app-workspace-page__drawer-empty { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-top: 14px; border: 1px dashed #bfdbfe; border-radius: 8px; background: #f8fbff; padding: 12px; }
.project-app-workspace-page__drawer-empty p { margin: 0; color: var(--app-muted); font-size: 12px; }
.project-app-workspace-page__drawer-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
.project-app-workspace-page__section-action { margin-top: 12px; }
.project-app-workspace-page__widget-meta { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-bottom: 12px; color: var(--app-muted); font-size: 12px; }
.project-app-workspace-page__widget-meta strong { color: var(--app-text); }
.project-app-workspace-page__widget-meta code { color: #475569; font: 11px ui-monospace, SFMono-Regular, Consolas, monospace; }
.project-app-workspace-page__widget-origin { margin-bottom: 16px; }
.project-app-workspace-page__widget-empty { border: 1px dashed #bfdbfe; border-radius: 8px; background: #f8fbff; color: var(--app-muted); font-size: 12px; line-height: 1.6; padding: 12px; }
.project-app-workspace-page__code-block { overflow: auto; border: 1px solid var(--app-border); border-radius: 8px; background: #f8fafc; padding: 14px; }
.project-app-workspace-page__code-block pre { margin: 0; color: #334155; font: 12px/1.65 ui-monospace, SFMono-Regular, Consolas, monospace; white-space: pre-wrap; word-break: break-word; }
.project-app-workspace-page__copy-config { width: 100%; margin-top: 12px; border-radius: 8px; }

.project-app-workspace-page__create-form { padding: 2px 24px 24px; }
.project-app-workspace-page__full-control { width: 100%; }
.project-app-workspace-page__type-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; width: 100%; }
.project-app-workspace-page__type-option { display: flex; min-height: 76px; align-items: center; gap: 10px; border: 1px solid var(--app-border); border-radius: 8px; background: #fff; color: var(--app-muted); cursor: pointer; padding: 12px; text-align: left; }
.project-app-workspace-page__type-option:hover,
.project-app-workspace-page__type-option.is-selected { border-color: #93c5fd; background: #f8fbff; color: var(--app-primary); }
.project-app-workspace-page__type-option:disabled { cursor: not-allowed; opacity: 0.72; }
.project-app-workspace-page__type-option > .el-icon { font-size: 20px; }
.project-app-workspace-page__type-option span { display: grid; gap: 4px; }
.project-app-workspace-page__type-option strong { color: var(--app-text); font-size: 13px; }
.project-app-workspace-page__type-option small { color: var(--app-muted); font-size: 11px; line-height: 1.4; }
.project-app-workspace-page__form-note { border: 1px solid #dbeafe; border-radius: 8px; background: #eff6ff; color: #475569; font-size: 12px; line-height: 1.6; padding: 11px 12px; }
.project-app-workspace-page__drawer-footer { display: flex; align-items: center; justify-content: flex-end; gap: 10px; }
.project-app-workspace-page__category-option { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.project-app-workspace-page__category-option small { color: var(--app-muted); font-size: 11px; }
.project-app-workspace-page__drawer-caption { color: var(--app-muted); font-size: 12px; }

.project-app-workspace-page__tool-body { padding: 0 24px 24px; }
.project-app-workspace-page__tool-toolbar { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 14px; border-bottom: 1px solid var(--app-border); padding: 4px 0 16px; }
.project-app-workspace-page__tool-group { margin-top: 18px; overflow: hidden; border: 1px solid var(--app-border); border-radius: 8px; }
.project-app-workspace-page__tool-group-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; background: #f8fafc; padding: 11px 14px; }
.project-app-workspace-page__tool-group-header strong { color: var(--app-text); font-size: 13px; }
.project-app-workspace-page__tool-option { display: flex; align-items: flex-start; gap: 10px; border-top: 1px solid #edf1f6; cursor: pointer; padding: 12px 14px; }
.project-app-workspace-page__tool-option > span { display: grid; min-width: 0; gap: 4px; }
.project-app-workspace-page__tool-option strong { color: var(--app-text); font-size: 13px; }
.project-app-workspace-page__tool-option small { color: var(--app-muted); font-size: 12px; line-height: 1.5; }
.project-app-workspace-page__tool-option code { color: #94a3b8; font: 11px ui-monospace, SFMono-Regular, Consolas, monospace; }

@media (max-width: 760px) {
  .project-app-workspace-page { padding: 14px; }
  .project-app-workspace-page__list-header { flex-direction: column; padding: 22px 18px; }
  .project-app-workspace-page__create-button { align-self: stretch; }
  .project-app-workspace-page__toolbar { flex-direction: column; padding: 12px 18px; }
  .project-app-workspace-page__toolbar .el-input,
  .project-app-workspace-page__toolbar .el-select { width: 100%; }
  .project-app-workspace-page__table-head,
  .project-app-workspace-page__table-row { padding: 0 18px; }
  .project-app-workspace-page__type-grid { grid-template-columns: 1fr; }
}
</style>
