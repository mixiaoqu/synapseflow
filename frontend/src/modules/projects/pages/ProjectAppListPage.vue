<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import {
  Collection,
  Connection,
  Cpu,
  Delete,
  EditPen,
  Grid,
  Link,
  Monitor,
  Plus,
  Search,
  Setting,
} from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import AdminDialog from "@/app/components/admin/AdminDialog.vue";
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
const loading = ref(false);
const loadError = ref<unknown>(null);
const hasLoadedData = ref(false);
const statusLoadingId = ref<number | null>(null);
const deletingAppId = ref<number | null>(null);
const configSavingKey = ref<"" | "knowledge_base" | "category" | "assistant">("");
const categoryLoading = ref(false);
const toolGrantLoading = ref(false);
const toolGrantDialogVisible = ref(false);
const toolGrantSaving = ref(false);
const toolGrantKeyword = ref("");
const toolGrantSelectedOnly = ref(false);
const draftToolGrantIds = ref<number[]>([]);
const activeAppId = ref<number | null>(null);
const integrationDialogVisible = ref(false);
const integrationApp = ref<ProjectAppSummary | null>(null);
const accessCredential = ref<ProjectAppAccessCredential | null>(null);
const issuedClientSecret = ref("");
const allowedOriginsText = ref("");
const accessLoading = ref(false);
const accessSavingAction = ref<"" | "create" | "update" | "enable" | "reset" | "revoke">("");
const categoryPath = ref<number[]>([]);
const appDialogVisible = ref(false);
const appDialogSaving = ref(false);
const editingApp = ref<ProjectAppSummary | null>(null);

