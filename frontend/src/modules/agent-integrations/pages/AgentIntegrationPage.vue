<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Delete, EditPen, Plus, Refresh, Search, View } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import AdminDataTable from "@/app/components/admin/AdminDataTable.vue";
import AdminDialog from "@/app/components/admin/AdminDialog.vue";
import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
import {
  createMcpServer,
  deleteMcpServer,
  listMcpServers,
  listMcpTools,
  testMcpServer,
  updateMcpServer,
  updateMcpToolEnabled,
} from "@/shared/api/agent-integrations";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import type { McpServer, McpServerPayload, McpTool } from "@/shared/types/agent-integration";
import { getErrorMessage } from "@/shared/utils/error";

type StatusFilter = "all" | "available" | "untested" | "error";
type ToolStatusFilter = "all" | "enabled" | "disabled";

const servers = ref<McpServer[]>([]);
const selectedServer = ref<McpServer | null>(null);
const tools = ref<McpTool[]>([]);
const loadingServers = ref(false);
const loadingTools = ref(false);
const serverLoadError = ref<unknown>(null);
const toolLoadError = ref<unknown>(null);
const testingServerId = ref<number | null>(null);
const togglingToolId = ref<number | null>(null);
const deletingServerId = ref<number | null>(null);
const serverDialogVisible = ref(false);
const serverSaving = ref(false);
const editingServer = ref<McpServer | null>(null);
const schemaDialogVisible = ref(false);
const schemaViewingTool = ref<McpTool | null>(null);

const serverFilters = reactive({
  keyword: "",
  status: "all" as StatusFilter,
});

const toolFilters = reactive({
  keyword: "",
  status: "all" as ToolStatusFilter,
});

const serverForm = reactive<McpServerPayload>({
  team_id: 1,
  name: "",
  description: "",
  environment: "production",
  endpoint_url: "",
  transport_type: "http",
  auth_type: "none",
  auth_token: null,
  auth_header_name: null,
  enabled: true,
});

const displayedTools = computed(() => {
  if (toolFilters.status === "enabled") {
    return tools.value.filter((tool) => tool.agent_tool_enabled);
  }
  if (toolFilters.status === "disabled") {
    return tools.value.filter((tool) => !tool.agent_tool_enabled);
  }
  return tools.value;
});

const enabledToolCount = computed(() => tools.value.filter((tool) => tool.agent_tool_enabled).length);

function statusLabel(status: string) {
  return ({ available: "可用", untested: "未测试", error: "异常" } as Record<string, string>)[status] ?? status;
}

function statusTagType(status: string) {
  if (status === "available") return "success";
  if (status === "error") return "danger";
  return "info";
}

function resetServerForm() {
  Object.assign(serverForm, {
    team_id: 1,
    name: "",
    description: "",
    environment: "production",
    endpoint_url: "",
    transport_type: "http",
    auth_type: "none",
    auth_token: null,
    auth_header_name: null,
    enabled: true,
  });
}

async function loadServers(preferredServerId?: number | null) {
  if (loadingServers.value) return;
  loadingServers.value = true;
  serverLoadError.value = null;
  try {
    const response = await listMcpServers({
      keyword: serverFilters.keyword.trim() || undefined,
      status: serverFilters.status,
      page: 1,
      page_size: 100,
    });
    servers.value = response.items;
    const targetId = preferredServerId ?? selectedServer.value?.id ?? null;
    selectedServer.value = servers.value.find((server) => server.id === targetId) ?? servers.value[0] ?? null;
    await loadTools();
  } catch (error) {
    serverLoadError.value = error;
  } finally {
    loadingServers.value = false;
  }
}

async function loadTools() {
  tools.value = [];
  toolLoadError.value = null;
  if (!selectedServer.value) return;
  loadingTools.value = true;
  try {
    const response = await listMcpTools({
      server_id: selectedServer.value.id,
      keyword: toolFilters.keyword.trim() || undefined,
      page: 1,
      page_size: 100,
    });
    tools.value = response.items;
  } catch (error) {
    toolLoadError.value = error;
  } finally {
    loadingTools.value = false;
  }
}

