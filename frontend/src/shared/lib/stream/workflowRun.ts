import type { SseEnvelope } from "@/shared/lib/stream/sse";

export type WorkflowRunStatus = "idle" | "running" | "done" | "error";
export type WorkflowNodeStatus = "pending" | "running" | "success" | "error" | "skipped";
export type WorkflowDisplayActivityStatus = "running" | "completed" | "error";
export type WorkflowDisplayStageStatus = "pending" | "running" | "success" | "error";

export interface WorkflowRunError {
  code?: string;
  message: string;
  retryable?: boolean;
}

export interface WorkflowNodeState {
  id: string;
  name: string;
  status: WorkflowNodeStatus;
  stage?: string;
  message?: string;
  detail?: Record<string, unknown>;
  startedAt?: number;
  endedAt?: number;
  durationMs?: number;
  error?: WorkflowRunError;
}

export interface WorkflowState {
  id: string;
  name: string;
  status: WorkflowNodeStatus;
  nodes: Record<string, WorkflowNodeState>;
  nodeOrder: string[];
  startedAt?: number;
  endedAt?: number;
  durationMs?: number;
}

export interface WorkflowDisplayActivity {
  text: string;
  status: WorkflowDisplayActivityStatus;
  at: number;
}

export interface WorkflowDisplayStage {
  id: string;
  title: string;
  status: WorkflowDisplayStageStatus;
  activities: WorkflowDisplayActivity[];
}

export interface ChatWorkflowRun {
  id: string;
  status: WorkflowRunStatus;
  workflows: Record<string, WorkflowState>;
  displayStages: WorkflowDisplayStage[];
  currentWorkflowId?: string;
  currentNodeId?: string;
  startedAt: number;
  endedAt?: number;
  durationMs?: number;
  message?: string;
  error?: WorkflowRunError;
}

function now() {
  return Date.now();
}

