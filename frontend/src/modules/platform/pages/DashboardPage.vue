<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  Collection,
  Connection,
  MagicStick,
  RefreshRight,
  Warning,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { listAssistants } from "@/shared/api/assistants";
import { listKnowledgeBases } from "@/shared/api/knowledge-bases";
import { listProjects } from "@/shared/api/projects";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import { useTeamScopeStore } from "@/stores/team-scope";
import type { AssistantSummary } from "@/shared/types/assistant";
import type { KnowledgeBaseListItem } from "@/shared/types/knowledge-base";
import type { ProjectSummary } from "@/shared/types/project";

const router = useRouter();
const teamScopeStore = useTeamScopeStore();

const loading = ref(false);
const loadError = ref<unknown>(null);
const hasLoadedData = ref(false);
const knowledgeBases = ref<KnowledgeBaseListItem[]>([]);
const knowledgeBaseTotal = ref(0);
const assistants = ref<AssistantSummary[]>([]);
const activeAssistantTotal = ref(0);
const inactiveAssistantTotal = ref(0);
const projects = ref<ProjectSummary[]>([]);
const projectTotal = ref(0);

const projectAppTotal = computed(() =>
  projects.value.reduce((total, item) => total + item.app_count, 0),
);
const pendingDocumentTotal = computed(() =>
  knowledgeBases.value.reduce(
    (total, item) =>
      total +
      item.queued_document_count +
      item.processing_document_count +
      item.pending_review_document_count,
    0,
  ),
);
const failedDocumentTotal = computed(() =>
  knowledgeBases.value.reduce((total, item) => total + item.failed_document_count, 0),
);
const recentKnowledgeBases = computed(() =>
  [...knowledgeBases.value]
    .sort((a, b) => getTimestamp(b.last_document_updated_at ?? b.updated_at) - getTimestamp(a.last_document_updated_at ?? a.updated_at))
    .slice(0, 5),
);
const recentProjects = computed(() =>
  [...projects.value]
    .sort((a, b) => getTimestamp(b.updated_at) - getTimestamp(a.updated_at))
    .slice(0, 5),
);