function selectServer(server: McpServer) {
  if (selectedServer.value?.id === server.id) return;
  selectedServer.value = server;
  toolFilters.keyword = "";
  toolFilters.status = "all";
  void loadTools();
}

function openCreateServerDialog() {
  editingServer.value = null;
  resetServerForm();
  serverDialogVisible.value = true;
}

function openEditServerDialog(server: McpServer) {
  editingServer.value = server;
  Object.assign(serverForm, {
    team_id: server.team_id,
    name: server.name,
    description: server.description ?? "",
    environment: server.environment,
    endpoint_url: server.endpoint_url,
    transport_type: server.transport_type,
    auth_type: server.auth_type,
    auth_token: null,
    auth_header_name: server.auth_header_name ?? null,
    enabled: server.enabled,
  });
  serverDialogVisible.value = true;
}

async function saveServer() {
  if (serverSaving.value) return;
  if (!serverForm.name.trim() || !serverForm.endpoint_url.trim()) {
    ElMessage.warning("请填写服务名称和 Endpoint。");
    return;
  }
  serverSaving.value = true;
  try {
    const payload: McpServerPayload = {
      ...serverForm,
      name: serverForm.name.trim(),
      description: serverForm.description?.trim() || null,
      endpoint_url: serverForm.endpoint_url.trim(),
      auth_token: serverForm.auth_token?.trim() || null,
      auth_header_name: serverForm.auth_header_name?.trim() || null,
    };
    const saved = editingServer.value
      ? await updateMcpServer(editingServer.value.id, payload)
      : await createMcpServer(payload);
    serverDialogVisible.value = false;
    await loadServers(saved.id);
    ElMessage.success("MCP 服务已保存。");
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "保存 MCP 服务失败，请稍后重试。"));
  } finally {
    serverSaving.value = false;
  }
}

async function handleTestServer(server: McpServer) {
  if (testingServerId.value) return;
  testingServerId.value = server.id;
  try {
    const result = await testMcpServer(server.id);
    await loadServers(server.id);
    ElMessage[result.success ? "success" : "error"](result.message);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "测试 MCP 服务失败，请稍后重试。"));
  } finally {
    testingServerId.value = null;
  }
}

async function handleDeleteServer(server: McpServer) {
  try {
    await ElMessageBox.confirm(
      `确定删除 MCP 工具集“${server.name}”吗？对应应用绑定也会一并移除。`,
      "删除 MCP 工具集",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  deletingServerId.value = server.id;
  try {
    await deleteMcpServer(server.id);
    await loadServers(selectedServer.value?.id === server.id ? null : selectedServer.value?.id);
    ElMessage.success("MCP 工具集已删除。");
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除 MCP 工具集失败，请稍后重试。"));
  } finally {
    deletingServerId.value = null;
  }
}

async function handleToolEnabledChange(tool: McpTool, value: unknown) {
  if (togglingToolId.value) return;
  const enabled = Boolean(value);
  togglingToolId.value = tool.id;
  try {
    const updated = await updateMcpToolEnabled(tool.id, enabled);
    const index = tools.value.findIndex((item) => item.id === tool.id);
    if (index >= 0) tools.value[index] = updated;
    ElMessage.success(enabled ? "工具已启用。" : "工具已停用。");
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "更新工具状态失败，请稍后重试。"));
  } finally {
    togglingToolId.value = null;
  }
}

