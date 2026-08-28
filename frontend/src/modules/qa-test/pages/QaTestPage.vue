<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import DOMPurify from "dompurify";
import MarkdownIt from "markdown-it";
import {
  ChatDotRound,
  Collection,
  Delete,
  MagicStick,
  Monitor,
  Position,
  Search,
} from "@element-plus/icons-vue";

import { listAssistants } from "@/shared/api/assistants";
import { listKnowledgeBases } from "@/shared/api/knowledge-bases";
import type { AssistantSummary } from "@/shared/types/assistant";
import type { KnowledgeBaseListItem } from "@/shared/types/knowledge-base";
import { useTeamScopeStore } from "@/stores/team-scope";
import { streamQa } from "@/modules/qa-test/api";
import type { SseEnvelope } from "@/shared/lib/stream/sse";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";

interface Citation {
  title: string;
  section: string;
  content: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  answerStatus?: string;
}

type ChatScrollBehavior = "auto" | "smooth" | "instant";

const teamScopeStore = useTeamScopeStore();
const chatContainerRef = ref<HTMLElement | null>(null);
const pageLoading = ref(false);
const previewLoading = ref(false);
const pageError = ref<unknown>(null);
const assistants = ref<AssistantSummary[]>([]);
const knowledgeBases = ref<KnowledgeBaseListItem[]>([]);
const messages = ref<ChatMessage[]>([]);
const userInput = ref("");
const citationDrawerVisible = ref(false);
const activeCitations = ref<Citation[]>([]);
const activeAnswerStatus = ref<string | null>(null);
const streamAbortController = ref<AbortController | null>(null);
const markdown = new MarkdownIt({ breaks: true, linkify: true });

const context = reactive({
  assistantId: null as number | null,
  knowledgeBaseId: null as number | null,
  includeUnpublished: true,
});

const selectedAssistant = computed(() =>
  assistants.value.find((item) => item.id === context.assistantId) ?? null,
);
const canPreview = computed(
  () =>
    Boolean(teamScopeStore.selectedTeamId) &&
    Boolean(context.knowledgeBaseId) &&
    Boolean(userInput.value.trim()) &&
    !previewLoading.value,
);
const suggestions = computed(() => selectedAssistant.value?.suggested_prompts?.slice(0, 4) ?? []);

function normalizeCitation(value: Record<string, unknown>, index: number): Citation {
  const metadata = value.metadata && typeof value.metadata === "object"
    ? (value.metadata as Record<string, unknown>)
    : {};

  return {
    title: String(
      metadata.document_title ?? metadata.title ?? metadata.source_name ?? `引用片段 ${index + 1}`,
    ),
    section: String(metadata.section_path ?? metadata.section ?? metadata.file_name ?? "知识库内容"),
    content: String(value.content ?? "").trim(),
  };
}

function normalizeCitations(value: unknown) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map(normalizeCitation);
}

function renderMarkdown(value: string) {
  return DOMPurify.sanitize(markdown.render(value || ""));
}

function scrollChatToBottom(behavior: ChatScrollBehavior = "smooth") {
  void nextTick(() => {
    chatContainerRef.value?.scrollTo({
      top: chatContainerRef.value.scrollHeight,
      behavior,
    });
  });
}

function resetSelection() {
  context.assistantId = assistants.value[0]?.id ?? null;
  context.knowledgeBaseId = knowledgeBases.value[0]?.id ?? null;
}

async function loadContext() {
  pageError.value = null;
  const teamId = teamScopeStore.selectedTeamId;
  if (!teamId) {
    assistants.value = [];
    knowledgeBases.value = [];
    resetSelection();
    return;
  }

  pageLoading.value = true;
  try {
    const [assistantResult, knowledgeBaseResult] = await Promise.all([
      listAssistants({ team_id: teamId, active_only: true, page: 1, page_size: 100 }),
      listKnowledgeBases({ team_id: teamId, active_only: true, page: 1, page_size: 100 }),
    ]);
    assistants.value = assistantResult.items;
    knowledgeBases.value = knowledgeBaseResult.items;
    resetSelection();
  } catch (error) {
    pageError.value = error;
  } finally {
    pageLoading.value = false;
  }
}

