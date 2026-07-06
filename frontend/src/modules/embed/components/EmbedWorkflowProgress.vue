<script setup lang="ts">
import { computed } from "vue";
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

const stages = computed(() => getWorkflowDisplayStages(props.run));

const visibleStages = computed(() => {
  if (props.run?.status === "done") {
    return [];
  }
  return stages.value.filter((stage) => stage.status !== "pending");
});

function stageActivities(stage: WorkflowDisplayStage) {
  return stage.activities;
}

function stageText(stage: WorkflowDisplayStage) {
  return stageActivities(stage)[0]?.text || stage.title;
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
    v-if="run && run.status !== 'done' && visibleStages.length > 0"
    class="embed-workflow-progress"
    :class="`is-${run.status}`"
    aria-live="polite"
  >
    <div class="embed-workflow-progress__stages">
      <div
        v-for="stage in visibleStages"
        :key="stage.id"
        class="embed-workflow-progress__stage"
        :class="`is-${stage.status}`"
      >
        <div class="embed-workflow-progress__stage-row">
          <span
            class="embed-workflow-progress__stage-status"
            :aria-label="statusLabel(stage.status)"
            role="img"
          >
            <el-icon v-if="stage.status === 'success'"><Check /></el-icon>
            <el-icon v-else-if="stage.status === 'running'" class="is-loading"><Loading /></el-icon>
            <el-icon v-else-if="stage.status === 'error'"><WarningFilled /></el-icon>
            <span v-else class="embed-workflow-progress__stage-dot" />
          </span>

          <div class="embed-workflow-progress__stage-copy">
            <span class="embed-workflow-progress__stage-title">{{ stageText(stage) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.embed-workflow-progress {
  display: flex;
  width: min(560px, 100%);
  flex-direction: column;
  gap: 8px;
  color: #1e293b;
}

.embed-workflow-progress__stages {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: fit-content;
  max-width: 100%;
  min-width: min(300px, 100%);
  margin-left: 8px;
  padding-left: 16px;
  border-left: 2px solid #e2e8f0;
}

.embed-workflow-progress__stage {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.embed-workflow-progress__stage-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}

.embed-workflow-progress__stage-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.embed-workflow-progress__stage-title {
  overflow: hidden;
  color: #334155;
  font-size: 12.5px;
  font-weight: 500;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.embed-workflow-progress__stage.is-success .embed-workflow-progress__stage-title {
  color: #94a3b8;
}

.embed-workflow-progress__stage.is-running .embed-workflow-progress__stage-title {
  color: #4f46e5;
}

.embed-workflow-progress__stage.is-error .embed-workflow-progress__stage-title {
  color: #dc2626;
  font-weight: 600;
}

.embed-workflow-progress__stage.is-pending .embed-workflow-progress__stage-title {
  color: #cbd5e1;
}

.embed-workflow-progress__stage-status {
  display: inline-flex;
  width: 14px;
  height: 14px;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
  color: #94a3b8;
  flex-shrink: 0;
}

.embed-workflow-progress__stage-status .el-icon {
  font-size: 12px;
}

.embed-workflow-progress__stage.is-success .embed-workflow-progress__stage-status .el-icon {
  color: #10b981;
}

.embed-workflow-progress__stage.is-running .embed-workflow-progress__stage-status .el-icon {
  color: #818cf8;
}

.embed-workflow-progress__stage.is-error .embed-workflow-progress__stage-status .el-icon {
  color: #dc2626;
}

.embed-workflow-progress__stage-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #818cf8;
}

</style>
