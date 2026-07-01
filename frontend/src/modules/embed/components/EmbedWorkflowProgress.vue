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
  getCurrentWorkflowNode,
  getWorkflowRunMessage,
  getWorkflowRunVisibleNodes,
  type ChatWorkflowRun,
  type WorkflowNodeDisplayItem,
  type WorkflowNodeStatus,
} from "@/shared/lib/stream/workflowRun";

const props = defineProps<{
  run: ChatWorkflowRun | null;
}>();

interface WorkflowGroup {
  id: string;
  name: string;
  status: WorkflowNodeStatus;
  nodes: WorkflowNodeDisplayItem[];
}

const isDetailExpanded = ref(false);

const currentNode = computed(() => getCurrentWorkflowNode(props.run));
const currentMessage = computed(() => getWorkflowRunMessage(props.run));
const visibleNodes = computed(() => getWorkflowRunVisibleNodes(props.run, 8));
const currentDisplayNode = computed(() => {
  if (!props.run?.currentWorkflowId || !props.run.currentNodeId) {
    return null;
  }
  return (
    visibleNodes.value.find(
      (node) =>
        node.workflowId === props.run?.currentWorkflowId &&
        node.id === props.run.currentNodeId,
    ) ?? null
  );
});
const workflowGroups = computed(() => {
  const groups: Array<Omit<WorkflowGroup, "status">> = [];
  const groupById = new Map<string, (typeof groups)[number]>();

  for (const node of visibleNodes.value) {
    let group = groupById.get(node.workflowId);
    if (!group) {
      group = {
        id: node.workflowId,
        name: workflowLabel(node.workflowId, node.workflowName),
        nodes: [],
      };
      groupById.set(node.workflowId, group);
      groups.push(group);
    }
    group.nodes.push({
      ...node,
      name: nodeLabel(node),
    });
  }

  return groups.map((group) => ({
    ...group,
    status: resolveGroupStatus(group.nodes),
  }));
});
const shouldShowDetails = computed(() => isDetailExpanded.value || props.run?.status === "error");
const summaryTitle = computed(() => {
  if (props.run?.status === "error") {
    return "处理遇到问题";
  }
  if (props.run?.status === "done") {
    return "已完成";
  }

  const node = currentDisplayNode.value;
  if (!node) {
    return currentNode.value?.name || "正在处理你的问题";
  }
  return activeTitle(node);
});
const summaryDescription = computed(() => {
  if (props.run?.status === "error") {
    return currentMessage.value || "请稍后重试，或调整问题后再试。";
  }
  if (props.run?.status === "done") {
    return "已根据知识库整理回复。";
  }

  const node = currentDisplayNode.value;
  if (!node) {
    return currentMessage.value || "请稍候，正在处理。";
  }
  return activeDescription(node);
});

watch(
  () => props.run?.id,
  () => {
    isDetailExpanded.value = false;
  },
);

function workflowLabel(workflowId: string, fallback: string) {
  if (workflowId === "agent") {
    return "处理流程";
  }
  if (workflowId === "knowledge_qa") {
    return "知识库查找";
  }
  if (workflowId === "business_ops") {
    return "业务处理";
  }
  return fallback;
}

function nodeLabel(node: WorkflowNodeDisplayItem) {
  if (node.workflowId === "agent") {
    const labels: Record<string, string> = {
      load_context: "准备问题信息",
      understand: "理解问题",
      route: "选择处理方式",
      clarify: "补充必要信息",
      plan: "安排处理步骤",
      execute: "执行处理",
      respond: "整理回复",
    };
    return labels[node.id] ?? node.name;
  }

  if (node.workflowId === "knowledge_qa") {
    const labels: Record<string, string> = {
      analyze_question: "分析问题",
      plan_retrieval: "规划查找范围",
      retrieve_knowledge: "查找资料",
      compose_answer: "生成回答",
    };
    return labels[node.id] ?? node.name;
  }

  return node.name;
}

function activeTitle(node: WorkflowNodeDisplayItem) {
  if (node.workflowId === "knowledge_qa") {
    if (node.id === "retrieve_knowledge") {
      return "正在查找知识库资料";
    }
    if (node.id === "compose_answer") {
      return "正在整理知识库回答";
    }
  }
  return `正在${nodeLabel(node)}`;
}

