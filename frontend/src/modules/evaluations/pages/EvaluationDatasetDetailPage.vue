<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Close,
  Delete,
  DataAnalysis,
  Document,
  Files,
  FolderOpened,
  Plus,
  RefreshRight,
  Search,
  VideoPlay,
} from "@element-plus/icons-vue";

import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import {
  bulkDeleteEvalCases,
  createEvalCase,
  deleteEvalCase,
  executeEvalDataset,
  getEvalDataset,
  listEvalCases,
  searchEvalChunks,
  updateEvalCase,
} from "@/shared/api/evaluations";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import type {
  EvalCase,
  EvalCasePayload,
  EvalChunkCandidate,
  EvalDataset,
  EvalRetrievedDocumentEvidence,
} from "@/modules/evaluations/types";

interface EvalCaseRow {
  id: number;
  question: string;
  expectedAnswer: string;
  expectedDocIds: number[];
  expectedSnippets: string[];
  expectedChunkIds: number[];
  expectedEvidence: EvalRetrievedDocumentEvidence[];
  enabled: boolean;
  updateTime: string;
}

const route = useRoute();
const router = useRouter();

const dataset = ref<EvalDataset | null>(null);
const cases = ref<EvalCase[]>([]);
const loading = ref(false);
const hasLoadedData = ref(false);
const loadError = ref<unknown>(null);
const dialogVisible = ref(false);
const dialogLoading = ref(false);
const dialogMode = ref<"create" | "edit">("create");
const editingCaseId = ref<number | null>(null);
const runDialogVisible = ref(false);
const runLoading = ref(false);
const runName = ref("");
const chunkDialogVisible = ref(false);
const chunkSearchKeyword = ref("");
const chunkSearchLoading = ref(false);
const chunkCandidates = ref<EvalChunkCandidate[]>([]);
const selectedChunkDetailMap = ref<Map<number, EvalChunkCandidate>>(new Map());
const draftSelectedChunkIds = ref<Set<number>>(new Set());
const caseSearchKeyword = ref("");
const caseStatusFilter = ref<"all" | "enabled" | "disabled">("all");
const selectedCaseIds = ref<Set<number>>(new Set());
const togglingCaseIds = ref<Set<number>>(new Set());
const bulkDeleting = ref(false);
const chunkPagination = reactive({
  offset: 0,
  limit: 30,
  total: 0,
  hasMore: false,
});
let loadRequestSeq = 0;
let chunkLoadRequestSeq = 0;

const form = reactive({
  question: "",
  expectedAnswer: "",
  expectedDocIdsText: "",
  expectedSnippetsText: "",
  expectedChunkIdsText: "",
  enabled: true,
});
const casePagination = reactive({
  page: 1,
  pageSize: 10,
});

const datasetId = computed(() => {
  const raw = Number(route.params.datasetId);
  return Number.isInteger(raw) && raw > 0 ? raw : null;
});
const rows = computed<EvalCaseRow[]>(() =>
  cases.value.map((item) => ({
    id: item.id,
    question: item.question,
    expectedAnswer: item.expected_answer,
    expectedDocIds: item.expected_doc_ids,
    expectedSnippets: item.expected_snippets,
    expectedChunkIds: item.expected_chunk_ids,
    expectedEvidence: item.expected_evidence,
    enabled: item.enabled,
    updateTime: formatDateTime(item.updated_at),
  })),
);
const filteredRows = computed(() => {
  const keyword = caseSearchKeyword.value.trim().toLowerCase();
  return rows.value.filter((item) => {
    const matchesKeyword =
      !keyword ||
      item.question.toLowerCase().includes(keyword) ||
      item.expectedAnswer.toLowerCase().includes(keyword) ||
      item.expectedSnippets.some((snippet) => snippet.toLowerCase().includes(keyword)) ||
      item.expectedEvidence.some(
        (document) =>
          document.document_title.toLowerCase().includes(keyword) ||
          document.chunks.some((chunk) => chunk.content.toLowerCase().includes(keyword)),
      );
    const matchesStatus =
      caseStatusFilter.value === "all" ||
      (caseStatusFilter.value === "enabled" && item.enabled) ||
      (caseStatusFilter.value === "disabled" && !item.enabled);
    return matchesKeyword && matchesStatus;
  });
});
const pagedRows = computed(() => {
  const start = (casePagination.page - 1) * casePagination.pageSize;
  return filteredRows.value.slice(start, start + casePagination.pageSize);
});
const dialogTitle = computed(() => (dialogMode.value === "create" ? "新增评测用例" : "编辑评测用例"));
const dialogActionText = computed(() => (dialogMode.value === "create" ? "新增" : "保存"));
const selectedChunkIds = computed(() => parseNumberList(form.expectedChunkIdsText));
const chunkCandidateById = computed(() => {
  const map = new Map<number, EvalChunkCandidate>();
  for (const item of chunkCandidates.value) {
    map.set(item.chunk_id, item);
  }
  for (const [chunkId, item] of selectedChunkDetailMap.value) {
    map.set(chunkId, item);
  }
  return map;
});
const selectedEvidenceGroups = computed(() => groupChunksByDocument(selectedChunkIds.value));
const draftEvidenceGroups = computed(() => groupChunksByDocument(Array.from(draftSelectedChunkIds.value)));
const chunkCandidateGroups = computed(() => groupChunkCandidatesByDocument(chunkCandidates.value));
const isChunkSearchActive = computed(() => chunkSearchKeyword.value.trim().length > 0);
const selectedCaseCount = computed(() => selectedCaseIds.value.size);

