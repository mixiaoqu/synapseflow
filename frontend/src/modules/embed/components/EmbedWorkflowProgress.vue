<script setup lang="ts">
import { computed, ref } from "vue";
import { Check, Loading, WarningFilled } from "@element-plus/icons-vue";

import {
  getWorkflowDisplayStages,
  type ChatWorkflowRun,
  type WorkflowDisplayStage,
  type WorkflowDisplayStageStatus,
} from "@/shared/lib/stream/workflowRun";

const props = defineProps<{
  run: ChatWorkflowRun | null;
}>();

const isExpanded = ref(false);
const stages = computed(() => getWorkflowDisplayStages(props.run));

const visibleStages = computed(() => {
  return stages.value.filter((stage) => stage.status !== "pending");
});

const currentSummary = computed(() => {
  if (props.run?.status === "done") {
    return "任务已完成";
  }

  if (props.run?.status === "error") {
    return props.run.error?.message || "处理遇到问题，请稍后重试。";
  }

  const runningStage = visibleStages.value.find((stage) => stage.status === "running");
  if (runningStage) {
    return `正在执行：${runningStage.title}`;
  }

  const latestStage = visibleStages.value[visibleStages.value.length - 1];
  if (latestStage) {
    return `正在执行：${latestStage.title}`;
  }

  return props.run?.message || "正在处理你的问题";
});

const summaryStatus = computed(() => {
  if (props.run?.status === "done") {
    return "completed";
  }
  if (props.run?.status === "error") {
    return "error";
  }
  return "running";
});

function stageActivities(stage: WorkflowDisplayStage) {
  return stage.activities;
}

function stageText(stage: WorkflowDisplayStage) {
  const activities = stageActivities(stage);
  return activities[activities.length - 1]?.text || stage.title;
}

