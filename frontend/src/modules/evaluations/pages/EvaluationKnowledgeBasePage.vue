<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Delete, Plus, RefreshRight, Search } from "@element-plus/icons-vue";

import AdminDataTable from "@/app/components/admin/AdminDataTable.vue";
import AdminDialog from "@/app/components/admin/AdminDialog.vue";
import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminPagination from "@/app/components/admin/AdminPagination.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import {
  createEvaluationKnowledgeBase,
  listEvaluationKnowledgeBases,
} from "@/shared/api/evaluations";
import { bulkActionKnowledgeBases, updateKnowledgeBase } from "@/shared/api/knowledge-bases";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import { useTeamScopeStore } from "@/stores/team-scope";
import type {
  KnowledgeBaseBulkAction,
  KnowledgeBaseListItem,
  KnowledgeBaseStatus,
} from "@/shared/types/knowledge-base";

interface EvaluationKnowledgeBaseRow {
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

const loading = ref(false);
const hasLoadedData = ref(false);
const loadError = ref<unknown>(null);
const knowledgeBases = ref<KnowledgeBaseListItem[]>([]);
const searchKeyword = ref("");
const createDialogVisible = ref(false);
const createLoading = ref(false);
const dialogMode = ref<"create" | "edit">("create");
const editingKnowledgeBaseId = ref<number | null>(null);
const selectedKnowledgeBaseIds = ref<Set<number>>(new Set());
const bulkActionLoading = ref<KnowledgeBaseBulkAction | null>(null);
const knowledgeBaseTableRef = ref<{ clearSelection: () => void } | null>(null);
let loadRequestSeq = 0;

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
});
const form = reactive({
  name: "",
  description: "",
});
const dialogTitle = computed(() =>
  dialogMode.value === "create" ? "创建评测基准库" : "编辑评测基准库信息",
);
const dialogActionText = computed(() => (dialogMode.value === "create" ? "创建" : "保存"));

