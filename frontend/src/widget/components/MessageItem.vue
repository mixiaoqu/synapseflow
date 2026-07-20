<script setup lang="ts">
import { computed, ref } from "vue";
import DOMPurify from "dompurify";
import MarkdownIt from "markdown-it";
import {
  ChatDotRound,
  Document,
  Loading,
  User,
} from "@element-plus/icons-vue";

import type { AgentChatMessage } from "../chat";
import type { ChatWorkflowRun } from "../stream/workflow-run";
import WorkflowProgress from "./WorkflowProgress.vue";

const props = defineProps<{
  message: AgentChatMessage;
  assistantName: string;
  isTyping: boolean;
  workflowRun?: ChatWorkflowRun | null;
}>();
const emit = defineEmits<{ feedback: [value: "helpful" | "not_helpful"] }>();
const copied = ref(false);
const markdown = new MarkdownIt({ breaks: true, linkify: true });
const html = computed(() => DOMPurify.sanitize(markdown.render(props.message.content || "")));

function docTitle(doc: Record<string, unknown>) {
  const metadata = doc.metadata;
  if (metadata && typeof metadata === "object" && !Array.isArray(metadata)) {
    const title = (metadata as Record<string, unknown>).document_title;
    if (typeof title === "string" && title.trim()) return title.trim();
    const path = (metadata as Record<string, unknown>).source_path;
    if (typeof path === "string" && path.trim()) {
      return path.split(/[\\/]/).filter(Boolean).pop() || path;
    }
  }
  return "知识库片段";
}

async function copy() {
  if (!props.message.content) return;
  try {
    await navigator.clipboard.writeText(props.message.content);
    copied.value = true;
    window.setTimeout(() => { copied.value = false; }, 1200);
  } catch {
    copied.value = false;
  }
}
</script>

<template>
  <article
    class="widget-message"
    :class="`is-${message.role}`"
  >
    <div
      class="widget-message__avatar"
      :class="`is-${message.role}`"
    >
      <el-icon
        v-if="message.role === 'assistant'"
        :aria-label="assistantName"
      >
        <ChatDotRound />
      </el-icon>
      <el-icon v-else>
        <User />
      </el-icon>
    </div>

    <div class="widget-message__body">
      <WorkflowProgress
        v-if="message.role === 'assistant' && workflowRun"
        :run="workflowRun"
      />

      <div
        v-if="message.content"
        class="widget-message__bubble"
        :class="`is-${message.role}`"
      >
        <!-- Markdown 已经过 DOMPurify 清洗。 -->
        <!-- eslint-disable vue/no-v-html -->
        <div
          v-if="message.role === 'assistant'"
          class="widget-message__markdown"
          v-html="html"
        />
        <!-- eslint-enable vue/no-v-html -->
        <div v-else>
          {{ message.content }}
        </div>
      </div>
      <div
        v-else-if="message.role === 'assistant' && !workflowRun"
        class="widget-message__typing"
      >
        <el-icon class="is-loading">
          <Loading />
        </el-icon><span>思考中...</span>
      </div>

      <div
        v-if="message.role === 'assistant' && message.content"
        class="widget-message__meta"
      >
        <div
          v-if="message.retrievedDocs?.length"
          class="widget-message__sources"
        >
          <span
            v-for="(doc, index) in message.retrievedDocs.slice(0, 4)"
            :key="`${message.id}-${index}`"
            :title="docTitle(doc)"
          >
            <el-icon><Document /></el-icon>
            <b v-if="index === 0">来源：</b>{{ docTitle(doc) }}
          </span>
          <span v-if="message.retrievedDocs.length > 4">+{{ message.retrievedDocs.length - 4 }}</span>
        </div>

        <div class="widget-message__actions">
          <button
            type="button"
            title="有帮助"
            :class="{ 'is-active': message.feedback === 'helpful' }"
            :disabled="!message.logId || isTyping || message.feedbackSubmitting"
            @click="emit('feedback', 'helpful')"
          >
            <svg
              class="widget-message__action-icon"
              aria-hidden="true"
              viewBox="0 0 24 24"
            >
              <path d="M7 10v12" />
              <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
            </svg>
          </button>
          <button
            type="button"
            title="没帮助"
            :class="{ 'is-active': message.feedback === 'not_helpful' }"
            :disabled="!message.logId || isTyping || message.feedbackSubmitting"
            @click="emit('feedback', 'not_helpful')"
          >
            <svg
              class="widget-message__action-icon"
              aria-hidden="true"
              viewBox="0 0 24 24"
            >
              <path d="M17 14V2" />
              <path d="m9 18.12 1-4.12H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z" />
            </svg>
          </button>
          <button
            type="button"
            :title="copied ? '已复制' : '复制回答'"
            @click="copy"
          >
            <svg
              class="widget-message__action-icon"
              aria-hidden="true"
              viewBox="0 0 24 24"
            >
              <rect
                width="14"
                height="14"
                x="8"
                y="8"
                rx="2"
                ry="2"
              />
              <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </article>
