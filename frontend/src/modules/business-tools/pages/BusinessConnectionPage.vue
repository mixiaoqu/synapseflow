<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Connection, Delete, Plus, Search } from "@element-plus/icons-vue";

import AdminDataTable from "@/app/components/admin/AdminDataTable.vue";
import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminPagination from "@/app/components/admin/AdminPagination.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import BusinessToolModuleNav from "@/modules/business-tools/components/BusinessToolModuleNav.vue";
import {
  createBusinessConnection,
  deleteBusinessConnection,
  listBusinessConnections,
  testBusinessConnection,
  updateBusinessConnection,
} from "@/shared/api/business-tools";
import { listTeamOptions } from "@/shared/api/teams";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import type {
  BusinessConnection as BusinessConnectionModel,
  BusinessConnectionAuthType,
  BusinessConnectionEnvironment,
  BusinessConnectionPayload,
  BusinessConnectionStatus,
} from "@/shared/types/business-tool";
import type { TeamOption } from "@/shared/types/team";
import { getErrorMessage } from "@/shared/utils/error";
import { useTeamScopeStore } from "@/stores/team-scope";

const teamScopeStore = useTeamScopeStore();
const connections = ref<BusinessConnectionModel[]>([]);
const teams = ref<TeamOption[]>([]);
const loading = ref(false);
const saving = ref(false);
const testingId = ref<number | null>(null);
const deletingId = ref<number | null>(null);
const drawerVisible = ref(false);
const editing = ref<BusinessConnectionModel | null>(null);
const filters = reactive({ keyword: "", status: "all" as "all" | BusinessConnectionStatus });
const pagination = reactive({ page: 1, pageSize: 10, total: 0 });
const form = reactive({
  team_id: null as number | null,
  name: "",
  description: "",
  environment: "production" as BusinessConnectionEnvironment,
  base_url: "",
  auth_type: "none" as BusinessConnectionAuthType,
  auth_secret_ref: "",
  auth_header_name: "X-API-Key",
  enabled: true,
});

const drawerTitle = computed(() => (editing.value ? "编辑业务连接" : "新建业务连接"));
const statusMeta = {
  untested: { label: "未验证", type: "info" as const },
  available: { label: "连接可用", type: "success" as const },
  error: { label: "连接异常", type: "danger" as const },
};
const environmentLabel = { development: "开发", staging: "预发", production: "生产" };

function getStatusMeta(status: BusinessConnectionStatus) {
  return statusMeta[status];
}

function getEnvironmentLabel(environment: BusinessConnectionEnvironment) {
  return environmentLabel[environment];
}

function resetForm() {
  editing.value = null;
  Object.assign(form, {
    team_id: teamScopeStore.selectedTeamId ?? teams.value[0]?.id ?? null,
    name: "",
    description: "",
    environment: "production",
    base_url: "",
    auth_type: "none",
    auth_secret_ref: "",
    auth_header_name: "X-API-Key",
    enabled: true,
  });
}

function openCreate() {
  resetForm();
  drawerVisible.value = true;
}

function openEdit(connection: BusinessConnectionModel) {
  editing.value = connection;
  Object.assign(form, {
    team_id: connection.team_id,
    name: connection.name,
    description: connection.description ?? "",
    environment: connection.environment,
    base_url: connection.base_url,
    auth_type: connection.auth_type,
    auth_secret_ref: connection.auth_secret_ref ?? "",
    auth_header_name: connection.auth_header_name ?? "X-API-Key",
    enabled: connection.enabled,
  });
  drawerVisible.value = true;
}

async function loadData() {
  if (loading.value) return;
  loading.value = true;
  try {
    const [response, teamItems] = await Promise.all([
      listBusinessConnections({
        team_id: teamScopeStore.selectedTeamId ?? undefined,
        keyword: filters.keyword.trim() || undefined,
        status: filters.status,
        page: pagination.page,
        page_size: pagination.pageSize,
      }),
      listTeamOptions({ limit: 100, include_team_id: teamScopeStore.selectedTeamId ?? undefined }),
    ]);
    connections.value = response.items;
    teams.value = teamItems;
    pagination.total = response.total;
    pagination.page = response.page;
    pagination.pageSize = response.page_size;
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "业务连接加载失败。"));
  } finally {
    loading.value = false;
  }
}

function buildPayload(): BusinessConnectionPayload {
  if (!form.team_id || !form.name.trim() || !form.base_url.trim()) {
    throw new Error("请填写所属团队、连接名称和基础地址。 ");
  }
  if (form.auth_type !== "none" && !form.auth_secret_ref.trim()) {
    throw new Error("请填写保存密钥的环境变量名称。 ");
  }
  if (form.auth_type === "header" && !form.auth_header_name.trim()) {
    throw new Error("请填写自定义请求头名称。 ");
  }
  return {
    team_id: form.team_id,
    name: form.name.trim(),
    description: form.description.trim() || null,
    environment: form.environment,
    base_url: form.base_url.trim(),
    auth_type: form.auth_type,
    auth_secret_ref: form.auth_type === "none" ? null : form.auth_secret_ref.trim(),
    auth_header_name: form.auth_type === "header" ? form.auth_header_name.trim() : null,
    enabled: form.enabled,
  };
}

