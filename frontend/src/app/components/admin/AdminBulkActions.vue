<script setup lang="ts">
defineProps<{
  selectedCount: number;
}>();
</script>

<template>
  <transition name="admin-bulk-actions">
    <div v-if="selectedCount > 0" class="admin-bulk-actions">
      <span class="admin-bulk-actions__count">已选 {{ selectedCount }}</span>
      <span class="admin-bulk-actions__divider" />
      <slot />
    </div>
  </transition>
</template>

<style scoped>
.admin-bulk-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--admin-primary-border);
  border-radius: var(--admin-radius-md);
  background: var(--admin-primary-soft);
  padding: 5px 10px;
}

.admin-bulk-actions__count {
  color: var(--admin-primary-hover);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.admin-bulk-actions__divider {
  width: 1px;
  height: 16px;
  background: var(--admin-primary-border);
}

.admin-bulk-actions-enter-active,
.admin-bulk-actions-leave-active {
  transition: all 0.18s ease;
}

.admin-bulk-actions-enter-from,
.admin-bulk-actions-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