function formatDateTime(value: string | null) {
  if (!value) {
    return "暂无更新";
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

function parseNumberList(value: string) {
  const result: number[] = [];
  const seen = new Set<number>();
  for (const token of value.split(/[\s,，;；]+/)) {
    const item = Number(token.trim());
    if (!Number.isInteger(item) || item <= 0 || seen.has(item)) {
      continue;
    }
    seen.add(item);
    result.push(item);
  }
  return result;
}

function parseTextList(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatNumberList(values: number[]) {
  return values.join(", ");
}

function formatTextList(values: string[]) {
  return values.join("\n");
}

function groupChunksByDocument(chunkIds: number[]) {
  const groups = new Map<
    string,
    {
      key: string;
      documentId: number | null;
      documentTitle: string;
      chunks: Array<{ chunkId: number; content: string; candidate: EvalChunkCandidate | null }>;
    }
  >();

  for (const chunkId of chunkIds) {
    const candidate = chunkCandidateById.value.get(chunkId) ?? null;
    const key = candidate ? String(candidate.document_id) : `unknown:${chunkId}`;
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        documentId: candidate?.document_id ?? null,
        documentTitle: candidate?.document_title ?? "未加载文档信息",
        chunks: [],
      });
    }
    groups.get(key)?.chunks.push({
      chunkId,
      content: candidate?.content ?? `切片 #${chunkId}`,
      candidate,
    });
  }

  return Array.from(groups.values());
}

function groupChunkCandidatesByDocument(candidates: EvalChunkCandidate[]) {
  const groups = new Map<
    number,
    {
      documentId: number;
      documentTitle: string;
      chunks: EvalChunkCandidate[];
    }
  >();

  for (const item of candidates) {
    if (!groups.has(item.document_id)) {
      groups.set(item.document_id, {
        documentId: item.document_id,
        documentTitle: item.document_title,
        chunks: [],
      });
    }
    groups.get(item.document_id)?.chunks.push(item);
  }

  return Array.from(groups.values());
}

function getCaseEvidenceGroups(row: EvalCaseRow) {
  return row.expectedEvidence;
}

function getSnippetPreview(value: string) {
  const normalizedValue = value.trim();
  if (!normalizedValue) {
    return "暂无片段内容";
  }
  return normalizedValue.length > 28 ? `${normalizedValue.slice(0, 28)}...` : normalizedValue;
}

function getCaseEvidenceChunkCount(row: EvalCaseRow) {
  return row.expectedEvidence.reduce((total, document) => total + document.chunks.length, 0);
}

function cacheChunkCandidates(candidates: EvalChunkCandidate[]) {
  if (candidates.length === 0) {
    return;
  }
  const nextMap = new Map(selectedChunkDetailMap.value);
  for (const item of candidates) {
    nextMap.set(item.chunk_id, item);
  }
  selectedChunkDetailMap.value = nextMap;
}

function getChunkPreview(value: string) {
  const normalizedValue = value.trim();
  if (!normalizedValue) {
    return "暂无切片内容";
  }
  return normalizedValue.length > 36 ? `${normalizedValue.slice(0, 36)}...` : normalizedValue;
}

function getDatasetStatusLabel(status: EvalDataset["status"] | undefined) {
  if (status === "active") {
    return "启用";
  }
  if (status === "archived") {
    return "归档";
  }
  return "草稿";
}

function getDatasetStatusType(status: EvalDataset["status"] | undefined) {
  if (status === "active") {
    return "success";
  }
  if (status === "archived") {
    return "info";
  }
  return "warning";
}

function normalizePaginationPage(page: number, pageSize: number, total: number) {
  const maxPage = Math.max(1, Math.ceil(total / pageSize));
  return Math.min(Math.max(1, page), maxPage);
}

function normalizePagination() {
  casePagination.page = normalizePaginationPage(casePagination.page, casePagination.pageSize, filteredRows.value.length);
}

function handleCasePageChange(page: number) {
  casePagination.page = page;
}

function handleCasePageSizeChange(pageSize: number) {
  casePagination.pageSize = pageSize;
  casePagination.page = 1;
}

function buildPayload(): EvalCasePayload | null {
  const question = form.question.trim();
  const expectedAnswer = form.expectedAnswer.trim();
  if (!question) {
    ElMessage.warning("请输入问题。");
    return null;
  }
  if (!expectedAnswer) {
    ElMessage.warning("请输入期望答案。");
    return null;
  }

  return {
    question,
    expected_answer: expectedAnswer,
    expected_doc_ids: parseNumberList(form.expectedDocIdsText),
    expected_snippets: parseTextList(form.expectedSnippetsText),
    expected_chunk_ids: parseNumberList(form.expectedChunkIdsText),
    enabled: form.enabled,
  };
}

async function loadDetail() {
  if (!datasetId.value) {
    loadError.value = new Error("评测集 ID 无效");
    return;
  }

  const requestSeq = ++loadRequestSeq;
  loading.value = true;
  loadError.value = null;
  try {
    const [datasetResult, caseResult] = await Promise.all([
      getEvalDataset(datasetId.value),
      listEvalCases(datasetId.value),
    ]);
    if (requestSeq !== loadRequestSeq) {
      return;
    }
    dataset.value = datasetResult;
    cases.value = caseResult.items;
    selectedCaseIds.value = new Set();
    normalizePagination();
    hasLoadedData.value = true;
  } catch (error) {
    if (requestSeq !== loadRequestSeq) {
      return;
    }
    if (hasLoadedData.value) {
      ElMessage.error(error instanceof Error ? error.message : "评测集详情刷新失败，请稍后重试。");
    } else {
      loadError.value = error;
    }
  } finally {
    if (requestSeq === loadRequestSeq) {
      loading.value = false;
    }
  }
}

function resetForm() {
  form.question = "";
  form.expectedAnswer = "";
  form.expectedDocIdsText = "";
  form.expectedSnippetsText = "";
  form.expectedChunkIdsText = "";
  form.enabled = true;
  editingCaseId.value = null;
}

function openCreateDialog() {
  dialogMode.value = "create";
  resetForm();
  dialogVisible.value = true;
}

function openEditDialog(row: EvalCaseRow) {
  dialogMode.value = "edit";
  editingCaseId.value = row.id;
  form.question = row.question;
  form.expectedAnswer = row.expectedAnswer;
  form.expectedDocIdsText = formatNumberList(row.expectedDocIds);
  form.expectedSnippetsText = formatTextList(row.expectedSnippets);
  form.expectedChunkIdsText = formatNumberList(row.expectedChunkIds);
  form.enabled = row.enabled;
  dialogVisible.value = true;
}

