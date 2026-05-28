<script setup lang="ts">
import { computed, nextTick, useTemplateRef } from "vue";
import { ChatDotRound, Opportunity, RefreshRight, Warning } from "@element-plus/icons-vue";

import EmbedChatComposer from "@/modules/embed/components/EmbedChatComposer.vue";
import EmbedMessageItem, {
  type EmbedRenderableMessage,
} from "@/modules/embed/components/EmbedMessageItem.vue";
import EmbedSessionHistoryPanel from "@/modules/embed/components/EmbedSessionHistoryPanel.vue";
import EmbedSuggestionChips from "@/modules/embed/components/EmbedSuggestionChips.vue";
import { useEmbeddedAssistant } from "@/modules/embed/composables/useEmbeddedAssistant";

const {
  assistantName,
  contextLabel,
  currentSessionId,
  error,
  greeting,
  isInitializing,
  isTyping,
  messages,
  placeholder,
  deletingSessionId,
  retrievedCount,
  scrollContainerRef,
  deleteSession,
  loadSessions,
  selectSession,
  sessions,
  sessionsError,
  sessionsLoading,
  streamPhase,
  streamStatus,
  suggestions,
  sendMessage,
  submitFeedback,
  startNewConversation,
  stopGenerating,
} = useEmbeddedAssistant();

const composerRef = useTemplateRef<InstanceType<typeof EmbedChatComposer>>("composerRef");

const renderedMessages = computed<EmbedRenderableMessage[]>(() => {
  const visibleMessages =
    isTyping.value && messages.value.at(-1)?.role === "assistant" && !messages.value.at(-1)?.content
      ? messages.value.slice(0, -1)
      : messages.value;

  if (visibleMessages.length === 0) {
    return [];
  }

  return visibleMessages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    kind: "normal",
    logId: message.logId,
    retrievedDocs: message.retrievedDocs,
    feedbackValue: message.feedbackValue,
    feedbackSubmitting: message.feedbackSubmitting,
  }));
});

const showThinkingState = computed(() => {
  const lastMessage = messages.value.at(-1);
  return (
    isTyping.value &&
    lastMessage?.role === "assistant" &&
    !lastMessage.content
  );
});

const STREAM_PHASE_META: Record<string, { title: string; accentClass: string }> = {
  plan_query: {
    title: "正在理解问题",
    accentClass: "is-sky",
  },
  analyze: {
    title: "正在分析问题",
    accentClass: "is-sky",
  },
  rewrite_query: {
    title: "正在整理检索线索",
    accentClass: "is-indigo",
  },
  retrieve: {
    title: "正在检索知识库",
    accentClass: "is-blue",
  },
  evaluate: {
    title: "正在核对答案依据",
    accentClass: "is-violet",
  },
  answer: {
    title: "正在生成回复",
    accentClass: "is-emerald",
  },
};

const thinkingPhase = computed(() => {
  const nodeId = streamPhase.value.nodeId;
  const phaseMeta = nodeId ? STREAM_PHASE_META[nodeId] : null;
  const fallbackTitle =
    typeof retrievedCount.value === "number" && retrievedCount.value > 0
      ? "正在组织答案"
      : streamStatus.value?.includes("连接")
        ? "正在连接助手"
        : "正在处理中";
  const detail =
    typeof retrievedCount.value === "number" && retrievedCount.value > 0 && nodeId === "retrieve"
      ? `已匹配 ${retrievedCount.value} 条相关内容`
      : streamStatus.value || "正在处理你的问题";

  return {
    title: phaseMeta?.title ?? fallbackTitle,
    detail,
    accentClass: phaseMeta?.accentClass ?? "is-blue",
  };
});

async function handleSend(text: string) {
  await sendMessage(text);
  await nextTick();
  composerRef.value?.focus();
}

function handleSuggestionSelect(question: string) {
  if (isTyping.value) {
    return;
  }

  void handleSend(question);
}

async function handleFeedback(message: EmbedRenderableMessage, value: "helpful" | "not_helpful") {
  if (!message.logId) {
    return;
  }

  await submitFeedback(message.logId, value);
}
</script>

