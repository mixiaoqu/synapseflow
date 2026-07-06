<script setup lang="ts">
import { Delete, Plus } from "@element-plus/icons-vue";

import type {
  BusinessApiFieldType,
  BusinessApiRequestFieldLocation,
  BusinessApiRequestFieldSpec,
} from "@/shared/types/business-tool";

const rows = defineModel<BusinessApiRequestFieldSpec[]>({ required: true });

const locationOptions: Array<{ label: string; value: BusinessApiRequestFieldLocation }> = [
  { label: "Query", value: "query" },
  { label: "Path", value: "path" },
  { label: "Header", value: "header" },
  { label: "Body", value: "body" },
];

const typeOptions: Array<{ label: string; value: BusinessApiFieldType }> = [
  { label: "字符串", value: "string" },
  { label: "数字", value: "number" },
  { label: "布尔", value: "boolean" },
  { label: "数组", value: "array" },
  { label: "对象", value: "object" },
];

function createEmptyField(): BusinessApiRequestFieldSpec {
  return {
    name: "",
    label: "",
    in: "query",
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
        <h4>请求字段</h4>
        <p>描述外部接口真正接收的参数结构，工具实现层再去做字段映射。</p>
      </div>
      <el-button plain size="small" @click="addField">
        <el-icon><Plus /></el-icon>
        添加字段
      </el-button>
    </div>

    <div v-if="rows.length" class="api-schema-editor__rows">
      <div class="api-schema-editor__columns" aria-hidden="true">
        <span>字段名</span>
        <span>显示名</span>
        <span>位置</span>
        <span>类型</span>
        <span>必填</span>
        <span>字段说明</span>
        <span></span>
      </div>

      <div v-for="(field, index) in rows" :key="index" class="api-schema-editor__row">
        <el-input v-model="field.name" placeholder="字段名，如 store_id" />
        <el-input v-model="field.label" placeholder="显示名" />
        <el-select v-model="field.in">
          <el-option v-for="item in locationOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="field.type">
          <el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-checkbox v-model="field.required">必填</el-checkbox>
        <el-input v-model="field.description" placeholder="说明字段含义和来源提示" />
        <el-button text type="danger" :aria-label="`删除第 ${index + 1} 个请求字段`" @click="removeField(index)">
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>

      <div class="api-schema-editor__meta">
        <p class="api-schema-editor__hint">
          如果某个字段不是由用户输入，而是由连接鉴权、应用上下文或业务侧统一注入，可以在“字段说明”里直接注明来源。
        </p>
      </div>
    </div>

    <button v-else type="button" class="api-schema-editor__empty" @click="addField">
      暂无请求字段，点击添加。建议先把 query / header / body / path 字段结构描述清楚。
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
  grid-template-columns: minmax(150px, 0.9fr) minmax(140px, 0.9fr) 120px 120px 72px minmax(220px, 1.6fr) 32px;
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
    grid-row: 1 / span 6;
  }
}
</style>