</template>

<style scoped>
.widget-message { display: flex; width: 100%; align-items: flex-start; gap: 10px; }
.widget-message.is-user { justify-content: flex-end; }
.widget-message__avatar { display: grid; width: 30px; height: 30px; flex: 0 0 30px; place-items: center; overflow: hidden; border-radius: 50%; }
.widget-message__avatar .el-icon { font-size: 16px; }
.widget-message__avatar.is-assistant { background: #e6f7fa; color: #0891b2; box-shadow: 0 5px 14px rgba(8, 145, 178, 0.14); }
.widget-message__avatar.is-user { order: 2; background: #dce7eb; color: #334155; }
.widget-message__body { display: flex; min-width: 0; max-width: calc(100% - 40px); flex-direction: column; align-items: flex-start; gap: 8px; }
.widget-message.is-assistant .widget-message__body { width: min(88%, 720px); }
.widget-message.is-user .widget-message__body { max-width: 76%; align-items: flex-end; }
.widget-message__bubble { min-width: 0; max-width: 100%; font-size: 14px; line-height: 1.72; word-break: break-word; }
.widget-message__bubble.is-user { padding: 9px 13px; border-radius: 8px 8px 2px 8px; background: #0891b2; color: #fff; box-shadow: 0 6px 16px rgba(8, 145, 178, 0.16); white-space: pre-wrap; }
.widget-message__bubble.is-assistant { width: 100%; color: #1e293b; }
.widget-message__markdown :deep(p), .widget-message__markdown :deep(ul), .widget-message__markdown :deep(ol), .widget-message__markdown :deep(pre), .widget-message__markdown :deep(blockquote), .widget-message__markdown :deep(table) { margin: 0; }
.widget-message__markdown :deep(* + p), .widget-message__markdown :deep(* + ul), .widget-message__markdown :deep(* + ol), .widget-message__markdown :deep(* + pre), .widget-message__markdown :deep(* + blockquote), .widget-message__markdown :deep(* + table) { margin-top: 9px; }
.widget-message__markdown :deep(ul), .widget-message__markdown :deep(ol) { padding-left: 20px; }
.widget-message__markdown :deep(a) { color: #0e7490; text-decoration: underline; text-underline-offset: 2px; }
.widget-message__markdown :deep(code) { padding: 2px 5px; border-radius: 4px; background: #e6f3f5; font-family: Consolas, monospace; font-size: 12px; }
.widget-message__markdown :deep(pre) { overflow-x: auto; padding: 11px 12px; border-radius: 8px; background: #12303b; color: #e6f7fa; }
.widget-message__markdown :deep(pre code) { padding: 0; background: transparent; color: inherit; }
.widget-message__markdown :deep(blockquote) { padding: 8px 11px; border-left: 3px solid #22d3ee; background: #ecfeff; color: #334155; }
.widget-message__markdown :deep(table) { width: 100%; border-collapse: collapse; font-size: 12px; }
.widget-message__markdown :deep(th), .widget-message__markdown :deep(td) { padding: 7px 8px; border: 1px solid #cbdde2; text-align: left; }
.widget-message__markdown :deep(th) { background: #f0f8fa; }
.widget-message__typing { display: flex; align-items: center; gap: 7px; color: #64748b; font-size: 12px; }
.widget-message__meta { display: flex; width: 100%; flex-direction: column; gap: 6px; }
.widget-message__sources { display: flex; flex-wrap: wrap; gap: 6px 10px; }
.widget-message__sources span { display: inline-flex; max-width: 100%; align-items: center; gap: 3px; overflow: hidden; color: #78909c; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.widget-message__sources b { font-weight: 500; }
.widget-message__actions { display: flex; align-items: center; gap: 8px; }
.widget-message__actions button { display: grid; width: 20px; height: 20px; padding: 0; place-items: center; border: 0; border-radius: 5px; background: transparent; color: #64748b; cursor: pointer; }
.widget-message__actions button:hover:not(:disabled), .widget-message__actions button.is-active { background: #e6f7fa; color: #0891b2; }
.widget-message__actions button:disabled { cursor: not-allowed; opacity: 0.4; }
.widget-message__actions button:focus-visible { outline: 3px solid rgba(8, 145, 178, 0.28); outline-offset: 1px; }
.widget-message__action-icon { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.8; }
@media (max-width: 480px) { .widget-message.is-assistant .widget-message__body { width: calc(100% - 40px); } .widget-message.is-user .widget-message__body { max-width: 82%; } }
</style>
