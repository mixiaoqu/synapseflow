<template>
  <div class="admin-table-toolbar">
    <div class="admin-table-toolbar__main">
      <slot name="left" />
    </div>
    <div class="admin-table-toolbar__side">
      <slot name="right" />
    </div>
  </div>
</template>

<style scoped>
.admin-table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--admin-border-soft);
  background: var(--admin-surface-muted);
  padding: 12px;
  flex-wrap: wrap;
}

.admin-table-toolbar__main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.admin-table-toolbar__side {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.admin-table-toolbar :deep(.el-input__wrapper),
.admin-table-toolbar :deep(.el-select__wrapper) {
  border-radius: var(--admin-radius-sm);
  background: var(--admin-surface);
  box-shadow: 0 0 0 1px var(--admin-border) inset;
}

.admin-table-toolbar :deep(.el-input__wrapper:hover),
.admin-table-toolbar :deep(.el-select__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--admin-text-subtle) inset;
}

.admin-table-toolbar :deep(.el-input__wrapper.is-focus),
.admin-table-toolbar :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px var(--admin-primary) inset;
}

@media (max-width: 768px) {
  .admin-table-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .admin-table-toolbar__main {
    align-items: stretch;
  }

  .admin-table-toolbar__side {
    justify-content: stretch;
  }
}
</style>
