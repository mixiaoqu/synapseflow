<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { Connection, Delete, EditPen, Plus, Refresh, Search, Upload } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import AdminDialog from "@/app/components/admin/AdminDialog.vue";
import {
  createToolProvider,
  deleteToolProvider,
  listAgentTools,
  listToolProviders,
  publishAgentTool,
  syncAgentTools,
  testAgentTool,
  testToolProvider,
  unpublishAgentTool,
  updateAgentTool,
  updateToolProvider,
} from "@/shared/api/agent-integrations";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import type {
  AgentTool,
  AgentToolUpdatePayload,
  ToolProvider,
  ToolProviderPayload,
} from "@/shared/types/agent-integration";
import { getErrorMessage } from "@/shared/utils/error";

const providers = ref<ToolProvider[]>([]);
const selectedProvider = ref<ToolProvider | null>(null);
const tools = ref<AgentTool[]>([]);
const loadingProviders = ref(false);
const loadingTools = ref(false);
const providerError = ref<unknown>(null);
const toolError = ref<unknown>(null);
const providerKeyword = ref("");
const toolKeyword = ref("");
const providerDialogVisible = ref(false);
const providerSaving = ref(false);
const editingProvider = ref<ToolProvider | null>(null);
const activeProviderAction = ref<number | null>(null);
const toolDialogVisible = ref(false);
const toolSaving = ref(false);
const editingTool = ref<AgentTool | null>(null);
const testDialogVisible = ref(false);
const testingTool = ref(false);
const testToolTarget = ref<AgentTool | null>(null);
const testArguments = ref("{}");
const testContext = ref('{\n  "scope": {\n    "store_id": ""\n  }\n}');

const providerForm = reactive<ToolProviderPayload>({
  team_id: 1,
  code: "",
  name: "",
  description: "",
  base_url: "",
  transport_type: "business_http",
  auth_type: "bearer",
  auth_header_name: null,
  auth_token: null,
  enabled: true,
});

const toolForm = reactive<AgentToolUpdatePayload>({
  name: "",
  agent_description: "",
  risk_level: "low",
  requires_confirmation: false,
});

const publishedCount = computed(() => tools.value.filter((tool) => tool.publish_status === "published").length);

watch(
  () => providerForm.transport_type,
  (transportType) => {
    if (transportType === "business_http") {
      providerForm.auth_type = "bearer";
      providerForm.auth_header_name = null;
    }
  },
);

function healthLabel(status: string) {
  return ({ available: "可用", untested: "未测试", error: "异常" } as Record<string, string>)[status] ?? status;
}

function healthType(status: string) {
  if (status === "available") return "success";
  if (status === "error") return "danger";
  return "info";
}

function publishLabel(status: string) {
  return ({ draft: "草稿", published: "已发布", needs_review: "待审核" } as Record<string, string>)[status] ?? status;
}

function publishType(status: string) {
  if (status === "published") return "success";
  if (status === "needs_review") return "warning";
  return "info";
}

async function loadProviders(preferredId?: number | null) {
  loadingProviders.value = true;
  providerError.value = null;
  try {
    const response = await listToolProviders({
      keyword: providerKeyword.value.trim() || undefined,
      page: 1,
      page_size: 100,
    });
    providers.value = response.items;
    const targetId = preferredId ?? selectedProvider.value?.id ?? null;
    selectedProvider.value = providers.value.find((provider) => provider.id === targetId) ?? providers.value[0] ?? null;
    await loadTools();
  } catch (error) {
    providerError.value = error;
  } finally {
    loadingProviders.value = false;
  }
}

async function loadTools() {
  tools.value = [];
  toolError.value = null;
  if (!selectedProvider.value) return;
  loadingTools.value = true;
  try {
    const response = await listAgentTools({
      provider_id: selectedProvider.value.id,
      keyword: toolKeyword.value.trim() || undefined,
      page: 1,
      page_size: 100,
    });
    tools.value = response.items;
  } catch (error) {
    toolError.value = error;
  } finally {
    loadingTools.value = false;
  }
}

