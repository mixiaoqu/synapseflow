<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Delete, EditPen, Link, Plus, Search } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
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
import type { ProjectAppSummary, ProjectAppUpsertPayload, ProjectSummary } from "@/shared/types/project";

type StatusFilter = "all" | "active" | "inactive";

const route = useRoute();
const router = useRouter();

const project = ref<ProjectSummary | null>(null);
const apps = ref<ProjectAppSummary[]>([]);
const loading = ref(false);
const loadError = ref<unknown>(null);
const searchKeyword = ref("");
const statusFilter = ref<StatusFilter>("all");
const statusLoadingId = ref<number | null>(null);
const deletingAppId = ref<number | null>(null);

const integrationDialogVisible = ref(false);
const integrationLoading = ref(false);
const integrationApp = ref<ProjectAppSummary | null>(null);
const integrationEmbedUrl = ref("");
const integrationExpiresInSeconds = ref<number | null>(null);

const projectId = computed(() => {
  const raw = Number(route.params.projectId);
  return Number.isInteger(raw) && raw > 0 ? raw : null;
});

const displayedApps = computed(() => {
  const normalizedKeyword = searchKeyword.value.trim().toLowerCase();

  return apps.value.filter((item) => {
    const matchesKeyword =
      normalizedKeyword.length === 0 ||
      [item.name, item.code, item.description ?? "", item.default_assistant_name ?? ""].some((value) =>
        value.toLowerCase().includes(normalizedKeyword),
      );
    const matchesStatus =
      statusFilter.value === "all" ||
      (statusFilter.value === "active" ? item.is_active : !item.is_active);
    return matchesKeyword && matchesStatus;
  });
});

const isForbidden = computed(() => Boolean(loadError.value) && isForbiddenError(loadError.value));

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

function buildUpdatePayload(app: ProjectAppSummary, isActive: boolean): ProjectAppUpsertPayload {
  return {
    code: app.code,
    name: app.name,
    description: app.description,
    default_assistant_id: app.default_assistant_id,
    bindings: app.bindings.map((item) => ({
      knowledge_base_id: item.knowledge_base_id,
    })),
    is_active: isActive,
  };
}

