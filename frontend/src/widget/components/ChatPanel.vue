<script setup lang="ts">
import { computed, nextTick, useTemplateRef } from "vue";
import { ChatDotRound, Close, Opportunity, RefreshRight, Warning } from "@element-plus/icons-vue";

import type { WidgetPageContext } from "../client/agent-chat-api";
import { useAgentChat } from "../chat";
import ChatComposer from "./ChatComposer.vue";
import MessageItem from "./MessageItem.vue";
import SessionHistory from "./SessionHistory.vue";
import SuggestionChips from "./SuggestionChips.vue";

const props = defineProps<{
  token: string;
  apiBaseUrl: string;
  pageContext: WidgetPageContext;
  refreshToken: () => Promise<string>;
}>();
const emit = defineEmits<{
  close: [];
  dragStart: [event: PointerEvent];
  resizeStart: [event: PointerEvent];
}>();
const composerRef = useTemplateRef<InstanceType<typeof ChatComposer>>("composerRef");

const {
  assistantName,
  contextLabel,
  currentSessionId,
  deleteSession,
  error,
  greeting,
  isInitializing,
  isLoadingSessions,
  isTyping,
  loadSessions,
  messages,
  placeholder,
  scrollRef,
  selectSession,
  sendMessage,
  sessions,
  startNewConversation,
  stopGenerating,
  submitFeedback,
  suggestions,
  workflowRun,
} = useAgentChat({
  apiBaseUrl: props.apiBaseUrl,
  token: computed(() => props.token),
  pageContext: computed(() => props.pageContext),
  refreshToken: props.refreshToken,
});

const activeWorkflowMessageId = computed(() => {
  if (!workflowRun.value) return null;
  const last = messages.value[messages.value.length - 1];
  return last?.role === "assistant" ? last.id : null;
});

async function handleSend(text: string) {
  await sendMessage(text);
  await nextTick();
  composerRef.value?.focus();
}

function handleNewConversation() {
  startNewConversation();
  void nextTick(() => composerRef.value?.focus());
}

function handleHeaderPointerDown(event: PointerEvent) {
  const target = event.target;
  if (target instanceof Element && target.closest("button, input, textarea, a, [role='button']")) {
    return;
  }
  emit("dragStart", event);
}

function handleResizePointerDown(event: PointerEvent) {
  emit("resizeStart", event);
}

defineExpose({ sendMessage: handleSend });
</script>

<template>
  <section
    class="widget-chat"
    aria-label="智能助手"
  >
    <div
      v-if="isInitializing"
      class="widget-chat__initializing"
    >
      <span class="widget-chat__loading-icon"><el-icon class="is-loading"><RefreshRight /></el-icon></span>
      <strong>正在初始化助手</strong>
      <span>正在校验访问凭证并加载应用配置</span>
    </div>

    <template v-else>
      <header
        class="widget-chat__header"
        @pointerdown="handleHeaderPointerDown"
      >
        <div class="widget-chat__identity">
          <span
            class="widget-chat__avatar"
            aria-hidden="true"
          ><el-icon><ChatDotRound /></el-icon></span>
          <span class="widget-chat__identity-copy">
            <span class="widget-chat__name-row">
              <strong>{{ assistantName }}</strong><small>AI</small>
            </span>
            <span class="widget-chat__status"><i aria-hidden="true" />在线服务中</span>
          </span>
        </div>
        <div class="widget-chat__header-actions">
          <SessionHistory
            :current-session-id="currentSessionId"
            :sessions="sessions"
            :loading="isLoadingSessions"
            @load="loadSessions"
            @select="selectSession"
            @create="handleNewConversation"
            @delete="deleteSession"
          />
          <button
            type="button"
            title="关闭智能助手"
            aria-label="关闭智能助手"
            @click="emit('close')"
          >
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </header>

      <div
        v-if="contextLabel"
        class="widget-chat__context"
      >
        <span>当前应用</span><strong>{{ contextLabel }}</strong>
      </div>

      <div
        v-if="error"
        class="widget-chat__error"
        role="alert"
      >
        <el-icon><Warning /></el-icon><span>{{ error }}</span>
      </div>

      <main
        ref="scrollRef"
        class="widget-chat__messages"
      >
        <div
          v-if="messages.length === 0"
          class="widget-chat__welcome"
        >
          <span
            class="widget-chat__welcome-avatar"
            aria-hidden="true"
          ><el-icon><ChatDotRound /></el-icon></span>
          <div class="widget-chat__welcome-card">
            <small>欢迎使用</small>
            <strong>{{ assistantName }}</strong>
            <p>{{ greeting }}</p>
          </div>
        </div>

        <MessageItem
          v-for="message in messages"
          :key="message.id"
          :message="message"
          :assistant-name="assistantName"
          :is-typing="isTyping"
          :workflow-run="message.id === activeWorkflowMessageId ? workflowRun : null"
          @feedback="submitFeedback(message, $event)"
        />
      </main>

      <footer class="widget-chat__footer">
        <div class="widget-chat__composer-shell">
          <div
            v-if="messages.length === 0 && suggestions.length"
            class="widget-chat__suggestion-area"
          >
            <span class="widget-chat__suggestion-title"><el-icon><Opportunity /></el-icon>热门问题</span>
            <SuggestionChips
              :suggestions="suggestions.slice(0, 3)"
              :disabled="isTyping"
              @select="handleSend"
            />
          </div>
          <ChatComposer
            ref="composerRef"
            :placeholder="placeholder"
            :is-typing="isTyping"
            @send="handleSend"
            @stop="stopGenerating"
          />
        </div>
        <div class="widget-chat__brand">
          <el-icon><ChatDotRound /></el-icon>Powered by SynapseFlow
        </div>
      </footer>
    </template>
    <button
      type="button"
      class="widget-chat__resize-handle"
      title="调整助手窗口大小"
      aria-label="调整助手窗口大小"
      @pointerdown="handleResizePointerDown"
    />
  </section>
