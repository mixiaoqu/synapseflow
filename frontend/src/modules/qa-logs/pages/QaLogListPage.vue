<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Refresh, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import { listQaLogs } from "@/modules/qa-logs/api";
import type { QaLogSummary } from "@/modules/qa-logs/types";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import { getErrorMessage } from "@/shared/utils/error";

type AnswerStatusFilter = "all" | "answered" | "partial" | "insufficient" | "blocked";
type RetrievalStatusFilter = "all" | "ok" | "no_hits" | "empty_knowledge_base" | "empty_collection";
type FeedbackFilter = "all" | "helpful" | "not_helpful";
type PriorityFilter = "all" | "zero_hits" | "high_latency";

const logs = ref<QaLogSummary[]>([]);
const loading = ref(false);
const loadError = ref<unknown>(null);
const hasLoadedData = ref(false);

const filters = reactive({
  answerStatus: "all" as AnswerStatusFilter,
  retrievalStatus: "all" as RetrievalStatusFilter,
  feedback: "all" as FeedbackFilter,
  priority: "all" as PriorityFilter,
  keyword: "",
});

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
});

const activeFilterCount = computed(() => {
  let count = 0;
  if (filters.answerStatus !== "all") count += 1;
  if (filters.retrievalStatus !== "all") count += 1;
  if (filters.feedback !== "all") count += 1;
  if (filters.priority !== "all") count += 1;
  if (filters.keyword.trim()) count += 1;
  return count;
});

function answerStatusLabel(value: string) {
  const labels: Record<string, string> = {
    answered: "已回答",
    partial: "部分回答",
    insufficient: "依据不足",
    blocked: "已拦截",
  };
  return labels[value] ?? value;
}

function answerStatusTagType(value: string) {
  if (value === "answered") return "success";
  if (value === "blocked") return "danger";
  if (value === "partial" || value === "insufficient") return "warning";
  return "info";
}

function retrievalStatusLabel(value: QaLogSummary["retrievalStatus"]) {
  if (value === "ok") return "已命中";
  if (value === "no_hits") return "无命中";
  if (value === "empty_knowledge_base") return "知识库为空";
  if (value === "empty_collection") return "集合为空";
  return value || "未记录";
}

function retrievalStatusTagType(value: QaLogSummary["retrievalStatus"]) {
  if (value === "ok") return "success";
  if (value === "no_hits") return "warning";
  if (value === "empty_knowledge_base" || value === "empty_collection") return "danger";
  return "info";
}

function feedbackLabel(value: QaLogSummary["feedbackValue"]) {
  if (value === "helpful") return "好评";
  if (value === "not_helpful") return "差评";
  return "未反馈";
}

function feedbackTagType(value: QaLogSummary["feedbackValue"]) {
  if (value === "helpful") return "success";
  if (value === "not_helpful") return "danger";
  return "info";
}

function reviewLabel(log: QaLogSummary) {
  return log.reviewLabel || log.suggestedReviewLabel || "未质检";
}

