<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  Bell,
  Connection,
  CircleCheck,
  CircleClose,
  Clock,
  Document,
  InfoFilled,
  MagicStick,
  RefreshRight,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import AdminPageHeader from "@/app/components/admin/AdminPageHeader.vue";
import AdminStatusTag from "@/app/components/admin/AdminStatusTag.vue";
import { listQaLogs } from "@/modules/qa-logs/api";
import type { QaLogSummary } from "@/modules/qa-logs/types";
import { listAssistants } from "@/shared/api/assistants";
import { listKnowledgeBases } from "@/shared/api/knowledge-bases";
import { listProjects } from "@/shared/api/projects";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import type { AssistantSummary } from "@/shared/types/assistant";
import type { KnowledgeBaseListItem } from "@/shared/types/knowledge-base";
import type { ProjectSummary } from "@/shared/types/project";
import { useTeamScopeStore } from "@/stores/team-scope";

const router = useRouter();
const teamScopeStore = useTeamScopeStore();

const loading = ref(false);
const loadError = ref<unknown>(null);
const hasLoadedData = ref(false);
const knowledgeBases = ref<KnowledgeBaseListItem[]>([]);
const assistants = ref<AssistantSummary[]>([]);
const projects = ref<ProjectSummary[]>([]);
const qaLogs = ref<QaLogSummary[]>([]);
const knowledgeBaseTotal = ref(0);
const projectTotal = ref(0);
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

function formatDateTime(value: string | null) {
  if (!value) return "暂无时间";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}

