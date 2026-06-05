<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { CopyDocument, Delete, Plus, Search } from "@element-plus/icons-vue";

import { createProduct, listProducts } from "@/shared/api/products";
import { copyProject, createProject, deleteProject, listProjects } from "@/shared/api/projects";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import { useTeamScopeStore } from "@/stores/team-scope";
import { isForbiddenError } from "@/shared/utils/error";
import type { ProductSummary, ProductUpsertPayload } from "@/shared/types/product";
import type { ProjectCopyPayload, ProjectSummary, ProjectUpsertPayload } from "@/shared/types/project";

const router = useRouter();
const teamScopeStore = useTeamScopeStore();

const keyword = ref("");
const projects = ref<ProjectSummary[]>([]);
const products = ref<ProductSummary[]>([]);
const loading = ref(false);
const loadError = ref<unknown>(null);
const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0,
});
const createProductDialogVisible = ref(false);
const createDialogVisible = ref(false);
const copyDialogVisible = ref(false);
const creatingProduct = ref(false);
const creating = ref(false);
const copyingProjectId = ref<number | null>(null);
const deletingProjectId = ref<number | null>(null);
const createProductForm = ref({
  name: "",
  code: "",
  description: "",
  is_active: true,
});
const createForm = ref({
  name: "",
  code: "",
  product_id: null as number | null,
  description: "",
  is_active: true,
});
const copyingProject = ref<ProjectSummary | null>(null);
const copyForm = ref({
  name: "",
  code: "",
  is_active: false,
});
let searchTimer: ReturnType<typeof setTimeout> | undefined;

const displayedProjects = computed(() => projects.value);

const isForbidden = computed(() => Boolean(loadError.value) && isForbiddenError(loadError.value));
const selectedTeamName = computed(() => teamScopeStore.selectedTeam?.name ?? "");
const hasAvailableProducts = computed(() => products.value.length > 0);

function resetCreateForm() {
  createForm.value = {
    name: "",
    code: "",
    product_id: products.value[0]?.id ?? null,
    description: "",
    is_active: true,
  };
}

