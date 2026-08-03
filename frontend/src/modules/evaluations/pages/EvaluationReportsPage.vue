<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Back,
  Calendar,
  Cpu,
  DataAnalysis,
  Document,
  Files,
  Plus,
  RefreshRight,
  Search,
  Timer,
  View,
  VideoPlay,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import AdminDataTable from "@/app/components/admin/AdminDataTable.vue";
import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminPagination from "@/app/components/admin/AdminPagination.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import {
  executeEvalDataset,
  getEvalCaseRetrievedEvidence,
  getEvalRunDetail,
  listEvalDatasets,
  listEvalCases,
  listEvalRuns,
  resumeEvalRun,
} from "@/shared/api/evaluations";
import { listAssistants } from "@/shared/api/assistants";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import type {
  EvalCaseResult,
  EvalCaseResultStatus,
  EvalDataset,
  EvalRetrievedDocumentEvidence,
  EvalRunDetail,
  EvalRunListItem,
  EvalRunStatus,
} from "@/modules/evaluations/types";
import type { AssistantSummary } from "@/shared/types/assistant";

interface EvalRunTaskRow {
  id: number;
  name: string;
  runCode: string;
  datasetName: string;
  datasetVersion: string;
  status: EvalRunStatus;
  modelLabel: string;
  totalCases: number;
  passedCases: number;
  failedCases: number;
  averageScore: number;
  passRateText: string;
  durationText: string;
  startedAt: string;
  finishedAt: string;
  heartbeatAt: string | null;
}

interface ReportCaseRow {
  id: number;
  caseId: number;
  status: EvalCaseResultStatus;
  score: number;
  question: string;
  expectedAnswer: string;
  actualAnswer: string;
  retrievedEvidence: EvalRetrievedDocumentEvidence[];
  judgeReason: string;
  errorMessage: string | null;
  latencyText: string;
}

type ReportFilter = "all" | "passed" | "failed";
type RunStatusFilter = "all" | EvalRunStatus;

const route = useRoute();
const router = useRouter();

const taskLoading = ref(false);
const taskHasLoadedData = ref(false);
const taskLoadError = ref<unknown>(null);
const taskRuns = ref<EvalRunListItem[]>([]);
const datasets = ref<EvalDataset[]>([]);
const taskKeyword = ref("");
const taskStatusFilter = ref<RunStatusFilter>("all");
const createDrawerVisible = ref(false);
const createSubmitting = ref(false);
const resumingRunIds = ref<Set<number>>(new Set());
const datasetLoading = ref(false);
const assistantLoading = ref(false);
const assistants = ref<AssistantSummary[]>([]);
const selectedDatasetCaseCount = ref<number | null>(null);
const createForm = reactive({
  runName: "",
  datasetId: null as number | null,
  assistantId: null as number | null,
  targetType: "kb_chat",
  judgeMethod: "llm_judge",
  recallEnabled: true,
  faithfulnessEnabled: true,
  relevanceEnabled: true,
});
const taskPagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
});

const reportLoading = ref(false);
const reportHasLoadedData = ref(false);
const reportLoadError = ref<unknown>(null);
const runDetail = ref<EvalRunDetail | null>(null);
const activeFilter = ref<ReportFilter>("all");
const expandedTextKeys = ref<Set<string>>(new Set());
const expandedEvidenceKeys = ref<Set<string>>(new Set());
const retrievedEvidenceByResultId = ref<Record<number, EvalRetrievedDocumentEvidence[]>>({});
const evidenceLoadingResultIds = ref<Set<number>>(new Set());
const reportPagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
});
let taskRequestSeq = 0;
let reportRequestSeq = 0;

const runId = computed(() => {
  const raw = Number(route.params.runId);
  return Number.isInteger(raw) && raw > 0 ? raw : null;
});
const isReportDetail = computed(() => runId.value !== null);
const taskRows = computed<EvalRunTaskRow[]>(() =>
  taskRuns.value.map((item) => ({
    id: item.id,
    name: item.run_name?.trim() || item.dataset_name,
    runCode: `RUN-${item.id}`,
    datasetName: item.dataset_name,
    datasetVersion: item.dataset_version,
    status: item.status,
    modelLabel: formatModelConfig(item.model_config),
    totalCases: item.total_cases,
    passedCases: item.passed_cases,
    failedCases: item.failed_cases,
    averageScore: item.average_score,
    passRateText: formatPassRate(item),
    durationText: formatDuration(item.started_at, item.finished_at, item.status),
    startedAt: formatDateTime(item.started_at),
    finishedAt: formatDateTime(item.finished_at),
    heartbeatAt: item.heartbeat_at,
  })),
);
const reportRows = computed<ReportCaseRow[]>(() =>
  (runDetail.value?.results ?? []).map((result) => {
    const caseSnapshot = result.case_snapshot ?? {};
    return {
      id: result.id,
      caseId: result.case_id ?? Number(caseSnapshot.case_id ?? 0),
      status: result.status,
      score: result.score,
      question: String(caseSnapshot.question ?? `用例 #${result.case_id ?? "未知"}`),
      expectedAnswer: String(caseSnapshot.expected_answer ?? "历史运行未保存期望答案。"),
      actualAnswer: result.actual_answer?.trim() || "暂无实际回答",
      retrievedEvidence: retrievedEvidenceByResultId.value[result.id] ?? [],
      judgeReason: getJudgeReason(result),
      errorMessage: result.error_message,
      latencyText: formatLatency(result.latency_ms),
    };
  }),
);
const filteredReportRows = computed(() => {
  if (activeFilter.value === "all") {
    return reportRows.value;
  }
  return reportRows.value.filter((item) => item.status === activeFilter.value);
});
const passedCount = computed(() => runDetail.value?.passed_cases ?? 0);
const failedCount = computed(() => runDetail.value?.failed_cases ?? 0);
const reportTitle = computed(() => `评测报告：${runDetail.value?.run_name?.trim() || "运行报告"}`);
const reportRunName = computed(() => runDetail.value?.run_name?.trim() || (runDetail.value ? `RUN-${runDetail.value.id}` : "暂无运行"));
const reportModelLabel = computed(() => formatModelConfig(runDetail.value?.model_config));
const selectedDataset = computed(() => datasets.value.find((item) => item.id === createForm.datasetId) ?? null);
const estimatedCallCount = computed(() => selectedDatasetCaseCount.value ?? 0);

