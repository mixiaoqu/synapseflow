"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Bot,
  Loader2,
  MessageSquare,
  Pencil,
  RefreshCcw,
  SendHorizonal,
  TestTube2,
  User,
} from "lucide-react";
import { toast } from "sonner";

import { AnswerMarkdown } from "@/components/kb-chat/AnswerMarkdown";
import {
  assistantsApi,
  type AssistantProfile,
} from "@/lib/api/assistants";
import type { RetrievedDoc } from "@/lib/api/endpoints/kbChat";
import { consumeSseStream } from "@/lib/stream/sse";

interface TestTurn {
  id: string;
  query: string;
  answer: string;
  answerStatus?: string | null;
  logId?: number | null;
  retrievedDocs: RetrievedDoc[];
  error: string | null;
}

function formatDateTime(value?: string | null): string {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function buildDocKey(turnId: string, index: number): string {
  return `${turnId}-${index}`;
}

export default function AssistantTestPage() {
  const params = useParams<{ assistantId: string }>();
  const router = useRouter();

  const assistantId = Number(params.assistantId);
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
        router.replace("/admin/assistants");
        return;
      }

      setLoading(true);
      try {
        const detail = await assistantsApi.get(assistantId);
        setAssistant(detail);
        setQuery(detail.suggested_prompts[0] ?? "");
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "加载助手失败");
        router.replace("/admin/assistants");
      } finally {
        setLoading(false);
      }
    };

    void run();
  }, [assistantId, router]);

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

    const turnId = crypto.randomUUID();
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
                  ? { ...turn, retrievedDocs: docs as RetrievedDoc[] }
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
                      retrievedDocs: Array.isArray(docs) ? (docs as RetrievedDoc[]) : turn.retrievedDocs,
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

  const resetConversation = () => {
    setTurns([]);
    setSessionId(null);
    setExpandedDocs(new Set());
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
      <div className="flex h-full items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          加载测试页中...
        </div>
      </div>
    );
  }

  if (!assistant) {
    return null;
  }

  return (
    <div className="min-h-full bg-[radial-gradient(circle_at_top_left,_rgba(20,184,166,0.12),_transparent_30%),linear-gradient(180deg,#ffffff_0%,#f8fafc_100%)]">
      <header className="border-b border-slate-200 bg-white/85 px-8 py-6 backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-500 to-cyan-600 text-white shadow-lg shadow-teal-500/20">
              <TestTube2 className="h-5 w-5" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-semibold text-slate-900">{assistant.name}</h1>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500">
                  {assistant.slug}
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-600">独立即时测试页，直接使用已保存的助手配置进行流式问答验证。</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => router.push("/admin/assistants")}
              className="inline-flex h-10 items-center gap-2 rounded-xl px-4 text-sm text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
            >
              <ArrowLeft className="h-4 w-4" />
              返回列表
            </button>
            <button
              type="button"
              onClick={() => router.push(`/admin/assistants/${assistantId}/edit`)}
              className="inline-flex h-10 items-center gap-2 rounded-xl px-4 text-sm text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
            >
              <Pencil className="h-4 w-4" />
              返回编辑
            </button>
            <button
              type="button"
              onClick={resetConversation}
              className="inline-flex h-10 items-center gap-2 rounded-xl px-4 text-sm text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
            >
              <RefreshCcw className="h-4 w-4" />
              清空会话
            </button>
          </div>
        </div>
      </header>

      <div className="grid gap-6 px-8 py-6 xl:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">助手信息</h2>
            <div className="mt-4 space-y-3 text-sm text-slate-600">
              <div>
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">所属团队</div>
                <div className="mt-1">{assistant.team_name ?? "--"}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">绑定知识库</div>
                <div className="mt-1">{assistant.knowledge_base_name ?? "--"}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">创建者</div>
                <div className="mt-1">{assistant.created_by_name ?? "--"}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">创建于</div>
                <div className="mt-1">{formatDateTime(assistant.created_at)}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">最近更新</div>
                <div className="mt-1">{formatDateTime(assistant.updated_at)}</div>
              </div>
            </div>
          </div>

          <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">推荐测试问题</h2>
            <div className="mt-4 flex flex-wrap gap-2">
              {(assistant.suggested_prompts.length > 0
                ? assistant.suggested_prompts
                : ["这个助手适合处理哪些问题？"]).map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => void submit(prompt)}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-left text-xs text-slate-700 transition-colors hover:border-teal-200 hover:bg-teal-50 hover:text-teal-700"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        </aside>

        <section className="flex min-h-[680px] flex-col overflow-hidden rounded-[32px] border border-slate-200 bg-white shadow-sm">
          <div ref={scrollRef} className="flex-1 space-y-6 overflow-y-auto px-6 py-6">
            {turns.length === 0 ? (
              <div className="flex h-full min-h-[420px] items-center justify-center">
                <div className="max-w-md text-center">
                  <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-teal-50 text-teal-600">
                    <MessageSquare className="h-7 w-7" />
                  </div>
                  <h2 className="mt-5 text-xl font-semibold text-slate-900">开始一轮即时测试</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    这里会直接用当前助手的知识库、人格和规则模板做真实流式问答。
                  </p>
                </div>
              </div>
            ) : (
              turns.map((turn) => (
                <div key={turn.id} className="space-y-4">
                  <div className="flex justify-end">
                    <div className="max-w-[78%] rounded-3xl rounded-tr-md bg-slate-900 px-5 py-4 text-sm text-white shadow-sm">
                      <div className="mb-2 flex items-center gap-2 text-xs text-slate-300">
                        <User className="h-3.5 w-3.5" />
                        你
                      </div>
                      <p className="whitespace-pre-wrap leading-6">{turn.query}</p>
                    </div>
                  </div>

                  <div className="flex justify-start">
                    <div className="max-w-[88%] rounded-3xl rounded-tl-md border border-slate-200 bg-slate-50 px-5 py-4 shadow-sm">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2 text-sm font-medium text-slate-800">
                          <Bot className="h-4 w-4 text-teal-600" />
                          {assistant.name}
                        </div>
                        {turn.answerStatus ? (
                          <span className="rounded-full bg-white px-2.5 py-1 text-[11px] text-slate-500">
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
                          <Loader2 className="h-4 w-4 animate-spin" />
                          正在生成回答...
                        </div>
                      )}

                      {turn.retrievedDocs.length > 0 ? (
                        <div className="mt-4 border-t border-slate-200 pt-4">
                          <div className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
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
                                  className="w-full rounded-2xl border border-slate-200 bg-white p-4 text-left transition-colors hover:border-teal-200 hover:bg-teal-50/40"
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="text-sm font-medium text-slate-800">{title}</div>
                                    <div className="text-xs text-slate-400">
                                      {expanded ? "收起" : "展开"}
                                    </div>
                                  </div>
                                  {doc.metadata?.category_name ? (
                                    <div className="mt-1 text-xs text-slate-400">
                                      {doc.metadata.category_name}
                                    </div>
                                  ) : null}
                                  <p className={`mt-2 text-sm leading-6 text-slate-600 ${expanded ? "" : "line-clamp-3"}`}>
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

          <div className="border-t border-slate-200 bg-white px-6 py-5">
            <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-3">
              <textarea
                rows={4}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                    event.preventDefault();
                    void submit();
                  }
                }}
                placeholder="输入测试问题，按 Ctrl/Cmd + Enter 发送"
                className="w-full resize-none bg-transparent px-2 py-2 text-sm leading-6 text-slate-800 outline-none placeholder:text-slate-400"
              />
              <div className="mt-3 flex items-center justify-between gap-3">
                <div className="text-xs text-slate-400">
                  当前会话 {sessionId ? "已建立" : "尚未开始"}，回答会使用保存后的真实配置。
                </div>
                <button
                  type="button"
                  disabled={submitLoading || !query.trim()}
                  onClick={() => void submit()}
                  className="inline-flex h-11 items-center gap-2 rounded-2xl bg-gradient-to-r from-teal-500 to-cyan-600 px-5 text-sm font-medium text-white shadow-lg shadow-teal-500/20 transition-all hover:-translate-y-0.5 hover:shadow-xl disabled:opacity-50"
                >
                  {submitLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      发送中...
                    </>
                  ) : (
                    <>
                      <SendHorizonal className="h-4 w-4" />
                      发送
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