function activeDescription(node: WorkflowNodeDisplayItem) {
  const message = node.message?.trim();
  if (message && !message.includes("正在处理")) {
    return message;
  }

  if (node.workflowId === "knowledge_qa") {
    const descriptions: Record<string, string> = {
      analyze_question: "正在判断问题重点。",
      plan_retrieval: "正在确定需要查找哪些资料。",
      retrieve_knowledge: "正在从知识库中查找相关内容。",
      compose_answer: "正在把查到的内容整理成回复。",
    };
    return descriptions[node.id] ?? "正在查询知识库。";
  }

  const descriptions: Record<string, string> = {
    load_context: "正在准备会话和知识库范围。",
    understand: "正在识别你的问题重点。",
    route: "正在选择合适的处理方式。",
    clarify: "还需要补充一点信息。",
    plan: "正在安排接下来的处理步骤。",
    execute: "正在执行处理流程。",
    respond: "正在组织最终回复。",
  };
  return descriptions[node.id] ?? "请稍候，正在处理。";
}

function resolveGroupStatus(nodes: WorkflowNodeDisplayItem[]): WorkflowNodeStatus {
  if (nodes.some((node) => node.status === "error")) {
    return "error";
  }
  if (nodes.some((node) => node.status === "running")) {
    return "running";
  }
  if (nodes.length > 0 && nodes.every((node) => node.status === "success")) {
    return "success";
  }
  if (nodes.length > 0 && nodes.every((node) => node.status === "skipped")) {
    return "skipped";
  }
  return "running";
}

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
        v-if="workflowGroups.length > 0"
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
      v-if="shouldShowDetails && workflowGroups.length > 0"
      class="embed-workflow-progress__steps"
    >
      <div
        v-for="group in workflowGroups"
        :key="group.id"
        class="embed-workflow-progress__group"
        :class="`is-${group.status}`"
      >
        <div class="embed-workflow-progress__group-title">
          <span class="embed-workflow-progress__group-title-label">{{ group.name }}</span>
          <span
            class="embed-workflow-progress__group-status"
            :aria-label="statusLabel(group.status)"
            role="img"
          >
            <el-icon v-if="group.status === 'success'"><Check /></el-icon>
            <span v-else class="embed-workflow-progress__step-dot" />
          </span>
        </div>
        <div class="embed-workflow-progress__group-steps">
          <div
            v-for="node in group.nodes"
            :key="`${node.workflowId}-${node.id}`"
            class="embed-workflow-progress__step"
            :class="`is-${node.status}`"
          >
            <span class="embed-workflow-progress__step-name">{{ node.name }}</span>
            <span
              class="embed-workflow-progress__step-status"
              :aria-label="statusLabel(node.status)"
              role="img"
            >
              <el-icon v-if="node.status === 'success'"><Check /></el-icon>
              <span v-else class="embed-workflow-progress__step-dot" />
            </span>
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
  border-radius: 14px 14px 14px 4px;
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
  font-size: 13px;
  line-height: 1.3;
  color: #0f172a;
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

.embed-workflow-progress__steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
}

.embed-workflow-progress__group {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;
}

.embed-workflow-progress__group-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.3;
}

.embed-workflow-progress__group-title-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.embed-workflow-progress__group.is-running .embed-workflow-progress__group-title-label {
  color: #2563eb;
}

.embed-workflow-progress__group.is-error .embed-workflow-progress__group-title-label {
  color: #dc2626;
}

.embed-workflow-progress__group-steps {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-left: 10px;
}

.embed-workflow-progress__step {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
  color: #64748b;
  font-size: 11px;
  line-height: 1.3;
}

.embed-workflow-progress__group-status,
.embed-workflow-progress__step-status {
  display: inline-flex;
  width: 14px;
  height: 14px;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  flex-shrink: 0;
}

.embed-workflow-progress__group-status .el-icon,
.embed-workflow-progress__step-status .el-icon {
  font-size: 12px;
}

.embed-workflow-progress__step-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #cbd5e1;
}

.embed-workflow-progress__group.is-running .embed-workflow-progress__step-dot,
.embed-workflow-progress__step.is-running .embed-workflow-progress__step-dot {
  background: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
}

.embed-workflow-progress__group.is-success .embed-workflow-progress__group-status,
.embed-workflow-progress__step.is-success .embed-workflow-progress__step-status {
  color: #059669;
}

.embed-workflow-progress__group.is-error .embed-workflow-progress__step-dot,
.embed-workflow-progress__step.is-error .embed-workflow-progress__step-dot {
  background: #dc2626;
}

.embed-workflow-progress__step-name {
  overflow: hidden;
  color: #334155;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.embed-workflow-progress__step.is-success .embed-workflow-progress__step-name {
  color: #94a3b8;
}

.embed-workflow-progress__step.is-running .embed-workflow-progress__step-name {
  color: #2563eb;
  font-weight: 600;
}

.embed-workflow-progress__step.is-error .embed-workflow-progress__step-name {
  color: #dc2626;
  font-weight: 600;
}
</style>