function clearConversation() {
  streamAbortController.value?.abort();
  streamAbortController.value = null;
  messages.value = [];
  activeCitations.value = [];
  activeAnswerStatus.value = null;
  citationDrawerVisible.value = false;
}

function useSuggestion(value: string) {
  userInput.value = value;
  void handlePreview();
}

function openCitations(message: ChatMessage) {
  activeCitations.value = message.citations ?? [];
  activeAnswerStatus.value = message.answerStatus ?? null;
  citationDrawerVisible.value = true;
}

function answerStatusLabel(value: string | null) {
  const labels: Record<string, string> = {
    answered: "已回答",
    partial: "部分回答",
    insufficient: "依据不足",
    blocked: "已拦截",
  };
  return value ? labels[value] ?? value : "暂无状态";
}

async function handlePreview() {
  const query = userInput.value.trim();
  const teamId = teamScopeStore.selectedTeamId;
  if (!teamId || !context.knowledgeBaseId || !query || previewLoading.value) {
    if (!teamId) ElMessage.warning("请先选择团队。");
    else if (!context.knowledgeBaseId) ElMessage.warning("请先选择知识库。");
    return;
  }

  messages.value.push({ role: "user", content: query });
  const assistantMessageIndex = messages.value.length;
  messages.value.push({ role: "assistant", content: "" });
  userInput.value = "";
  previewLoading.value = true;
  const controller = new AbortController();
  streamAbortController.value = controller;
  scrollChatToBottom();

  try {
    let streamError: Error | null = null;
    await streamQa({
      query,
      team_id: teamId,
      knowledge_base_id: context.knowledgeBaseId,
      assistant_id: context.assistantId,
      include_unpublished: context.includeUnpublished,
    }, (event: SseEnvelope) => {
      const message = messages.value[assistantMessageIndex];
      if (!message) {
        return;
      }

      const data = event.data as Record<string, unknown>;
      if (event.type === "token" && typeof data.text === "string") {
        message.content += data.text;
        scrollChatToBottom("auto");
        return;
      }

      if (event.type === "retrieved") {
        message.citations = normalizeCitations(data.retrieved_docs);
        return;
      }

      if (event.type === "complete") {
        const answer = data.answer_text ?? data.answer;
        if (typeof answer === "string" && answer.trim()) {
          message.content = answer;
        }
        message.answerStatus = typeof data.answer_status === "string" ? data.answer_status : undefined;
        const citations = normalizeCitations(data.retrieved_docs);
        if (citations.length > 0) {
          message.citations = citations;
        }
        scrollChatToBottom();
        return;
      }

      if (event.type === "error") {
        const errorMessage = typeof data.message === "string" ? data.message : "测试请求失败。";
        streamError = new Error(errorMessage);
      }
    }, controller.signal);

    if (controller.signal.aborted) {
      return;
    }
    if (streamError) {
      throw streamError;
    }
    if (!messages.value[assistantMessageIndex]?.content) {
      messages.value[assistantMessageIndex].content = "预览接口未返回回答。";
    }
  } catch (error) {
    if (controller.signal.aborted) {
      return;
    }
    ElMessage.error(error instanceof Error ? error.message : "测试请求失败，请稍后重试。");
  } finally {
    previewLoading.value = false;
    if (streamAbortController.value === controller) {
      streamAbortController.value = null;
    }
  }
}

onMounted(async () => {
  await teamScopeStore.bootstrap();
  await loadContext();
});

watch(
  () => teamScopeStore.selectedTeamId,
  () => {
    clearConversation();
    void loadContext();
  },
);

