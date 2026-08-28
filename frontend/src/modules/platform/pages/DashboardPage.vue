<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  Connection,
  CircleClose,
  Clock,
  Document,
  MagicStick,
  RefreshRight,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import AdminPageHeader from "@/app/components/admin/AdminPageHeader.vue";
import AdminStatusTag from "@/app/components/admin/AdminStatusTag.vue";
import { listEvalRuns } from "@/shared/api/evaluations";
import type { EvalRunListItem } from "@/modules/evaluations/types";
import { listQaLogs } from "@/modules/qa-logs/api";
import type { QaLogSummary } from "@/modules/qa-logs/types";
import { listAssistants } from "@/shared/api/assistants";
import { listKnowledgeBases } from "@/shared/api/knowledge-bases";
import { listProjects } from "@/shared/api/projects";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import type { KnowledgeBaseListItem } from "@/shared/types/knowledge-base";
import type { ProjectSummary } from "@/shared/types/project";
import { useTeamScopeStore } from "@/stores/team-scope";

const router = useRouter();
const teamScopeStore = useTeamScopeStore();

const loading = ref(false);
const loadError = ref<unknown>(null);
const hasLoadedData = ref(false);
const evaluationUnavailable = ref(false);
const knowledgeBases = ref<KnowledgeBaseListItem[]>([]);
const projects = ref<ProjectSummary[]>([]);
const qaLogs = ref<QaLogSummary[]>([]);
const evaluationRuns = ref<EvalRunListItem[]>([]);
const knowledgeBaseTotal = ref(0);
const qaTotal = ref(0);
const evaluationTotal = ref(0);
const activeAssistantTotal = ref(0);
const inactiveAssistantTotal = ref(0);

const indexedDocumentTotal = computed(() =>
  knowledgeBases.value.reduce((total, item) => total + item.indexed_document_count, 0),
);
const pendingDocumentTotal = computed(() =>
  knowledgeBases.value.reduce(
    (total, item) => total + item.queued_document_count + item.processing_document_count + item.pending_review_document_count,
    0,
  ),
);
const failedDocumentTotal = computed(() =>
  knowledgeBases.value.reduce((total, item) => total + item.failed_document_count, 0),
);
const projectAppTotal = computed(() =>
  projects.value.reduce((total, item) => total + item.app_count, 0),
);
const failedQaTotal = computed(() =>
  qaLogs.value.filter((item) => item.answerStatus === "blocked" || item.answerStatus === "insufficient").length,
);
const delayedQaTotal = computed(() =>
  qaLogs.value.filter((item) => (item.latencyMs ?? 0) >= 3000).length,
);
const evaluationPendingTotal = computed(() =>
  evaluationRuns.value.filter((item) => item.status === "pending" || item.status === "running").length,
);
const evaluationFailedTotal = computed(() =>
  evaluationRuns.value.filter((item) => item.status === "failed").length,
);
const knowledgeStatus = computed(() => (failedDocumentTotal.value > 0 ? "failed" : pendingDocumentTotal.value > 0 ? "pending" : "ok"));
const answerSummaryStatus = computed(() => (failedQaTotal.value > 0 ? "failed" : delayedQaTotal.value > 0 ? "pending" : "ok"));
const evaluationStatus = computed(() => {
  if (evaluationUnavailable.value) return "info";
  if (evaluationFailedTotal.value > 0) return "failed";
  if (evaluationPendingTotal.value > 0) return "pending";
  return evaluationTotal.value > 0 ? "ok" : "pending";
});

