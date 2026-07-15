<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { Promotion } from "@element-plus/icons-vue";

const props = defineProps<{ placeholder: string; isTyping: boolean }>();
const emit = defineEmits<{ send: [text: string]; stop: [] }>();
const value = ref("");
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const canSend = computed(() => value.value.trim().length > 0 && !props.isTyping);

function focus() { textareaRef.value?.focus(); }
function resize() {
  const textarea = textareaRef.value;
  if (!textarea) return;
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 118)}px`;
}
function send() {
  const text = value.value.trim();
  if (!text || props.isTyping) return;
  value.value = "";
  if (textareaRef.value) textareaRef.value.style.height = "auto";
  emit("send", text);
}
function onKeydown(event: KeyboardEvent) {
  if (!event.isComposing && event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    send();
  }
}
defineExpose({ focus });
</script>

<template>
  <div class="widget-composer">
    <textarea
      ref="textareaRef"
      v-model="value"
      :placeholder="placeholder"
      rows="1"
      aria-label="聊天输入"
      @input="nextTick(resize)"
      @keydown="onKeydown"
    />
    <button v-if="isTyping" type="button" class="is-stop" title="停止生成" @click="emit('stop')">
      <span aria-hidden="true">■</span>
    </button>
    <button v-else type="button" class="is-send" :disabled="!canSend" title="发送" @click="send">
      <el-icon><Promotion /></el-icon><span>发送</span>
    </button>
  </div>
</template>

<style scoped>
.widget-composer { display: flex; min-height: 58px; padding: 10px 12px; align-items: flex-end; gap: 10px; }
.widget-composer:focus-within { background: rgba(236, 254, 255, 0.42); }
.widget-composer textarea { min-width: 0; min-height: 28px; max-height: 118px; flex: 1; resize: none; border: 0; outline: 0; background: transparent; color: #164e63; font: inherit; font-size: 14px; line-height: 1.55; }
.widget-composer textarea::placeholder { color: #94a3b8; }
.widget-composer button { display: inline-flex; height: 38px; min-width: 44px; padding: 0 14px; align-items: center; justify-content: center; gap: 6px; border-radius: 8px; cursor: pointer; font: inherit; font-size: 13px; font-weight: 600; transition: background 0.18s ease, color 0.18s ease; }
.widget-composer button:focus-visible { outline: 3px solid rgba(8, 145, 178, 0.28); outline-offset: 2px; }
.widget-composer .is-send { border: 0; background: #0891b2; color: #fff; }
.widget-composer .is-send:hover:not(:disabled) { background: #0e7490; }
.widget-composer .is-send:disabled { background: #e2e8f0; color: #94a3b8; cursor: not-allowed; }
.widget-composer .is-stop { border: 1px solid #fecaca; background: #fef2f2; color: #dc2626; }
@media (max-width: 480px) { .widget-composer button span:not([aria-hidden]) { display: none; } .widget-composer button { padding: 0 11px; } }
@media (prefers-reduced-motion: reduce) { .widget-composer button { transition: none; } }
</style>