function formatDateTime(value: string | null) {
  if (!value) {
    return "暂无时间";
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

function formatLatency(value: number | null) {
  if (value === null || value === undefined) {
    return "暂无";
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}s`;
  }
  return `${value}ms`;
}

function formatDuration(startedAt: string | null, finishedAt: string | null, status: EvalRunStatus) {
  if (status === "running") {
    return "运行中";
  }
  if (!startedAt || !finishedAt) {
    return "暂无";
  }
  const started = new Date(startedAt).getTime();
  const finished = new Date(finishedAt).getTime();
  if (Number.isNaN(started) || Number.isNaN(finished) || finished < started) {
    return "暂无";
  }
  const seconds = Math.round((finished - started) / 1000);
  if (seconds < 60) {
    return `${seconds}s`;
  }
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function formatPassRate(run: EvalRunListItem) {
  if (run.total_cases <= 0 || run.status !== "completed") {
    return "暂无";
  }
  return `${Math.round((run.passed_cases / run.total_cases) * 100)}%`;
}

function formatModelConfig(value: Record<string, unknown> | undefined) {
  if (!value) {
    return "暂无模型信息";
  }

  const modelKeys = ["model", "model_name", "chat_model", "judge_model", "judge_model_role"];
  for (const key of modelKeys) {
    const item = value[key];
    if (typeof item === "string" && item.trim()) {
      return item;
    }
  }

  const chain = value.chat_chain;
  if (typeof chain === "string" && chain.trim()) {
    return chain;
  }

  return Object.keys(value).length > 0 ? "已记录模型配置" : "暂无模型信息";
}

function getRunStatusLabel(status: EvalRunStatus | undefined) {
  if (status === "completed") {
    return "已完成";
  }
  if (status === "running") {
    return "运行中";
  }
  if (status === "failed") {
    return "失败";
  }
  if (status === "canceled") {
    return "已取消";
  }
  return "等待中";
}

function getRunStatusType(status: EvalRunStatus | undefined) {
  if (status === "completed") {
    return "success";
  }
  if (status === "running") {
    return "warning";
  }
  if (status === "failed") {
    return "danger";
  }
  if (status === "canceled") {
    return "info";
  }
  return "info";
}

function canResumeRun(status: EvalRunStatus, heartbeatAt: string | null) {
  if (status === "canceled" || status === "failed") {
    return true;
  }
  if (status !== "running" || !heartbeatAt) {
    return status === "running";
  }
  const heartbeatTime = new Date(heartbeatAt).getTime();
  return Number.isNaN(heartbeatTime) || Date.now() - heartbeatTime >= 5 * 60 * 1000;
}

function getCaseStatusLabel(status: EvalCaseResultStatus) {
  if (status === "pending") {
    return "等待执行";
  }
  if (status === "running") {
    return "评测中";
  }
  return status === "passed" ? "评测通过" : "评测失败";
}

function getJudgeReason(result: EvalCaseResult) {
  const reason = result.judge_result.reason;
  return typeof reason === "string" && reason.trim() ? reason : "暂无裁判原因";
}

function getChunkLabel(chunk: { chunk_id: number; chunk_index: number; section_path: string | null }) {
  const section = chunk.section_path?.trim();
  return section || `切片 #${chunk.chunk_index + 1}`;
}

function getEvidenceKey(row: ReportCaseRow, documentId: number) {
  return `${row.id}:${documentId}`;
}

function isEvidenceExpanded(row: ReportCaseRow, documentId: number) {
  return expandedEvidenceKeys.value.has(getEvidenceKey(row, documentId));
}

function toggleEvidence(row: ReportCaseRow, documentId: number) {
  const nextKeys = new Set(expandedEvidenceKeys.value);
  const key = getEvidenceKey(row, documentId);
  if (nextKeys.has(key)) {
    nextKeys.delete(key);
  } else {
    nextKeys.add(key);
  }
  expandedEvidenceKeys.value = nextKeys;
}

function setReportFilter(filter: ReportFilter) {
  if (activeFilter.value === filter) {
    return;
  }
  activeFilter.value = filter;
  reportPagination.page = 1;
  void loadReport();
}

function getTextKey(row: ReportCaseRow, field: "expected" | "actual" | "judge" | "error") {
  return `${row.id}:${field}`;
}

function isTextExpanded(row: ReportCaseRow, field: "expected" | "actual" | "judge" | "error") {
  return expandedTextKeys.value.has(getTextKey(row, field));
}

function shouldShowTextToggle(value: string | null, collapsedLines = 6) {
  if (!value) {
    return false;
  }

  const normalizedValue = value.trim();
  if (!normalizedValue) {
    return false;
  }

  const lineCount = normalizedValue.split(/\r?\n/).length;
  return lineCount > collapsedLines || normalizedValue.length > collapsedLines * 42;
}

function toggleText(row: ReportCaseRow, field: "expected" | "actual" | "judge" | "error") {
  const nextKeys = new Set(expandedTextKeys.value);
  const key = getTextKey(row, field);
  if (nextKeys.has(key)) {
    nextKeys.delete(key);
  } else {
    nextKeys.add(key);
  }
  expandedTextKeys.value = nextKeys;
}

async function loadTaskRuns() {
  const requestSeq = ++taskRequestSeq;
  taskLoading.value = true;
  taskLoadError.value = null;
  try {
    const result = await listEvalRuns({
      keyword: taskKeyword.value,
      status: taskStatusFilter.value === "all" ? undefined : taskStatusFilter.value,
      page: taskPagination.page,
      page_size: taskPagination.pageSize,
    });
    if (requestSeq !== taskRequestSeq) {
      return;
    }
    taskRuns.value = result.items;
    taskPagination.total = result.total;
    taskHasLoadedData.value = true;
  } catch (error) {
    if (requestSeq !== taskRequestSeq) {
      return;
    }
    taskLoadError.value = error;
  } finally {
    if (requestSeq === taskRequestSeq) {
      taskLoading.value = false;
    }
  }
}

async function loadDatasets() {
  datasetLoading.value = true;
  try {
    const result = await listEvalDatasets({
      page: 1,
      page_size: 100,
    });
    datasets.value = result.items;
    if (!createForm.datasetId && result.items.length > 0) {
      createForm.datasetId = result.items[0].id;
    }
    if (createForm.datasetId) {
      await loadSelectedDatasetCaseCount(createForm.datasetId);
    }
  } finally {
    datasetLoading.value = false;
  }
}

async function loadSelectedDatasetCaseCount(datasetId: number) {
  selectedDatasetCaseCount.value = null;
  const result = await listEvalCases(datasetId);
  if (createForm.datasetId === datasetId) {
    selectedDatasetCaseCount.value = result.items.filter((item) => item.enabled).length;
  }
}

async function loadReport() {
  if (!runId.value) {
    return;
  }

  const requestSeq = ++reportRequestSeq;
  reportLoading.value = true;
  reportLoadError.value = null;
  try {
    const detail = await getEvalRunDetail(runId.value, {
      result_page: reportPagination.page,
      result_page_size: reportPagination.pageSize,
      ...(activeFilter.value === "all" ? {} : { result_status: activeFilter.value }),
    });
    if (requestSeq !== reportRequestSeq) {
      return;
    }
    runDetail.value = detail;
    reportPagination.total = detail.result_total;
    expandedTextKeys.value = new Set();
    expandedEvidenceKeys.value = new Set();
    reportHasLoadedData.value = true;
  } catch (error) {
    if (requestSeq !== reportRequestSeq) {
      return;
    }
    reportLoadError.value = error;
  } finally {
    if (requestSeq === reportRequestSeq) {
      reportLoading.value = false;
    }
  }
}

function openCreateDrawer() {
  if (!createForm.runName.trim()) {
    createForm.runName = `评测任务 ${formatDateTime(new Date().toISOString())}`;
  }
  createDrawerVisible.value = true;
  if (datasets.value.length === 0) {
    void loadDatasets();
  }
  if (assistants.value.length === 0) {
    assistantLoading.value = true;
    void listAssistants({ active_only: true, page: 1, page_size: 100 })
      .then((result) => { assistants.value = result.items; })
      .finally(() => { assistantLoading.value = false; });
  }
}

function closeCreateDrawer() {
  if (createSubmitting.value) {
    return;
  }
  createDrawerVisible.value = false;
}

function handleCreateDatasetChange(datasetId: string | number) {
  const normalizedDatasetId = Number(datasetId);
  if (!Number.isInteger(normalizedDatasetId) || normalizedDatasetId <= 0) {
    selectedDatasetCaseCount.value = null;
    return;
  }
  void loadSelectedDatasetCaseCount(normalizedDatasetId);
}

async function submitCreateTask() {
  const runName = createForm.runName.trim();
  if (!runName) {
    ElMessage.warning("请输入任务名称。");
    return;
  }
  if (!createForm.datasetId) {
    ElMessage.warning("请选择关联评测集。");
    return;
  }
  if (!createForm.assistantId) {
    ElMessage.warning("请选择 Assistant。");
    return;
  }

  createSubmitting.value = true;
  try {
    const result = await executeEvalDataset(createForm.datasetId, {
      run_name: runName,
      assistant_id: createForm.assistantId,
    });
    createDrawerVisible.value = false;
    ElMessage.success(`已提交后台运行：共 ${result.total_cases} 条用例。`);
    taskPagination.page = 1;
    await loadTaskRuns();
  } finally {
    createSubmitting.value = false;
  }
}

async function handleResumeRun(targetRunId: number) {
  const nextIds = new Set(resumingRunIds.value);
  nextIds.add(targetRunId);
  resumingRunIds.value = nextIds;
  try {
    await resumeEvalRun(targetRunId);
    ElMessage.success("已重新提交任务，将跳过已完成的用例继续执行。");
    if (runId.value === targetRunId) {
      await loadReport();
    } else {
      await loadTaskRuns();
    }
  } finally {
    const currentIds = new Set(resumingRunIds.value);
    currentIds.delete(targetRunId);
    resumingRunIds.value = currentIds;
  }
}

function isRetrievedEvidenceLoaded(row: ReportCaseRow) {
  return Object.prototype.hasOwnProperty.call(retrievedEvidenceByResultId.value, row.id);
}

async function loadRetrievedEvidence(row: ReportCaseRow) {
  if (!runId.value || isRetrievedEvidenceLoaded(row) || evidenceLoadingResultIds.value.has(row.id)) {
    return;
  }
  const nextLoadingIds = new Set(evidenceLoadingResultIds.value);
  nextLoadingIds.add(row.id);
  evidenceLoadingResultIds.value = nextLoadingIds;
  try {
    const result = await getEvalCaseRetrievedEvidence(runId.value, row.id);
    retrievedEvidenceByResultId.value = {
      ...retrievedEvidenceByResultId.value,
      [row.id]: result.items,
    };
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "检索依据加载失败，请稍后重试。");
  } finally {
    const currentLoadingIds = new Set(evidenceLoadingResultIds.value);
    currentLoadingIds.delete(row.id);
    evidenceLoadingResultIds.value = currentLoadingIds;
  }
}

function handleReportPageChange(page: number) {
  reportPagination.page = page;
  void loadReport();
}

function handleReportPageSizeChange(pageSize: number) {
  reportPagination.pageSize = pageSize;
  reportPagination.page = 1;
  void loadReport();
}

function handleTaskSearch() {
  taskPagination.page = 1;
  void loadTaskRuns();
}

function handleTaskStatusChange() {
  taskPagination.page = 1;
  void loadTaskRuns();
}

function resetTaskFilters() {
  taskKeyword.value = "";
  taskStatusFilter.value = "all";
  taskPagination.page = 1;
  void loadTaskRuns();
}

function handleTaskPageChange(page: number) {
  taskPagination.page = page;
  void loadTaskRuns();
}

function handleTaskPageSizeChange(pageSize: number) {
  taskPagination.pageSize = pageSize;
  taskPagination.page = 1;
  void loadTaskRuns();
}

function openRunReport(row: EvalRunTaskRow) {
  void router.push(`/evaluations/runs/${row.id}`);
}

function backToTaskList() {
  void router.push("/evaluations/reports");
}

function backToDataset() {
  if (runDetail.value?.dataset_id) {
    void router.push(`/evaluations/datasets/${runDetail.value.dataset_id}`);
    return;
  }
  void router.push("/evaluations");
}

function loadCurrentPage() {
  if (isReportDetail.value) {
    void loadReport();
    return;
  }
  void loadTaskRuns();
}

watch(
  () => route.fullPath,
  () => {
    runDetail.value = null;
    reportLoadError.value = null;
    reportHasLoadedData.value = false;
    activeFilter.value = "all";
    reportPagination.page = 1;
    reportPagination.total = 0;
    retrievedEvidenceByResultId.value = {};
    evidenceLoadingResultIds.value = new Set();
    loadCurrentPage();
  },
);

onMounted(() => {
  loadCurrentPage();
});
</script>

<template>
  <div class="evaluation-report-page">
    <AdminListPanel v-if="!isReportDetail">
      <AdminTableToolbar class="evaluation-report-page__task-toolbar">
        <template #left>
          <el-input
            v-model="taskKeyword"
            clearable
            class="evaluation-report-page__task-search"
            placeholder="搜索任务名称或评测集"
            :prefix-icon="Search"
            @keyup.enter="handleTaskSearch"
            @clear="handleTaskSearch"
          />
          <el-select
            v-model="taskStatusFilter"
            class="evaluation-report-page__status-filter"
            @change="handleTaskStatusChange"
          >
            <el-option
              label="全部状态"
              value="all"
            />
            <el-option
              label="等待中"
              value="pending"
            />
            <el-option
              label="运行中"
              value="running"
            />
            <el-option
              label="已完成"
              value="completed"
            />
            <el-option
              label="失败"
              value="failed"
            />
            <el-option
              label="已取消"
              value="canceled"
            />
          </el-select>
          <el-button
            link
            type="primary"
            @click="resetTaskFilters"
          >
            重置
          </el-button>
        </template>
        <template #right>
          <el-button
            type="primary"
            :icon="Plus"
            @click="openCreateDrawer"
          >
            新建评测任务
          </el-button>
          <el-button
            :icon="RefreshRight"
            :loading="taskLoading"
            @click="loadTaskRuns"
          >
            刷新
          </el-button>
        </template>
      </AdminTableToolbar>

      <AppError
        v-if="taskLoadError"
        title="评测任务加载失败"
        description="请检查服务状态或稍后重试。"
        @retry="loadTaskRuns"
      />
      <AppLoading
        v-else-if="taskLoading && !taskHasLoadedData"
        text="正在加载评测任务..."
      />
      <template v-else>
        <AppEmpty
          v-if="taskRows.length === 0"
          title="暂无评测任务"
          description="在评测集详情页运行评测后，任务会出现在这里。"
        />
        <template v-else>
          <AdminDataTable
            :data="taskRows"
            :loading="taskLoading && taskHasLoadedData"
            table-class="evaluation-report-page__task-table"
          >
            <el-table-column
              label="任务名称 / ID"
              min-width="240"
            >
              <template #default="{ row }">
                <div class="evaluation-report-page__task-name">
                  <strong>{{ row.name }}</strong>
                  <span>{{ row.runCode }}</span>
                  <em>
                    <el-icon><Calendar /></el-icon>
                    {{ row.startedAt }}
                  </em>
                </div>
              </template>
            </el-table-column>
            <el-table-column
              label="评测目标"
              min-width="180"
            >
              <template #default="{ row }">
                <div class="evaluation-report-page__icon-text">
                  <span class="evaluation-report-page__icon-box is-blue">
                    <el-icon><Cpu /></el-icon>
                  </span>
                  <strong>{{ row.modelLabel }}</strong>
                </div>
              </template>
            </el-table-column>
            <el-table-column
              label="关联评测集"
              min-width="220"
            >
              <template #default="{ row }">
                <div class="evaluation-report-page__dataset-cell">
                  <div class="evaluation-report-page__icon-text">
                    <span class="evaluation-report-page__icon-box">
                      <el-icon><Files /></el-icon>
                    </span>
                    <strong>{{ row.datasetName }}</strong>
                  </div>
                  <span>{{ row.datasetVersion }} · {{ row.totalCases }} 道用例</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column
              label="运行状态"
              width="150"
            >
              <template #default="{ row }">
                <div class="evaluation-report-page__status-cell">
                  <el-tag
                    :type="getRunStatusType(row.status)"
                    effect="light"
                  >
                    {{ getRunStatusLabel(row.status) }}
                  </el-tag>
                  <span>{{ row.durationText }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column
              label="核心指标"
              width="150"
            >
              <template #default="{ row }">
                <div class="evaluation-report-page__score-cell">
                  <strong>{{ row.averageScore }}<span>分</span></strong>
                  <em>通过率 {{ row.passRateText }}</em>
                </div>
              </template>
            </el-table-column>
            <el-table-column
              label="完成时间"
              width="180"
              prop="finishedAt"
            />
            <el-table-column
              label="操作"
              width="200"
              fixed="right"
            >
              <template #default="{ row }">
                <el-button
                  v-if="canResumeRun(row.status, row.heartbeatAt)"
                  link
                  type="primary"
                  :icon="VideoPlay"
                  :loading="resumingRunIds.has(row.id)"
                  @click="handleResumeRun(row.id)"
                >
                  继续执行
                </el-button>
                <el-button
                  link
                  type="primary"
                  :icon="View"
                  @click="openRunReport(row)"
                >
                  查看报告
                </el-button>
              </template>
            </el-table-column>
          </AdminDataTable>
          <AdminPagination
            :current-page="taskPagination.page"
            :page-size="taskPagination.pageSize"
            :page-sizes="[10, 20, 50]"
            :total="taskPagination.total"
            @page-change="handleTaskPageChange"
            @page-size-change="handleTaskPageSizeChange"
          />
        </template>
      </template>
    </AdminListPanel>

    <AdminListPanel v-else>
      <AdminTableToolbar>
        <template #left>
          <div class="evaluation-report-page__heading">
            <strong>{{ reportTitle }}</strong>
            <div class="evaluation-report-page__meta">
              <span>{{ reportRunName }}</span>
              <span>
                <el-icon><Calendar /></el-icon>
                {{ formatDateTime(runDetail?.started_at ?? null) }}
              </span>
              <span>
                <el-icon><DataAnalysis /></el-icon>
                {{ reportModelLabel }}
              </span>
            </div>
          </div>
        </template>
        <template #right>
          <el-button
            :icon="Back"
            @click="backToTaskList"
          >
            返回任务列表
          </el-button>
          <el-button
            :icon="Document"
            @click="backToDataset"
          >
            返回评测集
          </el-button>
          <el-button
            v-if="runDetail && canResumeRun(runDetail.status, runDetail.heartbeat_at)"
            type="primary"
            :icon="VideoPlay"
            :loading="resumingRunIds.has(runDetail.id)"
            @click="handleResumeRun(runDetail.id)"
          >
            继续执行
          </el-button>
        </template>
      </AdminTableToolbar>

      <AppError
        v-if="reportLoadError"
        title="评测报告加载失败"
        description="请检查该评测任务是否存在，或稍后重试。"
        @retry="loadReport"
      />
      <AppLoading
        v-else-if="reportLoading && !reportHasLoadedData"
        text="正在加载评测报告..."
      />
      <template v-else-if="runDetail">
        <section class="evaluation-report-page__summary">
          <div class="evaluation-report-page__summary-item">
            <span>运行状态</span>
            <strong>
              <el-tag
                :type="getRunStatusType(runDetail.status)"
                effect="light"
              >
                {{ getRunStatusLabel(runDetail.status) }}
              </el-tag>
            </strong>
          </div>
          <div class="evaluation-report-page__summary-item">
            <span>总用例数</span>
            <strong>{{ runDetail.total_cases }}</strong>
          </div>
          <div class="evaluation-report-page__summary-item">
            <span>通过 / 失败</span>
            <strong>{{ runDetail.passed_cases }} / {{ runDetail.failed_cases }}</strong>
          </div>
          <div class="evaluation-report-page__summary-item">
            <span>平均分</span>
            <strong>{{ runDetail.average_score }}</strong>
          </div>
          <div class="evaluation-report-page__summary-item">
            <span>完成时间</span>
            <strong>{{ formatDateTime(runDetail.finished_at) }}</strong>
          </div>
        </section>

        <section class="evaluation-report-page__filters">
          <el-button
            :type="activeFilter === 'all' ? 'primary' : 'default'"
            round
            @click="setReportFilter('all')"
          >
            全部 ({{ runDetail.total_cases }})
          </el-button>
          <el-button
            :type="activeFilter === 'passed' ? 'success' : 'default'"
            round
            @click="setReportFilter('passed')"
          >
            通过 ({{ passedCount }})
          </el-button>
          <el-button
            :type="activeFilter === 'failed' ? 'danger' : 'default'"
            round
            @click="setReportFilter('failed')"
          >
            失败 ({{ failedCount }})
          </el-button>
        </section>

        <AppEmpty
          v-if="filteredReportRows.length === 0"
          title="没有匹配的用例结果"
          description="切换筛选条件后再查看。"
        />
        <section
          v-else
          class="evaluation-report-page__records"
        >
          <article
            v-for="row in filteredReportRows"
            :key="row.id"
            class="evaluation-report-page__record"
            :class="`is-${row.status}`"
          >
            <aside class="evaluation-report-page__score-panel">
              <el-tag
                :type="row.status === 'passed' ? 'success' : 'danger'"
                effect="light"
              >
                {{ getCaseStatusLabel(row.status) }}
              </el-tag>
              <strong>{{ row.score }}<span>分</span></strong>
              <dl>
                <div>
                  <dt>
                    <el-icon><Timer /></el-icon>
                    耗时
                  </dt>
                  <dd>{{ row.latencyText }}</dd>
                </div>
              </dl>
            </aside>

            <main class="evaluation-report-page__answer-panel">
              <div class="evaluation-report-page__question-block">
                <span>Query</span>
                <p>{{ row.question }}</p>
              </div>
              <div class="evaluation-report-page__answer-stack">
                <section class="evaluation-report-page__compare-card is-expected">
                  <h3>期望答案</h3>
                  <p :class="{ 'is-collapsed': shouldShowTextToggle(row.expectedAnswer) && !isTextExpanded(row, 'expected') }">
                    {{ row.expectedAnswer }}
                  </p>
                  <el-button
                    v-if="shouldShowTextToggle(row.expectedAnswer)"
                    link
                    type="primary"
                    class="evaluation-report-page__text-toggle"
                    @click="toggleText(row, 'expected')"
                  >
                    {{ isTextExpanded(row, "expected") ? "收起" : "展开全文" }}
                  </el-button>
                </section>
                <section class="evaluation-report-page__compare-card">
                  <h3>实际回答</h3>
                  <p :class="{ 'is-collapsed': shouldShowTextToggle(row.actualAnswer) && !isTextExpanded(row, 'actual') }">
                    {{ row.actualAnswer }}
                  </p>
                  <el-button
                    v-if="shouldShowTextToggle(row.actualAnswer)"
                    link
                    type="primary"
                    class="evaluation-report-page__text-toggle"
                    @click="toggleText(row, 'actual')"
                  >
                    {{ isTextExpanded(row, "actual") ? "收起" : "展开全文" }}
                  </el-button>
                </section>
              </div>
            </main>

            <aside class="evaluation-report-page__judge-panel">
              <section class="evaluation-report-page__evidence-section">
                <div class="evaluation-report-page__section-title">
                  <h3>
                    <el-icon><Files /></el-icon>
                    检索依据
                  </h3>
                  <span v-if="row.retrievedEvidence.length > 0">
                    命中 {{ row.retrievedEvidence.length }} 个文档
                  </span>
                </div>
                <div
                  v-if="!isRetrievedEvidenceLoaded(row)"
                  class="evaluation-report-page__evidence-miss"
                >
                  <el-button
                    link
                    type="primary"
                    :loading="evidenceLoadingResultIds.has(row.id)"
                    @click="loadRetrievedEvidence(row)"
                  >
                    加载检索依据
                  </el-button>
                </div>
                <div
                  v-else-if="row.retrievedEvidence.length === 0"
                  class="evaluation-report-page__evidence-miss"
                >
                  切片召回为空
                </div>
                <div
                  v-else
                  class="evaluation-report-page__evidence-scroll"
                >
                  <section
                    v-for="documentItem in row.retrievedEvidence"
                    :key="documentItem.document_id"
                    class="evaluation-report-page__evidence-document"
                  >
                    <button
                      type="button"
                      class="evaluation-report-page__evidence-document-button"
                      @click="toggleEvidence(row, documentItem.document_id)"
                    >
                      <strong>
                        <el-icon><Document /></el-icon>
                        《{{ documentItem.document_title }}》
                      </strong>
                      <span>{{ documentItem.chunks.length }} 个切片</span>
                    </button>
                    <div
                      v-if="isEvidenceExpanded(row, documentItem.document_id) && documentItem.chunks.length > 0"
                      class="evaluation-report-page__chunk-list"
                    >
                      <el-tooltip
                        v-for="chunk in documentItem.chunks"
                        :key="chunk.chunk_id"
                        placement="left"
                        effect="dark"
                        popper-class="evaluation-report-page__chunk-tooltip"
                      >
                        <template #content>
                          <div class="evaluation-report-page__tooltip-content">
                            <strong>切片原文预览</strong>
                            <p>{{ chunk.content }}</p>
                          </div>
                        </template>
                        <button
                          type="button"
                          class="evaluation-report-page__chunk-tag"
                        >
                          <el-icon><Files /></el-icon>
                          {{ getChunkLabel(chunk) }}
                        </button>
                      </el-tooltip>
                    </div>
                  </section>
                </div>
              </section>
              <section class="evaluation-report-page__judge-section">
                <h3>裁判原因</h3>
                <p :class="{ 'is-collapsed': shouldShowTextToggle(row.judgeReason) && !isTextExpanded(row, 'judge') }">
                  {{ row.judgeReason }}
                </p>
                <el-button
                  v-if="shouldShowTextToggle(row.judgeReason)"
                  link
                  type="primary"
                  class="evaluation-report-page__text-toggle"
                  @click="toggleText(row, 'judge')"
                >
                  {{ isTextExpanded(row, "judge") ? "收起" : "展开全文" }}
                </el-button>
                <p
                  v-if="row.errorMessage"
                  class="evaluation-report-page__error"
                  :class="{ 'is-collapsed': shouldShowTextToggle(row.errorMessage, 3) && !isTextExpanded(row, 'error') }"
                >
                  {{ row.errorMessage }}
                </p>
                <el-button
                  v-if="shouldShowTextToggle(row.errorMessage, 3)"
                  link
                  type="primary"
                  class="evaluation-report-page__text-toggle"
                  @click="toggleText(row, 'error')"
                >
                  {{ isTextExpanded(row, "error") ? "收起" : "展开全文" }}
                </el-button>
              </section>
            </aside>
          </article>
        </section>
        <AdminPagination
          :current-page="reportPagination.page"
          :page-size="reportPagination.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="reportPagination.total"
          @page-change="handleReportPageChange"
          @page-size-change="handleReportPageSizeChange"
        />
      </template>
    </AdminListPanel>

    <el-drawer
      v-model="createDrawerVisible"
      title="发起评测任务"
      size="680px"
      direction="rtl"
      :close-on-click-modal="!createSubmitting"
      :close-on-press-escape="!createSubmitting"
      custom-class="evaluation-report-page__create-drawer"
      @close="closeCreateDrawer"
    >
      <div class="evaluation-report-page__drawer-body">
        <section class="evaluation-report-page__form-section">
          <div class="evaluation-report-page__form-section-title">
            <span />
            <strong>任务基础信息</strong>
          </div>
          <el-form
            label-position="top"
            @submit.prevent
          >
            <el-form-item
              label="任务名称"
              required
            >
              <el-input
                v-model="createForm.runName"
                maxlength="100"
                show-word-limit
                placeholder="输入本次评测任务名称"
              />
            </el-form-item>
          </el-form>
        </section>

        <section class="evaluation-report-page__form-section">
          <div class="evaluation-report-page__form-section-title">
            <span />
            <strong>配置评测目标</strong>
          </div>
          <el-form
            label-position="top"
            @submit.prevent
          >
            <el-form-item label="目标类型">
              <el-radio-group v-model="createForm.targetType">
                <el-radio-button label="kb_chat">
                  知识库问答链路
                </el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item
              label="关联评测集"
              required
            >
              <el-select
                v-model="createForm.datasetId"
                filterable
                class="evaluation-report-page__drawer-select"
                :loading="datasetLoading"
                placeholder="选择要运行的评测集"
                @change="handleCreateDatasetChange"
              >
                <el-option
                  v-for="item in datasets"
                  :key="item.id"
                  :label="`${item.name} · ${item.version}`"
                  :value="item.id"
                >
                  <div class="evaluation-report-page__dataset-option">
                    <strong>{{ item.name }}</strong>
                    <span>{{ item.version }} · {{ item.status }}</span>
                  </div>
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="Assistant" required>
              <el-select v-model="createForm.assistantId" class="evaluation-report-page__drawer-select" :loading="assistantLoading" placeholder="选择本次评测使用的 Assistant">
                <el-option v-for="item in assistants" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
            <div
              v-if="selectedDataset"
              class="evaluation-report-page__selected-dataset"
            >
              <div>
                <strong>{{ selectedDataset.name }}</strong>
                <span>{{ selectedDataset.description || "暂无评测集说明" }}</span>
              </div>
              <el-tag effect="light">
                {{ selectedDataset.version }}
              </el-tag>
            </div>
          </el-form>
        </section>

      </div>

      <template #footer>
        <div class="evaluation-report-page__drawer-footer">
          <span>
            预计运行 {{ estimatedCallCount }} 条启用用例
          </span>
          <div>
            <el-button @click="closeCreateDrawer">
              取消
            </el-button>
            <el-button
              type="primary"
              :icon="VideoPlay"
              :loading="createSubmitting"
              @click="submitCreateTask"
            >
              开始运行评测
            </el-button>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.evaluation-report-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.evaluation-report-page__heading {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.evaluation-report-page__heading strong {
  color: var(--admin-text-primary);
  font-size: 18px;
  line-height: 1.2;
}

.evaluation-report-page__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.evaluation-report-page__meta span,
.evaluation-report-page__icon-text,
.evaluation-report-page__status-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.evaluation-report-page :deep(.admin-table-toolbar) {
  border-bottom-color: var(--admin-border-soft);
  background: var(--admin-surface);
  padding: 16px 24px;
}

.evaluation-report-page__task-toolbar {
  border-bottom: 1px solid var(--admin-border-soft);
  background: var(--admin-surface-muted) !important;
}

.evaluation-report-page__task-search {
  width: 280px;
}

.evaluation-report-page__status-filter {
  width: 140px;
}

.evaluation-report-page__task-table :deep(.el-table__cell) {
  vertical-align: top;
}

.evaluation-report-page__task-name,
.evaluation-report-page__dataset-cell,
.evaluation-report-page__score-cell,
.evaluation-report-page__status-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;
}

.evaluation-report-page__task-name strong,
.evaluation-report-page__icon-text strong {
  overflow: hidden;
  color: var(--admin-text-primary);
  font-size: 14px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evaluation-report-page__task-name span,
.evaluation-report-page__dataset-cell span,
.evaluation-report-page__status-cell span,
.evaluation-report-page__score-cell em {
  color: var(--admin-text-subtle);
  font-size: 12px;
  font-style: normal;
}

.evaluation-report-page__task-name em {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--admin-text-subtle);
  font-size: 12px;
  font-style: normal;
}

.evaluation-report-page__icon-box {
  display: inline-flex;
  width: 26px;
  height: 26px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-sm);
  background: var(--admin-surface-muted);
  color: var(--admin-text-muted);
}

.evaluation-report-page__icon-box.is-blue {
  border-color: var(--admin-primary-border);
  background: var(--admin-primary-soft);
  color: var(--admin-primary);
}

.evaluation-report-page__score-cell strong {
  color: #16a34a;
  font-size: 22px;
  font-weight: 800;
  line-height: 1;
}

.evaluation-report-page__score-cell strong span {
  margin-left: 3px;
  color: var(--admin-text-subtle);
  font-size: 12px;
  font-weight: 500;
}

.evaluation-report-page__drawer-body {
  display: flex;
  flex-direction: column;
  gap: 28px;
  padding: 4px 4px 24px;
}

.evaluation-report-page__form-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.evaluation-report-page__form-section + .evaluation-report-page__form-section {
  border-top: 1px solid var(--admin-border-soft);
  padding-top: 24px;
}

.evaluation-report-page__form-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.evaluation-report-page__form-section-title span {
  width: 4px;
  height: 14px;
  border-radius: var(--admin-radius-sm);
  background: var(--admin-primary);
}

.evaluation-report-page__form-section-title strong {
  color: var(--admin-text-primary);
  font-size: 14px;
  font-weight: 700;
}

.evaluation-report-page__drawer-select {
  width: 100%;
}

.evaluation-report-page__dataset-option,
.evaluation-report-page__selected-dataset {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.evaluation-report-page__dataset-option strong {
  overflow: hidden;
  color: var(--admin-text-primary);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evaluation-report-page__dataset-option span,
.evaluation-report-page__selected-dataset span {
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.evaluation-report-page__selected-dataset {
  border: 1px solid var(--admin-primary-border);
  border-radius: var(--admin-radius-md);
  background: var(--admin-primary-soft);
  padding: 12px;
}

.evaluation-report-page__selected-dataset div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.evaluation-report-page__selected-dataset strong {
  overflow: hidden;
  color: var(--admin-text-primary);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evaluation-report-page__judge-card {
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-md);
  background: var(--admin-surface-muted);
  padding: 16px;
}

.evaluation-report-page__judge-card p {
  margin: 8px 0 0;
  color: var(--admin-text-muted);
  font-size: 12px;
  line-height: 1.7;
}

.evaluation-report-page__metric-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 14px;
}

.evaluation-report-page__drawer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.evaluation-report-page__drawer-footer span {
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.evaluation-report-page__drawer-footer div {
  display: flex;
  align-items: center;
  gap: 8px;
}

.evaluation-report-page__summary {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0;
  border-bottom: 1px solid var(--admin-border-soft);
  background: var(--admin-surface-muted);
  padding: 20px 24px;
}

.evaluation-report-page__summary-item {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 8px;
  border-right: 1px solid var(--admin-border-soft);
  padding: 0 24px;
}

.evaluation-report-page__summary-item:first-child {
  padding-left: 0;
}

.evaluation-report-page__summary-item:last-child {
  border-right: 0;
  padding-right: 0;
}

.evaluation-report-page__summary-item span {
  color: var(--admin-text-muted);
  font-size: 12px;
}

.evaluation-report-page__summary-item strong {
  display: flex;
  overflow: hidden;
  align-items: center;
  color: var(--admin-text-primary);
  font-size: 18px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evaluation-report-page__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--admin-border-soft);
  background: var(--admin-surface-muted);
  padding: 12px;
}

.evaluation-report-page__records {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.evaluation-report-page__record {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr) minmax(320px, 360px);
  overflow: hidden;
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-lg);
  background: var(--admin-surface);
}

.evaluation-report-page__record.is-failed {
  border-color: #fecaca;
}

.evaluation-report-page__score-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  border-right: 1px solid var(--admin-border-soft);
  background: var(--admin-surface-muted);
  padding: 18px;
}

.evaluation-report-page__record.is-failed .evaluation-report-page__score-panel {
  background: #fff1f2;
}

.evaluation-report-page__score-panel > strong {
  color: #16a34a;
  font-size: 34px;
  font-weight: 800;
  line-height: 1;
}

.evaluation-report-page__record.is-failed .evaluation-report-page__score-panel > strong {
  color: var(--admin-danger);
}

.evaluation-report-page__score-panel > strong span {
  margin-left: 3px;
  color: var(--admin-text-subtle);
  font-size: 13px;
  font-weight: 500;
}

.evaluation-report-page__score-panel dl {
  width: 100%;
  margin: 0;
  border-top: 1px solid var(--admin-border-soft);
  padding-top: 12px;
}

.evaluation-report-page__score-panel dl div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--admin-text-muted);
  font-size: 12px;
}

