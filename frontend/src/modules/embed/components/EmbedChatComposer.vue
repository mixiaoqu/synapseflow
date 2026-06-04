<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { Promotion } from "@element-plus/icons-vue";

const props = defineProps<{
  placeholder: string;
  isTyping?: boolean;
}>();

const emit = defineEmits<{
  send: [text: string];
  stop: [];
}>();

const inputValue = ref("");
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const canSend = computed(() => inputValue.value.trim().length > 0 && !props.isTyping);

function focus() {
  textareaRef.value?.focus();
}

function autoResize() {
  const textarea = textareaRef.value;
  if (!textarea) {
    return;
  }

  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
}

function handleSend() {
  const text = inputValue.value.trim();
  if (!text || props.isTyping) {
    return;
  }

  inputValue.value = "";
  if (textareaRef.value) {
    textareaRef.value.style.height = "auto";
  }
  emit("send", text);
}

function handleInput() {
  void nextTick(autoResize);
}

function handleComposerKeydown(event: KeyboardEvent) {
  if (event.isComposing) {
    return;
  }

  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    handleSend();
  }
}

defineExpose({
  focus,
});
</script>

<template>
  <div class="embed-chat-composer__input-wrapper">
    <textarea
      ref="textareaRef"
      v-model="inputValue"
      class="embed-chat-composer__textarea"
      :placeholder="placeholder"
      rows="1"
      @input="handleInput"
      @keydown="handleComposerKeydown"
    />

    <div class="embed-chat-composer__actions">
      <button
        v-if="isTyping"
        type="button"
        class="embed-chat-composer__stop-button"
        title="停止生成"
        @click="emit('stop')"
      >
        <span class="stop-icon">■</span>
      </button>
      <button
        v-else
        type="button"
        class="embed-chat-composer__send-button"
        :disabled="!canSend"
        @click="handleSend"
      >
        <el-icon><Promotion /></el-icon>
        <span class="send-text">发送</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.embed-chat-composer__input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 10px 14px 12px;
  transition: all 0.2s ease;
}

.embed-chat-composer__input-wrapper:focus-within {
  background: rgba(255, 255, 255, 0.36);
}

.embed-chat-composer__textarea {
  flex: 1;
  min-height: 26px;
  max-height: 120px;
  resize: none;
  border: none;
  background: transparent;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.6;
  outline: none;
  padding: 4px 0;
}

.embed-chat-composer__textarea::placeholder {
  color: #94a3b8;
}

.embed-chat-composer__actions {
  flex-shrink: 0;
  padding-bottom: 2px;
}

.embed-chat-composer__send-button,
.embed-chat-composer__stop-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 38px;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  padding: 0 16px;
  transition: all 0.2s ease;
}

.embed-chat-composer__send-button {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: #ffffff;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.18);
}

.embed-chat-composer__send-button:hover:not(:disabled) {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
}

.embed-chat-composer__send-button:disabled {
  background: #e2e8f0;
  color: #94a3b8;
  box-shadow: none;
  cursor: not-allowed;
}

.embed-chat-composer__stop-button {
  background: #fef2f2;
  color: #ef4444;
  border: 1px solid #fecaca;
  padding: 0 12px;
}

.embed-chat-composer__stop-button:hover {
  background: #fee2e2;
}

.stop-icon {
  font-size: 12px;
}

@media (max-width: 768px) {
  .send-text {
    display: none;
  }

  .embed-chat-composer__send-button {
    padding: 0 12px;
  }
}
</style>
