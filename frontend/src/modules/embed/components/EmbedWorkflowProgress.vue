<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  ArrowDown,
  ArrowUp,
  Check,
  CircleCheckFilled,
  Loading,
  WarningFilled,
} from "@element-plus/icons-vue";

import {
  getCurrentWorkflowDisplayStage,
  getWorkflowDisplayStages,
  getWorkflowRunMessage,
  type ChatWorkflowRun,
  type WorkflowDisplayStage,
  type WorkflowDisplayStageStatus,
} from "@/shared/lib/stream/workflowRun";

const props = defineProps<{
  run: ChatWorkflowRun | null;
}>();

const isDetailExpanded = ref(false);

const stages = computed(() => getWorkflowDisplayStages(props.run));
const currentStage = computed(() => getCurrentWorkflowDisplayStage(props.run));
const currentMessage = computed(() => getWorkflowRunMessage(props.run));
const shouldShowDetails = computed(() => isDetailExpanded.value || props.run?.status === "error");

const summaryTitle = computed(() => {
  if (props.run?.status === "error") {
    return "处理遇到问题";
  }
  if (props.run?.status === "done") {
    return "已完成";
  }
  if (currentStage.value?.title) {
    return `正在${currentStage.value.title}`;
  }
  return "正在处理您的问题";
});

const summaryDescription = computed(() => {
  if (props.run?.status === "error") {
    return currentMessage.value || "请稍后重试，或调整问题后再试。";
  }
  if (props.run?.status === "done") {
    return "回复已整理完成。";
  }
  return currentMessage.value || "请稍候，助手正在处理。";
});

watch(
  () => props.run?.id,
  () => {
    isDetailExpanded.value = false;
  },
);

function stageActivities(stage: WorkflowDisplayStage) {
  if (stage.status !== "running" && stage.status !== "error") {
    return [];
  }
  return stage.activities;
}

function statusLabel(status: WorkflowDisplayStageStatus) {
  if (status === "success") {
    return "完成";
  }
  if (status === "error") {
    return "失败";
  }
  if (status === "pending") {
    return "未开始";
  }
  return "进行中";
}
</script>