<template>
  <section class="embed-assistant-page">
    <div class="embed-assistant-page__backdrop" />

    <div class="embed-assistant-page__shell">
      <main class="embed-assistant-page__content">
        <div v-if="isInitializing" class="embed-assistant-page__state">
          <div class="embed-assistant-page__state-spinner">
            <el-icon class="is-loading"><RefreshRight /></el-icon>
          </div>
          <div class="embed-assistant-page__state-text">
            <strong>正在初始化助手</strong>
            <span>正在校验访问令牌并加载当前应用配置</span>
          </div>
        </div>

        <template v-else>
          <header class="embed-assistant-page__header">
            <div class="embed-assistant-page__header-main">
              <div class="embed-assistant-page__assistant-avatar">
                <el-icon><ChatDotRound /></el-icon>
              </div>
              <div class="embed-assistant-page__assistant-meta">
                <div class="embed-assistant-page__assistant-name-row">
                  <strong class="embed-assistant-page__assistant-name">{{ assistantName }}</strong>
                  <span class="embed-assistant-page__assistant-badge">AI</span>
                </div>
                <div class="embed-assistant-page__assistant-status">在线服务中</div>
              </div>
            </div>

            <EmbedSessionHistoryPanel
              :current-session-id="currentSessionId"
              :sessions="sessions"
              :loading="sessionsLoading"
              :error="sessionsError"
              :deleting-session-id="deletingSessionId"
              @refresh="loadSessions"
              @select="selectSession"
              @create="startNewConversation"
              @delete="deleteSession"
            />
          </header>

          <div v-if="contextLabel" class="embed-assistant-page__context-bar">
            <span class="embed-assistant-page__context-label">当前应用</span>
            <span class="embed-assistant-page__context-value">{{ contextLabel }}</span>
          </div>

          <div v-if="error" class="embed-assistant-page__error-banner">
            <el-icon><Warning /></el-icon>
            <span>{{ error }}</span>
          </div>

          <section ref="scrollContainerRef" class="embed-assistant-page__messages">
            <div v-if="messages.length === 0" class="embed-assistant-page__welcome">
              <div class="embed-assistant-page__welcome-row">
                <div class="embed-assistant-page__welcome-avatar">
                  <el-icon><ChatDotRound /></el-icon>
                </div>
                <div class="embed-assistant-page__welcome-card">
                  <div class="embed-assistant-page__welcome-eyebrow">欢迎使用</div>
                  <div class="embed-assistant-page__welcome-title">{{ assistantName }}</div>
                  <div class="embed-assistant-page__welcome-content">
                    {{ greeting }}
                  </div>
                </div>
              </div>
            </div>

            <EmbedMessageItem
              v-for="message in renderedMessages"
              :key="message.id"
              :message="message"
              :assistant-name="assistantName"
              :stream-status="streamStatus"
              :is-typing="isTyping"
              @feedback="handleFeedback(message, $event)"
            />

            <div v-if="showThinkingState" class="embed-assistant-page__thinking">
              <div class="embed-assistant-page__thinking-avatar">
                <el-icon><ChatDotRound /></el-icon>
              </div>
              <div class="embed-assistant-page__thinking-card">
                <div class="embed-assistant-page__thinking-row">
                  <div class="embed-assistant-page__thinking-dots">
                    <span class="dot" />
                    <span class="dot" />
                    <span class="dot" />
                  </div>
                  <span
                    class="embed-assistant-page__thinking-title"
                    :class="thinkingPhase.accentClass"
                  >
                    {{ thinkingPhase.title }}
                  </span>
                </div>
              </div>
            </div>
          </section>

          <footer class="embed-assistant-page__composer">
            <div class="embed-assistant-page__composer-module">
              <transition name="embed-suggestions-fade" appear>
                <div
                  v-if="messages.length === 0 && suggestions.length > 0"
                  class="embed-assistant-page__suggestions"
                >
                  <div class="embed-assistant-page__suggestions-header">
                    <el-icon><Opportunity /></el-icon>
                    <span>热门问题</span>
                  </div>
                  <EmbedSuggestionChips
                    :suggestions="suggestions.slice(0, 3)"
                    :disabled="isTyping"
                    @select="handleSuggestionSelect"
                  />
                </div>
              </transition>
              <EmbedChatComposer
                ref="composerRef"
                :placeholder="placeholder"
                :is-typing="isTyping"
                @send="handleSend"
                @stop="stopGenerating"
              />
            </div>
            <div class="embed-assistant-page__brand">
              <el-icon><ChatDotRound /></el-icon>
              <span>Powered by SynapseFlow</span>
            </div>
          </footer>
        </template>
      </main>
    </div>
  </section>
