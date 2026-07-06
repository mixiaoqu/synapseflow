<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Back,
  Check,
  Delete,
  EditPen,
  Link,
  Plus,
  Promotion,
  RefreshRight,
  VideoPlay,
} from "@element-plus/icons-vue";

import MappingEditor from "@/modules/business-tools/components/MappingEditor.vue";
import {
  createBusinessTool,
  createBusinessToolImplementation,
  deleteBusinessToolImplementation,
  getBusinessTool,
  listBusinessApis,
  listBusinessToolImplementations,
  publishBusinessTool,
  testBusinessTool,
  unpublishBusinessTool,
  updateBusinessTool,
  updateBusinessToolImplementation,
} from "@/shared/api/business-tools";
import { listTeamOptions } from "@/shared/api/teams";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import type {
  BusinessApi,
  BusinessTool,
  BusinessToolImplementation,
  BusinessToolImplementationPayload,
  BusinessToolImplementationType,
  BusinessToolParamSpec,
  BusinessToolParamType,
  BusinessToolPayload,
  BusinessToolRiskLevel,
  BusinessToolStatus,
  BusinessToolTestResponse,
} from "@/shared/types/business-tool";
import type { TeamOption } from "@/shared/types/team";
import { getErrorMessage } from "@/shared/utils/error";
import { useTeamScopeStore } from "@/stores/team-scope";

interface MappingRow {
  target: string;
  source: string;
}

interface MappingOption {
  label: string;
  value: string;
  description?: string;
}

interface ContextValueRow {
  key: string;
  value: string;
}

const route = useRoute();
const router = useRouter();
const teamScopeStore = useTeamScopeStore();
const toolId = computed(() => Number(route.params.toolId));
const isCreate = computed(() => route.name === "business-tool-create");

const loading = ref(!isCreate.value);
const saving = ref(false);
const publishing = ref(false);
const testing = ref(false);
const implementationSaving = ref(false);
const implementationDeletingId = ref<number | null>(null);
const implementationDialogVisible = ref(false);
const testDrawerVisible = ref(false);

const tool = ref<BusinessTool | null>(null);
const teams = ref<TeamOption[]>([]);
const apis = ref<BusinessApi[]>([]);
const implementations = ref<BusinessToolImplementation[]>([]);
const testResult = ref<BusinessToolTestResponse | null>(null);
const testContextRows = ref<ContextValueRow[]>([]);
const testParams = reactive<Record<string, string | number | boolean | null>>({});
const testImplementationId = ref<number | null>(null);

const form = reactive({
  team_id: null as number | null,
  tool_key: "",
  name: "",
  description: "",
  typical_queries: [] as string[],
  params_schema: [] as BusinessToolParamSpec[],
  risk_level: "low" as BusinessToolRiskLevel,
  requires_confirmation: false,
  enabled: true,
});

const implementationForm = reactive({
  id: null as number | null,
  business_api_id: null as number | null,
  implementation_type: "http" as BusinessToolImplementationType,
  context_mapping: [] as MappingRow[],
  request_mapping: [] as MappingRow[],
  response_mapping: [] as MappingRow[],
  priority: 100,
  enabled: true,
});

const status = computed<BusinessToolStatus>(() => tool.value?.status ?? "draft");
const implementationDialogTitle = computed(() =>
  implementationForm.id ? "编辑工具实现" : "新增工具实现",
);
const selectedImplementationApi = computed(
  () => apis.value.find((item) => item.id === implementationForm.business_api_id) ?? null,
);
const canPublish = computed(
  () => Boolean(tool.value && form.enabled && implementations.value.some((item) => item.enabled)),
);
const definedParams = computed(() =>
  form.params_schema.filter((item) => item.key.trim() && item.label.trim()),
);
const selectedApiRequestFieldOptions = computed<MappingOption[]>(() => {
  const api = selectedImplementationApi.value;
  if (!api) return [];
  return api.request_schema.fields.map((field) => ({
    label: `${field.label}${field.required ? " *" : ""}`,
    value: field.name,
    description: `${field.in} · ${field.name}`,
  }));
});
const contextSourceOptions = computed<MappingOption[]>(() => [
  { label: "门店ID", value: "scope.store_id", description: "scope.store_id" },
  { label: "租户ID", value: "scope.tenant_id", description: "scope.tenant_id" },
  { label: "项目ID", value: "scope.project_id", description: "scope.project_id" },
  { label: "应用ID", value: "scope.project_app_id", description: "scope.project_app_id" },
  { label: "登录用户ID", value: "actor.user_id", description: "actor.user_id" },
  { label: "外部用户ID", value: "actor.external_user_id", description: "actor.external_user_id" },
  { label: "外部用户名", value: "actor.external_user_name", description: "actor.external_user_name" },
]);
const requestSourceOptions = computed<MappingOption[]>(() =>
  definedParams.value.map((param) => ({
    label: `${param.label}${param.required ? " *" : ""}`,
    value: `params.${param.key}`,
    description: param.key,
  })),
);
const responseTargetOptions = computed<MappingOption[]>(() => {
  const api = selectedImplementationApi.value;
  if (!api) return [];
  const unique = new Map<string, MappingOption>();
  for (const field of api.response_schema.fields) {
    const normalized = toSuggestedResponseTarget(field.path);
    if (!normalized || unique.has(normalized)) continue;
    unique.set(normalized, {
      label: field.label,
      value: normalized,
      description: field.path,
    });
  }
  return [...unique.values()];
});
const responseSourceOptions = computed<MappingOption[]>(() => {
  const api = selectedImplementationApi.value;
  if (!api) return [];
  const options: MappingOption[] = [
    { label: "完整响应", value: "response", description: "完整返回对象" },
  ];
  for (const field of api.response_schema.fields) {
    options.push({
      label: field.label,
      value: `response.${normalizeResponseLookupPath(field.path)}`,
      description: field.path.includes("[]")
        ? `${field.path} · 数组字段默认指向首项示例路径`
        : field.path,
    });
  }
  return options;
});
const statusHelp = computed(() => {
  if (status.value === "error") {
    return tool.value?.last_test_error || "请修正工具实现或映射配置后重新测试。";
  }
  return statusMeta[status.value].help;
});

