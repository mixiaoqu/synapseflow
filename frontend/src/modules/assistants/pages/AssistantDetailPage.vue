<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import type { FormInstance, FormRules } from "element-plus";
import {
  ChatDotRound,
  InfoFilled,
  MagicStick,
  Monitor,
  Setting,
} from "@element-plus/icons-vue";

import {
  createAssistant,
  getAssistant,
  listAssistantModelOptions,
  previewAssistant,
  updateAssistant,
} from "@/shared/api/assistants";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import { useTeamScopeStore } from "@/stores/team-scope";
import type {
  AssistantDetail,
  AssistantModelOption,
  AssistantPreviewPayload,
  AssistantUpsertPayload,
} from "@/shared/types/assistant";

interface PreviewMessage {
  role: "user" | "assistant";
  content: string;
}

function createDefaultForm(teamId: number | null): AssistantUpsertPayload {
  return {
    name: "",
    slug: "",
    current_team_id: teamId ?? 0,
    description: "",
    welcome_message: "",
    placeholder_text: "",
    llm_model_key: null,
    persona_prompt: "",
    rule_template: "",
    suggested_prompts: [],
    is_active: true,
    sort_order: 0,
  };
}

function normalizeTextValue(value: string | null | undefined) {
  return value ?? "";
}

function normalizePrompts(values: string[]) {
  return [...new Set(values.map((item) => item.trim()).filter(Boolean))].slice(0, 6);
}

function generateSlug(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_")
    .replace(/[^a-z0-9_]/g, "")
    .replace(/^_+|_+$/g, "")
    .slice(0, 120);
}

const route = useRoute();
const router = useRouter();
const teamScopeStore = useTeamScopeStore();

const formRef = ref<FormInstance>();
const chatContainerRef = ref<HTMLElement | null>(null);

const form = reactive(createDefaultForm(teamScopeStore.selectedTeamId));
const pageLoading = ref(false);
const pageError = ref<unknown>(null);
const saveLoading = ref(false);
const previewLoading = ref(false);
const modelsLoading = ref(false);
const modelOptions = ref<AssistantModelOption[]>([]);
const userInput = ref("");
const chatHistory = ref<PreviewMessage[]>([]);
const currentAssistant = ref<AssistantDetail | null>(null);
const slugEditedManually = ref(false);

const isCreateMode = computed(() => route.name === "assistant-create");
const assistantId = computed(() => {
  const raw = Number(route.params.assistantId);
  return Number.isInteger(raw) && raw > 0 ? raw : null;
});
const selectedTeamName = computed(() => teamScopeStore.selectedTeam?.name ?? "未选择团队");
const pageTitle = computed(() => (isCreateMode.value ? "新建助手" : "编辑助手"));
const scopeText = computed(() =>
  teamScopeStore.selectedTeamId ? `当前团队：${selectedTeamName.value}` : "请先选择团队",
);
const previewWelcomeMessage = computed(() => form.welcome_message.trim());

const rules: FormRules<AssistantUpsertPayload> = {
  name: [{ required: true, message: "请输入助手名称", trigger: "blur" }],
  slug: [{ required: true, message: "请输入唯一标识", trigger: "blur" }],
};

