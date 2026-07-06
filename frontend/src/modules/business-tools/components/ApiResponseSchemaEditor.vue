<script setup lang="ts">
import { Delete, Plus } from "@element-plus/icons-vue";

import type { BusinessApiFieldType, BusinessApiResponseFieldSpec } from "@/shared/types/business-tool";

const rows = defineModel<BusinessApiResponseFieldSpec[]>({ required: true });

const typeOptions: Array<{ label: string; value: BusinessApiFieldType }> = [
  { label: "字符串", value: "string" },
  { label: "数字", value: "number" },
  { label: "布尔", value: "boolean" },
  { label: "数组", value: "array" },
  { label: "对象", value: "object" },
];

function createEmptyField(): BusinessApiResponseFieldSpec {
  return {
    path: "",
    label: "",
    type: "string",
    required: false,
    description: "",
  };
}

function addField() {
  rows.value.push(createEmptyField());
}

function removeField(index: number) {
  rows.value.splice(index, 1);
}
</script>

<template>
  <div class="api-schema-editor">
    <div class="api-schema-editor__header">
      <div>
        <h4>响应字段</h4>
        <p>使用稳定路径描述接口真实返回，后续响应映射可以直接引用这些字段。</p>
      </div>
      <el-button plain size="small" @click="addField">
        <el-icon><Plus /></el-icon>
        添加字段
      </el-button>
    </div>

    <div v-if="rows.length" class="api-schema-editor__rows">
      <div class="api-schema-editor__columns" aria-hidden="true">
        <span>字段路径</span>
        <span>显示名</span>
        <span>类型</span>
        <span>必返</span>
        <span>字段说明</span>
        <span></span>
      </div>

      <div v-for="(field, index) in rows" :key="index" class="api-schema-editor__row">
        <el-input v-model="field.path" placeholder="例如 result[].name" />
        <el-input v-model="field.label" placeholder="显示名" />
        <el-select v-model="field.type">
          <el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-checkbox v-model="field.required">必返</el-checkbox>
        <el-input v-model="field.description" placeholder="说明字段含义和用途" />
        <el-button text type="danger" :aria-label="`删除第 ${index + 1} 个响应字段`" @click="removeField(index)">
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>

      <div class="api-schema-editor__meta">
        <p class="api-schema-editor__hint">
          路径建议直接使用稳定返回结构，例如 <code>result[].name</code>、<code>count</code>、<code>page</code>。
        </p>
      </div>
    </div>

    <button v-else type="button" class="api-schema-editor__empty" @click="addField">
      暂无响应字段，点击添加。建议把结果列表、分页信息和关键业务字段都描述清楚。
    </button>
  </div>
</template>

<style scoped>
.api-schema-editor {
  border: 1px solid var(--admin-border-soft);
  border-radius: var(--admin-radius-md);
  background: var(--admin-surface);
}

.api-schema-editor__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--admin-border-soft);
  padding: 14px 16px;
}

.api-schema-editor__header h4 {
  margin: 0;
  color: var(--admin-text);
  font-size: 14px;
}

.api-schema-editor__header p {
  margin: 4px 0 0;
  color: var(--admin-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.api-schema-editor__rows {
  display: grid;
  gap: 12px;
  padding: 14px 16px;
}

.api-schema-editor__columns,
.api-schema-editor__row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(140px, 0.9fr) 120px 72px minmax(220px, 1.5fr) 32px;
  align-items: center;
  gap: 8px;
}

.api-schema-editor__columns {
  color: var(--admin-text-muted);
  font-size: 12px;
}

.api-schema-editor__columns span:last-child {
  visibility: hidden;
}

.api-schema-editor__meta {
  padding-top: 4px;
}

.api-schema-editor__hint {
  margin: 0;
  color: var(--admin-text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.api-schema-editor__hint code {
  font-family: Consolas, "Courier New", monospace;
}

.api-schema-editor__empty {
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

.api-schema-editor__empty:hover {
  color: var(--admin-primary);
}

@media (max-width: 760px) {
  .api-schema-editor__header {
    align-items: stretch;
    flex-direction: column;
  }

  .api-schema-editor__columns {
    display: none;
  }

  .api-schema-editor__row {
    grid-template-columns: 1fr 32px;
  }

  .api-schema-editor__row > :not(:last-child) {
    grid-column: 1;
  }

  .api-schema-editor__row > :last-child {
    grid-column: 2;
    grid-row: 1 / span 5;
  }
}
</style>
