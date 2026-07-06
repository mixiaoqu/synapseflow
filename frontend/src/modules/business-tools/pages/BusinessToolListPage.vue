<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Delete, Plus, Search } from "@element-plus/icons-vue";

import AdminDataTable from "@/app/components/admin/AdminDataTable.vue";
import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminPagination from "@/app/components/admin/AdminPagination.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import BusinessToolModuleNav from "@/modules/business-tools/components/BusinessToolModuleNav.vue";
import {
  deleteBusinessTool,
  listBusinessConnections,
  listBusinessTools,
} from "@/shared/api/business-tools";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import type { BusinessConnection, BusinessTool, BusinessToolStatus } from "@/shared/types/business-tool";
import { getErrorMessage, isForbiddenError } from "@/shared/utils/error";
import { useTeamScopeStore } from "@/stores/team-scope";

const router = useRouter();
const teamScopeStore = useTeamScopeStore();
const tools = ref<BusinessTool[]>([]);
const connections = ref<BusinessConnection[]>([]);
const loading = ref(false);
const loadError = ref<unknown>(null);
const hasLoadedData = ref(false);
const deletingToolId = ref<number | null>(null);

const filters = reactive({
  keyword: "",
  lifecycleStatus: "all" as "all" | BusinessToolStatus,
  connectionId: undefined as number | undefined,
});

const pagination = reactive({ page: 1, pageSize: 10, total: 0 });
const isForbidden = computed(() => Boolean(loadError.value) && isForbiddenError(loadError.value));
const hasActiveFilters = computed(
  () => filters.keyword.trim().length > 0 || filters.lifecycleStatus !== "all" || filters.connectionId !== undefined,
);

const statusMeta: Record<BusinessToolStatus, { label: string; type: "info" | "warning" | "success" | "danger" }> = {
  draft: { label: "草稿", type: "info" },
  verified: { label: "已验证", type: "warning" },
  published: { label: "已发布", type: "success" },
  error: { label: "验证失败", type: "danger" },
};

const riskMeta = {
  low: { label: "低风险", type: "success" as const },
  medium: { label: "中风险", type: "warning" as const },
  high: { label: "高风险", type: "danger" as const },
};

function getStatusMeta(status: BusinessToolStatus) {
  return statusMeta[status];
}

function getRiskMeta(risk: BusinessTool["risk_level"]) {
  return riskMeta[risk];
}

function formatDate(value: string | null) {
  if (!value) return "尚未验证";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(date);
}

async function loadConnections() {
  const response = await listBusinessConnections({
    team_id: teamScopeStore.selectedTeamId ?? undefined,
    page: 1,
    page_size: 100,
  });
  connections.value = response.items;
}

async function loadTools() {
  if (loading.value) return;
  loading.value = true;
  loadError.value = null;
  try {
    const [response] = await Promise.all([
      listBusinessTools({
        team_id: teamScopeStore.selectedTeamId ?? undefined,
        keyword: filters.keyword.trim() || undefined,
        lifecycle_status: filters.lifecycleStatus,
        connection_id: filters.connectionId,
        page: pagination.page,
        page_size: pagination.pageSize,
      }),
      loadConnections(),
    ]);
    tools.value = response.items;
    pagination.total = response.total;
    pagination.page = response.page;
    pagination.pageSize = response.page_size;
    hasLoadedData.value = true;
  } catch (error) {
    if (hasLoadedData.value) ElMessage.error(getErrorMessage(error, "业务工具刷新失败。"));
    else loadError.value = error;
  } finally {
    loading.value = false;
  }
}

function refreshFromFirstPage() {
  pagination.page = 1;
  void loadTools();
}

function resetFilters() {
  filters.keyword = "";
  filters.lifecycleStatus = "all";
  filters.connectionId = undefined;
  refreshFromFirstPage();
}

