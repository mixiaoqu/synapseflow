<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  ArrowLeft,
  CirclePlus,
  Delete,
  Document,
  EditPen,
  Folder,
  MoreFilled,
  RefreshRight,
  Search,
  UploadFilled,
  View,
} from "@element-plus/icons-vue";

import {
  createDocumentCategory,
  deleteDocumentCategory,
  listDocumentCategories,
  updateDocumentCategory,
} from "@/shared/api/document-categories";
import {
  deleteDocument,
  deleteDocumentsBatch,
  indexDocument,
  listDocuments,
  uploadDocumentsBatch,
} from "@/shared/api/documents";
import {
  listKnowledgeBases,
  reindexKnowledgeBaseDocuments,
} from "@/shared/api/knowledge-bases";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import StatusTag from "@/shared/components/page/StatusTag.vue";
import { useTeamScopeStore } from "@/stores/team-scope";
import { isForbiddenError } from "@/shared/utils/error";
import type { DocumentCategorySummary } from "@/shared/types/document-category";
import type {
  DocumentLifecycleStatus,
  DocumentSummary,
} from "@/shared/types/document";
import type { KnowledgeBaseSummary } from "@/shared/types/knowledge-base";

type CategoryFilterKey = "all" | number;

interface CategoryNavItem {
  key: CategoryFilterKey;
  label: string;
  count: number | null;
  categoryId: number | null;
}

const route = useRoute();
const router = useRouter();
const teamScopeStore = useTeamScopeStore();

const knowledgeBase = ref<KnowledgeBaseSummary | null>(null);
const categories = ref<DocumentCategorySummary[]>([]);
const documents = ref<DocumentSummary[]>([]);
const pageLoading = ref(false);
const documentsLoading = ref(false);
const loadError = ref<unknown>(null);
const categoryActionLoading = ref(false);
const documentActionLoading = ref(false);
const uploadLoading = ref(false);
const selectedCategoryKey = ref<CategoryFilterKey>("all");
const selectedDocuments = ref<DocumentSummary[]>([]);
const fileInputRef = ref<HTMLInputElement | null>(null);

const documentQuery = reactive({
  keyword: "",
  status: "" as "" | DocumentLifecycleStatus,
  page: 1,
  pageSize: 10,
  total: 0,
});

const categoryNavItems = computed<CategoryNavItem[]>(() => {
  const items: CategoryNavItem[] = [
    {
      key: "all",
      label: "全部文档",
      count: knowledgeBase.value?.document_count ?? null,
      categoryId: null,
    },
  ];

  for (const category of categories.value) {
    items.push({
      key: category.id,
      label: category.name,
      count: category.document_count,
      categoryId: category.id,
    });
  }

  return items;
});

const isForbidden = computed(() => Boolean(loadError.value) && isForbiddenError(loadError.value));
const selectedCategory = computed(() =>
  typeof selectedCategoryKey.value === "number"
    ? categories.value.find((item) => item.id === selectedCategoryKey.value) ?? null
    : null,
);
const currentCategoryLabel = computed(() => selectedCategory.value?.name ?? "全部文档");
const selectedDocumentIds = computed(() => selectedDocuments.value.map((item) => item.id));
const hasDocumentSelection = computed(() => selectedDocuments.value.length > 0);
const pageTitle = computed(() => knowledgeBase.value?.name ?? "知识库详情");
const pageDescription = computed(() => knowledgeBase.value?.description?.trim() || "当前知识库用于统一管理分类、文档和索引状态。");
const summaryStats = computed(() => {
  if (!knowledgeBase.value) {
    return [];
  }

  return [
    { label: "文档总数", value: String(knowledgeBase.value.document_count) },
    { label: "已索引", value: String(knowledgeBase.value.indexed_document_count) },
    {
      label: "索引中",
      value: String(knowledgeBase.value.queued_document_count + knowledgeBase.value.processing_document_count),
    },
    { label: "待审核", value: String(knowledgeBase.value.pending_review_document_count) },
  ];
});