function resetCreateProductForm() {
  createProductForm.value = {
    name: "",
    code: "",
    description: "",
    is_active: true,
  };
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

async function loadProjectList() {
  if (loading.value) {
    return;
  }

  loading.value = true;
  loadError.value = null;

  try {
    const teamId = teamScopeStore.selectedTeamId ?? undefined;
    const [projectResult, productResult] = await Promise.all([
      listProjects({
        team_id: teamId,
        keyword: keyword.value.trim() || undefined,
        page: pagination.value.page,
        page_size: pagination.value.pageSize,
      }),
      listProducts({
        team_id: teamId,
        page: 1,
        page_size: 100,
      }),
    ]);
    projects.value = projectResult.items;
    pagination.value.total = projectResult.total;
    products.value = productResult.items;
  } catch (error) {
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

function handlePageChange(page: number) {
  pagination.value.page = page;
  void loadProjectList();
}

function refreshProjectListFromFirstPage() {
  pagination.value.page = 1;
  void loadProjectList();
}

function openProjectApps(projectId: number) {
  void router.push(`/projects/${projectId}/apps`);
}

function openCreateProductDialog() {
  if (!teamScopeStore.selectedTeamId) {
    ElMessage.warning("请先选择所属团队，再创建产品。");
    return;
  }

  resetCreateProductForm();
  createProductDialogVisible.value = true;
}

function openCreateProjectDialog() {
  if (!teamScopeStore.selectedTeamId) {
    ElMessage.warning("请先选择所属团队，再创建项目。");
    return;
  }

  if (!hasAvailableProducts.value) {
    ElMessage.warning("当前团队下还没有可用产品，暂时无法创建项目。");
    return;
  }

  resetCreateForm();
  createDialogVisible.value = true;
}

function openCopyProjectDialog(project: ProjectSummary) {
  copyingProject.value = project;
  copyForm.value = {
    name: `${project.name} 副本`,
    code: `${project.code}-copy`,
    is_active: false,
  };
  copyDialogVisible.value = true;
}

function resetCopyProjectDialog() {
  copyingProject.value = null;
  copyForm.value = {
    name: "",
    code: "",
    is_active: false,
  };
}

async function submitCreateProduct() {
  if (creatingProduct.value) {
    return;
  }

  if (!teamScopeStore.selectedTeamId) {
    ElMessage.warning("请先选择所属团队，再创建产品。");
    return;
  }

  if (!createProductForm.value.name.trim() || !createProductForm.value.code.trim()) {
    ElMessage.warning("请填写产品名称和产品编码。");
    return;
  }

  creatingProduct.value = true;

  try {
    const payload: ProductUpsertPayload = {
      team_id: teamScopeStore.selectedTeamId,
      code: createProductForm.value.code.trim(),
      name: createProductForm.value.name.trim(),
      description: createProductForm.value.description.trim() || null,
      is_active: createProductForm.value.is_active,
    };
    const created = await createProduct(payload);
    ElMessage.success(`已创建产品“${created.name}”。`);
    createProductDialogVisible.value = false;
    await loadProjectList();
    createForm.value.product_id = created.id;
  } catch (error) {
    const message = error instanceof Error ? error.message : "创建产品失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    creatingProduct.value = false;
  }
}

async function submitCreateProject() {
  if (creating.value) {
    return;
  }

  if (!teamScopeStore.selectedTeamId) {
    ElMessage.warning("请先选择所属团队，再创建项目。");
    return;
  }

  if (!createForm.value.name.trim() || !createForm.value.code.trim()) {
    ElMessage.warning("请填写项目名称和项目编码。");
    return;
  }

  if (!createForm.value.product_id) {
    ElMessage.warning("请选择所属产品。");
    return;
  }

  creating.value = true;

  try {
    const payload: ProjectUpsertPayload = {
      team_id: teamScopeStore.selectedTeamId,
      product_id: createForm.value.product_id,
      code: createForm.value.code.trim(),
      name: createForm.value.name.trim(),
      description: createForm.value.description.trim() || null,
      is_active: createForm.value.is_active,
    };
    const created = await createProject(payload);
    ElMessage.success(`已创建项目“${created.name}”。`);
    createDialogVisible.value = false;
    await loadProjectList();
    await router.push(`/projects/${created.id}/apps`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "创建项目失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    creating.value = false;
  }
}

async function submitCopyProject() {
  const sourceProject = copyingProject.value;
  if (!sourceProject || copyingProjectId.value) {
    return;
  }

  if (!copyForm.value.name.trim() || !copyForm.value.code.trim()) {
    ElMessage.warning("请填写复制后的项目名称和项目编码。");
    return;
  }

  copyingProjectId.value = sourceProject.id;

  try {
    const payload: ProjectCopyPayload = {
      code: copyForm.value.code.trim(),
      name: copyForm.value.name.trim(),
      is_active: copyForm.value.is_active,
    };
    const created = await copyProject(sourceProject.id, payload);
    ElMessage.success(`已复制项目“${created.name}”。`);
    copyDialogVisible.value = false;
    await loadProjectList();
    await router.push(`/projects/${created.id}/apps`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "复制项目失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    copyingProjectId.value = null;
  }
}

async function handleDeleteProject(project: ProjectSummary) {
  if (deletingProjectId.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定删除项目“${project.name}”吗？删除后该项目下的发布渠道配置将一起删除。`,
      "删除项目",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  deletingProjectId.value = project.id;
  try {
    await deleteProject(project.id);
    ElMessage.success(`已删除项目“${project.name}”。`);
    if (projects.value.length === 1 && pagination.value.page > 1) {
      pagination.value.page -= 1;
    }
    await loadProjectList();
  } catch (error) {
    const message = error instanceof Error ? error.message : "删除项目失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    deletingProjectId.value = null;
  }
}

onMounted(() => {
  void loadProjectList();
});

watch(
  () => teamScopeStore.selectedTeamId,
  () => {
    pagination.value.page = 1;
    void loadProjectList();
  },
);

watch(keyword, () => {
  if (searchTimer) {
    clearTimeout(searchTimer);
  }
  searchTimer = setTimeout(refreshProjectListFromFirstPage, 300);
});
</script>

<template>
  <section class="project-list-page">
    <header class="project-list-page__header">
      <div>
        <h1 class="project-list-page__title">应用与发布</h1>
        <p class="project-list-page__description">先选择业务项目，再进入该项目下的发布渠道与接入配置。</p>
      </div>

      <div class="project-list-page__header-actions">
        <el-input
          v-model="keyword"
          size="large"
          clearable
          placeholder="搜索项目名称、编码或产品..."
          class="project-list-page__search"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-button size="large" @click="openCreateProductDialog">
          <el-icon><Plus /></el-icon>
          新建产品
        </el-button>
        <el-button type="primary" size="large" @click="openCreateProjectDialog">
          <el-icon><Plus /></el-icon>
          新建项目
        </el-button>
      </div>
    </header>

    <AppLoading
      v-if="loading"
      title="项目列表加载中"
      description="正在获取当前团队可访问的项目，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="loadError && !isForbidden"
      title="项目列表加载失败"
      description="暂时无法获取项目列表，请稍后重试。"
      :error="loadError"
      @retry="loadProjectList"
    />

    <AppError
      v-else-if="isForbidden"
      title="无权查看项目列表"
      description="当前账号没有访问项目列表的权限。"
      :error="loadError"
      :show-retry="false"
    />

    <AppEmpty
      v-else-if="displayedProjects.length === 0"
      title="暂无项目"
      description="当前筛选条件下没有可管理的业务项目。"
    >
      <el-button @click="openCreateProductDialog">新建产品</el-button>
      <el-button type="primary" @click="openCreateProjectDialog">新建项目</el-button>
    </AppEmpty>

    <section v-else class="project-list-page__table-panel">
      <el-table :data="displayedProjects" row-key="id" class="project-list-page__table">
        <el-table-column label="项目名称" min-width="280">
          <template #default="{ row }">
            <div class="project-list-page__name-cell">
              <strong>{{ row.name }}</strong>
              <span>{{ row.description?.trim() || "暂无说明" }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="项目编码" min-width="180">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="产品" min-width="180">
          <template #default="{ row }">
            <span>{{ row.product_name || "未设置" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="所属团队" min-width="150">
          <template #default="{ row }">
            <span>{{ row.team_name || "未知团队" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="发布渠道" width="120" align="center">
          <template #default="{ row }">
            <span>{{ row.app_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain" round>
              {{ row.is_active ? "启用中" : "已停用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近更新" width="140">
          <template #default="{ row }">
            <span>{{ formatDate(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right" align="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :loading="copyingProjectId === row.id"
              @click="openCopyProjectDialog(row)"
            >
              <el-icon><CopyDocument /></el-icon>
              <span>复制项目</span>
            </el-button>
            <el-button type="primary" plain size="small" @click="openProjectApps(row.id)">
              管理发布渠道
            </el-button>
            <el-button
              link
              type="danger"
              :loading="deletingProjectId === row.id"
              @click="handleDeleteProject(row)"
            >
              <el-icon><Delete /></el-icon>
              <span>删除</span>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="pagination.total > pagination.pageSize" class="project-list-page__pagination">
        <el-pagination
          background
          layout="prev, pager, next"
          :current-page="pagination.page"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          @current-change="handlePageChange"
        />
      </div>
    </section>

    <el-dialog
      v-model="createProductDialogVisible"
      title="新建产品"
      width="520px"
      destroy-on-close
    >
      <el-form label-position="top" @submit.prevent="submitCreateProduct">
        <el-form-item label="所属团队">
          <el-input :model-value="selectedTeamName || '未选择团队'" disabled />
        </el-form-item>
        <el-form-item label="产品名称" required>
          <el-input
            v-model="createProductForm.name"
            maxlength="100"
            show-word-limit
            placeholder="请输入产品名称"
          />
        </el-form-item>
        <el-form-item label="产品编码" required>
          <el-input
            v-model="createProductForm.code"
            maxlength="120"
            show-word-limit
            placeholder="请输入产品编码"
          />
        </el-form-item>
        <el-form-item label="产品说明">
          <el-input
            v-model="createProductForm.description"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="可选，补充说明这个产品的业务范围"
          />
        </el-form-item>
        <el-form-item label="产品状态">
          <el-switch
            v-model="createProductForm.is_active"
            inline-prompt
            active-text="启用"
            inactive-text="停用"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="project-list-page__dialog-footer">
          <el-button @click="createProductDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="creatingProduct" @click="submitCreateProduct">
            创建产品
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="createDialogVisible"
      title="新建项目"
      width="520px"
      destroy-on-close
    >
      <el-form label-position="top" @submit.prevent="submitCreateProject">
        <el-form-item label="所属团队">
          <el-input :model-value="selectedTeamName || '未选择团队'" disabled />
        </el-form-item>
        <el-form-item label="所属产品" required>
          <el-select
            v-model="createForm.product_id"
            placeholder="请选择所属产品"
            class="project-list-page__dialog-field"
          >
            <el-option
              v-for="product in products"
              :key="product.id"
              :label="product.name"
              :value="product.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="项目名称" required>
          <el-input
            v-model="createForm.name"
            maxlength="100"
            show-word-limit
            placeholder="请输入项目名称"
          />
        </el-form-item>
        <el-form-item label="项目编码" required>
          <el-input
            v-model="createForm.code"
            maxlength="120"
            show-word-limit
            placeholder="请输入项目编码"
          />
        </el-form-item>
        <el-form-item label="项目说明">
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="可选，补充说明这个项目的业务用途"
          />
        </el-form-item>
        <el-form-item label="项目状态">
          <el-switch
            v-model="createForm.is_active"
            inline-prompt
            active-text="启用"
            inactive-text="停用"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="project-list-page__dialog-footer">
          <el-button @click="createDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="creating" @click="submitCreateProject">
            创建并进入配置
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="copyDialogVisible"
      :title="copyingProject ? `复制项目：${copyingProject.name}` : '复制项目'"
      width="520px"
      destroy-on-close
      @closed="resetCopyProjectDialog"
    >
      <el-form label-position="top" @submit.prevent="submitCopyProject">
        <el-form-item label="所属团队">
          <el-input :model-value="copyingProject?.team_name || selectedTeamName || '未选择团队'" disabled />
        </el-form-item>
        <el-form-item label="所属产品">
          <el-input :model-value="copyingProject?.product_name || '未设置'" disabled />
        </el-form-item>
        <el-form-item label="项目名称" required>
          <el-input
            v-model="copyForm.name"
            maxlength="100"
            show-word-limit
            placeholder="请输入复制后的项目名称"
          />
        </el-form-item>
        <el-form-item label="项目编码" required>
          <el-input
            v-model="copyForm.code"
            maxlength="120"
            show-word-limit
            placeholder="请输入复制后的项目编码"
          />
        </el-form-item>
        <el-form-item label="项目状态">
          <el-switch
            v-model="copyForm.is_active"
            inline-prompt
            active-text="启用"
            inactive-text="停用"
          />
        </el-form-item>
      </el-form>
      <p class="project-list-page__copy-hint">
        复制后会保留原项目下所有发布渠道的知识库、限定分类和默认助手配置。
      </p>

      <template #footer>
        <div class="project-list-page__dialog-footer">
          <el-button @click="copyDialogVisible = false">取消</el-button>
          <el-button
            type="primary"
            :loading="copyingProjectId === copyingProject?.id"
            @click="submitCopyProject"
          >
            复制并进入配置
          </el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.project-list-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.project-list-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 56px;
  border: 1px solid #dbe2ea;
  border-radius: 12px;
  background: #ffffff;
  padding: 16px 18px;
}

.project-list-page__header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.project-list-page__title {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}

.project-list-page__description {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.project-list-page__search {
  width: 360px;
  max-width: 100%;
}

.project-list-page__dialog-field {
  width: 100%;
}

.project-list-page__dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.project-list-page__table-panel {
  border: 1px solid #dbe2ea;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
  padding: 8px 8px 2px;
}

.project-list-page__pagination {
  display: flex;
  justify-content: flex-end;
  padding: 12px 8px 10px;
}

.project-list-page__copy-hint {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.project-list-page__name-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.project-list-page__name-cell strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-list-page__name-cell span {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 960px) {
  .project-list-page__header {
    flex-direction: column;
    align-items: stretch;
  }

  .project-list-page__header-actions {
    justify-content: stretch;
  }

  .project-list-page__search {
    width: 100%;
  }
}
</style>
