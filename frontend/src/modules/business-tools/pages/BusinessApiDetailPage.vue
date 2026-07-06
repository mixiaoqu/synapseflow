<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Back, Check, Link } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import ApiRequestSchemaEditor from "@/modules/business-tools/components/ApiRequestSchemaEditor.vue";
import ApiResponseSchemaEditor from "@/modules/business-tools/components/ApiResponseSchemaEditor.vue";
import BusinessToolModuleNav from "@/modules/business-tools/components/BusinessToolModuleNav.vue";
import {
  createBusinessApi,
  getBusinessApi,
  listBusinessConnections,
  updateBusinessApi,
} from "@/shared/api/business-tools";
import { listTeamOptions } from "@/shared/api/teams";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import type {
  BusinessApiPayload,
  BusinessApiRequestFieldSpec,
  BusinessApiRequestSchema,
  BusinessApiResponseFieldSpec,
  BusinessApiResponseSchema,
  BusinessApiSourceType,
  BusinessConnection,
  BusinessToolMethod,
} from "@/shared/types/business-tool";
import type { TeamOption } from "@/shared/types/team";
import { getErrorMessage } from "@/shared/utils/error";
import { useTeamScopeStore } from "@/stores/team-scope";

const route = useRoute();
const router = useRouter();
const teamScopeStore = useTeamScopeStore();
const apiId = computed(() => Number(route.params.apiId));
const isCreate = computed(() => route.name === "business-tool-api-create");

const loading = ref(true);
const saving = ref(false);
const teams = ref<TeamOption[]>([]);
const formConnections = ref<BusinessConnection[]>([]);

const form = reactive({
  team_id: null as number | null,
  connection_id: null as number | null,
  api_key: "",
  name: "",
  description: "",
  method: "GET" as BusinessToolMethod,
  path: "",
  request_schema: createEmptyRequestSchema(),
  response_schema: createEmptyResponseSchema(),
  source_type: "manual" as BusinessApiSourceType,
  source_version: "",
  enabled: true,
});

const pageTitle = computed(() => (isCreate.value ? "新建业务接口" : form.name || "编辑业务接口"));
const pageDescription = computed(() =>
  isCreate.value
    ? "定义一份可复用的外部接口结构，供多个业务工具实现绑定。"
    : "调整接口路径、请求字段和响应字段，保持工具实现绑定稳定。",
);

function createEmptyRequestSchema(): BusinessApiRequestSchema {
  return { fields: [] };
}

function createEmptyResponseSchema(): BusinessApiResponseSchema {
  return { fields: [] };
}

function listRequestFields(schema?: BusinessApiRequestSchema | null): BusinessApiRequestFieldSpec[] {
  return Array.isArray(schema?.fields) ? schema.fields : [];
}

function listResponseFields(schema?: BusinessApiResponseSchema | null): BusinessApiResponseFieldSpec[] {
  return Array.isArray(schema?.fields) ? schema.fields : [];
}

function cloneRequestSchema(schema?: BusinessApiRequestSchema | null): BusinessApiRequestSchema {
  return {
    fields: listRequestFields(schema).map((field) => ({ ...field })),
  };
}

function cloneResponseSchema(schema?: BusinessApiResponseSchema | null): BusinessApiResponseSchema {
  return {
    fields: listResponseFields(schema).map((field) => ({ ...field })),
  };
}

function resetForm() {
  Object.assign(form, {
    team_id: teamScopeStore.selectedTeamId ?? teams.value[0]?.id ?? null,
    connection_id: null,
    api_key: "",
    name: "",
    description: "",
    method: "GET",
    path: "",
    request_schema: createEmptyRequestSchema(),
    response_schema: createEmptyResponseSchema(),
    source_type: "manual",
    source_version: "",
    enabled: true,
  });
}