function getTimestamp(value: string | null) {
  if (!value) {
    return 0;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "暂无更新";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

async function loadDashboard() {
  if (loading.value) {
    return;
  }

  loading.value = true;
  loadError.value = null;

  try {
    const teamId = teamScopeStore.selectedTeamId ?? undefined;
    const [
      knowledgeBaseResult,
      assistantResult,
      activeAssistantResult,
      inactiveAssistantResult,
      projectResult,
    ] = await Promise.all([
      listKnowledgeBases({ team_id: teamId, page: 1, page_size: 100 }),
      listAssistants({ team_id: teamId, status: "all", page: 1, page_size: 5 }),
      listAssistants({ team_id: teamId, status: "active", page: 1, page_size: 1 }),
      listAssistants({ team_id: teamId, status: "inactive", page: 1, page_size: 1 }),
      listProjects({ team_id: teamId, page: 1, page_size: 100 }),
    ]);

    knowledgeBases.value = knowledgeBaseResult.items;
    knowledgeBaseTotal.value = knowledgeBaseResult.total;
    assistants.value = assistantResult.items;
    activeAssistantTotal.value = activeAssistantResult.total;
    inactiveAssistantTotal.value = inactiveAssistantResult.total;
    projects.value = projectResult.items;
    projectTotal.value = projectResult.total;
    hasLoadedData.value = true;
  } catch (error) {
    if (hasLoadedData.value) {
      ElMessage.error(error instanceof Error ? error.message : "控制台刷新失败，请稍后重试。");
    } else {
      loadError.value = error;
    }
  } finally {
    loading.value = false;
  }
}

function openKnowledgeBase(knowledgeBaseId: number) {
  void router.push(`/knowledge-bases/${knowledgeBaseId}`);
}

function openProjectApps(projectId: number) {
  void router.push(`/projects/${projectId}/apps`);
}

function openAssistant(assistantId: number) {
  void router.push(`/assistants/${assistantId}`);
}

onMounted(() => {
  void loadDashboard();
});

watch(
  () => teamScopeStore.selectedTeamId,
  () => {
    void loadDashboard();
  },
);
</script>

<template>
  <section class="dashboard-page">
    <AppLoading
      v-if="loading && !hasLoadedData"
      title="控制台加载中"
      description="正在汇总当前团队的知识库、助手和发布入口。"
      :blocks="4"
    />

    <AppError
      v-else-if="loadError && !hasLoadedData"
      title="控制台加载失败"
      description="暂时无法获取控制台数据，请稍后重试。"
      :error="loadError"
      @retry="loadDashboard"
    />

    <template v-else>
      <div class="dashboard-page__actions">
        <el-button
          :loading="loading"
          @click="loadDashboard"
        >
          <el-icon><RefreshRight /></el-icon>
          刷新
        </el-button>
      </div>

      <section
        v-loading="loading"
        class="dashboard-page__metrics"
        element-loading-text="正在更新控制台"
      >
        <article class="dashboard-metric">
          <span class="dashboard-metric__label">待处理文档</span>
          <strong>{{ pendingDocumentTotal }}</strong>
          <span>失败 {{ failedDocumentTotal }}</span>
        </article>
        <article class="dashboard-metric">
          <span class="dashboard-metric__label">知识库</span>
          <strong>{{ knowledgeBaseTotal }}</strong>
          <span>按当前团队范围统计</span>
        </article>
        <article class="dashboard-metric">
          <span class="dashboard-metric__label">助手状态</span>
          <strong>{{ activeAssistantTotal }}</strong>
          <span>启用 {{ activeAssistantTotal }} / 停用 {{ inactiveAssistantTotal }}</span>
        </article>
        <article class="dashboard-metric">
          <span class="dashboard-metric__label">接入应用</span>
          <strong>{{ projectAppTotal }}</strong>
          <span>{{ projectTotal }} 个项目下的发布渠道</span>
        </article>
      </section>

      <section class="dashboard-page__grid">
        <article class="dashboard-panel">
          <div class="dashboard-panel__header">
            <div>
              <h2>待处理知识库</h2>
              <p>优先查看索引中、待审核和失败文档。</p>
            </div>
            <el-button
              link
              type="primary"
              @click="router.push('/knowledge-bases')"
            >
              查看全部
            </el-button>
          </div>

          <div
            v-if="recentKnowledgeBases.length === 0"
            class="dashboard-panel__empty"
          >
            当前团队暂无知识库。
          </div>
          <template v-else>
            <button
              v-for="item in recentKnowledgeBases"
              :key="item.id"
              type="button"
              class="dashboard-list-row"
              @click="openKnowledgeBase(item.id)"
            >
              <el-icon><Collection /></el-icon>
              <span class="dashboard-list-row__main">
                <strong>{{ item.name }}</strong>
                <span>
                  待处理 {{ item.queued_document_count + item.processing_document_count + item.pending_review_document_count }}
                  · 已发布 {{ item.published_document_count }}
                </span>
              </span>
              <span class="dashboard-list-row__time">
                {{ formatDateTime(item.last_document_updated_at ?? item.updated_at) }}
              </span>
            </button>
          </template>
        </article>

        <article class="dashboard-panel">
          <div class="dashboard-panel__header">
            <div>
              <h2>助手状态</h2>
              <p>检查当前团队可用助手和最近配置。</p>
            </div>
            <el-button
              link
              type="primary"
              @click="router.push('/assistants')"
            >
              管理助手
            </el-button>
          </div>

          <div
            v-if="assistants.length === 0"
            class="dashboard-panel__empty"
          >
            当前团队暂无助手。
          </div>
          <template v-else>
            <button
              v-for="item in assistants"
              :key="item.id"
              type="button"
              class="dashboard-list-row"
              @click="openAssistant(item.id)"
            >
              <el-icon><MagicStick /></el-icon>
              <span class="dashboard-list-row__main">
                <strong>{{ item.name }}</strong>
                <span>{{ item.llm_model_key || "未指定模型" }}</span>
              </span>
              <el-tag
                :type="item.is_active ? 'success' : 'info'"
                effect="plain"
              >
                {{ item.is_active ? "启用" : "停用" }}
              </el-tag>
            </button>
          </template>
        </article>

        <article class="dashboard-panel dashboard-panel--wide">
          <div class="dashboard-panel__header">
            <div>
              <h2>接入应用</h2>
              <p>进入项目发布渠道，检查嵌入入口、默认助手和绑定知识库。</p>
            </div>
            <el-button
              link
              type="primary"
              @click="router.push('/projects')"
            >
              管理项目
            </el-button>
          </div>

          <div
            v-if="recentProjects.length === 0"
            class="dashboard-panel__empty"
          >
            当前团队暂无项目。
          </div>
          <template v-else>
            <button
              v-for="item in recentProjects"
              :key="item.id"
              type="button"
              class="dashboard-list-row"
              @click="openProjectApps(item.id)"
            >
              <el-icon><Connection /></el-icon>
              <span class="dashboard-list-row__main">
                <strong>{{ item.name }}</strong>
                <span>{{ item.product_name || "未设置产品" }} · {{ item.code }}</span>
              </span>
              <span class="dashboard-list-row__badge">{{ item.app_count }} 个发布渠道</span>
            </button>
          </template>
        </article>

        <article class="dashboard-panel">
          <div class="dashboard-panel__header">
            <div>
              <h2>处理提醒</h2>
              <p>根据当前知识库状态生成的入口提示。</p>
            </div>
          </div>

          <div class="dashboard-alert">
            <el-icon><Warning /></el-icon>
            <span>
              当前有 {{ pendingDocumentTotal }} 个文档等待索引或审核，{{ failedDocumentTotal }} 个文档索引失败。
            </span>
          </div>
        </article>
      </section>
    </template>
  </section>
</template>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dashboard-page__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
}

.dashboard-page__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.dashboard-metric,
.dashboard-panel {
  border: 1px solid var(--admin-border);
  border-radius: var(--admin-radius-lg);
  background: var(--admin-surface);
  box-shadow: var(--admin-shadow-panel);
}

.dashboard-metric {
  display: flex;
  min-height: 112px;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  padding: 16px;
}

.dashboard-metric__label,
.dashboard-metric span {
  color: var(--admin-text-muted);
  font-size: 13px;
}

.dashboard-metric strong {
  color: var(--admin-text);
  font-size: 30px;
  line-height: 1;
}

.dashboard-page__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.dashboard-panel {
  overflow: hidden;
}

.dashboard-panel--wide {
  grid-column: span 1;
}

.dashboard-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--admin-border-soft);
  background: var(--admin-surface-muted);
  padding: 14px 16px;
}

