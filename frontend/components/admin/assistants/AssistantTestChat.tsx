"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  FileText,
  Loader2,
  MessageSquare,
  SendHorizonal,
  User,
} from "lucide-react";
import { toast } from "sonner";
import { v4 as uuidv4 } from "uuid";

import { AnswerMarkdown } from "@/components/ask/AnswerMarkdown";
import {
  assistantsApi,
  type AssistantPreviewRequest,
  type AssistantProfile,
} from "@/lib/api/assistants";
import type { AskRetrievedDoc } from "@/lib/api/endpoints/ask";
import { consumeSseStream } from "@/lib/stream/sse";
import { getStreamStatusMessage } from "@/lib/stream/status";
import { cn } from "@/lib/utils";

interface TestTurn {
  id: string;
  query: string;
  answer: string;
  answerStatus?: string | null;
  logId?: number | null;
  retrievedDocs: AskRetrievedDoc[];
  streamStatus?: string | null;
  error: string | null;
}

export type AssistantTestDraft = Omit<AssistantPreviewRequest, "query">;

export interface AssistantTestChatProps {
  assistantId?: number | null;
  draft?: AssistantTestDraft | null;
  className?: string;
}

function buildDocKey(turnId: string, index: number): string {
  return `${turnId}-${index}`;
}

function getAnswerText(value: unknown): string {
  if (!value || typeof value !== "object") return "";
  const record = value as { answer_text?: unknown; answer?: unknown };
  if (typeof record.answer_text === "string") return record.answer_text;
  if (typeof record.answer === "string") return record.answer;
  return "";
}

function getDocs(value: unknown): AskRetrievedDoc[] {
  if (!value || typeof value !== "object") return [];
  const record = value as {
    retrieved_docs?: unknown;
    backend_citations?: unknown;
  };
  if (Array.isArray(record.retrieved_docs)) {
    return record.retrieved_docs as AskRetrievedDoc[];
  }
  if (Array.isArray(record.backend_citations)) {
    return record.backend_citations as AskRetrievedDoc[];
  }
  return [];
}

