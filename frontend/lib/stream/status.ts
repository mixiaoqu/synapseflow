import type { SseEnvelope } from "./sse";

const NODE_START_MESSAGES: Record<string, string> = {
  analyze: "正在分析问题并生成检索方案...",
  rewrite_query: "正在优化检索问题...",
  retrieve: "正在检索知识库...",
  evaluate: "正在核对答案依据...",
  answer: "正在生成回答...",
};

const NODE_COMPLETE_MESSAGES: Record<string, string> = {
  analyze: "已完成问题分析",
  rewrite_query: "已准备检索问题",
  retrieve: "已匹配相关资料",
  evaluate: "已完成答案依据核对",
  answer: "正在整理回答...",
};

export function getStreamStatusMessage(event: SseEnvelope): string | null {
  const message = event.data?.message;
  if (typeof message === "string" && message.trim()) {
    return message.trim();
  }

  if (event.type === "start") {
    return "正在准备问题...";
  }

  if (event.type === "progress" || event.type === "node_start") {
    return NODE_START_MESSAGES[event.node_id ?? ""] ?? "正在处理...";
  }

  if (event.type === "node_complete") {
    if (event.node_id === "retrieve") {
      const count = event.data?.retrieved_count;
      if (typeof count === "number") {
        return count > 0 ? `已匹配 ${count} 条相关资料` : "未匹配到相关资料";
      }
    }
    return NODE_COMPLETE_MESSAGES[event.node_id ?? ""] ?? null;
  }

  if (event.type === "retrieved") {
    const docs = event.data?.retrieved_docs;
    if (Array.isArray(docs)) {
      return docs.length > 0 ? `已匹配 ${docs.length} 条相关资料` : "未匹配到相关资料";
    }
  }

  return null;
}
