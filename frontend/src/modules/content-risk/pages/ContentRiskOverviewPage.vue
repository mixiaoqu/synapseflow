<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { DocumentChecked, Refresh, Search, Warning } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import { listContentRiskLogs } from "@/modules/content-risk/api";
import type {
  ContentRiskLogSummary,
  ContentRiskResolvedAction,
  ContentRiskScene,
} from "@/modules/content-risk/types";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import { getErrorMessage } from "@/shared/utils/error";

type SceneFilter = "all" | ContentRiskScene;
type ActionFilter = "all" | ContentRiskResolvedAction;
type BlockedFilter = "all" | "blocked" | "recorded";
type RiskLevelFilter = "all" | NonNullable<ContentRiskLogSummary["riskLevel"]>;

const logs = ref<ContentRiskLogSummary[]>([]);
const total = ref(0);
const loading = ref(false);
const loadError = ref<unknown>(null);
const hasLoadedData = ref(false);
const detailVisible = ref(false);
const selectedLog = ref<ContentRiskLogSummary | null>(null);

const filters = reactive({
  scene: "all" as SceneFilter,
  action: "all" as ActionFilter,
  blocked: "all" as BlockedFilter,
  riskLevel: "all" as RiskLevelFilter,
  chatLogId: "",
});

const queryHits = computed(() => logs.value.filter((item) => item.scene === "query").length);
const answerHits = computed(() => logs.value.filter((item) => item.scene === "answer").length);
const blockedHits = computed(() => logs.value.filter((item) => item.blocked).length);
const reviewHits = computed(() => logs.value.filter((item) => item.action === "review").length);
const highRiskHits = computed(() => logs.value.filter((item) => item.riskLevel === "high").length);
const pendingLogs = computed(() =>
  logs.value.filter((item) => item.action === "review" || item.blocked || item.riskLevel === "high").slice(0, 5),
);

const summaryCards = computed(() => [
  {
    label: "判定日志",
    value: total.value,
    helper: "当前筛选条件下的风控记录",
  },
  {
    label: "已拦截",
    value: blockedHits.value,
    helper: "最近加载日志中的拦截结果",
  },
  {
    label: "待复核",
    value: reviewHits.value,
    helper: "需要人工确认的规则动作",
  },
  {
    label: "高风险",
    value: highRiskHits.value,
    helper: "最近命中的高风险内容",
  },
]);

const sourceBreakdown = computed(() => [
  { label: "提问侧", value: queryHits.value },
  { label: "回答侧", value: answerHits.value },
]);

function sceneLabel(value: ContentRiskScene) {
  return value === "query" ? "用户提问" : "AI 回答";
}

function actionLabel(value: ContentRiskResolvedAction) {
  const labels: Record<ContentRiskResolvedAction, string> = {
    pass: "放行",
    block: "拦截",
    review: "人工复核",
    log: "仅记录",
  };
  return labels[value];
}

function actionTagType(value: ContentRiskResolvedAction) {
  if (value === "block") {
    return "danger";
  }
  if (value === "review") {
    return "warning";
  }
  return "info";
}

function riskLevelLabel(value: ContentRiskLogSummary["riskLevel"]) {
  if (value === "high") {
    return "高风险";
  }
  if (value === "medium") {
    return "中风险";
  }
  if (value === "low") {
    return "低风险";
  }
  return "未分级";
}

function riskLevelTagType(value: ContentRiskLogSummary["riskLevel"]) {
  if (value === "high") {
    return "danger";
  }
  if (value === "medium") {
    return "warning";
  }
  if (value === "low") {
    return "info";
  }
  return "info";
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "-";
  }
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

function buildLogParams() {
  const chatLogId = Number(filters.chatLogId.trim());
  return {
    page: 1,
    page_size: 50,
    scene: filters.scene === "all" ? undefined : filters.scene,
    action: filters.action === "all" ? undefined : filters.action,
    blocked:
      filters.blocked === "all"
        ? undefined
        : filters.blocked === "blocked",
    risk_level: filters.riskLevel === "all" ? undefined : filters.riskLevel,
    chat_log_id: Number.isFinite(chatLogId) && chatLogId > 0 ? chatLogId : undefined,
  };
}