const attentionItems = computed(() => [
  {
    key: "knowledge",
    icon: Document,
    title: pendingDocumentTotal.value > 0 ? "文档索引积压" : "知识库运行正常",
    scope: "知识库",
    status: knowledgeStatus.value,
    statusLabel: knowledgeStatus.value === "failed" ? "异常" : pendingDocumentTotal.value > 0 ? "处理中" : "正常",
    reason: pendingDocumentTotal.value > 0
      ? `${pendingDocumentTotal.value} 个文档等待索引或审核`
      : `已索引文档 ${indexedDocumentTotal.value} 个`,
    actionLabel: pendingDocumentTotal.value > 0 ? "去处理" : "查看知识库",
    route: "/knowledge-bases",
  },
  {
    key: "qa",
    icon: CircleClose,
    title: failedQaTotal.value > 0 ? "失败或不足回答" : "回答运行正常",
    scope: "回答",
    status: answerSummaryStatus.value,
    statusLabel: failedQaTotal.value > 0 ? "需关注" : delayedQaTotal.value > 0 ? "响应较慢" : "正常",
    reason: failedQaTotal.value > 0
      ? `最近 ${qaLogs.value.length} 条请求中有 ${failedQaTotal.value} 条未正常回答`
      : delayedQaTotal.value > 0
        ? `最近 ${qaLogs.value.length} 条请求中有 ${delayedQaTotal.value} 条响应较慢`
        : "最近请求均已正常完成",
    actionLabel: "查看问答日志",
    route: "/qa-logs",
  },
  {
    key: "evaluation",
    icon: Connection,
    title: evaluationUnavailable.value ? "评测数据暂不可用" : evaluationPendingTotal.value > 0 ? "评测运行待处理" : "评测状态正常",
    scope: "评测集",
    status: evaluationStatus.value,
    statusLabel: evaluationUnavailable.value ? "暂无数据" : evaluationFailedTotal.value > 0 ? "有失败" : evaluationPendingTotal.value > 0 ? "待处理" : "正常",
    reason: evaluationUnavailable.value
      ? "当前账号暂时无法读取评测运行记录"
      : evaluationPendingTotal.value > 0
        ? `${evaluationPendingTotal.value} 个评测任务等待处理`
        : evaluationFailedTotal.value > 0
          ? `${evaluationFailedTotal.value} 个评测任务运行失败`
          : `已记录 ${evaluationTotal.value} 个评测任务`,
    actionLabel: "查看评测集",
    route: "/evaluations",
  },
  {
    key: "assistant",
    icon: MagicStick,
    title: inactiveAssistantTotal.value > 0 ? "有停用助手" : "助手运行正常",
    scope: "助手",
    status: inactiveAssistantTotal.value > 0 ? "pending" : activeAssistantTotal.value > 0 ? "ok" : "pending",
    statusLabel: inactiveAssistantTotal.value > 0 ? "需关注" : activeAssistantTotal.value > 0 ? "正常" : "待配置",
    reason: inactiveAssistantTotal.value > 0
      ? `${inactiveAssistantTotal.value} 个助手当前已停用`
      : `运行中 ${activeAssistantTotal.value} 个助手，应用端 ${projectAppTotal.value} 个`,
    actionLabel: "查看助手",
    route: "/assistants",
  },
]);

const recentRunItems = computed(() => {
  const qaItems = qaLogs.value.map((item) => ({
    id: `qa-${item.id}`,
    icon: MagicStick,
    title: `用户咨询：${item.query}`,
    subtitle: `应用：${item.projectAppName || "未标记应用"}`,
    status: answerStatus(item.answerStatus),
    statusLabel: answerStatusLabel(item.answerStatus),
    createdAt: item.createdAt,
    route: "/qa-logs",
  }));
  const evaluationItems = evaluationRuns.value.map((item) => ({
    id: `evaluation-${item.id}`,
    icon: Connection,
    title: `评测运行：${item.dataset_name}`,
    subtitle: `评测集版本：${item.dataset_version}`,
    status: item.status === "completed" ? "ok" : item.status === "canceled" ? "info" : item.status,
    statusLabel: evaluationRunStatusLabel(item.status),
    createdAt: item.created_at,
    route: "/evaluations/reports",
  }));

  return [...qaItems, ...evaluationItems]
    .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())
    .slice(0, 8);
});

function formatDateTime(value: string | null) {
  if (!value) return "暂无时间";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}

function answerStatus(status: string) {
  if (status === "answered") return "success";
  if (status === "partial") return "warning";
  if (status === "blocked" || status === "insufficient") return "failed";
  return "info";
}

function answerStatusLabel(status: string) {
  if (status === "answered") return "正常";
  if (status === "partial") return "部分回答";
  if (status === "blocked" || status === "insufficient") return "失败";
  return status || "未知";
}

function evaluationRunStatusLabel(status: string) {
  if (status === "pending") return "待运行";
  if (status === "running") return "运行中";
  if (status === "completed") return "已完成";
  if (status === "failed") return "失败";
  if (status === "canceled") return "已取消";
  return status || "未知";
}