function selectProvider(provider: ToolProvider) {
  if (selectedProvider.value?.id === provider.id) return;
  selectedProvider.value = provider;
  toolKeyword.value = "";
  void loadTools();
}

function resetProviderForm() {
  Object.assign(providerForm, {
    team_id: 1,
    code: "",
    name: "",
    description: "",
    base_url: "",
    transport_type: "business_http",
    auth_type: "bearer",
    auth_header_name: null,
    auth_token: null,
    enabled: true,
  });
}

function openCreateProvider() {
  editingProvider.value = null;
  resetProviderForm();
  providerDialogVisible.value = true;
}

function openEditProvider(provider: ToolProvider) {
  editingProvider.value = provider;
  Object.assign(providerForm, {
    team_id: provider.team_id,
    code: provider.code,
    name: provider.name,
    description: provider.description ?? "",
    base_url: provider.base_url,
    transport_type: provider.transport_type,
    auth_type: provider.auth_type,
    auth_header_name: provider.auth_header_name ?? null,
    auth_token: null,
    enabled: provider.enabled,
  });
  providerDialogVisible.value = true;
}

async function saveProvider() {
  if (!providerForm.name.trim() || !providerForm.base_url.trim() || !providerForm.code?.trim()) {
    ElMessage.warning("请填写 Provider code、名称和服务地址。");
    return;
  }
  providerSaving.value = true;
  try {
    const saved = editingProvider.value
      ? await updateToolProvider(editingProvider.value.id, providerForm)
      : await createToolProvider(providerForm);
    providerDialogVisible.value = false;
    ElMessage.success("工具提供方已保存。");
    await loadProviders(saved.id);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "保存工具提供方失败。"));
  } finally {
    providerSaving.value = false;
  }
}

async function runProviderAction(provider: ToolProvider, action: "test" | "sync") {
  activeProviderAction.value = provider.id;
  try {
    if (action === "test") {
      const result = await testToolProvider(provider.id);
      if (!result.success) throw new Error(result.message);
      ElMessage.success(result.message);
    } else {
      const result = await syncAgentTools(provider.id);
      ElMessage.success(result.message);
    }
    await loadProviders(provider.id);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, action === "test" ? "连接测试失败。" : "同步工具失败。"));
  } finally {
    activeProviderAction.value = null;
  }
}

async function removeProvider(provider: ToolProvider) {
  await ElMessageBox.confirm(`确定删除工具提供方“${provider.name}”吗？`, "删除工具提供方", { type: "warning" });
  try {
    await deleteToolProvider(provider.id);
    ElMessage.success("工具提供方已删除。");
    await loadProviders(null);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除工具提供方失败。"));
  }
}

function openToolEditor(tool: AgentTool) {
  editingTool.value = tool;
  Object.assign(toolForm, {
    name: tool.name,
    agent_description: tool.agent_description ?? "",
    risk_level: tool.risk_level,
    requires_confirmation: tool.requires_confirmation,
  });
  toolDialogVisible.value = true;
}

async function saveTool() {
  if (!editingTool.value || !toolForm.name.trim()) return;
  toolSaving.value = true;
  try {
    await updateAgentTool(editingTool.value.id, toolForm);
    toolDialogVisible.value = false;
    ElMessage.success("工具治理配置已保存。");
    await loadTools();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "保存工具失败。"));
  } finally {
    toolSaving.value = false;
  }
}

function openToolTest(tool: AgentTool) {
  testToolTarget.value = tool;
  testArguments.value = "{}";
  testContext.value = JSON.stringify({ scope: { store_id: "" } }, null, 2);
  testDialogVisible.value = true;
}

