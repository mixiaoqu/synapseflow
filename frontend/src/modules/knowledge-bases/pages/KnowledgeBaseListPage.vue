<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Check,
  Clock,
  Close,
  Delete,
  Plus,
  RefreshRight,
  Search,
  Setting,
  Warning,
} from "@element-plus/icons-vue";

import {
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
let searchTimer: ReturnType<typeof setTimeout> | undefined;

const knowledgeBases = ref<KnowledgeBaseListItem[]>([]);
const loading = ref(false);
const loadError = ref<unknown>(null);
const pagination = reactive({
  page: 1,
  pageSize: 20,
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

async function loadKnowledgeBaseList() {
  if (loading.value) {
    return;
  }

  loading.value = true;
  loadError.value = null;

  try {
    const result = await listKnowledgeBases({
      team_id: teamScopeStore.selectedTeamId ?? undefined,
      keyword: toolbar.search.trim() || undefined,
      page: pagination.page,
      page_size: pagination.pageSize,
    });
    knowledgeBases.value = result.items;
    pagination.total = result.total;
    pagination.page = result.page;
    pagination.pageSize = result.page_size;
    const validIds = new Set(result.items.map((item) => item.id));
    selectedKnowledgeBaseIds.value = selectedKnowledgeBaseIds.value.filter((item) => validIds.has(item));
  } catch (error) {
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

async function deleteKnowledgeBases(ids: number[]) {
  await Promise.all(ids.map((item) => deleteKnowledgeBase(item)));
}

async function reindexKnowledgeBases(ids: number[]) {
  await Promise.all(ids.map((item) => reindexKnowledgeBaseDocuments(item)));
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

function handlePageChange(page: number) {
  pagination.page = page;
  selectedKnowledgeBaseIds.value = [];
  void loadKnowledgeBaseList();
}

function refreshKnowledgeBaseListFromFirstPage() {
  pagination.page = 1;
  selectedKnowledgeBaseIds.value = [];
  void loadKnowledgeBaseList();
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
    await Promise.all(
      selectedKnowledgeBaseIds.value.map((id) => toggleKnowledgeBaseActive(id, true)),
    );
    ElMessage.success(`已批量启用 ${selectedKnowledgeBaseIds.value.length} 个知识库。`);
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
    await reindexKnowledgeBases(selectedKnowledgeBaseIds.value);
    ElMessage.success(`已提交 ${selectedKnowledgeBaseIds.value.length} 个知识库的重建索引任务。`);
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
    await deleteKnowledgeBases(selectedKnowledgeBaseIds.value);
    selectedKnowledgeBaseIds.value = [];
    ElMessage.success(`已删除 ${deleteCount} 个知识库。`);
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

watch(
  () => toolbar.search,
  () => {
    if (searchTimer) {
      clearTimeout(searchTimer);
    }
    searchTimer = setTimeout(refreshKnowledgeBaseListFromFirstPage, 300);
  },
);
</script>

<template>
  <section class="kb-list-page">
    <header class="kb-list-page__hero">
      <div class="kb-list-page__hero-copy">
        <h1 class="kb-list-page__hero-title">知识库管理</h1>
        <p class="kb-list-page__hero-description">管理企业内部或业务应用依赖的纯粹数据源集合。</p>
      </div>
      <el-button type="primary" size="large" @click="openCreateKnowledgeBase">
        <el-icon class="mr-2"><Plus /></el-icon>
        创建知识库
      </el-button>
    </header>

    <section
      v-if="!loading && !loadError"
      class="kb-list-page__toolbar-panel"
    >
      <div class="kb-list-page__toolbar-row">
        <div class="kb-list-page__toolbar-main">
          <el-input
            v-model="toolbar.search"
            size="large"
            clearable
            placeholder="搜索知识库名称或描述..."
            class="kb-list-page__search"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>

        </div>

        <div class="kb-list-page__toolbar-side">
          <label class="kb-list-page__select-all">
            <el-checkbox v-model="isAllDisplayedSelected" />
            <span>全选当前页</span>
          </label>

          <transition name="kb-bulk-actions">
            <div v-if="selectedCount > 0" class="kb-list-page__bulk-actions">
              <span class="kb-list-page__bulk-count">已选 {{ selectedCount }}</span>
              <span class="kb-list-page__bulk-divider" />
              <button
                type="button"
                class="kb-list-page__bulk-button"
                :disabled="Boolean(batchActionLoading)"
                @click="handleBatchEnable"
              >
                <el-icon><Check /></el-icon>
              </button>
              <button
                type="button"
                class="kb-list-page__bulk-button"
                :disabled="Boolean(batchActionLoading)"
                @click="handleBatchReindex"
              >
                <el-icon><RefreshRight /></el-icon>
              </button>
              <button
                type="button"
                class="kb-list-page__bulk-button kb-list-page__bulk-button--danger"
                :disabled="Boolean(batchActionLoading)"
                @click="handleBatchDelete"
              >
                <el-icon><Delete /></el-icon>
              </button>
            </div>
          </transition>
        </div>
      </div>
    </section>

    <AppLoading
      v-if="loading"
      title="知识库列表加载中"
      description="正在从后台获取知识库列表，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="loadError && !isForbidden"
      title="知识库列表加载失败"
      description="暂时无法获取知识库列表，请稍后重试。"
      :error="loadError"
      @retry="loadKnowledgeBaseList"
    />

    <AppError
      v-else-if="isForbidden"
      title="无权查看知识库列表"
      description="当前账号没有访问知识库列表的权限。"
      :error="loadError"
      :show-retry="false"
    />

    <AppEmpty
      v-else-if="displayedKnowledgeBases.length === 0"
      :title="isSearchActive ? '未找到相关知识库' : '暂无知识库'"
      :description="
        isSearchActive
          ? '请尝试更换搜索关键词，或清除搜索后查看全部知识库。'
          : '当前还没有可展示的知识库。'
      "
    >
      <el-button link type="primary" @click="resetFilters">清除筛选</el-button>
    </AppEmpty>

    <div v-else class="kb-list-page__grid">
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

    <div v-if="!loading && !loadError && pagination.total > pagination.pageSize" class="kb-list-page__pagination">
      <el-pagination
        background
        layout="prev, pager, next"
        :current-page="pagination.page"
        :page-size="pagination.pageSize"
        :total="pagination.total"
        @current-change="handlePageChange"
      />
    </div>

    <el-dialog
      v-model="isKnowledgeBaseDialogVisible"
      :title="knowledgeBaseDialogTitle"
      width="560px"
      :close-on-click-modal="false"
      :close-on-press-escape="!knowledgeBaseFormLoading"
      @closed="resetKnowledgeBaseForm"
    >
      <div class="kb-dialog__scope">
        <span class="kb-dialog__scope-label">所属团队</span>
        <span class="kb-dialog__scope-value">{{ selectedTeamName }}</span>
      </div>

      <el-form
        label-position="top"
        class="kb-dialog__form"
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
        <div class="kb-dialog__footer">
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
        </div>
      </template>
    </el-dialog>

    <Teleport to="body">
      <Transition name="delete-overlay">
        <div v-if="deleteOverlay.active" class="delete-overlay">
          <div class="delete-overlay__card">
            <div class="delete-overlay__icon-ring">
              <div class="delete-overlay__icon-inner">
                <el-icon :size="28" color="#dc2626"><Delete /></el-icon>
              </div>
            </div>

            <h3 class="delete-overlay__title">{{ deleteOverlay.title }}</h3>
            <p class="delete-overlay__desc">{{ deleteOverlay.description }}</p>

            <div class="delete-overlay__dots">
              <span class="delete-overlay__dot" />
              <span class="delete-overlay__dot" />
              <span class="delete-overlay__dot" />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </section>
</template>

<style scoped>
.kb-list-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.kb-list-page__hero {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.kb-list-page__hero-copy {
  min-width: 0;
}

.kb-list-page__hero-title {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.4;
}

.kb-list-page__hero-description {
  margin: 6px 0 0;
  color: #475569;
  font-size: 14px;
  line-height: 1.7;
}

.kb-list-page__toolbar-panel {
  border: 1px solid #dbe2ea;
  border-radius: 16px;
  background: #ffffff;
  padding: 18px 16px;
}

.kb-list-page__toolbar-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.kb-list-page__toolbar-main {
  display: flex;
  flex: 1;
  align-items: center;
  gap: 12px;
}

.kb-list-page__search {
  flex: 1;
  max-width: 404px;
}

.kb-list-page__toolbar-side {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}

.kb-list-page__select-all {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #334155;
  cursor: pointer;
  font-size: 14px;
  white-space: nowrap;
}

.kb-list-page__bulk-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #dbeafe;
  border-radius: 10px;
  background: #eff6ff;
  padding: 8px 10px;
}

.kb-list-page__bulk-count {
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
}

.kb-list-page__bulk-divider {
  width: 1px;
  height: 18px;
  background: #bfdbfe;
}

.kb-list-page__bulk-button {
  display: inline-flex;
  height: 28px;
  width: 28px;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #3562b8;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    color 0.2s ease,
    opacity 0.2s ease;
}

.kb-list-page__bulk-button:hover {
  background: #ffffff;
}

.kb-list-page__bulk-button:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.kb-list-page__bulk-button--danger {
  color: #dc2626;
}

.kb-bulk-actions-enter-active,
.kb-bulk-actions-leave-active {
  transition: all 0.2s ease;
}

.kb-bulk-actions-enter-from,
.kb-bulk-actions-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.kb-list-page__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 24px;
}

.kb-list-page__pagination {
  display: flex;
  justify-content: flex-end;
}

.kb-card {
  position: relative;
  display: flex;
  min-height: 292px;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 20px;
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.kb-card:hover {
  transform: translateY(-2px);
  border-color: #cbd5e1;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}

.kb-card--selected {
  border-color: #3b82f6;
  box-shadow:
    0 0 0 1px #3b82f6,
    0 12px 28px rgba(59, 130, 246, 0.14);
}

.kb-card--disabled {
  opacity: 0.55;
}

.kb-card--disabled:hover {
  transform: none;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
}

.kb-card__disabled-badge {
  border-radius: 999px;
  background: #f1f5f9;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  margin-left: 4px;
}

.kb-card__topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid #f1f5f9;
  background: rgba(248, 250, 252, 0.72);
  padding: 16px 20px;
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
  color: #0f172a;
  cursor: pointer;
  padding: 0;
  text-align: left;
}

.kb-card__title-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 16px;
  font-weight: 700;
}

.kb-card__status-dot {
  width: 10px;
  height: 10px;
  flex-shrink: 0;
  border-radius: 999px;
}

.kb-card__status-dot--available {
  background: #22c55e;
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.16);
}

.kb-card__status-dot--indexing {
  background: #f59e0b;
  box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.16);
}

.kb-card__status-dot--error {
  background: #ef4444;
  box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.16);
}

.kb-card__status-dot--empty {
  background: #cbd5e1;
}

.kb-card__content {
  display: flex;
  flex: 1;
  flex-direction: column;
  border: 0;
  background: transparent;
  cursor: pointer;
  padding: 20px;
  text-align: left;
}

.kb-card__description {
  display: -webkit-box;
  min-height: 44px;
  margin: 0 0 16px;
  overflow: hidden;
  color: #64748b;
  font-size: 14px;
  line-height: 1.7;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.kb-card__stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.kb-card__stat-item {
  display: flex;
  min-height: 76px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 1px solid #f1f5f9;
  border-radius: 14px;
  background: #f8fafc;
}

.kb-card__stat-label {
  color: #64748b;
  font-size: 12px;
}

.kb-card__stat-value {
  margin-top: 4px;
  color: #0f172a;
  font-size: 20px;
  font-weight: 700;
}

.kb-card__pending-tip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 14px;
  color: #b45309;
  font-size: 12px;
  font-weight: 600;
}

.kb-card__updated-at {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: auto;
  color: #94a3b8;
  font-size: 12px;
}

.kb-card__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px solid #f1f5f9;
  background: #f8fafc;
  padding: 12px 20px;
}

.kb-card__action-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  padding: 6px 10px;
  transition:
    background-color 0.2s ease,
    color 0.2s ease;
}

.kb-card__action-button:hover {
  background: #ffffff;
  color: #2563eb;
}

.kb-card__action-button--danger {
  padding-inline: 8px;
}

.kb-card__action-button--danger:hover {
  color: #dc2626;
}

.kb-dialog__scope {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  border: 1px solid #dbe2ea;
  border-radius: 12px;
  background: #f8fafc;
  padding: 12px 14px;
}

.kb-dialog__scope-label {
  color: #64748b;
  font-size: 13px;
}

.kb-dialog__scope-value {
  color: #0f172a;
  font-size: 14px;
  font-weight: 600;
}

.kb-dialog__form {
  margin-top: 8px;
}

.kb-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
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
  .kb-list-page__hero,
  .kb-list-page__toolbar-row,
  .kb-list-page__toolbar-main {
    flex-direction: column;
    align-items: stretch;
  }

  .kb-list-page__search {
    width: 100%;
    max-width: none;
  }

  .kb-list-page__toolbar-side {
    justify-content: space-between;
    flex-wrap: wrap;
  }
}

