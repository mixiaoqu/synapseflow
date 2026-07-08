<script setup lang="ts">
import { computed, ref } from "vue";
import DOMPurify from "dompurify";
import MarkdownIt from "markdown-it";
import { Document, Loading, User } from "@element-plus/icons-vue";
import EmbedFeedbackActions from "@/modules/embed/components/EmbedFeedbackActions.vue";
import EmbedWorkflowProgress from "@/modules/embed/components/EmbedWorkflowProgress.vue";
import assistantAvatarUrl from "@/shared/assets/assistant-avatar.png";
import type { ChatWorkflowRun } from "@/shared/lib/stream/workflowRun";

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
  workflowRun?: ChatWorkflowRun | null;
}>();

const emit = defineEmits<{
  feedback: [value: "helpful" | "not_helpful"];
}>();

const markdownRenderer = new MarkdownIt({
  breaks: true,
  linkify: true,
});

const displayContent = computed(() => {
  return props.message.content;
});

const renderedHtml = computed(() => {
  if (!displayContent.value) {
    return "";
  }

  const rawHtml = markdownRenderer.render(displayContent.value);
  return DOMPurify.sanitize(rawHtml);
});

const hasAssistantMeta = computed(() => {
  if (props.message.role !== "assistant") {
    return false;
  }
  if (props.message.kind === "streaming" || props.message.kind === "welcome") {
    return false;
  }
  return Boolean(
    props.message.content ||
    props.message.logId ||
    (props.message.retrievedDocs && props.message.retrievedDocs.length > 0),
  );
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
      <img
        v-if="message.role === 'assistant'"
        class="embed-message-item__assistant-avatar-image"
        :src="assistantAvatarUrl"
        :alt="assistantName"
      >
      <el-icon v-else><User /></el-icon>
    </div>

    <div class="embed-message-item__body">
      <EmbedWorkflowProgress
        v-if="message.role === 'assistant' && workflowRun"
        :run="workflowRun"
      />

      <article
        v-if="message.content || !(message.role === 'assistant' && workflowRun)"
        :class="['embed-message-item__bubble', `is-${message.role}`, `is-${message.kind ?? 'normal'}`]"
      >
        <div v-if="message.kind === 'streaming'" class="embed-message-item__streaming">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>思考中...</span>
        </div>
        <div
          v-else
          class="embed-message-item__content markdown-body"
          v-html="renderedHtml"
        />
      </article>

      <div
        v-if="hasAssistantMeta"
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
              <span v-if="index === 0">来源参考：</span>
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
          v-if="message.content"
          class="embed-message-item__actions-wrap"
        >
          <EmbedFeedbackActions
            :value="message.feedbackValue ?? null"
            :loading="message.feedbackSubmitting"
            :disabled="!message.logId || isTyping || !!message.feedbackValue"
            :copied="copied"
            :copy-disabled="!message.content"
            @submit="emit('feedback', $event)"
            @copy="handleCopy"
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
  gap: 12px;
  width: 100%;
}

.embed-message-item.is-user {
  justify-content: flex-end;
}

.embed-message-item__avatar {
  display: inline-flex;
  width: 30px;
  height: 30px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  flex-shrink: 0;
  margin-top: 0;
}

.embed-message-item__avatar.is-assistant {
  overflow: hidden;
  background: #ffffff;
  box-shadow: 0 6px 14px rgba(37, 99, 235, 0.12);
}

.embed-message-item__assistant-avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
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
  gap: 10px;
  min-width: 0;
}

.embed-message-item.is-user .embed-message-item__body {
  align-items: flex-end;
  max-width: min(62%, 420px);
}

.embed-message-item.is-assistant .embed-message-item__body {
  align-items: flex-start;
  width: min(88%, 720px);
  max-width: min(88%, 720px);
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
  padding: 0;
  width: 100%;
  background: transparent;
  color: #1e293b;
  border: 0;
  border-radius: 0;
  box-shadow: none;
}

.embed-message-item__bubble.is-welcome {
  padding: 16px 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  border-color: #dbeafe;
  border: 1px solid #dbeafe;
  border-radius: 18px 18px 18px 6px;
  box-shadow:
    0 12px 30px rgba(37, 99, 235, 0.06),
    0 1px 3px rgba(15, 23, 42, 0.03);
}

.embed-message-item__content {
  font-size: 14px;
  line-height: 1.75;
  word-break: break-word;
}

.embed-message-item__content :deep(p) {
  color: #1e293b;
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
  gap: 10px;
  margin-top: 6px;
  padding-left: 2px;
}

.embed-message-item__citations {
  width: 100%;
}

.embed-message-item__citation-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.embed-message-item__citation-chip {
  display: inline-flex;
  max-width: min(100%, 520px);
  align-items: center;
  gap: 4px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  font-size: 12px;
  color: #94a3b8;
  box-shadow: none;
}

.embed-message-item__citation-chip .el-icon {
  color: #94a3b8;
  font-size: 13px;
}

.embed-message-item__citation-chip span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.embed-message-item__citation-chip.is-more {
  max-width: none;
  color: #94a3b8;
}

.embed-message-item__actions-wrap {
  display: flex;
  align-items: center;
}

.embed-message-item__streaming {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 13px;
  margin-top: 4px;
}

.embed-message-item__streaming .el-icon {
  color: #818cf8;
  font-size: 14px;
}

@media (max-width: 768px) {
  .embed-message-item.is-user .embed-message-item__body {
    max-width: 78%;
  }

  .embed-message-item__body {
    max-width: 100%;
  }

  .embed-message-item.is-assistant .embed-message-item__body {
    width: calc(100% - 40px);
    max-width: calc(100% - 40px);
  }
}
</style>
