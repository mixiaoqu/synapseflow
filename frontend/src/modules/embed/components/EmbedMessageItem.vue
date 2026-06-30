<script setup lang="ts">
import { computed, ref } from "vue";
import DOMPurify from "dompurify";
import MarkdownIt from "markdown-it";
import { ChatDotRound, Check, CopyDocument, Document, User } from "@element-plus/icons-vue";
import EmbedFeedbackActions from "@/modules/embed/components/EmbedFeedbackActions.vue";

interface RetrievedDoc {
  content?: string;
  metadata?: Record<string, unknown>;
}

function getDocTitle(doc: RetrievedDoc): string {
  const title = doc.metadata?.document_title;
  if (typeof title === "string" && title.trim()) {
    return title.trim();
  }

  const sourcePath = doc.metadata?.source_path;
  if (typeof sourcePath === "string" && sourcePath.trim()) {
    return sourcePath.split(/[\\/]/).filter(Boolean).pop() || sourcePath;
  }

  return "知识库片段";
}

export interface EmbedRenderableMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  kind?: "normal" | "welcome" | "streaming";
  logId?: number | null;
  retrievedDocs?: RetrievedDoc[];
  feedbackValue?: "helpful" | "not_helpful" | null;
  feedbackSubmitting?: boolean;
}

const props = defineProps<{
  message: EmbedRenderableMessage;
  assistantName: string;
  isTyping?: boolean;
}>();

const emit = defineEmits<{
  feedback: [value: "helpful" | "not_helpful"];
}>();

const markdownRenderer = new MarkdownIt({
  breaks: true,
  linkify: true,
});

const AI_SUGGESTION_PREFIX = "🤖 AI智能客服建议（由AI生成）：";

const displayContent = computed(() => {
  if (
    props.message.role !== "assistant" ||
    props.message.kind === "welcome" ||
    !props.message.content.trim()
  ) {
    return props.message.content;
  }

  if (props.message.content.trimStart().startsWith(AI_SUGGESTION_PREFIX)) {
    return props.message.content;
  }

  return `${AI_SUGGESTION_PREFIX}\n\n${props.message.content}`;
});

const renderedHtml = computed(() => {
  if (!displayContent.value) {
    return "";
  }

  const rawHtml = markdownRenderer.render(displayContent.value);
  return DOMPurify.sanitize(rawHtml);
});

const copied = ref(false);

async function handleCopy() {
  if (!props.message.content) {
    return;
  }

  try {
    await navigator.clipboard.writeText(displayContent.value);
    copied.value = true;
    window.setTimeout(() => {
      copied.value = false;
    }, 1200);
  } catch {
    copied.value = false;
  }
}
</script>

<template>
  <div :class="['embed-message-item', `is-${message.role}`, `is-${message.kind ?? 'normal'}`]">
    <div :class="['embed-message-item__avatar', `is-${message.role}`]">
      <el-icon v-if="message.role === 'assistant'"><ChatDotRound /></el-icon>
      <el-icon v-else><User /></el-icon>
    </div>

    <div class="embed-message-item__body">
      <div v-if="message.role === 'assistant'" class="embed-message-item__role">
        {{ message.role === "assistant" ? assistantName : "我" }}
      </div>

      <article :class="['embed-message-item__bubble', `is-${message.role}`, `is-${message.kind ?? 'normal'}`]">
        <button
          v-if="message.role === 'assistant' && message.content"
          type="button"
          class="embed-message-item__copy-button"
          :class="{ 'is-copied': copied }"
          :title="copied ? '已复制' : '复制回答'"
          :aria-label="copied ? '已复制' : '复制回答'"
          @click="handleCopy"
        >
          <el-icon v-if="copied"><Check /></el-icon>
          <el-icon v-else><CopyDocument /></el-icon>
        </button>

        <div v-if="message.kind === 'streaming'" class="embed-message-item__streaming">
          <div class="embed-message-item__typing-indicator">
            <span class="dot" />
            <span class="dot" />
            <span class="dot" />
          </div>
          <span>正在生成回答...</span>
        </div>
        <div
          v-else
          class="embed-message-item__content markdown-body"
          v-html="renderedHtml"
        />
      </article>

      <div
        v-if="
          message.role === 'assistant' &&
          message.kind !== 'streaming' &&
          message.kind !== 'welcome' &&
          ((message.retrievedDocs && message.retrievedDocs.length > 0) || message.logId)
        "
        class="embed-message-item__meta"
      >
        <div
          v-if="message.retrievedDocs && message.retrievedDocs.length > 0"
          class="embed-message-item__citations"
        >
          <div class="embed-message-item__citation-list">
            <div
              v-for="(doc, index) in message.retrievedDocs.slice(0, 4)"
              :key="`${message.id}-doc-${index}`"
              class="embed-message-item__citation-chip"
              :title="getDocTitle(doc)"
            >
              <el-icon><Document /></el-icon>
              <span>{{ getDocTitle(doc) }}</span>
            </div>
            <div
              v-if="message.retrievedDocs.length > 4"
              class="embed-message-item__citation-chip is-more"
              :title="`还有 ${message.retrievedDocs.length - 4} 个参考来源`"
            >
              +{{ message.retrievedDocs.length - 4 }}
            </div>
          </div>
        </div>

        <div
          v-if="message.logId"
          class="embed-message-item__feedback-wrap"
        >
          <EmbedFeedbackActions
            :value="message.feedbackValue ?? null"
            :loading="message.feedbackSubmitting"
            :disabled="isTyping || !!message.feedbackValue"
            @submit="emit('feedback', $event)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.embed-message-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
}

.embed-message-item.is-user {
  justify-content: flex-end;
}