async function loadDashboard() {
  if (loading.value) return;
  loading.value = true;
  loadError.value = null;

  try {
    const teamId = teamScopeStore.selectedTeamId ?? undefined;
    const [knowledgeBaseResult, activeResult, inactiveResult, projectResult, qaResult] = await Promise.all([
      listKnowledgeBases({ team_id: teamId, page: 1, page_size: 100 }),
      listAssistants({ team_id: teamId, status: "active", page: 1, page_size: 1 }),
      listAssistants({ team_id: teamId, status: "inactive", page: 1, page_size: 1 }),
      listProjects({ team_id: teamId, page: 1, page_size: 100 }),
      listQaLogs({ team_id: teamId, page: 1, page_size: 7 }),
    ]);

    knowledgeBases.value = knowledgeBaseResult.items;
    knowledgeBaseTotal.value = knowledgeBaseResult.total;
    activeAssistantTotal.value = activeResult.total;
    inactiveAssistantTotal.value = inactiveResult.total;
    projects.value = projectResult.items;
    qaLogs.value = qaResult.items;
    qaTotal.value = qaResult.total;

    const evaluationResult = await listEvalRuns({ page: 1, page_size: 100 }).catch(() => null);
    evaluationUnavailable.value = evaluationResult === null;
    evaluationRuns.value = evaluationResult?.items ?? [];
    evaluationTotal.value = evaluationResult?.total ?? 0;
    hasLoadedData.value = true;
  } catch (error) {
    if (hasLoadedData.value) {
      ElMessage.error(error instanceof Error ? error.message : "刷新工作台失败，请稍后重试。");
    } else {
      loadError.value = error;
    }
  } finally {
    loading.value = false;
  }
}

function openRoute(route: string) {
  void router.push(route);
}

onMounted(() => void loadDashboard());
watch(() => teamScopeStore.selectedTeamId, () => void loadDashboard());
</script>