function stageDetail(stage: WorkflowDisplayStage) {
  const text = stageText(stage);
  return text && text !== stage.title ? text : "";
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
    v-if="run && (visibleStages.length > 0 || run.status === 'done' || run.status === 'error')"
    class="embed-workflow-progress"
    :class="`is-${run.status}`"
    aria-live="polite"
  >
    <button
      type="button"
      class="embed-workflow-progress__summary-button"
      :aria-expanded="isExpanded"
      @click="isExpanded = !isExpanded"
    >
      <span
        class="embed-workflow-progress__mark"
        :class="`is-${summaryStatus}`"
        aria-hidden="true"
      >
        <el-icon v-if="summaryStatus === 'completed'">
          <Check />
        </el-icon>
        <el-icon v-else-if="summaryStatus === 'error'">
          <WarningFilled />
        </el-icon>
        <el-icon
          v-else
          class="is-loading"
        >
          <Loading />
        </el-icon>
      </span>
      <span class="embed-workflow-progress__summary-text">
        {{ currentSummary }}
      </span>
      <span
        class="embed-workflow-progress__chevron"
        :class="{ 'is-expanded': isExpanded }"
        aria-hidden="true"
      />
    </button>

    <div
      v-if="isExpanded && visibleStages.length > 0"
      class="embed-workflow-progress__stages"
    >
      <div
        v-for="stage in visibleStages"
        :key="stage.id"
        class="embed-workflow-progress__stage"
        :class="`is-${stage.status}`"
      >
        <span
          class="embed-workflow-progress__stage-status"
          :aria-label="statusLabel(stage.status)"
          role="img"
        >
          <el-icon v-if="stage.status === 'success'">
            <Check />
          </el-icon>
          <el-icon
            v-else-if="stage.status === 'running'"
            class="is-loading"
          >
            <Loading />
          </el-icon>
          <el-icon v-else-if="stage.status === 'error'">
            <WarningFilled />
          </el-icon>
          <span
            v-else
            class="embed-workflow-progress__stage-dot"
          />
        </span>

        <div class="embed-workflow-progress__stage-copy">
          <div class="embed-workflow-progress__stage-row">
            <span class="embed-workflow-progress__stage-title">{{ stage.title }}</span>
            <span class="embed-workflow-progress__stage-label">
              {{ statusLabel(stage.status) }}
            </span>
          </div>
          <span
            v-if="stageDetail(stage)"
            class="embed-workflow-progress__stage-detail"
          >
            {{ stageDetail(stage) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.embed-workflow-progress {
  display: flex;
  width: min(420px, 100%);
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(203, 213, 225, 0.72);
  border-radius: 14px;
  background: #ffffff;
  color: #1e293b;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
}

.embed-workflow-progress__summary-button {
  display: inline-flex;
  width: 100%;
  max-width: 100%;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  border: 0;
  background: transparent;
  color: #334155;
  cursor: pointer;
  font: inherit;
  line-height: 1;
  transition:
    background 0.18s ease,
    color 0.18s ease;
}

.embed-workflow-progress__summary-button:hover {
  background: #f8fafc;
  color: #0f172a;
}

.embed-workflow-progress__summary-button:focus-visible {
  outline: 2px solid #93c5fd;
  outline-offset: 2px;
}

.embed-workflow-progress__mark {
  display: inline-flex;
  width: 16px;
  height: 16px;
  align-items: center;
  justify-content: center;
  color: #2563eb;
  flex-shrink: 0;
}

.embed-workflow-progress__mark :deep(.el-icon) {
  font-size: 13px;
}

.embed-workflow-progress__mark.is-completed {
  color: #059669;
}

.embed-workflow-progress__mark.is-error {
  color: #dc2626;
}

.embed-workflow-progress__summary-text {
  min-width: 0;
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.embed-workflow-progress__chevron {
  width: 6px;
  height: 6px;
  margin-left: auto;
  border-right: 1.5px solid #64748b;
  border-bottom: 1.5px solid #64748b;
  transform: rotate(45deg) translateY(-1px);
  transition: transform 0.18s ease;
  flex-shrink: 0;
}

.embed-workflow-progress__chevron.is-expanded {
  transform: rotate(225deg) translateY(-1px);
}

.embed-workflow-progress__stages {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 14px 18px 14px 20px;
  border-top: 1px solid #edf2f7;
  background: #f8fafc;
}

.embed-workflow-progress__stages::before {
  position: absolute;
  top: 20px;
  bottom: 20px;
  left: 26px;
  width: 1px;
  border-radius: 999px;
  background: #dbe3ee;
  content: "";
}

.embed-workflow-progress__stage {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 14px minmax(0, 1fr);
  align-items: flex-start;
  column-gap: 10px;
  min-width: 0;
  padding: 0;
  border: 0;
  background: transparent;
}

.embed-workflow-progress__stage-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.embed-workflow-progress__stage-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.embed-workflow-progress__stage-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.embed-workflow-progress__stage-title {
  color: #1e293b;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.35;
}

.embed-workflow-progress__stage-detail {
  overflow: hidden;
  color: #64748b;
  font-size: 11.5px;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.embed-workflow-progress__stage-label {
  display: none;
}

.embed-workflow-progress__stage.is-success .embed-workflow-progress__stage-title {
  color: #475569;
}

.embed-workflow-progress__stage.is-success .embed-workflow-progress__stage-label {
  background: #ecfdf5;
  color: #047857;
}

.embed-workflow-progress__stage.is-running .embed-workflow-progress__stage-title {
  color: #1d4ed8;
}

.embed-workflow-progress__stage.is-error .embed-workflow-progress__stage-title {
  color: #dc2626;
  font-weight: 600;
}

.embed-workflow-progress__stage.is-error .embed-workflow-progress__stage-label {
  background: #fee2e2;
  color: #b91c1c;
}

.embed-workflow-progress__stage.is-pending .embed-workflow-progress__stage-title {
  color: #cbd5e1;
}

.embed-workflow-progress__stage-status {
  display: inline-flex;
  width: 10px;
  height: 10px;
  align-items: center;
  justify-content: center;
  margin-top: 4px;
  border-radius: 999px;
  background: #f8fafc;
  color: #94a3b8;
  flex-shrink: 0;
}

.embed-workflow-progress__stage-status .el-icon {
  font-size: 12px;
  background: #f8fafc;
}

.embed-workflow-progress__stage.is-success .embed-workflow-progress__stage-status .el-icon {
  color: #059669;
}

.embed-workflow-progress__stage.is-running .embed-workflow-progress__stage-status .el-icon {
  color: #2563eb;
}

.embed-workflow-progress__stage.is-error .embed-workflow-progress__stage-status .el-icon {
  color: #dc2626;
}

.embed-workflow-progress__stage-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;
}

@media (max-width: 768px) {
  .embed-workflow-progress {
    width: 100%;
  }

  .embed-workflow-progress__stages {
    width: 100%;
  }
}
</style>