function formatDateTime(value: string | null) {
  if (!value) {
    return "暂无";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function buildUpsertPayload(): AssistantUpsertPayload | null {
  if (!teamScopeStore.selectedTeamId) {
    ElMessage.warning("请先选择所属团队，再保存助手。");
    return null;
  }

  return {
    name: form.name.trim(),
    slug: form.slug.trim(),
    current_team_id: teamScopeStore.selectedTeamId,
    description: form.description.trim() || null,
    welcome_message: form.welcome_message.trim() || null,
    placeholder_text: form.placeholder_text.trim() || null,
    llm_model_key: form.llm_model_key || null,
    persona_prompt: form.persona_prompt.trim() || null,
    rule_template: form.rule_template.trim() || null,
    suggested_prompts: normalizePrompts(form.suggested_prompts),
    is_active: form.is_active,
    sort_order: form.sort_order,
  };
}

function applyAssistant(detail: AssistantDetail) {
  currentAssistant.value = detail;
  Object.assign(form, createDefaultForm(teamScopeStore.selectedTeamId ?? detail.team_id), {
    name: detail.name,
    slug: detail.slug,
    current_team_id: teamScopeStore.selectedTeamId ?? detail.team_id,
    description: normalizeTextValue(detail.description),
    welcome_message: normalizeTextValue(detail.welcome_message),
    placeholder_text: normalizeTextValue(detail.placeholder_text),
    llm_model_key: detail.llm_model_key,
    persona_prompt: normalizeTextValue(detail.persona_prompt),
    rule_template: normalizeTextValue(detail.rule_template),
    suggested_prompts: normalizePrompts(detail.suggested_prompts ?? []),
    is_active: detail.is_active,
    sort_order: detail.sort_order,
  });
}

function resetPageForm() {
  currentAssistant.value = null;
  slugEditedManually.value = false;
  Object.assign(form, createDefaultForm(teamScopeStore.selectedTeamId));
  chatHistory.value = [];
  userInput.value = "";
}

async function loadModelOptions() {
  if (modelsLoading.value) {
    return;
  }

  modelsLoading.value = true;
  try {
    const response = await listAssistantModelOptions();
    modelOptions.value = response.items;
    if (!form.llm_model_key && response.items.length > 0) {
      form.llm_model_key = response.items[0]?.key ?? null;
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "加载模型列表失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    modelsLoading.value = false;
  }
}

async function loadPage() {
  pageError.value = null;

  if (isCreateMode.value) {
    resetPageForm();
    if (modelOptions.value.length === 0) {
      await loadModelOptions();
    }
    return;
  }

  if (!assistantId.value) {
    pageError.value = new Error("助手标识无效。");
    return;
  }

  pageLoading.value = true;
  try {
    await loadModelOptions();
    const detail = await getAssistant(assistantId.value);
    applyAssistant(detail);
    slugEditedManually.value = true;
  } catch (error) {
    pageError.value = error;
  } finally {
    pageLoading.value = false;
  }
}

function handleBack() {
  void router.push("/assistants");
}

function handleSlugInput() {
  slugEditedManually.value = true;
}

function handlePromptsChange(values: string[]) {
  const nextPrompts = normalizePrompts(values);
  if (nextPrompts.length < values.length) {
    ElMessage.warning("推荐问题最多保留 6 条，且会自动去重与去除空白。");
  }
  form.suggested_prompts = nextPrompts;
}

function clearPreview() {
  chatHistory.value = [];
}

function scrollPreviewToBottom() {
  nextTick(() => {
    chatContainerRef.value?.scrollTo({
      top: chatContainerRef.value.scrollHeight,
      behavior: "smooth",
    });
  });
}

async function handlePreview() {
  const query = userInput.value.trim();
  const payload = buildUpsertPayload();

  if (!payload || !query || previewLoading.value) {
    return;
  }

  const previewPayload: AssistantPreviewPayload = {
    ...payload,
    query,
    name: payload.name,
    include_unpublished: true,
  };

  chatHistory.value.push({
    role: "user",
    content: query,
  });
  userInput.value = "";
  previewLoading.value = true;
  scrollPreviewToBottom();

  try {
    const response = await previewAssistant(previewPayload);
    chatHistory.value.push({
      role: "assistant",
      content: response.answer_text || response.answer || "预览接口未返回内容。",
    });
    scrollPreviewToBottom();
  } catch (error) {
    const message = error instanceof Error ? error.message : "预览请求失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    previewLoading.value = false;
  }
}

async function handleSave() {
  if (!formRef.value || saveLoading.value) {
    return;
  }

  const isValid = await formRef.value
    .validate()
    .then(() => true)
    .catch(() => false);

  if (!isValid) {
    return;
  }

  const payload = buildUpsertPayload();
  if (!payload) {
    return;
  }

  saveLoading.value = true;
  try {
    if (isCreateMode.value) {
      await createAssistant(payload);
      ElMessage.success(`已创建助手“${payload.name}”。`);
    } else {
      if (!assistantId.value) {
        ElMessage.error("缺少助手标识，无法保存。");
        return;
      }

      await updateAssistant(assistantId.value, payload);
      ElMessage.success(`已保存助手“${payload.name}”。`);
    }

    void router.push("/assistants");
  } catch (error) {
    const message = error instanceof Error ? error.message : "保存助手失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    saveLoading.value = false;
  }
}

onMounted(() => {
  void loadPage();
});

watch(
  () => form.name,
  (value) => {
    if (!isCreateMode.value || slugEditedManually.value) {
      return;
    }

    const generated = generateSlug(value);
    if (generated) {
      form.slug = generated;
    }
  },
);

watch(
  () => route.fullPath,
  () => {
    void loadPage();
  },
);

watch(
  () => teamScopeStore.selectedTeamId,
  () => {
    if (isCreateMode.value) {
      Object.assign(form, createDefaultForm(teamScopeStore.selectedTeamId), {
        name: form.name,
        slug: form.slug,
        description: form.description,
        welcome_message: form.welcome_message,
        placeholder_text: form.placeholder_text,
        llm_model_key: form.llm_model_key,
        persona_prompt: form.persona_prompt,
        rule_template: form.rule_template,
        suggested_prompts: form.suggested_prompts,
        is_active: form.is_active,
        sort_order: form.sort_order,
      });
      return;
    }

    void loadPage();
  },
);
</script>

<template>
  <section class="assistant-detail-page">
    <AppLoading
      v-if="pageLoading"
      title="助手详情加载中"
      description="正在准备助手配置与模型列表，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="pageError"
      title="助手详情加载失败"
      description="暂时无法获取助手详情，请稍后重试。"
      :error="pageError"
      @retry="loadPage"
    />

    <section v-else class="assistant-detail-page__layout">
      <section class="assistant-panel assistant-panel--form">
        <div class="assistant-panel__header">
          <div class="assistant-panel__heading">
            <div class="assistant-panel__title-row">
              <h1 class="assistant-panel__title">
                <el-icon><Setting /></el-icon>
                <span>{{ form.name.trim() || pageTitle }}</span>
              </h1>
              <el-tag
                v-if="!isCreateMode"
                :type="form.is_active ? 'success' : 'info'"
                effect="plain"
                round
              >
                {{ form.is_active ? "已启用" : "已停用" }}
              </el-tag>
            </div>
            <div class="assistant-panel__meta">
              <span>{{ scopeText }}</span>
              <span v-if="currentAssistant">更新于 {{ formatDateTime(currentAssistant.updated_at) }}</span>
            </div>
          </div>

          <div class="assistant-panel__actions">
            <el-button @click="handleBack">取消</el-button>
            <el-button type="primary" :loading="saveLoading" @click="handleSave">
              保存配置
            </el-button>
          </div>
        </div>

        <div class="assistant-panel__body">
          <div
            class="assistant-scope"
            :class="{ 'assistant-scope--warning': !teamScopeStore.selectedTeamId }"
          >
            <el-icon><MagicStick /></el-icon>
            <span>
              {{
                teamScopeStore.selectedTeamId
                  ? `当前所有保存和预览都作用于团队「${selectedTeamName}」`
                  : "当前未选择团队，暂时无法保存或预览助手。"
              }}
            </span>
          </div>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-position="top"
            class="assistant-form"
          >
            <h2 class="assistant-form__section-title">基础信息</h2>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="助手名称" prop="name">
                  <el-input
                    v-model="form.name"
                    maxlength="100"
                    show-word-limit
                    placeholder="输入对外展示的助手名称"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="唯一标识" prop="slug">
                  <el-input
                    v-model="form.slug"
                    maxlength="120"
                    show-word-limit
                    placeholder="例如 legal_assistant"
                    @input="handleSlugInput"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="排序权重">
                  <el-input-number
                    v-model="form.sort_order"
                    :min="0"
                    :step="1"
                    controls-position="right"
                    class="assistant-form__number"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="发布状态">
                  <el-switch
                    v-model="form.is_active"
                    inline-prompt
                    active-text="启用"
                    inactive-text="停用"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="助手说明">
                  <el-input
                    v-model="form.description"
                    type="textarea"
                    :rows="3"
                    maxlength="500"
                    show-word-limit
                    placeholder="简要描述该助手的用途和适用场景"
                  />
                </el-form-item>
              </el-col>
            </el-row>

            <h2 class="assistant-form__section-title">模型与提示词</h2>
            <el-row :gutter="16">
              <el-col :span="24">
                <el-form-item label="选用模型">
                  <el-select
                    v-model="form.llm_model_key"
                    clearable
                    filterable
                    placeholder="请选择模型"
                    class="assistant-form__full"
                    :loading="modelsLoading"
                  >
                    <el-option
                      v-for="item in modelOptions"
                      :key="item.key"
                      :label="`${item.name} · ${item.provider}`"
                      :value="item.key"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="人设提示词">
                  <el-input
                    v-model="form.persona_prompt"
                    type="textarea"
                    :rows="6"
                    placeholder="定义该助手的角色、语气和基本行为边界"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="规则模板">
                  <el-input
                    v-model="form.rule_template"
                    type="textarea"
                    :rows="5"
                    placeholder="定义输出格式、拒答规则或其他硬性约束"
                  />
                </el-form-item>
              </el-col>
            </el-row>

            <h2 class="assistant-form__section-title">界面展现</h2>
            <el-row :gutter="16">
              <el-col :span="24">
                <el-form-item label="欢迎语">
                  <el-input
                    v-model="form.welcome_message"
                    type="textarea"
                    :rows="3"
                    placeholder="用户打开助手时看到的第一句话"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="输入框占位符">
                  <el-input
                    v-model="form.placeholder_text"
                    placeholder="例如：请输入您的问题..."
                  />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="推荐问题">
                  <el-select
                    v-model="form.suggested_prompts"
                    multiple
                    filterable
                    allow-create
                    default-first-option
                    :reserve-keyword="false"
                    class="assistant-form__full"
                    placeholder="输入问题后按回车添加"
                    @change="handlePromptsChange"
                  />
                  <div class="assistant-form__hint">
                    推荐问题会显示在预览区和前台会话入口，最多保留 6 条。
                  </div>
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </div>
      </section>

      <section class="assistant-panel assistant-panel--preview">
        <div class="assistant-panel__header">
          <el-icon><ChatDotRound /></el-icon>
          <span>预览沙盒</span>
        </div>

        <div class="assistant-preview__hint">
          <el-icon><InfoFilled /></el-icon>
          <span>这里只验证助手人设、欢迎语和规则模板，不代表正式接入知识库后的业务效果。</span>
        </div>

        <div ref="chatContainerRef" class="assistant-preview__messages">
          <div
            v-if="previewWelcomeMessage"
            class="assistant-preview__bubble assistant-preview__bubble--assistant"
          >
            <el-icon><Monitor /></el-icon>
            <span class="assistant-preview__text">{{ previewWelcomeMessage }}</span>
          </div>

          <div
            v-if="form.suggested_prompts.length > 0 && chatHistory.length === 0"
            class="assistant-preview__suggestions"
          >
            <el-button
              v-for="item in form.suggested_prompts"
              :key="item"
              size="small"
              round
              @click="userInput = item; handlePreview()"
            >
              {{ item }}
            </el-button>
          </div>

          <div
            v-for="(message, index) in chatHistory"
            :key="`${message.role}-${index}`"
            :class="[
              'assistant-preview__bubble',
              message.role === 'assistant'
                ? 'assistant-preview__bubble--assistant'
                : 'assistant-preview__bubble--user',
            ]"
          >
            <el-icon v-if="message.role === 'assistant'"><Monitor /></el-icon>
            <span class="assistant-preview__text">{{ message.content }}</span>
          </div>

          <div
            v-if="previewLoading"
            class="assistant-preview__bubble assistant-preview__bubble--assistant"
          >
            <el-icon class="is-loading"><Monitor /></el-icon>
            <span>预览请求处理中...</span>
          </div>
        </div>

        <div class="assistant-preview__input">
          <el-input
            v-model="userInput"
            type="textarea"
            :rows="3"
            :placeholder="form.placeholder_text.trim() || '输入测试问题，按 Ctrl + Enter 发送...'"
            @keydown.ctrl.enter.prevent="handlePreview"
          />
          <div class="assistant-preview__actions">
            <el-button @click="clearPreview">清空</el-button>
            <el-button
              type="primary"
              :disabled="!userInput.trim() || previewLoading || !teamScopeStore.selectedTeamId"
              :loading="previewLoading"
              @click="handlePreview"
            >
              发送预览
            </el-button>
          </div>
        </div>
      </section>
    </section>
  </section>
</template>

<style scoped>
.assistant-detail-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
}

.assistant-detail-page__layout {
  display: grid;
  flex: 1;
  grid-template-columns: minmax(0, 1.5fr) minmax(360px, 0.9fr);
  gap: 20px;
  min-height: 0;
  overflow: hidden;
}

.assistant-panel {
  display: flex;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--admin-border);
  border-radius: var(--admin-radius-lg);
  background: var(--admin-surface);
  box-shadow: var(--admin-shadow-panel);
}

