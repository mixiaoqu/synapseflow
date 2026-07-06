<script setup lang="ts">
import { onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { RefreshRight } from "@element-plus/icons-vue";

import AdminDataTable from "@/app/components/admin/AdminDataTable.vue";
import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminPagination from "@/app/components/admin/AdminPagination.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import BusinessToolModuleNav from "@/modules/business-tools/components/BusinessToolModuleNav.vue";
import { listBusinessToolCallLogs, listBusinessTools } from "@/shared/api/business-tools";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import type { BusinessTool, BusinessToolCallLog } from "@/shared/types/business-tool";
import { getErrorMessage } from "@/shared/utils/error";
import { useTeamScopeStore } from "@/stores/team-scope";

const teamScopeStore = useTeamScopeStore();
const logs = ref<BusinessToolCallLog[]>([]);
const tools = ref<BusinessTool[]>([]);
const loading = ref(false);
const detailVisible = ref(false);
const selectedLog = ref<BusinessToolCallLog | null>(null);
const filters = reactive({
  status: "all" as "all" | "success" | "error",
  toolId: undefined as number | undefined,
  dateRange: [] as Date[],
});
const pagination = reactive({ page: 1, pageSize: 20, total: 0 });

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).format(date);
}

function formatJson(value: Record<string, unknown>) {
  return JSON.stringify(value ?? {}, null, 2);
}

async function loadData() {
  if (loading.value) return;
  loading.value = true;
  try {
    const [logResponse, toolResponse] = await Promise.all([
      listBusinessToolCallLogs({
        team_id: teamScopeStore.selectedTeamId ?? undefined,
        tool_id: filters.toolId,
        status: filters.status,
        started_at: filters.dateRange[0]?.toISOString(),
        ended_at: filters.dateRange[1]?.toISOString(),
        page: pagination.page,
        page_size: pagination.pageSize,
      }),
      listBusinessTools({ team_id: teamScopeStore.selectedTeamId ?? undefined, page: 1, page_size: 100 }),
    ]);
    logs.value = logResponse.items;
    tools.value = toolResponse.items;
    pagination.total = logResponse.total;
    pagination.page = logResponse.page;
    pagination.pageSize = logResponse.page_size;
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "调用记录加载失败。"));
  } finally {
    loading.value = false;
  }
}

function refresh() { pagination.page = 1; void loadData(); }
function resetFilters() { filters.status = "all"; filters.toolId = undefined; filters.dateRange = []; refresh(); }
function openDetail(log: BusinessToolCallLog) { selectedLog.value = log; detailVisible.value = true; }

onMounted(() => void teamScopeStore.bootstrap({ allowAllTeams: true }).finally(loadData));
watch(() => teamScopeStore.selectedTeamId, refresh);
</script>

<template>
  <section class="tool-log-page">
    <AdminListPanel>
      <BusinessToolModuleNav />
      <div class="tool-log-page__intro">
        <div><strong>从一次调用快速定位配置或接口问题</strong><p>记录经过脱敏和截断，展示工具、应用、状态、耗时与请求响应摘要。</p></div>
        <el-button plain :loading="loading" @click="loadData"><el-icon><RefreshRight /></el-icon>刷新记录</el-button>
      </div>
      <AdminTableToolbar>
        <template #left>
          <el-select v-model="filters.status" class="tool-log-page__status" @change="refresh"><el-option label="全部结果" value="all" /><el-option label="调用成功" value="success" /><el-option label="调用失败" value="error" /></el-select>
          <el-select v-model="filters.toolId" clearable filterable placeholder="全部工具" class="tool-log-page__tool" @change="refresh"><el-option v-for="tool in tools" :key="tool.id" :label="tool.name" :value="tool.id" /></el-select>
          <el-date-picker v-model="filters.dateRange" type="datetimerange" range-separator="至" start-placeholder="开始时间" end-placeholder="结束时间" class="tool-log-page__date" @change="refresh" />
          <el-button type="primary" :loading="loading" @click="refresh">筛选</el-button><el-button @click="resetFilters">重置</el-button>
        </template>
      </AdminTableToolbar>
      <AppEmpty v-if="!loading && logs.length === 0" title="暂无调用记录" description="工具经过发布并被应用端实际调用后，记录会显示在这里。" />
      <AdminDataTable v-else :data="logs" :loading="loading" loading-text="正在更新调用记录">
        <el-table-column label="调用时间" width="185"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
        <el-table-column label="工具 / 接口" min-width="240"><template #default="{ row }"><button type="button" class="tool-log-page__tool-name" @click="openDetail(row)"><strong>{{ row.tool_name }}</strong><code>{{ row.tool_key }}</code><small>{{ row.api_name || "未记录接口" }}</small></button></template></el-table-column>
        <el-table-column label="应用端" min-width="160"><template #default="{ row }">{{ row.project_app_name || (row.project_app_id ? `应用 #${row.project_app_id}` : "后台测试") }}</template></el-table-column>
        <el-table-column label="结果" width="110" align="center"><template #default="{ row }"><el-tag :type="row.status === 'success' ? 'success' : 'danger'" effect="plain">{{ row.status === "success" ? "成功" : "失败" }}</el-tag></template></el-table-column>
        <el-table-column label="HTTP" width="85" align="center"><template #default="{ row }">{{ row.http_status ?? "—" }}</template></el-table-column>
        <el-table-column label="耗时" width="100" align="right"><template #default="{ row }">{{ row.duration_ms === null ? "—" : `${row.duration_ms} ms` }}</template></el-table-column>
        <el-table-column label="错误摘要" min-width="220" show-overflow-tooltip><template #default="{ row }"><span :class="{ 'tool-log-page__error': row.error_message }">{{ row.error_message || "—" }}</span></template></el-table-column>
        <el-table-column label="操作" width="80" fixed="right" align="right"><template #default="{ row }"><el-button link type="primary" @click="openDetail(row)">详情</el-button></template></el-table-column>
      </AdminDataTable>
      <AdminPagination :current-page="pagination.page" :page-size="pagination.pageSize" :total="pagination.total" @page-change="(page) => { pagination.page = page; loadData(); }" @page-size-change="(size) => { pagination.pageSize = size; pagination.page = 1; loadData(); }" />
    </AdminListPanel>

    <el-drawer v-model="detailVisible" title="调用详情" size="min(720px, 100%)">
      <div v-if="selectedLog" class="tool-log-detail">
        <section class="tool-log-detail__summary">
          <div><span>调用结果</span><el-tag :type="selectedLog.status === 'success' ? 'success' : 'danger'" effect="plain">{{ selectedLog.status === "success" ? "成功" : "失败" }}</el-tag></div>
          <div><span>HTTP 状态</span><strong>{{ selectedLog.http_status ?? "未响应" }}</strong></div>
          <div><span>调用耗时</span><strong>{{ selectedLog.duration_ms ?? 0 }} ms</strong></div>
        </section>
        <section class="tool-log-detail__meta"><h3>调用信息</h3><dl><div><dt>工具</dt><dd>{{ selectedLog.tool_name }}（{{ selectedLog.tool_key }}）</dd></div><div><dt>接口</dt><dd>{{ selectedLog.api_name || "—" }}<template v-if="selectedLog.api_key">（{{ selectedLog.api_key }}）</template></dd></div><div><dt>应用端</dt><dd>{{ selectedLog.project_app_name || "后台测试" }}</dd></div><div><dt>会话</dt><dd>{{ selectedLog.session_id || "—" }}</dd></div><div><dt>外部用户</dt><dd>{{ selectedLog.external_user_id || "—" }}</dd></div><div><dt>发生时间</dt><dd>{{ formatDate(selectedLog.created_at) }}</dd></div></dl></section>
        <section v-if="selectedLog.error_message" class="tool-log-detail__error"><h3>失败原因</h3><p>{{ selectedLog.error_message }}</p></section>
        <section><h3>请求摘要</h3><pre>{{ formatJson(selectedLog.request_payload) }}</pre></section>
        <section><h3>响应摘要</h3><pre>{{ formatJson(selectedLog.response_payload) }}</pre></section>
      </div>
    </el-drawer>
  </section>