function normalizeText(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function eventTimeMs(event: SseEnvelope) {
  return typeof event.timestamp === "number" && Number.isFinite(event.timestamp)
    ? Math.round(event.timestamp * 1000)
    : now();
}

function eventData(event: SseEnvelope): Record<string, unknown> {
  return event.data && typeof event.data === "object" && !Array.isArray(event.data)
    ? event.data
    : {};
}

function cloneRun(run: ChatWorkflowRun): ChatWorkflowRun {
  const workflows: Record<string, WorkflowState> = {};
  for (const [workflowId, workflow] of Object.entries(run.workflows)) {
    const nodes: Record<string, WorkflowNodeState> = {};
    for (const [nodeId, node] of Object.entries(workflow.nodes)) {
      nodes[nodeId] = { ...node, detail: node.detail ? { ...node.detail } : undefined };
    }
    workflows[workflowId] = {
      ...workflow,
      nodes,
      nodeOrder: [...workflow.nodeOrder],
    };
  }

  return {
    ...run,
    workflows,
    displayStages: run.displayStages.map((stage) => ({
      ...stage,
      activities: stage.activities.map((activity) => ({ ...activity })),
    })),
    error: run.error ? { ...run.error } : undefined,
  };
}

function resolveWorkflowName(workflowId: string) {
  return workflowId || "workflow";
}

function resolveNodeWorkflowId(event: SseEnvelope, nodeId: string) {
  const data = eventData(event);
  const explicitWorkflowId = normalizeText(event.workflow_id) || normalizeText(data.workflow_id);
  return explicitWorkflowId || "agent";
}

function resolveNodeName(nodeId: string, nodeName?: string) {
  return normalizeText(nodeName) || nodeId;
}

function ensureWorkflow(run: ChatWorkflowRun, workflowId: string, at: number) {
  if (!run.workflows[workflowId]) {
    run.workflows[workflowId] = {
      id: workflowId,
      name: resolveWorkflowName(workflowId),
      status: "running",
      nodes: {},
      nodeOrder: [],
      startedAt: at,
    };
    return run.workflows[workflowId];
  }

  const workflow = run.workflows[workflowId];
  if (workflow.status === "pending" || workflow.status === "skipped") {
    workflow.status = "running";
  }
  workflow.startedAt = workflow.startedAt ?? at;
  return workflow;
}

function ensureNode(
  workflow: WorkflowState,
  nodeId: string,
  nodeName: string,
  at: number,
) {
  if (!workflow.nodes[nodeId]) {
    workflow.nodes[nodeId] = {
      id: nodeId,
      name: nodeName,
      status: "pending",
    };
    workflow.nodeOrder.push(nodeId);
  }

  const node = workflow.nodes[nodeId];
  node.name = nodeName || node.name;
  node.startedAt = node.startedAt ?? at;
  return node;
}

function normalizeActivityStatus(value: unknown): WorkflowDisplayActivityStatus {
  const status = normalizeText(value);
  if (status === "completed" || status === "success") {
    return "completed";
  }
  if (status === "error" || status === "failed") {
    return "error";
  }
  return "running";
}

function ensureDisplayStage(
  run: ChatWorkflowRun,
  stageId: string,
  title: string,
): WorkflowDisplayStage | null {
  if (!stageId) {
    return null;
  }

  const existing = run.displayStages.find((stage) => stage.id === stageId);
  if (existing) {
    if (title) {
      existing.title = title;
    }
    return existing;
  }

  const stage = {
    id: stageId,
    title: title || stageId,
    status: "pending" as WorkflowDisplayStageStatus,
    activities: [],
  };
  run.displayStages.push(stage);
  return stage;
}

function moveDisplayStage(run: ChatWorkflowRun, stageId: string, status: WorkflowDisplayActivityStatus) {
  const currentIndex = run.displayStages.findIndex((stage) => stage.id === stageId);
  if (currentIndex < 0) {
    return;
  }

  run.displayStages.forEach((stage, index) => {
    if (index < currentIndex && stage.status !== "error") {
      stage.status = "success";
    }
  });

  const stage = run.displayStages[currentIndex];
  if (status === "error") {
    stage.status = "error";
    return;
  }
  if (status === "running" || stage.status === "pending") {
    stage.status = "running";
  }
}

function applyDisplayActivity(run: ChatWorkflowRun, data: Record<string, unknown>, at: number) {
  const stageId = normalizeText(data.display_stage);
  const activityText = normalizeText(data.activity_text) || normalizeText(data.message);
  if (!stageId || !activityText) {
    return;
  }

  const stage = ensureDisplayStage(
    run,
    stageId,
    normalizeText(data.display_title),
  );
  if (!stage) {
    return;
  }

  const activityStatus = normalizeActivityStatus(data.activity_status);
  moveDisplayStage(run, stage.id, activityStatus);

  if (!activityText) {
    return;
  }

  stage.activities = [
    ...stage.activities,
    {
      text: activityText,
      status: activityStatus,
      at,
    },
  ].slice(-2);
}

function completeRunningNodes(
  workflow: WorkflowState,
  at: number,
  currentNodeId?: string,
) {
  for (const node of Object.values(workflow.nodes)) {
    if (node.id !== currentNodeId && node.status === "running") {
      node.status = "success";
      node.endedAt = at;
      node.durationMs = node.startedAt ? Math.max(0, at - node.startedAt) : undefined;
    }
  }
}

function completeRun(run: ChatWorkflowRun, at: number) {
  for (const workflow of Object.values(run.workflows)) {
    completeRunningNodes(workflow, at);
    if (workflow.status === "running") {
      workflow.status = "success";
      workflow.endedAt = at;
      workflow.durationMs = workflow.startedAt ? Math.max(0, at - workflow.startedAt) : undefined;
    }
  }
  for (const stage of run.displayStages) {
    if (stage.status === "pending" || stage.status === "running") {
      stage.status = "success";
    }
  }
}

function buildRetrievedMessage(data: Record<string, unknown>) {
  const retrievedDocs = data.retrieved_docs;
  const retrievedCount = typeof data.retrieved_count === "number"
    ? data.retrieved_count
    : Array.isArray(retrievedDocs)
      ? retrievedDocs.length
      : null;

  if (retrievedCount == null) {
    return "";
  }
  return retrievedCount > 0
    ? `已匹配 ${retrievedCount} 条相关内容`
    : "未匹配到相关内容";
}

export function createWorkflowRun(runId?: string | null, message = "正在连接助手..."): ChatWorkflowRun {
  return {
    id: runId || `run-${now()}`,
    status: "running",
    workflows: {},
    displayStages: [],
    startedAt: now(),
    message,
  };
}

export function reduceWorkflowRunEvent(
  currentRun: ChatWorkflowRun | null,
  event: SseEnvelope,
): ChatWorkflowRun {
  const at = eventTimeMs(event);
  const data = eventData(event);
  const run = cloneRun(currentRun ?? createWorkflowRun(event.run_id, normalizeText(data.message)));

  if (event.run_id) {
    run.id = event.run_id;
  }
  run.startedAt = run.startedAt || at;

  if (
    run.status === "done" &&
    event.type !== "complete" &&
    event.type !== "workflow_complete" &&
    event.type !== "error"
  ) {
    return run;
  }

  applyDisplayActivity(run, data, at);

  if (event.type === "start") {
    run.status = "running";
    run.message = normalizeText(data.message) || "正在准备问题...";
    ensureWorkflow(run, normalizeText(event.workflow_id) || "agent", at);
    return run;
  }

  if (event.type === "complete" || event.type === "workflow_complete") {
    run.status = "done";
    run.message = "处理完成";
    run.endedAt = at;
    run.durationMs = Math.max(0, at - run.startedAt);
    completeRun(run, at);
    return run;
  }

  if (event.type === "error") {
    const message = normalizeText(data.message) || "请求失败，请稍后重试。";
    run.status = "error";
    run.message = message;
    run.error = { message };
    run.endedAt = at;
    run.durationMs = Math.max(0, at - run.startedAt);
    for (const stage of run.displayStages) {
      if (stage.status === "running") {
        stage.status = "error";
      }
    }
  }

  const nodeId = normalizeText(event.node_id);
  if (!nodeId || nodeId === "system") {
    return run;
  }

  const workflowId = resolveNodeWorkflowId(event, nodeId);
  const workflow = ensureWorkflow(run, workflowId, at);
  const nodeName = resolveNodeName(nodeId, event.node_name);
  const node = ensureNode(workflow, nodeId, nodeName, at);
  const message = normalizeText(data.message);

  if (event.type === "node_start" || event.type === "progress" || event.type === "token") {
    completeRunningNodes(workflow, at, nodeId);
    workflow.status = "running";
    node.status = "running";
    node.stage = normalizeText(data.stage) || node.stage;
    node.message = message || (event.type === "token" ? "正在生成回答..." : node.message);
    node.detail = { ...data };
    run.status = "running";
    run.currentWorkflowId = workflowId;
    run.currentNodeId = nodeId;
    run.message = node.message || node.name;
    return run;
  }

  if (event.type === "retrieved") {
    const retrievedMessage = buildRetrievedMessage(data);
    node.status = node.status === "pending" ? "running" : node.status;
    node.message = retrievedMessage || node.message;
    node.detail = { ...data };
    run.currentWorkflowId = workflowId;
    run.currentNodeId = nodeId;
    run.message = node.message || node.name;
    return run;
  }

  if (event.type === "node_complete") {
    node.status = "success";
    node.endedAt = at;
    node.durationMs = node.startedAt ? Math.max(0, at - node.startedAt) : undefined;
    node.message = buildRetrievedMessage(data) || message || node.message;
    node.detail = { ...data };
    completeRunningNodes(workflow, at, nodeId);
    run.currentWorkflowId = workflowId;
    run.currentNodeId = nodeId;
    run.message = node.message || `${node.name}完成`;
    return run;
  }

  if (event.type === "error") {
    workflow.status = "error";
    node.status = "error";
    node.error = run.error;
    node.message = run.error?.message;
  }

  return run;
}

export function getWorkflowDisplayStages(run: ChatWorkflowRun | null) {
  return run?.displayStages ?? [];
}