<template>
  <section class="dashboard-page">
    <AdminPageHeader title="工作台" description="Agent 运行与系统健康概览。">
      <template #actions>
        <span class="dashboard-updated">最后更新：{{ formatDateTime(qaLogs[0]?.createdAt ?? null) }}</span>
        <el-button :loading="loading" @click="loadDashboard">
          <el-icon><RefreshRight /></el-icon>
          刷新
        </el-button>
      </template>
    </AdminPageHeader>

    <AppLoading v-if="loading && !hasLoadedData" title="工作台加载中" description="正在汇总团队运行数据。" :blocks="3" />
    <AppError v-else-if="loadError && !hasLoadedData" title="工作台加载失败" description="暂时无法获取工作台数据，请稍后重试。" :error="loadError" @retry="loadDashboard" />

    <template v-else>
      <section class="dashboard-health" v-loading="loading">
        <article class="dashboard-health__item">
          <span class="dashboard-health__icon dashboard-health__icon--green"><Document /></span>
          <div class="dashboard-health__content">
            <div class="dashboard-health__title"><strong>知识库状态</strong><AdminStatusTag :status="knowledgeStatus" /></div>
            <div class="dashboard-health__stats"><span>知识库总数 <b>{{ knowledgeBaseTotal }}</b></span><span>待处理 <b>{{ pendingDocumentTotal }}</b></span></div>
            <el-button link type="primary" @click="openRoute('/knowledge-bases')">查看知识库</el-button>
          </div>
        </article>
        <article class="dashboard-health__item">
          <span class="dashboard-health__icon dashboard-health__icon--blue"><MagicStick /></span>
          <div class="dashboard-health__content">
            <div class="dashboard-health__title"><strong>回答状态</strong><AdminStatusTag :status="answerSummaryStatus" :label="failedQaTotal > 0 ? '需关注' : delayedQaTotal > 0 ? '响应较慢' : '正常'" /></div>
            <div class="dashboard-health__stats"><span>累计问答 <b>{{ qaTotal }}</b></span><span>最近异常 <b>{{ failedQaTotal }}</b></span></div>
            <el-button link type="primary" @click="openRoute('/qa-logs')">查看问答日志</el-button>
          </div>
        </article>
        <article class="dashboard-health__item">
          <span class="dashboard-health__icon dashboard-health__icon--purple"><Connection /></span>
          <div class="dashboard-health__content">
            <div class="dashboard-health__title"><strong>评测状态</strong><AdminStatusTag :status="evaluationStatus" :label="evaluationUnavailable ? '暂无数据' : undefined" /></div>
            <div class="dashboard-health__stats"><span>评测任务 <b>{{ evaluationTotal }}</b></span><span>待处理 <b>{{ evaluationPendingTotal }}</b></span></div>
            <el-button link type="primary" @click="openRoute('/evaluations')">查看评测集</el-button>
          </div>
        </article>
        <article class="dashboard-health__item">
          <span class="dashboard-health__icon dashboard-health__icon--indigo"><MagicStick /></span>
          <div class="dashboard-health__content">
            <div class="dashboard-health__title"><strong>助手与应用</strong><AdminStatusTag :status="activeAssistantTotal > 0 ? 'ok' : 'pending'" /></div>
            <div class="dashboard-health__stats"><span>运行中 <b>{{ activeAssistantTotal }}</b></span><span>应用端 <b>{{ projectAppTotal }}</b></span></div>
            <el-button link type="primary" @click="openRoute('/assistants')">管理助手</el-button>
          </div>
        </article>
      </section>

      <section class="dashboard-main-grid">
        <article class="dashboard-panel">
          <header class="dashboard-panel__header">
            <div><span class="dashboard-panel__eyebrow">ATTENTION</span><h2>需要关注</h2></div>
            <el-button link type="primary" @click="openRoute('/qa-logs')">查看全部</el-button>
          </header>
          <div class="dashboard-attention-list">
            <button v-for="item in attentionItems" :key="item.key" class="dashboard-attention-row" type="button" @click="openRoute(item.route)">
              <span class="dashboard-attention-row__icon" :class="`dashboard-attention-row__icon--${item.status}`"><el-icon><component :is="item.icon" /></el-icon></span>
              <span class="dashboard-attention-row__main">
                <strong>{{ item.title }}</strong>
                <small>{{ item.scope }} · {{ item.reason }}</small>
              </span>
              <AdminStatusTag :status="item.status" :label="item.statusLabel" />
              <span class="dashboard-attention-row__action">{{ item.actionLabel }} <span aria-hidden="true">›</span></span>
            </button>
          </div>
          <footer class="dashboard-panel__footer"><el-button link type="primary" @click="openRoute('/qa-logs')">查看全部关注事项</el-button></footer>
        </article>

        <article class="dashboard-panel">
          <header class="dashboard-panel__header">
            <div><span class="dashboard-panel__eyebrow">RECENT RUNS</span><h2>最近运行</h2></div>
            <el-button link type="primary" @click="openRoute('/qa-logs')">查看全部</el-button>
          </header>
          <div v-if="recentRunItems.length > 0" class="dashboard-run-list">
            <button v-for="item in recentRunItems" :key="item.id" class="dashboard-run-row" type="button" @click="openRoute(item.route)">
              <span class="dashboard-run-row__icon"><el-icon><component :is="item.icon" /></el-icon></span>
              <span class="dashboard-run-row__main">
                <strong>{{ item.title }}</strong>
                <small>{{ item.subtitle }}</small>
              </span>
              <AdminStatusTag :status="item.status" :label="item.statusLabel" />
              <span class="dashboard-run-row__time">{{ formatDateTime(item.createdAt) }}</span>
            </button>
          </div>
          <div v-else class="dashboard-empty"><Clock /> 暂无运行记录</div>
          <footer class="dashboard-panel__footer"><el-button link type="primary" @click="openRoute('/qa-logs')">查看更多运行记录</el-button></footer>
        </article>
      </section>
    </template>
  </section>
</template>