function openSchemaDialog(tool: McpTool) {
  schemaViewingTool.value = tool;
  schemaDialogVisible.value = true;
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

onMounted(() => {
  void loadServers();
});
</script>

<template>
  <section class="agent-integration-page">
    <AppLoading
      v-if="loadingServers && servers.length === 0"
      title="MCP 工具集加载中"
      description="正在获取 MCP 服务和已同步工具，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="serverLoadError"
      title="MCP 工具集加载失败"
      description="暂时无法获取 MCP 服务列表，请稍后重试。"
      :error="serverLoadError"
      @retry="loadServers()"
    />

    <section v-else class="agent-integration-page__workspace">
      <AdminListPanel>
        <AdminTableToolbar>
          <template #left>
            <el-input
              v-model="serverFilters.keyword"
              clearable
              placeholder="搜索 MCP 服务..."
              class="agent-integration-page__server-search"
              @keyup.enter="loadServers()"
              @clear="loadServers()"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-select v-model="serverFilters.status" class="agent-integration-page__status" @change="loadServers()">
              <el-option label="全部状态" value="all" />
              <el-option label="可用" value="available" />
              <el-option label="未测试" value="untested" />
              <el-option label="异常" value="error" />
            </el-select>
          </template>
          <template #right>
            <el-tooltip content="新增 MCP 服务" placement="top">
              <el-button type="primary" circle aria-label="新增 MCP 服务" @click="openCreateServerDialog">
                <el-icon><Plus /></el-icon>
              </el-button>
            </el-tooltip>
          </template>
        </AdminTableToolbar>

        <AppEmpty
          v-if="servers.length === 0"
          title="暂无 MCP 工具集"
          description="新增 MCP 服务后，通过测试连接自动同步工具。"
        >
          <el-button type="primary" @click="openCreateServerDialog">新增 MCP 服务</el-button>
        </AppEmpty>

        <div v-else class="agent-integration-page__server-list">
          <div
            v-for="server in servers"
            :key="server.id"
            class="agent-integration-page__server-row"
            :class="{ 'is-active': selectedServer?.id === server.id }"
          >
            <button type="button" class="agent-integration-page__server-main" @click="selectServer(server)">
              <span class="agent-integration-page__server-copy">
                <strong>{{ server.name }}</strong>
                <small>{{ server.description?.trim() || server.endpoint_url }}</small>
              </span>
              <span class="agent-integration-page__server-meta">
                <el-tag size="small" :type="statusTagType(server.status)" effect="plain">
                  {{ statusLabel(server.status) }}
                </el-tag>
                <span>{{ server.tool_count }} 个工具</span>
              </span>
            </button>
            <div class="agent-integration-page__server-actions">
              <el-tooltip content="编辑服务" placement="top">
                <el-button link type="primary" aria-label="编辑服务" @click.stop="openEditServerDialog(server)">
                  <el-icon><EditPen /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="删除服务" placement="top">
                <el-button
                  link
                  type="danger"
                  aria-label="删除服务"
                  :loading="deletingServerId === server.id"
                  @click.stop="handleDeleteServer(server)"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </div>
        </div>
      </AdminListPanel>

      <div class="agent-integration-page__tools">
        <AppEmpty
          v-if="!selectedServer"
          title="请选择 MCP 工具集"
          description="从左侧选择一个 MCP 服务后维护其工具。"
        />

        <AdminListPanel v-else>
          <div class="agent-integration-page__tool-heading">
            <div>
              <span>MCP 工具集</span>
              <h2>{{ selectedServer.name }}</h2>
              <p>{{ enabledToolCount }} / {{ tools.length }} 个工具已启用</p>
            </div>
            <el-button
              type="primary"
              :loading="testingServerId === selectedServer.id"
              @click="handleTestServer(selectedServer)"
            >
              <el-icon><Refresh /></el-icon>
              测试并同步
            </el-button>
          </div>

          <AdminTableToolbar>
            <template #left>
              <el-input
                v-model="toolFilters.keyword"
                clearable
                placeholder="搜索工具名称或描述..."
                class="agent-integration-page__tool-search"
                @keyup.enter="loadTools"
                @clear="loadTools"
              >
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
              <el-select v-model="toolFilters.status" class="agent-integration-page__status">
                <el-option label="全部工具" value="all" />
                <el-option label="已启用" value="enabled" />
                <el-option label="已停用" value="disabled" />
              </el-select>
            </template>
          </AdminTableToolbar>

          <AppLoading
            v-if="loadingTools"
            title="工具列表加载中"
            description="正在读取当前 MCP 服务已同步的工具。"
            :blocks="3"
          />
          <AppError
            v-else-if="toolLoadError"
            title="工具列表加载失败"
            description="暂时无法获取当前 MCP 工具集。"
            :error="toolLoadError"
            @retry="loadTools"
          />
          <AppEmpty
            v-else-if="displayedTools.length === 0"
            :title="tools.length === 0 ? '暂无同步工具' : '未找到符合条件的工具'"
            :description="tools.length === 0 ? '点击测试并同步，从 MCP 服务获取当前工具。' : '请调整搜索词或状态筛选。'"
          />
          <AdminDataTable v-else :data="displayedTools" table-class="agent-integration-page__tool-table">
            <el-table-column label="工具" min-width="280">
              <template #default="{ row }">
                <div class="agent-integration-page__tool-name">
                  <strong>{{ row.raw_name }}</strong>
                  <span>{{ row.raw_description?.trim() || "暂无工具说明" }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="参数" width="100" align="center">
              <template #default="{ row }">
                <el-tooltip content="查看参数 Schema" placement="top">
                  <el-button link type="primary" aria-label="查看参数 Schema" @click="openSchemaDialog(row)">
                    <el-icon><View /></el-icon>
                  </el-button>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="130" align="center">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.agent_tool_enabled"
                  :loading="togglingToolId === row.id"
                  inline-prompt
                  active-text="启用"
                  inactive-text="停用"
                  @change="handleToolEnabledChange(row, $event)"
                />
              </template>
            </el-table-column>
          </AdminDataTable>
        </AdminListPanel>
      </div>
    </section>

    <AdminDialog
      v-model="serverDialogVisible"
      :title="editingServer ? '编辑 MCP 服务' : '新增 MCP 服务'"
      width="640px"
      :loading="serverSaving"
    >
      <el-form label-position="top" @submit.prevent="saveServer">
        <div class="agent-integration-page__form-grid">
          <el-form-item label="团队 ID" required>
            <el-input-number v-model="serverForm.team_id" :min="1" class="agent-integration-page__full-control" />
          </el-form-item>
          <el-form-item label="服务名称" required>
            <el-input v-model.trim="serverForm.name" maxlength="100" placeholder="例如：库存查询服务" />
          </el-form-item>
        </div>
        <el-form-item label="Endpoint" required>
          <el-input v-model.trim="serverForm.endpoint_url" placeholder="https://example.com/mcp" />
        </el-form-item>
        <div class="agent-integration-page__form-grid">
          <el-form-item label="环境">
            <el-input v-model.trim="serverForm.environment" />
          </el-form-item>
          <el-form-item label="鉴权方式">
            <el-select v-model="serverForm.auth_type" class="agent-integration-page__full-control">
              <el-option label="无" value="none" />
              <el-option label="Bearer Token" value="bearer" />
              <el-option label="自定义 Header" value="header" />
            </el-select>
          </el-form-item>
        </div>
        <div v-if="serverForm.auth_type !== 'none'" class="agent-integration-page__form-grid">
          <el-form-item label="内部服务 Token" required>
            <el-input
              v-model.trim="serverForm.auth_token"
              type="password"
              show-password
              autocomplete="new-password"
              :placeholder="editingServer?.auth_token_masked ? `已配置 ${editingServer.auth_token_masked}，留空保持不变` : '请输入业务端配置的 Token'"
            />
          </el-form-item>
          <el-form-item v-if="serverForm.auth_type === 'header'" label="Header 名称">
            <el-input v-model.trim="serverForm.auth_header_name" placeholder="例如：X-API-Key" />
          </el-form-item>
        </div>
        <el-form-item label="服务说明">
          <el-input v-model.trim="serverForm.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="服务状态">
          <el-switch v-model="serverForm.enabled" inline-prompt active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="serverDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="serverSaving" @click="saveServer">保存</el-button>
      </template>
    </AdminDialog>

    <AdminDialog
      v-model="schemaDialogVisible"
      :title="`工具参数：${schemaViewingTool?.raw_name || ''}`"
      width="760px"
    >
      <div class="agent-integration-page__schema-grid">
        <section>
          <h3>入参 Schema</h3>
          <pre>{{ formatJson(schemaViewingTool?.input_schema || {}) }}</pre>
        </section>
        <section>
          <h3>出参 Schema</h3>
          <pre>{{ formatJson(schemaViewingTool?.output_schema || {}) }}</pre>
        </section>
      </div>
      <template #footer>
        <el-button type="primary" @click="schemaDialogVisible = false">关闭</el-button>
      </template>
    </AdminDialog>
  </section>
</template>

<style scoped>
.agent-integration-page {
  min-width: 0;
}

.agent-integration-page__workspace {
  display: grid;
  min-width: 0;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 16px;
}

.agent-integration-page__server-search {
  min-width: 0;
  width: 180px;
}

.agent-integration-page__tool-search {
  width: min(360px, 100%);
}

.agent-integration-page__status {
  width: 132px;
}

.agent-integration-page__server-list {
  display: grid;
}

.agent-integration-page__server-row {
  display: grid;
  min-width: 0;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  border-top: 1px solid #e5e7eb;
  transition: background-color 180ms ease, border-color 180ms ease;
}

.agent-integration-page__server-row:first-child {
  border-top: 0;
}

.agent-integration-page__server-row:hover,
.agent-integration-page__server-row.is-active {
  background: #f8fafc;
}

.agent-integration-page__server-row.is-active {
  box-shadow: inset 3px 0 0 var(--el-color-primary);
}

.agent-integration-page__server-main {
  display: grid;
  min-width: 0;
  gap: 10px;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 14px 10px 14px 16px;
  text-align: left;
}

.agent-integration-page__server-main:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: -2px;
}

.agent-integration-page__server-copy,
.agent-integration-page__server-copy strong,
.agent-integration-page__server-copy small {
  display: block;
  min-width: 0;
}

.agent-integration-page__server-copy strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-integration-page__server-copy small {
  overflow: hidden;
  margin-top: 5px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-integration-page__server-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
}

.agent-integration-page__server-actions {
  display: flex;
  align-items: center;
  padding-right: 10px;
}

.agent-integration-page__tools {
  min-width: 0;
}

.agent-integration-page__tool-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid #e5e7eb;
  padding: 18px 20px;
}

.agent-integration-page__tool-heading span {
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

.agent-integration-page__tool-heading h2 {
  margin: 3px 0 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 750;
}

.agent-integration-page__tool-heading p {
  margin: 5px 0 0;
  color: #64748b;
  font-size: 12px;
}

.agent-integration-page__tool-name {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.agent-integration-page__tool-name strong {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
}

.agent-integration-page__tool-name span {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-integration-page__form-grid,
.agent-integration-page__schema-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.agent-integration-page__full-control {
  width: 100%;
}

.agent-integration-page__schema-grid h3 {
  margin: 0 0 8px;
  color: #334155;
  font-size: 13px;
}

.agent-integration-page__schema-grid pre {
  max-height: 360px;
  overflow: auto;
  margin: 0;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
  line-height: 1.6;
  padding: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 980px) {
  .agent-integration-page__workspace {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .agent-integration-page__tool-heading,
  .agent-integration-page__form-grid,
  .agent-integration-page__schema-grid {
    grid-template-columns: 1fr;
  }

  .agent-integration-page__tool-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .agent-integration-page__server-search,
  .agent-integration-page__tool-search,
  .agent-integration-page__status {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .agent-integration-page__server-row {
    transition: none;
  }
}
</style>
