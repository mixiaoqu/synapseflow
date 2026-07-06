<script setup lang="ts">
import { onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Delete, Link, Plus, Search } from "@element-plus/icons-vue";

import AdminDataTable from "@/app/components/admin/AdminDataTable.vue";
import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminPagination from "@/app/components/admin/AdminPagination.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import BusinessToolModuleNav from "@/modules/business-tools/components/BusinessToolModuleNav.vue";
import { deleteBusinessApi, listBusinessApis, listBusinessConnections } from "@/shared/api/business-tools";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import type { BusinessApi, BusinessConnection } from "@/shared/types/business-tool";
import { getErrorMessage } from "@/shared/utils/error";
import { useTeamScopeStore } from "@/stores/team-scope";

const router = useRouter();
const teamScopeStore = useTeamScopeStore();
const apis = ref<BusinessApi[]>([]);
const filterConnections = ref<BusinessConnection[]>([]);
const loading = ref(false);
const deletingId = ref<number | null>(null);

const filters = reactive({
  keyword: "",
  enabledStatus: "all" as "all" | "enabled" | "disabled",
  connectionId: undefined as number | undefined,
});

const pagination = reactive({ page: 1, pageSize: 10, total: 0 });

function formatDate(value: string) {
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

async function loadData() {
  if (loading.value) return;
  loading.value = true;
  try {
    const currentTeamId = teamScopeStore.selectedTeamId ?? undefined;
    const [response, connectionResponse] = await Promise.all([
      listBusinessApis({
        team_id: currentTeamId,
        keyword: filters.keyword.trim() || undefined,
        enabled_status: filters.enabledStatus,
        connection_id: filters.connectionId,
        page: pagination.page,
        page_size: pagination.pageSize,
      }),
      listBusinessConnections({
        team_id: currentTeamId,
        page: 1,
        page_size: 100,
      }),
    ]);
    apis.value = response.items;
    filterConnections.value = connectionResponse.items;
    pagination.total = response.total;
    pagination.page = response.page;
    pagination.pageSize = response.page_size;
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "业务接口加载失败。"));
  } finally {
    loading.value = false;
  }
}