watch(
  () => context.knowledgeBaseId,
  (knowledgeBaseId, previousKnowledgeBaseId) => {
    if (knowledgeBaseId !== previousKnowledgeBaseId) {
      clearConversation();
    }
  },
);
</script>

<template>
  <section class="qa-test-page">
    <div class="qa-test-page__header">
      <div class="qa-test-page__brand">
        <span class="qa-test-page__brand-icon"><el-icon><ChatDotRound /></el-icon></span>
        <span class="qa-test-page__brand-title">问答测试台</span>
      </div>

      <div class="qa-test-page__context-bar">
        <div class="qa-test-page__context-item">
          <span>助手</span>
          <el-select v-model="context.assistantId" placeholder="选择助手" clearable>
            <template #prefix><el-icon><MagicStick /></el-icon></template>
            <el-option
              v-for="item in assistants"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </div>
        <div class="qa-test-page__context-item qa-test-page__context-item--wide">
          <span>知识库</span>
          <el-select v-model="context.knowledgeBaseId" placeholder="选择知识库" clearable>
            <template #prefix><el-icon><Collection /></el-icon></template>
            <el-option
              v-for="item in knowledgeBases"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </div>
      </div>

      <div class="qa-test-page__header-actions">
        <el-button @click="clearConversation">
          <el-icon><Delete /></el-icon>
          清空对话
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="!teamScopeStore.selectedTeamId"
      title="请先在顶部选择团队，再开始测试。"
      type="warning"
      :closable="false"
      show-icon
    />

    <AppLoading
      v-if="pageLoading"
      title="测试上下文加载中"
      description="正在准备助手和知识库。"
      :blocks="3"
    />

    <AppError
      v-else-if="pageError"
      title="测试上下文加载失败"
      description="暂时无法获取可测试的助手和知识库。"
      :error="pageError"
      @retry="loadContext"
    />

    <section v-else class="qa-test-page__workspace">
      <section class="qa-test-page__chat-panel">
        <div ref="chatContainerRef" class="qa-test-page__messages">
          <div v-if="messages.length === 0" class="qa-test-page__welcome">
            <div class="qa-test-page__welcome-icon"><el-icon><ChatDotRound /></el-icon></div>
            <h2>开始测试问答效果</h2>
            <p>从推荐问题开始，或直接在下方输入你的问题。</p>
            <div v-if="suggestions.length > 0" class="qa-test-page__suggestions">
              <el-button
                v-for="item in suggestions"
                :key="item"
                plain
                @click="useSuggestion(item)"
              >
                {{ item }}
                <el-icon><Position /></el-icon>
              </el-button>
            </div>
          </div>

          <div
            v-for="(message, index) in messages"
            :key="`${message.role}-${index}`"
            class="qa-test-page__message"
            :class="`qa-test-page__message--${message.role}`"
          >
            <div v-if="message.role === 'assistant'" class="qa-test-page__avatar">
              <el-icon><Monitor /></el-icon>
            </div>
            <div
              v-if="message.role === 'user' || message.content || (previewLoading && index === messages.length - 1)"
              class="qa-test-page__bubble"
            >
              <template v-if="message.role === 'assistant'">
                <!-- Markdown 已经过 DOMPurify 清洗。 -->
                <!-- eslint-disable vue/no-v-html -->
                <div
                  v-if="message.content"
                  class="qa-test-page__markdown"
                  v-html="renderMarkdown(message.content)"
                />
                <!-- eslint-enable vue/no-v-html -->
                <div v-else class="qa-test-page__bubble-loading">
                  正在生成回答<span class="qa-test-page__cursor" aria-hidden="true" />
                </div>
              </template>
              <div v-else class="qa-test-page__user-text">{{ message.content }}</div>
              <div
                v-if="message.role === 'assistant' && message.citations?.length"
                class="qa-test-page__answer-actions"
              >
                <el-button link type="primary" @click="openCitations(message)">
                  引用 {{ message.citations.length }} 条
                  <el-icon><Search /></el-icon>
                </el-button>
                <span>回答完成</span>
              </div>
            </div>
          </div>
        </div>

        <div class="qa-test-page__composer">
          <el-input
            v-model="userInput"
            type="textarea"
            :rows="3"
            resize="none"
            :disabled="previewLoading"
            placeholder="输入问题测试知识库回答，Enter 发送，Shift + Enter 换行"
            @keydown.enter.exact.prevent="handlePreview"
          />
          <div class="qa-test-page__composer-footer">
            <span>Enter 发送，Shift + Enter 换行</span>
            <span>{{ userInput.length }} / 1000</span>
            <el-button type="primary" :loading="previewLoading" :disabled="!canPreview" @click="handlePreview">
              <el-icon><Position /></el-icon>
              发送
            </el-button>
          </div>
        </div>
      </section>
    </section>

    <el-drawer v-model="citationDrawerVisible" title="检索引用" size="380px">
      <div class="qa-test-page__drawer-summary">
        <span>本次回答引用 {{ activeCitations.length }} 条知识库内容</span>
        <el-tag v-if="activeAnswerStatus" size="small" effect="plain">
          {{ answerStatusLabel(activeAnswerStatus) }}
        </el-tag>
      </div>
      <div class="qa-test-page__citation-list">
        <article v-for="(citation, index) in activeCitations" :key="`${citation.title}-${index}`" class="qa-test-page__citation">
          <div class="qa-test-page__citation-title">
            <span>{{ index + 1 }}</span>
            <strong>{{ citation.title }}</strong>
          </div>
          <div class="qa-test-page__citation-section">{{ citation.section }}</div>
          <p>{{ citation.content || "暂无引用片段内容。" }}</p>
        </article>
      </div>
    </el-drawer>
  </section>
