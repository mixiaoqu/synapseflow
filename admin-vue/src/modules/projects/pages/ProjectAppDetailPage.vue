<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import type { FormInstance, FormRules } from "element-plus";
import { ArrowLeft, Link, Plus, Setting } from "@element-plus/icons-vue";

import { listAssistants } from "@/shared/api/assistants";
import { listKnowledgeBases } from "@/shared/api/knowledge-bases";
import {
  createProjectApp,
  createProjectAppEmbedPreview,
  getProject,
  getProjectApp,
  updateProjectApp,
} from "@/shared/api/projects";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import type { AssistantSummary } from "@/shared/types/assistant";
import type { KnowledgeBaseSummary } from "@/shared/types/knowledge-base";
import type { ProjectAppSummary, ProjectAppUpsertPayload, ProjectSummary } from "@/shared/types/project";

interface ProjectAppFormState {
  code: string;
  name: string;
  description: string;
  default_assistant_id: number | null;
  knowledge_base_ids: number[];
  is_active: boolean;
}

function createDefaultForm(): ProjectAppFormState {
  return {
    code: "",
    name: "",
    description: "",
    default_assistant_id: null,
    knowledge_base_ids: [],
    is_active: true,
  };
}

function normalizeCode(value: string) {
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

const formRef = ref<FormInstance>();
const project = ref<ProjectSummary | null>(null);
const currentApp = ref<ProjectAppSummary | null>(null);
const assistants = ref<AssistantSummary[]>([]);
const knowledgeBases = ref<KnowledgeBaseSummary[]>([]);
const pageLoading = ref(false);
const pageError = ref<unknown>(null);
const saveLoading = ref(false);
const previewLoading = ref(false);
const kbDialogVisible = ref(false);
const tempSelectedKnowledgeBaseIds = ref<number[]>([]);
const previewEmbedUrl = ref("");
const codeEditedManually = ref(false);

const form = reactive(createDefaultForm());

const projectId = computed(() => {
  const raw = Number(route.params.projectId);
  return Number.isInteger(raw) && raw > 0 ? raw : null;
});

const appId = computed(() => {
  const raw = Number(route.params.appId);
  return Number.isInteger(raw) && raw > 0 ? raw : null;
});

const isCreateMode = computed(() => route.name === "project-app-create");
const pageTitle = computed(() => (isCreateMode.value ? "新建发布渠道" : "编辑发布渠道"));

const selectedKnowledgeBases = computed(() =>
  form.knowledge_base_ids
    .map((id) => knowledgeBases.value.find((item) => item.id === id))
    .filter((item): item is KnowledgeBaseSummary => Boolean(item)),
);

const availableKnowledgeBases = computed(() =>
  knowledgeBases.value.filter((item) => !tempSelectedKnowledgeBaseIds.value.includes(item.id)),
);

const temporarySelectedKnowledgeBases = computed(() =>
  tempSelectedKnowledgeBaseIds.value
    .map((id) => knowledgeBases.value.find((item) => item.id === id))
    .filter((item): item is KnowledgeBaseSummary => Boolean(item)),
);

const canGeneratePreview = computed(
  () => Boolean(projectId.value && appId.value && form.is_active),
);

const rules: FormRules<ProjectAppFormState> = {
  name: [{ required: true, message: "请输入应用名称", trigger: "blur" }],
  code: [{ required: true, message: "请输入应用编码", trigger: "blur" }],
  default_assistant_id: [{ required: true, message: "请选择默认助手", trigger: "change" }],
};

function applyApp(app: ProjectAppSummary) {
  currentApp.value = app;
  form.code = app.code;
  form.name = app.name;
  form.description = app.description ?? "";
  form.default_assistant_id = app.default_assistant_id;
  form.knowledge_base_ids = app.bindings.map((item) => item.knowledge_base_id);
  form.is_active = app.is_active;
}

function buildPayload(): ProjectAppUpsertPayload {
  return {
    code: form.code.trim(),
    name: form.name.trim(),
    description: form.description.trim() || null,
    default_assistant_id: form.default_assistant_id,
    bindings: form.knowledge_base_ids.map((id) => ({
      knowledge_base_id: id,
    })),
    is_active: form.is_active,
  };
}

async function loadPage() {
  if (!projectId.value) {
    pageError.value = new Error("项目标识无效。");
    return;
  }

  pageLoading.value = true;
  pageError.value = null;
  previewEmbedUrl.value = "";

  try {
    const projectResponse = await getProject(projectId.value);
    project.value = projectResponse;

    const [assistantResponses, knowledgeBaseResponses] = await Promise.all([
      listAssistants({ team_id: projectResponse.team_id }),
      listKnowledgeBases(projectResponse.team_id),
    ]);
    assistants.value = assistantResponses;
    knowledgeBases.value = knowledgeBaseResponses;

    if (isCreateMode.value) {
      Object.assign(form, createDefaultForm());
      codeEditedManually.value = false;
      return;
    }

    if (!appId.value) {
      throw new Error("发布渠道标识无效。");
    }

    const appResponse = await getProjectApp(projectId.value, appId.value);
    applyApp(appResponse);
    codeEditedManually.value = true;
  } catch (error) {
    pageError.value = error;
  } finally {
    pageLoading.value = false;
  }
}

function handleBack() {
  if (!projectId.value) {
    return;
  }

  void router.push(`/projects/${projectId.value}/apps`);
}

function handleCodeInput() {
  codeEditedManually.value = true;
}

function openKnowledgeBaseDialog() {
  tempSelectedKnowledgeBaseIds.value = [...form.knowledge_base_ids];
  kbDialogVisible.value = true;
}

function addKnowledgeBase(knowledgeBaseId: number) {
  if (!tempSelectedKnowledgeBaseIds.value.includes(knowledgeBaseId)) {
    tempSelectedKnowledgeBaseIds.value = [...tempSelectedKnowledgeBaseIds.value, knowledgeBaseId];
  }
}

function removeTemporaryKnowledgeBase(knowledgeBaseId: number) {
  tempSelectedKnowledgeBaseIds.value = tempSelectedKnowledgeBaseIds.value.filter((id) => id !== knowledgeBaseId);
}

function confirmKnowledgeBaseSelection() {
  form.knowledge_base_ids = [...tempSelectedKnowledgeBaseIds.value];
  kbDialogVisible.value = false;
}

function removeKnowledgeBase(knowledgeBaseId: number) {
  form.knowledge_base_ids = form.knowledge_base_ids.filter((id) => id !== knowledgeBaseId);
}

async function handleSave() {
  if (!projectId.value || !formRef.value || saveLoading.value) {
    return;
  }

  const isValid = await formRef.value
    .validate()
    .then(() => true)
    .catch(() => false);

  if (!isValid) {
    return;
  }

  if (form.knowledge_base_ids.length === 0) {
    ElMessage.warning("请至少绑定一个知识库。");
    return;
  }

  const payload = buildPayload();
  saveLoading.value = true;

  try {
    if (isCreateMode.value) {
      const created = await createProjectApp(projectId.value, payload);
      ElMessage.success(`已创建发布渠道“${created.name}”。`);
      void router.replace(`/projects/${projectId.value}/apps/${created.id}`);
      return;
    }

    if (!appId.value) {
      ElMessage.error("缺少发布渠道标识，无法保存。");
      return;
    }

    const updated = await updateProjectApp(projectId.value, appId.value, payload);
    currentApp.value = updated;
    applyApp(updated);
    ElMessage.success(`已保存发布渠道“${updated.name}”。`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "保存发布渠道失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    saveLoading.value = false;
  }
}

async function generatePreview() {
  if (!projectId.value || !appId.value || previewLoading.value) {
    return;
  }

  previewLoading.value = true;
  try {
    const response = await createProjectAppEmbedPreview(projectId.value, appId.value);
    previewEmbedUrl.value = response.embed_url;
    ElMessage.success("已生成嵌入预览链接。");
  } catch (error) {
    const message = error instanceof Error ? error.message : "生成嵌入预览失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    previewLoading.value = false;
  }
}

async function copyPreviewUrl() {
  if (!previewEmbedUrl.value) {
    return;
  }

  try {
    await navigator.clipboard.writeText(previewEmbedUrl.value);
    ElMessage.success("预览链接已复制。");
  } catch {
    ElMessage.error("复制失败，请手动复制。");
  }
}

onMounted(() => {
  void loadPage();
});

watch(
  () => form.name,
  (value) => {
    if (!isCreateMode.value || codeEditedManually.value) {
      return;
    }

    const nextCode = normalizeCode(value);
    if (nextCode) {
      form.code = nextCode;
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
  () => previewEmbedUrl.value,
  () => {
    nextTick(() => {
      // no-op placeholder to keep iframe refresh tied to reactive url updates
    });
  },
);
</script>

<template>
  <section class="project-app-detail-page">
    <header class="project-app-detail-page__header">
      <div class="project-app-detail-page__header-left">
        <button type="button" class="project-app-detail-page__back" @click="handleBack">
          <el-icon><ArrowLeft /></el-icon>
          <span>返回发布渠道列表</span>
        </button>
        <div class="project-app-detail-page__divider" />
        <div class="project-app-detail-page__title-group">
          <h1 class="project-app-detail-page__title">{{ pageTitle }}</h1>
          <span v-if="project" class="project-app-detail-page__meta">{{ project.name }}</span>
          <span v-if="currentApp" class="project-app-detail-page__meta">编码：{{ currentApp.code }}</span>
        </div>
      </div>

      <div class="project-app-detail-page__header-actions">
        <el-tag :type="form.is_active ? 'success' : 'info'" effect="plain" round>
          {{ form.is_active ? "已启用" : "已停用" }}
        </el-tag>
        <el-button @click="handleBack">取消</el-button>
        <el-button type="primary" :loading="saveLoading" @click="handleSave">保存配置</el-button>
      </div>
    </header>

    <AppLoading
      v-if="pageLoading"
      title="发布渠道详情加载中"
      description="正在获取项目、助手、知识库及当前应用配置，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="pageError"
      title="发布渠道详情加载失败"
      description="暂时无法获取当前应用与发布配置，请稍后重试。"
      :error="pageError"
      @retry="loadPage"
    />

    <section v-else class="project-app-detail-page__layout">
      <section class="project-app-panel project-app-panel--form">
        <div class="project-app-panel__header">
          <el-icon><Setting /></el-icon>
          <span>应用编排配置</span>
        </div>

        <div class="project-app-panel__body">
          <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
            <h2 class="project-app-detail-page__section-title">基础信息</h2>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="应用名称" prop="name">
                  <el-input v-model="form.name" maxlength="100" show-word-limit placeholder="例如：官网右下角客服挂件" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="应用编码" prop="code">
                  <el-input
                    v-model="form.code"
                    maxlength="120"
                    show-word-limit
                    placeholder="例如：website_customer_service"
                    @input="handleCodeInput"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="应用说明">
                  <el-input
                    v-model="form.description"
                    type="textarea"
                    :rows="3"
                    maxlength="500"
                    show-word-limit
                    placeholder="描述该发布渠道的接入场景和目标用户"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="服务状态">
                  <el-switch
                    v-model="form.is_active"
                    inline-prompt
                    active-text="启用"
                    inactive-text="停用"
                  />
                </el-form-item>
              </el-col>
            </el-row>

            <h2 class="project-app-detail-page__section-title">绑定助手</h2>
            <el-form-item label="默认助手" prop="default_assistant_id">
              <el-select
                v-model="form.default_assistant_id"
                filterable
                clearable
                placeholder="选择一个助手作为默认对话引擎"
                class="project-app-detail-page__full"
              >
                <el-option
                  v-for="assistant in assistants"
                  :key="assistant.id"
                  :label="assistant.name"
                  :value="assistant.id"
                >
                  <div class="project-app-detail-page__option-row">
                    <span>{{ assistant.name }}</span>
                    <span>{{ assistant.llm_model_key || "未指定模型" }}</span>
                  </div>
                </el-option>
              </el-select>
              <div class="project-app-detail-page__hint">
                当前项目应用层使用已有助手能力，不在这里额外配置提示词或模型参数。
              </div>
            </el-form-item>

            <h2 class="project-app-detail-page__section-title project-app-detail-page__section-title--with-action">
              <span>绑定知识库</span>
              <el-button type="primary" link :icon="Plus" @click="openKnowledgeBaseDialog">
                选择知识库
              </el-button>
            </h2>

            <div v-if="selectedKnowledgeBases.length > 0" class="project-app-detail-page__kb-list">
              <div
                v-for="item in selectedKnowledgeBases"
                :key="item.id"
                class="project-app-detail-page__kb-item"
              >
                <div class="project-app-detail-page__kb-copy">
                  <strong>{{ item.name }}</strong>
                  <span>{{ item.description?.trim() || "暂无说明" }}</span>
                </div>
                <el-button link type="danger" @click="removeKnowledgeBase(item.id)">移除</el-button>
              </div>
            </div>

            <AppEmpty
              v-else
              title="暂未绑定知识库"
              description="当前发布渠道至少需要绑定一个知识库，才能在嵌入端提供 RAG 问答能力。"
            >
              <el-button type="primary" plain @click="openKnowledgeBaseDialog">选择知识库</el-button>
            </AppEmpty>
          </el-form>
        </div>
      </section>

      <section class="project-app-panel project-app-panel--preview">
        <div class="project-app-panel__header">
          <div class="project-app-detail-page__preview-header-main">
            <el-icon><Link /></el-icon>
            <span>嵌入预览</span>
          </div>
          <div v-if="previewEmbedUrl" class="project-app-detail-page__preview-header-actions">
            <el-button size="small" @click="copyPreviewUrl">复制预览链接</el-button>
            <el-button size="small" type="primary" plain @click="generatePreview">
              刷新预览链接
            </el-button>
          </div>
        </div>

        <div class="project-app-detail-page__preview-body">
          <template v-if="previewEmbedUrl">
            <iframe
              :src="previewEmbedUrl"
              title="嵌入预览"
              class="project-app-detail-page__iframe"
            />
          </template>

          <template v-else-if="canGeneratePreview">
            <AppEmpty
              title="尚未生成嵌入预览"
              description="当前应用已保存并启用，可以生成一个短时有效的嵌入预览链接。"
            >
              <el-button type="primary" :loading="previewLoading" @click="generatePreview">
                生成嵌入预览
              </el-button>
            </AppEmpty>
          </template>

          <template v-else>
            <AppEmpty
              title="当前无法生成预览"
              description="请先保存当前应用；若应用处于停用状态，也无法生成嵌入预览。"
            />
          </template>
        </div>
      </section>
    </section>

    <el-dialog
      v-model="kbDialogVisible"
      title="选择知识库"
      width="760px"
      destroy-on-close
    >
      <div class="project-app-detail-page__kb-dialog">
        <section class="project-app-detail-page__kb-panel">
          <header class="project-app-detail-page__kb-panel-header">可选知识库</header>
          <div class="project-app-detail-page__kb-panel-body">
            <div
              v-for="item in availableKnowledgeBases"
              :key="item.id"
              class="project-app-detail-page__kb-pick-item"
            >
              <div class="project-app-detail-page__kb-copy">
                <strong>{{ item.name }}</strong>
                <span>{{ item.description?.trim() || "暂无说明" }}</span>
              </div>
              <el-button type="primary" link @click="addKnowledgeBase(item.id)">添加</el-button>
            </div>
          </div>
        </section>

        <section class="project-app-detail-page__kb-panel">
          <header class="project-app-detail-page__kb-panel-header">已选知识库</header>
          <div class="project-app-detail-page__kb-panel-body">
            <div
              v-for="item in temporarySelectedKnowledgeBases"
              :key="item.id"
              class="project-app-detail-page__kb-pick-item"
            >
              <div class="project-app-detail-page__kb-copy">
                <strong>{{ item.name }}</strong>
                <span>{{ item.description?.trim() || "暂无说明" }}</span>
              </div>
              <el-button link type="danger" @click="removeTemporaryKnowledgeBase(item.id)">移除</el-button>
            </div>

            <div
              v-if="temporarySelectedKnowledgeBases.length === 0"
              class="project-app-detail-page__kb-empty"
            >
              暂未选择知识库
            </div>
          </div>
        </section>
      </div>

      <template #footer>
        <div class="project-app-detail-page__dialog-footer">
          <el-button @click="kbDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmKnowledgeBaseSelection">确认绑定</el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.project-app-detail-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
}

.project-app-detail-page__header {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 56px;
  border: 1px solid #dbe2ea;
  border-radius: 12px;
  background: #ffffff;
  padding: 0 16px;
}

.project-app-detail-page__header-left,
.project-app-detail-page__header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.project-app-detail-page__back {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  color: #475569;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  padding: 0;
}

.project-app-detail-page__back:hover {
  color: #2563eb;
}

.project-app-detail-page__divider {
  width: 1px;
  height: 20px;
  background: #e2e8f0;
}

.project-app-detail-page__title-group {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.project-app-detail-page__title {
  margin: 0;
  color: #0f172a;
  font-size: 16px;
  font-weight: 600;
}

.project-app-detail-page__meta {
  color: #64748b;
  font-size: 13px;
  white-space: nowrap;
}

.project-app-detail-page__layout {
  display: grid;
  flex: 1;
  min-height: 0;
  grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.95fr);
  gap: 20px;
  overflow: hidden;
}

.project-app-panel {
  display: flex;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #dbe2ea;
  border-radius: 20px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.project-app-panel__header {
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid #f1f5f9;
  background: #fafafa;
  color: #334155;
  font-size: 14px;
  font-weight: 600;
  padding: 14px 18px;
}

.project-app-panel__body {
  flex: 1;
  overflow-y: auto;
  padding: 18px;
}

.project-app-detail-page__section-title {
  margin: 0 0 16px;
  border-bottom: 1px solid #e5e7eb;
  color: #111827;
  font-size: 14px;
  font-weight: 700;
  padding-bottom: 8px;
}

.project-app-detail-page__section-title--with-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.project-app-detail-page__section-title:not(:first-child) {
  margin-top: 8px;
}

.project-app-detail-page__full {
  width: 100%;
}

.project-app-detail-page__hint {
  margin-top: 6px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.project-app-detail-page__option-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.project-app-detail-page__option-row span:last-child {
  color: #94a3b8;
  font-size: 12px;
}

.project-app-detail-page__kb-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.project-app-detail-page__kb-item,
.project-app-detail-page__kb-pick-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
  padding: 12px 14px;
}

.project-app-detail-page__kb-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.project-app-detail-page__kb-copy strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-app-detail-page__kb-copy span {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.project-app-panel--preview {
  background: #f8fafc;
}

.project-app-detail-page__preview-header-main {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.project-app-detail-page__preview-header-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.project-app-detail-page__preview-body {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  padding: 16px;
}

.project-app-detail-page__iframe {
  flex: 1;
  width: 100%;
  min-height: 0;
  border: 1px solid #dbe2ea;
  border-radius: 16px;
  background: #ffffff;
}

.project-app-detail-page__kb-dialog {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
}

.project-app-detail-page__kb-panel {
  display: flex;
  min-height: 420px;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #dbe2ea;
  border-radius: 16px;
  background: #ffffff;
}

.project-app-detail-page__kb-panel-header {
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
  padding: 12px 14px;
}

.project-app-detail-page__kb-panel-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  padding: 12px;
}

.project-app-detail-page__kb-empty {
  margin: auto;
  color: #94a3b8;
  font-size: 13px;
}

.project-app-detail-page__dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 1280px) {
  .project-app-detail-page__layout {
    grid-template-columns: 1fr;
    overflow: auto;
  }

  .project-app-panel--preview {
    min-height: 560px;
  }
}

@media (max-width: 900px) {
  .project-app-detail-page {
    overflow: auto;
  }

  .project-app-detail-page__header,
  .project-app-detail-page__header-left,
  .project-app-detail-page__header-actions,
  .project-app-detail-page__title-group {
    flex-direction: column;
    align-items: stretch;
  }

  .project-app-detail-page__layout {
    display: flex;
    flex-direction: column;
    overflow: visible;
  }

  .project-app-detail-page__kb-dialog {
    grid-template-columns: 1fr;
  }
}
</style>
