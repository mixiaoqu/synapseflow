import type { SseEnvelope } from "@/shared/lib/stream/sse";

export type WorkflowRunStatus = "idle" | "running" | "done" | "error";
export type WorkflowNodeStatus = "pending" | "running" | "success" | "error" | "skipped";

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

export interface ChatWorkflowRun {
  id: string;
  status: WorkflowRunStatus;
  workflows: Record<string, WorkflowState>;
  currentWorkflowId?: string;
  currentNodeId?: string;
  startedAt: number;
  endedAt?: number;
  durationMs?: number;
  message?: string;
  error?: WorkflowRunError;
}

export interface WorkflowNodeDisplayItem extends WorkflowNodeState {
  workflowId: string;
  workflowName: string;
}

const WORKFLOW_NAMES: Record<string, string> = {
  agent: "助手编排",
  knowledge_qa: "知识库问答",
  business_ops: "业务操作",
};

const NODE_NAMES: Record<string, Record<string, string>> = {
  agent: {
    load_context: "准备上下文",
    understand: "理解问题",
    route: "匹配处理方式",
    clarify: "补齐信息",
    plan: "制定步骤",
    execute: "执行任务",
    respond: "整理回复",
  },
  knowledge_qa: {
    analyze_question: "分析问题",
    plan_retrieval: "规划检索",
    retrieve_knowledge: "查找资料",
    compose_answer: "生成回答",
  },
  business_ops: {
    analyze_request: "分析请求",
    match_operation: "匹配操作",
    collect_params: "补齐参数",
    authorize: "权限校验",
    confirm_action: "等待确认",
    execute_operation: "执行业务操作",
    compose_result: "整理结果",
  },
};

const WORKFLOW_ORDER = ["agent", "knowledge_qa", "business_ops"];

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
    error: run.error ? { ...run.error } : undefined,
  };
}

function resolveWorkflowName(workflowId: string) {
  return WORKFLOW_NAMES[workflowId] ?? workflowId;
}

function resolveNodeWorkflowId(event: SseEnvelope, nodeId: string) {
  const data = eventData(event);
  const explicitWorkflowId = normalizeText(event.workflow_id) || normalizeText(data.workflow_id);
  if (explicitWorkflowId) {
    return explicitWorkflowId;
  }

  if (NODE_NAMES.knowledge_qa[nodeId]) {
    return "knowledge_qa";
  }
  if (NODE_NAMES.business_ops[nodeId]) {
    return "business_ops";
  }
  return "agent";
}

function resolveNodeName(workflowId: string, nodeId: string, nodeName?: string) {
  return NODE_NAMES[workflowId]?.[nodeId] || normalizeText(nodeName) || nodeId;
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

  if (event.type === "start") {
    run.status = "running";
    run.message = normalizeText(data.message) || "正在准备问题...";
    ensureWorkflow(run, normalizeText(event.workflow_id) || "agent", at);
    return run;
  }

  if (event.type === "complete") {
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
  }

  const nodeId = normalizeText(event.node_id);
  if (!nodeId || nodeId === "system") {
    return run;
  }

  const workflowId = resolveNodeWorkflowId(event, nodeId);
  const workflow = ensureWorkflow(run, workflowId, at);
  const nodeName = resolveNodeName(workflowId, nodeId, event.node_name);
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

export function getCurrentWorkflowNode(run: ChatWorkflowRun | null) {
  if (!run) {
    return null;
  }

  if (run.currentWorkflowId && run.currentNodeId) {
    return run.workflows[run.currentWorkflowId]?.nodes[run.currentNodeId] ?? null;
  }

  const runningNode = getWorkflowRunVisibleNodes(run).find((node) => node.status === "running");
  return runningNode ?? null;
}

export function getWorkflowRunMessage(run: ChatWorkflowRun | null) {
  if (!run) {
    return null;
  }

  if (run.status === "error") {
    return run.error?.message || run.message || "请求失败";
  }

  const currentNode = getCurrentWorkflowNode(run);
  if (currentNode) {
    return currentNode.message || currentNode.name;
  }

  return run.message || null;
}

export function getWorkflowRunVisibleNodes(
  run: ChatWorkflowRun | null,
  limit = 6,
): WorkflowNodeDisplayItem[] {
  if (!run) {
    return [];
  }

  const workflowIds = Object.keys(run.workflows).sort((left, right) => {
    const leftIndex = WORKFLOW_ORDER.indexOf(left);
    const rightIndex = WORKFLOW_ORDER.indexOf(right);
    return (leftIndex === -1 ? 99 : leftIndex) - (rightIndex === -1 ? 99 : rightIndex);
  });

  const nodes = workflowIds.flatMap((workflowId) => {
    const workflow = run.workflows[workflowId];
    return workflow.nodeOrder
      .map((nodeId) => workflow.nodes[nodeId])
      .filter((node): node is WorkflowNodeState => Boolean(node))
      .map((node) => ({
        ...node,
        workflowId,
        workflowName: workflow.name,
      }));
  });

  return nodes
    .filter((node) => node.status !== "pending")
    .sort((left, right) => (left.startedAt ?? 0) - (right.startedAt ?? 0))
    .slice(-limit);
}