</template>

<style scoped>
.tool-log-page__intro { display: flex; align-items: center; justify-content: space-between; gap: 18px; border-bottom: 1px solid var(--admin-border-soft); background: var(--admin-primary-soft); padding: 16px 20px; }.tool-log-page__intro strong { color: var(--admin-text); font-size: 14px; }.tool-log-page__intro p { margin: 4px 0 0; color: var(--admin-text-muted); font-size: 12px; }.tool-log-page__status { width: 130px; }.tool-log-page__tool { width: 200px; }.tool-log-page__date { width: 360px; }.tool-log-page__tool-name { display: grid; gap: 4px; border: 0; background: transparent; padding: 0; cursor: pointer; text-align: left; }.tool-log-page__tool-name strong { color: var(--admin-text); font-size: 13px; }.tool-log-page__tool-name:hover strong { color: var(--admin-primary); }.tool-log-page__tool-name code, .tool-log-page__tool-name small { color: var(--admin-text-muted); font-size: 11px; }.tool-log-page__error { color: var(--admin-danger); }
.tool-log-detail { display: grid; gap: 16px; }.tool-log-detail > section { border: 1px solid var(--admin-border); border-radius: var(--admin-radius-md); background: var(--admin-surface); padding: 16px; }.tool-log-detail h3 { margin: 0 0 13px; color: var(--admin-text); font-size: 14px; }.tool-log-detail__summary { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 12px; }.tool-log-detail__summary div { display: grid; gap: 7px; border-right: 1px solid var(--admin-border-soft); }.tool-log-detail__summary div:last-child { border-right: 0; }.tool-log-detail__summary span,.tool-log-detail dt { color: var(--admin-text-muted); font-size: 12px; }.tool-log-detail__summary strong { color: var(--admin-text); font-size: 18px; }.tool-log-detail dl { display: grid; gap: 10px; margin: 0; }.tool-log-detail dl div { display: grid; grid-template-columns: 90px 1fr; gap: 12px; }.tool-log-detail dd { margin: 0; color: var(--admin-text-secondary); font-size: 13px; }.tool-log-detail__error { border-color: #fecaca !important; background: #fef2f2 !important; }.tool-log-detail__error h3,.tool-log-detail__error p { color: var(--admin-danger); }.tool-log-detail__error p { margin: 0; font-size: 13px; line-height: 1.6; }.tool-log-detail pre { max-height: 380px; overflow: auto; margin: 0; border-radius: var(--admin-radius-sm); background: #0f172a; padding: 14px; color: #e2e8f0; font-family: Consolas,"Courier New",monospace; font-size: 12px; line-height: 1.6; white-space: pre-wrap; }
@media (max-width: 760px) { .tool-log-page__intro { align-items: flex-start; flex-direction: column; }.tool-log-page__status,.tool-log-page__tool,.tool-log-page__date { width: 100%; }.tool-log-detail__summary { grid-template-columns: 1fr; }.tool-log-detail__summary div { border-right: 0; border-bottom: 1px solid var(--admin-border-soft); padding-bottom: 10px; }.tool-log-detail__summary div:last-child { border-bottom: 0; }.tool-log-detail dl div { grid-template-columns: 1fr; gap: 3px; } }
</style>