.evaluation-report-page__score-panel dt,
.evaluation-report-page__score-panel dd {
  margin: 0;
}

.evaluation-report-page__answer-panel {
  min-width: 0;
  padding: 18px;
}

.evaluation-report-page__question-block {
  margin-bottom: 16px;
}

.evaluation-report-page__question-block span {
  display: inline-flex;
  border-radius: var(--admin-radius-sm);
  background: #111827;
  padding: 2px 8px;
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
}

.evaluation-report-page__question-block p {
  margin: 8px 0 0;
  color: var(--admin-text-primary);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.7;
}

.evaluation-report-page__answer-stack,
.evaluation-report-page__judge-panel,
.evaluation-report-page__evidence-scroll,
.evaluation-report-page__chunk-list {
  display: flex;
  flex-direction: column;
}

.evaluation-report-page__answer-stack {
  gap: 12px;
}

.evaluation-report-page__compare-card {
  min-width: 0;
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-md);
  background: var(--admin-surface-muted);
  padding: 14px;
}

.evaluation-report-page__compare-card.is-expected {
  border-color: var(--admin-primary-border);
  background: var(--admin-primary-soft);
}

.evaluation-report-page__compare-card h3,
.evaluation-report-page__judge-panel h3 {
  margin: 0;
  color: var(--admin-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.evaluation-report-page__compare-card p,
.evaluation-report-page__judge-panel p {
  margin: 8px 0 0;
  color: var(--admin-text-secondary);
  font-size: 13px;
  line-height: 1.7;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.evaluation-report-page__compare-card p.is-collapsed,
.evaluation-report-page__judge-panel p.is-collapsed {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 6;
}

.evaluation-report-page__error.is-collapsed {
  -webkit-line-clamp: 3;
}

.evaluation-report-page__text-toggle {
  margin-top: 6px;
  padding: 0;
  font-size: 12px;
}

.evaluation-report-page__judge-panel {
  min-width: 0;
  gap: 18px;
  border-left: 1px solid var(--admin-border-soft);
  background: var(--admin-surface-muted);
  padding: 18px;
}

.evaluation-report-page__section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.evaluation-report-page__section-title h3 {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.evaluation-report-page__section-title span {
  border-radius: var(--admin-radius-sm);
  background: var(--admin-surface);
  padding: 2px 6px;
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.evaluation-report-page__evidence-scroll {
  gap: 10px;
  height: 128px;
  overflow-y: auto;
  padding-right: 4px;
}

.evaluation-report-page__evidence-document {
  flex: 0 0 auto;
  overflow: hidden;
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-sm);
  background: var(--admin-surface);
}

.evaluation-report-page__evidence-document-button {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 0;
  background: var(--admin-surface-muted);
  padding: 8px;
  color: var(--admin-text-primary);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
  text-align: left;
  cursor: pointer;
}

.evaluation-report-page__evidence-document-button:hover {
  background: var(--admin-primary-soft);
}

.evaluation-report-page__evidence-document-button strong,
.evaluation-report-page__evidence-document-button span {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 5px;
}

.evaluation-report-page__evidence-document-button strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evaluation-report-page__evidence-document-button span {
  flex-shrink: 0;
  color: var(--admin-text-subtle);
  font-weight: 500;
}

.evaluation-report-page__chunk-list {
  gap: 8px;
  max-height: 124px;
  overflow-y: auto;
  padding: 8px;
}

.evaluation-report-page__chunk-tag {
  display: inline-flex;
  width: 100%;
  align-items: center;
  gap: 6px;
  overflow: hidden;
  border: 1px solid var(--admin-primary-border);
  border-radius: var(--admin-radius-sm);
  background: var(--admin-primary-soft);
  padding: 6px 8px;
  color: var(--admin-primary);
  font-size: 12px;
  line-height: 1.4;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: help;
}

.evaluation-report-page__evidence-miss {
  border: 1px solid #fed7aa;
  border-radius: var(--admin-radius-sm);
  background: #fff7ed;
  padding: 8px 10px;
  color: #c2410c;
  font-size: 12px;
  font-weight: 600;
}

.evaluation-report-page__tooltip-content {
  max-width: 360px;
}

.evaluation-report-page__tooltip-content strong {
  display: block;
  margin-bottom: 6px;
  color: var(--admin-primary-border);
  font-size: 12px;
}

.evaluation-report-page__tooltip-content p {
  max-height: 220px;
  overflow-y: auto;
  margin: 0;
  color: #ffffff;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.evaluation-report-page__judge-section {
  border-top: 1px solid var(--admin-border-soft);
  padding-top: 16px;
}

.evaluation-report-page__error {
  border: 1px solid #fecaca;
  border-radius: var(--admin-radius-sm);
  background: #fff1f2;
  padding: 8px;
  color: var(--admin-danger) !important;
}

@media (max-width: 1280px) {
  .evaluation-report-page__record {
    grid-template-columns: 148px minmax(0, 1fr);
  }

  .evaluation-report-page__judge-panel {
    grid-column: 1 / -1;
    border-top: 1px solid var(--admin-border-soft);
    border-left: 0;
  }
}

@media (max-width: 900px) {
  .evaluation-report-page__summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .evaluation-report-page__record {
    grid-template-columns: 1fr;
  }

  .evaluation-report-page__score-panel {
    border-right: 0;
    border-bottom: 1px solid var(--admin-border-soft);
  }
}
</style>