.assistant-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--admin-border-soft);
  background: var(--admin-surface-muted);
  color: var(--admin-text-secondary);
  padding: 10px 16px;
}

.assistant-panel__heading {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 12px;
}

.assistant-panel__title-row,
.assistant-panel__meta,
.assistant-panel__actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.assistant-panel__title-row,
.assistant-panel__meta {
  flex-wrap: wrap;
}

.assistant-panel__title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  max-width: min(520px, 100%);
  overflow: hidden;
  color: var(--admin-text);
  font-size: 15px;
  font-weight: 700;
  white-space: nowrap;
}

.assistant-panel__title span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.assistant-panel__title .el-icon {
  flex-shrink: 0;
  color: var(--admin-primary);
}

.assistant-panel__meta {
  color: var(--admin-text-muted);
  font-size: 12px;
  white-space: nowrap;
}

.assistant-panel__actions {
  flex-shrink: 0;
}

.assistant-panel__body {
  flex: 1;
  overflow-y: auto;
  padding: 18px;
}

.assistant-scope {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 18px;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 13px;
  line-height: 1.6;
  padding: 12px 14px;
}

.assistant-scope--warning {
  border-color: #fde68a;
  background: #fffbeb;
  color: #b45309;
}

.assistant-form__section-title {
  margin: 0 0 16px;
  border-bottom: 1px solid var(--admin-border-soft);
  color: var(--admin-text);
  font-size: 14px;
  font-weight: 700;
  padding-bottom: 8px;
}