const appForm = reactive({
  name: "",
  code: "",
  widget_version: "1.0.0",
  terminal_type: "web" as ProjectAppTerminalType,
  description: "",
});

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
const activeApp = computed(() => apps.value.find((item) => item.id === activeAppId.value) ?? apps.value[0] ?? null);
const appDialogTitle = computed(() => (editingApp.value ? "编辑应用端" : "新建应用端"));
const appDialogSubmitText = computed(() => (editingApp.value ? "保存应用端" : "创建应用端"));
const grantedToolIdSet = computed(() => new Set(toolGrants.value.map((grant) => grant.agent_tool_id)));
const grantedProviderCount = computed(
  () => new Set(toolGrants.value.map((grant) => grant.provider_id)).size,
);
const toolGrantHasChanges = computed(() => {
  const saved = [...grantedToolIdSet.value].sort((a, b) => a - b);
  const draft = [...new Set(draftToolGrantIds.value)].sort((a, b) => a - b);
  return saved.length !== draft.length || saved.some((id, index) => id !== draft[index]);
});
const groupedAvailableTools = computed(() => {
  const keyword = toolGrantKeyword.value.trim().toLowerCase();
  const selectedIds = new Set(draftToolGrantIds.value);
  const filtered = availableTools.value.filter((tool) => {
    if (toolGrantSelectedOnly.value && !selectedIds.has(tool.id)) {
      return false;
    }
    if (!keyword) {
      return true;
    }
    return [tool.name, tool.tool_key, tool.provider_name, tool.agent_description, tool.external_description]
      .some((value) => String(value || "").toLowerCase().includes(keyword));
  });
  const groups = new Map<number, { providerId: number; providerName: string; tools: AgentTool[] }>();
  for (const tool of filtered) {
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

let toolGrantRequestSequence = 0;


function formatTerminalType(value: ProjectAppTerminalType) {
  return PROJECT_APP_TERMINAL_TYPE_LABELS[value] ?? "其他";
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function getTerminalIcon(value: ProjectAppTerminalType) {
  if (value === "web" || value === "h5") {
    return Monitor;
  }
  if (value === "mini_program") {
    return Grid;
  }
  if (value === "admin") {
    return Setting;
  }
  return value === "api" ? Connection : Link;
}

function getTerminalIconClass(value: ProjectAppTerminalType) {
  return `project-app-workspace-page__terminal-icon--${value}`;
}

function buildUpdatePayload(
  app: ProjectAppSummary,
  overrides: Partial<ProjectAppUpsertPayload> = {},
): ProjectAppUpsertPayload {
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
  };
}

function normalizeCode(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_")
    .replace(/[^a-z0-9_]/g, "")
    .replace(/^_+|_+$/g, "")
    .slice(0, 120);
}

function resetAppForm() {
  appForm.name = "";
  appForm.code = "";
  appForm.widget_version = "1.0.0";
  appForm.terminal_type = "web";
  appForm.description = "";
  editingApp.value = null;
}

function findCategoryPath(
  nodes: DocumentCategoryTreeNode[],
  targetId: number,
  parentPath: number[] = [],
): number[] {
  for (const node of nodes) {
    const path = [...parentPath, node.id];
    if (node.id === targetId) {
      return path;
    }
    const childPath = findCategoryPath(node.children || [], targetId, path);
    if (childPath.length > 0) {
      return childPath;
    }
  }
  return [];
}

async function loadCategories(knowledgeBaseId: number | null, categoryId: number | null = null) {
  categoryTree.value = [];
  categoryPath.value = [];
  if (!knowledgeBaseId) {
    return;
  }

  categoryLoading.value = true;
  try {
    categoryTree.value = await listDocumentCategoriesTree(knowledgeBaseId);
    if (categoryId) {
      categoryPath.value = findCategoryPath(categoryTree.value, categoryId);
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "加载知识库分类失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    categoryLoading.value = false;
  }
}

async function listAllPublishedTools(teamId: number) {
  const pageSize = 100;
  const tools: AgentTool[] = [];
  let page = 1;
  let total = 0;
  do {
    const response = await listAgentTools({
      team_id: teamId,
      publish_status: "published",
      sync_status: "active",
      page,
      page_size: pageSize,
    });
    tools.push(...response.items);
    total = response.total;
    if (response.items.length === 0) {
      break;
    }
    page += 1;
  } while (tools.length < total);
  return tools;
}

async function loadOptionData(projectResponse: ProjectSummary) {
  const [assistantResponses, knowledgeBaseResponses, toolResponse] = await Promise.all([
    listAssistants({
      team_id: projectResponse.team_id,
      active_only: true,
      page: 1,
      page_size: 100,
    }),
    listKnowledgeBases({
      team_id: projectResponse.team_id,
      active_only: true,
      page: 1,
      page_size: 100,
    }),
    listAllPublishedTools(projectResponse.team_id),
  ]);
  assistants.value = assistantResponses.items;
  knowledgeBases.value = knowledgeBaseResponses.items;
  availableTools.value = toolResponse;
}

async function loadToolGrants(appId: number | null) {
  const requestSequence = ++toolGrantRequestSequence;
  toolGrants.value = [];
  if (!projectId.value || !appId) {
    return;
  }

  toolGrantLoading.value = true;
  try {
    const response = await listProjectAppToolGrants(projectId.value, appId);
    if (requestSequence === toolGrantRequestSequence && activeApp.value?.id === appId) {
      toolGrants.value = response.items;
    }
  } catch (error) {
    if (requestSequence === toolGrantRequestSequence) {
      const message = error instanceof Error ? error.message : "加载工具授权失败，请稍后重试。";
      ElMessage.error(message);
    }
  } finally {
    if (requestSequence === toolGrantRequestSequence) {
      toolGrantLoading.value = false;
    }
  }
}

async function loadPage() {
  if (!projectId.value || loading.value) {
    return;
  }

  loading.value = true;
  loadError.value = null;

  try {
    const projectResponse = await getProject(projectId.value);
    const [appResponses] = await Promise.all([
      listProjectApps(projectId.value, {
        status: "all",
        page: 1,
        page_size: 100,
      }),
      loadOptionData(projectResponse),
    ]);
    project.value = projectResponse;
    apps.value = appResponses.items;
    const requestedAppId = Number(route.query.appId);
    if (Number.isInteger(requestedAppId) && apps.value.some((item) => item.id === requestedAppId)) {
      activeAppId.value = requestedAppId;
    }
    if (!apps.value.some((item) => item.id === activeAppId.value)) {
      activeAppId.value = apps.value[0]?.id ?? null;
    }
    if (activeApp.value) {
      await loadCategories(activeApp.value.knowledge_base_id, activeApp.value.category_id);
    }
    await loadToolGrants(activeApp.value?.id ?? null);
    hasLoadedData.value = true;
  } catch (error) {
    if (hasLoadedData.value) {
      ElMessage.error(error instanceof Error ? error.message : "应用端刷新失败，请稍后重试。");
    } else {
      loadError.value = error;
    }
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
  appForm.widget_version = app.widget_version;
  appForm.terminal_type = app.terminal_type;
  appForm.description = app.description ?? "";
  appDialogVisible.value = true;
}

function selectApp(appId: number) {
  activeAppId.value = appId;
  const nextApp = apps.value.find((item) => item.id === appId) ?? null;
  void loadCategories(nextApp?.knowledge_base_id ?? null, nextApp?.category_id ?? null);
  void loadToolGrants(nextApp?.id ?? null);
}

async function handleToggleStatus(app: ProjectAppSummary, nextValue: boolean | string | number) {
  if (!projectId.value || statusLoadingId.value) {
    return;
  }

  statusLoadingId.value = app.id;
  try {
    const updated = await updateProjectApp(
      projectId.value,
      app.id,
      buildUpdatePayload(app, { is_active: Boolean(nextValue) }),
    );
    const index = apps.value.findIndex((item) => item.id === app.id);
    if (index >= 0) {
      apps.value[index] = updated;
    }
    activeAppId.value = updated.id;
    ElMessage.success(`已${updated.is_active ? "启用" : "停用"}应用端“${updated.name}”。`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "更新应用端状态失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    statusLoadingId.value = null;
  }
}

async function saveActiveAppConfig(
  key: "knowledge_base" | "category" | "assistant",
  overrides: Partial<ProjectAppUpsertPayload>,
  successMessage: string,
) {
  if (!projectId.value || !activeApp.value || configSavingKey.value) {
    return;
  }

  const app = activeApp.value;
  configSavingKey.value = key;
  try {
    const updated = await updateProjectApp(projectId.value, app.id, buildUpdatePayload(app, overrides));
    const index = apps.value.findIndex((item) => item.id === app.id);
    if (index >= 0) {
      apps.value[index] = updated;
    }
    activeAppId.value = updated.id;
    ElMessage.success(successMessage);
  } catch (error) {
    const message = error instanceof Error ? error.message : "保存应用端配置失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    configSavingKey.value = "";
  }
}

async function handleKnowledgeBaseChange(value: number | string | null) {
  const knowledgeBaseId = Number(value);
  const nextKnowledgeBaseId =
    Number.isInteger(knowledgeBaseId) && knowledgeBaseId > 0 ? knowledgeBaseId : null;
  await saveActiveAppConfig(
    "knowledge_base",
    {
      knowledge_base_id: nextKnowledgeBaseId,
      category_id: null,
    },
    "已更新知识库。",
  );
  await loadCategories(nextKnowledgeBaseId, null);
}

async function handleCategoryPathChange(value: unknown) {
  const selectedPath = Array.isArray(value)
    ? value.map((item) => Number(item)).filter((item) => Number.isInteger(item) && item > 0)
    : [];
  categoryPath.value = selectedPath;
  const categoryId = selectedPath.length > 0 ? selectedPath[selectedPath.length - 1] : null;
  await saveActiveAppConfig("category", { category_id: categoryId }, "已更新限定分类。");
}

async function handleAssistantChange(value: number | string | null) {
  const assistantId = Number(value);
  const nextAssistantId = Number.isInteger(assistantId) && assistantId > 0 ? assistantId : null;
  await saveActiveAppConfig("assistant", { default_assistant_id: nextAssistantId }, "已更新默认助手。");
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
  const selected = new Set(draftToolGrantIds.value);
  const selectedCount = tools.filter((tool) => selected.has(tool.id)).length;
  return selectedCount > 0 && selectedCount < tools.length;
}

function handleProviderSelection(tools: AgentTool[], selected: boolean | string | number) {
  const nextIds = new Set(draftToolGrantIds.value);
  for (const tool of tools) {
    if (selected === true) {
      nextIds.add(tool.id);
    } else {
      nextIds.delete(tool.id);
    }
  }
  draftToolGrantIds.value = [...nextIds].sort((a, b) => a - b);
}

function handleToolSelection(toolId: number, selected: boolean | string | number) {
  const nextIds = new Set(draftToolGrantIds.value);
  if (selected === true) {
    nextIds.add(toolId);
  } else {
    nextIds.delete(toolId);
  }
  draftToolGrantIds.value = [...nextIds].sort((a, b) => a - b);
}

async function handleSaveToolGrants() {
  if (!projectId.value || !activeApp.value || toolGrantSaving.value || !toolGrantHasChanges.value) {
    return;
  }
  const appId = activeApp.value.id;
  toolGrantSaving.value = true;
  try {
    const response = await replaceProjectAppToolGrants(
      projectId.value,
      appId,
      [...new Set(draftToolGrantIds.value)].sort((a, b) => a - b),
    );
    if (activeApp.value?.id !== appId) {
      return;
    }
    toolGrantRequestSequence += 1;
    toolGrants.value = response.items;
    toolGrantDialogVisible.value = false;
    ElMessage.success("工具授权已保存。");
  } catch (error) {
    const message = error instanceof Error ? error.message : "保存工具授权失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    toolGrantSaving.value = false;
  }
}

async function handleSaveAppBasicInfo() {
  if (!projectId.value || appDialogSaving.value) {
    return;
  }
  const name = appForm.name.trim();
  const code = normalizeCode(appForm.code);
  if (!name || !code) {
    ElMessage.warning("请填写应用端名称和编码。");
    return;
  }
  if (!/^\d+\.\d+\.\d+$/.test(appForm.widget_version)) {
    ElMessage.warning("Widget 版本必须是精确版本，例如 1.0.0。");
    return;
  }

  appDialogSaving.value = true;
  try {
    if (editingApp.value) {
      const updated = await updateProjectApp(
        projectId.value,
        editingApp.value.id,
        buildUpdatePayload(editingApp.value, {
          name,
          code,
          widget_version: appForm.widget_version,
          terminal_type: appForm.terminal_type,
          description: appForm.description.trim() || null,
        }),
      );
      const index = apps.value.findIndex((item) => item.id === updated.id);
      if (index >= 0) {
        apps.value[index] = updated;
      }
      activeAppId.value = updated.id;
      appDialogVisible.value = false;
      ElMessage.success(`已保存应用端“${updated.name}”。`);
      return;
    }

    const created = await createProjectApp(projectId.value, {
      name,
      code,
      widget_version: appForm.widget_version,
      terminal_type: appForm.terminal_type,
      description: appForm.description.trim() || null,
      knowledge_base_id: null,
      category_id: null,
      default_assistant_id: null,
      is_active: true,
    });
    apps.value = [created, ...apps.value];
    activeAppId.value = created.id;
    appDialogVisible.value = false;
    ElMessage.success(`已创建应用端“${created.name}”。`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "保存应用端失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    appDialogSaving.value = false;
  }
}

function handleAppDialogClosed() {
  if (!appDialogSaving.value) {
    resetAppForm();
  }
}

async function handleDeleteApp(app: ProjectAppSummary) {
  if (!projectId.value || deletingAppId.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定删除应用端“${app.name}”吗？删除后该嵌入入口将立即失效。`,
      "删除应用端",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
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
    const message = error instanceof Error ? error.message : "删除应用端失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    deletingAppId.value = null;
  }
}

async function openIntegration(app: ProjectAppSummary) {
  if (!app.is_active) {
    ElMessage.warning("当前应用端已停用，请先启用后再查看接入说明。");
    return;
  }

  integrationDialogVisible.value = true;
  integrationApp.value = app;
  accessCredential.value = null;
  issuedClientSecret.value = "";
  allowedOriginsText.value = "https://your-business.example.com";
  accessLoading.value = true;
  try {
    const credential = await getProjectAppAccess(projectId.value as number, app.id);
    accessCredential.value = credential;
    allowedOriginsText.value = credential.allowed_origins.join("\n");
  } catch (error) {
    if (!(error instanceof AppRequestError) || error.status !== 404) {
      ElMessage.error(error instanceof Error ? error.message : "加载业务接入凭证失败。");
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
  const hasInvalidOrigin = origins.some((origin) => {
    try {
      const parsed = new URL(origin);
      return !["http:", "https:"].includes(parsed.protocol) || parsed.origin !== origin;
    } catch {
      return true;
    }
  });
  if (!origins.length || hasInvalidOrigin) {
    ElMessage.warning("请填写不含路径的完整 HTTP 或 HTTPS Origin。");
    return null;
  }
  return origins;
}

async function handleCreateAccess() {
  if (!projectId.value || !integrationApp.value || accessSavingAction.value) return;
  const allowedOrigins = validateAllowedOrigins();
  if (!allowedOrigins) return;
  accessSavingAction.value = "create";
  try {
    const issued = await createProjectAppAccess(projectId.value, integrationApp.value.id, {
      allowed_origins: allowedOrigins,
    });
    accessCredential.value = issued;
    issuedClientSecret.value = issued.client_secret;
    allowedOriginsText.value = issued.allowed_origins.join("\n");
    ElMessage.success("业务接入已启用，请立即保存 Client Secret。");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "启用业务接入失败。");
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
    accessCredential.value = await updateProjectAppAccess(projectId.value, integrationApp.value.id, {
      allowed_origins: allowedOrigins,
    });
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
    accessCredential.value = await enableProjectAppAccess(
      projectId.value,
      integrationApp.value.id,
    );
    ElMessage.success("业务接入已重新启用。");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "重新启用业务接入失败。");
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
    await ElMessageBox.confirm("吊销后当前应用的 Widget Token 将失效，确定继续吗？", "吊销业务接入", {
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
    ElMessage.success("业务接入已吊销。");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "吊销业务接入失败。");
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

const agentPublicOrigin = window.location.origin.replace(/\/+$/, "");

const bootstrapEnvironmentCode = computed(() => `AGENT_BASE_URL=${agentPublicOrigin}/api/v1
AGENT_CLIENT_ID=${accessCredential.value?.client_id || "<启用后生成>"}
AGENT_CLIENT_SECRET=${issuedClientSecret.value || "<仅在启用或重置后显示>"}`);

const loaderCode = `<script
  src="${agentPublicOrigin}/agent-static/loader/v1/loader.js"
  data-bootstrap-endpoint="/api/agent/bootstrap"
  defer
>` + "<" + "/script>";

onMounted(() => {
  void loadPage();
});

watch(
  () => route.params.projectId,
  () => {
    activeAppId.value = null;
    void loadPage();
  },
);

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

    <AdminListPanel
      v-else
      class="project-app-workspace-page__panel"
    >
      <div class="project-app-workspace-page__header">
        <div class="project-app-workspace-page__title-row">
          <div>
            <h2>{{ project?.name || "项目应用端" }}</h2>
          </div>
          <el-button
            class="project-app-workspace-page__create-button"
            type="primary"
            @click="openCreateApp"
          >
            <el-icon><Plus /></el-icon>
            新建应用端
          </el-button>
        </div>

        <div
          v-if="apps.length > 0"
          class="project-app-workspace-page__tabs"
        >
          <div
            v-for="app in apps"
            :key="app.id"
            :class="[
              'project-app-workspace-page__tab',
              activeApp?.id === app.id ? 'project-app-workspace-page__tab--active' : '',
              !app.is_active ? 'project-app-workspace-page__tab--disabled' : '',
              app.is_active && (!app.knowledge_base_id || !app.default_assistant_id)
                ? 'project-app-workspace-page__tab--incomplete'
                : '',
            ]"
          >
            <button
              type="button"
              class="project-app-workspace-page__tab-main"
              @click="selectApp(app.id)"
            >
              <el-icon :class="getTerminalIconClass(app.terminal_type)">
                <component :is="getTerminalIcon(app.terminal_type)" />
              </el-icon>
              <span>{{ app.name }}</span>
            </button>
            <span
              v-if="app.is_active && (!app.knowledge_base_id || !app.default_assistant_id)"
              class="project-app-workspace-page__tab-badge"
            >
              未配置
            </span>
            <button
              type="button"
              class="project-app-workspace-page__tab-delete"
              :disabled="deletingAppId === app.id"
              @click.stop="handleDeleteApp(app)"
            >
              <el-icon><Delete /></el-icon>
            </button>
          </div>
        </div>
      </div>

      <AppEmpty
        v-if="apps.length === 0"
        v-loading="loading"
        title="当前项目暂无应用端"
        description="可以先创建一个应用端，再绑定助手和知识库。"
      >
        <el-button
          type="primary"
          @click="openCreateApp"
        >
          新建应用端
        </el-button>
      </AppEmpty>

      <section
        v-else-if="activeApp"
        class="project-app-workspace-page__body"
      >
        <div class="project-app-workspace-page__inspector">
          <section class="project-app-workspace-page__status-card">
            <div class="project-app-workspace-page__app-identity">
              <div
                :class="[
                  'project-app-workspace-page__app-icon',
                  getTerminalIconClass(activeApp.terminal_type),
                ]"
              >
                <el-icon><component :is="getTerminalIcon(activeApp.terminal_type)" /></el-icon>
              </div>
              <div>
                <div class="project-app-workspace-page__app-title">
                  <h3>{{ activeApp.name }}</h3>
                  <el-tag
                    size="small"
                    type="info"
                    effect="plain"
                  >
                    {{ activeApp.code }}
                  </el-tag>
                </div>
                <p>{{ activeApp.description?.trim() || "暂无说明" }}</p>
              </div>
            </div>

            <div class="project-app-workspace-page__status-control">
              <el-button
                class="project-app-workspace-page__icon-button"
                :icon="EditPen"
                circle
                plain
                title="编辑应用端"
                @click="openEditApp(activeApp)"
              />
              <span :class="activeApp.is_active ? 'is-active' : ''">{{ activeApp.is_active ? "在线" : "停用" }}</span>
              <el-switch
                :model-value="activeApp.is_active"
                :loading="statusLoadingId === activeApp.id"
                @change="handleToggleStatus(activeApp, $event)"
              />
            </div>
          </section>

          <section class="project-app-workspace-page__config-card">
            <div class="project-app-workspace-page__config-header">
              <div>
                <h3>问答引擎</h3>
                <p>为当前应用端指定回答来源、检索范围和默认助手。</p>
              </div>
            </div>

            <div class="project-app-workspace-page__config-list">
              <div class="project-app-workspace-page__config-row">
                <div class="project-app-workspace-page__row-icon project-app-workspace-page__row-icon--knowledge">
                  <el-icon><Collection /></el-icon>
                </div>
                <div class="project-app-workspace-page__config-copy">
                  <span>知识库</span>
                  <p>选择此应用端优先召回的业务知识来源。</p>
                </div>
                <el-select
                  :model-value="activeApp.knowledge_base_id"
                  clearable
                  filterable
                  placeholder="未绑定"
                  class="project-app-workspace-page__config-control"
                  :loading="configSavingKey === 'knowledge_base'"
                  @change="handleKnowledgeBaseChange"
                >
                  <el-option
                    v-for="item in knowledgeBases"
                    :key="item.id"
                    :label="item.name"
                    :value="item.id"
                  />
                </el-select>
              </div>
              <div class="project-app-workspace-page__config-row">
                <div class="project-app-workspace-page__row-icon project-app-workspace-page__row-icon--category">
                  <el-icon><Grid /></el-icon>
                </div>
                <div class="project-app-workspace-page__config-copy">
                  <span>分类范围</span>
                  <p>可选限定分类，让回答聚焦到具体业务边界。</p>
                </div>
                <el-cascader
                  v-model="categoryPath"
                  :options="categoryTree"
                  :props="categoryCascaderProps"
                  :disabled="!activeApp.knowledge_base_id || categoryLoading || configSavingKey === 'category'"
                  clearable
                  filterable
                  :placeholder="categoryLoading ? '分类加载中...' : '全部分类'"
                  class="project-app-workspace-page__config-control"
                  @change="handleCategoryPathChange"
                >
                  <template #default="{ data }">
                    <div class="project-app-workspace-page__category-option">
                      <span>{{ data.name }}</span>
                      <small>{{ data.document_count }} 个文档</small>
                    </div>
                  </template>
                </el-cascader>
              </div>
              <div class="project-app-workspace-page__config-row">
                <div class="project-app-workspace-page__row-icon project-app-workspace-page__row-icon--assistant">
                  <el-icon><Cpu /></el-icon>
                </div>
                <div class="project-app-workspace-page__config-copy">
                  <span>默认助手</span>
                  <p>选择对话人设、模型和回复策略。</p>
                </div>
                <el-select
                  :model-value="activeApp.default_assistant_id"
                  clearable
                  filterable
                  placeholder="未绑定"
                  class="project-app-workspace-page__config-control"
                  :loading="configSavingKey === 'assistant'"
                  @change="handleAssistantChange"
                >
                  <el-option
                    v-for="assistant in assistants"
                    :key="assistant.id"
                    :label="assistant.name"
                    :value="assistant.id"
                  >
                    <div class="project-app-workspace-page__assistant-option">
                      <span>{{ assistant.name }}</span>
                      <small>{{ assistant.llm_model_key || "未指定模型" }}</small>
                    </div>
                  </el-option>
                </el-select>
              </div>
            </div>
          </section>

          <section class="project-app-workspace-page__business-tool-card">
            <div class="project-app-workspace-page__config-header">
              <div>
                <h3>Agent 工具授权</h3>
                <p>控制当前应用端可以调用的业务能力。</p>
              </div>
              <div class="project-app-workspace-page__tool-header-actions">
                <router-link
                  class="project-app-workspace-page__plain-link"
                  to="/agent-integrations"
                >
                  工具目录
                </router-link>
                <el-button
                  type="primary"
                  :disabled="toolGrantLoading || availableTools.length === 0"
                  @click="openToolGrantManager"
                >
                  <el-icon><Setting /></el-icon>
                  管理授权
                </el-button>
              </div>
            </div>

            <div
              v-loading="toolGrantLoading"
              class="project-app-workspace-page__business-tool-body"
            >
              <div
                v-if="availableTools.length > 0"
                class="project-app-workspace-page__tool-summary"
              >
                <div>
                  <strong>{{ toolGrants.length }}</strong>
                  <span>已授权工具</span>
                </div>
                <div>
                  <strong>{{ availableTools.length }}</strong>
                  <span>可用工具</span>
                </div>
                <div>
                  <strong>{{ grantedProviderCount }}</strong>
                  <span>已覆盖提供方</span>
                </div>
                <p>
                  {{ toolGrants.length > 0
                    ? `当前应用可调用 ${toolGrants.length} 个已发布工具。`
                    : "当前应用尚未获得业务工具授权。" }}
                </p>
              </div>

              <div
                v-else
                class="project-app-workspace-page__binding-empty"
              >
                <strong>当前团队还没有已发布工具</strong>
                <span>请先在 Agent 工具页同步并发布工具。</span>
              </div>
            </div>
          </section>

          <section class="project-app-workspace-page__access-card">
            <div class="project-app-workspace-page__access-header">
              <div>
                <h3>接入信息</h3>
                <p>用于业务系统识别并嵌入当前应用端。</p>
              </div>
              <el-button
                class="project-app-workspace-page__link-button"
                type="primary"
                @click="openIntegration(activeApp)"
              >
                <el-icon><Link /></el-icon>
                管理业务接入
              </el-button>
            </div>

            <dl class="project-app-workspace-page__access-list">
              <div>
                <dt>终端类型</dt>
                <dd>{{ formatTerminalType(activeApp.terminal_type) }}</dd>
              </div>
              <div>
                <dt>应用编码</dt>
                <dd>{{ activeApp.code }}</dd>
              </div>
              <div>
                <dt>Widget 版本</dt>
                <dd>{{ activeApp.widget_version }}</dd>
              </div>
              <div>
                <dt>运行状态</dt>
                <dd :class="activeApp.is_active ? 'is-active' : ''">
                  {{ activeApp.is_active ? "在线" : "停用" }}
                </dd>
              </div>
              <div>
                <dt>更新时间</dt>
                <dd>{{ formatDateTime(activeApp.updated_at) }}</dd>
              </div>
            </dl>
          </section>
        </div>
      </section>
    </AdminListPanel>

    <el-drawer
      v-model="toolGrantDialogVisible"
      class="project-app-workspace-page__tool-drawer"
      size="720px"
      :show-close="!toolGrantSaving"
      :close-on-click-modal="!toolGrantSaving"
      :close-on-press-escape="!toolGrantSaving"
    >
      <template #header>
        <div class="project-app-workspace-page__drawer-title">
          <h3>管理工具授权</h3>
          <p>{{ activeApp?.name }} · 已选择 {{ draftToolGrantIds.length }} / {{ availableTools.length }}</p>
        </div>
      </template>

      <div class="project-app-workspace-page__tool-drawer-body">
        <div class="project-app-workspace-page__tool-toolbar">
          <el-input
            v-model="toolGrantKeyword"
            clearable
            placeholder="搜索工具名称、标识或提供方"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-checkbox v-model="toolGrantSelectedOnly">
            仅看已授权
          </el-checkbox>
        </div>

        <div class="project-app-workspace-page__tool-groups">
          <section
            v-for="group in groupedAvailableTools"
            :key="group.providerId"
            class="project-app-workspace-page__tool-group"
          >
            <div class="project-app-workspace-page__tool-group-header">
              <el-checkbox
                :model-value="isProviderFullySelected(group.tools)"
                :indeterminate="isProviderPartiallySelected(group.tools)"
                @change="handleProviderSelection(group.tools, $event)"
              >
                {{ group.providerName }}
              </el-checkbox>
              <span>{{ group.tools.length }} 个工具</span>
            </div>
            <label
              v-for="tool in group.tools"
              :key="tool.id"
              class="project-app-workspace-page__tool-option"
            >
              <el-checkbox
                :model-value="draftToolGrantIds.includes(tool.id)"
                @change="handleToolSelection(tool.id, $event)"
              />
              <div class="project-app-workspace-page__tool-option-main">
                <div class="project-app-workspace-page__tool-option-title">
                  <strong>{{ tool.name }}</strong>
                  <el-tag
                    v-if="tool.risk_level !== 'low'"
                    size="small"
                    :type="tool.risk_level === 'high' ? 'danger' : 'warning'"
                    effect="plain"
                  >
                    {{ tool.risk_level === "high" ? "高风险" : "中风险" }}
                  </el-tag>
                  <el-tag
                    v-if="tool.requires_confirmation"
                    size="small"
                    type="warning"
                    effect="plain"
                  >
                    调用前确认
                  </el-tag>
                </div>
                <p>{{ tool.agent_description || tool.external_description || "暂无工具说明" }}</p>
                <span>{{ tool.tool_key }}</span>
              </div>
            </label>
          </section>
        </div>

        <AppEmpty
          v-if="groupedAvailableTools.length === 0"
          title="没有匹配的工具"
          description="请调整搜索词或关闭仅看已授权。"
        />
      </div>

      <template #footer>
        <div class="project-app-workspace-page__drawer-footer">
          <span>已选择 {{ draftToolGrantIds.length }} 个工具</span>
          <div>
            <el-button
              :disabled="toolGrantSaving"
              @click="toolGrantDialogVisible = false"
            >
              取消
            </el-button>
            <el-button
              type="primary"
              :loading="toolGrantSaving"
              :disabled="!toolGrantHasChanges"
              @click="handleSaveToolGrants"
            >
              保存授权
            </el-button>
          </div>
        </div>
      </template>
    </el-drawer>

    <AdminDialog
      v-model="integrationDialogVisible"
      width="720px"
      :title="integrationApp ? `业务接入：${integrationApp.name}` : '业务接入'"
    >
      <div v-loading="accessLoading">
        <div class="project-app-workspace-page__integration-summary">
          <div>
            <span>当前应用</span>
            <strong>{{ integrationApp?.name || "-" }}</strong>
          </div>
          <div>
            <span>Client ID</span>
            <strong>{{ accessCredential?.client_id || "尚未生成" }}</strong>
          </div>
          <div>
            <span>接入状态</span>
            <strong>{{ accessCredential?.enabled ? "已启用" : accessCredential ? "已吊销" : "未启用" }}</strong>
          </div>
        </div>

        <el-alert
          v-if="issuedClientSecret"
          class="project-app-workspace-page__integration-secret"
          title="Client Secret 只显示这一次，请立即保存到业务后端的密钥配置。"
          type="warning"
          :closable="false"
          show-icon
        >
          <template #default>
            <div class="project-app-workspace-page__secret-value">
              <code>{{ issuedClientSecret }}</code>
              <el-button
                size="small"
                @click="copyText(issuedClientSecret, 'Client Secret 已复制。')"
              >
                复制
              </el-button>
            </div>
          </template>
        </el-alert>

        <section class="project-app-workspace-page__integration-step">
          <div class="project-app-workspace-page__integration-step-header">
            <div>
              <span>浏览器来源</span>
              <h3>允许的 Origin</h3>
              <p>每行填写一个完整 Origin，例如 https://b2c.example.com。</p>
            </div>
          </div>
          <el-input
            v-model="allowedOriginsText"
            type="textarea"
            :rows="3"
            placeholder="https://b2c.example.com"
          />
          <div class="project-app-workspace-page__integration-actions">
            <el-button
              v-if="!accessCredential"
              type="primary"
              :loading="accessSavingAction === 'create'"
              @click="handleCreateAccess"
            >
              启用业务接入
            </el-button>
            <template v-else>
              <el-button
                :loading="accessSavingAction === 'update'"
                @click="handleUpdateAccess"
              >
                保存 Origin
              </el-button>
              <el-button
                :loading="accessSavingAction === 'reset'"
                @click="handleResetAccessSecret"
              >
                重置 Secret
              </el-button>
              <el-button
                v-if="!accessCredential.enabled"
                type="primary"
                :loading="accessSavingAction === 'enable'"
                @click="handleEnableExistingAccess"
              >
                重新启用
              </el-button>
              <el-button
                v-else
                type="danger"
                plain
                :loading="accessSavingAction === 'revoke'"
                @click="handleRevokeAccess"
              >
                吊销接入
              </el-button>
            </template>
          </div>
        </section>

        <section
          v-if="accessCredential"
          class="project-app-workspace-page__integration-step"
        >
          <div class="project-app-workspace-page__integration-step-header">
            <div>
              <span>服务端配置</span>
              <h3>业务 Bootstrap 环境变量</h3>
              <p>业务后端验证登录与权限后，使用这组凭证调用 Agent 的 /integration/bootstrap。</p>
            </div>
            <el-button
              size="small"
              @click="copyText(bootstrapEnvironmentCode, '环境变量模板已复制。')"
            >
              复制
            </el-button>
          </div>
          <div class="project-app-workspace-page__code-block">
            <pre>{{ bootstrapEnvironmentCode }}</pre>
          </div>
          <div class="project-app-workspace-page__credential-meta">
            <span>Secret 尾号：{{ accessCredential.client_secret_last_four }}</span>
            <span>Token 版本：{{ accessCredential.token_version }}</span>
          </div>
        </section>

        <section
          v-if="accessCredential"
          class="project-app-workspace-page__integration-step"
        >
          <div class="project-app-workspace-page__integration-step-header">
            <div>
              <span>浏览器接入</span>
              <h3>加载 CDN Loader</h3>
              <p>按钮和权限展示由业务前端负责；Loader 只在用户触发时启动 Widget。</p>
            </div>
            <el-button
              size="small"
              @click="copyText(loaderCode, 'Loader 代码已复制。')"
            >
              复制
            </el-button>
          </div>
          <div class="project-app-workspace-page__code-block">
            <pre>{{ loaderCode }}</pre>
          </div>
        </section>
      </div>
    </AdminDialog>

    <AdminDialog
      v-model="appDialogVisible"
      :title="appDialogTitle"
      :loading="appDialogSaving"
      @closed="handleAppDialogClosed"
    >
      <el-form
        label-position="top"
        class="project-app-workspace-page__create-form"
      >
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item
              label="应用端名称"
              required
            >
              <el-input
                v-model="appForm.name"
                maxlength="100"
                placeholder="例如：Web H5 演示端"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item
              label="应用端编码"
              required
            >
              <el-input
                v-model="appForm.code"
                maxlength="120"
                placeholder="例如：demo_web_01"
                @blur="appForm.code = normalizeCode(appForm.code)"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="终端类型">
              <el-select
                v-model="appForm.terminal_type"
                class="project-app-workspace-page__create-full"
              >
                <el-option
                  v-for="(label, value) in PROJECT_APP_TERMINAL_TYPE_LABELS"
                  :key="value"
                  :label="label"
                  :value="value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item
              label="Widget 精确版本"
              required
            >
              <el-input
                v-model="appForm.widget_version"
                maxlength="30"
                placeholder="例如：1.0.0"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="描述说明">
              <el-input
                v-model="appForm.description"
                type="textarea"
                :rows="3"
                maxlength="500"
                show-word-limit
                placeholder="简要描述该应用端的使用场景或接入方"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="appDialogVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="appDialogSaving"
          @click="handleSaveAppBasicInfo"
        >
          {{ appDialogSubmitText }}
        </el-button>
      </template>
    </AdminDialog>
  </section>
</template>

<style scoped>
.project-app-workspace-page {
  display: flex;
  min-height: 0;
  flex-direction: column;
}

.project-app-workspace-page__panel {
  min-height: 0;
  border: 0;
  background: #ffffff;
  box-shadow: none;
}

.project-app-workspace-page__header {
  display: grid;
  gap: 22px;
  border-bottom: 1px solid #e5e7eb;
  background: #ffffff;
  padding: 0 0 0;
}

.project-app-workspace-page__title-row,
.project-app-workspace-page__app-title,
.project-app-workspace-page__status-control,
.project-app-workspace-page__config-header,
.project-app-workspace-page__access-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.project-app-workspace-page__title-row {
  justify-content: space-between;
  gap: 16px;
  padding: 0 8px;
}

.project-app-workspace-page__title-row h2 {
  margin: 0;
  color: #020617;
  font-size: 28px;
  font-weight: 800;
  line-height: 1.2;
}

.project-app-workspace-page__create-button {
  --el-button-bg-color: #0f172a;
  --el-button-border-color: #0f172a;
  --el-button-hover-bg-color: #1e293b;
  --el-button-hover-border-color: #1e293b;
  height: 40px;
  border-radius: 12px;
  padding: 0 18px;
  font-weight: 700;
}

.project-app-workspace-page__tabs {
  display: flex;
  gap: 30px;
  overflow-x: auto;
  padding: 0 8px;
}

.project-app-workspace-page__tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: var(--admin-text-muted);
  padding: 0 0 15px;
}

.project-app-workspace-page__tab:hover,
.project-app-workspace-page__tab--active {
  border-bottom-color: var(--admin-primary);
  color: var(--admin-primary);
}

.project-app-workspace-page__tab--disabled {
  opacity: 0.58;
}

.project-app-workspace-page__tab--incomplete {
  color: #b45309;
}

.project-app-workspace-page__tab-main {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0;
  text-align: left;
}

.project-app-workspace-page__tab-main span,
.project-app-workspace-page__tab small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-app-workspace-page__tab-main span {
  font-size: 14px;
  font-weight: 500;
}

.project-app-workspace-page__tab-main > .el-icon {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  border-radius: 7px;
  font-size: 14px;
}

.project-app-workspace-page__tab-badge {
  flex-shrink: 0;
  border: 1px solid #fed7aa;
  border-radius: 999px;
  background: #fff7ed;
  color: #b45309;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  padding: 4px 7px;
}

.project-app-workspace-page__tab-delete {
  display: inline-flex;
  width: 20px;
  height: 20px;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s ease, background 0.15s ease, color 0.15s ease;
}

.project-app-workspace-page__tab:hover .project-app-workspace-page__tab-delete,
.project-app-workspace-page__tab--active .project-app-workspace-page__tab-delete {
  opacity: 1;
}

.project-app-workspace-page__tab-delete:hover {
  background: #fee2e2;
  color: #dc2626;
}

.project-app-workspace-page__tab-delete:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.project-app-workspace-page__body {
  min-height: 0;
  width: min(960px, 100%);
  margin: 0 auto;
  padding: 32px 8px 0;
}

.project-app-workspace-page__inspector {
  display: flex;
  min-height: 0;
  flex-direction: column;
  gap: 24px;
}

.project-app-workspace-page__status-card,
.project-app-workspace-page__config-card,
.project-app-workspace-page__business-tool-card,
.project-app-workspace-page__access-card {
  border: 1px solid var(--admin-border);
  border-radius: 18px;
  background: var(--admin-surface);
  box-shadow: 0 16px 45px rgba(15, 23, 42, 0.04);
}

.project-app-workspace-page__status-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 80px;
  padding: 16px;
}

.project-app-workspace-page__app-identity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 12px;
}

.project-app-workspace-page__app-icon {
  display: inline-flex;
  width: 50px;
  height: 50px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--admin-border-soft);
  border-radius: 14px;
  background: #f8fafc;
  color: #0f172a;
  font-size: 24px;
}

.project-app-workspace-page__app-title {
  flex-wrap: wrap;
}

.project-app-workspace-page__app-title h3,
.project-app-workspace-page__config-header h3,
.project-app-workspace-page__access-header h3,
.project-app-workspace-page__dialog-title {
  margin: 0;
  color: #020617;
  font-size: 16px;
  font-weight: 800;
}

.project-app-workspace-page__app-identity p,
.project-app-workspace-page__config-header p,
.project-app-workspace-page__access-header p,
.project-app-workspace-page__config-row p {
  margin: 4px 0 0;
  color: var(--admin-text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.project-app-workspace-page__status-control {
  flex-shrink: 0;
  border-left: 1px solid #eef2f7;
  padding-left: 16px;
}

.project-app-workspace-page__sandbox-button {
  margin-left: 0;
}

.project-app-workspace-page__icon-button {
  width: 32px;
  height: 32px;
  border-color: #e2e8f0;
  color: #64748b;
}

.project-app-workspace-page__icon-button:hover {
  border-color: var(--admin-primary-border);
  color: var(--admin-primary);
}

.project-app-workspace-page__status-control span {
  color: var(--admin-text-muted);
  font-size: 13px;
  font-weight: 600;
}

.project-app-workspace-page__status-control span.is-active {
  color: #059669;
}

.project-app-workspace-page__config-card {
  overflow: hidden;
}

.project-app-workspace-page__business-tool-card {
  overflow: hidden;
}

.project-app-workspace-page__config-header,
.project-app-workspace-page__access-header {
  justify-content: space-between;
  border-bottom: 1px solid #eef2f7;
  background: #ffffff;
  padding: 20px 24px;
}

.project-app-workspace-page__access-header {
  align-items: flex-start;
}

.project-app-workspace-page__link-button {
  border-radius: 10px;
}

.project-app-workspace-page__plain-link {
  flex-shrink: 0;
  color: var(--admin-primary);
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}

.project-app-workspace-page__plain-link:hover {
  color: var(--admin-primary-strong);
}

.project-app-workspace-page__tool-header-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

.project-app-workspace-page__config-list {
  display: grid;
}

.project-app-workspace-page__config-row {
  display: flex;
  align-items: center;
  gap: 16px;
  border-bottom: 1px solid #eef2f7;
  padding: 26px 24px;
}

.project-app-workspace-page__config-row:last-child {
  border-bottom: 0;
}

.project-app-workspace-page__config-row span {
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
}

.project-app-workspace-page__config-copy {
  min-width: 0;
  flex: 1;
}

.project-app-workspace-page__config-control {
  margin-left: auto;
  width: 240px;
  flex-shrink: 0;
}

.project-app-workspace-page__config-control :deep(.el-input),
.project-app-workspace-page__config-control :deep(.el-select__wrapper),
.project-app-workspace-page__config-control :deep(.el-cascader__tags) {
  width: 100%;
}

.project-app-workspace-page__category-option,
.project-app-workspace-page__assistant-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.project-app-workspace-page__category-option small,
.project-app-workspace-page__assistant-option small {
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.project-app-workspace-page__row-icon {
  display: inline-flex;
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  font-size: 20px;
}

.project-app-workspace-page__row-icon--knowledge {
  background: var(--admin-primary-soft);
  color: var(--admin-primary);
}

.project-app-workspace-page__row-icon--category {
  background: #f5f3ff;
  color: #7c3aed;
}

.project-app-workspace-page__row-icon--assistant {
  background: #ecfdf5;
  color: #059669;
}

.project-app-workspace-page__business-tool-body {
  display: grid;
  gap: 14px;
  padding: 0;
}

.project-app-workspace-page__tool-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  padding: 0 24px;
}

.project-app-workspace-page__tool-summary > div {
  border-right: 1px solid #eef2f7;
  padding: 20px 24px 20px 0;
}

.project-app-workspace-page__tool-summary > div + div {
  padding-left: 24px;
}

.project-app-workspace-page__tool-summary > div:nth-child(3) {
  border-right: 0;
}

.project-app-workspace-page__tool-summary strong,
.project-app-workspace-page__tool-summary span {
  display: block;
}

.project-app-workspace-page__tool-summary strong {
  color: #0f172a;
  font-size: 24px;
  font-weight: 800;
}

.project-app-workspace-page__tool-summary span {
  margin-top: 4px;
  color: var(--admin-text-muted);
  font-size: 12px;
}

.project-app-workspace-page__tool-summary p {
  grid-column: 1 / -1;
  margin: 0 -24px;
  border-top: 1px solid #eef2f7;
  background: #f8fafc;
  color: var(--admin-text-muted);
  font-size: 12px;
  padding: 12px 24px;
}

.project-app-workspace-page__binding-empty {
  display: grid;
  gap: 5px;
  border: 1px dashed #cbd5e1;
  border-radius: var(--admin-radius-md);
  background: #f8fafc;
  color: var(--admin-text-muted);
  font-size: 13px;
  padding: 18px;
  text-align: center;
}

.project-app-workspace-page__binding-empty strong {
  color: var(--admin-text-secondary);
  font-size: 13px;
}

.project-app-workspace-page__binding-empty span {
  color: var(--admin-text-muted);
  font-size: 12px;
}

.project-app-workspace-page__terminal-icon--web {
  background: var(--admin-primary-soft);
  color: var(--admin-primary);
}

.project-app-workspace-page__terminal-icon--h5 {
  background: #f0fdfa;
  color: #0f766e;
}

.project-app-workspace-page__terminal-icon--mini_program {
  background: #f5f3ff;
  color: #7c3aed;
}

.project-app-workspace-page__terminal-icon--admin {
  background: #fff7ed;
  color: #c2410c;
}

.project-app-workspace-page__terminal-icon--api {
  background: #ecfdf5;
  color: #047857;
}

.project-app-workspace-page__terminal-icon--other {
  background: #f8fafc;
  color: #475569;
}

.project-app-workspace-page__access-card {
  overflow: hidden;
}

.project-app-workspace-page__access-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0;
  margin: 16px;
}

.project-app-workspace-page__access-list div {
  min-width: 0;
  border-right: 1px solid #eef2f7;
  border-bottom: 1px solid #eef2f7;
  padding: 16px 18px;
}

.project-app-workspace-page__access-list div:nth-child(2n) {
  border-right: 0;
}

.project-app-workspace-page__access-list div:nth-last-child(-n + 2) {
  border-bottom: 0;
}

.project-app-workspace-page__access-list dt {
  margin: 0 0 6px;
  color: var(--admin-text-muted);
  font-size: 12px;
}

.project-app-workspace-page__access-list dd {
  overflow: hidden;
  margin: 0;
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-app-workspace-page__access-list dd.is-active {
  color: #059669;
}

.project-app-workspace-page__drawer-title h3 {
  margin: 0;
  color: #0f172a;
  font-size: 17px;
  font-weight: 800;
}

.project-app-workspace-page__drawer-title p {
  margin: 4px 0 0;
  color: var(--admin-text-muted);
  font-size: 12px;
}

.project-app-workspace-page__tool-drawer-body,
.project-app-workspace-page__sandbox-drawer-content {
  display: flex;
  min-height: 100%;
  flex-direction: column;
}

.project-app-workspace-page__sandbox-drawer-content {
  width: 100%;
  min-width: 0;
  flex: 1;
}

.project-app-workspace-page__tool-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 18px;
  border-bottom: 1px solid #eef2f7;
  padding-bottom: 18px;
}

.project-app-workspace-page__tool-groups {
  display: grid;
  gap: 22px;
  padding: 20px 0;
}

.project-app-workspace-page__tool-group {
  border: 1px solid var(--admin-border);
  border-radius: 8px;
  overflow: hidden;
}

.project-app-workspace-page__tool-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid #e5e7eb;
  background: #f8fafc;
  padding: 12px 16px;
}

.project-app-workspace-page__tool-group-header span {
  color: var(--admin-text-muted);
  font-size: 12px;
}

.project-app-workspace-page__tool-option {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 12px;
  cursor: pointer;
  padding: 15px 16px;
}

.project-app-workspace-page__tool-option + .project-app-workspace-page__tool-option {
  border-top: 1px solid #eef2f7;
}

.project-app-workspace-page__tool-option:hover {
  background: #f8fafc;
}

.project-app-workspace-page__tool-option-main {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 5px;
}

.project-app-workspace-page__tool-option-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.project-app-workspace-page__tool-option-title strong {
  color: #0f172a;
  font-size: 14px;
}

.project-app-workspace-page__tool-option-main p {
  margin: 0;
  color: var(--admin-text-muted);
  font-size: 12px;
  line-height: 1.55;
}

.project-app-workspace-page__tool-option-main > span {
  overflow-wrap: anywhere;
  color: var(--admin-text-subtle);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 11px;
}

.project-app-workspace-page__drawer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.project-app-workspace-page__drawer-footer > span {
  color: var(--admin-text-muted);
  font-size: 13px;
}

.project-app-workspace-page__sandbox-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  border-bottom: 1px solid #eef2f7;
  padding-bottom: 16px;
}

.project-app-workspace-page__sandbox-store {
  width: 180px;
}

.project-app-workspace-page__sandbox-body {
  display: flex;
  flex: 1;
  min-height: 0;
  margin-top: 16px;
  overflow: hidden;
  background: #fafafa;
  padding: 0;
}

.project-app-workspace-page__iframe {
  flex: 1;
  width: 100%;
  min-height: 0;
  border: 1px solid var(--admin-border);
  border-radius: var(--admin-radius-md);
  background: var(--admin-surface);
}

.project-app-workspace-page__sandbox-empty {
  width: 100%;
  padding: 36px;
}

.project-app-workspace-page__sandbox-empty :deep(.app-empty__icon) {
  width: 58px;
  height: 58px;
  border-radius: 8px;
}

.project-app-workspace-page :deep(.project-app-workspace-page__tool-drawer),
.project-app-workspace-page :deep(.project-app-workspace-page__sandbox-drawer) {
  max-width: 100%;
}

.project-app-workspace-page :deep(.project-app-workspace-page__sandbox-drawer .el-drawer__body) {
  display: flex;
  min-height: 0;
}

.project-app-workspace-page__integration-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  border-radius: var(--admin-radius-md);
  background: #ffffff;
}

.project-app-workspace-page__integration-summary div {
  min-width: 0;
  border-right: 1px solid #eef2f7;
  padding: 14px 16px;
}

.project-app-workspace-page__integration-summary div:last-child {
  border-right: 0;
}

.project-app-workspace-page__integration-summary span {
  display: block;
  margin-bottom: 6px;
  color: var(--admin-text-muted);
  font-size: 12px;
}

.project-app-workspace-page__integration-summary strong {
  display: block;
  overflow: hidden;
  color: #0f172a;
  font-size: 13px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-app-workspace-page__integration-alert {
  margin-top: 14px;
  border: 1px solid #fed7aa;
  border-radius: var(--admin-radius-md);
  background: #fff7ed;
  color: #9a3412;
  font-size: 13px;
  line-height: 1.6;
  padding: 12px 14px;
}

.project-app-workspace-page__integration-secret {
  margin-top: 14px;
}

.project-app-workspace-page__secret-value {
  display: flex;
  min-width: 0;
  margin-top: 8px;
  align-items: center;
  gap: 10px;
}

.project-app-workspace-page__secret-value code {
  min-width: 0;
  overflow-wrap: anywhere;
  color: #7c2d12;
}

.project-app-workspace-page__integration-actions,
.project-app-workspace-page__credential-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.project-app-workspace-page__credential-meta {
  color: var(--admin-text-muted);
  font-size: 12px;
}

.project-app-workspace-page__integration-step {
  display: grid;
  gap: 12px;
  margin-top: 16px;
  border: 1px solid #e5e7eb;
  border-radius: var(--admin-radius-md);
  background: #ffffff;
  padding: 16px;
}

.project-app-workspace-page__integration-step-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.project-app-workspace-page__integration-step-header span {
  display: block;
  margin-bottom: 4px;
  color: var(--admin-primary);
  font-size: 12px;
  font-weight: 800;
}

.project-app-workspace-page__integration-step-header h3 {
  margin: 0;
  color: #0f172a;
  font-size: 15px;
  font-weight: 800;
}

.project-app-workspace-page__integration-step-header p {
  margin: 4px 0 0;
  color: var(--admin-text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.project-app-workspace-page__code-block {
  overflow: auto;
  border-radius: var(--admin-radius-md);
  background: #0f172a;
  color: #e2e8f0;
  padding: 18px;
}

.project-app-workspace-page__code-block pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.project-app-workspace-page__create-form {
  padding-top: 4px;
}

.project-app-workspace-page__create-full {
  width: 100%;
}

@media (max-width: 760px) {
  .project-app-workspace-page__title-row,
  .project-app-workspace-page__status-card,
  .project-app-workspace-page__config-header {
    align-items: stretch;
    flex-direction: column;
  }

  .project-app-workspace-page__body {
    padding: 14px;
  }

  .project-app-workspace-page__config-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .project-app-workspace-page__config-control {
    width: 100%;
    margin-left: 0;
  }

  .project-app-workspace-page__tool-header-actions {
    justify-content: space-between;
  }

  .project-app-workspace-page__sandbox-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .project-app-workspace-page__sandbox-store {
    width: 100%;
  }

  .project-app-workspace-page__tool-summary {
    grid-template-columns: 1fr;
  }

  .project-app-workspace-page__tool-summary > div,
  .project-app-workspace-page__tool-summary > div + div {
    border-right: 0;
    border-bottom: 1px solid #eef2f7;
    padding: 14px 0;
  }

  .project-app-workspace-page__tool-toolbar {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .project-app-workspace-page__drawer-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .project-app-workspace-page__secret-value {
    align-items: stretch;
    flex-direction: column;
  }

  .project-app-workspace-page__access-list {
    grid-template-columns: 1fr;
  }

  .project-app-workspace-page__access-list div,
  .project-app-workspace-page__access-list div:nth-child(2n),
  .project-app-workspace-page__access-list div:nth-last-child(-n + 2) {
    border-right: 0;
    border-bottom: 1px solid #eef2f7;
  }

  .project-app-workspace-page__access-list div:last-child {
    border-bottom: 0;
  }

  .project-app-workspace-page__status-control {
    justify-content: flex-start;
    border-left: 0;
    border-top: 1px solid var(--admin-border-soft);
    padding: 12px 0 0;
  }
}
</style>