function getKnowledgeBaseId() {
  const raw = Number(route.params.knowledgeBaseId);
  return Number.isInteger(raw) && raw > 0 ? raw : null;
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "暂无";
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

function formatFileSize(size: number) {
  if (!Number.isFinite(size) || size <= 0) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB"];
  let value = size;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${value.toFixed(value >= 100 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function getDocumentTypeLabel(documentType: string | null) {
  if (!documentType) {
    return "未知";
  }

  return documentType.toUpperCase();
}

function getIndexStatusMeta(status: DocumentSummary["index_status"]) {
  const metaMap = {
    queued: { label: "排队中", type: "warning" as const },
    processing: { label: "处理中", type: "primary" as const },
    indexed: { label: "已索引", type: "success" as const },
    failed: { label: "失败", type: "danger" as const },
  };

  return metaMap[status];
}

function getLifecycleStatusMeta(status: DocumentLifecycleStatus) {
  const metaMap = {
    draft: { label: "草稿", type: "info" as const },
    pending_review: { label: "待审核", type: "warning" as const },
    published: { label: "已发布", type: "success" as const },
    archived: { label: "已归档", type: "info" as const },
  };

  return metaMap[status];
}

async function loadKnowledgeBaseSummary(knowledgeBaseId: number) {
  const teamId = teamScopeStore.selectedTeamId ?? undefined;
  const currentScopeItems = await listKnowledgeBases(teamId);
  const currentItem = currentScopeItems.find((item) => item.id === knowledgeBaseId);
  if (currentItem) {
    knowledgeBase.value = currentItem;
    return;
  }

  if (!teamId) {
    throw new Error("未找到对应知识库。");
  }

  const globalItems = await listKnowledgeBases();
  const fallbackItem = globalItems.find((item) => item.id === knowledgeBaseId);
  if (!fallbackItem) {
    throw new Error("未找到对应知识库。");
  }

  knowledgeBase.value = fallbackItem;
}

async function loadCategories(knowledgeBaseId: number) {
  categories.value = await listDocumentCategories(knowledgeBaseId);
  if (typeof selectedCategoryKey.value === "number") {
    const stillExists = categories.value.some((item) => item.id === selectedCategoryKey.value);
    if (!stillExists) {
      selectedCategoryKey.value = "all";
    }
  }
}

async function loadDocuments() {
  const knowledgeBaseId = getKnowledgeBaseId();
  if (!knowledgeBaseId) {
    loadError.value = new Error("知识库标识无效。");
    return;
  }

  documentsLoading.value = true;
  try {
    const response = await listDocuments({
      page: documentQuery.page,
      page_size: documentQuery.pageSize,
      keyword: documentQuery.keyword.trim() || undefined,
      team_id: teamScopeStore.selectedTeamId ?? undefined,
      knowledge_base_id: knowledgeBaseId,
      category_id:
        typeof selectedCategoryKey.value === "number" ? selectedCategoryKey.value : undefined,
      status: documentQuery.status || undefined,
    });
    documents.value = response.items;
    documentQuery.total = response.total;
    selectedDocuments.value = selectedDocuments.value.filter((item) =>
      response.items.some((doc) => doc.id === item.id),
    );
  } finally {
    documentsLoading.value = false;
  }
}

async function loadPage() {
  const knowledgeBaseId = getKnowledgeBaseId();
  if (!knowledgeBaseId) {
    loadError.value = new Error("知识库标识无效。");
    return;
  }

  pageLoading.value = true;
  loadError.value = null;
  try {
    await Promise.all([
      loadKnowledgeBaseSummary(knowledgeBaseId),
      loadCategories(knowledgeBaseId),
    ]);
    await loadDocuments();
  } catch (error) {
    loadError.value = error;
  } finally {
    pageLoading.value = false;
  }
}

function handleBack() {
  void router.push("/knowledge-bases");
}

function handleSelectCategory(key: CategoryFilterKey) {
  if (selectedCategoryKey.value === key) {
    return;
  }

  selectedCategoryKey.value = key;
  documentQuery.page = 1;
  void loadDocuments();
}

function handleSearch() {
  documentQuery.page = 1;
  void loadDocuments();
}

function resetSearch() {
  documentQuery.keyword = "";
  documentQuery.status = "";
  documentQuery.page = 1;
  void loadDocuments();
}

async function promptCategoryName(options: {
  title: string;
  initialValue?: string;
}) {
  try {
    const { value } = await ElMessageBox.prompt("请输入分类名称", options.title, {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      inputValue: options.initialValue ?? "",
      inputPattern: /\S+/,
      inputErrorMessage: "分类名称不能为空",
    });
    return value.trim();
  } catch {
    return null;
  }
}

async function handleCreateCategory() {
  const knowledgeBaseId = getKnowledgeBaseId();
  if (!knowledgeBaseId || categoryActionLoading.value) {
    return;
  }

  const name = await promptCategoryName({ title: "新建分类" });
  if (!name) {
    return;
  }

  categoryActionLoading.value = true;
  try {
    await createDocumentCategory({
      knowledge_base_id: knowledgeBaseId,
      name,
    });
    ElMessage.success(`已创建分类“${name}”。`);
    await loadCategories(knowledgeBaseId);
  } catch (error) {
    const message = error instanceof Error ? error.message : "创建分类失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    categoryActionLoading.value = false;
  }
}

async function handleRenameCategory(category: DocumentCategorySummary) {
  if (categoryActionLoading.value) {
    return;
  }

  const name = await promptCategoryName({
    title: `重命名“${category.name}”`,
    initialValue: category.name,
  });
  if (!name || name === category.name) {
    return;
  }

  categoryActionLoading.value = true;
  try {
    await updateDocumentCategory(category.id, { name });
    ElMessage.success(`已将分类更新为“${name}”。`);
    await loadCategories(category.knowledge_base_id);
    await loadDocuments();
  } catch (error) {
    const message = error instanceof Error ? error.message : "更新分类失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    categoryActionLoading.value = false;
  }
}

async function handleDeleteCategory(category: DocumentCategorySummary) {
  if (categoryActionLoading.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定删除分类“${category.name}”吗？已归属到该分类的文档会失去分类标记。`,
      "删除分类",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  categoryActionLoading.value = true;
  try {
    await deleteDocumentCategory(category.id);
    ElMessage.success(`已删除分类“${category.name}”。`);
    if (selectedCategoryKey.value === category.id) {
      selectedCategoryKey.value = "all";
    }
    await loadCategories(category.knowledge_base_id);
    await loadDocuments();
  } catch (error) {
    const message = error instanceof Error ? error.message : "删除分类失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    categoryActionLoading.value = false;
  }
}

function handleUploadClick() {
  if (!knowledgeBase.value || uploadLoading.value) {
    return;
  }

  fileInputRef.value?.click();
}

async function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  const files = Array.from(target.files ?? []);
  target.value = "";

  if (!knowledgeBase.value || files.length === 0) {
    return;
  }

  uploadLoading.value = true;
  try {
    await uploadDocumentsBatch({
      files,
      knowledgeBaseId: knowledgeBase.value.id,
      categoryId: selectedCategory.value?.id ?? null,
    });
    ElMessage.success(`已提交 ${files.length} 个文档的上传任务。`);
    documentQuery.page = 1;
    await Promise.all([
      loadKnowledgeBaseSummary(knowledgeBase.value.id),
      loadCategories(knowledgeBase.value.id),
      loadDocuments(),
    ]);
  } catch (error) {
    const message = error instanceof Error ? error.message : "上传文档失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    uploadLoading.value = false;
  }
}

function handleDocumentSelectionChange(items: DocumentSummary[]) {
  selectedDocuments.value = items;
}

async function handleDeleteOneDocument(document: DocumentSummary) {
  if (documentActionLoading.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定删除文档“${document.title}”吗？删除后不可恢复。`,
      "删除文档",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  documentActionLoading.value = true;
  try {
    await deleteDocument(document.id);
    ElMessage.success(`已删除文档“${document.title}”。`);
    if (knowledgeBase.value) {
      await Promise.all([
        loadKnowledgeBaseSummary(knowledgeBase.value.id),
        loadCategories(knowledgeBase.value.id),
        loadDocuments(),
      ]);
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "删除文档失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    documentActionLoading.value = false;
  }
}

async function handleBatchDeleteDocuments() {
  if (!hasDocumentSelection.value || documentActionLoading.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定删除已选中的 ${selectedDocuments.value.length} 个文档吗？删除后不可恢复。`,
      "批量删除文档",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  documentActionLoading.value = true;
  try {
    await deleteDocumentsBatch(selectedDocumentIds.value);
    selectedDocuments.value = [];
    ElMessage.success("已删除所选文档。");
    if (knowledgeBase.value) {
      await Promise.all([
        loadKnowledgeBaseSummary(knowledgeBase.value.id),
        loadCategories(knowledgeBase.value.id),
        loadDocuments(),
      ]);
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "批量删除失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    documentActionLoading.value = false;
  }
}

async function handleIndexDocument(document: DocumentSummary) {
  if (documentActionLoading.value) {
    return;
  }

  documentActionLoading.value = true;
  try {
    await indexDocument(document.id);
    ElMessage.success(`已提交“${document.title}”的重建索引任务。`);
    await loadDocuments();
  } catch (error) {
    const message = error instanceof Error ? error.message : "提交索引任务失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    documentActionLoading.value = false;
  }
}

async function handleReindexKnowledgeBase() {
  if (!knowledgeBase.value || documentActionLoading.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定重建知识库“${knowledgeBase.value.name}”的索引吗？该操作会重新提交全部文档的索引任务，处理中可能短暂影响检索结果。`,
      "重建知识库索引",
      {
        type: "warning",
        confirmButtonText: "继续重建",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  documentActionLoading.value = true;
  try {
    await reindexKnowledgeBaseDocuments(knowledgeBase.value.id);
    ElMessage.success(`已提交“${knowledgeBase.value.name}”的重建索引任务。`);
    await loadDocuments();
  } catch (error) {
    const message = error instanceof Error ? error.message : "提交重建索引任务失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    documentActionLoading.value = false;
  }
}

function handleOpenDocumentDetail(document: DocumentSummary) {
  if (!knowledgeBase.value) {
    return;
  }

  void router.push(`/knowledge-bases/${knowledgeBase.value.id}/documents/${document.id}`);
}

function handlePageChange(page: number) {
  documentQuery.page = page;
  void loadDocuments();
}

onMounted(() => {
  void loadPage();
});

watch(
  () => teamScopeStore.selectedTeamId,
  () => {
    selectedDocuments.value = [];
    documentQuery.page = 1;
    selectedCategoryKey.value = "all";
    void loadPage();
  },
);

watch(
  () => route.params.knowledgeBaseId,
  () => {
    selectedDocuments.value = [];
    documentQuery.page = 1;
    selectedCategoryKey.value = "all";
    void loadPage();
  },
);
</script>

<template>
  <section class="kb-detail-page">
    <header class="kb-detail-page__header">
      <div class="kb-detail-page__header-left">
        <button type="button" class="kb-detail-page__back" @click="handleBack">
          <el-icon><ArrowLeft /></el-icon>
          <span>返回</span>
        </button>
        <div class="kb-detail-page__divider" />
        <div v-if="knowledgeBase" class="kb-detail-page__title-group">
          <h1 class="kb-detail-page__toolbar-title">{{ pageTitle }}</h1>
          <span class="kb-detail-page__toolbar-meta">
            {{ teamScopeStore.selectedTeam?.name ?? "全部团队可见" }}
          </span>
          <span class="kb-detail-page__toolbar-meta">
            更新于 {{ formatDateTime(knowledgeBase.last_document_updated_at ?? knowledgeBase.updated_at) }}
          </span>
        </div>
      </div>

      <div v-if="knowledgeBase" class="kb-detail-page__header-right">
        <span
          v-for="item in summaryStats"
          :key="item.label"
          class="kb-detail-page__stat-chip"
        >
          {{ item.label }} {{ item.value }}
        </span>
        <el-button
          type="primary"
          plain
          size="small"
          :loading="documentActionLoading"
          :disabled="!knowledgeBase"
          @click="handleReindexKnowledgeBase"
        >
          <el-icon class="mr-2"><RefreshRight /></el-icon>
          重建索引
        </el-button>
      </div>
    </header>

    <AppLoading
      v-if="pageLoading"
      title="知识库详情加载中"
      description="正在准备分类与文档列表，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="loadError && !isForbidden"
      title="知识库详情加载失败"
      description="暂时无法获取知识库详情，请稍后重试。"
      :error="loadError"
      @retry="loadPage"
    />

    <AppError
      v-else-if="isForbidden"
      title="无权查看知识库详情"
      description="当前账号没有访问该知识库详情页的权限。"
      :error="loadError"
      :show-retry="false"
    />

    <template v-else-if="knowledgeBase">
      <section class="kb-detail-page__layout">
        <aside class="kb-sidebar">
          <div class="kb-sidebar__header">
            <div>
              <h2 class="kb-sidebar__title">文档分类</h2>
              <p class="kb-sidebar__hint">按分类筛选当前知识库中的文档。</p>
            </div>
            <el-button
              type="primary"
              link
              :disabled="categoryActionLoading"
              @click="handleCreateCategory"
            >
              <el-icon><CirclePlus /></el-icon>
            </el-button>
          </div>

          <div class="kb-sidebar__list">
            <div
              v-for="item in categoryNavItems"
              :key="String(item.key)"
              :class="[
                'kb-sidebar__item',
                selectedCategoryKey === item.key ? 'kb-sidebar__item--active' : '',
              ]"
              role="button"
              tabindex="0"
              @click="handleSelectCategory(item.key)"
              @keyup.enter="handleSelectCategory(item.key)"
            >
              <span class="kb-sidebar__item-main">
                <el-icon><Folder /></el-icon>
                <span class="kb-sidebar__item-label">{{ item.label }}</span>
              </span>

              <span class="kb-sidebar__item-side">
                <span v-if="item.count !== null" class="kb-sidebar__item-count">{{ item.count }}</span>
                <el-dropdown
                  v-if="item.categoryId"
                  trigger="click"
                  placement="bottom-end"
                  @command="(command) => {
                    const category = categories.find((entry) => entry.id === item.categoryId);
                    if (!category) {
                      return;
                    }
                    if (command === 'rename') {
                      void handleRenameCategory(category);
                      return;
                    }
                    if (command === 'delete') {
                      void handleDeleteCategory(category);
                    }
                  }"
                >
                  <button type="button" class="kb-sidebar__item-more" @click.stop>
                    <el-icon><MoreFilled /></el-icon>
                  </button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="rename">
                        <el-icon><EditPen /></el-icon>
                        <span>重命名</span>
                      </el-dropdown-item>
                      <el-dropdown-item command="delete">
                        <el-icon><Delete /></el-icon>
                        <span>删除</span>
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </span>
            </div>
          </div>
        </aside>

        <div class="kb-documents">
          <section class="kb-documents__toolbar">
            <div class="kb-documents__toolbar-copy">
              <h2 class="kb-documents__title">{{ currentCategoryLabel }}</h2>
              <p class="kb-documents__hint">管理当前分类下的文档、索引状态和内容预览。</p>
            </div>

            <div class="kb-documents__toolbar-actions">
              <el-input
                v-model="documentQuery.keyword"
                size="large"
                clearable
                placeholder="搜索文档标题..."
                class="kb-documents__search"
                @clear="handleSearch"
                @keyup.enter="handleSearch"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>

              <el-select
                v-model="documentQuery.status"
                size="large"
                clearable
                placeholder="发布状态"
                class="kb-documents__status"
                @change="handleSearch"
              >
                <el-option label="草稿" value="draft" />
                <el-option label="待审核" value="pending_review" />
                <el-option label="已发布" value="published" />
                <el-option label="已归档" value="archived" />
              </el-select>

              <el-button @click="resetSearch">重置</el-button>
              <el-button
                type="danger"
                plain
                :disabled="!hasDocumentSelection || documentActionLoading"
                @click="handleBatchDeleteDocuments"
              >
                批量删除
              </el-button>
              <el-button
                type="primary"
                :loading="uploadLoading"
                @click="handleUploadClick"
              >
                <el-icon class="mr-2"><UploadFilled /></el-icon>
                上传文档
              </el-button>
              <input
                ref="fileInputRef"
                class="kb-documents__hidden-input"
                type="file"
                multiple
                @change="handleFileChange"
              >
            </div>
          </section>

          <section class="kb-documents__content">
            <AppEmpty
              v-if="!documentsLoading && documents.length === 0"
              title="当前没有可展示的文档"
              description="可以调整筛选条件，或直接上传新文档到当前知识库。"
            >
              <el-button link type="primary" @click="handleUploadClick">上传文档</el-button>
            </AppEmpty>

            <el-table
              v-else
              :data="documents"
              v-loading="documentsLoading"
              row-key="id"
              class="kb-documents__table"
              @selection-change="handleDocumentSelectionChange"
            >
              <el-table-column type="selection" width="48" />
              <el-table-column label="文档标题" min-width="280" show-overflow-tooltip>
                <template #default="{ row }">
                  <div class="kb-documents__name-cell">
                    <el-icon><Document /></el-icon>
                    <div class="kb-documents__name-copy">
                      <strong>{{ row.title }}</strong>
                      <span>{{ row.category_name || "未分配分类" }}</span>
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="类型" width="100">
                <template #default="{ row }">
                  <span>{{ getDocumentTypeLabel(row.document_type) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="大小" width="110">
                <template #default="{ row }">
                  <span>{{ formatFileSize(row.size) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="索引状态" width="120">
                <template #default="{ row }">
                  <StatusTag
                    :label="getIndexStatusMeta(row.index_status).label"
                    :type="getIndexStatusMeta(row.index_status).type"
                  />
                </template>
              </el-table-column>
              <el-table-column label="发布状态" width="120">
                <template #default="{ row }">
                  <StatusTag
                    :label="getLifecycleStatusMeta(row.status).label"
                    :type="getLifecycleStatusMeta(row.status).type"
                  />
                </template>
              </el-table-column>
              <el-table-column label="最后更新" width="180">
                <template #default="{ row }">
                  <span>{{ formatDateTime(row.updated_at) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="220" fixed="right" align="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="handleOpenDocumentDetail(row)">
                    <el-icon><View /></el-icon>
                    <span>查看</span>
                  </el-button>
                  <el-button link type="primary" @click="handleIndexDocument(row)">
                    <el-icon><RefreshRight /></el-icon>
                    <span>索引</span>
                  </el-button>
                  <el-button link type="danger" @click="handleDeleteOneDocument(row)">
                    <el-icon><Delete /></el-icon>
                    <span>删除</span>
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </section>

          <footer class="kb-documents__footer">
            <el-pagination
              background
              layout="total, prev, pager, next"
              :total="documentQuery.total"
              :page-size="documentQuery.pageSize"
              :current-page="documentQuery.page"
              @current-change="handlePageChange"
            />
          </footer>
        </div>
      </section>
    </template>

  </section>
</template>

<style scoped>
.kb-detail-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.kb-detail-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 56px;
  padding: 0 16px;
  border: 1px solid #dbe2ea;
  border-radius: 12px;
  background: #fff;
}

.kb-detail-page__header-left,
.kb-detail-page__header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.kb-detail-page__back {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  color: #475569;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  padding: 0;
}

.kb-detail-page__back:hover {
  color: #2563eb;
}

.kb-detail-page__divider {
  width: 1px;
  height: 20px;
  background: #e2e8f0;
}

.kb-detail-page__title-group {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.kb-detail-page__toolbar-title {
  margin: 0;
  max-width: 320px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  color: #0f172a;
  font-size: 16px;
  font-weight: 600;
}

.kb-detail-page__toolbar-meta {
  color: #64748b;
  font-size: 13px;
  white-space: nowrap;
}

.kb-detail-page__stat-chip {
  border-radius: 999px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  font-weight: 500;
  padding: 6px 10px;
}

.kb-detail-page__layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 20px;
}

.kb-sidebar,
.kb-documents {
  border: 1px solid #dbe2ea;
  border-radius: 22px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.kb-sidebar {
  display: flex;
  flex-direction: column;
  min-height: 680px;
}

.kb-sidebar__header,
.kb-documents__toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px;
}

.kb-sidebar__title,
.kb-documents__title {
  margin: 0;
  color: #0f172a;
  font-size: 17px;
  font-weight: 700;
}

.kb-sidebar__hint,
.kb-documents__hint {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.kb-sidebar__list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  padding: 0 12px 14px;
}

.kb-sidebar__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid transparent;
  border-radius: 14px;
  background: transparent;
  color: #334155;
  cursor: pointer;
  padding: 12px 14px;
  text-align: left;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease;
}

.kb-sidebar__item:hover {
  background: #f8fafc;
}

.kb-sidebar__item--active {
  border-color: #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
}

.kb-sidebar__item-main,
.kb-sidebar__item-side {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.kb-sidebar__item-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 600;
}

.kb-sidebar__item-count {
  color: #94a3b8;
  font-size: 12px;
  font-weight: 600;
}

.kb-sidebar__item-more {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  padding: 4px;
}

.kb-sidebar__item-more:hover {
  background: rgba(255, 255, 255, 0.9);
  color: #2563eb;
}

.kb-documents {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.kb-documents__toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}

.kb-documents__search {
  width: 280px;
}

.kb-documents__status {
  width: 150px;
}

.kb-documents__content {
  flex: 1;
  padding: 0 20px;
}

.kb-documents__table {
  width: 100%;
}

.kb-documents__name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.kb-documents__name-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.kb-documents__name-copy strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-documents__name-copy span {
  color: #64748b;
  font-size: 12px;
}

.kb-documents__footer {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #f1f5f9;
  padding: 16px 20px 20px;
}

.kb-documents__hidden-input {
  display: none;
}

.kb-preview {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.kb-preview__meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.kb-preview__meta > div {
  display: flex;
  min-height: 84px;
  flex-direction: column;
  justify-content: center;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
  padding: 14px;
}

.kb-preview__label {
  color: #64748b;
  font-size: 12px;
}

.kb-preview__content {
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #ffffff;
  color: #0f172a;
  font-family: Consolas, "SFMono-Regular", Monaco, monospace;
  font-size: 13px;
  line-height: 1.75;
  margin: 0;
  padding: 18px;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 1280px) {
  .kb-detail-page__layout {
    grid-template-columns: 1fr;
  }

  .kb-sidebar {
    min-height: auto;
  }
}

@media (max-width: 900px) {
  .kb-detail-page__header,
  .kb-detail-page__header-left,
  .kb-detail-page__header-right,
  .kb-sidebar__header,
  .kb-documents__toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .kb-detail-page__toolbar-title {
    max-width: none;
  }

  .kb-documents__toolbar-actions {
    justify-content: stretch;
  }

  .kb-documents__search,
  .kb-documents__status {
    width: 100%;
  }

  .kb-preview__meta {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .kb-detail-page__stats {
    grid-template-columns: 1fr;
  }
}
</style>