function reviewTagType(log: QaLogSummary) {
  if (log.reviewLabel) return "success";
  if (log.suggestedReviewLabel) return "warning";
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

function formatLatency(value: number | null) {
  if (value === null) return "-";
  if (value >= 1000) return `${(value / 1000).toFixed(1)}s`;
  return `${value}ms`;
}

function sourceName(log: QaLogSummary) {
  return (
    log.projectAppName ||
    log.projectName ||
    log.assistantName ||
    log.knowledgeBaseName ||
    log.teamName ||
    "未知来源"
  );
}

function userName(log: QaLogSummary) {
  return log.externalUserName || log.externalUserId || (log.userId ? `用户 #${log.userId}` : "-");
}

function buildLogParams() {
  const params = {
    page: pagination.page,
    page_size: pagination.pageSize,
    answer_status: filters.answerStatus === "all" ? undefined : filters.answerStatus,
    retrieval_status: filters.retrievalStatus === "all" ? undefined : filters.retrievalStatus,
    feedback_value:
      filters.feedback === "all" ? undefined : filters.feedback,
    query_keyword: filters.keyword.trim() || undefined,
    zero_hits_only: filters.priority === "zero_hits" ? true : undefined,
    high_latency_only: filters.priority === "high_latency" ? true : undefined,
    high_latency_threshold_ms: filters.priority === "high_latency" ? 5000 : undefined,
  };

  return params;
}

async function loadLogs() {
  if (loading.value) return;

  loading.value = true;
  loadError.value = null;
  try {
    const response = await listQaLogs(buildLogParams());
    logs.value = response.items;
    pagination.total = response.total;
    pagination.page = response.page;
    pagination.pageSize = response.pageSize;
    hasLoadedData.value = true;
  } catch (error) {
    if (hasLoadedData.value) {
      ElMessage.error(getErrorMessage(error, "刷新问答日志失败"));
    } else {
      loadError.value = error;
    }
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  filters.answerStatus = "all";
  filters.retrievalStatus = "all";
  filters.feedback = "all";
  filters.priority = "all";
  filters.keyword = "";
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

onMounted(() => {
  void loadLogs();
});
</script>

<template>
  <section class="qa-log-list-page">
    <AppError
      v-if="loadError"
      title="问答日志加载失败"
      :error="loadError"
      @retry="loadLogs"
    />
    <AppLoading
      v-else-if="loading && !hasLoadedData"
      title="问答日志加载中"
      description="正在获取最近的问答记录，请稍候。"
    />

    <AdminListPanel v-else>
      <AdminTableToolbar>
        <template #left>
          <el-select
            v-model="filters.answerStatus"
            class="qa-log-list-page__filter"
            @change="handleFilterChange"
          >
            <el-option
              label="全部回答"
              value="all"
            />
            <el-option
              label="已回答"
              value="answered"
            />
            <el-option
              label="部分回答"
              value="partial"
            />
            <el-option
              label="依据不足"
              value="insufficient"
            />
            <el-option
              label="已拦截"
              value="blocked"
            />
          </el-select>
          <el-select
            v-model="filters.retrievalStatus"
            class="qa-log-list-page__filter"
            @change="handleFilterChange"
          >
            <el-option
              label="全部检索"
              value="all"
            />
            <el-option
              label="已命中"
              value="ok"
            />
            <el-option
              label="无命中"
              value="no_hits"
            />
            <el-option
              label="知识库为空"
              value="empty_knowledge_base"
            />
            <el-option
              label="集合为空"
              value="empty_collection"
            />
          </el-select>
          <el-select
            v-model="filters.feedback"
            class="qa-log-list-page__filter"
            @change="handleFilterChange"
          >
            <el-option
              label="全部反馈"
              value="all"
            />
            <el-option
              label="好评"
              value="helpful"
            />
            <el-option
              label="差评"
              value="not_helpful"
            />
          </el-select>
          <el-select
            v-model="filters.priority"
            class="qa-log-list-page__filter"
            @change="handleFilterChange"
          >
            <el-option
              label="全部重点"
              value="all"
            />
            <el-option
              label="零命中"
              value="zero_hits"
            />
            <el-option
              label="高延迟"
              value="high_latency"
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
            v-model="filters.keyword"
            class="qa-log-list-page__keyword"
            clearable
            placeholder="搜索问题关键词"
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
            <span class="qa-log-list-page__muted">{{ formatDateTime(row.createdAt) }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="来源"
          min-width="170"
        >
          <template #default="{ row }">
            <span
              class="qa-log-list-page__source"
              :title="sourceName(row)"
            >
              {{ sourceName(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column
          label="用户"
          min-width="130"
        >
          <template #default="{ row }">
            <span
              class="qa-log-list-page__muted"
              :title="userName(row)"
            >{{ userName(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="问答内容"
          min-width="420"
        >
          <template #default="{ row }">
            <p
              class="qa-log-list-page__query"
              :title="row.query"
            >
              {{ row.query || "-" }}
            </p>
            <p
              class="qa-log-list-page__answer"
              :title="row.answerText"
            >
              {{ row.answerText || "-" }}
            </p>
          </template>
        </el-table-column>
        <el-table-column
          label="回答"
          min-width="105"
        >
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="answerStatusTagType(row.answerStatus)"
              effect="plain"
            >
              {{ answerStatusLabel(row.answerStatus) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="检索"
          min-width="120"
        >
          <template #default="{ row }">
            <div class="qa-log-list-page__retrieval">
              <el-tag
                size="small"
                :type="retrievalStatusTagType(row.retrievalStatus)"
                effect="plain"
              >
                {{ retrievalStatusLabel(row.retrievalStatus) }}
              </el-tag>
              <span>{{ row.retrievedCount }} 条</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          label="反馈"
          min-width="96"
        >
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="feedbackTagType(row.feedbackValue)"
              effect="plain"
            >
              {{ feedbackLabel(row.feedbackValue) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="质检"
          min-width="110"
        >
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="reviewTagType(row)"
              effect="plain"
            >
              {{ reviewLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="耗时"
          min-width="90"
        >
          <template #default="{ row }">
            <span class="qa-log-list-page__muted">{{ formatLatency(row.latencyMs) }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <div class="qa-log-list-page__empty">
            暂无问答日志
          </div>
        </template>
      </el-table>

      <div
        v-if="pagination.total > 0"
        class="qa-log-list-page__pagination"
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
  </section>
</template>

<style scoped>
.qa-log-list-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.qa-log-list-page__filter {
  width: 132px;
}

.qa-log-list-page__keyword {
  width: 220px;
}

.qa-log-list-page__source {
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

.qa-log-list-page__muted {
  overflow: hidden;
  color: var(--admin-text-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qa-log-list-page__query,
.qa-log-list-page__answer {
  overflow: hidden;
  margin: 0;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qa-log-list-page__query {
  color: var(--admin-text);
  font-weight: 600;
}

.qa-log-list-page__answer {
  margin-top: 4px;
  color: var(--admin-text-muted);
  font-size: 12px;
}

.qa-log-list-page__retrieval {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.qa-log-list-page__retrieval span {
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.qa-log-list-page__empty {
  padding: 36px 0;
  color: var(--admin-text-subtle);
  font-size: 13px;
  text-align: center;
}

.qa-log-list-page__pagination {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--admin-border-soft);
  background: var(--admin-surface);
  padding: 12px;
}

@media (max-width: 768px) {
  .qa-log-list-page__filter,
  .qa-log-list-page__keyword {
    width: 100%;
  }
}
</style>
