<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { CopyDocument, Delete, EditPen, Folder, Grid, MoreFilled, Plus, Search } from "@element-plus/icons-vue";

import AdminBulkActions from "@/app/components/admin/AdminBulkActions.vue";
import AdminDataTable from "@/app/components/admin/AdminDataTable.vue";
import AdminDialog from "@/app/components/admin/AdminDialog.vue";
import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminPagination from "@/app/components/admin/AdminPagination.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import { createProduct, deleteProduct, listProducts, updateProduct } from "@/shared/api/products";
import { bulkActionProjects, copyProject, createProject, deleteProject, listProjects } from "@/shared/api/projects";
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
const selectedProductId = ref<number | "all">("all");
const projects = ref<ProjectSummary[]>([]);
const products = ref<ProductSummary[]>([]);
const loading = ref(false);
const loadError = ref<unknown>(null);
const hasLoadedData = ref(false);
const selectedProjectIds = ref<number[]>([]);
const batchActionLoading = ref<"" | "enable" | "disable" | "delete">("");
const pagination = ref({
  page: 1,
  pageSize: 10,
  total: 0,
});
const createProductDialogVisible = ref(false);
const createDialogVisible = ref(false);
const copyDialogVisible = ref(false);
const creatingProduct = ref(false);
const editingProduct = ref<ProductSummary | null>(null);
const deletingProductId = ref<number | null>(null);
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
const hasActiveFilters = computed(() => keyword.value.trim().length > 0);
const currentProduct = computed(() =>
  selectedProductId.value === "all"
    ? null
    : products.value.find((item) => item.id === selectedProductId.value) ?? null,
);
const productDialogTitle = computed(() => (editingProduct.value ? "编辑产品" : "新建产品"));
const productDialogSubmitText = computed(() => (editingProduct.value ? "保存产品" : "创建产品"));
const productScopeTitle = computed(() => currentProduct.value?.name ?? "全部产品");
const productScopeDescription = computed(() =>
  currentProduct.value?.description?.trim() || "管理当前团队下的产品、项目和应用端接入配置。",
);

function resetCreateForm() {
  createForm.value = {
    name: "",
    code: "",
    product_id: currentProduct.value?.id ?? products.value[0]?.id ?? null,
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
        product_id: selectedProductId.value === "all" ? undefined : selectedProductId.value,
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
    selectedProjectIds.value = [];
    hasLoadedData.value = true;
  } catch (error) {
    if (hasLoadedData.value) {
      ElMessage.error(error instanceof Error ? error.message : "项目列表刷新失败，请稍后重试。");
    } else {
      loadError.value = error;
    }
  } finally {
    loading.value = false;
  }
}

function handlePageChange(page: number) {
  pagination.value.page = page;
  selectedProjectIds.value = [];
  void loadProjectList();
}

function resetFilters() {
  keyword.value = "";
  refreshProjectListFromFirstPage();
}

function refreshProjectListFromFirstPage() {
  pagination.value.page = 1;
  selectedProjectIds.value = [];
  void loadProjectList();
}

function selectProduct(productId: number | "all") {
  selectedProductId.value = productId;
  refreshProjectListFromFirstPage();
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
  editingProduct.value = null;
  createProductDialogVisible.value = true;
}

function openEditProductDialog(product: ProductSummary) {
  editingProduct.value = product;
  createProductForm.value = {
    name: product.name,
    code: product.code,
    description: product.description ?? "",
    is_active: product.is_active,
  };
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

async function submitProductForm() {
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
    const saved = editingProduct.value
      ? await updateProduct(editingProduct.value.id, payload)
      : await createProduct(payload);
    ElMessage.success(`已${editingProduct.value ? "保存" : "创建"}产品“${saved.name}”。`);
    createProductDialogVisible.value = false;
    selectedProductId.value = saved.id;
    createForm.value.product_id = saved.id;
    await loadProjectList();
  } catch (error) {
    const message = error instanceof Error ? error.message : "产品保存失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    creatingProduct.value = false;
  }
}

