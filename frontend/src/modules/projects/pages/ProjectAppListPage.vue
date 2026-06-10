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
  Refresh,
  Setting,
} from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import AdminDialog from "@/app/components/admin/AdminDialog.vue";
import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import { listAssistants } from "@/shared/api/assistants";
import { listDocumentCategoriesTree } from "@/shared/api/document-categories";
import { listKnowledgeBases } from "@/shared/api/knowledge-bases";
import {
  createProjectApp,
  createProjectAppEmbedPreview,
  deleteProjectApp,
  getProject,
  listProjectApps,
  updateProjectApp,
} from "@/shared/api/projects";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import { isForbiddenError } from "@/shared/utils/error";
import type { AssistantSummary } from "@/shared/types/assistant";
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
const knowledgeBases = ref<KnowledgeBaseListItem[]>([]);
const categoryTree = ref<DocumentCategoryTreeNode[]>([]);
const loading = ref(false);
const loadError = ref<unknown>(null);
const hasLoadedData = ref(false);
const statusLoadingId = ref<number | null>(null);
const deletingAppId = ref<number | null>(null);
const configSavingKey = ref<"" | "knowledge_base" | "category" | "assistant">("");
const categoryLoading = ref(false);
const activeAppId = ref<number | null>(null);
const integrationDialogVisible = ref(false);
const integrationApp = ref<ProjectAppSummary | null>(null);
const previewLoading = ref(false);
const previewEmbedUrl = ref("");
const previewNeedsRefresh = ref(false);
const categoryPath = ref<number[]>([]);
const appDialogVisible = ref(false);
const appDialogSaving = ref(false);
const editingApp = ref<ProjectAppSummary | null>(null);