async function confirmDeleteTool(tool: BusinessTool) {
  try {
    await ElMessageBox.confirm(
      `确定删除“${tool.name}”吗？应用端中的相关授权也会失效。`,
      "删除业务工具",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  deletingToolId.value = tool.id;
  try {
    await deleteBusinessTool(tool.id);
    ElMessage.success("业务工具已删除。 ");
    if (tools.value.length === 1 && pagination.page > 1) pagination.page -= 1;
    await loadTools();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除业务工具失败。"));
  } finally {
    deletingToolId.value = null;
  }
}

onMounted(() => {
  void teamScopeStore.bootstrap({ allowAllTeams: true }).finally(loadTools);
});

watch(
  () => teamScopeStore.selectedTeamId,
  () => {
    pagination.page = 1;
    filters.connectionId = undefined;
    void loadTools();
  },
);
</script>

<template>
  <section class="business-tool-page">
    <AdminListPanel>
      <BusinessToolModuleNav />

      <div class="business-tool-page__guide">
      <div>
          <strong>把外部接口变成助手可用的业务能力</strong>
          <span>先配置连接和接口，再定义工具实现，最后发布并授权给应用。</span>
        </div>
        <ol aria-label="配置步骤">
          <li><span>1</span>连接系统</li>
          <li><span>2</span>定义接口</li>
          <li><span>3</span>绑定实现并发布</li>
        </ol>
      </div>

      <AppLoading
        v-if="loading && !hasLoadedData"
        title="业务工具加载中"
        description="正在获取当前团队的工具目录。"
        :blocks="4"
      />
      <AppError
        v-else-if="loadError && !isForbidden && !hasLoadedData"
        title="业务工具加载失败"
        description="暂时无法获取工具目录，请稍后重试。"
        :error="loadError"
        @retry="loadTools"
      />
      <AppError
        v-else-if="isForbidden && !hasLoadedData"
        title="无权查看业务工具"
        description="当前账号没有访问业务工具的权限。"
        :error="loadError"
        :show-retry="false"
      />

      <template v-else>
        <AdminTableToolbar>
          <template #left>
            <el-input
              v-model="filters.keyword"
              clearable
              placeholder="搜索工具名称、标识或用途..."
              class="business-tool-page__search"
              @keyup.enter="refreshFromFirstPage"
              @clear="refreshFromFirstPage"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-select
              v-model="filters.lifecycleStatus"
              class="business-tool-page__status"
              @change="refreshFromFirstPage"
            >
              <el-option label="全部生命周期" value="all" />
              <el-option label="草稿" value="draft" />
              <el-option label="已验证" value="verified" />
              <el-option label="已发布" value="published" />
              <el-option label="验证失败" value="error" />
            </el-select>
            <el-select
              v-model="filters.connectionId"
              clearable
              filterable
              placeholder="全部连接"
              class="business-tool-page__connection"
              @change="refreshFromFirstPage"
            >
              <el-option v-for="item in connections" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
            <el-button :loading="loading" type="primary" @click="refreshFromFirstPage">搜索</el-button>
            <el-button :disabled="loading" @click="resetFilters">重置</el-button>
          </template>
          <template #right>
            <el-button type="primary" @click="router.push('/business-tools/new')">
              <el-icon><Plus /></el-icon>
              新建工具
            </el-button>
          </template>
        </AdminTableToolbar>

        <AppEmpty
          v-if="tools.length === 0"
          v-loading="loading"
          :title="hasActiveFilters ? '未找到相关业务工具' : '还没有业务工具'"
          :description="hasActiveFilters ? '可以调整筛选条件后重试。' : '完成业务连接后，创建第一个可供助手调用的工具。'"
        >
          <el-button v-if="hasActiveFilters" link type="primary" @click="resetFilters">清除筛选</el-button>
          <el-button v-else type="primary" @click="router.push('/business-tools/new')">新建工具</el-button>
        </AppEmpty>

        <AdminDataTable v-else :data="tools" :loading="loading" loading-text="正在更新工具目录">
          <el-table-column label="工具" min-width="260">
            <template #default="{ row }">
              <button type="button" class="business-tool-page__tool-cell" @click="router.push(`/business-tools/${row.id}`)">
                <span class="business-tool-page__tool-title">
                  <strong>{{ row.name }}</strong>
                  <el-tag v-if="row.primary_implementation" size="small" effect="plain">
                    {{ row.primary_implementation.method }}
                  </el-tag>
                </span>
                <small>{{ row.description }}</small>
              </button>
            </template>
          </el-table-column>
          <el-table-column label="实现数" width="90" align="center" prop="implementation_count" />
          <el-table-column label="工具标识" min-width="170">
            <template #default="{ row }"><code>{{ row.tool_key }}</code></template>
          </el-table-column>
          <el-table-column label="主实现" min-width="220">
            <template #default="{ row }">
              <div class="business-tool-page__connection-cell">
                <span>{{ row.primary_implementation?.connection_name || "未配置实现" }}</span>
                <small>
                  {{
                    row.primary_implementation
                      ? `${row.primary_implementation.connection_environment} · ${row.primary_implementation.path}`
                      : "先在详情页绑定业务接口"
                  }}
                </small>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="生命周期" width="120" align="center">
            <template #default="{ row }">
              <el-tag :type="getStatusMeta(row.status).type" effect="plain">{{ getStatusMeta(row.status).label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="风险" width="105" align="center">
            <template #default="{ row }">
              <el-tag :type="getRiskMeta(row.risk_level).type" effect="plain">{{ getRiskMeta(row.risk_level).label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="最近验证" width="170">
            <template #default="{ row }"><span>{{ formatDate(row.last_tested_at) }}</span></template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right" align="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="router.push(`/business-tools/${row.id}`)">配置</el-button>
              <el-button link type="danger" :loading="deletingToolId === row.id" @click="confirmDeleteTool(row)">
                <el-icon><Delete /></el-icon>删除
              </el-button>
            </template>
          </el-table-column>
        </AdminDataTable>

        <AdminPagination
          :current-page="pagination.page"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          @page-change="(page) => { pagination.page = page; loadTools(); }"
          @page-size-change="(size) => { pagination.pageSize = size; pagination.page = 1; loadTools(); }"
        />
      </template>
    </AdminListPanel>
  </section>
</template>

<style scoped>
.business-tool-page { min-height: 0; }
.business-tool-page__guide {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  border-bottom: 1px solid var(--admin-border-soft);
  background: var(--admin-primary-soft);
  padding: 16px 20px;
}
.business-tool-page__guide > div { display: grid; gap: 4px; }
.business-tool-page__guide strong { color: var(--admin-text); font-size: 14px; }
.business-tool-page__guide > div span { color: var(--admin-text-muted); font-size: 12px; }
.business-tool-page__guide ol { display: flex; align-items: center; gap: 18px; margin: 0; padding: 0; list-style: none; }
.business-tool-page__guide li { display: inline-flex; align-items: center; gap: 7px; color: var(--admin-text-secondary); font-size: 12px; white-space: nowrap; }
.business-tool-page__guide li span { display: inline-flex; width: 22px; height: 22px; align-items: center; justify-content: center; border: 1px solid var(--admin-primary-border); border-radius: 50%; background: white; color: var(--admin-primary); font-weight: 700; }
.business-tool-page__search { width: 290px; }
.business-tool-page__status { width: 145px; }
.business-tool-page__connection { width: 180px; }
.business-tool-page__tool-cell { display: grid; width: 100%; gap: 5px; border: 0; background: transparent; padding: 0; cursor: pointer; text-align: left; }
.business-tool-page__tool-cell:hover strong { color: var(--admin-primary); }
.business-tool-page__tool-title { display: flex; align-items: center; gap: 8px; }
.business-tool-page__tool-title strong { overflow: hidden; color: var(--admin-text); font-size: 14px; text-overflow: ellipsis; transition: color 180ms ease; white-space: nowrap; }
.business-tool-page__tool-cell small, .business-tool-page__connection-cell small { overflow: hidden; color: var(--admin-text-muted); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.business-tool-page__connection-cell { display: grid; gap: 4px; }
.business-tool-page code { border: 1px solid var(--admin-border-soft); border-radius: 4px; background: var(--admin-surface-muted); padding: 3px 6px; color: var(--admin-text-secondary); font-size: 12px; }
@media (max-width: 900px) {
  .business-tool-page__guide { align-items: flex-start; flex-direction: column; }
  .business-tool-page__guide ol { overflow-x: auto; max-width: 100%; }
  .business-tool-page__search, .business-tool-page__status, .business-tool-page__connection { width: 100%; }
}
</style>