function applyApi(api: {
  team_id: number;
  connection_id: number;
  api_key: string;
  name: string;
  description: string;
  method: BusinessToolMethod;
  path: string;
  request_schema: BusinessApiRequestSchema;
  response_schema: BusinessApiResponseSchema;
  source_type: BusinessApiSourceType;
  source_version: string | null;
  enabled: boolean;
}) {
  Object.assign(form, {
    team_id: api.team_id,
    connection_id: api.connection_id,
    api_key: api.api_key,
    name: api.name,
    description: api.description,
    method: api.method,
    path: api.path,
    request_schema: cloneRequestSchema(api.request_schema),
    response_schema: cloneResponseSchema(api.response_schema),
    source_type: api.source_type,
    source_version: api.source_version ?? "",
    enabled: api.enabled,
  });
}

async function loadFormConnections(teamId = form.team_id) {
  if (!teamId) {
    formConnections.value = [];
    return;
  }
  const response = await listBusinessConnections({
    team_id: teamId,
    page: 1,
    page_size: 100,
  });
  formConnections.value = response.items;
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
      await loadFormConnections();
      return;
    }
    const api = await getBusinessApi(apiId.value);
    applyApi(api);
    await loadFormConnections(api.team_id);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "业务接口配置加载失败。"));
    void router.push("/business-tools/apis");
  } finally {
    loading.value = false;
  }
}

function normalizeRequestSchema(schema: BusinessApiRequestSchema): BusinessApiRequestSchema {
  const fields = listRequestFields(schema)
    .map((field) => ({
      ...field,
      name: field.name.trim(),
      label: field.label.trim(),
      description: field.description.trim(),
    }))
    .filter((field) => field.name || field.label || field.description);

  if (fields.some((field) => !field.name || !field.label)) {
    throw new Error("每个请求字段都需要填写字段名和显示名。");
  }

  const uniqueKeys = new Set(fields.map((field) => `${field.in}:${field.name}`));
  if (uniqueKeys.size !== fields.length) {
    throw new Error("请求字段中不能存在重复的位置和字段名组合。");
  }

  return { fields };
}

function normalizeResponseSchema(schema: BusinessApiResponseSchema): BusinessApiResponseSchema {
  const fields = listResponseFields(schema)
    .map((field) => ({
      ...field,
      path: field.path.trim(),
      label: field.label.trim(),
      description: field.description.trim(),
    }))
    .filter((field) => field.path || field.label || field.description);

  if (fields.some((field) => !field.path || !field.label)) {
    throw new Error("每个响应字段都需要填写字段路径和显示名。");
  }

  const uniquePaths = new Set(fields.map((field) => field.path));
  if (uniquePaths.size !== fields.length) {
    throw new Error("响应字段路径不能重复。");
  }

  return { fields };
}

function buildPayload(): BusinessApiPayload {
  if (!form.team_id || !form.connection_id) {
    throw new Error("请选择所属团队和业务连接。");
  }
  if (!form.api_key.trim() || !form.name.trim() || !form.path.trim()) {
    throw new Error("请填写接口标识、接口名称和相对路径。");
  }
  return {
    team_id: form.team_id,
    connection_id: form.connection_id,
    api_key: form.api_key.trim().toLowerCase(),
    name: form.name.trim(),
    description: form.description.trim(),
    method: form.method,
    path: form.path.trim(),
    request_schema: normalizeRequestSchema(form.request_schema),
    response_schema: normalizeResponseSchema(form.response_schema),
    source_type: form.source_type,
    source_version: form.source_version.trim() || null,
    enabled: form.enabled,
  };
}

async function submit() {
  let payload: BusinessApiPayload;
  try {
    payload = buildPayload();
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : "请检查接口配置。");
    return;
  }
  saving.value = true;
  try {
    if (isCreate.value) {
      const created = await createBusinessApi(payload);
      ElMessage.success("业务接口已创建。");
      await router.replace(`/business-tools/apis/${created.id}`);
      applyApi(created);
      await loadFormConnections(created.team_id);
    } else {
      const updated = await updateBusinessApi(apiId.value, payload);
      ElMessage.success("业务接口已更新。");
      applyApi(updated);
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "保存业务接口失败。"));
  } finally {
    saving.value = false;
  }
}

watch(
  () => form.team_id,
  async (teamId, previous) => {
    if (!teamId || teamId === previous || loading.value) return;
    form.connection_id = null;
    await loadFormConnections(teamId);
  },
);