async function submitCaseForm() {
  if (!datasetId.value) {
    return;
  }
  const payload = buildPayload();
  if (!payload) {
    return;
  }

  dialogLoading.value = true;
  try {
    if (dialogMode.value === "create") {
      await createEvalCase(datasetId.value, payload);
      ElMessage.success("已新增评测用例。");
    } else if (editingCaseId.value) {
      await updateEvalCase(datasetId.value, editingCaseId.value, payload);
      ElMessage.success("已保存评测用例。");
    }
    dialogVisible.value = false;
    await loadDetail();
  } finally {
    dialogLoading.value = false;
  }
}

async function handleDeleteCase(row: EvalCaseRow) {
  if (!datasetId.value) {
    return;
  }
  try {
    await ElMessageBox.confirm("删除后该用例不会再参与评测运行。", "删除评测用例", {
      type: "warning",
      confirmButtonText: "删除用例",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }

  await deleteEvalCase(datasetId.value, row.id);
  ElMessage.success("已删除评测用例。");
  await loadDetail();
}

function handleCaseSelectionChange(selection: EvalCaseRow[]) {
  selectedCaseIds.value = new Set(selection.map((item) => item.id));
}

async function handleBulkDeleteCases() {
  if (!datasetId.value || selectedCaseIds.value.size === 0) {
    return;
  }

  const selectedRows = rows.value.filter((item) => selectedCaseIds.value.has(item.id));
  try {
    await ElMessageBox.confirm(`将删除已选的 ${selectedRows.length} 条评测用例，删除后不会再参与评测运行。`, "批量删除用例", {
      type: "warning",
      confirmButtonText: "删除所选",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }

  bulkDeleting.value = true;
  try {
    await bulkDeleteEvalCases(
      datasetId.value,
      selectedRows.map((item) => item.id),
    );
    selectedCaseIds.value = new Set();
    ElMessage.success(`已删除 ${selectedRows.length} 条评测用例。`);
    await loadDetail();
  } finally {
    bulkDeleting.value = false;
  }
}

async function handleToggleCaseEnabled(row: EvalCaseRow, enabled: boolean | string | number) {
  if (!datasetId.value) {
    return;
  }
  const nextEnabled = Boolean(enabled);
  const nextTogglingIds = new Set(togglingCaseIds.value);
  nextTogglingIds.add(row.id);
  togglingCaseIds.value = nextTogglingIds;
  try {
    await updateEvalCase(datasetId.value, row.id, {
      question: row.question,
      expected_answer: row.expectedAnswer,
      expected_doc_ids: row.expectedDocIds,
      expected_snippets: row.expectedSnippets,
      expected_chunk_ids: row.expectedChunkIds,
      enabled: nextEnabled,
    });
    const targetCase = cases.value.find((item) => item.id === row.id);
    if (targetCase) {
      targetCase.enabled = nextEnabled;
      targetCase.updated_at = new Date().toISOString();
    }
    ElMessage.success(nextEnabled ? "已启用该用例。" : "已停用该用例。");
  } finally {
    const nextIds = new Set(togglingCaseIds.value);
    nextIds.delete(row.id);
    togglingCaseIds.value = nextIds;
  }
}

function openRunDialog() {
  if (rows.value.length === 0) {
    ElMessage.warning("请先新增评测用例。");
    return;
  }
  if (!rows.value.some((item) => item.enabled)) {
    ElMessage.warning("请至少启用一条评测用例。");
    return;
  }
  runName.value = `${dataset.value?.name ?? "评测集"} ${formatDateTime(new Date().toISOString())}`;
  runDialogVisible.value = true;
}

async function submitRunEvaluation() {
  if (!datasetId.value) {
    return;
  }
  runLoading.value = true;
  try {
    const result = await executeEvalDataset(datasetId.value, {
      run_name: runName.value.trim() || null,
    });
    runDialogVisible.value = false;
    ElMessage.success(`已提交后台运行：共 ${result.total_cases} 条用例。`);
    void router.push("/evaluations/reports");
  } finally {
    runLoading.value = false;
  }
}

function openReportsPage() {
  void router.push("/evaluations/reports");
}

async function openChunkDialog() {
  draftSelectedChunkIds.value = new Set(selectedChunkIds.value);
  chunkDialogVisible.value = true;
  if (chunkCandidates.value.length === 0) {
    await resetChunkCandidates();
  }
}

async function resetChunkCandidates() {
  chunkPagination.offset = 0;
  chunkPagination.total = 0;
  chunkPagination.hasMore = false;
  chunkCandidates.value = [];
  await loadChunkCandidates({ append: false });
}

async function loadChunkCandidates({ append = false } = {}) {
  if (!datasetId.value) {
    return;
  }
  if (chunkSearchLoading.value) {
    return;
  }
  if (append && !chunkPagination.hasMore) {
    return;
  }
  const requestSeq = ++chunkLoadRequestSeq;
  chunkSearchLoading.value = true;
  try {
    const result = await searchEvalChunks(datasetId.value, {
      query: chunkSearchKeyword.value,
      offset: append ? chunkPagination.offset : 0,
      limit: chunkPagination.limit,
    });
    if (requestSeq !== chunkLoadRequestSeq) {
      return;
    }
    cacheChunkCandidates(result.items);
    const existingIds = new Set(append ? chunkCandidates.value.map((item) => item.chunk_id) : []);
    const nextItems = append
      ? [
          ...chunkCandidates.value,
          ...result.items.filter((item) => !existingIds.has(item.chunk_id)),
        ]
      : result.items;
    chunkCandidates.value = nextItems;
    chunkPagination.offset = result.offset + result.items.length;
    chunkPagination.total = result.total;
    chunkPagination.hasMore = result.has_more;
  } finally {
    if (requestSeq === chunkLoadRequestSeq) {
      chunkSearchLoading.value = false;
    }
  }
}

function handleChunkListScroll(event: Event) {
  const target = event.currentTarget;
  if (!(target instanceof HTMLElement)) {
    return;
  }
  const distanceToBottom = target.scrollHeight - target.scrollTop - target.clientHeight;
  if (distanceToBottom <= 80) {
    void loadChunkCandidates({ append: true });
  }
}

function toggleDraftChunkSelection(chunk: EvalChunkCandidate) {
  cacheChunkCandidates([chunk]);
  const current = new Set(draftSelectedChunkIds.value);
  if (current.has(chunk.chunk_id)) {
    current.delete(chunk.chunk_id);
  } else {
    current.add(chunk.chunk_id);
  }
  draftSelectedChunkIds.value = current;
}

function syncExpectedEvidenceFromChunkIds(chunkIds: number[]) {
  const chunkIdSet = new Set(chunkIds);
  const documentIds = new Set<number>();
  for (const item of selectedChunkDetailMap.value.values()) {
    if (chunkIdSet.has(item.chunk_id)) {
      documentIds.add(item.document_id);
    }
  }
  form.expectedChunkIdsText = Array.from(chunkIdSet).sort((a, b) => a - b).join(", ");
  form.expectedDocIdsText = Array.from(documentIds).sort((a, b) => a - b).join(", ");
}

function removeSelectedChunk(chunkId: number) {
  const nextIds = selectedChunkIds.value.filter((item) => item !== chunkId);
  syncExpectedEvidenceFromChunkIds(nextIds);
}

function removeSelectedDocument(groupKey: string) {
  const group = selectedEvidenceGroups.value.find((item) => item.key === groupKey);
  if (!group) {
    return;
  }
  const removingIds = new Set(group.chunks.map((item) => item.chunkId));
  syncExpectedEvidenceFromChunkIds(selectedChunkIds.value.filter((item) => !removingIds.has(item)));
}

function removeDraftChunk(chunkId: number) {
  const nextIds = new Set(draftSelectedChunkIds.value);
  nextIds.delete(chunkId);
  draftSelectedChunkIds.value = nextIds;
}

function clearDraftSelection() {
  draftSelectedChunkIds.value = new Set();
}

function confirmChunkSelection() {
  syncExpectedEvidenceFromChunkIds(Array.from(draftSelectedChunkIds.value));
  chunkDialogVisible.value = false;
}

onMounted(() => {
  void loadDetail();
});

watch(
  () => route.params.datasetId,
  () => {
    void loadDetail();
  },
);

watch([caseSearchKeyword, caseStatusFilter, filteredRows], () => {
  casePagination.page = normalizePaginationPage(casePagination.page, casePagination.pageSize, filteredRows.value.length);
});
</script>

<template>
  <div class="evaluation-dataset-detail-page">
    <AdminListPanel>
      <AdminTableToolbar>
        <template #left>
          <span class="evaluation-dataset-detail-page__dataset-name">
            {{ dataset?.name ?? "评测集详情" }}
          </span>
          <el-tag effect="light">
            {{ dataset?.version ?? "暂无版本" }}
          </el-tag>
          <el-tag
            :type="getDatasetStatusType(dataset?.status)"
            effect="light"
          >
            {{ getDatasetStatusLabel(dataset?.status) }}
          </el-tag>
          <el-button
            :loading="loading"
            :icon="RefreshRight"
            @click="loadDetail"
          >
            刷新
          </el-button>
        </template>
        <template #right>
          <el-button
            :icon="DataAnalysis"
            @click="openReportsPage"
          >
            评测任务/报告
          </el-button>
          <el-button
            :icon="VideoPlay"
            :loading="runLoading"
            @click="openRunDialog"
          >
            运行评测
          </el-button>
          <el-button
            type="primary"
            :icon="Plus"
            @click="openCreateDialog"
          >
            新增用例
          </el-button>
        </template>
      </AdminTableToolbar>

      <AppError
        v-if="loadError"
        title="评测集详情加载失败"
        description="请检查服务状态或稍后重试。"
        @retry="loadDetail"
      />
      <AppLoading
        v-else-if="loading && !hasLoadedData"
        text="正在加载评测集详情..."
      />
      <template v-else>
        <AppEmpty
          v-if="!loading && rows.length === 0"
          title="还没有评测用例"
          description="新增问题和期望答案后，就可以沉淀评测数据。"
        >
          <template #actions>
            <el-button
              type="primary"
              :icon="Plus"
              @click="openCreateDialog"
            >
              新增用例
            </el-button>
          </template>
        </AppEmpty>

        <template v-else>
          <AdminTableToolbar class="evaluation-dataset-detail-page__case-toolbar">
            <template #left>
              <el-input
                v-model="caseSearchKeyword"
                clearable
                class="evaluation-dataset-detail-page__case-search"
                placeholder="搜索问题、答案或依据"
                :prefix-icon="Search"
              />
              <el-select
                v-model="caseStatusFilter"
                class="evaluation-dataset-detail-page__status-filter"
              >
                <el-option
                  label="全部状态"
                  value="all"
                />
                <el-option
                  label="仅启用"
                  value="enabled"
                />
                <el-option
                  label="仅停用"
                  value="disabled"
                />
              </el-select>
              <span class="evaluation-dataset-detail-page__toolbar-note">
                已筛选 {{ filteredRows.length }} / {{ rows.length }} 条
              </span>
            </template>
            <template #right>
              <el-button
                type="danger"
                plain
                :icon="Delete"
                :disabled="selectedCaseCount === 0"
                :loading="bulkDeleting"
                @click="handleBulkDeleteCases"
              >
                批量删除{{ selectedCaseCount ? ` (${selectedCaseCount})` : "" }}
              </el-button>
            </template>
          </AdminTableToolbar>

          <el-table
            :data="pagedRows"
            class="evaluation-dataset-detail-page__table"
            row-key="id"
            @selection-change="handleCaseSelectionChange"
          >
            <el-table-column
              type="selection"
              width="46"
              reserve-selection
            />
            <el-table-column
              label="问题"
              min-width="360"
            >
              <template #default="{ row }">
                <div class="evaluation-dataset-detail-page__qa-cell">
                  <div class="evaluation-dataset-detail-page__qa-turn">
                    <span class="evaluation-dataset-detail-page__qa-badge is-question">Q</span>
                    <strong class="evaluation-dataset-detail-page__question">{{ row.question }}</strong>
                  </div>
                  <div class="evaluation-dataset-detail-page__qa-turn is-answer">
                    <span class="evaluation-dataset-detail-page__qa-badge is-answer">A</span>
                    <p class="evaluation-dataset-detail-page__answer">
                      {{ row.expectedAnswer }}
                    </p>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column
              label="期望依据"
              min-width="300"
            >
              <template #default="{ row }">
                <div class="evaluation-dataset-detail-page__case-evidence">
                  <div
                    v-if="getCaseEvidenceGroups(row).length === 0 && row.expectedSnippets.length === 0"
                    class="evaluation-dataset-detail-page__evidence-empty"
                  >
                    暂无依据
                  </div>
                  <template v-else>
                    <el-tooltip
                      v-for="document in getCaseEvidenceGroups(row)"
                      :key="document.document_id"
                      placement="top-start"
                      effect="light"
                      popper-class="evaluation-dataset-detail-page__evidence-tooltip"
                    >
                      <template #content>
                        <div class="evaluation-dataset-detail-page__evidence-tooltip-content">
                          <strong>{{ document.document_title }}</strong>
                          <p
                            v-for="chunk in document.chunks"
                            :key="chunk.chunk_id"
                          >
                            {{ chunk.content }}
                          </p>
                        </div>
                      </template>
                      <span class="evaluation-dataset-detail-page__document-chip">
                        <el-icon><Document /></el-icon>
                        {{ document.document_title }}
                        <em>{{ document.chunks.length }} 个切片</em>
                      </span>
                    </el-tooltip>
                    <el-tooltip
                      v-for="snippet in row.expectedSnippets"
                      :key="snippet"
                      placement="top-start"
                      effect="light"
                      :content="snippet"
                    >
                      <span class="evaluation-dataset-detail-page__snippet-chip">
                        片段 {{ getSnippetPreview(snippet) }}
                      </span>
                    </el-tooltip>
                    <span
                      v-if="getCaseEvidenceChunkCount(row) === 0 && row.expectedChunkIds.length > 0"
                      class="evaluation-dataset-detail-page__evidence-missing"
                    >
                      {{ row.expectedChunkIds.length }} 个切片未匹配到文档
                    </span>
                  </template>
                </div>
              </template>
            </el-table-column>
            <el-table-column
              label="状态"
              width="120"
            >
              <template #default="{ row }">
                <el-switch
                  :model-value="row.enabled"
                  :loading="togglingCaseIds.has(row.id)"
                  active-text="启用"
                  inactive-text="停用"
                  inline-prompt
                  @change="(value) => handleToggleCaseEnabled(row, value)"
                />
              </template>
            </el-table-column>
            <el-table-column
              label="更新时间"
              prop="updateTime"
              width="180"
            />
            <el-table-column
              label="操作"
              width="150"
              fixed="right"
            >
              <template #default="{ row }">
                <el-button
                  link
                  type="primary"
                  @click="openEditDialog(row)"
                >
                  编辑
                </el-button>
                <el-button
                  link
                  type="danger"
                  @click="handleDeleteCase(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="evaluation-dataset-detail-page__pagination">
            <el-pagination
              background
              layout="total, sizes, prev, pager, next"
              :current-page="casePagination.page"
              :page-size="casePagination.pageSize"
              :page-sizes="[10, 20, 50]"
              :total="filteredRows.length"
              @current-change="handleCasePageChange"
              @size-change="handleCasePageSizeChange"
            />
          </div>
        </template>
      </template>
    </AdminListPanel>

    <el-drawer
      v-model="dialogVisible"
      :title="dialogTitle"
      size="640px"
      direction="rtl"
      :close-on-click-modal="!dialogLoading"
      :close-on-press-escape="!dialogLoading"
      custom-class="evaluation-dataset-detail-page__case-drawer"
    >
      <div class="evaluation-dataset-detail-page__case-drawer-body">
        <el-form
          label-position="top"
          @submit.prevent
        >
          <section class="evaluation-dataset-detail-page__form-section">
            <div class="evaluation-dataset-detail-page__form-section-title">
              <span />
              <strong>基础问答内容</strong>
            </div>
            <el-form-item
              label="问题 (Query)"
              required
            >
              <el-input
                v-model="form.question"
                type="textarea"
                :rows="3"
                maxlength="1000"
                show-word-limit
                placeholder="请输入用户提问内容，尽量覆盖真实的业务场景语境..."
              />
            </el-form-item>
            <el-form-item
              label="期望答案 (Expected Answer)"
              required
            >
              <el-input
                v-model="form.expectedAnswer"
                type="textarea"
                :rows="5"
                maxlength="4000"
                show-word-limit
                placeholder="请输入系统应该回答的标准内容，大模型将以此为基准进行对比评分..."
              />
            </el-form-item>
          </section>

          <section class="evaluation-dataset-detail-page__form-section">
            <div class="evaluation-dataset-detail-page__form-section-title">
              <span />
              <strong>检索预期 (RAG 归因配置)</strong>
              <em>用于评测系统的检索召回能力</em>
            </div>
            <div class="evaluation-dataset-detail-page__evidence-selector-head">
              <label>期望命中的依据 (文档/切片)</label>
              <el-button
                type="primary"
                plain
                :icon="FolderOpened"
                @click="openChunkDialog"
              >
                选择知识库依据
              </el-button>
            </div>
            <div class="evaluation-dataset-detail-page__selected-evidence-box">
              <div
                v-if="selectedEvidenceGroups.length === 0"
                class="evaluation-dataset-detail-page__selected-empty"
              >
                暂未关联任何文档或切片，点击上方按钮选择
              </div>
              <template v-else>
                <article
                  v-for="group in selectedEvidenceGroups"
                  :key="group.key"
                  class="evaluation-dataset-detail-page__selected-document"
                >
                  <div class="evaluation-dataset-detail-page__selected-document-title">
                    <el-icon><Document /></el-icon>
                    <strong>{{ group.documentTitle }}</strong>
                    <el-button
                      link
                      type="danger"
                      :icon="Delete"
                      @click="removeSelectedDocument(group.key)"
                    />
                  </div>
                  <div class="evaluation-dataset-detail-page__selected-chunks">
                    <el-tag
                      v-for="chunk in group.chunks"
                      :key="chunk.chunkId"
                      closable
                      type="primary"
                      effect="light"
                      @close="removeSelectedChunk(chunk.chunkId)"
                    >
                      [切片] {{ getChunkPreview(chunk.content) }}
                    </el-tag>
                  </div>
                </article>
              </template>
            </div>
            <el-form-item label="期望关键片段 (Keyword/Snippet)">
              <el-input
                v-model="form.expectedSnippetsText"
                type="textarea"
                :rows="3"
                placeholder="每行一个期望命中的关键片段"
              />
            </el-form-item>
          </section>

          <section class="evaluation-dataset-detail-page__form-section">
            <div class="evaluation-dataset-detail-page__form-section-title">
              <span />
              <strong>用例设置</strong>
            </div>
            <el-form-item label="启用状态">
              <el-switch
                v-model="form.enabled"
                active-text="参与评测"
                inactive-text="暂不参与"
              />
            </el-form-item>
          </section>
        </el-form>
      </div>
      <template #footer>
        <el-button
          :disabled="dialogLoading"
          @click="dialogVisible = false"
        >
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="dialogLoading"
          @click="submitCaseForm"
        >
          确定{{ dialogActionText }}
        </el-button>
      </template>
    </el-drawer>

    <el-dialog
      v-model="runDialogVisible"
      title="运行评测"
      width="520px"
      :close-on-click-modal="!runLoading"
      :close-on-press-escape="!runLoading"
    >
      <el-alert
        class="evaluation-dataset-detail-page__run-alert"
        title="当前会同步执行所有已启用用例，运行期间请不要重复提交。"
        type="info"
        show-icon
        :closable="false"
      />
      <el-form
        label-position="top"
        @submit.prevent
      >
        <el-form-item label="运行名称">
          <el-input
            v-model="runName"
            maxlength="100"
            show-word-limit
            placeholder="例如：回归验证 2026-06-09"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button
          :disabled="runLoading"
          @click="runDialogVisible = false"
        >
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="runLoading"
          @click="submitRunEvaluation"
        >
          开始运行
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="chunkDialogVisible"
      title="选择知识库依据"
      width="860px"
      class="evaluation-dataset-detail-page__chunk-dialog"
    >
      <div class="evaluation-dataset-detail-page__chunk-picker">
        <section class="evaluation-dataset-detail-page__chunk-picker-left">
          <div class="evaluation-dataset-detail-page__chunk-search-row">
            <el-input
              v-model="chunkSearchKeyword"
              clearable
              class="evaluation-dataset-detail-page__chunk-search"
              placeholder="搜索文档标题或切片内容"
              :prefix-icon="Search"
              @keyup.enter="resetChunkCandidates"
              @clear="resetChunkCandidates"
            />
            <el-button
              :loading="chunkSearchLoading"
              @click="resetChunkCandidates"
            >
              搜索
            </el-button>
          </div>
          <div
            v-loading="chunkSearchLoading"
            class="evaluation-dataset-detail-page__chunk-group-list"
            @scroll="handleChunkListScroll"
          >
            <div
              v-if="chunkCandidateGroups.length === 0 && !chunkSearchLoading"
              class="evaluation-dataset-detail-page__chunk-empty"
            >
              {{ isChunkSearchActive ? "没有匹配的切片" : "暂无可选切片" }}
            </div>
            <template v-else>
              <article
                v-for="group in chunkCandidateGroups"
                :key="group.documentId"
                class="evaluation-dataset-detail-page__candidate-document"
              >
                <header class="evaluation-dataset-detail-page__candidate-document-head">
                  <div>
                    <el-icon><Document /></el-icon>
                    <strong>{{ group.documentTitle }}</strong>
                  </div>
                  <span>{{ group.chunks.length }} 个{{ isChunkSearchActive ? "匹配" : "切片" }}</span>
                </header>
                <label
                  v-for="chunk in group.chunks"
                  :key="chunk.chunk_id"
                  class="evaluation-dataset-detail-page__candidate-chunk"
                  :class="{ 'is-selected': draftSelectedChunkIds.has(chunk.chunk_id) }"
                >
                  <el-checkbox
                    :model-value="draftSelectedChunkIds.has(chunk.chunk_id)"
                    @change="toggleDraftChunkSelection(chunk)"
                  />
                  <el-icon><Files /></el-icon>
                  <span>{{ chunk.content }}</span>
                </label>
              </article>
            </template>
            <div
              v-if="chunkCandidates.length > 0"
              class="evaluation-dataset-detail-page__chunk-load-state"
            >
              <span v-if="chunkSearchLoading">正在加载更多切片...</span>
              <span v-else-if="chunkPagination.hasMore">向下滚动加载更多</span>
              <span v-else>已加载全部 {{ chunkPagination.total }} 个切片</span>
            </div>
          </div>
        </section>
        <section class="evaluation-dataset-detail-page__chunk-picker-right">
          <div class="evaluation-dataset-detail-page__selected-panel-head">
            <strong>已选切片 <span>({{ draftSelectedChunkIds.size }})</span></strong>
            <el-button
              link
              type="primary"
              @click="clearDraftSelection"
            >
              清空
            </el-button>
          </div>
          <div class="evaluation-dataset-detail-page__draft-selected-list">
            <div
              v-if="draftSelectedChunkIds.size === 0"
              class="evaluation-dataset-detail-page__draft-empty"
            >
              <el-icon><Files /></el-icon>
              <span>暂未选择任何切片</span>
            </div>
            <template v-else>
              <article
                v-for="group in draftEvidenceGroups"
                :key="group.key"
                class="evaluation-dataset-detail-page__draft-document"
              >
                <strong>
                  <el-icon><Document /></el-icon>
                  {{ group.documentTitle }}
                </strong>
                <div
                  v-for="chunk in group.chunks"
                  :key="chunk.chunkId"
                  class="evaluation-dataset-detail-page__draft-chunk"
                >
                  <p>[切片] {{ getChunkPreview(chunk.content) }}</p>
                  <el-button
                    link
                    type="danger"
                    :icon="Close"
                    @click="removeDraftChunk(chunk.chunkId)"
                  />
                </div>
              </article>
            </template>
          </div>
        </section>
      </div>
      <template #footer>
        <el-button @click="chunkDialogVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          @click="confirmChunkSelection"
        >
          确认选择
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.evaluation-dataset-detail-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.evaluation-dataset-detail-page__evidence,
.evaluation-dataset-detail-page__inline-field {
  display: flex;
  align-items: center;
  gap: 8px;
}

.evaluation-dataset-detail-page__dataset-name {
  color: var(--admin-text-primary);
  font-size: 13px;
  font-weight: 700;
}

.evaluation-dataset-detail-page__toolbar-note {
  color: var(--admin-text-subtle);
  font-size: 13px;
}

.evaluation-dataset-detail-page__case-toolbar {
  border-top: 1px solid var(--admin-border-soft);
}

.evaluation-dataset-detail-page__case-search {
  width: 260px;
}

.evaluation-dataset-detail-page__status-filter {
  width: 120px;
}

.evaluation-dataset-detail-page__table :deep(.el-table__cell) {
  vertical-align: top;
}

.evaluation-dataset-detail-page__qa-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 8px;
}

.evaluation-dataset-detail-page__qa-turn {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 8px;
}

.evaluation-dataset-detail-page__qa-turn.is-answer {
  border-radius: var(--admin-radius-sm);
  background: #f4f8ff;
  padding: 8px;
}

.evaluation-dataset-detail-page__qa-badge {
  display: inline-flex;
  width: 20px;
  height: 20px;
  flex: 0 0 20px;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
}

.evaluation-dataset-detail-page__qa-badge.is-question {
  background: #111827;
  color: #fff;
}

.evaluation-dataset-detail-page__qa-badge.is-answer {
  background: #2563eb;
  color: #fff;
}

.evaluation-dataset-detail-page__question,
.evaluation-dataset-detail-page__chunk-title {
  display: -webkit-box;
  flex: 1;
  overflow: hidden;
  color: var(--admin-text-primary);
  font-size: 13px;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.evaluation-dataset-detail-page__answer,
.evaluation-dataset-detail-page__chunk-content {
  flex: 1;
  margin: 0;
  display: -webkit-box;
  overflow: hidden;
  color: var(--admin-text-secondary);
  font-size: 12px;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.evaluation-dataset-detail-page__evidence,
.evaluation-dataset-detail-page__case-evidence {
  flex-wrap: wrap;
}

.evaluation-dataset-detail-page__case-evidence {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 6px;
}

.evaluation-dataset-detail-page__evidence span {
  border: 1px solid var(--admin-border-soft);
  border-radius: 999px;
  padding: 2px 8px;
  color: var(--admin-text-secondary);
  font-size: 12px;
}

.evaluation-dataset-detail-page__document-chip,
.evaluation-dataset-detail-page__snippet-chip,
.evaluation-dataset-detail-page__evidence-missing {
  display: inline-flex;
  min-width: 0;
  max-width: 100%;
  align-items: center;
  gap: 5px;
  border: 1px solid var(--admin-border-soft);
  border-radius: 999px;
  padding: 4px 8px;
  color: var(--admin-text-secondary);
  font-size: 12px;
  line-height: 1.3;
}

.evaluation-dataset-detail-page__document-chip {
  background: var(--admin-surface);
  color: var(--admin-text-primary);
  cursor: default;
}

.evaluation-dataset-detail-page__document-chip .el-icon {
  flex: 0 0 auto;
  color: var(--admin-primary);
}

.evaluation-dataset-detail-page__document-chip em {
  flex: 0 0 auto;
  color: var(--admin-text-subtle);
  font-style: normal;
}

.evaluation-dataset-detail-page__snippet-chip {
  background: #f8fafc;
  cursor: default;
}

.evaluation-dataset-detail-page__evidence-missing {
  border-color: #facc15;
  background: #fefce8;
  color: #854d0e;
}

.evaluation-dataset-detail-page__evidence-empty {
  color: var(--admin-text-subtle);
  font-size: 12px;
}

:global(.evaluation-dataset-detail-page__evidence-tooltip) {
  max-width: 420px;
}

:global(.evaluation-dataset-detail-page__evidence-tooltip-content) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

:global(.evaluation-dataset-detail-page__evidence-tooltip-content strong) {
  color: var(--admin-text-primary);
  font-size: 13px;
}

:global(.evaluation-dataset-detail-page__evidence-tooltip-content p) {
  margin: 0;
  color: var(--admin-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.evaluation-dataset-detail-page__form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.evaluation-dataset-detail-page :deep(.evaluation-dataset-detail-page__case-drawer) {
  display: flex;
  flex-direction: column;
}

.evaluation-dataset-detail-page :deep(.evaluation-dataset-detail-page__case-drawer .el-drawer__body) {
  flex: 1;
  overflow: hidden;
  padding: 0;
}

.evaluation-dataset-detail-page :deep(.evaluation-dataset-detail-page__case-drawer .el-drawer__footer) {
  border-top: 1px solid var(--admin-border-soft);
  background: var(--admin-surface-muted);
  padding: 14px 24px;
}

.evaluation-dataset-detail-page__case-drawer-body {
  height: 100%;
  overflow-y: auto;
  padding: 24px;
}

.evaluation-dataset-detail-page__form-section {
  border-bottom: 1px solid var(--admin-border-soft);
  padding: 0 0 22px;
}

.evaluation-dataset-detail-page__form-section + .evaluation-dataset-detail-page__form-section {
  padding-top: 22px;
}

.evaluation-dataset-detail-page__form-section:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.evaluation-dataset-detail-page__form-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.evaluation-dataset-detail-page__form-section-title > span {
  width: 4px;
  height: 14px;
  border-radius: var(--admin-radius-sm);
  background: var(--admin-primary);
}

.evaluation-dataset-detail-page__form-section-title strong {
  color: var(--admin-text-primary);
  font-size: 14px;
  font-weight: 700;
}

.evaluation-dataset-detail-page__form-section-title em {
  color: var(--admin-text-subtle);
  font-size: 12px;
  font-style: normal;
}

.evaluation-dataset-detail-page__evidence-selector-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.evaluation-dataset-detail-page__evidence-selector-head label {
  color: var(--admin-text-secondary);
  font-size: 14px;
  font-weight: 500;
}

.evaluation-dataset-detail-page__selected-evidence-box {
  display: flex;
  min-height: 88px;
  flex-direction: column;
  gap: 10px;
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-sm);
  background: #fafafa;
  padding: 12px;
}

.evaluation-dataset-detail-page__selected-empty {
  display: flex;
  min-height: 62px;
  align-items: center;
  justify-content: center;
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.evaluation-dataset-detail-page__selected-document {
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-sm);
  background: var(--admin-surface);
  padding: 12px;
}

.evaluation-dataset-detail-page__selected-document-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.evaluation-dataset-detail-page__selected-document-title strong {
  flex: 1;
  overflow: hidden;
  color: var(--admin-text-primary);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evaluation-dataset-detail-page__selected-document-title :deep(.el-button) {
  color: var(--admin-text-subtle);
}

.evaluation-dataset-detail-page__selected-document-title :deep(.el-button:hover) {
  color: var(--admin-danger);
}

.evaluation-dataset-detail-page__selected-chunks {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-left: 20px;
}

.evaluation-dataset-detail-page__inline-field .el-input {
  flex: 1;
}

.evaluation-dataset-detail-page__chunk-search {
  flex: 1;
}

.evaluation-dataset-detail-page__chunk-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.evaluation-dataset-detail-page__chunk-picker {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(260px, 2fr);
  min-height: 500px;
}

.evaluation-dataset-detail-page__chunk-picker-left,
.evaluation-dataset-detail-page__chunk-picker-right {
  min-width: 0;
}

.evaluation-dataset-detail-page__chunk-picker-left {
  border-right: 1px solid var(--admin-border-soft);
  background: var(--admin-surface);
}

.evaluation-dataset-detail-page__chunk-picker-right {
  display: flex;
  flex-direction: column;
  background: var(--admin-surface-muted);
}

.evaluation-dataset-detail-page__chunk-search-row {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid var(--admin-border-soft);
  padding: 14px;
}

.evaluation-dataset-detail-page__chunk-group-list {
  height: 420px;
  overflow-y: auto;
  padding: 10px 12px;
}

.evaluation-dataset-detail-page__chunk-empty {
  display: flex;
  height: 100%;
  align-items: center;
  justify-content: center;
  color: var(--admin-text-subtle);
  font-size: 13px;
}

.evaluation-dataset-detail-page__candidate-document {
  padding: 6px 0 10px;
}

.evaluation-dataset-detail-page__candidate-document + .evaluation-dataset-detail-page__candidate-document {
  border-top: 1px solid var(--admin-border-soft);
}

.evaluation-dataset-detail-page__candidate-document-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 2px;
}

.evaluation-dataset-detail-page__candidate-document-head div {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
}

.evaluation-dataset-detail-page__candidate-document-head strong {
  overflow: hidden;
  color: var(--admin-text-primary);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evaluation-dataset-detail-page__candidate-document-head span {
  flex-shrink: 0;
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.evaluation-dataset-detail-page__candidate-chunk {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-left: 20px;
  border-radius: var(--admin-radius-sm);
  padding: 7px 8px;
  cursor: pointer;
}

.evaluation-dataset-detail-page__candidate-chunk:hover,
.evaluation-dataset-detail-page__candidate-chunk.is-selected {
  background: var(--admin-primary-soft);
}

.evaluation-dataset-detail-page__candidate-chunk > .el-icon {
  flex-shrink: 0;
  margin-top: 3px;
  color: var(--admin-text-subtle);
}

.evaluation-dataset-detail-page__candidate-chunk span {
  display: -webkit-box;
  overflow: hidden;
  color: var(--admin-text-secondary);
  font-size: 12px;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.evaluation-dataset-detail-page__chunk-load-state {
  display: flex;
  justify-content: center;
  padding: 10px 0 4px;
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.evaluation-dataset-detail-page__selected-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--admin-border-soft);
  padding: 14px 16px;
}

.evaluation-dataset-detail-page__selected-panel-head strong {
  color: var(--admin-text-primary);
  font-size: 13px;
}

.evaluation-dataset-detail-page__selected-panel-head span {
  color: var(--admin-primary);
}

.evaluation-dataset-detail-page__draft-selected-list {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
}

.evaluation-dataset-detail-page__draft-empty {
  display: flex;
  height: 100%;
  min-height: 300px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.evaluation-dataset-detail-page__draft-empty .el-icon {
  font-size: 30px;
}

.evaluation-dataset-detail-page__draft-document {
  margin-bottom: 14px;
}

.evaluation-dataset-detail-page__draft-document > strong {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  color: var(--admin-text-primary);
  font-size: 12px;
}

.evaluation-dataset-detail-page__draft-chunk {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-left: 20px;
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-sm);
  background: var(--admin-surface);
  padding: 8px;
}

.evaluation-dataset-detail-page__draft-chunk + .evaluation-dataset-detail-page__draft-chunk {
  margin-top: 6px;
}

.evaluation-dataset-detail-page__draft-chunk p {
  flex: 1;
  margin: 0;
  color: var(--admin-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.evaluation-dataset-detail-page__pagination {
  display: flex;
  min-height: 56px;
  align-items: center;
  justify-content: flex-end;
  border-top: 1px solid var(--admin-border-soft);
  padding: 12px 0 0;
}

.evaluation-dataset-detail-page__run-alert {
  margin-bottom: 16px;
}

@media (max-width: 768px) {
  .evaluation-dataset-detail-page__form-grid {
    grid-template-columns: 1fr;
  }

  .evaluation-dataset-detail-page__chunk-picker {
    grid-template-columns: 1fr;
  }

  .evaluation-dataset-detail-page__chunk-picker-left {
    border-right: 0;
    border-bottom: 1px solid var(--admin-border-soft);
  }

  .evaluation-dataset-detail-page__chunk-search {
    width: 100%;
  }
}
</style>

