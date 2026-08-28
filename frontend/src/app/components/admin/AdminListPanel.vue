<template>
  <section class="admin-list-panel">
    <slot />
  </section>
</template>

<style scoped>
.admin-list-panel {
  --admin-table-height: calc(100vh - 260px);
  overflow: hidden;
  border: 1px solid var(--admin-border);
  border-radius: var(--admin-radius-lg);
  background: var(--admin-surface);
  box-shadow: var(--admin-shadow-panel);
}

.admin-list-panel :deep(.el-button) {
  border-radius: var(--admin-radius-sm);
  font-weight: 500;
}

.admin-list-panel :deep(.el-button--primary:not(.is-link)) {
  border-color: var(--admin-primary);
  background: var(--admin-primary);
}

.admin-list-panel :deep(.el-button--primary:not(.is-link):hover),
.admin-list-panel :deep(.el-button--primary:not(.is-link):focus) {
  border-color: var(--admin-primary-hover);
  background: var(--admin-primary-hover);
}

.admin-list-panel :deep(.el-table) {
  --el-table-border-color: var(--admin-border-soft);
  --el-table-header-bg-color: var(--admin-surface-muted);
  --el-table-row-hover-bg-color: var(--admin-surface-muted);
  color: var(--admin-text-secondary);
  font-size: 13px;
}

.admin-list-panel :deep(.el-table th.el-table__cell) {
  background: var(--admin-surface-muted);
  color: var(--admin-text-secondary);
  font-weight: 700;
}

.admin-list-panel :deep(.el-table .el-table__cell) {
  border-bottom-color: var(--admin-border-soft);
}

.admin-list-panel :deep(.el-table__row) {
  transition: background-color 0.18s ease;
}

.admin-list-panel :deep(.el-table .el-button.is-link) {
  color: var(--admin-primary);
}

.admin-list-panel :deep(.el-table .el-button.is-link:hover) {
  color: var(--admin-primary-strong);
}

.admin-list-panel :deep(.el-table .el-button--danger.is-link) {
  color: var(--admin-danger);
}

.admin-list-panel :deep(.el-table .el-button--danger.is-link:hover) {
  color: var(--admin-danger-hover);
}

.admin-list-panel :deep(.el-tag) {
  border-radius: var(--admin-radius-sm);
  font-weight: 600;
}
</style>
