<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Check,
  Clock,
  Close,
  Delete,
  Grid,
  List,
  Plus,
  RefreshRight,
  Search,
  Setting,
  Warning,
} from "@element-plus/icons-vue";

import AdminPageHeader from "@/app/components/admin/AdminPageHeader.vue";
import AdminBulkActions from "@/app/components/admin/AdminBulkActions.vue";
import AdminDataTable from "@/app/components/admin/AdminDataTable.vue";
import AdminDialog from "@/app/components/admin/AdminDialog.vue";
import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminPagination from "@/app/components/admin/AdminPagination.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import {
  bulkActionKnowledgeBases,
  createKnowledgeBase,
  deleteKnowledgeBase,
  listKnowledgeBases,
  reindexKnowledgeBaseDocuments,
  toggleKnowledgeBaseActive,
  updateKnowledgeBase,
} from "@/shared/api/knowledge-bases";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import { useTeamScopeStore } from "@/stores/team-scope";
import { isForbiddenError } from "@/shared/utils/error";
import type {
  KnowledgeBaseListItem,
  KnowledgeBaseStatus,
} from "@/shared/types/knowledge-base";

interface KnowledgeBaseCardItem {
  id: number;
  name: string;
  description: string;
  documentCount: number;
  indexedDocumentCount: number;
  pendingDocumentCount: number;
  status: KnowledgeBaseStatus;
  isActive: boolean;
  updateTime: string;
}

const router = useRouter();
const teamScopeStore = useTeamScopeStore();

const toolbar = reactive({
  search: "",
});
const viewMode = ref<"table" | "card">("table");
let loadRequestSeq = 0;

const knowledgeBases = ref<KnowledgeBaseListItem[]>([]);
const loading = ref(false);
const loadError = ref<unknown>(null);
const hasLoadedData = ref(false);
const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
});
const selectedKnowledgeBaseIds = ref<number[]>([]);
const batchActionLoading = ref<"" | "enable" | "reindex" | "delete">("");
const deleteOverlay = reactive({ active: false, title: "", description: "" });
const dialogMode = ref<"create" | "edit">("create");
const editingKnowledgeBaseId = ref<number | null>(null);
const isKnowledgeBaseDialogVisible = ref(false);
const knowledgeBaseFormLoading = ref(false);
const knowledgeBaseForm = reactive({
  name: "",
  description: "",
});

const cardItems = computed<KnowledgeBaseCardItem[]>(() =>
  knowledgeBases.value.map((item) => ({
    id: item.id,
    name: item.name,
    description: item.description?.trim() || "暂无说明",
    documentCount: item.document_count,
    indexedDocumentCount: item.indexed_document_count,
    pendingDocumentCount: item.queued_document_count + item.processing_document_count,
    status: item.status,
    isActive: item.is_active,
    updateTime: formatDateTime(item.last_document_updated_at ?? item.updated_at),
  })),
);

const displayedKnowledgeBases = computed(() => {
  return cardItems.value;
});

const isForbidden = computed(() => Boolean(loadError.value) && isForbiddenError(loadError.value));
const isSearchActive = computed(() => toolbar.search.trim().length > 0);
const selectedCount = computed(() => selectedKnowledgeBaseIds.value.length);
const hasMoreKnowledgeBases = computed(() => knowledgeBases.value.length < pagination.total);
const selectedTeamName = computed(() => teamScopeStore.selectedTeam?.name ?? "未选择团队");
const knowledgeBaseDialogTitle = computed(() =>
  dialogMode.value === "create" ? "创建知识库" : "编辑知识库",
);
const knowledgeBaseDialogActionText = computed(() =>
  dialogMode.value === "create" ? "创建" : "保存",
);
const isAllDisplayedSelected = computed({
  get() {
    return (
      displayedKnowledgeBases.value.length > 0 &&
      displayedKnowledgeBases.value.every((item) => selectedKnowledgeBaseIds.value.includes(item.id))
    );
  },
  set(value: boolean) {
    if (!value) {
      const displayedIds = new Set(displayedKnowledgeBases.value.map((item) => item.id));
      selectedKnowledgeBaseIds.value = selectedKnowledgeBaseIds.value.filter((item) => !displayedIds.has(item));
      return;
    }

    const mergedIds = new Set(selectedKnowledgeBaseIds.value);
    for (const item of displayedKnowledgeBases.value) {
      mergedIds.add(item.id);
    }
    selectedKnowledgeBaseIds.value = [...mergedIds];
  },
});

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