</template>

<style scoped>
.embed-assistant-page {
  position: relative;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  background:
    radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.1) 0%, transparent 40%),
    radial-gradient(circle at 90% 80%, rgba(14, 165, 233, 0.1) 0%, transparent 40%),
    #f4f7f9;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

.embed-assistant-page__backdrop {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(148, 163, 184, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.05) 1px, transparent 1px);
  background-size: 24px 24px;
  pointer-events: none;
}

.embed-assistant-page__shell {
  position: relative;
  z-index: 1;
  height: 100%;
  max-width: 1024px;
  margin: 0 auto;
  padding: 14px 16px 16px;
}

.embed-assistant-page__content {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 12px 36px rgba(15, 23, 42, 0.05), 0 1px 3px rgba(15, 23, 42, 0.02);
  backdrop-filter: blur(20px);
  overflow: hidden;
}

.embed-assistant-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 56px;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.92);
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.embed-assistant-page__header-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.embed-assistant-page__assistant-avatar {
  display: inline-flex;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
  color: #ffffff;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.18);
  flex-shrink: 0;
}

.embed-assistant-page__assistant-meta {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.embed-assistant-page__assistant-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.embed-assistant-page__assistant-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  color: #0f172a;
}

.embed-assistant-page__assistant-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 18px;
  padding: 0 6px;
  border-radius: 999px;
  background: linear-gradient(135deg, #3b82f6 0%, #4f46e5 100%);
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  flex-shrink: 0;
}

.embed-assistant-page__assistant-status {
  margin-top: 2px;
  font-size: 11px;
  color: #10b981;
}

.embed-assistant-page__header-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #ffffff;
  color: #475569;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
  flex-shrink: 0;
}

.embed-assistant-page__header-action:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #0f172a;
}

.embed-assistant-page__context-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 16px;
  border-bottom: 1px solid #dbeafe;
  background: rgba(239, 246, 255, 0.9);
  flex-shrink: 0;
}

.embed-assistant-page__context-label {
  font-size: 10px;
  font-weight: 700;
  color: #60a5fa;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  flex-shrink: 0;
}

.embed-assistant-page__context-value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 500;
  color: #1d4ed8;
}

.embed-assistant-page__state {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.embed-assistant-page__state-spinner {
  display: inline-flex;
  height: 54px;
  width: 54px;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 26px;
}

.embed-assistant-page__state-text {
  text-align: center;
}

.embed-assistant-page__state-text strong {
  display: block;
  color: #1e293b;
  font-size: 16px;
  margin-bottom: 6px;
}

.embed-assistant-page__state-text span {
  color: #64748b;
  font-size: 14px;
}

.embed-assistant-page__error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding: 10px 16px;
  background: #fef2f2;
  border-bottom: 1px solid #fee2e2;
  color: #ef4444;
  flex-shrink: 0;
}

.embed-assistant-page__messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 18px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.embed-assistant-page__messages::-webkit-scrollbar {
  width: 6px;
}

.embed-assistant-page__messages::-webkit-scrollbar-track {
  background: transparent;
}

.embed-assistant-page__messages::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 10px;
}

.embed-assistant-page__messages::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.embed-assistant-page__welcome {
  display: flex;
  width: 100%;
  padding: 6px 0 10px;
}

.embed-assistant-page__welcome-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  width: min(86%, 720px);
  max-width: 100%;
}

.embed-assistant-page__welcome-avatar {
  display: inline-flex;
  width: 32px;
  height: 32px;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
  color: #ffffff;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.18);
  flex-shrink: 0;
  margin-bottom: 4px;
}

.embed-assistant-page__welcome-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  padding: 18px 20px;
  border: 1px solid #dbeafe;
  border-radius: 22px 22px 22px 8px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 251, 255, 0.98) 100%);
  box-shadow:
    0 14px 32px rgba(37, 99, 235, 0.06),
    0 1px 3px rgba(15, 23, 42, 0.03);
}

.embed-assistant-page__welcome-eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #60a5fa;
}

.embed-assistant-page__welcome-title {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
}

