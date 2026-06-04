<script setup lang="ts">
defineProps<{
  suggestions: string[];
  disabled?: boolean;
}>();

const emit = defineEmits<{
  select: [question: string];
}>();
</script>

<template>
  <transition-group
    v-if="suggestions.length > 0"
    name="embed-suggestion-chip"
    tag="div"
    class="embed-suggestion-chips"
    appear
  >
    <button
      v-for="(question, index) in suggestions"
      :key="question"
      type="button"
      class="embed-suggestion-chips__item"
      :style="{ transitionDelay: `${index * 60}ms` }"
      :disabled="disabled"
      @click="emit('select', question)"
    >
      {{ question }}
    </button>
  </transition-group>
</template>

<style scoped>
.embed-suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  gap: 8px;
}

.embed-suggestion-chips__item {
  flex: 0 0 auto;
  border: 1px solid #dbeafe;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  cursor: pointer;
  font-size: 12px;
  line-height: 1.2;
  padding: 7px 12px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease;
}

.embed-suggestion-chips__item:hover:not(:disabled) {
  border-color: #93c5fd;
  background: #dbeafe;
  color: #1e40af;
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(59, 130, 246, 0.12);
}

.embed-suggestion-chip-enter-active,
.embed-suggestion-chip-appear-active {
  transition:
    opacity 0.28s ease,
    transform 0.28s ease;
}

.embed-suggestion-chip-enter-from,
.embed-suggestion-chip-appear-from {
  opacity: 0;
  transform: translateX(48px);
}

.embed-suggestion-chips__item:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
</style>