.assistant-form__section-title:not(:first-child) {
  margin-top: 8px;
}

.assistant-form__full,
.assistant-form__number {
  width: 100%;
}

.assistant-form__hint {
  margin-top: 6px;
  color: var(--admin-text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.assistant-panel--preview {
  background: var(--admin-surface-muted);
}

.assistant-preview__hint {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  border-bottom: 1px solid #fef3c7;
  background: #fffbeb;
  color: #b45309;
  font-size: 12px;
  line-height: 1.6;
  padding: 12px 16px;
}

.assistant-preview__messages {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding: 18px;
}

.assistant-preview__suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.assistant-preview__bubble {
  display: inline-flex;
  max-width: 88%;
  align-items: flex-start;
  gap: 8px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.7;
  padding: 12px 14px;
  word-break: break-word;
}

.assistant-preview__text {
  white-space: pre-wrap;
}

.assistant-preview__bubble--assistant {
  align-self: flex-start;
  border: 1px solid var(--admin-border-soft);
  border-top-left-radius: 4px;
  background: var(--admin-surface);
  color: #1f2937;
}

.assistant-preview__bubble--user {
  align-self: flex-end;
  border-top-right-radius: 4px;
  background: var(--admin-primary);
  color: #ffffff;
}

.assistant-preview__input {
  flex-shrink: 0;
  border-top: 1px solid var(--admin-border-soft);
  background: var(--admin-surface);
  padding: 16px;
}

.assistant-preview__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

@media (max-width: 1280px) {
  .assistant-detail-page__layout {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(0, 1fr) minmax(520px, 1fr);
    overflow: auto;
  }

  .assistant-panel--preview {
    min-height: 520px;
  }
}

@media (max-width: 900px) {
  .assistant-detail-page {
    overflow: auto;
  }

  .assistant-panel__header,
  .assistant-panel__heading,
  .assistant-panel__actions {
    flex-direction: column;
    align-items: stretch;
  }

  .assistant-detail-page__layout {
    display: flex;
    flex-direction: column;
    overflow: visible;
  }

  .assistant-panel--form,
  .assistant-panel--preview {
    min-height: 560px;
  }
}
</style>
