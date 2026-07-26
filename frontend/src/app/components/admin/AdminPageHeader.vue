<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    description?: string;
    eyebrow?: string;
  }>(),
  {
    description: "",
    eyebrow: "",
  },
);
</script>

<template>
  <header class="admin-page-header">
    <div class="admin-page-header__content">
      <p
        v-if="eyebrow"
        class="admin-page-header__eyebrow"
      >
        {{ eyebrow }}
      </p>
      <h1 class="admin-page-header__title">
        {{ title }}
      </h1>
      <p
        v-if="description"
        class="admin-page-header__description"
      >
        {{ description }}
      </p>
    </div>

    <div
      v-if="$slots.actions"
      class="admin-page-header__actions"
    >
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.admin-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  min-height: 58px;
}

.admin-page-header__content {
  min-width: 0;
}

.admin-page-header__eyebrow {
  margin: 0 0 4px;
  color: var(--admin-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.admin-page-header__title {
  margin: 0;
  color: var(--admin-text);
  font-size: 24px;
  font-weight: 750;
  line-height: 1.25;
}

.admin-page-header__description {
  margin: 6px 0 0;
  color: var(--admin-text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.admin-page-header__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 720px) {
  .admin-page-header {
    flex-direction: column;
    gap: 12px;
  }

  .admin-page-header__actions {
    justify-content: flex-start;
  }
}
</style>
