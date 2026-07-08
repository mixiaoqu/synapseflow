<script setup lang="ts">
type FeedbackValue = "helpful" | "not_helpful";

defineProps<{
  value?: FeedbackValue | null;
  loading?: boolean;
  disabled?: boolean;
  copied?: boolean;
  copyDisabled?: boolean;
}>();

const emit = defineEmits<{
  submit: [value: FeedbackValue];
  copy: [];
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
      <svg
        class="embed-feedback-actions__icon"
        aria-hidden="true"
        viewBox="0 0 24 24"
      >
        <path d="M7 10v10" />
        <path d="M11 10l1.8-5.1c.3-.8 1.1-1.4 2-1.2 1 .2 1.6 1.2 1.3 2.2L15 10h3.5c1.5 0 2.6 1.4 2.3 2.8l-1 4.8c-.3 1.4-1.5 2.4-2.9 2.4H7" />
        <path d="M3 10h4v10H3z" />
      </svg>
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
      <svg
        class="embed-feedback-actions__icon"
        aria-hidden="true"
        viewBox="0 0 24 24"
      >
        <path d="M7 14V4" />
        <path d="M11 14l1.8 5.1c.3.8 1.1 1.4 2 1.2 1-.2 1.6-1.2 1.3-2.2L15 14h3.5c1.5 0 2.6-1.4 2.3-2.8l-1-4.8C19.5 5 18.3 4 16.9 4H7" />
        <path d="M3 4h4v10H3z" />
      </svg>
    </button>
    <button
      type="button"
      class="embed-feedback-actions__button"
      :class="{ 'is-active': copied }"
      :disabled="copyDisabled"
      :title="copied ? '已复制' : '复制回答'"
      :aria-label="copied ? '已复制' : '复制回答'"
      @click="emit('copy')"
    >
      <svg
        class="embed-feedback-actions__icon"
        aria-hidden="true"
        viewBox="0 0 24 24"
      >
        <rect
          x="8"
          y="8"
          width="11"
          height="13"
          rx="2"
        />
        <path d="M5 16H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
      </svg>
    </button>
    <button
      type="button"
      class="embed-feedback-actions__button"
      title="更多"
      aria-label="更多"
    >
      <svg
        class="embed-feedback-actions__icon"
        aria-hidden="true"
        viewBox="0 0 24 24"
      >
        <path d="M5 12h.01" />
        <path d="M12 12h.01" />
        <path d="M19 12h.01" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.embed-feedback-actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.embed-feedback-actions__button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 27px;
  height: 27px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #111827;
  cursor: pointer;
  transition:
    background 0.18s ease,
    color 0.18s ease;
}

.embed-feedback-actions__button:hover:not(:disabled) {
  background: #f1f5f9;
  color: #0f172a;
}

.embed-feedback-actions__button.is-active {
  color: #1d4ed8;
  background: #eff6ff;
}

.embed-feedback-actions__button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.embed-feedback-actions__icon {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}
</style>