<style scoped>
.dashboard-page { display: flex; flex-direction: column; gap: 16px; }
.dashboard-updated { align-self: center; color: var(--admin-text-muted); font-size: 12px; }
.dashboard-health, .dashboard-panel { border: 1px solid var(--admin-border); border-radius: var(--admin-radius-lg); background: var(--admin-surface); box-shadow: var(--admin-shadow-panel); }
.dashboard-health { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); overflow: hidden; }
.dashboard-health__item { display: flex; min-width: 0; align-items: flex-start; gap: 12px; padding: 20px 18px; }
.dashboard-health__item + .dashboard-health__item { border-left: 1px solid var(--admin-border-soft); }
.dashboard-health__icon { display: grid; width: 40px; height: 40px; flex: 0 0 40px; place-items: center; border-radius: 50%; font-size: 20px; }
.dashboard-health__icon--green { background: #ecfdf5; color: #16a34a; }
.dashboard-health__icon--blue { background: #eff6ff; color: #2563eb; }
.dashboard-health__icon--purple { background: #f5f3ff; color: #7c3aed; }
.dashboard-health__icon--indigo { background: #eef2ff; color: #4f46e5; }
.dashboard-health__content { min-width: 0; }
.dashboard-health__title { display: flex; align-items: center; gap: 8px; color: var(--admin-text); }
.dashboard-health__title strong { font-size: 14px; }
.dashboard-health__stats { display: flex; gap: 14px; margin-top: 9px; color: var(--admin-text-muted); font-size: 12px; white-space: nowrap; }
.dashboard-health__stats b { margin-left: 3px; color: var(--admin-text); font-size: 17px; font-weight: 600; }
.dashboard-health__content .el-button { margin-top: 8px; padding: 0; font-size: 12px; }
.dashboard-main-grid { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(360px, 0.85fr); align-items: start; gap: 16px; }
.dashboard-panel { min-width: 0; overflow: hidden; }
.dashboard-panel__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--admin-border-soft); background: var(--admin-surface-muted); padding: 16px 18px; }
.dashboard-panel__eyebrow { color: var(--admin-primary); font-size: 11px; font-weight: 700; letter-spacing: .08em; }
.dashboard-panel h2 { margin: 5px 0 0; color: var(--admin-text); font-size: 17px; }
.dashboard-attention-list, .dashboard-run-list { display: flex; flex-direction: column; }
.dashboard-attention-row, .dashboard-run-row { display: flex; min-width: 0; align-items: center; gap: 11px; border: 0; border-bottom: 1px solid var(--admin-border-soft); background: transparent; cursor: pointer; padding: 13px 18px; text-align: left; }
.dashboard-attention-row:hover, .dashboard-run-row:hover { background: var(--admin-surface-muted); }
.dashboard-attention-row__icon, .dashboard-run-row__icon { display: grid; width: 34px; height: 34px; flex: 0 0 34px; place-items: center; border-radius: 10px; }
.dashboard-attention-row__icon--failed { background: #fef2f2; color: #dc2626; }
.dashboard-attention-row__icon--pending { background: #fff7ed; color: #ea580c; }
.dashboard-attention-row__icon--ok { background: #ecfdf5; color: #16a34a; }
.dashboard-attention-row__icon--info { background: #f1f5f9; color: #64748b; }
.dashboard-attention-row__icon .el-icon, .dashboard-run-row__icon .el-icon { font-size: 15px; }
.dashboard-run-row__icon { background: var(--admin-primary-soft); color: var(--admin-primary); }
.dashboard-attention-row__main, .dashboard-run-row__main { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 4px; }
.dashboard-attention-row__main strong, .dashboard-run-row__main strong { overflow: hidden; color: var(--admin-text); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.dashboard-attention-row__main small, .dashboard-run-row__main small { overflow: hidden; color: var(--admin-text-muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.dashboard-attention-row__action { flex: 0 0 auto; color: var(--admin-primary); font-size: 12px; white-space: nowrap; }
.dashboard-run-row__time { flex: 0 0 auto; color: var(--admin-text-muted); font-size: 11px; white-space: nowrap; }
.dashboard-panel__footer { display: flex; justify-content: center; border-top: 1px solid var(--admin-border-soft); padding: 11px 18px; }
.dashboard-empty { display: flex; min-height: 176px; align-items: center; justify-content: center; gap: 7px; color: var(--admin-text-muted); font-size: 12px; }
@media (max-width: 1120px) { .dashboard-health { grid-template-columns: repeat(2, minmax(0, 1fr)); } .dashboard-health__item:nth-child(3) { border-top: 1px solid var(--admin-border-soft); border-left: 0; } .dashboard-health__item:nth-child(4) { border-top: 1px solid var(--admin-border-soft); } }
@media (max-width: 980px) { .dashboard-main-grid { grid-template-columns: 1fr; } }
@media (max-width: 680px) { .dashboard-updated { display: none; } .dashboard-health { grid-template-columns: 1fr; } .dashboard-health__item + .dashboard-health__item, .dashboard-health__item:nth-child(3), .dashboard-health__item:nth-child(4) { border-top: 1px solid var(--admin-border-soft); border-left: 0; } .dashboard-attention-row__action, .dashboard-run-row__time { display: none; } }
</style>