const statusMeta = {
  draft: { label: "草稿", type: "info" as const, help: "工具基础定义已保存，还需要为它绑定并验证至少一个实现。" },
  verified: { label: "已验证", type: "warning" as const, help: "至少一个工具实现测试通过，可以发布给应用使用。" },
  published: { label: "已发布", type: "success" as const, help: "已授权的应用端和 Agent 可以发现并调用这个工具。" },
  error: { label: "验证失败", type: "danger" as const, help: "请修正工具实现或映射配置后重新测试。" },
};

function emptyParam(): BusinessToolParamSpec {
  return { key: "", label: "", type: "text", required: false, description: "" };
}

function normalizeResponseLookupPath(path: string) {
  return path
    .trim()
    .replace(/\[\]/g, ".0")
    .replace(/\.+/g, ".")
    .replace(/^\./, "")
    .replace(/\.$/, "");
}

function toSuggestedResponseTarget(path: string) {
  const normalized = path.trim().replace(/\[\]/g, "");
  const parts = normalized.split(".").filter(Boolean);
  return parts[parts.length - 1] ?? "";
}

function objectToRows(value: Record<string, unknown>): MappingRow[] {
  return Object.entries(value || {}).map(([target, source]) => ({
    target,
    source: String(source ?? ""),
  }));
}

function rowsToObject(rows: MappingRow[]): Record<string, unknown> {
  return Object.fromEntries(
    rows
      .map((row) => [row.target.trim(), row.source.trim()] as const)
      .filter(([target, source]) => target && source),
  );
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

function getStatusMeta(currentStatus: BusinessToolStatus) {
  return statusMeta[currentStatus];
}

function getImplementationStatusType(currentStatus: BusinessToolStatus) {
  return statusMeta[currentStatus].type;
}

function resetForm() {
  Object.assign(form, {
    team_id: teamScopeStore.selectedTeamId ?? teams.value[0]?.id ?? null,
    tool_key: "",
    name: "",
    description: "",
    typical_queries: [],
    params_schema: [emptyParam()],
    risk_level: "low",
    requires_confirmation: false,
    enabled: true,
  });
}

function resetImplementationForm() {
  Object.assign(implementationForm, {
    id: null,
    business_api_id: null,
    implementation_type: "http",
    context_mapping: [],
    request_mapping: [],
    response_mapping: [],
    priority: 100,
    enabled: true,
  });
}

function applyTool(value: BusinessTool) {
  tool.value = value;
  Object.assign(form, {
    team_id: value.team_id,
    tool_key: value.tool_key,
    name: value.name,
    description: value.description,
    typical_queries: [...value.typical_queries],
    params_schema:
      value.params_schema.length > 0 ? value.params_schema.map((item) => ({ ...item })) : [emptyParam()],
    risk_level: value.risk_level,
    requires_confirmation: value.requires_confirmation,
    enabled: value.enabled,
  });
}

function applyImplementation(value: BusinessToolImplementation) {
  Object.assign(implementationForm, {
    id: value.id,
    business_api_id: value.business_api_id,
    implementation_type: value.implementation_type,
    context_mapping: objectToRows(value.context_binding),
    request_mapping: objectToRows(value.request_mapping),
    response_mapping: objectToRows(value.response_mapping),
    priority: value.priority,
    enabled: value.enabled,
  });
}

async function loadApis(teamId = form.team_id) {
  if (!teamId) {
    apis.value = [];
    return;
  }
  const response = await listBusinessApis({
    team_id: teamId,
    enabled_status: "all",
    page: 1,
    page_size: 100,
  });
  apis.value = response.items;
}

async function loadImplementations(nextToolId: number) {
  const response = await listBusinessToolImplementations(nextToolId);
  implementations.value = response.items;
  if (!testImplementationId.value || !implementations.value.some((item) => item.id === testImplementationId.value)) {
    testImplementationId.value = implementations.value[0]?.id ?? null;
  }
}

async function refreshToolData(nextToolId: number) {
  const [toolResponse] = await Promise.all([
    getBusinessTool(nextToolId),
    loadImplementations(nextToolId),
  ]);
  applyTool(toolResponse);
}

async function loadPage() {
  loading.value = true;
  try {
    teams.value = await listTeamOptions({
      limit: 100,
      include_team_id: teamScopeStore.selectedTeamId ?? undefined,
    });
    if (isCreate.value) {
      resetForm();
      await loadApis();
      implementations.value = [];
      return;
    }
    const value = await getBusinessTool(toolId.value);
    applyTool(value);
    await Promise.all([loadApis(value.team_id), loadImplementations(value.id)]);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "业务工具配置加载失败。"));
    void router.push("/business-tools");
  } finally {
    loading.value = false;
  }
}