.embed-message-item__avatar {
  display: inline-flex;
  width: 32px;
  height: 32px;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  flex-shrink: 0;
  margin-top: 2px;
}

.embed-message-item__avatar.is-assistant {
  background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%);
  color: #ffffff;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.18);
}

.embed-message-item__avatar.is-user {
  background: #e2e8f0;
  color: #334155;
}

.embed-message-item.is-user .embed-message-item__avatar {
  order: 2;
}

.embed-message-item__body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.embed-message-item.is-user .embed-message-item__body {
  align-items: flex-end;
  max-width: min(62%, 420px);
}

.embed-message-item.is-assistant .embed-message-item__body {
  align-items: flex-start;
  width: min(86%, 720px);
  max-width: min(86%, 720px);
}

.embed-message-item__bubble {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.embed-message-item__bubble.is-user {
  width: fit-content;
  max-width: 100%;
  padding: 10px 14px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: #ffffff;
  border-radius: 18px 18px 6px 18px;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.16);
}

.embed-message-item__bubble.is-assistant {
  position: relative;
  padding: 16px 18px;
  width: 100%;
  background: rgba(255, 255, 255, 0.96);
  color: #1e293b;
  border: 1px solid #e2e8f0;
  border-radius: 18px 18px 18px 6px;
  box-shadow:
    0 10px 28px rgba(15, 23, 42, 0.05),
    0 1px 3px rgba(15, 23, 42, 0.03);
}

.embed-message-item__bubble.is-welcome {
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  border-color: #dbeafe;
  box-shadow:
    0 12px 30px rgba(37, 99, 235, 0.06),
    0 1px 3px rgba(15, 23, 42, 0.03);
}

.embed-message-item__role {
  font-size: 12px;
  line-height: 1;
  padding: 0 2px;
}

.embed-message-item__copy-button {
  position: absolute;
  right: 10px;
  bottom: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
  color: #94a3b8;
  cursor: pointer;
  opacity: 0;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
}

.embed-message-item__bubble.is-assistant:hover .embed-message-item__copy-button,
.embed-message-item__copy-button:focus-visible,
.embed-message-item__copy-button.is-copied {
  opacity: 1;
}

.embed-message-item__copy-button:hover {
  border-color: #cbd5e1;
  color: #475569;
  background: #f8fafc;
}

.embed-message-item__copy-button.is-copied {
  border-color: #bbf7d0;
  color: #16a34a;
  background: #f0fdf4;
}

.embed-message-item.is-assistant .embed-message-item__role {
  color: #2563eb;
  font-weight: 600;
  opacity: 0.95;
}

.embed-message-item__content {
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.markdown-body :deep(*) {
  box-sizing: border-box;
}

.markdown-body :deep(p),
.markdown-body :deep(ul),
.markdown-body :deep(ol),
.markdown-body :deep(pre),
.markdown-body :deep(blockquote),
.markdown-body :deep(table) {
  margin: 0;
}

.markdown-body :deep(* + p),
.markdown-body :deep(* + ul),
.markdown-body :deep(* + ol),
.markdown-body :deep(* + pre),
.markdown-body :deep(* + blockquote),
.markdown-body :deep(* + table) {
  margin-top: 10px;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 20px;
}

.markdown-body :deep(li + li) {
  margin-top: 4px;
}

.markdown-body :deep(a) {
  color: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.markdown-body :deep(strong) {
  font-weight: 600;
}

.markdown-body :deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(148, 163, 184, 0.16);
  font-size: 13px;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
}

.markdown-body :deep(pre) {
  overflow-x: auto;
  padding: 12px 14px;
  border-radius: 12px;
  background: #0f172a;
  color: #e2e8f0;
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
}

.markdown-body :deep(blockquote) {
  padding: 10px 12px;
  border-left: 3px solid #93c5fd;
  border-radius: 0 10px 10px 0;
  background: rgba(219, 234, 254, 0.65);
  color: #334155;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  overflow: hidden;
  border-radius: 10px;
  font-size: 13px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 8px 10px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  text-align: left;
}

.markdown-body :deep(th) {
  background: rgba(241, 245, 249, 0.85);
  font-weight: 600;
}

.embed-message-item__meta {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  margin-top: 2px;
  padding-left: 2px;
}

.embed-message-item__citations {
  width: 100%;
}

.embed-message-item__citation-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.embed-message-item__citation-chip {
  display: inline-flex;
  max-width: 170px;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  background: #ffffff;
  font-size: 12px;
  color: #64748b;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

.embed-message-item__citation-chip span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.embed-message-item__citation-chip.is-more {
  max-width: none;
  border-color: #dbeafe;
  background: #eff6ff;
  color: #2563eb;
}

.embed-message-item__feedback-wrap {
  display: flex;
  align-items: center;
}

.embed-message-item__streaming {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #64748b;
  font-size: 13px;
  margin-top: 4px;
}

.embed-message-item__typing-indicator {
  display: flex;
  gap: 3px;
}

.embed-message-item__typing-indicator .dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background-color: #94a3b8;
  animation: typing 1.4s infinite ease-in-out both;
}

.embed-message-item__typing-indicator .dot:nth-child(1) {
  animation-delay: -0.32s;
}

.embed-message-item__typing-indicator .dot:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes typing {
  0%,
  80%,
  100% {
    transform: scale(0);
  }

  40% {
    transform: scale(1);
  }
}

@media (max-width: 768px) {
  .embed-message-item.is-user .embed-message-item__body {
    max-width: 78%;
  }

  .embed-message-item__body {
    max-width: 100%;
  }

  .embed-message-item.is-assistant .embed-message-item__body {
    width: calc(100% - 42px);
    max-width: calc(100% - 42px);
  }
}
</style>
