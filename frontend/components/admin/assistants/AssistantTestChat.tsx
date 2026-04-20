"use client";

import { useEffect, useRef, useState } from "react";
import {
  Bot,
  Loader2,
  MessageSquare,
  SendHorizonal,
  User,
} from "lucide-react";
import { toast } from "sonner";

import { AnswerMarkdown } from "@/components/ask/AnswerMarkdown";
import {
  assistantsApi,
  type AssistantProfile,
} from "@/lib/api/assistants";
import type { AskRetrievedDoc } from "@/lib/api/endpoints/ask";
import { consumeSseStream } from "@/lib/stream/sse";
import { v4 as uuidv4 } from "uuid";

interface TestTurn {
  id: string;
  query: string;
  answer: string;
  answerStatus?: string | null;
  logId?: number | null;
  retrievedDocs: AskRetrievedDoc[];
  error: string | null;
}

function buildDocKey(turnId: string, index: number): string {
  return `${turnId}-${index}`;
}

export interface AssistantTestChatProps {
  assistantId: number;
}

export function AssistantTestChat({ assistantId }: AssistantTestChatProps) {
  const [assistant, setAssistant] = useState<AssistantProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [turns, setTurns] = useState<TestTurn[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [expandedDocs, setExpandedDocs] = useState<Set<string>>(new Set());

  const scrollRef = useRef<HTMLDivElement>(null);
  const activeTurnIdRef = useRef<string | null>(null);

  useEffect(() => {
    const run = async () => {
      if (!Number.isFinite(assistantId) || assistantId <= 0) {
        toast.error("无效的助手编号");
        return;
      }

      setLoading(true);
      try {
        const detail = await assistantsApi.get(assistantId);
        setAssistant(detail);
        setQuery(detail.suggested_prompts[0] ?? "");
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "加载助手失败");
      } finally {
        setLoading(false);
      }
    };

    void run();
  }, [assistantId]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    container.scrollTo({
      top: container.scrollHeight,
      behavior: submitLoading ? "auto" : "smooth",
    });
  }, [submitLoading, turns]);

  const submit = async (prefill?: string) => {
    const nextQuery = (prefill ?? query).trim();
    if (!assistant || !nextQuery || submitLoading) return;

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
        error: null,
      },
    ]);

    try {
      const stream = await assistantsApi.stream(assistant.id, {
        query: nextQuery,
        session_id: sessionId,
      });

      await consumeSseStream(stream, (event) => {
        const activeTurnId = activeTurnIdRef.current;
        if (!activeTurnId) return;

        switch (event.type) {
          case "retrieved": {
            const docs = event.data.retrieved_docs;
            if (!Array.isArray(docs)) break;
            setTurns((current) =>
              current.map((turn) =>
                turn.id === activeTurnId
                  ? { ...turn, retrievedDocs: docs as AskRetrievedDoc[] }
                  : turn,
              ),
            );
            break;
          }
          case "token": {
            const text = event.data.text;
            if (typeof text !== "string" || !text) break;
            setTurns((current) =>
              current.map((turn) =>
                turn.id === activeTurnId
                  ? { ...turn, answer: `${turn.answer}${text}` }
                  : turn,
              ),
            );
            break;
          }
          case "complete": {
            const docs = event.data.retrieved_docs;
            const nextSessionId = event.data.session_id;
            const answerStatus = event.data.answer_status;
            const logId = event.data.log_id;

            if (typeof nextSessionId === "string" && nextSessionId) {
              setSessionId(nextSessionId);
            }

            setTurns((current) =>
              current.map((turn) =>
                turn.id === activeTurnId
                  ? {
                      ...turn,
                      answer: typeof event.data.answer === "string" ? event.data.answer : turn.answer,
                      answerStatus: typeof answerStatus === "string" ? answerStatus : turn.answerStatus,
                      logId: typeof logId === "number" ? logId : turn.logId,
                      retrievedDocs: Array.isArray(docs) ? (docs as AskRetrievedDoc[]) : turn.retrievedDocs,
                    }
                  : turn,
              ),
            );
            break;
          }
          case "error": {
            const message = String(event.data.message ?? "测试失败");
            setTurns((current) =>
              current.map((turn) =>
                turn.id === activeTurnId ? { ...turn, error: message } : turn,
              ),
            );
            toast.error(message);
            break;
          }
          default:
            break;
        }
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "测试失败";
      setTurns((current) =>
        current.map((turn) =>
          turn.id === activeTurnIdRef.current ? { ...turn, error: message } : turn,
        ),
      );
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
      <div className="flex h-[400px] items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-slate-500">
          <Loader2 className="h-6 w-6 animate-spin text-teal-600" />
          <span className="text-sm">加载测试环境...</span>
        </div>
      </div>
    );
  }

  if (!assistant) {
    return null;
  }

  return (
    <div className="flex h-full flex-col bg-slate-50">
      <div className="border-b border-slate-200 bg-white p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-50 text-teal-600">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-medium text-slate-900">{assistant.name}</h3>
            <p className="text-xs text-slate-500">正在与未发布的草稿进行测试对话</p>
          </div>
        </div>

        {assistant.suggested_prompts.length > 0 && turns.length === 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs text-slate-500">推荐测试问题：</p>
            <div className="flex flex-wrap gap-2">
              {assistant.suggested_prompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => void submit(prompt)}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 transition-colors hover:border-teal-200 hover:text-teal-700"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div ref={scrollRef} className="flex-1 space-y-6 overflow-y-auto p-4 sm:p-6">
        {turns.length === 0 ? (
           <div className="flex h-full min-h-[300px] items-center justify-center">
             <div className="max-w-xs text-center">
               <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-slate-400 shadow-sm border border-slate-100">
                 <MessageSquare className="h-6 w-6" />
               </div>
               <p className="mt-4 text-sm leading-6 text-slate-500">
                 这里会直接用当前助手的知识库、人格和规则模板做真实流式问答。
               </p>
             </div>
           </div>
        ) : (
          turns.map((turn) => (
            <div key={turn.id} className="space-y-4">
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-slate-900 px-4 py-3 text-sm text-white shadow-sm">
                  <p className="whitespace-pre-wrap leading-6">{turn.query}</p>
                </div>
              </div>

              <div className="flex justify-start">
                <div className="max-w-[90%] rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 shadow-sm">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-xs font-medium text-slate-800">
                      <Bot className="h-3.5 w-3.5 text-teal-600" />
                      {assistant.name}
                    </div>
                    {turn.answerStatus ? (
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">
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
                      正在生成回答...
                    </div>
                  )}

                  {turn.retrievedDocs.length > 0 ? (
                    <div className="mt-3 border-t border-slate-100 pt-3">
                      <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
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
                              className="w-full rounded-xl border border-slate-200 bg-slate-50 p-3 text-left transition-colors hover:border-teal-200"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="text-xs font-medium text-slate-700">{title}</div>
                                <div className="text-[10px] text-slate-400">
                                  {expanded ? "收起" : "展开"}
                                </div>
                              </div>
                              <p className={`mt-1.5 text-xs leading-5 text-slate-500 ${expanded ? "" : "line-clamp-2"}`}>
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

      <div className="border-t border-slate-200 bg-white p-4">
        <div className="relative flex items-end gap-2">
          <textarea
            rows={1}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void submit();
              }
            }}
            placeholder="输入测试问题..."
            className="min-h-[44px] w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 pr-12 text-sm text-slate-800 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
          />
          <button
            type="button"
            disabled={submitLoading || !query.trim()}
            onClick={() => void submit()}
            className="absolute bottom-1 right-1 flex h-9 w-9 items-center justify-center rounded-lg bg-teal-600 text-white transition-colors hover:bg-teal-700 disabled:opacity-50"
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