function buildToolPayload(): BusinessToolPayload {
  if (!form.team_id) throw new Error("请选择所属团队。");
  if (!form.name.trim() || !form.tool_key.trim() || !form.description.trim()) {
    throw new Error("请填写工具名称、标识和能力说明。");
  }
  const params = form.params_schema
    .filter((item) => item.key.trim() || item.label.trim())
    .map((item) => ({
      ...item,
      key: item.key.trim(),
      label: item.label.trim(),
      description: item.description.trim(),
    }));
  if (params.some((item) => !item.key || !item.label)) {
    throw new Error("每个输入参数都需要填写参数名和显示名称。");
  }
  if (new Set(params.map((item) => item.key)).size !== params.length) {
    throw new Error("输入参数名不能重复。");
  }
  return {
    team_id: form.team_id,
    tool_key: form.tool_key.trim().toLowerCase(),
    name: form.name.trim(),
    description: form.description.trim(),
    typical_queries: form.typical_queries.map((item) => item.trim()).filter(Boolean),
    params_schema: params,
    risk_level: form.risk_level,
    requires_confirmation: form.requires_confirmation,
    enabled: form.enabled,
  };
}

async function saveTool(options: { notify?: boolean } = {}) {
  let payload: BusinessToolPayload;
  try {
    payload = buildToolPayload();
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : "请检查工具配置。");
    return null;
  }
  saving.value = true;
  try {
    const saved = tool.value
      ? await updateBusinessTool(tool.value.id, payload)
      : await createBusinessTool(payload);
    applyTool(saved);
    if (isCreate.value) {
      await router.replace(`/business-tools/${saved.id}`);
    }
    if (options.notify !== false) {
      ElMessage.success("工具基本信息已保存。");
    }
    return saved;
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "保存业务工具失败。"));
    return null;
  } finally {
    saving.value = false;
  }
}

function openCreateImplementation() {
  if (!tool.value) {
    ElMessage.warning("请先保存工具基本信息，再新增工具实现。");
    return;
  }
  resetImplementationForm();
  implementationDialogVisible.value = true;
}

function openEditImplementation(implementation: BusinessToolImplementation) {
  applyImplementation(implementation);
  implementationDialogVisible.value = true;
}

function buildImplementationPayload(): BusinessToolImplementationPayload {
  if (!implementationForm.business_api_id) {
    throw new Error("请选择要绑定的业务接口。");
  }
  return {
    business_api_id: implementationForm.business_api_id,
    implementation_type: implementationForm.implementation_type,
    context_binding: rowsToObject(implementationForm.context_mapping),
    request_mapping: rowsToObject(implementationForm.request_mapping),
    response_mapping: rowsToObject(implementationForm.response_mapping),
    priority: implementationForm.priority,
    enabled: implementationForm.enabled,
  };
}

async function submitImplementation() {
  if (!tool.value) return;
  let payload: BusinessToolImplementationPayload;
  try {
    payload = buildImplementationPayload();
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : "请检查工具实现配置。");
    return;
  }
  implementationSaving.value = true;
  try {
    if (implementationForm.id) {
      await updateBusinessToolImplementation(implementationForm.id, payload);
      ElMessage.success("工具实现已更新。");
    } else {
      await createBusinessToolImplementation(tool.value.id, payload);
      ElMessage.success("工具实现已创建。");
    }
    implementationDialogVisible.value = false;
    await refreshToolData(tool.value.id);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "保存工具实现失败。"));
  } finally {
    implementationSaving.value = false;
  }
}

async function removeImplementation(implementation: BusinessToolImplementation) {
  try {
    await ElMessageBox.confirm(
      `确定删除实现“${implementation.api_name}”吗？`,
      "删除工具实现",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  implementationDeletingId.value = implementation.id;
  try {
    await deleteBusinessToolImplementation(implementation.id);
    ElMessage.success("工具实现已删除。");
    if (tool.value) {
      await refreshToolData(tool.value.id);
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除工具实现失败。"));
  } finally {
    implementationDeletingId.value = null;
  }
}

function prepareTestInputs() {
  if (!tool.value) {
    ElMessage.warning("请先保存工具。");
    return;
  }
  if (implementations.value.length === 0) {
    ElMessage.warning("请先新增至少一个工具实现。");
    return;
  }
  for (const key of Object.keys(testParams)) delete testParams[key];
  definedParams.value.forEach((item) => {
    testParams[item.key] = item.type === "boolean" ? false : "";
  });
  testContextRows.value = [];
  testResult.value = null;
  testImplementationId.value = implementations.value[0]?.id ?? null;
  testDrawerVisible.value = true;
}

function normalizeTestValue(value: unknown, type: BusinessToolParamType) {
  if (type === "number") return value === "" ? null : Number(value);
  if (type === "boolean") return Boolean(value);
  if (type === "array" || type === "object") {
    if (!String(value ?? "").trim()) return type === "array" ? [] : {};
    try {
      return JSON.parse(String(value));
    } catch {
      throw new Error(`${type === "array" ? "数组" : "对象"}参数必须是有效 JSON。`);
    }
  }
  return String(value ?? "").trim();
}

function testValuePlaceholder(type: BusinessToolParamType) {
  return type === "array" ? '["value"]' : '{"key": "value"}';
}

async function runTest() {
  const saved = await saveTool({ notify: false });
  if (!saved || !testImplementationId.value) return;
  const params: Record<string, unknown> = {};
  try {
    for (const item of definedParams.value) {
      params[item.key] = normalizeTestValue(testParams[item.key], item.type);
    }
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : "请检查测试参数。");
    return;
  }
  testing.value = true;
  try {
    const result = await testBusinessTool(saved.id, {
      implementation_id: testImplementationId.value,
      params,
      scope: Object.fromEntries(
        testContextRows.value
          .map((row) => [row.key.trim(), row.value] as const)
          .filter(([key]) => key),
      ),
    });
    testResult.value = result;
    await refreshToolData(saved.id);
    (result.success ? ElMessage.success : ElMessage.error)(result.message);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "工具测试失败。"));
  } finally {
    testing.value = false;
  }
}

