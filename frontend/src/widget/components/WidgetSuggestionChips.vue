<script setup lang="ts">
defineProps<{ suggestions: string[]; disabled?: boolean }>();
const emit = defineEmits<{ select: [question: string] }>();
</script>

<template>
  <div v-if="suggestions.length" class="widget-suggestions">
    <button
      v-for="question in suggestions"
      :key="question"
      type="button"
      :disabled="disabled"
      @click="emit('select', question)"
    >{{ question }}</button>
  </div>
</template>

<style scoped>
.widget-suggestions { display: flex; flex-wrap: wrap; gap: 7px; }
.widget-suggestions button { min-height: 32px; padding: 6px 11px; border: 1px solid #bae6ef; border-radius: 8px; background: #ecfeff; color: #0e7490; cursor: pointer; font: inherit; font-size: 12px; line-height: 1.35; transition: background 0.18s ease, border-color 0.18s ease; }
.widget-suggestions button:hover:not(:disabled) { border-color: #67e8f9; background: #cffafe; }
.widget-suggestions button:focus-visible { outline: 3px solid rgba(8, 145, 178, 0.28); outline-offset: 2px; }
.widget-suggestions button:disabled { cursor: not-allowed; opacity: 0.55; }
@media (prefers-reduced-motion: reduce) { .widget-suggestions button { transition: none; } }
</style>