.dashboard-panel__header h2 {
  margin: 0 0 4px;
  color: var(--admin-text);
  font-size: 15px;
  font-weight: 700;
}

.dashboard-panel__header p {
  margin: 0;
  color: var(--admin-text-muted);
  font-size: 13px;
}

.dashboard-list-row {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 12px;
  border: 0;
  border-bottom: 1px solid var(--admin-border-soft);
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 12px 16px;
  text-align: left;
}

.dashboard-list-row:hover {
  background: var(--admin-surface-muted);
}

.dashboard-list-row:last-child {
  border-bottom: 0;
}

.dashboard-list-row .el-icon {
  color: var(--admin-primary);
}

.dashboard-list-row__main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 3px;
}

.dashboard-list-row__main strong {
  overflow: hidden;
  color: var(--admin-text);
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dashboard-list-row__main span,
.dashboard-list-row__time,
.dashboard-list-row__badge {
  color: var(--admin-text-muted);
  font-size: 12px;
}

.dashboard-list-row__badge {
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-sm);
  background: var(--admin-surface-muted);
  padding: 4px 8px;
  white-space: nowrap;
}

.dashboard-panel__empty {
  color: var(--admin-text-muted);
  font-size: 13px;
  padding: 24px 16px;
}

.dashboard-alert {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  color: var(--admin-text-secondary);
  font-size: 13px;
  line-height: 1.6;
  padding: 16px;
}

.dashboard-alert .el-icon {
  margin-top: 3px;
  color: var(--admin-warning);
}

@media (max-width: 1180px) {
  .dashboard-page__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .dashboard-page__actions,
  .dashboard-panel__header {
    flex-direction: column;
    align-items: stretch;
  }

  .dashboard-page__grid,
  .dashboard-page__metrics {
    grid-template-columns: 1fr;
  }
}
</style>
