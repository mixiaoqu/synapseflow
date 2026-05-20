<script setup lang="ts">
type FeedbackValue = "helpful" | "not_helpful";

defineProps<{
  value?: FeedbackValue | null;
  loading?: boolean;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  submit: [value: FeedbackValue];
}>();
</script>

<template>
  <div class="embed-feedback-actions">
    <button
      type="button"
      class="embed-feedback-actions__button"
      :class="{ 'is-active': value === 'helpful' }"
      :disabled="disabled || loading"
      title="有帮助"
      aria-label="有帮助"
      @click="emit('submit', 'helpful')"
    >
      <span class="embed-feedback-actions__icon" aria-hidden="true">👍</span>
    </button>
    <button
      type="button"
      class="embed-feedback-actions__button"
      :class="{ 'is-active': value === 'not_helpful' }"
      :disabled="disabled || loading"
      title="没帮助"
      aria-label="没帮助"
      @click="emit('submit', 'not_helpful')"
    >
      <span class="embed-feedback-actions__icon" aria-hidden="true">👎</span>
    </button>
  </div>
</template>

<style scoped>
.embed-feedback-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.embed-feedback-actions__button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid #dbe3ee;
  border-radius: 999px;
  background: #ffffff;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
}

.embed-feedback-actions__button:hover:not(:disabled) {
  border-color: #93c5fd;
  color: #1d4ed8;
  background: #eff6ff;
}

.embed-feedback-actions__button.is-active {
  border-color: #bfdbfe;
  color: #1d4ed8;
  background: #dbeafe;
}

.embed-feedback-actions__button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.embed-feedback-actions__icon {
  font-size: 14px;
  line-height: 1;
}
</style>
