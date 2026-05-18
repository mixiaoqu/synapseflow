<script setup lang="ts">
import { computed } from "vue";

type TagType = "" | "primary" | "success" | "warning" | "info" | "danger";

const STATUS_PRESET: Record<string, { label: string; type: TagType }> = {
  active: { label: "启用", type: "success" },
  archived: { label: "已归档", type: "info" },
  danger: { label: "风险", type: "danger" },
  draft: { label: "草稿", type: "info" },
  error: { label: "异常", type: "danger" },
  inactive: { label: "停用", type: "info" },
  pending: { label: "待处理", type: "warning" },
  primary: { label: "进行中", type: "primary" },
  published: { label: "已发布", type: "success" },
  success: { label: "成功", type: "success" },
  warning: { label: "注意", type: "warning" },
};

const props = withDefaults(
  defineProps<{
    status?: string;
    label?: string;
    type?: TagType;
    effect?: "light" | "dark" | "plain";
    round?: boolean;
  }>(),
  {
    status: "info",
    label: "",
    type: "",
    effect: "light",
    round: true,
  },
);

const normalizedStatus = computed(() => props.status.trim().toLowerCase());
const preset = computed(() => STATUS_PRESET[normalizedStatus.value]);
const resolvedType = computed(() => props.type || preset.value?.type || "info");
const resolvedLabel = computed(() => props.label || preset.value?.label || props.status);
</script>

<template>
  <el-tag
    :type="resolvedType"
    :effect="effect"
    :round="round"
  >
    {{ resolvedLabel }}
  </el-tag>
</template>
