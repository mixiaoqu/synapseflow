<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Plus, RefreshRight, Search } from "@element-plus/icons-vue";

import AdminDataTable from "@/app/components/admin/AdminDataTable.vue";
import AdminDialog from "@/app/components/admin/AdminDialog.vue";
import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminPagination from "@/app/components/admin/AdminPagination.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import {
  createEvaluationKnowledgeBase,
  createEvalDataset,
  listEvalDatasets,
  listEvaluationKnowledgeBases,
  updateEvalDataset,
} from "@/shared/api/evaluations";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import { useTeamScopeStore } from "@/stores/team-scope";
import type {
  EvalDataset,
  EvalDatasetStatus,
} from "@/modules/evaluations/types";
import type { KnowledgeBaseListItem } from "@/shared/types/knowledge-base";

interface EvalDatasetRow {
  id: number;
  name: string;
  description: string;
  knowledgeBaseId: number;
  knowledgeBaseName: string;
  version: string;
  status: EvalDatasetStatus;
  updateTime: string;
}

const router = useRouter();
const teamScopeStore = useTeamScopeStore();

const loading = ref(false);
const hasLoadedData = ref(false);
const loadError = ref<unknown>(null);
const datasets = ref<EvalDataset[]>([]);
const evaluationKnowledgeBases = ref<KnowledgeBaseListItem[]>([]);
const searchKeyword = ref("");
const dialogVisible = ref(false);
const dialogLoading = ref(false);
const knowledgeBaseDialogVisible = ref(false);
const knowledgeBaseCreating = ref(false);
const dialogMode = ref<"create" | "edit">("create");
const editingDatasetId = ref<number | null>(null);
const selectedDatasetIds = ref<Set<number>>(new Set());
const datasetTableRef = ref<{ clearSelection: () => void } | null>(null);
let loadRequestSeq = 0;

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
});
const form = reactive({
  name: "",
  description: "",
  knowledgeBaseId: null as number | null,
  version: "v1",
  status: "draft" as EvalDatasetStatus,
});
const knowledgeBaseForm = reactive({
  name: "",
  description: "",
});

const knowledgeBaseNameById = computed(() => {
  const map = new Map<number, string>();
  for (const item of evaluationKnowledgeBases.value) {
    map.set(item.id, item.name);
  }
  return map;
});
const rows = computed<EvalDatasetRow[]>(() =>
  datasets.value.map((item) => ({
    id: item.id,
    name: item.name,
    description: item.description?.trim() || "暂无说明",
    knowledgeBaseId: item.knowledge_base_id,
    knowledgeBaseName: knowledgeBaseNameById.value.get(item.knowledge_base_id) ?? `#${item.knowledge_base_id}`,
    version: item.version,
    status: item.status,
    updateTime: formatDateTime(item.updated_at),
  })),
);
const isSearchActive = computed(() => searchKeyword.value.trim().length > 0);
const dialogTitle = computed(() => (dialogMode.value === "create" ? "创建评测集" : "编辑评测集信息"));
const dialogActionText = computed(() => (dialogMode.value === "create" ? "创建" : "保存"));

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

function getStatusLabel(status: EvalDatasetStatus) {
  if (status === "active") {
    return "启用";
  }
  if (status === "archived") {
    return "归档";
  }
  return "草稿";
}

function getStatusType(status: EvalDatasetStatus) {
  if (status === "active") {
    return "success";
  }
  if (status === "archived") {
    return "info";
  }
  return "warning";
}

async function loadEvaluationKnowledgeBases() {
  const result = await listEvaluationKnowledgeBases({
    team_id: teamScopeStore.selectedTeamId ?? undefined,
    page: 1,
    page_size: 100,
  });
  evaluationKnowledgeBases.value = result.items;
}