async function publish() {
  if (!tool.value) return;
  publishing.value = true;
  try {
    await publishBusinessTool(tool.value.id);
    await refreshToolData(tool.value.id);
    ElMessage.success("工具已发布。");
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "发布业务工具失败。"));
  } finally {
    publishing.value = false;
  }
}

async function unpublish() {
  if (!tool.value) return;
  try {
    await ElMessageBox.confirm(
      "取消发布后，所有应用端将立即停止发现此工具。",
      "取消发布",
      { type: "warning", confirmButtonText: "取消发布", cancelButtonText: "返回" },
    );
  } catch {
    return;
  }
  publishing.value = true;
  try {
    await unpublishBusinessTool(tool.value.id);
    await refreshToolData(tool.value.id);
    ElMessage.success("工具已取消发布。");
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "取消发布失败。"));
  } finally {
    publishing.value = false;
  }
}

watch(
  () => form.team_id,
  async (teamId, previous) => {
    if (!teamId || teamId === previous || loading.value || !isCreate.value) return;
    await loadApis(teamId);
  },
);

watch(
  () => form.risk_level,
  (riskLevel) => {
    if (riskLevel === "high") form.requires_confirmation = true;
  },
);

onMounted(loadPage);
</script>

<template>
  <AppLoading v-if="loading" title="工具配置加载中" description="正在准备业务工具配置。" :blocks="5" />

  <section v-else class="tool-detail">
    <header class="tool-detail__header">
      <div class="tool-detail__title-group">
        <el-button text class="tool-detail__back" @click="router.push('/business-tools')">
          <el-icon><Back /></el-icon>返回工具目录
        </el-button>
        <div class="tool-detail__title-row">
          <div>
            <h2>{{ isCreate ? "新建业务工具" : form.name }}</h2>
            <p>{{ isCreate ? "定义稳定的业务能力，再为它绑定一个或多个外部接口实现。" : statusHelp }}</p>
          </div>
          <el-tag :type="statusMeta[status].type" effect="plain" size="large">{{ statusMeta[status].label }}</el-tag>
        </div>
      </div>
      <div class="tool-detail__actions">
        <el-button :loading="saving" @click="saveTool()"><el-icon><Check /></el-icon>保存</el-button>
        <el-button :disabled="!tool || implementations.length === 0" @click="prepareTestInputs">
          <el-icon><VideoPlay /></el-icon>测试工具
        </el-button>
        <el-button v-if="status === 'published'" type="warning" plain :loading="publishing" @click="unpublish">
          <el-icon><RefreshRight /></el-icon>取消发布
        </el-button>
        <el-button v-else type="primary" :disabled="!canPublish" :loading="publishing" @click="publish">
          <el-icon><Promotion /></el-icon>发布工具
        </el-button>
      </div>
    </header>

    <div class="tool-detail__layout">
      <main class="tool-detail__form-stack">
        <section class="tool-detail__section">
          <header>
            <span>1</span>
            <div>
              <h3>基本信息</h3>
              <p>让规划模型准确理解这个工具能做什么、什么时候该调用。</p>
            </div>
          </header>
          <div class="tool-detail__grid">
            <el-form-item label="所属团队" required>
              <el-select v-model="form.team_id" filterable class="w-full" :disabled="!isCreate">
                <el-option v-for="team in teams" :key="team.id" :label="team.name" :value="team.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="工具标识" required>
              <el-input
                v-model="form.tool_key"
                maxlength="120"
                placeholder="例如：product.search"
                @blur="form.tool_key = form.tool_key.trim().toLowerCase()"
              />
            </el-form-item>
            <el-form-item label="工具名称" required>
              <el-input v-model="form.name" maxlength="100" placeholder="例如：查询门店商品" />
            </el-form-item>
            <el-form-item label="风险等级">
              <el-select v-model="form.risk_level" class="w-full">
                <el-option label="低风险 · 只读查询" value="low" />
                <el-option label="中风险 · 有业务影响" value="medium" />
                <el-option label="高风险 · 关键写操作" value="high" />
              </el-select>
            </el-form-item>
          </div>
          <el-form-item label="能力说明" required>
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="4"
              maxlength="1000"
              show-word-limit
              placeholder="写清楚工具能查询或操作什么数据、适用范围和结果内容。"
            />
          </el-form-item>
          <el-form-item label="典型问法">
            <el-select
              v-model="form.typical_queries"
              multiple
              filterable
              allow-create
              default-first-option
              class="w-full"
              placeholder="输入一句用户可能会说的话，按回车添加"
            />
            <p class="tool-detail__help">示例问法会帮助模型在多个工具之间做出更稳定的选择。</p>
          </el-form-item>
          <div class="tool-detail__grid">
            <el-form-item label="执行确认">
              <el-switch v-model="form.requires_confirmation" active-text="执行前必须由用户确认" />
            </el-form-item>
            <el-form-item label="工具状态">
              <el-switch v-model="form.enabled" active-text="允许测试、发布和授权" />
            </el-form-item>
          </div>
        </section>

        <section class="tool-detail__section">
          <header class="tool-detail__section-header">
            <span>2</span>
            <div>
              <h3>输入参数</h3>
              <p>模型只会生成这里声明的参数；必填参数缺失时会先向用户追问。</p>
            </div>
            <el-button plain size="small" @click="form.params_schema.push(emptyParam())">
              <el-icon><Plus /></el-icon>添加参数
            </el-button>
          </header>
          <div v-if="form.params_schema.length" class="tool-detail__params">
            <div v-for="(param, index) in form.params_schema" :key="index" class="tool-detail__param-row">
              <el-input v-model="param.key" placeholder="参数名，如 keyword" />
              <el-input v-model="param.label" placeholder="显示名称" />
              <el-select v-model="param.type">
                <el-option label="文本" value="text" />
                <el-option label="数字" value="number" />
                <el-option label="布尔" value="boolean" />
                <el-option label="数组" value="array" />
                <el-option label="对象" value="object" />
              </el-select>
              <el-checkbox v-model="param.required">必填</el-checkbox>
              <el-input v-model="param.description" placeholder="说明参数含义和取值" />
              <el-button text type="danger" @click="form.params_schema.splice(index, 1)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
          <button v-else type="button" class="tool-detail__empty-row" @click="form.params_schema.push(emptyParam())">
            当前工具没有输入参数，点击添加。
          </button>
        </section>

        <section class="tool-detail__section">
          <header class="tool-detail__section-header">
            <span>3</span>
            <div>
              <h3>工具实现</h3>
              <p>把工具绑定到具体业务接口，并配置上下文、请求和响应映射。</p>
            </div>
            <el-button plain size="small" @click="openCreateImplementation">
              <el-icon><Plus /></el-icon>新增实现
            </el-button>
          </header>

          <div v-if="implementations.length" class="tool-detail__implementation-list">
            <article
              v-for="implementation in implementations"
              :key="implementation.id"
              class="tool-detail__implementation-card"
            >
              <div class="tool-detail__implementation-main">
                <div class="tool-detail__implementation-title">
                  <strong>{{ implementation.api_name }}</strong>
                  <el-tag size="small" effect="plain">{{ implementation.method }}</el-tag>
                  <el-tag size="small" effect="plain" :type="getImplementationStatusType(implementation.status)">
                    {{ getStatusMeta(implementation.status).label }}
                  </el-tag>
                </div>
                <p>{{ implementation.connection_name }} · {{ implementation.path }}</p>
                <div class="tool-detail__implementation-meta">
                  <span>接口标识：{{ implementation.api_key }}</span>
                  <span>优先级：{{ implementation.priority }}</span>
                  <span>{{ implementation.enabled ? "已启用" : "已停用" }}</span>
                  <span>最近验证：{{ formatDate(implementation.last_tested_at) }}</span>
                </div>
                <small v-if="implementation.last_test_error" class="tool-detail__implementation-error">
                  {{ implementation.last_test_error }}
                </small>
              </div>
              <div class="tool-detail__implementation-actions">
                <el-button link type="primary" @click="openEditImplementation(implementation)">
                  <el-icon><EditPen /></el-icon>编辑
                </el-button>
                <el-button
                  link
                  type="danger"
                  :loading="implementationDeletingId === implementation.id"
                  @click="removeImplementation(implementation)"
                >
                  <el-icon><Delete /></el-icon>删除
                </el-button>
              </div>
            </article>
          </div>

          <div v-else class="tool-detail__empty-block">
            <strong>还没有工具实现</strong>
            <span>先到“业务接口”中准备接口定义，再回来给这个工具绑定实现。</span>
            <div class="tool-detail__empty-actions">
              <router-link to="/business-tools/apis" class="tool-detail__inline-link">去维护业务接口</router-link>
              <el-button size="small" type="primary" plain @click="openCreateImplementation">新增实现</el-button>
            </div>
          </div>
        </section>
      </main>

      <aside class="tool-detail__aside">
        <div class="tool-detail__status-card">
          <h3>上线检查</h3>
          <ul>
            <li :class="{ 'is-done': Boolean(tool || isCreate) }"><el-icon><Check /></el-icon>已定义工具能力</li>
            <li :class="{ 'is-done': implementations.length > 0 }"><el-icon><Check /></el-icon>已绑定至少一个实现</li>
            <li :class="{ 'is-done': ['verified', 'published'].includes(status) }"><el-icon><Check /></el-icon>工具测试通过</li>
            <li :class="{ 'is-done': status === 'published' }"><el-icon><Check /></el-icon>工具已发布</li>
          </ul>
          <p v-if="tool?.last_test_error" class="tool-detail__error">{{ tool.last_test_error }}</p>
        </div>

        <div class="tool-detail__aside-note">
          <strong>配置建议</strong>
          <p>一个工具可以绑定多个接口实现。优先级越小，运行时越优先被选择为主实现。</p>
        </div>

        <div class="tool-detail__aside-note">
          <strong>接口入口</strong>
          <p>工具只描述业务能力，真正的 HTTP 方法、路径和结构映射都放在工具实现层。</p>
          <router-link to="/business-tools/apis" class="tool-detail__inline-link">
            <el-icon><Link /></el-icon>查看业务接口
          </router-link>
        </div>
      </aside>
    </div>

    <el-drawer v-model="implementationDialogVisible" :title="implementationDialogTitle" size="min(760px, 100%)" destroy-on-close>
      <div class="tool-detail__dialog-stack">
        <section class="tool-detail__section">
          <header>
            <span>1</span>
            <div>
              <h3>绑定接口</h3>
              <p>选择已经定义好的业务接口，作为当前工具的具体执行方式。</p>
            </div>
          </header>
          <div class="tool-detail__grid">
            <el-form-item label="业务接口" required>
              <el-select
                v-model="implementationForm.business_api_id"
                filterable
                class="w-full"
                placeholder="选择接口"
              >
                <el-option
                  v-for="api in apis"
                  :key="api.id"
                  :label="`${api.name} · ${api.method} ${api.path}`"
                  :value="api.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="优先级">
              <el-input-number v-model="implementationForm.priority" :min="0" :max="10000" class="w-full" />
            </el-form-item>
          </div>
          <div v-if="selectedImplementationApi" class="tool-detail__api-hint">
            <strong>{{ selectedImplementationApi.connection_name }}</strong>
            <span>{{ selectedImplementationApi.method }} · {{ selectedImplementationApi.path }}</span>
          </div>
          <el-form-item label="实现状态">
            <el-switch v-model="implementationForm.enabled" active-text="允许此实现参与测试和发布" />
          </el-form-item>
        </section>

        <section class="tool-detail__section">
          <header>
            <span>2</span>
            <div>
              <h3>数据映射</h3>
              <p>只有当平台默认结构与接口字段不一致时，才需要配置这些映射。</p>
            </div>
          </header>
          <div class="tool-detail__mapping-stack">
            <MappingEditor
              v-model="implementationForm.context_mapping"
              title="上下文映射"
              description="把应用上下文中的字段带入请求，例如 store_id ← scope.store_id。"
              :target-options="selectedApiRequestFieldOptions"
              :source-options="contextSourceOptions"
              target-placeholder="选择接口字段"
              source-placeholder="选择上下文字段"
            />
            <MappingEditor
              v-model="implementationForm.request_mapping"
              title="请求映射"
              description="把模型参数映射为外部接口字段，例如 q ← params.keyword。"
              :target-options="selectedApiRequestFieldOptions"
              :source-options="requestSourceOptions"
              target-placeholder="选择接口字段"
              source-placeholder="选择工具参数"
            />
            <MappingEditor
              v-model="implementationForm.response_mapping"
              title="响应映射"
              description="提取接口响应中需要交给助手的字段，例如 items ← response.data.items。"
              :target-options="responseTargetOptions"
              :source-options="responseSourceOptions"
              target-placeholder="选择返回字段名"
              source-placeholder="选择接口响应字段"
            />
          </div>
        </section>
      </div>

      <template #footer>
        <div class="tool-detail__drawer-footer">
          <el-button @click="implementationDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="implementationSaving" @click="submitImplementation">
            保存实现
          </el-button>
        </div>
      </template>
    </el-drawer>

    <el-drawer v-model="testDrawerVisible" title="测试业务工具" size="min(680px, 100%)">
      <div class="tool-test">
        <div class="tool-test__notice">
          <strong>测试会发起真实请求</strong>
          <span>请选择要测试的工具实现，并使用安全的测试参数。</span>
        </div>

        <section>
          <h3>选择实现</h3>
          <el-select v-model="testImplementationId" class="w-full" placeholder="选择要测试的实现">
            <el-option
              v-for="implementation in implementations"
              :key="implementation.id"
              :label="`${implementation.api_name} · ${implementation.method} ${implementation.path}`"
              :value="implementation.id"
            />
          </el-select>
        </section>

        <section>
          <h3>工具参数</h3>
          <el-form label-position="top">
            <el-form-item
              v-for="param in definedParams"
              :key="param.key"
              :label="`${param.label}${param.required ? ' *' : ''}`"
            >
              <el-switch v-if="param.type === 'boolean'" v-model="testParams[param.key]" />
              <el-input-number
                v-else-if="param.type === 'number'"
                v-model="testParams[param.key]"
                class="w-full"
                controls-position="right"
              />
              <el-input
                v-else-if="param.type === 'array' || param.type === 'object'"
                v-model="testParams[param.key]"
                type="textarea"
                :rows="3"
                :placeholder="testValuePlaceholder(param.type)"
              />
              <el-input
                v-else
                v-model="testParams[param.key]"
                :placeholder="param.description || '输入测试值'"
              />
            </el-form-item>
            <p v-if="definedParams.length === 0" class="tool-test__empty">此工具没有声明输入参数。</p>
          </el-form>
        </section>

        <section>
          <div class="tool-test__section-title">
            <h3>上下文参数</h3>
            <el-button size="small" plain @click="testContextRows.push({ key: '', value: '' })">
              <el-icon><Plus /></el-icon>添加
            </el-button>
          </div>
          <div v-for="(row, index) in testContextRows" :key="index" class="tool-test__context-row">
            <el-input v-model="row.key" placeholder="字段，如 store_id" />
            <el-input v-model="row.value" placeholder="测试值" />
            <el-button text type="danger" @click="testContextRows.splice(index, 1)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <p v-if="testContextRows.length === 0" class="tool-test__empty">如工具依赖门店、租户等上下文，可在这里补充。</p>
        </section>

        <section v-if="testResult" class="tool-test__result" :class="testResult.success ? 'is-success' : 'is-error'">
          <div>
            <strong>{{ testResult.success ? "测试成功" : "测试失败" }}</strong>
            <span>
              {{ testResult.http_status ? `HTTP ${testResult.http_status}` : "未收到 HTTP 响应" }}
              ·
              {{ testResult.duration_ms ?? 0 }} ms
            </span>
          </div>
          <p>{{ testResult.message }}</p>
          <pre>{{ JSON.stringify(testResult.data, null, 2) }}</pre>
        </section>
      </div>

      <template #footer>
        <el-button @click="testDrawerVisible = false">关闭</el-button>
        <el-button type="primary" :loading="testing || saving" @click="runTest">
          <el-icon><VideoPlay /></el-icon>保存并运行测试
        </el-button>
      </template>
    </el-drawer>
  </section>
