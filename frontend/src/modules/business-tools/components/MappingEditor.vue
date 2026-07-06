<script setup lang="ts">
import { computed } from "vue";
import { Delete, Plus } from "@element-plus/icons-vue";

interface MappingRow {
  target: string;
  source: string;
}

interface MappingOption {
  label: string;
  value: string;
  description?: string;
}

const props = defineProps<{
  title: string;
  description: string;
  targetPlaceholder?: string;
  sourcePlaceholder?: string;
  targetOptions?: MappingOption[];
  sourceOptions?: MappingOption[];
  targetAllowCreate?: boolean;
  sourceAllowCreate?: boolean;
}>();

const rows = defineModel<MappingRow[]>({ required: true });
const targetOptions = computed(() => props.targetOptions ?? []);
const sourceOptions = computed(() => props.sourceOptions ?? []);
const canCreateTarget = computed(() => props.targetAllowCreate ?? true);
const canCreateSource = computed(() => props.sourceAllowCreate ?? true);

function addRow() {
  rows.value.push({ target: "", source: "" });
}

function removeRow(index: number) {
  rows.value.splice(index, 1);
}
</script>

<template>
  <div class="mapping-editor">
    <div class="mapping-editor__header">
      <div>
        <h4>{{ title }}</h4>
        <p>{{ description }}</p>
      </div>
      <el-button plain size="small" @click="addRow">
        <el-icon><Plus /></el-icon>
        添加映射
      </el-button>
    </div>

    <div v-if="rows.length" class="mapping-editor__rows">
      <div class="mapping-editor__columns" aria-hidden="true">
        <span>目标字段</span>
        <span></span>
        <span>来源字段</span>
        <span></span>
      </div>

      <div v-for="(row, index) in rows" :key="index" class="mapping-editor__row">
        <el-select
          v-model="row.target"
          filterable
          clearable
          default-first-option
          :allow-create="canCreateTarget"
          :placeholder="targetPlaceholder || '目标字段'"
        >
          <el-option
            v-for="item in targetOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          >
            <div class="mapping-editor__option">
              <strong>{{ item.label }}</strong>
              <small>{{ item.description || item.value }}</small>
            </div>
          </el-option>
        </el-select>
        <span class="mapping-editor__arrow" aria-hidden="true">←</span>
        <el-select
          v-model="row.source"
          filterable
          clearable
          default-first-option
          :allow-create="canCreateSource"
          :placeholder="sourcePlaceholder || '来源路径，例如 params.keyword'"
        >
          <el-option
            v-for="item in sourceOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          >
            <div class="mapping-editor__option">
              <strong>{{ item.label }}</strong>
              <small>{{ item.description || item.value }}</small>
            </div>
          </el-option>
        </el-select>
        <el-button text type="danger" :aria-label="`删除第 ${index + 1} 条映射`" @click="removeRow(index)">
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </div>
    <button v-else type="button" class="mapping-editor__empty" @click="addRow">
      暂无自定义映射，点击添加；留空时将沿用默认数据结构。
    </button>
  </div>
</template>

<style scoped>
.mapping-editor {
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-md);
  background: var(--admin-surface);
}

.mapping-editor__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--admin-border-soft);
  padding: 14px 16px;
}

.mapping-editor__header h4 {
  margin: 0;
  color: var(--admin-text);
  font-size: 14px;
}

.mapping-editor__header p {
  margin: 4px 0 0;
  color: var(--admin-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.mapping-editor__rows {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
}

.mapping-editor__columns,
.mapping-editor__row {
  display: grid;
  grid-template-columns: minmax(150px, 0.8fr) 20px minmax(220px, 1.2fr) 32px;
  align-items: center;
  gap: 8px;
}

.mapping-editor__columns {
  color: var(--admin-text-muted);
  font-size: 12px;
}

.mapping-editor__columns span:nth-child(2),
.mapping-editor__columns span:last-child {
  visibility: hidden;
}

.mapping-editor__arrow {
  color: var(--admin-text-subtle);
  text-align: center;
}

.mapping-editor__option {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.mapping-editor__option strong {
  color: var(--admin-text);
  font-size: 13px;
  font-weight: 500;
}

.mapping-editor__option small {
  overflow: hidden;
  color: var(--admin-text-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mapping-editor__empty {
  width: 100%;
  border: 0;
  background: var(--admin-surface-muted);
  padding: 18px;
  color: var(--admin-text-muted);
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  text-align: left;
}

.mapping-editor__empty:hover {
  color: var(--admin-primary);
}

@media (max-width: 760px) {
  .mapping-editor__header {
    align-items: stretch;
    flex-direction: column;
  }

  .mapping-editor__columns {
    display: none;
  }

  .mapping-editor__row {
    grid-template-columns: 1fr 28px;
  }

  .mapping-editor__row :deep(.el-select):first-child,
  .mapping-editor__row :deep(.el-select):nth-of-type(2) {
    grid-column: 1;
  }

  .mapping-editor__arrow {
    display: none;
  }

  .mapping-editor__row :deep(.el-button) {
    grid-column: 2;
    grid-row: 1 / span 2;
  }
}
</style>
