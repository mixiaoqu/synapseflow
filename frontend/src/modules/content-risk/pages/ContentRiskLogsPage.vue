<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { Refresh, Search } from "@element-plus/icons-vue";
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
import { useTeamScopeStore } from "@/stores/team-scope";
import { getErrorMessage } from "@/shared/utils/error";

type SceneFilter = "all" | ContentRiskScene;
type ActionFilter = "all" | ContentRiskResolvedAction;
type BlockedFilter = "all" | "blocked" | "recorded";
type RiskLevelFilter = "all" | NonNullable<ContentRiskLogSummary["riskLevel"]>;

const logs = ref<ContentRiskLogSummary[]>([]);
const teamScopeStore = useTeamScopeStore();
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

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
});

const activeFilterCount = computed(() => {
  let count = 0;
  if (filters.scene !== "all") count += 1;
  if (filters.action !== "all") count += 1;
  if (filters.blocked !== "all") count += 1;
  if (filters.riskLevel !== "all") count += 1;
  if (filters.chatLogId.trim()) count += 1;
  return count;
});

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
  if (value === "block") return "danger";
  if (value === "review") return "warning";
  if (value === "pass") return "success";
  return "info";
}

function riskLevelLabel(value: ContentRiskLogSummary["riskLevel"]) {
  if (value === "high") return "高风险";
  if (value === "medium") return "中风险";
  if (value === "low") return "低风险";
  return "未分级";
}

function riskLevelTagType(value: ContentRiskLogSummary["riskLevel"]) {
  if (value === "high") return "danger";
  if (value === "medium") return "warning";
  return "info";
}

