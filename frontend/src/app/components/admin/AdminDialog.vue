<script setup lang="ts">
defineOptions({
  inheritAttrs: false,
});

withDefaults(
  defineProps<{
    modelValue: boolean;
    title: string;
    width?: string | number;
    loading?: boolean;
    destroyOnClose?: boolean;
    closeOnClickModal?: boolean;
  }>(),
  {
    width: "560px",
    loading: false,
    destroyOnClose: true,
    closeOnClickModal: false,
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  closed: [];
}>();
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    :width="width"
    :destroy-on-close="destroyOnClose"
    :close-on-click-modal="closeOnClickModal"
    :close-on-press-escape="!loading"
    class="admin-dialog"
    v-bind="$attrs"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="emit('closed')"
  >
    <template v-if="$slots.header" #header>
      <slot name="header" />
    </template>

    <slot />

    <template v-if="$slots.footer" #footer>
      <div class="admin-dialog__footer-actions">
        <slot name="footer" />
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
:global(.admin-dialog) {
  --el-color-primary: var(--admin-primary);
  --el-color-primary-light-3: var(--admin-primary-light);
  --el-color-primary-light-5: var(--admin-primary-light);
  --el-color-primary-light-7: var(--admin-primary-border);
  --el-color-primary-light-9: var(--admin-primary-soft);
  --el-color-primary-dark-2: var(--admin-primary-hover);
  overflow: hidden;
  border: 1px solid var(--admin-border);
  border-radius: var(--admin-radius-lg);
  box-shadow: 0 20px 48px rgba(15, 23, 42, 0.18);
}

:global(.admin-dialog .el-dialog__header) {
  display: flex;
  align-items: center;
  min-height: 54px;
  margin: 0;
  border-bottom: 1px solid var(--admin-border-soft);
  background: var(--admin-surface-muted);
  padding: 0 18px;
}

:global(.admin-dialog .el-dialog__title) {
  color: var(--admin-text);
  font-size: 15px;
  font-weight: 700;
}

:global(.admin-dialog .el-dialog__body) {
  padding: 18px;
}

:global(.admin-dialog .el-dialog__footer) {
  border-top: 1px solid var(--admin-border-soft);
  background: var(--admin-surface);
  padding: 12px 18px;
}

:global(.admin-dialog__footer-actions) {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

:global(.admin-dialog__scope) {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  border: 1px solid var(--admin-border);
  border-radius: var(--admin-radius-lg);
  background: var(--admin-surface-muted);
  padding: 12px 14px;
}

:global(.admin-dialog__scope--stacked) {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: stretch;
  gap: 12px;
}

:global(.admin-dialog__scope--stacked > div) {
  display: grid;
  min-width: 0;
  gap: 4px;
}

:global(.admin-dialog__scope-label) {
  color: var(--admin-text-muted);
  font-size: 13px;
}

:global(.admin-dialog__scope-value) {
  overflow: hidden;
  color: var(--admin-text);
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:global(.admin-dialog__form) {
  margin-top: 8px;
}

:global(.admin-dialog__hint) {
  margin: -4px 0 16px;
  color: var(--admin-text-muted);
  font-size: 13px;
  line-height: 1.6;
}
</style>
