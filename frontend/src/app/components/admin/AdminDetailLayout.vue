<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    description?: string;
    loading?: boolean;
  }>(),
  {
    description: "",
    loading: false,
  },
);
</script>

<template>
  <section class="admin-detail-layout">
    <header class="admin-detail-layout__header">
      <div class="admin-detail-layout__heading">
        <p v-if="$slots.eyebrow" class="admin-detail-layout__eyebrow">
          <slot name="eyebrow" />
        </p>
        <h1>{{ title }}</h1>
        <p v-if="description" class="admin-detail-layout__description">{{ description }}</p>
        <div v-if="$slots.meta" class="admin-detail-layout__meta">
          <slot name="meta" />
        </div>
      </div>
      <div v-if="$slots.actions" class="admin-detail-layout__actions">
        <slot name="actions" />
      </div>
    </header>

    <div v-loading="loading" class="admin-detail-layout__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.admin-detail-layout {
  display: flex;
  min-height: 100%;
  flex-direction: column;
  gap: 16px;
}

.admin-detail-layout__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  border-bottom: 1px solid var(--admin-border-soft);
  padding-bottom: 16px;
}

.admin-detail-layout__heading {
  min-width: 0;
}

.admin-detail-layout__eyebrow {
  margin: 0 0 6px;
  color: var(--admin-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.admin-detail-layout h1 {
  margin: 0;
  color: var(--admin-text);
  font-size: 24px;
  line-height: 1.25;
}

.admin-detail-layout__description,
.admin-detail-layout__meta {
  margin: 8px 0 0;
  color: var(--admin-text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.admin-detail-layout__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.admin-detail-layout__actions {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.admin-detail-layout__body {
  min-height: 0;
  flex: 1;
}

@media (max-width: 720px) {
  .admin-detail-layout__header {
    flex-direction: column;
  }

  .admin-detail-layout__actions {
    justify-content: flex-start;
  }
}
</style>