onMounted(() => void teamScopeStore.bootstrap({ allowAllTeams: true }).finally(loadPage));
</script>

<template>
  <AppLoading v-if="loading" title="业务接口加载中" description="正在准备接口配置页面。" :blocks="4" />

  <section v-else class="api-detail">
    <BusinessToolModuleNav />

    <header class="api-detail__header">
      <div class="api-detail__title-group">
        <el-button text class="api-detail__back" @click="router.push('/business-tools/apis')">
          <el-icon><Back /></el-icon>返回业务接口
        </el-button>
        <div class="api-detail__title-row">
          <div>
            <h2>{{ pageTitle }}</h2>
            <p>{{ pageDescription }}</p>
          </div>
          <el-tag :type="form.enabled ? 'success' : 'info'" effect="plain" size="large">
            {{ form.enabled ? "已启用" : "已停用" }}
          </el-tag>
        </div>
      </div>
      <div class="api-detail__actions">
        <el-button :loading="saving" type="primary" @click="submit">
          <el-icon><Check /></el-icon>保存接口
        </el-button>
      </div>
    </header>

    <div class="api-detail__content">
      <main class="api-detail__main">
        <section class="api-detail__section">
          <header>
            <span>1</span>
            <div>
              <h3>基本信息</h3>
              <p>描述接口来源、归属连接和标识规则。</p>
            </div>
          </header>
          <div class="api-detail__grid">
            <el-form-item label="所属团队" required>
              <el-select v-model="form.team_id" filterable class="w-full" :disabled="!isCreate">
                <el-option v-for="team in teams" :key="team.id" :label="team.name" :value="team.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="业务连接" required>
              <el-select v-model="form.connection_id" filterable class="w-full" placeholder="选择连接">
                <el-option
                  v-for="item in formConnections"
                  :key="item.id"
                  :label="`${item.name} · ${item.status === 'available' ? '可用' : '待验证'}`"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="接口名称" required>
              <el-input v-model="form.name" maxlength="100" placeholder="例如：商品搜索接口" />
            </el-form-item>
            <el-form-item label="接口标识" required>
              <el-input
                v-model="form.api_key"
                maxlength="120"
                placeholder="例如：product.search.api"
                @blur="form.api_key = form.api_key.trim().toLowerCase()"
              />
            </el-form-item>
          </div>
          <el-form-item label="描述说明">
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="3"
              maxlength="1000"
              show-word-limit
              placeholder="说明这个接口的业务用途、入参与返回内容。"
            />
          </el-form-item>
        </section>

        <section class="api-detail__section">
          <header>
            <span>2</span>
            <div>
              <h3>请求定义</h3>
              <p>接口路径必须使用连接下的相对路径。</p>
            </div>
          </header>
          <div class="api-detail__request-row">
            <el-form-item label="请求方法">
              <el-select v-model="form.method" class="api-detail__method">
                <el-option
                  v-for="method in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']"
                  :key="method"
                  :label="method"
                  :value="method"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="接口路径" required>
              <el-input v-model="form.path" placeholder="/v1/products/search" />
            </el-form-item>
          </div>
          <div class="api-detail__grid">
            <el-form-item label="来源类型">
              <el-select v-model="form.source_type" class="w-full">
                <el-option label="手动维护" value="manual" />
                <el-option label="OpenAPI 导入" value="openapi_imported" />
              </el-select>
            </el-form-item>
            <el-form-item label="来源版本">
              <el-input v-model="form.source_version" maxlength="100" placeholder="例如：v1.2.0" />
            </el-form-item>
          </div>
        </section>

        <section class="api-detail__section">
          <header>
            <span>3</span>
            <div>
              <h3>接口字段</h3>
              <p>这里描述外部 API 真实的输入输出结构，供后续工具实现直接复用。</p>
            </div>
          </header>
          <div class="api-detail__schema-stack">
            <ApiRequestSchemaEditor v-model="form.request_schema.fields" />
            <ApiResponseSchemaEditor v-model="form.response_schema.fields" />
          </div>
        </section>
      </main>

      <aside class="api-detail__aside">
        <div class="api-detail__note">
          <strong>接口状态</strong>
          <el-switch v-model="form.enabled" active-text="允许工具实现绑定此接口" />
        </div>

        <div class="api-detail__note">
          <strong>配置建议</strong>
          <p>这里定义的是外部系统真实接口结构。工具实现层只负责做上下文、请求和响应映射。</p>
        </div>

        <div class="api-detail__note api-detail__note--soft">
          <strong>复用关系</strong>
          <p>一个业务接口可以被多个业务工具实现复用，所以这里尽量保持稳定的接口抽象。</p>
          <div class="api-detail__note-link">
            <el-icon><Link /></el-icon>
            <span>后续可直接在工具实现页绑定</span>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.api-detail { display: grid; gap: 18px; }