const rows = computed<EvaluationKnowledgeBaseRow[]>(() =>
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
const isSearchActive = computed(() => searchKeyword.value.trim().length > 0);
const selectedKnowledgeBaseCount = computed(() => selectedKnowledgeBaseIds.value.size);

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

function getStatusLabel(status: KnowledgeBaseStatus) {
  if (status === "available") {
    return "可用";
  }
  if (status === "indexing") {
    return "索引中";
  }
  if (status === "error") {
    return "异常";
  }
  return "空库";
}

function getStatusType(status: KnowledgeBaseStatus) {
  if (status === "available") {
    return "success";
  }
  if (status === "indexing") {
    return "warning";
  }
  if (status === "error") {
    return "danger";
  }
  return "info";
}

async function loadEvaluationKnowledgeBases() {
  const requestSeq = ++loadRequestSeq;
  loading.value = true;
  loadError.value = null;

  try {
    const result = await listEvaluationKnowledgeBases({
      team_id: teamScopeStore.selectedTeamId ?? undefined,
      keyword: searchKeyword.value.trim() || undefined,
      page: pagination.page,
      page_size: pagination.pageSize,
    });
    if (requestSeq !== loadRequestSeq) {
      return;
    }
    knowledgeBases.value = result.items;
    selectedKnowledgeBaseIds.value = new Set();
    pagination.total = result.total;
    pagination.page = result.page;
    pagination.pageSize = result.page_size;
    hasLoadedData.value = true;
  } catch (error) {
    if (requestSeq !== loadRequestSeq) {
      return;
    }
    if (hasLoadedData.value) {
      ElMessage.error(error instanceof Error ? error.message : "评测基准库刷新失败，请稍后重试。");
    } else {
      loadError.value = error;
    }
  } finally {
    if (requestSeq === loadRequestSeq) {
      loading.value = false;
    }
  }
}

function refreshFromFirstPage() {
  pagination.page = 1;
  void loadEvaluationKnowledgeBases();
}

function resetSearch() {
  searchKeyword.value = "";
  refreshFromFirstPage();
}

function openCreateDialog() {
  dialogMode.value = "create";
  editingKnowledgeBaseId.value = null;
  form.name = "";
  form.description = "";
  createDialogVisible.value = true;
}

function openEditDialog(row: EvaluationKnowledgeBaseRow) {
  dialogMode.value = "edit";
  editingKnowledgeBaseId.value = row.id;
  form.name = row.name;
  form.description = row.description === "暂无说明" ? "" : row.description;
  createDialogVisible.value = true;
}

async function submitKnowledgeBaseForm() {
  const name = form.name.trim();
  const description = form.description.trim();
  const teamId = teamScopeStore.selectedTeamId;
  if (!name) {
    ElMessage.warning("请输入评测基准库名称。");
    return;
  }
  if (!teamId) {
    ElMessage.warning("请先选择团队。");
    return;
  }

  createLoading.value = true;
  try {
    if (dialogMode.value === "create") {
      await createEvaluationKnowledgeBase({
        name,
        description: description || null,
        team_id: teamId,
      });
      ElMessage.success("已创建评测基准库。");
    } else if (editingKnowledgeBaseId.value) {
      await updateKnowledgeBase(editingKnowledgeBaseId.value, {
        name,
        description: description || null,
      });
      ElMessage.success("已保存评测基准库信息。");
    }
    createDialogVisible.value = false;
    refreshFromFirstPage();
  } finally {
    createLoading.value = false;
  }
}

function openKnowledgeBaseDetail(knowledgeBaseId: number) {
  void router.push(`/knowledge-bases/${knowledgeBaseId}`);
}

function handleKnowledgeBaseSelectionChange(selection: EvaluationKnowledgeBaseRow[]) {
  selectedKnowledgeBaseIds.value = new Set(selection.map((item) => item.id));
}

async function handleBulkAction(action: KnowledgeBaseBulkAction) {
  if (selectedKnowledgeBaseIds.value.size === 0) {
    return;
  }

  const knowledgeBaseIds = Array.from(selectedKnowledgeBaseIds.value);
  if (action === "delete") {
    try {
      await ElMessageBox.confirm(
        `将删除已选的 ${knowledgeBaseIds.length} 个评测基准库及其文档。`,
        "批量删除评测基准库",
        {
          type: "warning",
          confirmButtonText: "删除所选",
          cancelButtonText: "取消",
        },
      );
    } catch {
      return;
    }
  }

  bulkActionLoading.value = action;
  try {
    const result = await bulkActionKnowledgeBases(knowledgeBaseIds, action);
    selectedKnowledgeBaseIds.value = new Set();
    knowledgeBaseTableRef.value?.clearSelection();
    if (result.failed.length > 0) {
      ElMessage.warning(`已处理 ${result.affected} 个，${result.failed.length} 个失败。`);
    } else {
      ElMessage.success(`已处理 ${result.affected} 个评测基准库。`);
    }
    await loadEvaluationKnowledgeBases();
  } finally {
    bulkActionLoading.value = null;
  }
}

function handlePageChange(page: number) {
  pagination.page = page;
  void loadEvaluationKnowledgeBases();
}

function handlePageSizeChange(pageSize: number) {
  pagination.pageSize = pageSize;
  pagination.page = 1;
  void loadEvaluationKnowledgeBases();
}

onMounted(() => {
  void loadEvaluationKnowledgeBases();
});

watch(
  () => teamScopeStore.selectedTeamId,
  () => {
    refreshFromFirstPage();
  },
);
</script>

<template>
  <div class="kb-list-page evaluation-kb-page">
    <AdminListPanel>
      <AdminTableToolbar>
        <template #left>
          <el-input
            v-model="searchKeyword"
            clearable
            class="evaluation-kb-page__search"
            placeholder="搜索评测基准库名称或说明"
            :prefix-icon="Search"
            @keyup.enter="refreshFromFirstPage"
            @clear="refreshFromFirstPage"
          />
          <el-button
            :loading="loading"
            :icon="RefreshRight"
            @click="loadEvaluationKnowledgeBases"
          >
            刷新
          </el-button>
        </template>

        <template #right>
          <span class="kb-list-page__toolbar-note">
            共 {{ pagination.total }} 个评测基准库
          </span>
          <el-button
            :disabled="selectedKnowledgeBaseCount === 0"
            :loading="bulkActionLoading === 'enable'"
            @click="handleBulkAction('enable')"
          >
            批量启用{{ selectedKnowledgeBaseCount ? ` (${selectedKnowledgeBaseCount})` : "" }}
          </el-button>
          <el-button
            :disabled="selectedKnowledgeBaseCount === 0"
            :loading="bulkActionLoading === 'disable'"
            @click="handleBulkAction('disable')"
          >
            批量停用
          </el-button>
          <el-button
            :disabled="selectedKnowledgeBaseCount === 0"
            :loading="bulkActionLoading === 'reindex'"
            @click="handleBulkAction('reindex')"
          >
            批量重建索引
          </el-button>
          <el-button
            type="danger"
            plain
            :icon="Delete"
            :disabled="selectedKnowledgeBaseCount === 0"
            :loading="bulkActionLoading === 'delete'"
            @click="handleBulkAction('delete')"
          >
            批量删除
          </el-button>
          <el-button
            type="primary"
            :icon="Plus"
            @click="openCreateDialog"
          >
            创建评测基准库
          </el-button>
        </template>
      </AdminTableToolbar>

      <AppError
        v-if="loadError"
        title="评测基准库加载失败"
        description="请检查服务状态或稍后重试。"
        @retry="loadEvaluationKnowledgeBases"
      />
      <AppLoading
        v-else-if="loading && !hasLoadedData"
        text="正在加载评测基准库..."
      />
      <AppEmpty
        v-else-if="!loading && rows.length === 0"
        :title="isSearchActive ? '没有匹配的评测基准库' : '还没有评测基准库'"
        :description="isSearchActive ? '换个关键词再试一次。' : '创建基准库并上传稳定文档后，就可以绑定评测集。'"
      >
        <template #actions>
          <el-button
            v-if="isSearchActive"
            @click="resetSearch"
          >
            清空搜索
          </el-button>
          <el-button
            v-else
            type="primary"
            :icon="Plus"
            @click="openCreateDialog"
          >
            创建评测基准库
          </el-button>
        </template>
      </AppEmpty>

      <template v-else>
        <AdminDataTable
          ref="knowledgeBaseTableRef"
          :data="rows"
          table-class="kb-list-page__table"
          @selection-change="handleKnowledgeBaseSelectionChange"
        >
          <el-table-column
            type="selection"
            width="46"
            reserve-selection
          />
          <el-table-column
            label="名称"
            min-width="240"
          >
            <template #default="{ row }">
              <button
                type="button"
                class="kb-list-page__name-button"
                @click="openKnowledgeBaseDetail(row.id)"
              >
                {{ row.name }}
              </button>
              <p class="kb-list-page__description">
                {{ row.description }}
              </p>
            </template>
          </el-table-column>
          <el-table-column
            label="状态"
            width="110"
          >
            <template #default="{ row }">
              <el-tag
                :type="getStatusType(row.status)"
                effect="light"
              >
                {{ getStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="文档"
            width="190"
          >
            <template #default="{ row }">
              <div class="kb-list-page__metric">
                {{ row.documentCount }} 个文档
              </div>
              <div class="kb-list-page__metric-note">
                已索引 {{ row.indexedDocumentCount }}，待处理 {{ row.pendingDocumentCount }}
              </div>
            </template>
          </el-table-column>
          <el-table-column
            label="更新时间"
            prop="updateTime"
            width="180"
          />
          <el-table-column
            label="操作"
            width="190"
            fixed="right"
          >
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                @click="openKnowledgeBaseDetail(row.id)"
              >
                管理文档
              </el-button>
              <el-button
                link
                type="primary"
                @click="openEditDialog(row)"
              >
                编辑信息
              </el-button>
            </template>
          </el-table-column>
        </AdminDataTable>

        <AdminPagination
          :current-page="pagination.page"
          :page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="pagination.total"
          @page-change="handlePageChange"
          @page-size-change="handlePageSizeChange"
        />
      </template>
    </AdminListPanel>

    <AdminDialog
      v-model="createDialogVisible"
      :title="dialogTitle"
      width="520px"
      :loading="createLoading"
      :close-on-click-modal="!createLoading"
    >
      <el-alert
        class="kb-list-page__dialog-alert"
        :title="dialogMode === 'create'
          ? '评测基准库用于沉淀稳定的评测数据来源。完成文档和索引准备后，建议保持内容稳定；如需调整数据范围，可创建新的基准库版本。'
          : '这里只修改评测基准库的名称和说明，不会改变文档、切片或索引。'"
        type="info"
        show-icon
        :closable="false"
      />
      <el-form
        label-position="top"
        @submit.prevent
      >
        <el-form-item
          label="名称"
          required
        >
          <el-input
            v-model="form.name"
            maxlength="100"
            show-word-limit
            placeholder="例如：客服问答基准库 v1"
          />
        </el-form-item>
        <el-form-item label="说明">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="说明该基准库覆盖的文档范围、版本和用途"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button
          :disabled="createLoading"
          @click="createDialogVisible = false"
        >
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="createLoading"
          @click="submitKnowledgeBaseForm"
        >
          {{ dialogActionText }}
        </el-button>
      </template>
    </AdminDialog>
  </div>
</template>

<style scoped>
.kb-list-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.evaluation-kb-page__search {
  width: 320px;
}

.kb-list-page__toolbar-note,
.kb-list-page__muted,
.kb-list-page__metric-note,
.kb-list-page__description {
  color: var(--admin-text-subtle);
}

.kb-list-page__toolbar-note {
  font-size: 13px;
}

.kb-list-page__name-button {
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--admin-text-primary);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.kb-list-page__name-button:hover {
  color: var(--admin-primary);
}

.kb-list-page__description {
  margin: 4px 0 0;
  display: -webkit-box;
  overflow: hidden;
  font-size: 12px;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.kb-list-page__metric {
  color: var(--admin-text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.kb-list-page__metric-note {
  margin-top: 4px;
  font-size: 12px;
}

.kb-list-page__table :deep(.el-table__cell) {
  vertical-align: top;
}

.kb-list-page__dialog-alert {
  margin-bottom: 16px;
}

@media (max-width: 768px) {
  .evaluation-kb-page__search {
    width: 100%;
  }
}
</style>