async function loadDatasets() {
  const requestSeq = ++loadRequestSeq;
  loading.value = true;
  loadError.value = null;

  try {
    const [datasetResult] = await Promise.all([
      listEvalDatasets({
        keyword: searchKeyword.value.trim() || undefined,
        page: pagination.page,
        page_size: pagination.pageSize,
      }),
      loadEvaluationKnowledgeBases(),
    ]);
    if (requestSeq !== loadRequestSeq) {
      return;
    }
    datasets.value = datasetResult.items;
    selectedDatasetIds.value = new Set();
    pagination.total = datasetResult.total;
    pagination.page = datasetResult.page;
    pagination.pageSize = datasetResult.page_size;
    hasLoadedData.value = true;
  } catch (error) {
    if (requestSeq !== loadRequestSeq) {
      return;
    }
    if (hasLoadedData.value) {
      ElMessage.error(error instanceof Error ? error.message : "评测集刷新失败，请稍后重试。");
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
  void loadDatasets();
}

function resetSearch() {
  searchKeyword.value = "";
  refreshFromFirstPage();
}

function resetForm() {
  form.name = "";
  form.description = "";
  form.knowledgeBaseId = null;
  form.version = "v1";
  form.status = "draft";
  editingDatasetId.value = null;
}

function openCreateDialog() {
  dialogMode.value = "create";
  resetForm();
  dialogVisible.value = true;
  if (evaluationKnowledgeBases.value.length === 0) {
    void loadEvaluationKnowledgeBases();
  }
}

function openEditDialog(row: EvalDatasetRow) {
  dialogMode.value = "edit";
  editingDatasetId.value = row.id;
  form.name = row.name;
  form.description = row.description === "暂无说明" ? "" : row.description;
  form.knowledgeBaseId = row.knowledgeBaseId;
  form.version = row.version;
  form.status = row.status;
  dialogVisible.value = true;
}

function openCreateKnowledgeBaseDialog() {
  if (!teamScopeStore.selectedTeamId) {
    ElMessage.warning("请先选择团队。");
    return;
  }
  knowledgeBaseForm.name = "";
  knowledgeBaseForm.description = "";
  knowledgeBaseDialogVisible.value = true;
}

async function submitKnowledgeBaseForm() {
  const name = knowledgeBaseForm.name.trim();
  if (!name || !teamScopeStore.selectedTeamId) {
    ElMessage.warning(name ? "请先选择团队。" : "请输入测试知识库名称。");
    return;
  }
  knowledgeBaseCreating.value = true;
  try {
    const knowledgeBase = await createEvaluationKnowledgeBase({
      name,
      description: knowledgeBaseForm.description.trim() || null,
      team_id: teamScopeStore.selectedTeamId,
    });
    await loadEvaluationKnowledgeBases();
    form.knowledgeBaseId = knowledgeBase.id;
    knowledgeBaseDialogVisible.value = false;
    ElMessage.success("已创建并绑定测试知识库。");
  } finally {
    knowledgeBaseCreating.value = false;
  }
}

async function submitDatasetForm() {
  const name = form.name.trim();
  const description = form.description.trim();
  const version = form.version.trim();
  if (!name) {
    ElMessage.warning("请输入评测集名称。");
    return;
  }
  if (!version) {
    ElMessage.warning("请输入评测集版本。");
    return;
  }
  if (!form.knowledgeBaseId) {
    ElMessage.warning("请选择绑定的测试知识库。");
    return;
  }

  dialogLoading.value = true;
  try {
    const payload = {
      name,
      description: description || null,
      knowledge_base_id: form.knowledgeBaseId,
      version,
      status: form.status,
    };
    if (dialogMode.value === "create") {
      await createEvalDataset(payload);
      ElMessage.success("已创建评测集。");
    } else if (editingDatasetId.value) {
      await updateEvalDataset(editingDatasetId.value, payload);
      ElMessage.success("已保存评测集信息。");
    }
    dialogVisible.value = false;
    refreshFromFirstPage();
  } finally {
    dialogLoading.value = false;
  }
}

function openDatasetDetail(datasetId: number) {
  void router.push(`/evaluations/datasets/${datasetId}`);
}

function handleDatasetSelectionChange(selection: EvalDatasetRow[]) {
  selectedDatasetIds.value = new Set(selection.map((item) => item.id));
}

function handlePageChange(page: number) {
  pagination.page = page;
  void loadDatasets();
}

function handlePageSizeChange(pageSize: number) {
  pagination.pageSize = pageSize;
  pagination.page = 1;
  void loadDatasets();
}

onMounted(() => {
  void loadDatasets();
});
</script>

<template>
  <div class="evaluation-list-page">
    <AdminListPanel>
      <AdminTableToolbar>
        <template #left>
          <el-input
            v-model="searchKeyword"
            clearable
            class="evaluation-list-page__search"
            placeholder="搜索评测集名称或说明"
            :prefix-icon="Search"
            @keyup.enter="refreshFromFirstPage"
            @clear="refreshFromFirstPage"
          />
          <el-button
            :loading="loading"
            :icon="RefreshRight"
            @click="loadDatasets"
          >
            刷新
          </el-button>
        </template>

        <template #right>
          <span class="evaluation-list-page__toolbar-note">
            共 {{ pagination.total }} 个评测集
          </span>
          <el-button
            type="primary"
            :icon="Plus"
            @click="openCreateDialog"
          >
            创建评测集
          </el-button>
        </template>
      </AdminTableToolbar>

      <AppError
        v-if="loadError"
        title="评测集加载失败"
        description="请检查服务状态或稍后重试。"
        @retry="loadDatasets"
      />
      <AppLoading
        v-else-if="loading && !hasLoadedData"
        text="正在加载评测集..."
      />
      <AppEmpty
        v-else-if="!loading && rows.length === 0"
        :title="isSearchActive ? '没有匹配的评测集' : '还没有评测集'"
        :description="isSearchActive ? '换个关键词再试一次。' : '创建评测集并绑定评测基准库后，就可以维护用例。'"
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
            创建评测集
          </el-button>
        </template>
      </AppEmpty>

      <template v-else>
        <AdminDataTable
          ref="datasetTableRef"
          :data="rows"
          table-class="evaluation-list-page__table"
          @selection-change="handleDatasetSelectionChange"
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
                class="evaluation-list-page__name-button"
                @click="openDatasetDetail(row.id)"
              >
                {{ row.name }}
              </button>
              <p class="evaluation-list-page__description">
                {{ row.description }}
              </p>
            </template>
          </el-table-column>
          <el-table-column
            label="评测基准库"
            min-width="180"
          >
            <template #default="{ row }">
              <span class="evaluation-list-page__metric">
                {{ row.knowledgeBaseName }}
              </span>
            </template>
          </el-table-column>
          <el-table-column
            label="版本"
            width="100"
            prop="version"
          />
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
                @click="openDatasetDetail(row.id)"
              >
                进入详情
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
      v-model="dialogVisible"
      :title="dialogTitle"
      width="560px"
      :loading="dialogLoading"
      :close-on-click-modal="!dialogLoading"
    >
      <el-alert
        class="evaluation-list-page__dialog-alert"
        :title="dialogMode === 'create'
          ? '评测集创建后会绑定一个测试知识库。用例中的期望证据均来自该知识库。'
          : '这里只修改评测集名称、说明、版本和状态；绑定的测试知识库保持不变。'"
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
            placeholder="例如：客服问答回归集 v1"
          />
        </el-form-item>
        <el-form-item label="说明">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="说明该评测集覆盖的问题范围和验收目的"
          />
        </el-form-item>
        <el-form-item
          label="测试知识库"
          required
        >
          <el-select
            v-model="form.knowledgeBaseId"
            class="w-full"
            filterable
            :disabled="dialogMode === 'edit'"
            placeholder="请选择测试知识库"
          >
            <el-option
              v-for="item in evaluationKnowledgeBases"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
          <el-button
            v-if="dialogMode === 'create'"
            link
            type="primary"
            :icon="Plus"
            class="evaluation-list-page__create-knowledge-base"
            @click="openCreateKnowledgeBaseDialog"
          >
            新建测试知识库
          </el-button>
        </el-form-item>
        <div class="evaluation-list-page__form-grid">
          <el-form-item
            label="版本"
            required
          >
            <el-input
              v-model="form.version"
              maxlength="50"
              placeholder="v1"
            />
          </el-form-item>
          <el-form-item label="状态">
            <el-select
              v-model="form.status"
              class="w-full"
            >
              <el-option
                label="草稿"
                value="draft"
              />
              <el-option
                label="启用"
                value="active"
              />
              <el-option
                label="归档"
                value="archived"
              />
            </el-select>
          </el-form-item>
        </div>
      </el-form>
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
          @click="submitDatasetForm"
        >
          {{ dialogActionText }}
        </el-button>
      </template>
    </AdminDialog>

    <AdminDialog
      v-model="knowledgeBaseDialogVisible"
      title="新建测试知识库"
      width="520px"
      :loading="knowledgeBaseCreating"
      :close-on-click-modal="!knowledgeBaseCreating"
    >
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="名称" required>
          <el-input v-model="knowledgeBaseForm.name" maxlength="100" show-word-limit placeholder="例如：客服测试知识库 v1" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="knowledgeBaseForm.description" type="textarea" :rows="4" maxlength="500" show-word-limit placeholder="说明该知识库覆盖的文档范围" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="knowledgeBaseCreating" @click="knowledgeBaseDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="knowledgeBaseCreating" @click="submitKnowledgeBaseForm">创建并选择</el-button>
      </template>
    </AdminDialog>
  </div>
</template>

<style scoped>
.evaluation-list-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.evaluation-list-page__search {
  width: 320px;
}

.evaluation-list-page__toolbar-note,
.evaluation-list-page__description {
  color: var(--admin-text-subtle);
}

.evaluation-list-page__toolbar-note {
  font-size: 13px;
}

.evaluation-list-page__name-button {
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--admin-text-primary);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.evaluation-list-page__name-button:hover {
  color: var(--admin-primary);
}

.evaluation-list-page__description {
  margin: 4px 0 0;
  display: -webkit-box;
  overflow: hidden;
  font-size: 12px;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.evaluation-list-page__metric {
  color: var(--admin-text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.evaluation-list-page__table :deep(.el-table__cell) {
  vertical-align: top;
}

.evaluation-list-page__dialog-alert {
  margin-bottom: 16px;
}

.evaluation-list-page__create-knowledge-base {
  margin-top: 6px;
  padding-left: 0;
}

.evaluation-list-page__form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 768px) {
  .evaluation-list-page__search {
    width: 100%;
  }

  .evaluation-list-page__form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