async function loadLogs() {
  if (loading.value) {
    return;
  }

  loading.value = true;
  loadError.value = null;
  try {
    const response = await listContentRiskLogs(buildLogParams());
    logs.value = response.items;
    total.value = response.total;
    hasLoadedData.value = true;
  } catch (error) {
    if (hasLoadedData.value) {
      ElMessage.error(getErrorMessage(error, "刷新风控日志失败"));
    } else {
      loadError.value = error;
    }
  } finally {
    loading.value = false;
  }
}

function primaryRuleName(log: ContentRiskLogSummary) {
  return log.hits[0]?.ruleName ?? "-";
}

function sourceName(log: ContentRiskLogSummary) {
  return (
    log.projectAppName ??
    log.projectName ??
    log.productName ??
    log.knowledgeBaseName ??
    log.assistantName ??
    "全局"
  );
}

function openDetail(log: ContentRiskLogSummary) {
  selectedLog.value = log;
  detailVisible.value = true;
}

onMounted(() => {
  void loadLogs();
});
</script>

<template>
  <div class="content-risk-overview-page">
    <div class="content-risk-overview-page__actions">
      <el-button
        :icon="Refresh"
        :loading="loading"
        @click="loadLogs"
      >
        刷新
      </el-button>
    </div>

    <AppError
      v-if="loadError"
      title="内容风控加载失败"
      :error="loadError"
      @retry="loadLogs"
    />
    <AppLoading
      v-else-if="loading && !hasLoadedData"
      title="内容风控加载中"
      description="正在获取最近的风控判定日志，请稍候。"
    />

    <template v-else>
      <section class="content-risk-overview-page__summary">
        <article
          v-for="card in summaryCards"
          :key="card.label"
          class="risk-metric"
        >
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <p>{{ card.helper }}</p>
        </article>
      </section>

      <section class="content-risk-overview-page__workbench">
        <div class="risk-workbench-panel">
          <div class="risk-workbench-panel__title">
            <el-icon><Warning /></el-icon>
            <span>近期重点记录</span>
          </div>
          <div
            v-if="pendingLogs.length > 0"
            class="risk-priority-list"
          >
            <button
              v-for="log in pendingLogs"
              :key="log.id"
              type="button"
              class="risk-priority-item"
              @click="openDetail(log)"
            >
              <span>
                <strong>{{ riskLevelLabel(log.riskLevel) }}</strong>
                <small>{{ sourceName(log) }} · {{ sceneLabel(log.scene) }}</small>
              </span>
              <el-tag
                size="small"
                :type="actionTagType(log.action)"
                effect="plain"
              >
                {{ actionLabel(log.action) }}
              </el-tag>
            </button>
          </div>
          <div
            v-else
            class="risk-empty-inline"
          >
            暂无高风险、拦截或复核记录
          </div>
        </div>

        <div class="risk-workbench-panel">
          <div class="risk-workbench-panel__title">
            <el-icon><DocumentChecked /></el-icon>
            <span>场景分布</span>
          </div>
          <div class="risk-source-list">
            <div
              v-for="item in sourceBreakdown"
              :key="item.label"
              class="risk-source-item"
            >
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </div>
      </section>

      <AdminListPanel>
        <AdminTableToolbar>
          <template #left>
            <el-select
              v-model="filters.scene"
              class="risk-filter"
              @change="loadLogs"
            >
              <el-option
                label="全部场景"
                value="all"
              />
              <el-option
                label="用户提问"
                value="query"
              />
              <el-option
                label="AI 回答"
                value="answer"
              />
            </el-select>
            <el-select
              v-model="filters.action"
              class="risk-filter"
              @change="loadLogs"
            >
              <el-option
                label="全部动作"
                value="all"
              />
              <el-option
                label="放行"
                value="pass"
              />
              <el-option
                label="拦截"
                value="block"
              />
              <el-option
                label="人工复核"
                value="review"
              />
              <el-option
                label="仅记录"
                value="log"
              />
            </el-select>
            <el-select
              v-model="filters.riskLevel"
              class="risk-filter"
              @change="loadLogs"
            >
              <el-option
                label="全部风险"
                value="all"
              />
              <el-option
                label="高风险"
                value="high"
              />
              <el-option
                label="中风险"
                value="medium"
              />
              <el-option
                label="低风险"
                value="low"
              />
            </el-select>
            <el-select
              v-model="filters.blocked"
              class="risk-filter"
              @change="loadLogs"
            >
              <el-option
                label="全部结果"
                value="all"
              />
              <el-option
                label="已拦截"
                value="blocked"
              />
              <el-option
                label="未拦截"
                value="recorded"
              />
            </el-select>
          </template>
          <template #right>
            <el-input
              v-model="filters.chatLogId"
              class="risk-chat-log-filter"
              clearable
              placeholder="问答日志 ID"
              :prefix-icon="Search"
              @keyup.enter="loadLogs"
              @clear="loadLogs"
            />
            <el-button
              :icon="Search"
              type="primary"
              @click="loadLogs"
            >
              查询
            </el-button>
          </template>
        </AdminTableToolbar>

        <el-table
          v-loading="loading"
          :data="logs"
          row-key="id"
          class="content-risk-overview-page__table"
        >
          <el-table-column
            label="时间"
            min-width="150"
          >
            <template #default="{ row }">
              <span class="risk-muted-text">{{ formatDateTime(row.createdAt) }}</span>
            </template>
          </el-table-column>
          <el-table-column
            label="来源"
            min-width="170"
          >
            <template #default="{ row }">
              <span class="risk-source-pill">{{ sourceName(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column
            label="场景"
            min-width="105"
          >
            <template #default="{ row }">
              {{ sceneLabel(row.scene) }}
            </template>
          </el-table-column>
          <el-table-column
            label="文本片段"
            min-width="320"
          >
            <template #default="{ row }">
              <p
                class="risk-text-snippet"
                :title="row.checkedText"
              >
                {{ row.checkedText || "-" }}
              </p>
              <p
                v-if="row.matchedText"
                class="risk-hit-snippet"
              >
                命中：{{ row.matchedText }}
              </p>
            </template>
          </el-table-column>
          <el-table-column
            label="命中规则"
            min-width="180"
          >
            <template #default="{ row }">
              <div class="risk-rule-tags">
                <el-tag
                  size="small"
                  type="danger"
                  effect="plain"
                >
                  {{ primaryRuleName(row) }}
                </el-tag>
                <el-tag
                  v-if="row.hits.length > 1"
                  size="small"
                  type="info"
                  effect="plain"
                >
                  +{{ row.hits.length - 1 }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column
            label="风险"
            min-width="105"
          >
            <template #default="{ row }">
              <el-tag
                size="small"
                :type="riskLevelTagType(row.riskLevel)"
                effect="plain"
              >
                {{ riskLevelLabel(row.riskLevel) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="动作"
            min-width="110"
          >
            <template #default="{ row }">
              <el-tag
                size="small"
                :type="actionTagType(row.action)"
                effect="plain"
              >
                {{ actionLabel(row.action) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="耗时"
            min-width="90"
          >
            <template #default="{ row }">
              <span class="risk-muted-text">{{ row.elapsedMs }}ms</span>
            </template>
          </el-table-column>
          <el-table-column
            label="操作"
            width="100"
            fixed="right"
          >
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                @click="openDetail(row)"
              >
                详情
              </el-button>
            </template>
          </el-table-column>
          <template #empty>
            <div class="risk-table-empty">
              暂无风控判定日志
            </div>
          </template>
        </el-table>
      </AdminListPanel>
    </template>

    <el-drawer
      v-model="detailVisible"
      title="风控判定详情"
      size="520px"
    >
      <div
        v-if="selectedLog"
        class="risk-detail"
      >
        <dl>
          <div>
            <dt>判定时间</dt>
            <dd>{{ formatDateTime(selectedLog.createdAt) }}</dd>
          </div>
          <div>
            <dt>来源</dt>
            <dd>{{ sourceName(selectedLog) }}</dd>
          </div>
          <div>
            <dt>场景</dt>
            <dd>{{ sceneLabel(selectedLog.scene) }}</dd>
          </div>
          <div>
            <dt>问答日志 ID</dt>
            <dd>{{ selectedLog.chatLogId ?? "-" }}</dd>
          </div>
        </dl>

        <section>
          <h3>检测文本</h3>
          <p>{{ selectedLog.checkedText || "-" }}</p>
        </section>

        <section>
          <h3>命中文本</h3>
          <p>{{ selectedLog.matchedText || "-" }}</p>
        </section>

        <section>
          <h3>命中规则</h3>
          <div
            v-if="selectedLog.hits.length > 0"
            class="risk-detail__hits"
          >
            <div
              v-for="hit in selectedLog.hits"
              :key="`${hit.libraryId}-${hit.ruleId}-${hit.matchedText}`"
            >
              <strong>{{ hit.ruleName }}</strong>
              <span>{{ riskLevelLabel(hit.riskLevel) }} · {{ actionLabel(hit.action) }}</span>
              <p>{{ hit.matchedText }}</p>
            </div>
          </div>
          <p v-else>
            -
          </p>
        </section>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.content-risk-overview-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.content-risk-overview-page__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
}

.content-risk-overview-page__summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.risk-metric {
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-lg);
  background: var(--admin-surface);
  padding: 16px;
  box-shadow: var(--admin-shadow-panel);
}

.risk-metric span {
  display: block;
  color: var(--admin-text-muted);
  font-size: 12px;
  font-weight: 600;
}

.risk-metric strong {
  display: block;
  margin-top: 10px;
  color: var(--admin-text);
  font-size: 28px;
  line-height: 1;
}

.risk-metric p {
  margin: 10px 0 0;
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.content-risk-overview-page__workbench {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr);
  gap: 12px;
}

.risk-workbench-panel {
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-lg);
  background: var(--admin-surface);
  padding: 14px;
  box-shadow: var(--admin-shadow-panel);
}

.risk-workbench-panel__title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--admin-text);
  font-size: 13px;
  font-weight: 700;
}

.risk-priority-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.risk-priority-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-md);
  background: var(--admin-surface-muted);
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
}

.risk-priority-item strong,
.risk-priority-item small {
  display: block;
}

.risk-priority-item strong {
  color: var(--admin-text);
  font-size: 13px;
}

.risk-priority-item small {
  margin-top: 4px;
  color: var(--admin-text-muted);
  font-size: 12px;
}

.risk-source-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.risk-source-item {
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-md);
  background: var(--admin-surface-muted);
  padding: 12px;
}