async function submit() {
  let payload: BusinessConnectionPayload;
  try {
    payload = buildPayload();
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : "请检查连接配置。 ");
    return;
  }
  saving.value = true;
  try {
    if (editing.value) await updateBusinessConnection(editing.value.id, payload);
    else await createBusinessConnection(payload);
    ElMessage.success(editing.value ? "业务连接已更新，请重新测试。" : "业务连接已创建，请进行连接测试。 ");
    drawerVisible.value = false;
    await loadData();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "保存业务连接失败。"));
  } finally {
    saving.value = false;
  }
}

async function handleTest(connection: BusinessConnectionModel) {
  testingId.value = connection.id;
  try {
    const result = await testBusinessConnection(connection.id);
    (result.success ? ElMessage.success : ElMessage.error)(result.message);
    await loadData();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "连接测试失败。"));
  } finally {
    testingId.value = null;
  }
}

async function handleDelete(connection: BusinessConnectionModel) {
  try {
    await ElMessageBox.confirm(
      `确定删除“${connection.name}”吗？仅没有工具引用时才能删除。`,
      "删除业务连接",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  deletingId.value = connection.id;
  try {
    await deleteBusinessConnection(connection.id);
    ElMessage.success("业务连接已删除。 ");
    await loadData();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除业务连接失败。"));
  } finally {
    deletingId.value = null;
  }
}

onMounted(() => void teamScopeStore.bootstrap({ allowAllTeams: true }).finally(loadData));
watch(() => teamScopeStore.selectedTeamId, () => { pagination.page = 1; void loadData(); });
</script>

<template>
  <section class="connection-page">
    <AdminListPanel>
      <BusinessToolModuleNav />
      <div class="connection-page__intro">
        <div class="connection-page__icon"><el-icon><Connection /></el-icon></div>
        <div>
          <strong>集中管理外部业务系统的地址与鉴权</strong>
          <p>一个连接可以承载多个工具。平台只保存环境变量名称，不保存真实密钥。</p>
        </div>
      </div>
      <AdminTableToolbar>
        <template #left>
          <el-input v-model="filters.keyword" clearable placeholder="搜索连接名称或地址..." class="connection-page__search" @keyup.enter="pagination.page = 1; loadData()" @clear="pagination.page = 1; loadData()">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="filters.status" class="connection-page__status" @change="pagination.page = 1; loadData()">
            <el-option label="全部状态" value="all" />
            <el-option label="未验证" value="untested" />
            <el-option label="连接可用" value="available" />
            <el-option label="连接异常" value="error" />
          </el-select>
          <el-button type="primary" :loading="loading" @click="pagination.page = 1; loadData()">搜索</el-button>
        </template>
        <template #right>
          <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建连接</el-button>
        </template>
      </AdminTableToolbar>

      <AppEmpty v-if="!loading && connections.length === 0" title="还没有业务连接" description="先配置外部业务系统的基础地址和鉴权方式，再创建具体工具。">
        <el-button type="primary" @click="openCreate">新建连接</el-button>
      </AppEmpty>
      <AdminDataTable v-else :data="connections" :loading="loading" loading-text="正在更新业务连接">
        <el-table-column label="连接" min-width="240">
          <template #default="{ row }">
            <button type="button" class="connection-page__name" @click="openEdit(row)">
              <strong>{{ row.name }}</strong>
              <span>{{ row.description || "暂无说明" }}</span>
            </button>
          </template>
        </el-table-column>
        <el-table-column label="环境" width="100" align="center">
          <template #default="{ row }"><el-tag effect="plain" type="info">{{ getEnvironmentLabel(row.environment) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="基础地址" min-width="280" show-overflow-tooltip prop="base_url" />
        <el-table-column label="鉴权" width="130">
          <template #default="{ row }"><span>{{ row.auth_type === "none" ? "无需鉴权" : row.auth_type === "bearer" ? "Bearer Token" : "自定义 Header" }}</span></template>
        </el-table-column>
        <el-table-column label="工具数" width="90" align="center" prop="tool_count" />
        <el-table-column label="状态" width="120" align="center">
          <template #default="{ row }"><el-tag :type="getStatusMeta(row.status).type" effect="plain">{{ getStatusMeta(row.status).label }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right" align="right">
          <template #default="{ row }">
            <el-button link type="primary" :loading="testingId === row.id" @click="handleTest(row)">测试连接</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" :loading="deletingId === row.id" @click="handleDelete(row)"><el-icon><Delete /></el-icon></el-button>
          </template>
        </el-table-column>
      </AdminDataTable>
      <AdminPagination :current-page="pagination.page" :page-size="pagination.pageSize" :total="pagination.total" @page-change="(page) => { pagination.page = page; loadData(); }" @page-size-change="(size) => { pagination.pageSize = size; pagination.page = 1; loadData(); }" />
    </AdminListPanel>

    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="min(560px, 100%)" destroy-on-close>
      <el-form label-position="top" class="connection-page__form" @submit.prevent="submit">
        <section class="connection-page__section">
          <header><h3>基本信息</h3><p>用于识别外部业务系统和运行环境。</p></header>
          <el-form-item label="所属团队" required><el-select v-model="form.team_id" filterable class="w-full"><el-option v-for="team in teams" :key="team.id" :label="team.name" :value="team.id" /></el-select></el-form-item>
          <el-form-item label="连接名称" required><el-input v-model="form.name" maxlength="100" placeholder="例如：生产环境商品中心" /></el-form-item>
          <el-form-item label="说明"><el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="说明该系统提供的业务数据" /></el-form-item>
          <el-form-item label="运行环境"><el-segmented v-model="form.environment" :options="[{ label: '开发', value: 'development' }, { label: '预发', value: 'staging' }, { label: '生产', value: 'production' }]" /></el-form-item>
        </section>
        <section class="connection-page__section">
          <header><h3>连接与鉴权</h3><p>工具会在此基础地址下使用相对路径发起请求。</p></header>
          <el-form-item label="基础地址" required><el-input v-model="form.base_url" placeholder="https://api.example.com" /></el-form-item>
          <el-form-item label="鉴权方式"><el-select v-model="form.auth_type" class="w-full"><el-option label="无需鉴权" value="none" /><el-option label="Bearer Token" value="bearer" /><el-option label="自定义请求头" value="header" /></el-select></el-form-item>
          <el-form-item v-if="form.auth_type === 'header'" label="请求头名称" required><el-input v-model="form.auth_header_name" placeholder="例如：X-API-Key" /></el-form-item>
          <el-form-item v-if="form.auth_type !== 'none'" label="密钥环境变量" required>
            <el-input v-model="form.auth_secret_ref" placeholder="例如：PRODUCT_API_TOKEN" />
            <p class="connection-page__help">后台只保存环境变量名称。请在后端运行环境中配置真实密钥。</p>
          </el-form-item>
          <el-form-item label="连接状态"><el-switch v-model="form.enabled" active-text="允许工具使用此连接" /></el-form-item>
        </section>
      </el-form>
      <template #footer><div class="connection-page__footer"><el-button @click="drawerVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">保存连接</el-button></div></template>
    </el-drawer>
  </section>
</template>

<style scoped>
.connection-page__intro { display: flex; align-items: center; gap: 14px; border-bottom: 1px solid var(--admin-border-soft); background: var(--admin-primary-soft); padding: 16px 20px; }
.connection-page__icon { display: inline-flex; width: 36px; height: 36px; align-items: center; justify-content: center; border: 1px solid var(--admin-primary-border); border-radius: var(--admin-radius-md); background: white; color: var(--admin-primary); font-size: 18px; }
.connection-page__intro strong { color: var(--admin-text); font-size: 14px; }
.connection-page__intro p { margin: 4px 0 0; color: var(--admin-text-muted); font-size: 12px; }
.connection-page__search { width: 300px; }.connection-page__status { width: 130px; }
.connection-page__name { display: grid; width: 100%; gap: 4px; border: 0; background: transparent; padding: 0; cursor: pointer; text-align: left; }
.connection-page__name strong { color: var(--admin-text); font-size: 14px; }.connection-page__name:hover strong { color: var(--admin-primary); }
.connection-page__name span { overflow: hidden; color: var(--admin-text-muted); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.connection-page__form { display: grid; gap: 18px; }
.connection-page__section { border: 1px solid var(--admin-border); border-radius: var(--admin-radius-lg); background: var(--admin-surface); padding: 18px; }
.connection-page__section header { margin-bottom: 18px; }.connection-page__section h3 { margin: 0; color: var(--admin-text); font-size: 15px; }.connection-page__section header p { margin: 5px 0 0; color: var(--admin-text-muted); font-size: 12px; }
.connection-page__section :deep(.el-form-item:last-child) { margin-bottom: 0; }
.connection-page__help { margin: 6px 0 0; color: var(--admin-text-muted); font-size: 12px; line-height: 1.5; }
.connection-page__footer { display: flex; justify-content: flex-end; gap: 10px; }
@media (max-width: 760px) { .connection-page__search, .connection-page__status { width: 100%; } .connection-page__intro { align-items: flex-start; } }
</style>