function formatLatency(value: number | null) {
  if (value === null) return "-";
  return value >= 1000 ? `${(value / 1000).toFixed(1)}s` : `${value}ms`;
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

async function loadDashboard() {
  if (loading.value) return;
  loading.value = true;
  loadError.value = null;

  try {
    const teamId = teamScopeStore.selectedTeamId ?? undefined;
    const [knowledgeBaseResult, assistantResult, activeResult, inactiveResult, projectResult, qaResult] = await Promise.all([
      listKnowledgeBases({ team_id: teamId, page: 1, page_size: 100 }),
      listAssistants({ team_id: teamId, status: "all", page: 1, page_size: 100 }),
      listAssistants({ team_id: teamId, status: "active", page: 1, page_size: 1 }),
      listAssistants({ team_id: teamId, status: "inactive", page: 1, page_size: 1 }),
      listProjects({ team_id: teamId, page: 1, page_size: 100 }),
      listQaLogs({ team_id: teamId, page: 1, page_size: 7 }),
    ]);

    knowledgeBases.value = knowledgeBaseResult.items;
    knowledgeBaseTotal.value = knowledgeBaseResult.total;
    assistants.value = assistantResult.items;
    activeAssistantTotal.value = activeResult.total;
    inactiveAssistantTotal.value = inactiveResult.total;
    projects.value = projectResult.items;
    projectTotal.value = projectResult.total;
    qaLogs.value = qaResult.items;
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

function openQaLog() {
  void router.push("/qa-logs");
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
          <div>
            <div class="dashboard-health__title"><strong>知识库索引</strong><AdminStatusTag :status="failedDocumentTotal > 0 ? 'failed' : 'ok'" /></div>
            <div class="dashboard-health__stats"><span>已索引文档 <b>{{ indexedDocumentTotal }}</b></span><span>待处理 <b>{{ pendingDocumentTotal }}</b></span></div>
          </div>
        </article>
        <article class="dashboard-health__item">
          <span class="dashboard-health__icon dashboard-health__icon--blue"><MagicStick /></span>
          <div>
            <div class="dashboard-health__title"><strong>智能体（Assistants）</strong><AdminStatusTag :status="activeAssistantTotal > 0 ? 'ok' : 'pending'" /></div>
            <div class="dashboard-health__stats"><span>运行中 <b>{{ activeAssistantTotal }}</b></span><span>停用 <b>{{ inactiveAssistantTotal }}</b></span></div>
          </div>
        </article>
        <article class="dashboard-health__item">
          <span class="dashboard-health__icon dashboard-health__icon--purple"><Connection /></span>
          <div>
            <div class="dashboard-health__title"><strong>已接入应用</strong><AdminStatusTag :status="projectAppTotal > 0 ? 'ok' : 'pending'" /></div>
            <div class="dashboard-health__stats"><span>应用端 <b>{{ projectAppTotal }}</b></span><span>项目 <b>{{ projectTotal }}</b></span></div>
          </div>
        </article>
      </section>

      <section class="dashboard-main-grid">
        <article class="dashboard-panel">
          <header class="dashboard-panel__header">
            <div><span class="dashboard-panel__eyebrow">QA LOGS</span><h2>运行状态</h2></div>
            <el-button link type="primary" @click="router.push('/qa-logs')">查看全部</el-button>
          </header>
          <div class="dashboard-filter-hint"><span><Clock /> 最近 7 条应用请求</span><span>请求来源：应用端</span></div>
          <div v-if="qaLogs.length > 0" class="dashboard-run-list">
            <button v-for="item in qaLogs" :key="item.id" class="dashboard-run-row" type="button" @click="openQaLog()">
              <span class="dashboard-run-row__time">{{ formatDateTime(item.createdAt) }}</span>
              <span class="dashboard-run-row__dot" :class="`dashboard-run-row__dot--${answerStatus(item.answerStatus)}`" />
              <span class="dashboard-run-row__main">
                <strong>{{ item.assistantName || "默认助手" }}</strong>
                <small>请求来源：应用端 · {{ item.projectAppName || "未标记应用" }} · 耗时 {{ formatLatency(item.latencyMs) }}</small>
              </span>
              <AdminStatusTag :status="answerStatus(item.answerStatus)" :label="answerStatusLabel(item.answerStatus)" />
              <span class="dashboard-run-row__link">查看日志</span>
            </button>
          </div>
          <AppEmpty v-else title="暂无运行记录" description="应用产生问答请求后，运行状态会显示在这里。" compact />
          <footer class="dashboard-panel__footer"><el-button link type="primary" @click="router.push('/qa-logs')">查看更多运行记录</el-button></footer>
        </article>

        <article class="dashboard-panel">
          <header class="dashboard-panel__header">
            <div><span class="dashboard-panel__eyebrow">QUALITY</span><h2>质量观察</h2></div>
            <el-button link type="primary" @click="router.push('/qa-logs')">查看全部</el-button>
          </header>
          <div class="dashboard-quality-list">
            <div class="dashboard-quality-row">
              <span class="dashboard-quality-row__icon dashboard-quality-row__icon--danger"><CircleClose /></span>
              <div><strong>失败回答</strong><small>最近 7 条应用请求</small></div>
              <b>{{ failedQaTotal }}</b>
            </div>
            <div class="dashboard-quality-row">
              <span class="dashboard-quality-row__icon dashboard-quality-row__icon--warning"><Bell /></span>
              <div><strong>响应较慢</strong><small>耗时超过 3 秒</small></div>
              <b>{{ delayedQaTotal }}</b>
            </div>
            <div class="dashboard-quality-row">
              <span class="dashboard-quality-row__icon dashboard-quality-row__icon--success"><CircleCheck /></span>
              <div><strong>正常回答</strong><small>应用请求已完成</small></div>
              <b>{{ Math.max(qaLogs.length - failedQaTotal, 0) }}</b>
            </div>
          </div>
          <div class="dashboard-quality-note"><InfoFilled /> 质量观察基于当前 QA 日志，不代表独立告警服务。</div>
          <footer class="dashboard-panel__footer"><el-button type="primary" @click="router.push('/evaluations')">查看评测</el-button></footer>
        </article>
      </section>
    </template>
  </section>
</template>

<style scoped>
.dashboard-page { display: flex; flex-direction: column; gap: 16px; }
.dashboard-updated { align-self: center; color: var(--admin-text-muted); font-size: 12px; }
.dashboard-health, .dashboard-panel { border: 1px solid var(--admin-border); border-radius: var(--admin-radius-lg); background: var(--admin-surface); box-shadow: var(--admin-shadow-panel); }
.dashboard-health { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); overflow: hidden; }
.dashboard-health__item { display: flex; min-width: 0; align-items: center; gap: 14px; padding: 22px 20px; }
.dashboard-health__item + .dashboard-health__item { border-left: 1px solid var(--admin-border-soft); }
.dashboard-health__icon { display: grid; width: 44px; height: 44px; flex: 0 0 44px; place-items: center; border-radius: 50%; font-size: 22px; }
.dashboard-health__icon--green { background: #ecfdf5; color: #16a34a; }
.dashboard-health__icon--blue { background: #eff6ff; color: #2563eb; }
.dashboard-health__icon--purple { background: #f5f3ff; color: #7c3aed; }
.dashboard-health__title { display: flex; align-items: center; gap: 8px; color: var(--admin-text); }
.dashboard-health__title strong { font-size: 14px; }
.dashboard-health__stats { display: flex; gap: 24px; margin-top: 10px; color: var(--admin-text-muted); font-size: 12px; }
.dashboard-health__stats b { margin-left: 4px; color: var(--admin-text); font-size: 18px; font-weight: 500; }
.dashboard-main-grid { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(360px, 0.85fr); gap: 16px; }
.dashboard-panel { min-width: 0; overflow: hidden; }
.dashboard-panel__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--admin-border-soft); background: var(--admin-surface-muted); padding: 16px 18px; }
.dashboard-panel__eyebrow { color: var(--admin-primary); font-size: 11px; font-weight: 700; letter-spacing: .08em; }
.dashboard-panel h2 { margin: 5px 0 0; color: var(--admin-text); font-size: 17px; }
.dashboard-filter-hint { display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--admin-border-soft); color: var(--admin-text-muted); font-size: 12px; padding: 11px 18px; }
.dashboard-filter-hint span:first-child { display: inline-flex; align-items: center; gap: 6px; }
.dashboard-run-list { display: flex; flex-direction: column; }
.dashboard-run-row { display: flex; min-height: 68px; align-items: center; gap: 10px; border: 0; border-bottom: 1px solid var(--admin-border-soft); background: transparent; cursor: pointer; padding: 10px 18px; text-align: left; }
.dashboard-run-row:hover { background: var(--admin-surface-muted); }
.dashboard-run-row__time { width: 84px; flex: 0 0 84px; color: var(--admin-text-muted); font-size: 11px; }
.dashboard-run-row__dot { width: 8px; height: 8px; flex: 0 0 8px; border-radius: 50%; }
.dashboard-run-row__dot--success { background: #16a34a; }
.dashboard-run-row__dot--warning { background: #f59e0b; }
.dashboard-run-row__dot--failed { background: #dc2626; }
.dashboard-run-row__dot--info { background: #64748b; }
.dashboard-run-row__main { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 4px; }
.dashboard-run-row__main strong { overflow: hidden; color: var(--admin-text); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.dashboard-run-row__main small, .dashboard-run-row__link { color: var(--admin-text-muted); font-size: 11px; }
.dashboard-run-row__link { color: var(--admin-primary); }
.dashboard-panel__footer { display: flex; justify-content: center; border-top: 1px solid var(--admin-border-soft); padding: 12px 18px; }
.dashboard-quality-list { display: flex; flex-direction: column; padding: 6px 18px; }
.dashboard-quality-row { display: flex; align-items: center; gap: 12px; border-bottom: 1px solid var(--admin-border-soft); padding: 16px 0; }
.dashboard-quality-row:last-child { border-bottom: 0; }
.dashboard-quality-row__icon { display: grid; width: 34px; height: 34px; flex: 0 0 34px; place-items: center; border-radius: 10px; }
.dashboard-quality-row__icon--danger { background: #fef2f2; color: #dc2626; }
.dashboard-quality-row__icon--warning { background: #fff7ed; color: #ea580c; }
.dashboard-quality-row__icon--success { background: #ecfdf5; color: #16a34a; }
.dashboard-quality-row div { display: flex; flex: 1; flex-direction: column; gap: 3px; }
.dashboard-quality-row strong { color: var(--admin-text); font-size: 14px; }
.dashboard-quality-row small { color: var(--admin-text-muted); font-size: 12px; }
.dashboard-quality-row b { color: var(--admin-text); font-size: 24px; font-weight: 600; }
.dashboard-quality-note { display: flex; align-items: flex-start; gap: 7px; margin: 8px 18px 16px; border: 1px solid var(--admin-primary-border); border-radius: 10px; background: var(--admin-primary-soft); color: var(--admin-text-secondary); font-size: 11px; line-height: 1.5; padding: 10px; }
.dashboard-quality-note .el-icon { color: var(--admin-primary); }
@media (max-width: 980px) { .dashboard-health, .dashboard-main-grid { grid-template-columns: 1fr; } .dashboard-health__item + .dashboard-health__item { border-top: 1px solid var(--admin-border-soft); border-left: 0; } }
@media (max-width: 680px) { .dashboard-updated { display: none; } .dashboard-filter-hint { flex-direction: column; } .dashboard-run-row__time { display: none; } .dashboard-run-row__link { display: none; } }
</style>