async function loadKnowledgeBaseList(options: { append?: boolean } = {}) {
  const requestSeq = ++loadRequestSeq;
  loading.value = true;
  loadError.value = null;

  try {
    const result = await listKnowledgeBases({
      team_id: teamScopeStore.selectedTeamId ?? undefined,
      keyword: toolbar.search.trim() || undefined,
      page: pagination.page,
      page_size: pagination.pageSize,
    });
    if (requestSeq !== loadRequestSeq) {
      return;
    }
    knowledgeBases.value = options.append ? [...knowledgeBases.value, ...result.items] : result.items;
    pagination.total = result.total;
    pagination.page = result.page;
    pagination.pageSize = result.page_size;
    const validIds = new Set(knowledgeBases.value.map((item) => item.id));
    selectedKnowledgeBaseIds.value = selectedKnowledgeBaseIds.value.filter((item) => validIds.has(item));
    hasLoadedData.value = true;
  } catch (error) {
    if (requestSeq !== loadRequestSeq) {
      return;
    }
    if (hasLoadedData.value) {
      ElMessage.error(error instanceof Error ? error.message : "知识库列表刷新失败，请稍后重试。");
    } else {
      loadError.value = error;
    }
  } finally {
    if (requestSeq === loadRequestSeq) {
      loading.value = false;
    }
  }
}

async function deleteKnowledgeBases(ids: number[]) {
  if (ids.length === 1) {
    await deleteKnowledgeBase(ids[0]);
    return { affected: 1, failed: [] };
  }
  return await bulkActionKnowledgeBases(ids, "delete");
}

async function reindexKnowledgeBases(ids: number[]) {
  if (ids.length === 1) {
    await reindexKnowledgeBaseDocuments(ids[0]);
    return { affected: 1, failed: [] };
  }
  return await bulkActionKnowledgeBases(ids, "reindex");
}

function resetFilters() {
  toolbar.search = "";
  selectedKnowledgeBaseIds.value = [];
  pagination.page = 1;
  void loadKnowledgeBaseList();
}

function resetKnowledgeBaseForm() {
  knowledgeBaseForm.name = "";
  knowledgeBaseForm.description = "";
  editingKnowledgeBaseId.value = null;
  dialogMode.value = "create";
}

function openKnowledgeBase(knowledgeBaseId: number) {
  void router.push(`/knowledge-bases/${knowledgeBaseId}`);
}

function openCreateKnowledgeBase() {
  if (!teamScopeStore.selectedTeamId) {
    ElMessage.warning("请先选择所属团队，再创建知识库。");
    return;
  }

  resetKnowledgeBaseForm();
  dialogMode.value = "create";
  isKnowledgeBaseDialogVisible.value = true;
}

function openEditKnowledgeBase(knowledgeBase: KnowledgeBaseCardItem) {
  const currentKnowledgeBase = knowledgeBases.value.find((item) => item.id === knowledgeBase.id);
  if (!currentKnowledgeBase) {
    ElMessage.error("未找到知识库信息，请刷新列表后重试。");
    return;
  }

  dialogMode.value = "edit";
  editingKnowledgeBaseId.value = currentKnowledgeBase.id;
  knowledgeBaseForm.name = currentKnowledgeBase.name;
  knowledgeBaseForm.description = currentKnowledgeBase.description ?? "";
  isKnowledgeBaseDialogVisible.value = true;
}

function closeKnowledgeBaseDialog(force = false) {
  if (knowledgeBaseFormLoading.value && !force) {
    return;
  }

  isKnowledgeBaseDialogVisible.value = false;
}

async function submitKnowledgeBaseForm() {
  const name = knowledgeBaseForm.name.trim();
  const description = knowledgeBaseForm.description.trim();

  if (!name) {
    ElMessage.warning("请输入知识库名称。");
    return;
  }

  knowledgeBaseFormLoading.value = true;
  try {
    if (dialogMode.value === "create") {
      if (!teamScopeStore.selectedTeamId) {
        ElMessage.warning("请先选择所属团队，再创建知识库。");
        return;
      }

      await createKnowledgeBase({
        name,
        team_id: teamScopeStore.selectedTeamId,
        description: description || null,
      });
      ElMessage.success(`已在"${selectedTeamName.value}"下创建知识库"${name}"。`);
    } else {
      if (!editingKnowledgeBaseId.value) {
        ElMessage.error("缺少知识库标识，无法保存。");
        return;
      }

      await updateKnowledgeBase(editingKnowledgeBaseId.value, {
        name,
        description: description || null,
      });
      ElMessage.success(`已更新知识库"${name}"。`);
    }

    closeKnowledgeBaseDialog(true);
    await loadKnowledgeBaseList();
  } catch (error) {
    const message = error instanceof Error ? error.message : "知识库保存失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    knowledgeBaseFormLoading.value = false;
  }
}