.api-detail__header { position: sticky; z-index: 6; top: -24px; display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; border: 1px solid var(--admin-border); border-radius: var(--admin-radius-lg); background: rgba(255,255,255,.96); box-shadow: var(--admin-shadow-panel); padding: 16px 18px; backdrop-filter: blur(10px); }
.api-detail__title-group { display: grid; min-width: 0; gap: 8px; }
.api-detail__back { width: fit-content; margin-left: -10px; color: var(--admin-text-muted); }
.api-detail__title-row { display: flex; align-items: center; gap: 12px; }
.api-detail__title-row h2 { margin: 0; color: var(--admin-text); font-size: 22px; }
.api-detail__title-row p { margin: 5px 0 0; color: var(--admin-text-muted); font-size: 13px; line-height: 1.5; }
.api-detail__actions { display: flex; flex: 0 0 auto; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.api-detail__content { display: grid; grid-template-columns: minmax(0, 1fr) 280px; align-items: start; gap: 18px; }
.api-detail__main { display: grid; gap: 16px; }
.api-detail__section { border: 1px solid var(--admin-border); border-radius: var(--admin-radius-lg); background: var(--admin-surface); box-shadow: var(--admin-shadow-panel); padding: 20px; }
.api-detail__section > header { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 20px; }
.api-detail__section > header > span { display: inline-flex; width: 26px; height: 26px; flex: 0 0 auto; align-items: center; justify-content: center; border-radius: 50%; background: var(--admin-primary-soft); color: var(--admin-primary); font-size: 12px; font-weight: 700; }
.api-detail__section h3 { margin: 2px 0 0; color: var(--admin-text); font-size: 15px; }
.api-detail__section header p { margin: 4px 0 0; color: var(--admin-text-muted); font-size: 12px; line-height: 1.5; }
.api-detail__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 18px; }
.api-detail__request-row { display: grid; grid-template-columns: 150px minmax(0, 1fr); gap: 18px; }
.api-detail__schema-stack { display: grid; gap: 14px; }
.api-detail__method { width: 100%; }
.api-detail__aside { position: sticky; top: 100px; display: grid; gap: 14px; }
.api-detail__note { display: grid; gap: 12px; border: 1px solid var(--admin-border); border-radius: var(--admin-radius-lg); background: var(--admin-surface); box-shadow: var(--admin-shadow-panel); padding: 17px; }
.api-detail__note strong { color: var(--admin-text); font-size: 14px; }
.api-detail__note p { margin: 0; color: var(--admin-text-secondary); font-size: 12px; line-height: 1.6; }
.api-detail__note--soft { background: var(--admin-primary-soft); }
.api-detail__note-link { display: inline-flex; align-items: center; gap: 6px; color: var(--admin-primary); font-size: 12px; }
@media (max-width: 1100px) {
  .api-detail__content { grid-template-columns: 1fr; }
  .api-detail__aside { position: static; grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .api-detail__header { position: static; align-items: stretch; flex-direction: column; }
  .api-detail__actions { justify-content: flex-start; }
  .api-detail__title-row { align-items: flex-start; flex-direction: column; }
  .api-detail__grid, .api-detail__request-row, .api-detail__aside { grid-template-columns: 1fr; }
}
</style>