const appForm = reactive({
  name: "",
  code: "",
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
const canPreviewActiveApp = computed(
  () => Boolean(activeApp.value?.is_active && activeApp.value.knowledge_base_id && activeApp.value.default_assistant_id),
);
const hasFreshPreview = computed(() => Boolean(previewEmbedUrl.value && !previewNeedsRefresh.value));
const previewUnavailableDescription = computed(() => {
  if (!activeApp.value?.is_active) {
    return "启用后才能生成沙盒测试链接。";
  }
  const missingItems = [];
  if (!activeApp.value.knowledge_base_id) {
    missingItems.push("知识库");
  }
  if (!activeApp.value.default_assistant_id) {
    missingItems.push("默认助手");
  }
  return missingItems.length > 0
    ? `请先选择${missingItems.join("和")}后再生成沙盒测试。`
    : "配置已就绪，可以生成测试会话。";
});
const appDialogTitle = computed(() => (editingApp.value ? "编辑应用端" : "新建应用端"));
const appDialogSubmitText = computed(() => (editingApp.value ? "保存应用端" : "创建应用端"));

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

async function loadOptionData(projectResponse: ProjectSummary) {
  const [assistantResponses, knowledgeBaseResponses] = await Promise.all([
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
  ]);
  assistants.value = assistantResponses.items;
  knowledgeBases.value = knowledgeBaseResponses.items;
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
    if (!apps.value.some((item) => item.id === activeAppId.value)) {
      activeAppId.value = apps.value[0]?.id ?? null;
    }
    if (activeApp.value) {
      await loadCategories(activeApp.value.knowledge_base_id, activeApp.value.category_id);
    }
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
  appForm.terminal_type = app.terminal_type;
  appForm.description = app.description ?? "";
  appDialogVisible.value = true;
}

function selectApp(appId: number) {
  activeAppId.value = appId;
  previewEmbedUrl.value = "";
  previewNeedsRefresh.value = false;
  const nextApp = apps.value.find((item) => item.id === appId) ?? null;
  void loadCategories(nextApp?.knowledge_base_id ?? null, nextApp?.category_id ?? null);
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
    if (previewEmbedUrl.value) {
      previewNeedsRefresh.value = true;
    }
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
    if (previewEmbedUrl.value) {
      previewNeedsRefresh.value = true;
    }
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

  appDialogSaving.value = true;
  try {
    if (editingApp.value) {
      const updated = await updateProjectApp(
        projectId.value,
        editingApp.value.id,
        buildUpdatePayload(editingApp.value, {
          name,
          code,
          terminal_type: appForm.terminal_type,
          description: appForm.description.trim() || null,
        }),
      );
      const index = apps.value.findIndex((item) => item.id === updated.id);
      if (index >= 0) {
        apps.value[index] = updated;
      }
      activeAppId.value = updated.id;
      previewEmbedUrl.value = "";
      previewNeedsRefresh.value = false;
      appDialogVisible.value = false;
      ElMessage.success(`已保存应用端“${updated.name}”。`);
      return;
    }

    const created = await createProjectApp(projectId.value, {
      name,
      code,
      terminal_type: appForm.terminal_type,
      description: appForm.description.trim() || null,
      knowledge_base_id: null,
      category_id: null,
      default_assistant_id: null,
      is_active: true,
    });
    apps.value = [created, ...apps.value];
    activeAppId.value = created.id;
    previewEmbedUrl.value = "";
    previewNeedsRefresh.value = false;
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
    previewEmbedUrl.value = "";
    previewNeedsRefresh.value = false;
    ElMessage.success(`已删除应用端“${app.name}”。`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "删除应用端失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    deletingAppId.value = null;
  }
}

function openIntegration(app: ProjectAppSummary) {
  if (!app.is_active) {
    ElMessage.warning("当前应用端已停用，请先启用后再查看接入说明。");
    return;
  }

  integrationDialogVisible.value = true;
  integrationApp.value = app;
}

async function generatePreview() {
  if (!projectId.value || !activeApp.value || previewLoading.value) {
    return;
  }
  if (!canPreviewActiveApp.value) {
    ElMessage.warning("请先启用应用端，并绑定知识库和助手后再生成沙盒测试。");
    return;
  }

  previewLoading.value = true;
  try {
    const response = await createProjectAppEmbedPreview(projectId.value, activeApp.value.id);
    previewEmbedUrl.value = response.embed_url;
    previewNeedsRefresh.value = false;
    ElMessage.success("已生成沙盒测试链接。");
  } catch (error) {
    const message = error instanceof Error ? error.message : "生成沙盒测试失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    previewLoading.value = false;
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

const embedSessionRequestCode = computed(() => {
  const selectedProject = project.value;
  const selectedApp = integrationApp.value ?? activeApp.value;
  const productCode = selectedProject?.product_code || "product_code";
  const projectCode = selectedProject?.code || "project_code";
  const appCode = selectedApp?.code || "app_code";

  return `POST https://你的LangChain RAG知识库域名/api/v1/embed/sessions
Authorization: Bearer <平台管理员提供的服务端接入 Token>
Content-Type: application/json

{
  "product_code": "${productCode}",
  "project_code": "${projectCode}",
  "app_code": "${appCode}",
  "external_user_id": "YOUR_USER_ID",
  "external_user_name": "张三"
}`;
});

const businessIframeCode = `<iframe
  src="{embed_url}"
  width="100%"
  height="720"
  frameborder="0"
  allow="microphone"
></iframe>`;

onMounted(() => {
  void loadPage();
});

watch(
  () => route.params.projectId,
  () => {
    activeAppId.value = null;
    previewEmbedUrl.value = "";
    previewNeedsRefresh.value = false;
    void loadPage();
  },
);
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
      <div class="project-app-workspace-page__header">
        <div class="project-app-workspace-page__title-row">
          <div>
            <h2>{{ project?.name || "项目应用端" }}</h2>
          </div>
          <el-button class="project-app-workspace-page__create-button" type="primary" @click="openCreateApp">
            <el-icon><Plus /></el-icon>
            新建应用端
          </el-button>
        </div>

        <div v-if="apps.length > 0" class="project-app-workspace-page__tabs">
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
            <button type="button" class="project-app-workspace-page__tab-main" @click="selectApp(app.id)">
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
        <el-button type="primary" @click="openCreateApp">新建应用端</el-button>
      </AppEmpty>

      <section v-else-if="activeApp" class="project-app-workspace-page__body">
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
                  <el-tag size="small" type="info" effect="plain">{{ activeApp.code }}</el-tag>
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

          <section class="project-app-workspace-page__access-card">
            <div class="project-app-workspace-page__access-header">
              <div>
                <h3>接入信息</h3>
                <p>用于业务系统识别并嵌入当前应用端。</p>
              </div>
              <el-button class="project-app-workspace-page__link-button" type="primary"  @click="openIntegration(activeApp)">
                <el-icon><Link /></el-icon>
                接入代码
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

        <section class="project-app-workspace-page__sandbox">
          <div class="project-app-workspace-page__sandbox-header">
            <div>
              <h3>沙盒测试</h3>
            </div>
            <el-button
              link
              class="project-app-workspace-page__refresh-button"
              :disabled="!canPreviewActiveApp"
              :loading="previewLoading"
              @click="generatePreview"
            >
              <el-icon><Refresh /></el-icon>
              {{ previewEmbedUrl || previewNeedsRefresh ? "刷新测试" : "生成测试" }}
            </el-button>
          </div>

          <div class="project-app-workspace-page__sandbox-body">
            <iframe
              v-if="hasFreshPreview"
              :src="previewEmbedUrl"
              title="沙盒测试"
              class="project-app-workspace-page__iframe"
            />
            <AppEmpty
              v-else-if="previewNeedsRefresh && canPreviewActiveApp"
              class="project-app-workspace-page__sandbox-empty"
              title="配置已更新"
              description="问答引擎配置已保存，刷新测试后将使用最新知识库、分类和助手。"
            >
              <div class="project-app-workspace-page__suggestions">
                <button type="button" @click="generatePreview">刷新测试会话</button>
              </div>
            </AppEmpty>
            <AppEmpty
              v-else-if="canPreviewActiveApp"
              class="project-app-workspace-page__sandbox-empty"
              :title="`我是 ${activeApp.default_assistant_name || '默认助手'}`"
              description="配置已就绪，可以生成测试会话。"
            >
              <div class="project-app-workspace-page__suggestions">
                <button type="button" @click="generatePreview">生成测试会话</button>
              </div>
            </AppEmpty>
            <AppEmpty
              v-else-if="activeApp.is_active"
              class="project-app-workspace-page__sandbox-empty"
              title="配置未完成"
              :description="previewUnavailableDescription"
            />
            <AppEmpty
              v-else
              class="project-app-workspace-page__sandbox-empty"
              title="应用端已停用"
              :description="previewUnavailableDescription"
            />
          </div>
        </section>
      </section>
    </AdminListPanel>

    <AdminDialog
      v-model="integrationDialogVisible"
      width="720px"
      :title="integrationApp ? `接入代码：${integrationApp.name}` : '接入代码'"
    >
      <div class="project-app-workspace-page__integration-summary">
        <div>
          <span>当前应用</span>
          <strong>{{ integrationApp?.name || "-" }}</strong>
        </div>
        <div>
          <span>终端类型</span>
          <strong>{{ integrationApp ? formatTerminalType(integrationApp.terminal_type) : "-" }}</strong>
        </div>
        <div>
          <span>应用编码</span>
          <strong>{{ integrationApp?.code || "-" }}</strong>
        </div>
      </div>

      <div class="project-app-workspace-page__integration-alert">
        服务端接入 Token 由平台管理员提供，只能保存在业务后端，不能写入浏览器、H5 或小程序前端代码。
      </div>

      <section class="project-app-workspace-page__integration-step">
        <div class="project-app-workspace-page__integration-step-header">
          <div>
            <span>步骤 1</span>
            <h3>业务后端创建嵌入会话</h3>
            <p>业务后端使用产品、项目和应用编码换取短期 embed_url。</p>
          </div>
          <el-button size="small" @click="copyText(embedSessionRequestCode, '服务端请求示例已复制。')">
            复制请求示例
          </el-button>
        </div>
        <div class="project-app-workspace-page__code-block">
          <pre>{{ embedSessionRequestCode }}</pre>
        </div>
      </section>

      <section class="project-app-workspace-page__integration-step">
        <div class="project-app-workspace-page__integration-step-header">
          <div>
            <span>步骤 2</span>
            <h3>业务前端嵌入助手</h3>
            <p>将上一步返回的 embed_url 填入 iframe，页面会使用短期凭证访问助手。</p>
          </div>
          <el-button size="small" @click="copyText(businessIframeCode, 'Iframe 示例已复制。')">
            复制 iframe 示例
          </el-button>
        </div>
        <div class="project-app-workspace-page__code-block">
          <pre>{{ businessIframeCode }}</pre>
        </div>
      </section>
    </AdminDialog>

    <AdminDialog
      v-model="appDialogVisible"
      :title="appDialogTitle"
      :loading="appDialogSaving"
      @closed="handleAppDialogClosed"
    >
      <el-form label-position="top" class="project-app-workspace-page__create-form">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="应用端名称" required>
              <el-input v-model="appForm.name" maxlength="100" placeholder="例如：Web H5 演示端" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="应用端编码" required>
              <el-input
                v-model="appForm.code"
                maxlength="120"
                placeholder="例如：demo_web_01"
                @blur="appForm.code = normalizeCode(appForm.code)"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="终端类型">
              <el-select v-model="appForm.terminal_type" class="project-app-workspace-page__create-full">
                <el-option
                  v-for="(label, value) in PROJECT_APP_TERMINAL_TYPE_LABELS"
                  :key="value"
                  :label="label"
                  :value="value"
                />
              </el-select>
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
        <el-button @click="appDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="appDialogSaving" @click="handleSaveAppBasicInfo">
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
.project-app-workspace-page__access-header,
.project-app-workspace-page__sandbox-header {
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
  display: grid;
  min-height: 0;
  grid-template-columns: minmax(420px, 460px) minmax(640px, 1fr);
  gap: 28px;
  padding: 32px 8px 0;
}

.project-app-workspace-page__inspector,
.project-app-workspace-page__sandbox {
  display: flex;
  min-height: 0;
  flex-direction: column;
}

.project-app-workspace-page__inspector {
  gap: 24px;
}

.project-app-workspace-page__status-card,
.project-app-workspace-page__config-card,
.project-app-workspace-page__access-card,
.project-app-workspace-page__sandbox {
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
.project-app-workspace-page__sandbox-header h3,
.project-app-workspace-page__dialog-title {
  margin: 0;
  color: #020617;
  font-size: 16px;
  font-weight: 800;
}

.project-app-workspace-page__app-identity p,
.project-app-workspace-page__config-header p,
.project-app-workspace-page__access-header p,
.project-app-workspace-page__sandbox-header p,
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
  margin: 0;
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

.project-app-workspace-page__sandbox {
  overflow: hidden;
}

.project-app-workspace-page__sandbox-header {
  justify-content: space-between;
  border-bottom: 1px solid #eef2f7;
  background: #ffffff;
  padding: 20px 22px;
}

.project-app-workspace-page__refresh-button {
  color: #94a3b8;
}

.project-app-workspace-page__sandbox-body {
  display: flex;
  flex: 1;
  min-height: clamp(620px, calc(100vh - 285px), 820px);
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
  border-radius: 16px;
}

.project-app-workspace-page__suggestions {
  display: grid;
  width: min(280px, 100%);
  gap: 10px;
  margin-top: 8px;
}

.project-app-workspace-page__suggestions button {
  width: 100%;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #ffffff;
  color: #475569;
  cursor: pointer;
  font-size: 13px;
  padding: 13px 16px;
  text-align: left;
}

.project-app-workspace-page__suggestions button:hover {
  border-color: var(--admin-primary-border);
  color: var(--admin-primary);
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

@media (max-width: 1180px) {
  .project-app-workspace-page__body {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .project-app-workspace-page__title-row,
  .project-app-workspace-page__status-card,
  .project-app-workspace-page__config-header,
  .project-app-workspace-page__sandbox-header {
    align-items: stretch;
    flex-direction: column;
  }

  .project-app-workspace-page__body {
    grid-template-columns: 1fr;
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