.embed-assistant-page__welcome-content {
  font-size: 14px;
  line-height: 1.75;
  color: #334155;
  white-space: pre-wrap;
}

.embed-assistant-page__thinking {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
}

.embed-assistant-page__thinking-avatar {
  display: inline-flex;
  width: 32px;
  height: 32px;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
  color: #ffffff;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.18);
  flex-shrink: 0;
  margin-top: 2px;
}

.embed-assistant-page__thinking-card {
  display: flex;
  flex-direction: column;
  gap: 0;
  width: 260px;
  max-width: calc(100% - 42px);
  padding: 14px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 18px 18px 18px 4px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

.embed-assistant-page__thinking-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.embed-assistant-page__thinking-dots {
  display: flex;
  gap: 4px;
}

.embed-assistant-page__thinking-dots .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #60a5fa;
  animation: embed-thinking 1.2s infinite ease-in-out both;
}

.embed-assistant-page__thinking-dots .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.embed-assistant-page__thinking-dots .dot:nth-child(3) {
  animation-delay: 0.4s;
}

.embed-assistant-page__thinking-title {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.embed-assistant-page__thinking-title.is-sky {
  color: #0284c7;
}

.embed-assistant-page__thinking-title.is-indigo {
  color: #4f46e5;
}

.embed-assistant-page__thinking-title.is-blue {
  color: #2563eb;
}

.embed-assistant-page__thinking-title.is-violet {
  color: #7c3aed;
}

.embed-assistant-page__thinking-title.is-emerald {
  color: #059669;
}

.embed-assistant-page__composer {
  padding: 12px 16px 14px;
  background: rgba(255, 255, 255, 0.94);
  border-top: 1px solid #f1f5f9;
  flex-shrink: 0;
}

.embed-assistant-page__composer-module {
  overflow: hidden;
  border: 1px solid #dbe3ee;
  border-radius: 22px;
  background:
    linear-gradient(180deg, rgba(248, 250, 252, 0.96) 0%, rgba(255, 255, 255, 0.99) 100%);
  box-shadow:
    0 12px 28px rgba(15, 23, 42, 0.05),
    0 1px 2px rgba(15, 23, 42, 0.03);
}

.embed-assistant-page__suggestions {
  padding: 12px 14px 10px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
  background:
    linear-gradient(180deg, rgba(248, 250, 252, 0.9) 0%, rgba(255, 255, 255, 0.9) 100%);
}

.embed-assistant-page__suggestions-header {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  padding: 0 2px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #94a3b8;
}

.embed-assistant-page__suggestions-header :deep(svg) {
  color: #f59e0b;
}

.embed-assistant-page__brand {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  margin-top: 8px;
  font-size: 10px;
  color: #94a3b8;
}

.embed-assistant-page__brand :deep(svg) {
  font-size: 12px;
  color: #60a5fa;
}

.embed-suggestions-fade-enter-active,
.embed-suggestions-fade-appear-active {
  transition:
    opacity 0.28s ease,
    transform 0.28s ease;
}

.embed-suggestions-fade-enter-from,
.embed-suggestions-fade-appear-from {
  opacity: 0;
  transform: translateY(10px);
}

@media (max-width: 768px) {
  .embed-assistant-page__shell {
    padding: 10px;
  }

  .embed-assistant-page__header {
    padding: 10px 12px;
  }

  .embed-assistant-page__content {
    border-radius: 16px;
  }

  .embed-assistant-page__context-bar {
    padding: 8px 12px;
  }

  .embed-assistant-page__messages {
    padding: 12px;
  }

  .embed-assistant-page__welcome {
    padding: 2px 0 8px;
  }

  .embed-assistant-page__welcome-row {
    width: 100%;
  }

  .embed-assistant-page__welcome-card {
    padding: 16px 16px 18px;
  }

  .embed-assistant-page__welcome-title {
    font-size: 16px;
  }

  .embed-assistant-page__thinking-card {
    width: 100%;
    max-width: calc(100% - 42px);
  }

  .embed-assistant-page__composer {
    padding: 10px 12px 12px;
  }
}

@keyframes embed-thinking {
  0%,
  80%,
  100% {
    opacity: 0.35;
    transform: scale(0.85);
  }

  40% {
    opacity: 1;
    transform: scale(1);
  }
}

</style>