</template>

<style scoped>
.tool-detail { display: grid; gap: 18px; max-width: 1380px; margin: 0 auto; }
.tool-detail__header { position: sticky; z-index: 6; top: -24px; display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; border: 1px solid var(--admin-border); border-radius: var(--admin-radius-lg); background: rgba(255,255,255,.96); box-shadow: var(--admin-shadow-panel); padding: 16px 18px; backdrop-filter: blur(10px); }
.tool-detail__title-group { display: grid; min-width: 0; gap: 8px; }
.tool-detail__back { width: fit-content; margin-left: -10px; color: var(--admin-text-muted); }
.tool-detail__title-row { display: flex; align-items: center; gap: 12px; }
.tool-detail__title-row h2 { margin: 0; color: var(--admin-text); font-size: 22px; }
.tool-detail__title-row p { margin: 5px 0 0; color: var(--admin-text-muted); font-size: 13px; line-height: 1.5; }
.tool-detail__actions { display: flex; flex: 0 0 auto; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.tool-detail__layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; align-items: start; gap: 18px; }
.tool-detail__form-stack { display: grid; gap: 16px; }
.tool-detail__section { border: 1px solid var(--admin-border); border-radius: var(--admin-radius-lg); background: var(--admin-surface); box-shadow: var(--admin-shadow-panel); padding: 20px; }
.tool-detail__section > header { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 20px; }
.tool-detail__section > header > span { display: inline-flex; width: 26px; height: 26px; flex: 0 0 auto; align-items: center; justify-content: center; border-radius: 50%; background: var(--admin-primary-soft); color: var(--admin-primary); font-size: 12px; font-weight: 700; }
.tool-detail__section h3 { margin: 2px 0 0; color: var(--admin-text); font-size: 15px; }
.tool-detail__section header p { margin: 4px 0 0; color: var(--admin-text-muted); font-size: 12px; line-height: 1.5; }
.tool-detail__section-header .el-button { margin-left: auto; }
.tool-detail__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 18px; }
.tool-detail__help { margin: 6px 0 0; color: var(--admin-text-muted); font-size: 12px; }
.tool-detail__inline-link { display: inline-flex; align-items: center; gap: 6px; margin-top: 7px; color: var(--admin-primary); font-size: 12px; text-decoration: none; }
.tool-detail__inline-link:hover { color: var(--admin-primary-strong); }
.tool-detail__params { display: grid; gap: 10px; }
.tool-detail__param-row { display: grid; grid-template-columns: minmax(120px,.8fr) minmax(140px,1fr) 110px 72px minmax(180px,1.5fr) 32px; align-items: center; gap: 8px; }
.tool-detail__empty-row { width: 100%; border: 1px dashed var(--admin-border); border-radius: var(--admin-radius-md); background: var(--admin-surface-muted); padding: 18px; color: var(--admin-text-muted); cursor: pointer; font: inherit; font-size: 13px; }
.tool-detail__empty-row:hover { border-color: var(--admin-primary-border); color: var(--admin-primary); }
.tool-detail__implementation-list { display: grid; gap: 12px; }
.tool-detail__implementation-card { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; border: 1px solid var(--admin-border-soft); border-radius: var(--admin-radius-md); background: var(--admin-surface-muted); padding: 16px; }
.tool-detail__implementation-main { display: grid; min-width: 0; gap: 8px; }
.tool-detail__implementation-title { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.tool-detail__implementation-title strong { color: var(--admin-text); font-size: 14px; }
.tool-detail__implementation-main p { margin: 0; color: var(--admin-text-secondary); font-size: 13px; }
.tool-detail__implementation-meta { display: flex; flex-wrap: wrap; gap: 10px 18px; color: var(--admin-text-muted); font-size: 12px; }
.tool-detail__implementation-error { color: var(--admin-danger); font-size: 12px; line-height: 1.5; }
.tool-detail__implementation-actions { display: flex; flex-shrink: 0; align-items: center; gap: 8px; }
.tool-detail__empty-block { display: grid; gap: 6px; border: 1px dashed var(--admin-border); border-radius: var(--admin-radius-md); background: var(--admin-surface-muted); padding: 18px; }
.tool-detail__empty-block strong { color: var(--admin-text-secondary); font-size: 14px; }
.tool-detail__empty-block span { color: var(--admin-text-muted); font-size: 12px; line-height: 1.6; }
.tool-detail__empty-actions { display: flex; align-items: center; gap: 12px; margin-top: 4px; }
.tool-detail__mapping-stack { display: grid; gap: 14px; }
.tool-detail__api-hint { display: grid; gap: 4px; margin-bottom: 18px; border: 1px solid var(--admin-border-soft); border-radius: var(--admin-radius-md); background: var(--admin-surface-muted); padding: 12px 14px; }
.tool-detail__api-hint strong { color: var(--admin-text); font-size: 13px; }
.tool-detail__api-hint span { color: var(--admin-text-muted); font-size: 12px; }
.tool-detail__aside { position: sticky; top: 100px; display: grid; gap: 14px; }
.tool-detail__status-card, .tool-detail__aside-note { border: 1px solid var(--admin-border); border-radius: var(--admin-radius-lg); background: var(--admin-surface); box-shadow: var(--admin-shadow-panel); padding: 17px; }
.tool-detail__status-card h3, .tool-detail__aside-note strong { margin: 0; color: var(--admin-text); font-size: 14px; }
.tool-detail__status-card ul { display: grid; gap: 12px; margin: 16px 0 0; padding: 0; list-style: none; }
.tool-detail__status-card li { display: flex; align-items: center; gap: 8px; color: var(--admin-text-subtle); font-size: 12px; }
.tool-detail__status-card li .el-icon { border: 1px solid var(--admin-border); border-radius: 50%; padding: 2px; }
.tool-detail__status-card li.is-done { color: #15803d; }
.tool-detail__status-card li.is-done .el-icon { border-color: #bbf7d0; background: #f0fdf4; }
.tool-detail__error { margin: 14px 0 0; border-radius: var(--admin-radius-sm); background: #fef2f2; padding: 10px; color: var(--admin-danger); font-size: 12px; line-height: 1.5; }
.tool-detail__aside-note { background: var(--admin-primary-soft); }
.tool-detail__aside-note p { margin: 6px 0 0; color: var(--admin-text-secondary); font-size: 12px; line-height: 1.6; }
.tool-detail__dialog-stack { display: grid; gap: 16px; }
.tool-detail__drawer-footer { display: flex; justify-content: flex-end; gap: 10px; }
.tool-test { display: grid; gap: 16px; }
.tool-test > section { border: 1px solid var(--admin-border); border-radius: var(--admin-radius-md); padding: 16px; }
.tool-test h3 { margin: 0 0 14px; color: var(--admin-text); font-size: 14px; }
.tool-test__notice { display: grid; gap: 4px; border: 1px solid #fde68a; border-radius: var(--admin-radius-md); background: #fffbeb; padding: 13px 15px; }
.tool-test__notice strong { color: #92400e; font-size: 13px; }
.tool-test__notice span, .tool-test__empty { color: var(--admin-text-muted); font-size: 12px; }
.tool-test__section-title { display: flex; align-items: center; justify-content: space-between; }
.tool-test__context-row { display: grid; grid-template-columns: 1fr 1fr 32px; gap: 8px; margin-top: 8px; }
.tool-test__result { display: grid; gap: 10px; }
.tool-test__result.is-success { border-color: #bbf7d0; background: #f0fdf4; }
.tool-test__result.is-error { border-color: #fecaca; background: #fef2f2; }
.tool-test__result > div { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.tool-test__result span, .tool-test__result p { margin: 0; color: var(--admin-text-muted); font-size: 12px; }
.tool-test__result pre { max-height: 320px; overflow: auto; border-radius: var(--admin-radius-sm); background: #0f172a; padding: 14px; color: #e2e8f0; font-family: Consolas, "Courier New", monospace; font-size: 12px; line-height: 1.6; white-space: pre-wrap; }
@media (max-width: 1100px) {
  .tool-detail__layout { grid-template-columns: 1fr; }
  .tool-detail__aside { position: static; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tool-detail__param-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tool-detail__param-row > :last-child { justify-self: end; }
}
@media (max-width: 760px) {
  .tool-detail__header { position: static; align-items: stretch; flex-direction: column; }
  .tool-detail__actions { justify-content: flex-start; }
  .tool-detail__title-row { align-items: flex-start; flex-direction: column; }
  .tool-detail__grid, .tool-detail__aside { grid-template-columns: 1fr; }
  .tool-detail__implementation-card, .tool-detail__empty-actions, .tool-detail__implementation-actions { align-items: stretch; flex-direction: column; }
  .tool-detail__param-row { grid-template-columns: 1fr 36px; }
  .tool-detail__param-row > *:not(:last-child) { grid-column: 1; }
  .tool-detail__param-row > :last-child { grid-column: 2; grid-row: 1 / span 5; }
  .tool-test__context-row { grid-template-columns: 1fr 32px; }
  .tool-test__context-row > :nth-child(2) { grid-column: 1; }
  .tool-test__context-row > :last-child { grid-column: 2; grid-row: 1 / span 2; }
}
</style>
