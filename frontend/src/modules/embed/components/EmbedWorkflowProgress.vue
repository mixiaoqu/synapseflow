<script setup lang="ts">
import { computed } from "vue";
import { CircleCheckFilled, Loading, WarningFilled } from "@element-plus/icons-vue";

import {
  getCurrentWorkflowNode,
  getWorkflowRunMessage,
  getWorkflowRunVisibleNodes,
  type ChatWorkflowRun,
  type WorkflowNodeStatus,
} from "@/shared/lib/stream/workflowRun";

const props = defineProps<{
  run: ChatWorkflowRun | null;
}>();

const currentNode = computed(() => getCurrentWorkflowNode(props.run));
const currentMessage = computed(() => getWorkflowRunMessage(props.run));
const visibleNodes = computed(() => getWorkflowRunVisibleNodes(props.run, 5));

function statusLabel(status: WorkflowNodeStatus) {
  if (status === "success") {
    return "完成";
  }
  if (status === "error") {
    return "失败";
  }
  if (status === "skipped") {
    return "跳过";
  }
  return "进行中";
}
</script>

<template>
  <div
    v-if="run"
    class="embed-workflow-progress"
    :class="`is-${run.status}`"
  >
    <div class="embed-workflow-progress__headline">
      <div class="embed-workflow-progress__icon">
        <el-icon v-if="run.status === 'error'"><WarningFilled /></el-icon>
        <el-icon v-else-if="run.status === 'done'"><CircleCheckFilled /></el-icon>
        <el-icon v-else class="is-loading"><Loading /></el-icon>
      </div>
      <div class="embed-workflow-progress__text">
        <strong>{{ currentNode?.name || "正在处理" }}</strong>
        <span>{{ currentMessage || "正在处理你的问题" }}</span>
      </div>
    </div>

    <div
      v-if="visibleNodes.length > 0"
      class="embed-workflow-progress__steps"
    >
      <div
        v-for="node in visibleNodes"
        :key="`${node.workflowId}-${node.id}`"
        class="embed-workflow-progress__step"
        :class="`is-${node.status}`"
      >
        <span class="embed-workflow-progress__step-dot" />
        <span class="embed-workflow-progress__step-workflow">{{ node.workflowName }}</span>
        <span class="embed-workflow-progress__step-name">{{ node.name }}</span>
        <span class="embed-workflow-progress__step-status">{{ statusLabel(node.status) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.embed-workflow-progress {
  width: min(360px, 100%);
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 14px 14px 14px 4px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

.embed-workflow-progress__headline {
  display: flex;
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
  font-size: 13px;
  line-height: 1.3;
  color: #0f172a;
}

.embed-workflow-progress__text span {
  font-size: 12px;
  line-height: 1.45;
  color: #64748b;
  word-break: break-word;
}

.embed-workflow-progress__steps {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
}

.embed-workflow-progress__step {
  display: grid;
  grid-template-columns: 8px minmax(58px, auto) minmax(0, 1fr) auto;
  align-items: center;
  gap: 7px;
  min-width: 0;
  color: #64748b;
  font-size: 11px;
  line-height: 1.3;
}

.embed-workflow-progress__step-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #cbd5e1;
}

.embed-workflow-progress__step.is-running .embed-workflow-progress__step-dot {
  background: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
}

.embed-workflow-progress__step.is-success .embed-workflow-progress__step-dot {
  background: #10b981;
}

.embed-workflow-progress__step.is-error .embed-workflow-progress__step-dot {
  background: #dc2626;
}

.embed-workflow-progress__step-workflow {
  overflow: hidden;
  color: #94a3b8;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.embed-workflow-progress__step-name {
  overflow: hidden;
  color: #334155;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.embed-workflow-progress__step-status {
  color: #94a3b8;
  white-space: nowrap;
}

.embed-workflow-progress__step.is-running .embed-workflow-progress__step-status {
  color: #2563eb;
}

.embed-workflow-progress__step.is-success .embed-workflow-progress__step-status {
  color: #059669;
}

.embed-workflow-progress__step.is-error .embed-workflow-progress__step-status {
  color: #dc2626;
}
</style>