@media (max-width: 720px) {
  .kb-list-page__grid {
    grid-template-columns: 1fr;
  }
}

/* ── Delete overlay ── */
.delete-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(6px);
}

.delete-overlay__card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  width: 340px;
  padding: 40px 32px 36px;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 22px 48px rgba(15, 23, 42, 0.14);
}

.delete-overlay__icon-ring {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: 999px;
  background: rgba(220, 38, 38, 0.08);
  animation: breathe 2s ease-in-out infinite;
}

.delete-overlay__icon-inner {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 999px;
  background: rgba(220, 38, 38, 0.12);
}

.delete-overlay__title {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}

.delete-overlay__desc {
  margin: 0;
  color: #64748b;
  font-size: 14px;
  text-align: center;
  word-break: break-all;
}

.delete-overlay__dots {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.delete-overlay__dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #94a3b8;
  animation: dotPulse 1.4s ease-in-out infinite;
}

.delete-overlay__dot:nth-child(2) {
  animation-delay: 0.2s;
}

.delete-overlay__dot:nth-child(3) {
  animation-delay: 0.4s;
}

/* Transitions */
.delete-overlay-enter-active {
  transition: opacity 0.25s ease;
}

.delete-overlay-enter-active .delete-overlay__card {
  transition: transform 0.25s ease, opacity 0.25s ease;
}

.delete-overlay-enter-from {
  opacity: 0;
}

.delete-overlay-enter-from .delete-overlay__card {
  transform: scale(0.92) translateY(8px);
  opacity: 0;
}

.delete-overlay-leave-active {
  transition: opacity 0.2s ease;
}

.delete-overlay-leave-to {
  opacity: 0;
}

/* Animations */
@keyframes breathe {
  0%, 100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.12);
  }
  50% {
    transform: scale(1.06);
    box-shadow: 0 0 0 12px rgba(220, 38, 38, 0);
  }
}

@keyframes dotPulse {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}
</style>