<template>
  <div
    v-if="run"
    class="embed-workflow-progress"
    :class="`is-${run.status}`"
    aria-live="polite"
  >
    <div class="embed-workflow-progress__summary">
      <div class="embed-workflow-progress__summary-main">
        <div class="embed-workflow-progress__icon">
          <el-icon v-if="run.status === 'error'"><WarningFilled /></el-icon>
          <el-icon v-else-if="run.status === 'done'"><CircleCheckFilled /></el-icon>
          <el-icon v-else class="is-loading"><Loading /></el-icon>
        </div>
        <div class="embed-workflow-progress__text">
          <strong>{{ summaryTitle }}</strong>
          <span>{{ summaryDescription }}</span>
        </div>
      </div>

      <button
        v-if="stages.length > 0"
        type="button"
        class="embed-workflow-progress__toggle"
        :aria-expanded="shouldShowDetails"
        @click="isDetailExpanded = !isDetailExpanded"
      >
        <span>{{ shouldShowDetails ? "收起过程" : "查看过程" }}</span>
        <el-icon>
          <ArrowUp v-if="shouldShowDetails" />
          <ArrowDown v-else />
        </el-icon>
      </button>
    </div>

    <div
      v-if="shouldShowDetails && stages.length > 0"
      class="embed-workflow-progress__stages"
    >
      <div
        v-for="stage in stages"
        :key="stage.id"
        class="embed-workflow-progress__stage"
        :class="`is-${stage.status}`"
      >
        <div class="embed-workflow-progress__stage-row">
          <span class="embed-workflow-progress__stage-title">{{ stage.title }}</span>
          <span
            class="embed-workflow-progress__stage-status"
            :aria-label="statusLabel(stage.status)"
            role="img"
          >
            <el-icon v-if="stage.status === 'success'"><Check /></el-icon>
            <span v-else class="embed-workflow-progress__stage-dot" />
          </span>
        </div>

        <div
          v-if="stageActivities(stage).length > 0"
          class="embed-workflow-progress__activities"
        >
          <div
            v-for="activity in stageActivities(stage)"
            :key="`${activity.at}-${activity.text}`"
            class="embed-workflow-progress__activity"
            :class="`is-${activity.status}`"
          >
            <span class="embed-workflow-progress__activity-dot" />
            <span>{{ activity.text }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.embed-workflow-progress {
  width: min(360px, 100%);
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 12px 12px 12px 4px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

.embed-workflow-progress__summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.embed-workflow-progress__summary-main {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
}

.embed-workflow-progress__icon {
  display: inline-flex;
  width: 24px;
  height: 24px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #eff6ff;
  color: #2563eb;
  flex-shrink: 0;
}

.embed-workflow-progress.is-done .embed-workflow-progress__icon {
  background: #ecfdf5;
  color: #059669;
}

.embed-workflow-progress.is-error .embed-workflow-progress__icon {
  background: #fef2f2;
  color: #dc2626;
}

.embed-workflow-progress__text {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.embed-workflow-progress__text strong {
  color: #0f172a;
  font-size: 13px;
  line-height: 1.3;
}

.embed-workflow-progress__text span {
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
  word-break: break-word;
}

.embed-workflow-progress__toggle {
  display: inline-flex;
  height: 24px;
  align-items: center;
  gap: 3px;
  border: 0;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  flex-shrink: 0;
  font-size: 11px;
  line-height: 1;
  padding: 0;
}

.embed-workflow-progress__toggle:hover {
  color: #2563eb;
}

.embed-workflow-progress__toggle .el-icon {
  font-size: 12px;
}

.embed-workflow-progress__stages {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
}

.embed-workflow-progress__stage {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;
}

.embed-workflow-progress__stage-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.embed-workflow-progress__stage-title {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.embed-workflow-progress__stage.is-success .embed-workflow-progress__stage-title {
  color: #94a3b8;
}

.embed-workflow-progress__stage.is-running .embed-workflow-progress__stage-title {
  color: #2563eb;
  font-weight: 700;
}

.embed-workflow-progress__stage.is-error .embed-workflow-progress__stage-title {
  color: #dc2626;
  font-weight: 700;
}

.embed-workflow-progress__stage.is-pending .embed-workflow-progress__stage-title {
  color: #cbd5e1;
}

.embed-workflow-progress__stage-status {
  display: inline-flex;
  width: 16px;
  height: 16px;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  flex-shrink: 0;
}

.embed-workflow-progress__stage-status .el-icon {
  color: #059669;
  font-size: 13px;
}

.embed-workflow-progress__stage-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #cbd5e1;
}

.embed-workflow-progress__stage.is-running .embed-workflow-progress__stage-dot {
  background: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
}

.embed-workflow-progress__stage.is-error .embed-workflow-progress__stage-dot {
  background: #dc2626;
  box-shadow: 0 0 0 4px rgba(220, 38, 38, 0.1);
}

.embed-workflow-progress__activities {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-left: 12px;
}

.embed-workflow-progress__activity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 7px;
  color: #64748b;
  font-size: 11px;
  line-height: 1.4;
}

.embed-workflow-progress__activity-dot {
  width: 6px;
  height: 6px;
  margin-top: 5px;
  border-radius: 50%;
  background: #94a3b8;
  flex-shrink: 0;
}

.embed-workflow-progress__activity.is-running .embed-workflow-progress__activity-dot {
  background: #2563eb;
  animation: workflow-activity-pulse 1.4s ease-in-out infinite;
}

.embed-workflow-progress__activity.is-completed {
  color: #94a3b8;
}

.embed-workflow-progress__activity.is-completed .embed-workflow-progress__activity-dot {
  background: #10b981;
}

.embed-workflow-progress__activity.is-error {
  color: #dc2626;
}

.embed-workflow-progress__activity.is-error .embed-workflow-progress__activity-dot {
  background: #dc2626;
}

@keyframes workflow-activity-pulse {
  0%,
  100% {
    opacity: 0.45;
  }
  50% {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .embed-workflow-progress__activity.is-running .embed-workflow-progress__activity-dot {
    animation: none;
  }
}
</style>