</template>

<style scoped>
.widget-chat { position: relative; display: flex; width: 100%; height: 100%; min-height: 0; flex-direction: column; overflow: hidden; border: 1px solid rgba(203, 213, 225, 0.86); border-radius: 8px; background: #fff; color: #164e63; box-shadow: 0 22px 58px rgba(15, 23, 42, 0.2); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif; }
.widget-chat__initializing { display: flex; flex: 1; align-items: center; justify-content: center; flex-direction: column; gap: 8px; background: #f8fbfc; }
.widget-chat__initializing strong { margin-top: 5px; color: #164e63; font-size: 15px; }
.widget-chat__initializing > span:last-child { color: #64748b; font-size: 12px; }
.widget-chat__loading-icon { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 8px; background: #e6f7fa; color: #0891b2; font-size: 23px; }
.widget-chat__header { display: flex; min-height: 62px; padding: 10px 12px; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid #e5edf0; background: rgba(255, 255, 255, 0.98); }
.widget-chat__identity { display: flex; min-width: 0; align-items: center; gap: 9px; }
.widget-chat__avatar, .widget-chat__welcome-avatar { display: inline-grid; overflow: hidden; place-items: center; border-radius: 50%; background: #e6f7fa; color: #0891b2; box-shadow: 0 6px 16px rgba(8, 145, 178, 0.14); }
.widget-chat__avatar { width: 36px; height: 36px; flex: 0 0 36px; }
.widget-chat__avatar .el-icon { font-size: 20px; }
.widget-chat__identity-copy { display: flex; min-width: 0; flex-direction: column; gap: 3px; }
.widget-chat__name-row { display: flex; min-width: 0; align-items: center; gap: 6px; }
.widget-chat__name-row strong { overflow: hidden; color: #164e63; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.widget-chat__name-row small { padding: 2px 5px; border-radius: 5px; background: #e6f7fa; color: #0e7490; font-size: 9px; font-weight: 700; }
.widget-chat__status { display: flex; align-items: center; gap: 5px; color: #64748b; font-size: 11px; }
.widget-chat__status i { width: 6px; height: 6px; border-radius: 50%; background: #059669; box-shadow: 0 0 0 2px #d1fae5; }
.widget-chat__header-actions { display: flex; align-items: center; gap: 5px; }
.widget-chat__header-actions > button { display: grid; width: 40px; height: 40px; padding: 0; place-items: center; border: 1px solid #dbe5ea; border-radius: 8px; background: #fff; color: #475569; cursor: pointer; }
.widget-chat__header-actions > button:hover { background: #f0f9fa; color: #0891b2; }
.widget-chat__header-actions > button:focus-visible { outline: 3px solid rgba(8, 145, 178, 0.28); outline-offset: 1px; }
.widget-chat__context { display: flex; min-height: 34px; padding: 7px 12px; align-items: center; gap: 8px; border-bottom: 1px solid #ccecf1; background: #ecfeff; }
.widget-chat__context span { flex: 0 0 auto; color: #0891b2; font-size: 9px; font-weight: 700; text-transform: uppercase; }
.widget-chat__context strong { min-width: 0; overflow: hidden; color: #0e7490; font-size: 11px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.widget-chat__error { display: flex; padding: 8px 12px; align-items: center; gap: 7px; border-bottom: 1px solid #fecaca; background: #fef2f2; color: #b91c1c; font-size: 12px; }
.widget-chat__messages { display: flex; min-height: 0; flex: 1; padding: 16px 14px; flex-direction: column; gap: 14px; overflow-y: auto; background: linear-gradient(180deg, #f8fbfc 0%, #fff 100%); scrollbar-color: #cbdde2 transparent; scrollbar-width: thin; }
.widget-chat__welcome { display: flex; width: 100%; align-items: flex-end; gap: 9px; }
.widget-chat__welcome-avatar { width: 30px; height: 30px; flex: 0 0 30px; margin-bottom: 3px; }
.widget-chat__welcome-avatar .el-icon { font-size: 17px; }
.widget-chat__welcome-card { display: flex; width: min(88%, 700px); padding: 15px 16px; flex-direction: column; gap: 6px; border: 1px solid #ccecf1; border-radius: 8px 8px 8px 2px; background: #fff; box-shadow: 0 8px 22px rgba(8, 145, 178, 0.06); }
.widget-chat__welcome-card small { color: #0891b2; font-size: 9px; font-weight: 700; text-transform: uppercase; }
.widget-chat__welcome-card strong { color: #164e63; font-size: 16px; }
.widget-chat__welcome-card p { margin: 0; color: #334155; font-size: 13px; line-height: 1.7; white-space: pre-wrap; }
.widget-chat__footer { padding: 9px 11px 8px; border-top: 1px solid #edf2f5; background: #fff; }
.widget-chat__composer-shell { overflow: hidden; border: 1px solid #d6e3e7; border-radius: 8px; background: #fbfdfe; box-shadow: 0 7px 20px rgba(15, 23, 42, 0.05); }
.widget-chat__suggestion-area { padding: 10px 12px; border-bottom: 1px solid #e5edf0; background: #f8fbfc; }
.widget-chat__suggestion-title { display: flex; margin-bottom: 8px; align-items: center; gap: 5px; color: #64748b; font-size: 10px; font-weight: 700; }
.widget-chat__suggestion-title .el-icon { color: #059669; }
.widget-chat__brand { display: flex; margin-top: 7px; align-items: center; justify-content: center; gap: 4px; color: #94a3b8; font-size: 9px; }
.widget-chat__resize-handle { position: absolute; z-index: 4; right: 0; bottom: 0; width: 22px; height: 22px; padding: 0; border: 0; background: transparent; color: #94a3b8; cursor: nwse-resize; touch-action: none; }
.widget-chat__resize-handle::after { position: absolute; right: 4px; bottom: 4px; width: 8px; height: 8px; border-right: 2px solid currentColor; border-bottom: 2px solid currentColor; content: ""; }
.widget-chat__resize-handle:hover { color: #0891b2; }
.widget-chat__resize-handle:focus-visible { outline: 2px solid rgba(8, 145, 178, 0.42); outline-offset: -3px; }
@media (max-width: 640px) { .widget-chat__resize-handle { display: none; } .widget-chat { border: 0; border-radius: 0; box-shadow: none; } .widget-chat__messages { padding: 13px 11px; } .widget-chat__footer { padding: 8px; } }
@media (min-width: 641px) { .widget-chat__header { cursor: grab; touch-action: none; user-select: none; } .widget-chat__header-actions { cursor: default; } }
@media (prefers-reduced-motion: reduce) { .widget-chat * { scroll-behavior: auto !important; } }
</style>