async function loadPage() {
  if (!projectId.value || loading.value) {
    return;
  }

  loading.value = true;
  loadError.value = null;

  try {
    const [projectResponse, appResponses] = await Promise.all([
      getProject(projectId.value),
      listProjectApps(projectId.value),
    ]);
    project.value = projectResponse;
    apps.value = appResponses;
  } catch (error) {
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

function handleBack() {
  void router.push("/projects");
}

function openCreateApp() {
  if (!projectId.value) {
    return;
  }

  void router.push(`/projects/${projectId.value}/apps/new`);
}

function openAppDetail(appId: number) {
  if (!projectId.value) {
    return;
  }

  void router.push(`/projects/${projectId.value}/apps/${appId}`);
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
      buildUpdatePayload(app, Boolean(nextValue)),
    );
    const index = apps.value.findIndex((item) => item.id === app.id);
    if (index >= 0) {
      apps.value[index] = updated;
    }
    ElMessage.success(`已${updated.is_active ? "启用" : "停用"}发布渠道“${updated.name}”。`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "更新发布渠道状态失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    statusLoadingId.value = null;
  }
}

async function handleDeleteApp(app: ProjectAppSummary) {
  if (!projectId.value || deletingAppId.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定删除发布渠道“${app.name}”吗？删除后该嵌入入口将立即失效。`,
      "删除发布渠道",
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
    ElMessage.success(`已删除发布渠道“${app.name}”。`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "删除发布渠道失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    deletingAppId.value = null;
  }
}

async function openIntegration(app: ProjectAppSummary) {
  if (!projectId.value) {
    return;
  }

  if (!app.is_active) {
    ElMessage.warning("当前发布渠道已停用，请先启用后再生成嵌入预览链接。");
    return;
  }

  integrationDialogVisible.value = true;
  integrationLoading.value = true;
  integrationApp.value = app;
  integrationEmbedUrl.value = "";
  integrationExpiresInSeconds.value = null;

  try {
    const response = await createProjectAppEmbedPreview(projectId.value, app.id);
    integrationEmbedUrl.value = response.embed_url;
    integrationExpiresInSeconds.value = response.expires_in_seconds;
  } catch (error) {
    integrationDialogVisible.value = false;
    const message = error instanceof Error ? error.message : "生成嵌入预览链接失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    integrationLoading.value = false;
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

const iframeCode = computed(() => {
  if (!integrationEmbedUrl.value) {
    return "";
  }

  return `<iframe
  src="${integrationEmbedUrl.value}"
  width="100%"
  height="720"
  frameborder="0"
  allow="microphone"
></iframe>`;
});

onMounted(() => {
  void loadPage();
});

watch(
  () => route.params.projectId,
  () => {
    void loadPage();
  },
);
</script>

<template>
  <section class="project-app-list-page">
    <header class="project-app-list-page__header">
      <div class="project-app-list-page__header-left">
        <button type="button" class="project-app-list-page__back" @click="handleBack">
          返回项目列表
        </button>
        <div class="project-app-list-page__divider" />
        <div v-if="project" class="project-app-list-page__title-group">
          <h1 class="project-app-list-page__title">{{ project.name }}</h1>
          <span class="project-app-list-page__meta">应用与发布</span>
          <span class="project-app-list-page__meta">产品：{{ project.product_name || "未设置" }}</span>
        </div>
      </div>

      <el-button type="primary" @click="openCreateApp">
        <el-icon class="mr-2"><Plus /></el-icon>
        新建发布渠道
      </el-button>
    </header>

    <section v-if="!loading && !loadError" class="project-app-list-page__toolbar">
      <el-input
        v-model="searchKeyword"
        size="large"
        clearable
        placeholder="搜索应用名称、编码、说明或绑定助手..."
        class="project-app-list-page__search"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-select v-model="statusFilter" size="large" class="project-app-list-page__status">
        <el-option label="全部状态" value="all" />
        <el-option label="已启用" value="active" />
        <el-option label="已停用" value="inactive" />
      </el-select>
    </section>

    <AppLoading
      v-if="loading"
      title="发布渠道加载中"
      description="正在获取当前项目下的应用与发布配置，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="loadError && !isForbidden"
      title="发布渠道加载失败"
      description="暂时无法获取当前项目的发布渠道，请稍后重试。"
      :error="loadError"
      @retry="loadPage"
    />

    <AppError
      v-else-if="isForbidden"
      title="无权查看发布渠道"
      description="当前账号没有访问该项目应用与发布配置的权限。"
      :error="loadError"
      :show-retry="false"
    />

    <AppEmpty
      v-else-if="displayedApps.length === 0"
      title="当前项目暂无发布渠道"
      description="可以先创建一个发布渠道，再绑定助手和知识库。"
    >
      <el-button type="primary" @click="openCreateApp">新建发布渠道</el-button>
    </AppEmpty>

    <section v-else class="project-app-list-page__table-panel">
      <el-table :data="displayedApps" row-key="id" class="project-app-list-page__table">
        <el-table-column label="应用名称" min-width="260">
          <template #default="{ row }">
            <div class="project-app-list-page__name-cell">
              <strong>{{ row.name }}</strong>
              <span>{{ row.description?.trim() || "暂无说明" }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="应用编码" min-width="180">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="绑定配置" min-width="240">
          <template #default="{ row }">
            <div class="project-app-list-page__binding-cell">
              <el-tag size="small" type="primary" effect="light">
                助手：{{ row.default_assistant_name || "未绑定" }}
              </el-tag>
              <el-tag size="small" type="info" effect="light">
                知识库：{{ row.bindings.length }} 个
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="180">
          <template #default="{ row }">
            <span>{{ formatDateTime(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              :loading="statusLoadingId === row.id"
              @change="(value) => handleToggleStatus(row, value)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openAppDetail(row.id)">
              <el-icon><EditPen /></el-icon>
              <span>编排配置</span>
            </el-button>
            <el-button link type="success" @click="openIntegration(row)">
              <el-icon><Link /></el-icon>
              <span>接入集成</span>
            </el-button>
            <el-button
              link
              type="danger"
              :loading="deletingAppId === row.id"
              @click="handleDeleteApp(row)"
            >
              <el-icon><Delete /></el-icon>
              <span>删除</span>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog
      v-model="integrationDialogVisible"
      width="720px"
      :title="integrationApp ? `接入集成：${integrationApp.name}` : '接入集成'"
      destroy-on-close
    >
      <AppLoading
        v-if="integrationLoading"
        title="生成预览链接中"
        description="正在为当前发布渠道生成嵌入预览地址，请稍候。"
        :blocks="3"
      />

      <template v-else>
        <p class="project-app-list-page__integration-hint">
          当前后端已支持嵌入预览链接，可直接用于 iframe 内嵌或独立页面访问。
        </p>

        <div class="project-app-list-page__integration-meta">
          <span>有效期：{{ integrationExpiresInSeconds ? `${integrationExpiresInSeconds} 秒` : "-" }}</span>
        </div>

        <div class="project-app-list-page__code-block">
          <button
            type="button"
            class="project-app-list-page__copy-button"
            @click="copyText(integrationEmbedUrl, '预览链接已复制。')"
          >
            复制链接
          </button>
          <pre>{{ integrationEmbedUrl }}</pre>
        </div>

        <h3 class="project-app-list-page__dialog-title">Iframe 嵌入示例</h3>
        <div class="project-app-list-page__code-block">
          <button
            type="button"
            class="project-app-list-page__copy-button"
            @click="copyText(iframeCode, 'Iframe 代码已复制。')"
          >
            复制代码
          </button>
          <pre>{{ iframeCode }}</pre>
        </div>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.project-app-list-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.project-app-list-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 56px;
  border: 1px solid #dbe2ea;
  border-radius: 12px;
  background: #ffffff;
  padding: 0 16px;
}

.project-app-list-page__header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.project-app-list-page__back {
  border: 0;
  background: transparent;
  color: #475569;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  padding: 0;
}

.project-app-list-page__back:hover {
  color: #2563eb;
}

.project-app-list-page__divider {
  width: 1px;
  height: 20px;
  background: #e2e8f0;
}

.project-app-list-page__title-group {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.project-app-list-page__title {
  margin: 0;
  color: #0f172a;
  font-size: 16px;
  font-weight: 600;
}

.project-app-list-page__meta {
  color: #64748b;
  font-size: 13px;
  white-space: nowrap;
}

.project-app-list-page__toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid #dbe2ea;
  border-radius: 12px;
  background: #ffffff;
  padding: 14px 16px;
}

.project-app-list-page__search {
  width: 380px;
  max-width: 100%;
}

.project-app-list-page__status {
  width: 132px;
}

.project-app-list-page__table-panel {
  border: 1px solid #dbe2ea;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
  padding: 8px 8px 2px;
}

.project-app-list-page__name-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.project-app-list-page__name-cell strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-app-list-page__name-cell span {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.project-app-list-page__binding-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.project-app-list-page__integration-hint {
  margin: 0 0 12px;
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

.project-app-list-page__integration-meta {
  margin-bottom: 12px;
  color: #64748b;
  font-size: 12px;
}

.project-app-list-page__dialog-title {
  margin: 18px 0 12px;
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
}

.project-app-list-page__code-block {
  position: relative;
  overflow: auto;
  border-radius: 12px;
  background: #0f172a;
  color: #e2e8f0;
  padding: 18px;
}

.project-app-list-page__code-block pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.project-app-list-page__copy-button {
  position: absolute;
  top: 12px;
  right: 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
  cursor: pointer;
  font-size: 12px;
  padding: 6px 10px;
}

@media (max-width: 960px) {
  .project-app-list-page__header,
  .project-app-list-page__toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .project-app-list-page__search,
  .project-app-list-page__status {
    width: 100%;
  }
}
</style>