async function handleDeleteProduct(product: ProductSummary) {
  if (deletingProductId.value) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定删除产品“${product.name}”吗？删除后该产品下的项目和应用端配置将一起删除。`,
      "删除产品",
      {
        type: "warning",
        confirmButtonText: "删除产品",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  deletingProductId.value = product.id;
  try {
    await deleteProduct(product.id);
    ElMessage.success(`已删除产品“${product.name}”。`);
    if (selectedProductId.value === product.id) {
      selectedProductId.value = "all";
    }
    await loadProjectList();
  } catch (error) {
    const message = error instanceof Error ? error.message : "删除产品失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    deletingProductId.value = null;
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
      `确定删除项目“${project.name}”吗？删除后该项目下的应用端配置将一起删除。`,
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
    selectedProjectIds.value = selectedProjectIds.value.filter((item) => item !== project.id);
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

function handleSelectionChange(selection: ProjectSummary[]) {
  selectedProjectIds.value = selection.map((item) => item.id);
}

async function handleBatchAction(action: "enable" | "disable" | "delete") {
  if (selectedProjectIds.value.length === 0 || batchActionLoading.value) {
    return;
  }

  const actionTextMap = {
    enable: "批量启用",
    disable: "批量停用",
    delete: "批量删除",
  };
  const actionText = actionTextMap[action];

  try {
    await ElMessageBox.confirm(
      action === "delete"
        ? `确定删除已选中的 ${selectedProjectIds.value.length} 个项目吗？删除后项目下的应用端配置将一起删除。`
        : `确定${actionText}已选中的 ${selectedProjectIds.value.length} 个项目吗？`,
      action === "delete" ? "批量删除项目" : actionText,
      {
        type: action === "delete" ? "warning" : "info",
        confirmButtonText: action === "delete" ? "删除" : "确定",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  batchActionLoading.value = action;
  try {
    const result = await bulkActionProjects(selectedProjectIds.value, action);
    ElMessage.success(`${actionText}完成，影响 ${result.affected_count} 个项目。`);
    if (action === "delete" && projects.value.length === selectedProjectIds.value.length && pagination.value.page > 1) {
      pagination.value.page -= 1;
    }
    await loadProjectList();
  } catch (error) {
    const message = error instanceof Error ? error.message : `${actionText}失败，请稍后重试。`;
    ElMessage.error(message);
  } finally {
    batchActionLoading.value = "";
  }
}

onMounted(() => {
  void loadProjectList();
});

watch(
  () => teamScopeStore.selectedTeamId,
  () => {
    pagination.value.page = 1;
    selectedProductId.value = "all";
    selectedProjectIds.value = [];
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
    <AppLoading
      v-if="loading && !hasLoadedData"
      title="项目列表加载中"
      description="正在获取当前团队可访问的项目，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="loadError && !isForbidden && !hasLoadedData"
      title="项目列表加载失败"
      description="暂时无法获取项目列表，请稍后重试。"
      :error="loadError"
      @retry="loadProjectList"
    />

    <AppError
      v-else-if="isForbidden && !hasLoadedData"
      title="无权查看项目列表"
      description="当前账号没有访问项目列表的权限。"
      :error="loadError"
      :show-retry="false"
    />

    <div v-else class="project-list-page__workspace">
      <aside class="project-list-page__product-sidebar">
        <div class="project-list-page__product-header">
          <span>产品</span>
          <el-button link type="primary" @click="openCreateProductDialog">
            <el-icon><Plus /></el-icon>
          </el-button>
        </div>

        <div
          :class="[
            'project-list-page__product-item',
            'project-list-page__product-item--overview',
            selectedProductId === 'all' ? 'project-list-page__product-item--active' : '',
          ]"
        >
          <button type="button" class="project-list-page__product-main" @click="selectProduct('all')">
            <el-icon><Grid /></el-icon>
            <span>全部产品</span>
          </button>
        </div>

        <div class="project-list-page__product-list">
          <div
            v-for="product in products"
            :key="product.id"
            :class="[
              'project-list-page__product-item',
              selectedProductId === product.id ? 'project-list-page__product-item--active' : '',
              !product.is_active ? 'project-list-page__product-item--disabled' : '',
            ]"
          >
            <button type="button" class="project-list-page__product-main" @click="selectProduct(product.id)">
              <el-icon><Folder /></el-icon>
              <span>{{ product.name }}</span>
            </button>

            <el-dropdown trigger="click" @click.stop>
              <button
                type="button"
                class="project-list-page__product-more"
                aria-label="产品更多操作"
                @click.stop
              >
                <el-icon><MoreFilled /></el-icon>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="openEditProductDialog(product)">
                    <el-icon><EditPen /></el-icon>
                    编辑产品
                  </el-dropdown-item>
                  <el-dropdown-item
                    divided
                    :disabled="deletingProductId === product.id"
                    @click="handleDeleteProduct(product)"
                  >
                    <el-icon><Delete /></el-icon>
                    删除产品
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </aside>

      <AdminListPanel class="project-list-page__main">
        <div class="project-list-page__scope-header">
          <div>
            <h2>{{ productScopeTitle }}</h2>
            <p>{{ productScopeDescription }}</p>
          </div>
          <el-button type="primary" @click="openCreateProjectDialog">
            <el-icon><Plus /></el-icon>
            新建项目
          </el-button>
        </div>

        <AdminTableToolbar>
          <template #left>
            <el-input
              v-model="keyword"
              clearable
              placeholder="搜索项目名称、编码或产品..."
              class="project-list-page__search"
              @keyup.enter="refreshProjectListFromFirstPage"
              @clear="refreshProjectListFromFirstPage"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-button :loading="loading" type="primary" @click="refreshProjectListFromFirstPage">
              搜索
            </el-button>
            <el-button :disabled="loading" @click="resetFilters">重置</el-button>
          </template>

          <template #right>
            <AdminBulkActions :selected-count="selectedProjectIds.length">
              <el-button
                link
                type="primary"
                :loading="batchActionLoading === 'enable'"
                :disabled="Boolean(batchActionLoading)"
                @click="handleBatchAction('enable')"
              >
                启用
              </el-button>
              <el-button
                link
                type="primary"
                :loading="batchActionLoading === 'disable'"
                :disabled="Boolean(batchActionLoading)"
                @click="handleBatchAction('disable')"
              >
                停用
              </el-button>
              <el-button
                link
                type="danger"
                :loading="batchActionLoading === 'delete'"
                :disabled="Boolean(batchActionLoading)"
                @click="handleBatchAction('delete')"
              >
                删除
              </el-button>
            </AdminBulkActions>
          </template>
        </AdminTableToolbar>

        <AppEmpty
          v-if="displayedProjects.length === 0"
          v-loading="loading"
          class="project-list-page__empty"
          :title="hasActiveFilters ? '未找到相关项目' : '暂无项目'"
          description="当前筛选条件下没有可管理的业务项目。"
        >
          <el-button v-if="hasActiveFilters" link type="primary" @click="resetFilters">清除筛选</el-button>
          <el-button v-else type="primary" @click="openCreateProjectDialog">新建项目</el-button>
        </AppEmpty>

        <AdminDataTable
          v-else
          :data="displayedProjects"
          :loading="loading"
          table-class="project-list-page__table"
          loading-text="正在更新项目列表"
          @selection-change="handleSelectionChange"
        >
        <el-table-column type="selection" width="44" fixed="left" />
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
        <el-table-column label="应用端" width="120" align="center">
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
            <el-button type="primary" link  size="small" @click="openProjectApps(row.id)">
              管理应用端
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
        </AdminDataTable>
        <AdminPagination
          v-if="pagination.total > pagination.pageSize"
          :current-page="pagination.page"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          layout="prev, pager, next"
          @page-change="handlePageChange"
          @page-size-change="() => undefined"
        />
      </AdminListPanel>
    </div>

    <AdminDialog
      v-model="createProductDialogVisible"
      :title="productDialogTitle"
      :loading="creatingProduct"
    >
      <div class="admin-dialog__scope">
        <span class="admin-dialog__scope-label">所属团队</span>
        <span class="admin-dialog__scope-value">{{ selectedTeamName || "未选择团队" }}</span>
      </div>

      <el-form class="admin-dialog__form" label-position="top" @submit.prevent="submitProductForm">
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
        <el-button @click="createProductDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingProduct" @click="submitProductForm">
          {{ productDialogSubmitText }}
        </el-button>
      </template>
    </AdminDialog>

    <AdminDialog
      v-model="createDialogVisible"
      title="新建项目"
      :loading="creating"
    >
      <div class="admin-dialog__scope">
        <span class="admin-dialog__scope-label">所属团队</span>
        <span class="admin-dialog__scope-value">{{ selectedTeamName || "未选择团队" }}</span>
      </div>

      <el-form class="admin-dialog__form" label-position="top" @submit.prevent="submitCreateProject">
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
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreateProject">
          创建并进入配置
        </el-button>
      </template>
    </AdminDialog>

    <AdminDialog
      v-model="copyDialogVisible"
      title="复制项目"
      :loading="copyingProjectId === copyingProject?.id"
      @closed="resetCopyProjectDialog"
    >
      <div class="admin-dialog__scope admin-dialog__scope--stacked">
        <div>
          <span class="admin-dialog__scope-label">来源项目</span>
          <span class="admin-dialog__scope-value">{{ copyingProject?.name || "-" }}</span>
        </div>
        <div>
          <span class="admin-dialog__scope-label">所属产品</span>
          <span class="admin-dialog__scope-value">{{ copyingProject?.product_name || "未设置" }}</span>
        </div>
        <div>
          <span class="admin-dialog__scope-label">所属团队</span>
          <span class="admin-dialog__scope-value">
            {{ copyingProject?.team_name || selectedTeamName || "未选择团队" }}
          </span>
        </div>
      </div>

      <p class="admin-dialog__hint">
        复制后会保留原项目下所有应用端的知识库、限定分类和默认助手配置。
      </p>

      <el-form class="admin-dialog__form" label-position="top" @submit.prevent="submitCopyProject">
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

      <template #footer>
        <el-button @click="copyDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="copyingProjectId === copyingProject?.id"
          @click="submitCopyProject"
        >
          复制并进入配置
        </el-button>
      </template>
    </AdminDialog>
  </section>
</template>

<style scoped>
.project-list-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.project-list-page__workspace {
  display: grid;
  min-height: calc(100vh - 160px);
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 12px;
}

.project-list-page__product-sidebar {
  display: flex;
  min-height: 0;
  flex-direction: column;
  border: 1px solid var(--admin-border-soft);
  background: var(--admin-surface);
}

.project-list-page__product-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--admin-border-soft);
  padding: 12px 14px;
}

.project-list-page__product-header span {
  color: var(--admin-text);
  font-size: 14px;
  font-weight: 700;
}

.project-list-page__product-list {
  display: grid;
  gap: 4px;
  overflow: auto;
  padding: 6px;
}

.project-list-page__product-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 28px;
  align-items: center;
  width: 100%;
  border-radius: var(--admin-radius-sm);
  background: transparent;
  color: var(--admin-text-muted);
}

.project-list-page__product-item:hover,
.project-list-page__product-item--active {
  background: var(--admin-primary-soft);
  color: var(--admin-primary-hover);
}

.project-list-page__product-item--disabled {
  opacity: 0.62;
}

.project-list-page__product-item--overview {
  grid-template-columns: minmax(0, 1fr);
  margin: 6px;
}

.project-list-page__product-main {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  min-width: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 9px 2px 9px 10px;
  text-align: left;
}

.project-list-page__product-main span {
  overflow: hidden;
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-list-page__product-more {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: var(--admin-radius-sm);
  background: transparent;
  color: inherit;
  cursor: pointer;
  opacity: 0;
}

.project-list-page__product-item:hover .project-list-page__product-more,
.project-list-page__product-item--active .project-list-page__product-more,
.project-list-page__product-more:focus-visible {
  opacity: 1;
}

.project-list-page__product-more:hover {
  background: color-mix(in srgb, var(--admin-primary-soft) 70%, var(--admin-surface));
  color: var(--admin-primary-hover);
}

.project-list-page__main {
  min-width: 0;
}

.project-list-page__scope-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--admin-border-soft);
  padding: 16px;
}

.project-list-page__scope-header h2 {
  margin: 0;
  color: var(--admin-text);
  font-size: 18px;
  font-weight: 700;
}

.project-list-page__scope-header p {
  margin: 4px 0 0;
  color: var(--admin-text-muted);
  font-size: 13px;
}

.project-list-page__search {
  width: 280px;
}

.project-list-page__dialog-field {
  width: 100%;
}

.project-list-page__table {
  width: 100%;
}

.project-list-page__empty {
  min-height: 420px;
  border-top: 1px solid #e2e8f0;
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
  .project-list-page__workspace {
    grid-template-columns: 1fr;
  }

  .project-list-page__product-sidebar {
    min-height: auto;
  }

  .project-list-page__search {
    width: 100%;
  }
}
</style>
