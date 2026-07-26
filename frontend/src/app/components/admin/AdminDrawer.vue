<script setup lang="ts">
defineOptions({
  inheritAttrs: false,
});

withDefaults(
  defineProps<{
    modelValue: boolean;
    title?: string;
    size?: string | number;
    direction?: "ltr" | "rtl" | "ttb" | "btt";
    loading?: boolean;
    destroyOnClose?: boolean;
    closeOnClickModal?: boolean;
  }>(),
  {
    title: "详情",
    size: "720px",
    direction: "rtl",
    loading: false,
    destroyOnClose: true,
    closeOnClickModal: true,
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  closed: [];
}>();
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    :title="title"
    :size="size"
    :direction="direction"
    :destroy-on-close="destroyOnClose"
    :close-on-click-modal="closeOnClickModal"
    :close-on-press-escape="!loading"
    class="admin-drawer"
    v-bind="$attrs"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="emit('closed')"
  >
    <template v-if="$slots.header" #header>
      <slot name="header" />
    </template>

    <slot />

    <template v-if="$slots.footer" #footer>
      <div class="admin-drawer__footer-actions">
        <slot name="footer" />
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
:global(.admin-drawer) {
  --el-color-primary: var(--admin-primary);
  --el-color-primary-light-3: var(--admin-primary-light);
  --el-color-primary-light-5: var(--admin-primary-light);
  --el-color-primary-light-7: var(--admin-primary-border);
  --el-color-primary-light-9: var(--admin-primary-soft);
  --el-color-primary-dark-2: var(--admin-primary-hover);
  overflow: hidden;
  border-left: 1px solid var(--admin-border);
  box-shadow: -20px 0 48px rgba(15, 23, 42, 0.12);
}

:global(.admin-drawer .el-drawer__header) {
  min-height: 58px;
  margin: 0;
  border-bottom: 1px solid var(--admin-border-soft);
  background: var(--admin-surface-muted);
  padding: 0 20px;
}

:global(.admin-drawer .el-drawer__title) {
  color: var(--admin-text);
  font-size: 16px;
  font-weight: 700;
}

:global(.admin-drawer .el-drawer__body) {
  background: var(--admin-bg);
  padding: 20px;
}

:global(.admin-drawer .el-drawer__footer) {
  border-top: 1px solid var(--admin-border-soft);
  background: var(--admin-surface);
  padding: 12px 20px;
}

:global(.admin-drawer__footer-actions) {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