async function openDelete(knowledgeBaseId: number, knowledgeBaseName: string) {
  try {
    await ElMessageBox.confirm(
      `确定删除"${knowledgeBaseName}"吗？删除后该知识库及其文档将不可恢复。`,
      "删除知识库",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  deleteOverlay.active = true;
  deleteOverlay.title = "正在删除";
  deleteOverlay.description = knowledgeBaseName;
  batchActionLoading.value = "delete";

  try {
    await deleteKnowledgeBases([knowledgeBaseId]);
    ElMessage.success(`已删除"${knowledgeBaseName}"。`);
    selectedKnowledgeBaseIds.value = selectedKnowledgeBaseIds.value.filter((item) => item !== knowledgeBaseId);
    await loadKnowledgeBaseList();
  } catch (error) {
    const message = error instanceof Error ? error.message : "删除知识库失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    deleteOverlay.active = false;
    batchActionLoading.value = "";
  }
}

function toggleCardSelection(knowledgeBaseId: number) {
  if (selectedKnowledgeBaseIds.value.includes(knowledgeBaseId)) {
    selectedKnowledgeBaseIds.value = selectedKnowledgeBaseIds.value.filter((item) => item !== knowledgeBaseId);
    return;
  }

  selectedKnowledgeBaseIds.value = [...selectedKnowledgeBaseIds.value, knowledgeBaseId];
}

function handleTableSelectionChange(selection: KnowledgeBaseCardItem[]) {
  selectedKnowledgeBaseIds.value = selection.map((item) => item.id);
}

function handlePageChange(page: number) {
  pagination.page = page;
  selectedKnowledgeBaseIds.value = [];
  void loadKnowledgeBaseList();
}

function handleSizeChange(size: number) {
  pagination.pageSize = size;
  refreshKnowledgeBaseListFromFirstPage();
}

function refreshKnowledgeBaseListFromFirstPage() {
  pagination.page = 1;
  selectedKnowledgeBaseIds.value = [];
  void loadKnowledgeBaseList();
}

function handleViewModeChange() {
  refreshKnowledgeBaseListFromFirstPage();
}

async function loadMoreKnowledgeBases() {
  if (loading.value || !hasMoreKnowledgeBases.value) {
    return;
  }

  pagination.page += 1;
  await loadKnowledgeBaseList({ append: true });
}

function getStatusText(status: KnowledgeBaseStatus) {
  const statusTextMap: Record<KnowledgeBaseStatus, string> = {
    available: "可用",
    indexing: "索引中",
    error: "异常",
    empty: "空库",
  };

  return statusTextMap[status];
}

function getStatusClass(status: KnowledgeBaseStatus) {
  const statusClassMap: Record<KnowledgeBaseStatus, string> = {
    available: "kb-card__status-dot--available",
    indexing: "kb-card__status-dot--indexing",
    error: "kb-card__status-dot--error",
    empty: "kb-card__status-dot--empty",
  };

  return statusClassMap[status];
}

async function handleToggleActive(knowledgeBaseId: number, knowledgeBaseName: string, targetActive: boolean) {
  if (batchActionLoading.value) {
    return;
  }

  const actionText = targetActive ? "启用" : "禁用";
  try {
    await ElMessageBox.confirm(
      `确定${actionText}知识库"${knowledgeBaseName}"吗？`,
      `${actionText}知识库`,
      { type: "warning", confirmButtonText: "确定", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }

  batchActionLoading.value = "enable";
  try {
    await toggleKnowledgeBaseActive(knowledgeBaseId, targetActive);
    ElMessage.success(`已${actionText}"${knowledgeBaseName}"。`);
    await loadKnowledgeBaseList();
  } catch (error) {
    const message = error instanceof Error ? error.message : `${actionText}失败，请稍后重试。`;
    ElMessage.error(message);
  } finally {
    batchActionLoading.value = "";
  }
}

async function handleBatchEnable() {
  if (selectedKnowledgeBaseIds.value.length === 0 || batchActionLoading.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定批量启用 ${selectedKnowledgeBaseIds.value.length} 个知识库吗？`,
      "批量启用",
      { type: "info", confirmButtonText: "确定", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }

  batchActionLoading.value = "enable";
  try {
    const result = await bulkActionKnowledgeBases(selectedKnowledgeBaseIds.value, "enable");
    if (result.failed.length > 0) {
      ElMessage.warning(`已启用 ${result.affected} 个知识库，${result.failed.length} 个处理失败。`);
    } else {
      ElMessage.success(`已启用 ${result.affected} 个知识库。`);
    }
    selectedKnowledgeBaseIds.value = [];
    await loadKnowledgeBaseList();
  } catch (error) {
    const message = error instanceof Error ? error.message : "批量启用失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    batchActionLoading.value = "";
  }
}

async function confirmReindexKnowledgeBases(targetLabel: string) {
  try {
    await ElMessageBox.confirm(
      `确定重建 ${targetLabel} 的索引吗？该操作会重新提交全部文档的索引任务，处理中可能短暂影响当前检索结果。`,
      "重建索引提醒",
      {
        type: "warning",
        confirmButtonText: "继续重建",
        cancelButtonText: "取消",
      },
    );
    return true;
  } catch {
    return false;
  }
}

async function handleSingleReindex(knowledgeBaseId: number, knowledgeBaseName: string) {
  if (batchActionLoading.value) {
    return;
  }

  const isConfirmed = await confirmReindexKnowledgeBases(`"${knowledgeBaseName}"`);
  if (!isConfirmed) {
    return;
  }

  batchActionLoading.value = "reindex";
  try {
    await reindexKnowledgeBases([knowledgeBaseId]);
    ElMessage.success(`已提交"${knowledgeBaseName}"的重建索引任务。`);
    await loadKnowledgeBaseList();
  } catch (error) {
    const message = error instanceof Error ? error.message : "重建索引失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    batchActionLoading.value = "";
  }
}

async function handleBatchReindex() {
  if (selectedKnowledgeBaseIds.value.length === 0 || batchActionLoading.value) {
    return;
  }

  const isConfirmed = await confirmReindexKnowledgeBases(
    `已选中的 ${selectedKnowledgeBaseIds.value.length} 个知识库`,
  );
  if (!isConfirmed) {
    return;
  }

  batchActionLoading.value = "reindex";
  try {
    const result = await reindexKnowledgeBases(selectedKnowledgeBaseIds.value);
    if (result.failed.length > 0) {
      ElMessage.warning(`已提交 ${result.affected} 个知识库的重建索引任务，${result.failed.length} 个处理失败。`);
    } else {
      ElMessage.success(`已提交 ${result.affected} 个知识库的重建索引任务。`);
    }
    selectedKnowledgeBaseIds.value = [];
    await loadKnowledgeBaseList();
  } catch (error) {
    const message = error instanceof Error ? error.message : "批量重建索引失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    batchActionLoading.value = "";
  }
}

async function handleBatchDelete() {
  if (selectedKnowledgeBaseIds.value.length === 0 || batchActionLoading.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定删除已选中的 ${selectedKnowledgeBaseIds.value.length} 个知识库吗？删除后该知识库及其文档将不可恢复。`,
      "批量删除知识库",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  const deleteCount = selectedKnowledgeBaseIds.value.length;
  deleteOverlay.active = true;
  deleteOverlay.title = "正在批量删除";
  deleteOverlay.description = `${deleteCount} 个知识库`;
  batchActionLoading.value = "delete";

  try {
    const result = await deleteKnowledgeBases(selectedKnowledgeBaseIds.value);
    selectedKnowledgeBaseIds.value = [];
    if (result.failed.length > 0) {
      ElMessage.warning(`已删除 ${result.affected} 个知识库，${result.failed.length} 个处理失败。`);
    } else {
      ElMessage.success(`已删除 ${result.affected} 个知识库。`);
    }
    await loadKnowledgeBaseList();
  } catch (error) {
    const message = error instanceof Error ? error.message : "批量删除知识库失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    deleteOverlay.active = false;
    batchActionLoading.value = "";
  }
}

onMounted(() => {
  void loadKnowledgeBaseList();
});

watch(
  () => teamScopeStore.selectedTeamId,
  () => {
    pagination.page = 1;
    selectedKnowledgeBaseIds.value = [];
    void loadKnowledgeBaseList();
  },
);

</script>

<template>
  <section class="kb-list-page">
    <AdminPageHeader
      title="知识库"
      description="管理企业知识、文档生命周期和索引状态。"
    />

    <AppLoading
      v-if="loading && !hasLoadedData"
      title="知识库列表加载中"
      description="正在从后台获取知识库列表，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="loadError && !isForbidden && !hasLoadedData"
      title="知识库列表加载失败"
      description="暂时无法获取知识库列表，请稍后重试。"
      :error="loadError"
      @retry="loadKnowledgeBaseList"
    />

    <AppError
      v-else-if="isForbidden && !hasLoadedData"
      title="无权查看知识库列表"
      description="当前账号没有访问知识库列表的权限。"
      :error="loadError"
      :show-retry="false"
    />

    <AdminListPanel v-else>
      <AdminTableToolbar>
        <template #left>
          <el-input
            v-model="toolbar.search"
            clearable
            placeholder="搜索知识库名称或描述..."
            class="kb-list-page__search"
            @keyup.enter="refreshKnowledgeBaseListFromFirstPage"
            @clear="refreshKnowledgeBaseListFromFirstPage"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button :loading="loading" type="primary" @click="refreshKnowledgeBaseListFromFirstPage">
            搜索
          </el-button>
          <el-button :disabled="loading" @click="resetFilters">重置</el-button>
        </template>

        <template #right>
          <el-segmented
            v-model="viewMode"
            class="kb-list-page__view-switch"
            :options="[
              { label: '列表', value: 'table' },
              { label: '卡片', value: 'card' },
            ]"
            @change="handleViewModeChange"
          >
            <template #default="{ item }">
              <span class="kb-list-page__view-option">
                <el-icon>
                  <List v-if="item.value === 'table'" />
                  <Grid v-else />
                </el-icon>
                <span>{{ item.label }}</span>
              </span>
            </template>
          </el-segmented>

          <AdminBulkActions :selected-count="selectedCount">
            <el-button
              link
              type="primary"
              :loading="batchActionLoading === 'enable'"
              :disabled="Boolean(batchActionLoading)"
              @click="handleBatchEnable"
            >
              启用
            </el-button>
            <el-button
              link
              type="primary"
              :loading="batchActionLoading === 'reindex'"
              :disabled="Boolean(batchActionLoading)"
              @click="handleBatchReindex"
            >
              重建索引
            </el-button>
            <el-button
              link
              type="danger"
              :loading="batchActionLoading === 'delete'"
              :disabled="Boolean(batchActionLoading)"
              @click="handleBatchDelete"
            >
              删除
            </el-button>
          </AdminBulkActions>

          <el-button :loading="loading" @click="loadKnowledgeBaseList">
            <el-icon class="mr-2"><RefreshRight /></el-icon>
            刷新
          </el-button>
          <el-button type="primary" :disabled="loading" @click="openCreateKnowledgeBase">
            <el-icon class="mr-2"><Plus /></el-icon>
            创建知识库
          </el-button>
        </template>
      </AdminTableToolbar>

    <AppEmpty
      v-if="!loading && displayedKnowledgeBases.length === 0"
      class="kb-list-page__empty"
      :title="isSearchActive ? '未找到相关知识库' : '暂无知识库'"
      :description="
        isSearchActive
          ? '请尝试更换搜索关键词，或清除搜索后查看全部知识库。'
          : '当前还没有可展示的知识库。'
      "
    >
      <el-button link type="primary" @click="resetFilters">清除筛选</el-button>
    </AppEmpty>

      <AdminDataTable
        v-else-if="viewMode === 'table'"
        :data="displayedKnowledgeBases"
        :loading="loading"
        table-class="kb-list-page__table"
        loading-text="正在更新知识库列表"
        @selection-change="handleTableSelectionChange"
      >
        <el-table-column type="selection" width="44" fixed="left" />
        <el-table-column label="知识库" min-width="260">
          <template #default="{ row }">
            <button type="button" class="kb-list-page__name-button" @click="openKnowledgeBase(row.id)">
              <strong>{{ row.name }}</strong>
              <span>{{ row.description || "暂无说明" }}</span>
            </button>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="120">
          <template #default="{ row }">
            <span class="kb-list-page__status">
              <span :class="['kb-card__status-dot', getStatusClass(row.status)]" />
              {{ getStatusText(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="文档" min-width="190">
          <template #default="{ row }">
            <div class="kb-list-page__doc-stats">
              <span>总数 {{ row.documentCount }}</span>
              <span>已索引 {{ row.indexedDocumentCount }}</span>
              <span v-if="row.pendingDocumentCount > 0" class="kb-list-page__pending">
                待处理 {{ row.pendingDocumentCount }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="启用状态" min-width="110">
          <template #default="{ row }">
            <el-switch
              :model-value="row.isActive"
              :loading="batchActionLoading === 'enable'"
              inline-prompt
              active-text="启用"
              inactive-text="禁用"
              @change="handleToggleActive(row.id, row.name, Boolean($event))"
            />
          </template>
        </el-table-column>
        <el-table-column label="最近更新" min-width="170">
          <template #default="{ row }">
            <span class="kb-list-page__muted">{{ row.updateTime }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="208" fixed="right" align="center">
          <template #default="{ row }">
            <div class="kb-list-page__row-actions">
              <el-button link type="primary" @click="openKnowledgeBase(row.id)">进入</el-button>
              <el-button link type="primary" @click="openEditKnowledgeBase(row)">设置</el-button>
              <el-button
                link
                type="primary"
                :disabled="Boolean(batchActionLoading)"
                @click="handleSingleReindex(row.id, row.name)"
              >
                重建
              </el-button>
              <el-button link type="danger" @click="openDelete(row.id, row.name)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </AdminDataTable>

      <div v-else class="kb-list-page__card-wrap">
        <div class="kb-list-page__card-toolbar">
          <label class="kb-list-page__select-all">
            <el-checkbox v-model="isAllDisplayedSelected" />
            <span>全选当前页</span>
          </label>
        </div>
        <div class="kb-list-page__grid">
      <article
        v-for="item in displayedKnowledgeBases"
        :key="item.id"
        :class="[
          'kb-card',
          selectedKnowledgeBaseIds.includes(item.id) ? 'kb-card--selected' : '',
          !item.isActive ? 'kb-card--disabled' : '',
        ]"
      >
        <div class="kb-card__topbar">
          <label class="kb-card__checkbox" @click.stop>
            <el-checkbox
              :model-value="selectedKnowledgeBaseIds.includes(item.id)"
              @change="() => toggleCardSelection(item.id)"
            />
          </label>

          <button
            type="button"
            class="kb-card__title-button"
            @click="openKnowledgeBase(item.id)"
          >
            <span class="kb-card__title-text">{{ item.name }}</span>
          </button>

          <span
            :class="[
              'kb-card__status-dot',
              getStatusClass(item.status),
            ]"
            :title="getStatusText(item.status)"
          />
          <span v-if="!item.isActive" class="kb-card__disabled-badge">已禁用</span>
        </div>

        <button
          type="button"
          class="kb-card__content"
          @click="openKnowledgeBase(item.id)"
        >
          <p class="kb-card__description">
            {{ item.description || "暂无说明" }}
          </p>

          <div class="kb-card__stats">
            <div class="kb-card__stat-item">
              <span class="kb-card__stat-label">可用文档</span>
              <span class="kb-card__stat-value">{{ item.documentCount }}</span>
            </div>
            <div class="kb-card__stat-item">
              <span class="kb-card__stat-label">已索引文档</span>
              <span class="kb-card__stat-value">{{ item.indexedDocumentCount }}</span>
            </div>
          </div>

          <div
            v-if="item.pendingDocumentCount > 0"
            class="kb-card__pending-tip"
          >
            <el-icon><Warning /></el-icon>
            <span>待处理文档 {{ item.pendingDocumentCount }}</span>
          </div>

          <div class="kb-card__updated-at">
            <el-icon><Clock /></el-icon>
            <span>更新于 {{ item.updateTime }}</span>
          </div>
        </button>

        <footer class="kb-card__footer">
          <button
            type="button"
            class="kb-card__action-button"
            :disabled="Boolean(batchActionLoading)"
            @click.stop="handleSingleReindex(item.id, item.name)"
          >
            <el-icon><RefreshRight /></el-icon>
            <span>重建索引</span>
          </button>
          <button
            type="button"
            class="kb-card__action-button"
            @click.stop="openEditKnowledgeBase(item)"
          >
            <el-icon><Setting /></el-icon>
            <span>设置</span>
          </button>
          <button
            v-if="item.isActive"
            type="button"
            class="kb-card__action-button kb-card__action-button--danger"
            :disabled="Boolean(batchActionLoading)"
            @click.stop="handleToggleActive(item.id, item.name, false)"
          >
            <el-icon><Close /></el-icon>
            <span>禁用</span>
          </button>
          <button
            v-else
            type="button"
            class="kb-card__action-button"
            :disabled="Boolean(batchActionLoading)"
            @click.stop="handleToggleActive(item.id, item.name, true)"
          >
            <el-icon><Check /></el-icon>
            <span>启用</span>
          </button>
          <button
            type="button"
            class="kb-card__action-button kb-card__action-button--danger"
            @click.stop="openDelete(item.id, item.name)"
          >
            <el-icon><Delete /></el-icon>
          </button>
        </footer>
      </article>
        </div>
        <div class="kb-list-page__load-more">
          <el-button
            v-if="hasMoreKnowledgeBases"
            :loading="loading"
            :disabled="loading"
            @click="loadMoreKnowledgeBases"
          >
            加载更多
          </el-button>
          <span v-else class="kb-list-page__load-more-text">
            已显示全部 {{ pagination.total }} 个知识库
          </span>
        </div>
    </div>

      <AdminPagination
        v-if="viewMode === 'table' && displayedKnowledgeBases.length > 0"
        :current-page="pagination.page"
        :page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50]"
        :total="pagination.total"
        @page-change="handlePageChange"
        @page-size-change="handleSizeChange"
      />
    </AdminListPanel>

    <AdminDialog
      v-model="isKnowledgeBaseDialogVisible"
      :title="knowledgeBaseDialogTitle"
      width="560px"
      :loading="knowledgeBaseFormLoading"
      @closed="resetKnowledgeBaseForm"
    >
      <div class="admin-dialog__scope">
        <span class="admin-dialog__scope-label">所属团队</span>
        <span class="admin-dialog__scope-value">{{ selectedTeamName }}</span>
      </div>

      <el-form
        label-position="top"
        class="admin-dialog__form"
      >
        <el-form-item label="知识库名称" required>
          <el-input
            v-model="knowledgeBaseForm.name"
            maxlength="100"
            show-word-limit
            placeholder="请输入知识库名称"
          />
        </el-form-item>

        <el-form-item label="知识库说明">
          <el-input
            v-model="knowledgeBaseForm.description"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="请输入知识库说明"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button :disabled="knowledgeBaseFormLoading" @click="closeKnowledgeBaseDialog">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="knowledgeBaseFormLoading"
          @click="submitKnowledgeBaseForm"
        >
          {{ knowledgeBaseDialogActionText }}
        </el-button>
      </template>
    </AdminDialog>

    <Teleport to="body">
      <Transition name="delete-overlay">
        <div v-if="deleteOverlay.active" class="delete-overlay">
          <div class="delete-overlay__card">
            <el-icon class="is-loading delete-overlay__spinner" :size="24"><RefreshRight /></el-icon>
            <h3 class="delete-overlay__title">{{ deleteOverlay.title }}</h3>
            <p class="delete-overlay__desc">{{ deleteOverlay.description }}</p>
          </div>
        </div>
      </Transition>
    </Teleport>
  </section>
</template>

<style scoped>
.kb-list-page {
  --el-color-primary: var(--admin-primary);
  --el-color-primary-light-3: var(--admin-primary-light);
  --el-color-primary-light-5: var(--admin-primary-light);
  --el-color-primary-light-7: var(--admin-primary-border);
  --el-color-primary-light-9: var(--admin-primary-soft);
  --el-color-primary-dark-2: var(--admin-primary-hover);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.kb-list-page__search {
  width: 280px;
}

.kb-list-page__view-option,
.kb-list-page__status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.kb-list-page__view-option {
  font-size: 13px;
}

.kb-list-page__view-switch :deep(.el-segmented__item) {
  min-width: 66px;
}

.kb-list-page__empty {
  min-height: 420px;
  border-top: 1px solid var(--admin-border-soft);
}

.kb-list-page__table {
  width: 100%;
}

.kb-list-page__name-button {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  width: 100%;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0;
  text-align: left;
}

.kb-list-page__name-button strong {
  overflow: hidden;
  color: var(--admin-text);
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-list-page__name-button span,
.kb-list-page__muted {
  color: var(--admin-text-muted);
  font-size: 13px;
}

.kb-list-page__doc-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  color: var(--admin-text-secondary);
  font-size: 13px;
}

.kb-list-page__pending {
  color: var(--admin-warning);
  font-weight: 600;
}

.kb-list-page__row-actions {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
}

.kb-list-page__select-all {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--admin-text-secondary);
  cursor: pointer;
  font-size: 14px;
  white-space: nowrap;
}

.kb-list-page__card-wrap {
  height: var(--admin-table-height);
  overflow: auto;
  border-top: 1px solid var(--admin-border-soft);
  background: var(--admin-surface);
  padding: 12px;
}

.kb-list-page__card-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.kb-list-page__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.kb-list-page__load-more {
  display: flex;
  justify-content: center;
  padding: 16px 0 4px;
}

.kb-list-page__load-more-text {
  color: var(--admin-text-muted);
  font-size: 13px;
}

.kb-card {
  position: relative;
  display: flex;
  min-height: 220px;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-lg);
  background: var(--admin-surface);
  box-shadow: none;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease;
}

.kb-card:hover {
  border-color: var(--admin-border);
  background: var(--admin-surface);
}

.kb-card--selected {
  border-color: var(--admin-primary);
  box-shadow: 0 0 0 1px var(--admin-primary);
}

.kb-card--disabled {
  background: var(--admin-surface-muted);
  opacity: 0.72;
}

.kb-card--disabled:hover {
  background: var(--admin-surface-muted);
  box-shadow: none;
}

.kb-card__disabled-badge {
  border-radius: 999px;
  background: var(--admin-border-soft);
  color: var(--admin-text-subtle);
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  margin-left: 4px;
}

.kb-card__topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid var(--admin-border-soft);
  background: var(--admin-surface-muted);
  padding: 12px;
}

.kb-card__checkbox {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.kb-card__title-button {
  display: inline-flex;
  flex: 1;
  align-items: center;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--admin-text);
  cursor: pointer;
  padding: 0;
  text-align: left;
}

.kb-card__title-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 700;
}

.kb-card__status-dot {
  width: 8px;
  height: 8px;
  flex-shrink: 0;
  border-radius: 999px;
}

.kb-card__status-dot--available {
  background: #22c55e;
  box-shadow: none;
}

.kb-card__status-dot--indexing {
  background: #f59e0b;
  box-shadow: none;
}

.kb-card__status-dot--error {
  background: #ef4444;
  box-shadow: none;
}

.kb-card__status-dot--empty {
  background: var(--admin-border);
}

.kb-card__content {
  display: flex;
  flex: 1;
  flex-direction: column;
  border: 0;
  background: transparent;
  cursor: pointer;
  padding: 12px;
  text-align: left;
}

.kb-card__description {
  display: -webkit-box;
  min-height: 40px;
  margin: 0 0 12px;
  overflow: hidden;
  color: var(--admin-text-muted);
  font-size: 13px;
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.kb-card__stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.kb-card__stat-item {
  display: flex;
  min-height: 42px;
  align-items: center;
  justify-content: space-between;
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-sm);
  background: var(--admin-surface-muted);
  padding: 8px 10px;
}

.kb-card__stat-label {
  color: var(--admin-text-muted);
  font-size: 12px;
}

.kb-card__stat-value {
  color: var(--admin-text);
  font-size: 15px;
  font-weight: 700;
}

.kb-card__pending-tip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  color: var(--admin-warning);
  font-size: 12px;
  font-weight: 600;
}

.kb-card__updated-at {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: auto;
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.kb-card__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  border-top: 1px solid var(--admin-border-soft);
  background: var(--admin-surface-muted);
  padding: 8px 12px;
}

.kb-card__action-button {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  border: 0;
  border-radius: var(--admin-radius-sm);
  background: transparent;
  color: var(--admin-text-muted);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  padding: 5px 8px;
  transition:
    background-color 0.2s ease,
    color 0.2s ease;
}

.kb-card__action-button:hover {
  background: var(--admin-surface);
  color: var(--admin-primary);
}

.kb-card__action-button--danger {
  padding-inline: 8px;
}

.kb-card__action-button--danger:hover {
  color: var(--admin-danger);
}

@media (max-width: 1280px) {
  .kb-list-page__grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1080px) {
  .kb-list-page__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .kb-list-page__search {
    width: 100%;
  }
}

@media (max-width: 720px) {
  .kb-list-page__grid {
    grid-template-columns: 1fr;
  }
}

.delete-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.28);
  backdrop-filter: blur(2px);
}

.delete-overlay__card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  width: 280px;
  border: 1px solid var(--admin-border);
  border-radius: var(--admin-radius-lg);
  background: var(--admin-surface);
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.16);
  padding: 22px 24px;
}

.delete-overlay__spinner {
  color: var(--admin-primary);
}

.delete-overlay__title {
  margin: 0;
  color: var(--admin-text);
  font-size: 15px;
  font-weight: 700;
}

.delete-overlay__desc {
  margin: 0;
  color: var(--admin-text-muted);
  font-size: 14px;
  text-align: center;
  word-break: break-all;
}

.delete-overlay-enter-active {
  transition: opacity 0.18s ease;
}

.delete-overlay-enter-active .delete-overlay__card {
  transition: transform 0.18s ease, opacity 0.18s ease;
}

.delete-overlay-enter-from {
  opacity: 0;
}

.delete-overlay-enter-from .delete-overlay__card {
  transform: translateY(4px);
  opacity: 0;
}

.delete-overlay-leave-active {
  transition: opacity 0.2s ease;
}

.delete-overlay-leave-to {
  opacity: 0;
}
</style>
