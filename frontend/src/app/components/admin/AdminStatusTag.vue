<script setup lang="ts">
import { computed } from "vue";

type TagType = "" | "primary" | "success" | "warning" | "info" | "danger";

const STATUS_PRESETS: Record<string, { label: string; type: TagType }> = {
  active: { label: "启用", type: "success" },
  archived: { label: "已归档", type: "info" },
  cancelled: { label: "已取消", type: "info" },
  completed: { label: "已完成", type: "success" },
  danger: { label: "风险", type: "danger" },
  disabled: { label: "禁用", type: "info" },
  draft: { label: "草稿", type: "info" },
  enabled: { label: "已启用", type: "success" },
  error: { label: "异常", type: "danger" },
  failed: { label: "失败", type: "danger" },
  inactive: { label: "停用", type: "info" },
  indexing: { label: "索引中", type: "primary" },
  no_hits: { label: "无命中", type: "warning" },
  ok: { label: "正常", type: "success" },
  pending: { label: "待处理", type: "warning" },
  processing: { label: "处理中", type: "primary" },
  published: { label: "已发布", type: "success" },
  queued: { label: "排队中", type: "warning" },
  rejected: { label: "已拒绝", type: "danger" },
  review: { label: "待审核", type: "warning" },
  running: { label: "运行中", type: "primary" },
  skipped: { label: "已跳过", type: "info" },
  success: { label: "成功", type: "success" },
  unpublished: { label: "未发布", type: "info" },
  warning: { label: "注意", type: "warning" },
};

const props = withDefaults(
  defineProps<{
    status?: string;
    label?: string;
    type?: TagType;
    effect?: "light" | "dark" | "plain";
    round?: boolean;
    size?: "large" | "default" | "small";
  }>(),
  {
    status: "unknown",
    label: "",
    type: "",
    effect: "light",
    round: true,
    size: "small",
  },
);

const normalizedStatus = computed(() => props.status.trim().toLowerCase());
const preset = computed(() => STATUS_PRESETS[normalizedStatus.value]);
const resolvedType = computed(() => props.type || preset.value?.type || "info");
const resolvedLabel = computed(() => props.label || preset.value?.label || props.status || "未知");
</script>

<template>
  <el-tag
    :type="resolvedType"
    :effect="effect"
    :round="round"
    :size="size"
  >
    {{ resolvedLabel }}
  </el-tag>
</template>