export function AssistantTestChat({
  assistantId,
  draft,
  className,
}: AssistantTestChatProps) {
  const [assistant, setAssistant] = useState<AssistantProfile | null>(null);
  const [loading, setLoading] = useState(!draft && Number.isFinite(assistantId));
  const [query, setQuery] = useState("");
  const [turns, setTurns] = useState<TestTurn[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [expandedDocs, setExpandedDocs] = useState<Set<string>>(new Set());

  const scrollRef = useRef<HTMLDivElement>(null);
  const activeTurnIdRef = useRef<string | null>(null);

  const assistantName = draft?.name?.trim() || assistant?.name || "未命名助手";
  const suggestedPrompts = useMemo(
    () =>
      (draft?.suggested_prompts ?? assistant?.suggested_prompts ?? [])
        .map((item) => item.trim())
        .filter(Boolean),
    [assistant?.suggested_prompts, draft?.suggested_prompts],
  );
  const welcomeMessage =
    draft?.welcome_message?.trim() ||
    assistant?.welcome_message?.trim() ||
    "你好，我可以根据当前助手配置回答你的问题。";
  const placeholderText =
    draft?.placeholder_text?.trim() || assistant?.placeholder_text?.trim() || "输入测试问题...";
  const hasDraftScope =
    draft != null &&
    Number.isFinite(draft.current_team_id) &&
    draft.current_team_id > 0 &&
    Number.isFinite(draft.knowledge_base_id) &&
    draft.knowledge_base_id > 0;
  const canSubmit =
    submitLoading === false &&
    (hasDraftScope || (!draft && assistant != null && Number.isFinite(assistant.id)));

  useEffect(() => {
    if (draft) {
      setLoading(false);
      return;
    }

    if (!Number.isFinite(assistantId) || !assistantId || assistantId <= 0) {
      setAssistant(null);
      setLoading(false);
      return;
    }

    void (async () => {
      setLoading(true);
      try {
        const detail = await assistantsApi.get(assistantId);
        setAssistant(detail);
        setQuery((current) => current || detail.suggested_prompts[0] || "");
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "加载助手失败");
      } finally {
        setLoading(false);
      }
    })();
  }, [assistantId, draft]);

  useEffect(() => {
    setQuery((current) => current || suggestedPrompts[0] || "");
  }, [suggestedPrompts]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    container.scrollTo({
      top: container.scrollHeight,
      behavior: submitLoading ? "auto" : "smooth",
    });
  }, [submitLoading, turns]);

  const patchActiveTurn = (patch: Partial<TestTurn>) => {
    const activeTurnId = activeTurnIdRef.current;
    if (!activeTurnId) return;
    setTurns((current) =>
      current.map((turn) => (turn.id === activeTurnId ? { ...turn, ...patch } : turn)),
    );
  };

  const submit = async (prefill?: string) => {
    const nextQuery = (prefill ?? query).trim();
    if (!nextQuery || submitLoading) return;

    if (!canSubmit) {
      toast.error(draft ? "请先选择知识库" : "请先保存并启用助手");
      return;
    }

    const turnId = `assistant-test-turn-${uuidv4()}`;
    activeTurnIdRef.current = turnId;
    setSubmitLoading(true);
    setQuery("");
    setTurns((current) => [
      ...current,
      {
        id: turnId,
        query: nextQuery,
        answer: "",
        answerStatus: null,
        logId: null,
        retrievedDocs: [],
        streamStatus: null,
        error: null,
      },
    ]);

    try {
      if (draft) {
        const response = await assistantsApi.preview({
          ...draft,
          query: nextQuery,
        });
        patchActiveTurn({
          answer: getAnswerText(response),
          answerStatus: response.answer_status,
          logId: response.log_id ?? null,
          retrievedDocs: getDocs(response),
        });
        return;
      }

      if (!assistant) return;
      const stream = await assistantsApi.stream(assistant.id, {
        query: nextQuery,
        session_id: sessionId,
      });

      await consumeSseStream(stream, (event) => {
        const streamStatus = getStreamStatusMessage(event);
        if (streamStatus) {
          patchActiveTurn({ streamStatus });
        }

        switch (event.type) {
          case "retrieved": {
            const docs = event.data.retrieved_docs;
            if (Array.isArray(docs)) {
              patchActiveTurn({
                retrievedDocs: docs as AskRetrievedDoc[],
                streamStatus:
                  docs.length > 0
                    ? `已匹配 ${docs.length} 条相关资料`
                    : "未匹配到相关资料",
              });
            }
            break;
          }
          case "token": {
            const text = event.data.text;
            if (typeof text !== "string" || !text) break;
            const activeTurnId = activeTurnIdRef.current;
            if (!activeTurnId) break;
            setTurns((current) =>
              current.map((turn) =>
                turn.id === activeTurnId
                  ? {
                      ...turn,
                      answer: `${turn.answer}${text}`,
                      streamStatus: "正在生成回答...",
                    }
                  : turn,
              ),
            );
            break;
          }
          case "complete": {
            const nextSessionId = event.data.session_id;
            if (typeof nextSessionId === "string" && nextSessionId) {
              setSessionId(nextSessionId);
            }

            const completeAnswer = getAnswerText(event.data);
            const completeDocs = getDocs(event.data);
            const patch: Partial<TestTurn> = {};
            if (completeAnswer) patch.answer = completeAnswer;
            if (typeof event.data.answer_status === "string") {
              patch.answerStatus = event.data.answer_status;
            }
            if (typeof event.data.log_id === "number") {
              patch.logId = event.data.log_id;
            }
            if (completeDocs.length > 0) {
              patch.retrievedDocs = completeDocs;
            }
            patch.streamStatus = null;
            patchActiveTurn(patch);
            break;
          }
          case "error": {
            const message = String(event.data.message ?? "测试失败");
            patchActiveTurn({ error: message, streamStatus: null });
            toast.error(message);
            break;
          }
          default:
            break;
        }
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "测试失败";
      patchActiveTurn({ error: message, streamStatus: null });
      toast.error(message);
    } finally {
      setSubmitLoading(false);
      activeTurnIdRef.current = null;
    }
  };

  const toggleDoc = (key: string) => {
    setExpandedDocs((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  if (loading) {
    return (
      <div className={cn("flex h-full min-h-[360px] items-center justify-center", className)}>
        <div className="flex flex-col items-center gap-3 text-slate-500">
          <Loader2 className="h-5 w-5 animate-spin text-teal-600" />
          <span className="text-sm">加载测试环境...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex h-full min-h-0 flex-col bg-slate-50", className)}>
      <div className="shrink-0 border-b border-slate-200 bg-white p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-teal-50 text-teal-700">
            <Bot className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h3 className="truncate font-medium text-slate-900">{assistantName}</h3>
            <p className="truncate text-xs text-slate-500">{welcomeMessage}</p>
          </div>
        </div>

        {suggestedPrompts.length > 0 && turns.length === 0 ? (
          <div className="mt-4">
            <div className="flex flex-wrap gap-2">
              {suggestedPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => void submit(prompt)}
                  disabled={!canSubmit}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 transition-colors hover:border-teal-200 hover:text-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-6 overflow-y-auto p-4">
        {turns.length === 0 ? (
          <div className="flex h-full min-h-[260px] items-center justify-center">
            <div className="max-w-xs text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-lg border border-slate-100 bg-white text-slate-400 shadow-sm">
                <MessageSquare className="h-6 w-6" />
              </div>
              <p className="mt-4 text-sm leading-6 text-slate-500">{welcomeMessage}</p>
            </div>
          </div>
        ) : (
          turns.map((turn) => (
            <div key={turn.id} className="space-y-4">
              <div className="flex justify-end">
                <div className="max-w-[86%] rounded-2xl rounded-tr-sm bg-slate-900 px-4 py-3 text-sm text-white shadow-sm">
                  <div className="mb-1 flex items-center gap-1.5 text-[11px] text-white/65">
                    <User className="h-3 w-3" />
                    测试问题
                  </div>
                  <p className="whitespace-pre-wrap leading-6">{turn.query}</p>
                </div>
              </div>

              <div className="flex justify-start">
                <div className="max-w-[92%] rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 shadow-sm">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2 text-xs font-medium text-slate-800">
                      <Bot className="h-3.5 w-3.5 shrink-0 text-teal-600" />
                      <span className="truncate">{assistantName}</span>
                    </div>
                    {turn.answerStatus ? (
                      <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">
                        {turn.answerStatus}
                      </span>
                    ) : null}
                  </div>
                  {turn.error ? (
                    <p className="text-sm text-red-600">{turn.error}</p>
                  ) : turn.answer ? (
                    <AnswerMarkdown text={turn.answer} />
                  ) : (
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      {turn.streamStatus || "正在生成回答..."}
                    </div>
                  )}

                  {turn.retrievedDocs.length > 0 ? (
                    <div className="mt-3 border-t border-slate-100 pt-3">
                      <div className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                        <FileText className="h-3 w-3" />
                        参考片段
                      </div>
                      <div className="space-y-2">
                        {turn.retrievedDocs.map((doc, index) => {
                          const key = buildDocKey(turn.id, index);
                          const expanded = expandedDocs.has(key);
                          const content = doc.content?.trim() || "";
                          const title =
                            doc.metadata?.document_title?.trim() || `片段 ${index + 1}`;

                          return (
                            <button
                              key={key}
                              type="button"
                              onClick={() => toggleDoc(key)}
                              className="w-full rounded-lg border border-slate-200 bg-slate-50 p-3 text-left transition-colors hover:border-teal-200"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="text-xs font-medium text-slate-700">{title}</div>
                                <div className="text-[10px] text-slate-400">
                                  {expanded ? "收起" : "展开"}
                                </div>
                              </div>
                              <p
                                className={cn(
                                  "mt-1.5 text-xs leading-5 text-slate-500",
                                  !expanded && "line-clamp-2",
                                )}
                              >
                                {content || "无可展示内容"}
                              </p>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="shrink-0 border-t border-slate-200 bg-white p-4">
        <div className="relative flex items-end gap-2">
          <textarea
            rows={1}
            value={query}
            disabled={!canSubmit}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void submit();
              }
            }}
            placeholder={placeholderText}
            className="min-h-[44px] w-full resize-none rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 pr-12 text-sm text-slate-800 outline-none transition-all placeholder:text-slate-400 focus:border-teal-500 focus:ring-2 focus:ring-teal-100 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
          />
          <button
            type="button"
            disabled={submitLoading || !query.trim() || !canSubmit}
            onClick={() => void submit()}
            className="absolute bottom-1 right-1 flex h-9 w-9 items-center justify-center rounded-md bg-teal-600 text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
            title="发送"
          >
            {submitLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <SendHorizonal className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