.risk-source-item span {
  color: var(--admin-text-muted);
  font-size: 12px;
}

.risk-source-item strong {
  display: block;
  margin-top: 8px;
  color: var(--admin-text);
  font-size: 22px;
}

.risk-empty-inline,
.risk-table-empty {
  padding: 28px 0;
  color: var(--admin-text-subtle);
  font-size: 13px;
  text-align: center;
}

.risk-filter {
  width: 132px;
}

.risk-chat-log-filter {
  width: 180px;
}

.content-risk-overview-page__table {
  width: 100%;
}

.risk-muted-text {
  color: var(--admin-text-muted);
  font-size: 12px;
}

.risk-source-pill {
  display: inline-flex;
  max-width: 150px;
  overflow: hidden;
  border-radius: var(--admin-radius-sm);
  background: var(--admin-surface-muted);
  padding: 4px 8px;
  color: var(--admin-text-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.risk-text-snippet,
.risk-hit-snippet {
  overflow: hidden;
  margin: 0;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.risk-text-snippet {
  color: var(--admin-text-muted);
}

.risk-hit-snippet {
  margin-top: 4px;
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.risk-rule-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.risk-detail {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.risk-detail dl {
  display: grid;
  gap: 10px;
  margin: 0;
}

.risk-detail dl div {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 12px;
}

.risk-detail dt {
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.risk-detail dd {
  margin: 0;
  color: var(--admin-text);
  font-size: 13px;
}

.risk-detail h3 {
  margin: 0 0 8px;
  color: var(--admin-text);
  font-size: 13px;
  font-weight: 700;
}

.risk-detail section > p,
.risk-detail__hits {
  margin: 0;
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-md);
  background: var(--admin-surface-muted);
  padding: 12px;
  color: var(--admin-text-muted);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.risk-detail__hits {
  display: grid;
  gap: 10px;
}

.risk-detail__hits div + div {
  border-top: 1px solid var(--admin-border-soft);
  padding-top: 10px;
}

.risk-detail__hits strong,
.risk-detail__hits span {
  display: block;
}

.risk-detail__hits strong {
  color: var(--admin-text);
}

.risk-detail__hits span {
  margin-top: 4px;
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.risk-detail__hits p {
  margin: 8px 0 0;
}

@media (max-width: 1024px) {
  .content-risk-overview-page__summary,
  .content-risk-overview-page__workbench {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .content-risk-overview-page__header {
    flex-direction: column;
  }

  .content-risk-overview-page__summary,
  .content-risk-overview-page__workbench,
  .risk-source-list {
    grid-template-columns: 1fr;
  }

  .risk-filter,
  .risk-chat-log-filter {
    width: 100%;
  }
}
</style>