async function runToolTest() {
  if (!testToolTarget.value) return;
  testingTool.value = true;
  try {
    const args = JSON.parse(testArguments.value) as Record<string, unknown>;
    const context = JSON.parse(testContext.value) as Record<string, unknown>;
    const result = await testAgentTool(testToolTarget.value.id, args, context);
    if (!result.success) throw new Error(result.message);
    ElMessage.success(result.message);
    testDialogVisible.value = false;
    await loadTools();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "工具测试失败。"));
  } finally {
    testingTool.value = false;
  }
}

async function togglePublish(tool: AgentTool) {
  try {
    const result = tool.publish_status === "published"
      ? await unpublishAgentTool(tool.id)
      : await publishAgentTool(tool.id);
    ElMessage.success(result.message);
    await loadTools();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "更新发布状态失败。"));
  }
}

onMounted(() => void loadProviders());
</script>

<template>
  <section class="agent-integration-page">
    <header class="agent-integration-page__header">
      <div>
        <h1>Agent 工具</h1>
        <p>工具提供方、发布状态与 Schema 审核</p>
      </div>
      <el-button
        type="primary"
        :icon="Plus"
        @click="openCreateProvider"
      >
        新增提供方
      </el-button>
    </header>

    <div class="agent-integration-page__layout">
      <aside class="provider-panel">
        <div class="panel-toolbar">
          <el-input
            v-model="providerKeyword"
            :prefix-icon="Search"
            clearable
            placeholder="搜索提供方"
            @keyup.enter="loadProviders()"
          />
          <el-button
            :icon="Refresh"
            circle
            aria-label="刷新提供方"
            @click="loadProviders()"
          />
        </div>

        <AppLoading
          v-if="loadingProviders"
          title="正在加载工具提供方"
        />
        <AppError
          v-else-if="providerError"
          title="工具提供方加载失败"
          @retry="loadProviders()"
        />
        <AppEmpty
          v-else-if="providers.length === 0"
          title="暂无工具提供方"
          description=""
        />
        <div
          v-else
          class="provider-list"
        >
          <button
            v-for="provider in providers"
            :key="provider.id"
            type="button"
            class="provider-row"
            :class="{ 'is-active': selectedProvider?.id === provider.id }"
            @click="selectProvider(provider)"
          >
            <span class="provider-row__main">
              <strong>{{ provider.name }}</strong>
              <small>{{ provider.code }}</small>
            </span>
            <el-tag
              :type="healthType(provider.health_status)"
              size="small"
            >
              {{ healthLabel(provider.health_status) }}
            </el-tag>
          </button>
        </div>
      </aside>

      <main class="tool-panel">
        <AppEmpty
          v-if="!selectedProvider"
          title="请选择工具提供方"
          description=""
        />
        <template v-else>
          <div class="tool-panel__provider">
            <div>
              <div class="tool-panel__title">
                <h2>{{ selectedProvider.name }}</h2>
                <el-tag
                  size="small"
                  effect="plain"
                >
                  {{ selectedProvider.transport_type }}
                </el-tag>
              </div>
              <p>{{ selectedProvider.base_url }}</p>
            </div>
            <div class="provider-actions">
              <el-button
                :icon="Connection"
                :loading="activeProviderAction === selectedProvider.id"
                @click="runProviderAction(selectedProvider, 'test')"
              >
                测试
              </el-button>
              <el-button
                :icon="Refresh"
                :loading="activeProviderAction === selectedProvider.id"
                @click="runProviderAction(selectedProvider, 'sync')"
              >
                同步
              </el-button>
              <el-button
                :icon="EditPen"
                circle
                aria-label="编辑提供方"
                @click="openEditProvider(selectedProvider)"
              />
              <el-button
                :icon="Delete"
                circle
                type="danger"
                plain
                aria-label="删除提供方"
                @click="removeProvider(selectedProvider)"
              />
            </div>
          </div>

          <div class="panel-toolbar tool-toolbar">
            <el-input
              v-model="toolKeyword"
              :prefix-icon="Search"
              clearable
              placeholder="搜索工具"
              @keyup.enter="loadTools"
            />
            <span>{{ publishedCount }} / {{ tools.length }} 已发布</span>
          </div>

          <AppLoading
            v-if="loadingTools"
            title="正在加载工具"
          />
          <AppError
            v-else-if="toolError"
            title="工具加载失败"
            @retry="loadTools"
          />
          <AppEmpty
            v-else-if="tools.length === 0"
            title="暂无已同步工具"
            description=""
          />
          <el-table
            v-else
            :data="tools"
            row-key="id"
            class="tool-table"
          >
            <el-table-column
              label="工具"
              min-width="230"
            >
              <template #default="{ row }">
                <div class="tool-name">
                  <strong>{{ row.name }}</strong>
                  <code>{{ row.tool_key }}</code>
                </div>
              </template>
            </el-table-column>
            <el-table-column
              label="外部名称"
              prop="external_name"
              min-width="170"
            />
            <el-table-column
              label="上下文"
              min-width="150"
            >
              <template #default="{ row }">
                {{ row.required_context.join(", ") || "无" }}
              </template>
            </el-table-column>
            <el-table-column
              label="状态"
              width="110"
            >
              <template #default="{ row }">
                <el-tag
                  :type="publishType(row.publish_status)"
                  size="small"
                >
                  {{ publishLabel(row.publish_status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              label="操作"
              width="250"
              fixed="right"
            >
              <template #default="{ row }">
                <el-button
                  link
                  type="primary"
                  @click="openToolEditor(row)"
                >
                  编辑
                </el-button>
                <el-button
                  link
                  type="primary"
                  @click="openToolTest(row)"
                >
                  测试
                </el-button>
                <el-button
                  link
                  :type="row.publish_status === 'published' ? 'warning' : 'success'"
                  :disabled="row.sync_status !== 'active'"
                  @click="togglePublish(row)"
                >
                  {{ row.publish_status === "published" ? "下线" : "发布" }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </main>
    </div>

    <AdminDialog
      v-model="providerDialogVisible"
      :title="editingProvider ? '编辑工具提供方' : '新增工具提供方'"
      width="620px"
    >
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="团队 ID">
            <el-input-number
              v-model="providerForm.team_id"
              :min="1"
            />
          </el-form-item>
          <el-form-item label="Provider code">
            <el-input
              v-model.trim="providerForm.code"
              :disabled="Boolean(editingProvider)"
            />
          </el-form-item>
        </div>
        <el-form-item label="名称">
          <el-input v-model.trim="providerForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="providerForm.description"
            type="textarea"
            :rows="2"
          />
        </el-form-item>
        <el-form-item label="接入类型">
          <el-radio-group v-model="providerForm.transport_type">
            <el-radio-button value="business_http">
              业务 HTTP
            </el-radio-button>
            <el-radio-button value="mcp_http">
              MCP HTTP
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="服务地址">
          <el-input
            v-model.trim="providerForm.base_url"
            placeholder="https://business.example.com/internal/agent-tools"
          />
        </el-form-item>
        <el-form-item label="鉴权方式">
          <el-select
            v-model="providerForm.auth_type"
            :disabled="providerForm.transport_type === 'business_http'"
          >
            <el-option
              label="Bearer Token"
              value="bearer"
            />
            <el-option
              v-if="providerForm.transport_type === 'mcp_http'"
              label="无鉴权"
              value="none"
            />
            <el-option
              v-if="providerForm.transport_type === 'mcp_http'"
              label="自定义 Header"
              value="header"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="providerForm.auth_type === 'header'"
          label="鉴权 Header"
        >
          <el-input v-model.trim="providerForm.auth_header_name" />
        </el-form-item>
        <el-form-item
          v-if="providerForm.auth_type !== 'none'"
          :label="editingProvider ? '更新 Token' : 'Service Token'"
        >
          <el-input
            v-model="providerForm.auth_token"
            type="password"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="providerForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="providerDialogVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="providerSaving"
          @click="saveProvider"
        >
          保存
        </el-button>
      </template>
    </AdminDialog>

    <AdminDialog
      v-model="toolDialogVisible"
      title="工具治理配置"
      width="600px"
    >
      <el-form label-position="top">
        <el-form-item label="名称">
          <el-input v-model.trim="toolForm.name" />
        </el-form-item>
        <el-form-item label="Agent 描述">
          <el-input
            v-model="toolForm.agent_description"
            type="textarea"
            :rows="4"
          />
        </el-form-item>
        <el-form-item label="风险级别">
          <el-select v-model="toolForm.risk_level">
            <el-option
              label="低"
              value="low"
            /><el-option
              label="中"
              value="medium"
            /><el-option
              label="高"
              value="high"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="调用前确认">
          <el-switch v-model="toolForm.requires_confirmation" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="toolDialogVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="toolSaving"
          @click="saveTool"
        >
          保存
        </el-button>
      </template>
    </AdminDialog>

    <AdminDialog
      v-model="testDialogVisible"
      :title="`测试 ${testToolTarget?.name ?? ''}`"
      width="680px"
    >
      <el-form label-position="top">
        <el-form-item label="Arguments JSON">
          <el-input
            v-model="testArguments"
            type="textarea"
            :rows="8"
          />
        </el-form-item>
        <el-form-item label="Trusted Context JSON">
          <el-input
            v-model="testContext"
            type="textarea"
            :rows="8"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="testDialogVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :icon="Upload"
          :loading="testingTool"
          @click="runToolTest"
        >
          执行
        </el-button>
      </template>
    </AdminDialog>
  </section>
</template>

<style scoped>
.agent-integration-page { display: grid; gap: 16px; min-width: 0; }
.agent-integration-page__header, .tool-panel__provider, .panel-toolbar, .provider-row { display: flex; align-items: center; }
.agent-integration-page__header, .tool-panel__provider { justify-content: space-between; gap: 16px; }
.agent-integration-page__header h1, .tool-panel__title h2 { margin: 0; }
.agent-integration-page__header p, .tool-panel__provider p { margin: 4px 0 0; color: var(--el-text-color-secondary); }
.agent-integration-page__layout { display: grid; grid-template-columns: minmax(250px, 310px) minmax(0, 1fr); min-height: 620px; border: 1px solid var(--el-border-color-light); border-radius: 8px; overflow: hidden; background: var(--el-bg-color); }
.provider-panel { border-right: 1px solid var(--el-border-color-light); padding: 14px; }
.panel-toolbar { gap: 8px; }
.provider-list { display: grid; gap: 6px; margin-top: 12px; }
.provider-row { width: 100%; justify-content: space-between; gap: 12px; padding: 10px; border: 1px solid transparent; border-radius: 6px; background: transparent; color: inherit; text-align: left; cursor: pointer; }
.provider-row:hover, .provider-row.is-active { border-color: var(--el-color-primary-light-5); background: var(--el-color-primary-light-9); }
.provider-row__main, .tool-name { display: grid; gap: 3px; min-width: 0; }
.provider-row small, .tool-name code { overflow: hidden; color: var(--el-text-color-secondary); text-overflow: ellipsis; white-space: nowrap; }
.tool-panel { min-width: 0; padding: 18px; }
.tool-panel__title, .provider-actions { display: flex; align-items: center; gap: 8px; }
.tool-panel__provider p { overflow-wrap: anywhere; }
.tool-toolbar { justify-content: space-between; margin: 20px 0 12px; }
.tool-toolbar .el-input { max-width: 320px; }
.tool-toolbar span { color: var(--el-text-color-secondary); }
.tool-table { width: 100%; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 900px) {
  .agent-integration-page__layout { grid-template-columns: 1fr; }
  .provider-panel { border-right: 0; border-bottom: 1px solid var(--el-border-color-light); }
  .tool-panel__provider, .agent-integration-page__header { align-items: flex-start; flex-direction: column; }
  .provider-actions { flex-wrap: wrap; }
  .form-grid { grid-template-columns: 1fr; }
}
</style>