</template>

<style scoped>
.qa-test-page {
  display: flex;
  min-height: calc(100% + 48px);
  margin: -24px;
  flex-direction: column;
  overflow: hidden;
  background: var(--admin-bg, #f7f9fc);
}

.qa-test-page__header {
  display: flex;
  min-height: 64px;
  flex: 0 0 64px;
  align-items: center;
  gap: 28px;
  border-bottom: 1px solid var(--admin-border-soft, #e3e8f0);
  background: var(--admin-surface, #fff);
  padding: 0 24px;
}

.qa-test-page__brand {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 12px;
}

.qa-test-page__brand-icon {
  display: flex;
  width: 32px;
  height: 32px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--admin-primary, #2563eb);
  color: #fff;
  font-size: 18px;
}

.qa-test-page__brand-title {
  color: var(--admin-text-primary, #172033);
  font-size: 19px;
  font-weight: 700;
  white-space: nowrap;
}

.qa-test-page__context-bar {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 24px;
}

.qa-test-page__context-item {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 9px;
}

.qa-test-page__context-item > span {
  flex-shrink: 0;
  color: var(--admin-text-secondary, #46536a);
  font-size: 13px;
  font-weight: 600;
}

.qa-test-page__context-item :deep(.el-select) {
  width: 230px;
}

.qa-test-page__context-item--wide {
  flex-shrink: 0;
}

.qa-test-page__header-actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  margin-left: auto;
}

.qa-test-page__header-actions :deep(.el-button) {
  border: 0;
  background: transparent;
  color: var(--admin-text-secondary, #46536a);
  font-size: 13px;
}

.qa-test-page__header-actions :deep(.el-button:hover) {
  background: var(--admin-surface-muted, #f3f6fa);
  color: var(--admin-text-primary, #172033);
}

.qa-test-page__workspace,
.qa-test-page__chat-panel {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  background: transparent;
}

.qa-test-page__messages {
  width: min(880px, calc(100% - 48px));
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin: 0 auto;
  padding: 30px 0 24px;
}

.qa-test-page__welcome {
  display: flex;
  min-height: 420px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.qa-test-page__welcome-icon {
  display: flex;
  width: 48px;
  height: 48px;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--admin-primary-border);
  border-radius: 14px;
  background: var(--admin-primary-soft);
  color: var(--admin-primary);
  font-size: 24px;
}

.qa-test-page__welcome h2 {
  margin: 16px 0 0;
  color: var(--admin-text-primary);
  font-size: 20px;
}

.qa-test-page__welcome p {
  margin: 8px 0 0;
  color: var(--admin-text-muted);
  font-size: 13px;
}

.qa-test-page__suggestions {
  display: grid;
  width: min(520px, 100%);
  gap: 8px;
  margin-top: 22px;
}

.qa-test-page__suggestions :deep(.el-button) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0;
  border-color: var(--admin-primary-border);
  background: var(--admin-primary-soft);
  color: var(--admin-primary);
  text-align: left;
}

.qa-test-page__message {
  display: flex;
  width: 100%;
  gap: 10px;
  margin-bottom: 18px;
  align-items: flex-start;
}

.qa-test-page__message--user {
  justify-content: flex-end;
}

.qa-test-page__avatar {
  display: flex;
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--admin-primary, #2563eb);
  color: #fff;
  font-size: 17px;
}

.qa-test-page__bubble {
  max-width: min(700px, calc(100% - 44px));
  border: 1px solid var(--admin-border-soft, #dfe5ef);
  border-radius: 10px;
  background: var(--admin-surface, #fff);
  padding: 15px 17px;
  color: var(--admin-text-secondary, #334155);
  font-size: 14px;
  line-height: 1.75;
}

.qa-test-page__message--user .qa-test-page__bubble {
  max-width: min(360px, 78%);
  border-color: var(--admin-primary-border, #c7dbff);
  background: #eaf2ff;
  color: var(--admin-primary-strong, #174ea6);
  padding: 12px 16px;
}

.qa-test-page__user-text {
  white-space: pre-wrap;
}

.qa-test-page__bubble-loading {
  color: var(--admin-text-secondary, #46536a);
  white-space: nowrap;
}

.qa-test-page__cursor {
  display: inline-block;
  width: 2px;
  height: 16px;
  margin-left: 5px;
  vertical-align: -3px;
  animation: qa-test-cursor 1s step-end infinite;
  background: var(--admin-primary, #2563eb);
}

.qa-test-page__markdown :deep(p),
.qa-test-page__markdown :deep(ul),
.qa-test-page__markdown :deep(ol),
.qa-test-page__markdown :deep(pre),
.qa-test-page__markdown :deep(blockquote),
.qa-test-page__markdown :deep(table) {
  margin: 0;
}

.qa-test-page__markdown :deep(* + p),
.qa-test-page__markdown :deep(* + ul),
.qa-test-page__markdown :deep(* + ol),
.qa-test-page__markdown :deep(* + pre),
.qa-test-page__markdown :deep(* + blockquote),
.qa-test-page__markdown :deep(* + table) {
  margin-top: 9px;
}

.qa-test-page__markdown :deep(ul),
.qa-test-page__markdown :deep(ol) {
  padding-left: 20px;
}

.qa-test-page__markdown :deep(a) {
  color: var(--admin-primary);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.qa-test-page__markdown :deep(code) {
  border-radius: 4px;
  background: var(--admin-primary-soft);
  padding: 2px 5px;
  font-family: Consolas, monospace;
  font-size: 12px;
}

.qa-test-page__markdown :deep(pre) {
  overflow-x: auto;
  border-radius: 8px;
  background: #172033;
  padding: 11px 12px;
  color: #e5efff;
}

.qa-test-page__markdown :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.qa-test-page__markdown :deep(blockquote) {
  border-left: 3px solid var(--admin-primary-light);
  background: var(--admin-primary-soft);
  padding: 8px 11px;
  color: var(--admin-text-secondary);
}

.qa-test-page__markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.qa-test-page__markdown :deep(th),
.qa-test-page__markdown :deep(td) {
  border: 1px solid var(--admin-border);
  padding: 7px 8px;
  text-align: left;
}

.qa-test-page__markdown :deep(th) {
  background: var(--admin-surface-muted);
}

.qa-test-page__answer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 13px;
  border-top: 1px solid var(--admin-border-soft, #e7ebf2);
  padding-top: 8px;
  color: var(--admin-text-subtle, #7b879a);
  font-size: 12px;
}

.qa-test-page__answer-actions :deep(.el-button) {
  margin-left: -10px;
  color: var(--admin-primary, #2563eb);
  font-size: 12px;
}

.qa-test-page__composer {
  width: min(876px, calc(100% - 48px));
  flex-shrink: 0;
  margin: 0 auto 24px;
  border: 1px solid var(--admin-border-soft, #dfe5ef);
  border-radius: 10px;
  background: var(--admin-surface, #fff);
  padding: 12px 14px 10px;
}

.qa-test-page__composer :deep(.el-textarea__inner) {
  border: 0;
  box-shadow: none;
  padding: 7px 0;
}

.qa-test-page__composer-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}

.qa-test-page__composer-footer > span {
  color: var(--admin-text-subtle, #8792a5);
  font-size: 12px;
}

.qa-test-page__composer-footer > span:first-child {
  margin-right: auto;
}

.qa-test-page__composer-footer :deep(.el-button) {
  min-width: 82px;
  border-radius: 7px;
}

.qa-test-page__drawer-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--admin-text-muted);
  font-size: 12px;
}

.qa-test-page__citation-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
}

.qa-test-page__citation {
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-md);
  padding: 12px;
}

.qa-test-page__citation-title {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  color: var(--admin-text-primary);
  font-size: 13px;
}

.qa-test-page__citation-title > span {
  display: inline-flex;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 5px;
  background: var(--admin-primary);
  color: #fff;
  font-size: 11px;
}

.qa-test-page__citation-section {
  margin: 8px 0;
  color: var(--admin-text-subtle);
  font-size: 12px;
}

.qa-test-page__citation p {
  display: -webkit-box;
  overflow: hidden;
  margin: 0;
  color: var(--admin-text-secondary);
  font-size: 12px;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 5;
}

@keyframes qa-test-cursor {
  0%,
  49% {
    opacity: 1;
  }
  50%,
  100% {
    opacity: 0;
  }
}

@media (max-width: 900px) {
  .qa-test-page__header {
    gap: 16px;
    padding: 0 16px;
  }

  .qa-test-page__brand-title {
    display: none;
  }

  .qa-test-page__context-bar {
    gap: 12px;
  }

  .qa-test-page__context-item :deep(.el-select) {
    width: min(220px, 28vw);
  }

  .qa-test-page__messages,
  .qa-test-page__composer {
    width: min(100% - 32px, 880px);
  }
}

@media (max-width: 640px) {
  .qa-test-page__header {
    min-height: auto;
    flex-wrap: wrap;
    padding-top: 12px;
    padding-bottom: 12px;
  }

  .qa-test-page__context-bar {
    order: 3;
    width: 100%;
    flex-basis: 100%;
    flex-direction: column;
    align-items: stretch;
  }

  .qa-test-page__context-item {
    justify-content: space-between;
  }

  .qa-test-page__context-item :deep(.el-select) {
    width: min(240px, 70vw);
  }

  .qa-test-page__header-actions :deep(.el-button) {
    padding-right: 0;
    padding-left: 0;
  }

  .qa-test-page__messages {
    width: calc(100% - 24px);
    padding-top: 20px;
  }

  .qa-test-page__composer {
    width: calc(100% - 24px);
    margin-bottom: 12px;
  }

  .qa-test-page__bubble {
    max-width: calc(100% - 44px);
  }

  .qa-test-page__message--user .qa-test-page__bubble {
    max-width: 82%;
  }
}
</style>