function formatDateTime(value: string | null) {
  if (!value) return "-";
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

function sourceName(log: ContentRiskLogSummary) {
  return (
    log.projectAppName ??
    log.projectName ??
    log.teamName ??
    log.productName ??
    log.knowledgeBaseName ??
    log.assistantName ??
    "全局"
  );
}

function primaryRuleName(log: ContentRiskLogSummary) {
  return log.hits[0]?.ruleName ?? "-";
}

function buildLogParams() {
  const chatLogId = Number(filters.chatLogId.trim());
  return {
    page: pagination.page,
    page_size: pagination.pageSize,
    team_id: teamScopeStore.selectedTeamId ?? undefined,
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
  if (loading.value) return;

  loading.value = true;
  loadError.value = null;
  try {
    const response = await listContentRiskLogs(buildLogParams());
    logs.value = response.items;
    pagination.total = response.total;
    hasLoadedData.value = true;
  } catch (error) {
    if (hasLoadedData.value) {
      ElMessage.error(getErrorMessage(error, "刷新判定日志失败"));
    } else {
      loadError.value = error;
    }
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  filters.scene = "all";
  filters.action = "all";
  filters.blocked = "all";
  filters.riskLevel = "all";
  filters.chatLogId = "";
  pagination.page = 1;
  void loadLogs();
}

function handleFilterChange() {
  pagination.page = 1;
  void loadLogs();
}

function handlePageChange(page: number) {
  pagination.page = page;
  void loadLogs();
}

function handlePageSizeChange(pageSize: number) {
  pagination.pageSize = pageSize;
  pagination.page = 1;
  void loadLogs();
}

function openDetail(log: ContentRiskLogSummary) {
  selectedLog.value = log;
  detailVisible.value = true;
}

onMounted(() => {
  void teamScopeStore.bootstrap();
  void loadLogs();
});

watch(
  () => teamScopeStore.selectedTeamId,
  () => {
    pagination.page = 1;
    void loadLogs();
  },
);
</script>

<template>
  <section class="content-risk-logs-page">
    <AppError
      v-if="loadError"
      title="判定日志加载失败"
      :error="loadError"
      @retry="loadLogs"
    />
    <AppLoading
      v-else-if="loading && !hasLoadedData"
      title="判定日志加载中"
      description="正在获取最近的风控判定记录，请稍候。"
    />

    <AdminListPanel v-else>
      <AdminTableToolbar>
        <template #left>
          <el-select
            v-model="filters.scene"
            class="content-risk-logs-page__filter"
            @change="handleFilterChange"
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
            class="content-risk-logs-page__filter"
            @change="handleFilterChange"
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
            class="content-risk-logs-page__filter"
            @change="handleFilterChange"
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
            class="content-risk-logs-page__filter"
            @change="handleFilterChange"
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
          <el-button
            :icon="Refresh"
            :loading="loading"
            @click="loadLogs"
          >
            刷新
          </el-button>
          <el-input
            v-model="filters.chatLogId"
            class="content-risk-logs-page__chat-log"
            clearable
            placeholder="问答日志 ID"
            :prefix-icon="Search"
            @keyup.enter="handleFilterChange"
            @clear="handleFilterChange"
          />
          <el-button
            :icon="Search"
            type="primary"
            @click="handleFilterChange"
          >
            查询
          </el-button>
          <el-button
            v-if="activeFilterCount > 0"
            @click="resetFilters"
          >
            重置
          </el-button>
        </template>
      </AdminTableToolbar>

      <el-table
        v-loading="loading"
        :data="logs"
        row-key="id"
      >
        <el-table-column
          label="时间"
          min-width="150"
        >
          <template #default="{ row }">
            <span class="content-risk-logs-page__muted">{{ formatDateTime(row.createdAt) }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="来源"
          min-width="170"
        >
          <template #default="{ row }">
            <span
              class="content-risk-logs-page__source"
              :title="sourceName(row)"
            >
              {{ sourceName(row) }}
            </span>
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
          min-width="340"
        >
          <template #default="{ row }">
            <p
              class="content-risk-logs-page__snippet"
              :title="row.checkedText"
            >
              {{ row.checkedText || "-" }}
            </p>
            <p
              v-if="row.matchedText"
              class="content-risk-logs-page__hit"
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
            <div class="content-risk-logs-page__tags">
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
            <span class="content-risk-logs-page__muted">{{ row.elapsedMs }}ms</span>
          </template>
        </el-table-column>
        <el-table-column
          label="问答日志"
          min-width="105"
        >
          <template #default="{ row }">
            <span class="content-risk-logs-page__muted">{{ row.chatLogId ?? "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="操作"
          width="96"
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
          <div class="content-risk-logs-page__empty">
            暂无判定日志
          </div>
        </template>
      </el-table>

      <div
        v-if="pagination.total > 0"
        class="content-risk-logs-page__pagination"
      >
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="handlePageChange"
          @size-change="handlePageSizeChange"
        />
      </div>
    </AdminListPanel>

    <el-drawer
      v-model="detailVisible"
      title="判定日志详情"
      size="560px"
    >
      <div
        v-if="selectedLog"
        class="content-risk-logs-page__detail"
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
            <dt>最终动作</dt>
            <dd>{{ actionLabel(selectedLog.action) }}</dd>
          </div>
          <div>
            <dt>风险等级</dt>
            <dd>{{ riskLevelLabel(selectedLog.riskLevel) }}</dd>
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
            class="content-risk-logs-page__hits"
          >
            <div
              v-for="hit in selectedLog.hits"
              :key="`${hit.libraryId}-${hit.ruleId}-${hit.matchedText}`"
            >
              <strong>{{ hit.ruleName }}</strong>
              <span>{{ hit.riskCategory }} · {{ riskLevelLabel(hit.riskLevel) }} · {{ actionLabel(hit.action) }}</span>
              <p>{{ hit.matchedText }}</p>
            </div>
          </div>
          <p v-else>
            -
          </p>
        </section>
      </div>
    </el-drawer>
  </section>
</template>

<style scoped>
.content-risk-logs-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.content-risk-logs-page__filter {
  width: 132px;
}

.content-risk-logs-page__chat-log {
  width: 180px;
}

.content-risk-logs-page__source {
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

.content-risk-logs-page__muted {
  color: var(--admin-text-muted);
  font-size: 12px;
}

.content-risk-logs-page__snippet,
.content-risk-logs-page__hit {
  overflow: hidden;
  margin: 0;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content-risk-logs-page__snippet {
  color: var(--admin-text-muted);
}

.content-risk-logs-page__hit {
  margin-top: 4px;
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.content-risk-logs-page__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.content-risk-logs-page__empty {
  padding: 36px 0;
  color: var(--admin-text-subtle);
  font-size: 13px;
  text-align: center;
}

.content-risk-logs-page__pagination {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--admin-border-soft);
  background: var(--admin-surface);
  padding: 12px;
}

.content-risk-logs-page__detail {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.content-risk-logs-page__detail dl {
  display: grid;
  gap: 10px;
  margin: 0;
}

.content-risk-logs-page__detail dl div {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 12px;
}

.content-risk-logs-page__detail dt {
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.content-risk-logs-page__detail dd {
  margin: 0;
  color: var(--admin-text);
  font-size: 13px;
}

.content-risk-logs-page__detail h3 {
  margin: 0 0 8px;
  color: var(--admin-text);
  font-size: 13px;
  font-weight: 700;
}

.content-risk-logs-page__detail section > p,
.content-risk-logs-page__hits {
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

.content-risk-logs-page__hits {
  display: grid;
  gap: 10px;
}

.content-risk-logs-page__hits div + div {
  border-top: 1px solid var(--admin-border-soft);
  padding-top: 10px;
}

.content-risk-logs-page__hits strong,
.content-risk-logs-page__hits span {
  display: block;
}

.content-risk-logs-page__hits strong {
  color: var(--admin-text);
}

.content-risk-logs-page__hits span {
  margin-top: 4px;
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.content-risk-logs-page__hits p {
  margin: 8px 0 0;
}

@media (max-width: 768px) {
  .content-risk-logs-page__filter,
  .content-risk-logs-page__chat-log {
    width: 100%;
  }
}
</style>