async function handleDelete(api: BusinessApi) {
  try {
    await ElMessageBox.confirm(
      `确定删除“${api.name}”吗？仅未被工具实现引用时才能删除。`,
      "删除业务接口",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  deletingId.value = api.id;
  try {
    await deleteBusinessApi(api.id);
    ElMessage.success("业务接口已删除。");
    await loadData();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除业务接口失败。"));
  } finally {
    deletingId.value = null;
  }
}

onMounted(() => void teamScopeStore.bootstrap({ allowAllTeams: true }).finally(loadData));

watch(
  () => teamScopeStore.selectedTeamId,
  () => {
    pagination.page = 1;
    filters.connectionId = undefined;
    void loadData();
  },
);
</script>

<template>
  <section class="business-api-page">
    <AdminListPanel>
      <BusinessToolModuleNav />

      <div class="business-api-page__intro">
        <div class="business-api-page__icon"><el-icon><Link /></el-icon></div>
        <div>
          <strong>把外部系统的原始 API 沉淀成标准接口定义</strong>
          <p>业务工具只绑定这里定义好的接口，接口可以被多个工具实现复用。</p>
        </div>
      </div>

      <AdminTableToolbar>
        <template #left>
          <el-input
            v-model="filters.keyword"
            clearable
            placeholder="搜索接口名称、标识或路径..."
            class="business-api-page__search"
            @keyup.enter="pagination.page = 1; loadData()"
            @clear="pagination.page = 1; loadData()"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select
            v-model="filters.enabledStatus"
            class="business-api-page__status"
            @change="pagination.page = 1; loadData()"
          >
            <el-option label="全部状态" value="all" />
            <el-option label="已启用" value="enabled" />
            <el-option label="已停用" value="disabled" />
          </el-select>
          <el-select
            v-model="filters.connectionId"
            clearable
            filterable
            placeholder="全部连接"
            class="business-api-page__connection"
            @change="pagination.page = 1; loadData()"
          >
            <el-option v-for="item in filterConnections" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
          <el-button type="primary" :loading="loading" @click="pagination.page = 1; loadData()">搜索</el-button>
        </template>
        <template #right>
          <el-button type="primary" @click="router.push('/business-tools/apis/new')">
            <el-icon><Plus /></el-icon>
            新建接口
          </el-button>
        </template>
      </AdminTableToolbar>

      <AppEmpty
        v-if="!loading && apis.length === 0"
        title="还没有业务接口"
        description="先基于业务连接维护接口定义，后续工具实现会直接绑定这里的接口。"
      >
        <el-button type="primary" @click="router.push('/business-tools/apis/new')">新建接口</el-button>
      </AppEmpty>

      <AdminDataTable v-else :data="apis" :loading="loading" loading-text="正在更新业务接口">
        <el-table-column label="接口" min-width="250">
          <template #default="{ row }">
            <button type="button" class="business-api-page__name" @click="router.push(`/business-tools/apis/${row.id}`)">
              <strong>{{ row.name }}</strong>
              <span>{{ row.description || "暂无说明" }}</span>
            </button>
          </template>
        </el-table-column>
        <el-table-column label="接口标识" min-width="170">
          <template #default="{ row }"><code>{{ row.api_key }}</code></template>
        </el-table-column>
        <el-table-column label="连接 / 路径" min-width="250">
          <template #default="{ row }">
            <div class="business-api-page__path-cell">
              <span>{{ row.connection_name }}</span>
              <small>{{ row.method }} · {{ row.path }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="130" align="center">
          <template #default="{ row }">
            <el-tag effect="plain" :type="row.source_type === 'manual' ? 'info' : 'success'">
              {{ row.source_type === "manual" ? "手动维护" : "OpenAPI 导入" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="140" align="center">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" effect="plain">
              {{ row.enabled ? "已启用" : "已停用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="router.push(`/business-tools/apis/${row.id}`)">编辑</el-button>
            <el-button link type="danger" :loading="deletingId === row.id" @click="handleDelete(row)">
              <el-icon><Delete /></el-icon>删除
            </el-button>
          </template>
        </el-table-column>
      </AdminDataTable>

      <AdminPagination
        :current-page="pagination.page"
        :page-size="pagination.pageSize"
        :total="pagination.total"
        @page-change="(page) => { pagination.page = page; loadData(); }"
        @page-size-change="(size) => { pagination.pageSize = size; pagination.page = 1; loadData(); }"
      />
    </AdminListPanel>
  </section>
</template>

<style scoped>
.business-api-page__intro { display: flex; align-items: center; gap: 14px; border-bottom: 1px solid var(--admin-border-soft); background: var(--admin-primary-soft); padding: 16px 20px; }
.business-api-page__icon { display: inline-flex; width: 36px; height: 36px; align-items: center; justify-content: center; border: 1px solid var(--admin-primary-border); border-radius: var(--admin-radius-md); background: white; color: var(--admin-primary); font-size: 18px; }
.business-api-page__intro strong { color: var(--admin-text); font-size: 14px; }
.business-api-page__intro p { margin: 4px 0 0; color: var(--admin-text-muted); font-size: 12px; }
.business-api-page__search { width: 300px; }
.business-api-page__status { width: 130px; }
.business-api-page__connection { width: 200px; }
.business-api-page__name { display: grid; width: 100%; gap: 4px; border: 0; background: transparent; padding: 0; cursor: pointer; text-align: left; }
.business-api-page__name strong { color: var(--admin-text); font-size: 14px; }
.business-api-page__name:hover strong { color: var(--admin-primary); }
.business-api-page__name span { overflow: hidden; color: var(--admin-text-muted); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.business-api-page__path-cell { display: grid; gap: 4px; }
.business-api-page__path-cell span { color: var(--admin-text-secondary); font-size: 13px; }
.business-api-page__path-cell small { overflow: hidden; color: var(--admin-text-muted); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.business-api-page code { border: 1px solid var(--admin-border-soft); border-radius: 4px; background: var(--admin-surface-muted); padding: 3px 6px; color: var(--admin-text-secondary); font-size: 12px; }
@media (max-width: 760px) {
  .business-api-page__intro { align-items: flex-start; }
  .business-api-page__search, .business-api-page__status, .business-api-page__connection { width: 100%; }
}
</style>
