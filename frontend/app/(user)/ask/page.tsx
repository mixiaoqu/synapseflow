"use client";

import type { FormEvent, KeyboardEvent as ReactKeyboardEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  BookOpen,
  ChevronDown,
  Copy,
  History,
  Loader2,
  MessageSquarePlus,
  MoreHorizontal,
  PanelLeft,
  Search,
  SendHorizontal,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  X,
} from "lucide-react";
import { Toaster, toast } from "sonner";

import { AnswerMarkdown } from "@/components/kb-chat/AnswerMarkdown";
import { AnswerSourcesSection } from "@/components/kb-chat/SourcesPanel";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useKbChat } from "@/hooks/useKbChat";
import { kbChatApi } from "@/lib/api/endpoints/kbChat";

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const INPUT_MIN_HEIGHT = 52;
const INPUT_MAX_HEIGHT = 180;

function buildPromptTopic(name: string): string {
  return name.replace(/\s+/g, " ").trim().slice(0, 24);
}

function buildKnowledgeBasePrompts(knowledgeBaseNames: string[]): string[] {
  const templates = [
    (topic: string) => `《${topic}》里有哪些核心内容？`,
    (topic: string) => `基于《${topic}》，帮我梳理关键流程和注意事项`,
    (topic: string) => `《${topic}》中最常见的问题有哪些？`,
    (topic: string) => `如果我是新手，应该怎么快速了解《${topic}》？`,
  ];

  const topics = Array.from(
    new Set(knowledgeBaseNames.map(buildPromptTopic).filter(Boolean)),
  );

  if (topics.length === 0) return [];

  return Array.from({ length: 4 }, (_, index) => {
    const topic = topics[index % topics.length];
    return templates[index % templates.length](topic);
  });
}

/* ------------------------------------------------------------------ */
/*  Helper components                                                  */
/* ------------------------------------------------------------------ */

function getAnswerStatusMeta(status?: string | null, retrievedCount: number = 0) {
  const config: Record<string, { style: string; label: string; hint?: string }> = {
    answered: {
      style: "bg-emerald-50 text-emerald-700 border-emerald-200",
      label: retrievedCount > 0 ? `基于 ${retrievedCount} 篇文档` : "已生成回答",
      hint: retrievedCount > 0 ? "回答内容可结合下方来源继续核对。" : undefined,
    },
    partial: {
      style: "bg-amber-50 text-amber-700 border-amber-200",
      label: "部分内容有依据",
      hint: `当前仅检索到 ${retrievedCount} 篇文档，部分回答可能是归纳结果。`,
    },
    no_answer: {
      style: "bg-slate-50 text-slate-600 border-slate-200",
      label: "未找到直接依据",
      hint: "当前知识范围内没有足够匹配内容，建议换个问法或调整范围。",
    },
    error: {
      style: "bg-red-50 text-red-700 border-red-200",
      label: "回答生成异常",
      hint: "这次回答没有完整生成，可以稍后重试。",
    },
  };

  return config[status || ""] ?? {
    style: "bg-slate-50 text-slate-600 border-slate-200",
    label: "已生成回答",
  };
}

function AnswerStatusBadge({
  status,
  retrievedCount,
}: {
  status?: string | null;
  retrievedCount?: number;
}) {
  if (!status) return null;
  const meta = getAnswerStatusMeta(status, retrievedCount ?? 0);
  return (
    <span className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-none ${meta.style}`}>
      {meta.label}
    </span>
  );
}

function StreamingDots() {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-emerald-500 [animation-delay:0ms]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-emerald-500 [animation-delay:150ms]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-emerald-500 [animation-delay:300ms]" />
    </span>
  );
}

function formatRelativeTime(dateStr?: string | null): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return "";

  const now = Date.now();
  const diffMs = now - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin} 分钟前`;

  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} 小时前`;

  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 7) return `${diffDay} 天前`;

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/* ------------------------------------------------------------------ */
/*  Scope select (native select, same visual style as design)         */
/* ------------------------------------------------------------------ */

function ScopeSelect({
  label,
  value,
  options,
  disabled,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  disabled?: boolean;
  onChange: (v: string) => void;
}) {
  const selected = options.find((o) => o.value === value);

  return (
    <div className="relative">
      <span className="pointer-events-none absolute left-2.5 top-1.5 text-[10px] font-medium uppercase tracking-wide text-slate-400">
        {label}
      </span>
      <select
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 w-full cursor-pointer rounded-lg border border-slate-200 bg-white py-1 pl-[52px] pr-7 text-xs text-slate-700 outline-none transition-colors hover:border-slate-300 hover:bg-slate-50 focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3 w-3 -translate-y-1/2 text-slate-400" />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function AskPage() {
  const {
    query,
    setQuery,
    teamId,
    setTeamId,
    teams,
    teamsLoading,
    selectedTeam,
    knowledgeBaseId,
    setKnowledgeBaseId,
    categoryId,
    setCategoryId,
    knowledgeBases,
    categories,
    loading,
    historyLoading,
    sessionLoading,
    deletingSessionId,
    turns,
    sessions,
    activeSessionId,
    expandedChunks,
    toggleChunk,
    expandChunksForTurn,
    collapseChunksForTurn,
    knowledgeBaseLabel,
    resetConversation,
    openSession,
    deleteSession,
    submit,
  } = useKbChat({ enableScopeFilters: true });

  const messageScrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [feedbackState, setFeedbackState] = useState<Record<number, "up" | "down">>({});
  const [feedbackLoading, setFeedbackLoading] = useState<Record<number, boolean>>({});
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sessionSearch, setSessionSearch] = useState("");
  const [openSourceTurns, setOpenSourceTurns] = useState<Set<string>>(new Set());
  const [activeMenuSession, setActiveMenuSession] = useState<string | null>(null);

  const selectedKnowledgeBase = useMemo(
    () => knowledgeBases.find((kb) => kb.id === knowledgeBaseId) ?? null,
    [knowledgeBaseId, knowledgeBases],
  );

  const promptSourceKnowledgeBases = useMemo(() => {
    const queryable = knowledgeBases.filter((kb) => kb.indexed_document_count > 0);
    if (selectedKnowledgeBase) {
      return selectedKnowledgeBase.indexed_document_count > 0 ? [selectedKnowledgeBase] : [];
    }
    return queryable.slice(0, 4);
  }, [knowledgeBases, selectedKnowledgeBase]);

  const suggestedPrompts = useMemo(
    () => buildKnowledgeBasePrompts(promptSourceKnowledgeBases.map((kb) => kb.name)),
    [promptSourceKnowledgeBases],
  );

  const hasQueryableKnowledge = suggestedPrompts.length > 0;

  const filteredSessions = useMemo(() => {
    const kw = sessionSearch.trim().toLowerCase();
    if (!kw) return sessions;
    return sessions.filter(
      (s) =>
        s.title.toLowerCase().includes(kw) ||
        (s.preview ?? "").toLowerCase().includes(kw),
    );
  }, [sessionSearch, sessions]);

  useEffect(() => {
    setOpenSourceTurns((prev) => {
      const activeTurnIds = new Set(turns.map((t) => t.id));
      const next = new Set(Array.from(prev).filter((id) => activeTurnIds.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [turns]);

  const toggleSourceSection = (turnId: string) => {
    setOpenSourceTurns((prev) => {
      const next = new Set(prev);
      if (next.has(turnId)) next.delete(turnId);
      else next.add(turnId);
      return next;
    });
  };

  /* ---- auto-resize textarea ---- */
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const next = Math.min(Math.max(el.scrollHeight, INPUT_MIN_HEIGHT), INPUT_MAX_HEIGHT);
    el.style.height = `${next}px`;
    el.style.overflowY = el.scrollHeight > INPUT_MAX_HEIGHT ? "auto" : "hidden";
  }, [query]);

  /* ---- auto-scroll ---- */
  useEffect(() => {
    const el = messageScrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: loading ? "auto" : "smooth" });
  }, [loading, turns]);

  const focusInput = () => {
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const handleSubmit = async (event?: FormEvent) => {
    event?.preventDefault();
    const ok = await submit();
    if (ok) focusInput();
  };

  const onTextareaKeyDown = (event: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter") return;
    if (event.shiftKey) return;
    if (event.nativeEvent.isComposing) return;
    event.preventDefault();
    void handleSubmit();
  };

  const submitFeedback = async (logId: number, feedback: "up" | "down") => {
    setFeedbackLoading((prev) => ({ ...prev, [logId]: true }));
    try {
      await kbChatApi.submitFeedback(logId, {
        feedback_value: feedback === "up" ? "helpful" : "not_helpful",
      });
      setFeedbackState((prev) => ({ ...prev, [logId]: feedback }));
      toast.success(feedback === "up" ? "已记录「有帮助」" : "已记录「待改进」");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "反馈提交失败");
    } finally {
      setFeedbackLoading((prev) => ({ ...prev, [logId]: false }));
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    if (!window.confirm("确认删除这条历史会话吗？删除后无法恢复。")) return;
    const ok = await deleteSession(sessionId);
    if (ok) toast.success("历史会话已删除");
    setActiveMenuSession(null);
  };

  /* ================================================================ */
  /*  Sidebar                                                          */
  /* ================================================================ */

  const sidebar = (
    <div className="flex h-full min-h-0 flex-col bg-[#111215] text-slate-200">
      {/* New conversation */}
      <div className="shrink-0 p-3 pb-2">
        <button
          type="button"
          onClick={() => {
            resetConversation();
            setSidebarOpen(false);
            focusInput();
          }}
          className="flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.06] text-sm font-medium text-white transition-colors hover:bg-white/[0.1]"
        >
          <MessageSquarePlus className="h-4 w-4" />
          新建对话
        </button>
      </div>

      {/* Current scope summary */}
      <div className="shrink-0 px-3 pb-2">
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-2.5">
          <p className="text-[10px] font-medium uppercase tracking-widest text-slate-500">当前范围</p>
          <p className="mt-1 truncate text-xs font-medium text-slate-200">
            {selectedTeam?.name ?? (teamsLoading ? "加载中…" : "未选择团队")}
          </p>
          <p className="truncate text-[11px] text-slate-500">
            {selectedKnowledgeBase?.name ?? "全部知识库"}
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="shrink-0 px-3 pb-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
          <input
            value={sessionSearch}
            onChange={(e) => setSessionSearch(e.target.value)}
            placeholder="搜索历史会话…"
            className="h-8 w-full rounded-lg border border-white/[0.06] bg-white/[0.04] pl-8 pr-3 text-xs text-slate-300 outline-none placeholder:text-slate-600 transition focus:border-white/10 focus:bg-white/[0.06]"
          />
        </div>
      </div>

      {/* History label */}
      <div className="shrink-0 px-3 pb-1">
        <p className="text-[10px] font-medium uppercase tracking-widest text-slate-500">历史会话</p>
      </div>

      {/* Session list */}
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {historyLoading ? (
          <div className="space-y-1.5 px-1 pt-1">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-xl bg-white/[0.03] p-3 space-y-2">
                <Skeleton className="h-3.5 w-3/4 bg-white/[0.06]" />
                <Skeleton className="h-3 w-full bg-white/[0.04]" />
              </div>
            ))}
          </div>
        ) : filteredSessions.length === 0 ? (
          <div className="px-2 pt-2">
            <div className="rounded-xl border border-dashed border-white/[0.06] bg-white/[0.02] px-3 py-4 text-center text-xs text-slate-500">
              {sessionSearch ? "没有匹配的会话" : "暂无历史会话"}
            </div>
          </div>
        ) : (
          <div className="space-y-0.5 pt-0.5">
            {filteredSessions.map((session) => {
              const isActive = session.session_id === activeSessionId;
              const isDeleting = deletingSessionId === session.session_id;
              const isMenuOpen = activeMenuSession === session.session_id;
              return (
                <div key={session.session_id} className="group relative">
                  <button
                    type="button"
                    disabled={loading || isDeleting}
                    onClick={() => {
                      void openSession(session.session_id);
                      setSidebarOpen(false);
                    }}
                    className={`w-full rounded-xl px-3 py-2.5 pr-10 text-left transition-colors ${
                      isActive
                        ? "bg-white/[0.08] text-white"
                        : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
                    } ${isDeleting ? "opacity-60" : ""}`}
                  >
                    <p className="truncate text-[13px] font-medium leading-snug">
                      {session.title}
                    </p>
                    <p className="mt-0.5 line-clamp-1 text-[11px] leading-relaxed text-slate-500">
                      {session.preview ?? "继续提问"}
                    </p>
                    <p className="mt-0.5 text-[10px] text-slate-600">
                      {formatRelativeTime(session.updated_at)}
                    </p>
                  </button>

                  {/* More menu */}
                  <button
                    type="button"
                    aria-label="会话操作"
                    disabled={loading || isDeleting}
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveMenuSession(isMenuOpen ? null : session.session_id);
                    }}
                    className={`absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-500 transition ${
                      isActive
                        ? "bg-white/[0.06] text-slate-300 hover:bg-red-500/15 hover:text-red-300"
                        : "opacity-0 group-hover:opacity-100 hover:bg-red-500/15 hover:text-red-300"
                    } disabled:opacity-50`}
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </button>

                  {/* Dropdown menu */}
                  {isMenuOpen && (
                    <div className="absolute right-1.5 top-full z-20 mt-1 w-36 rounded-xl border border-white/10 bg-[#1a1a1f] py-1 shadow-xl">
                      <button
                        type="button"
                        onClick={() => void handleDeleteSession(session.session_id)}
                        className="flex w-full items-center gap-2 px-3 py-2 text-xs text-red-400 transition hover:bg-red-500/10"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        删除会话
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );

  /* ================================================================ */
  /*  Main render                                                      */
  /* ================================================================ */

  return (
    <div className="h-full min-h-0 overflow-hidden bg-slate-50">
      <Toaster position="top-right" richColors />

      <div className="mx-auto grid h-full min-h-0 max-w-[1440px] grid-cols-1 overflow-hidden lg:grid-cols-[260px_minmax(0,1fr)]">

        {/* Desktop sidebar */}
        <aside className="hidden min-h-0 border-r border-black/5 lg:block">
          {sidebar}
        </aside>

        {/* Main content */}
        <div className="grid min-h-0 overflow-hidden grid-rows-[auto_minmax(0,1fr)_auto]">

          {/* ---- Header ---- */}
          <header className="shrink-0 border-b border-slate-200/60 bg-white px-4 py-3 sm:px-5">
            <div className="flex items-center gap-2">
              {/* Mobile sidebar toggle */}
              <button
                type="button"
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition-colors hover:bg-slate-50 lg:hidden"
                onClick={() => setSidebarOpen(true)}
              >
                <PanelLeft className="h-4 w-4" />
              </button>

              {/* Logo */}
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-600 to-teal-600 text-white shadow-sm">
                <BookOpen className="h-4 w-4" />
              </div>

              {/* Scope selectors */}
              <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto pb-0.5">
                <ScopeSelect
                  label="团队"
                  value={teamId != null ? String(teamId) : ""}
                  disabled={teamsLoading || loading}
                  onChange={(v) => {
                    setTeamId(v ? Number(v) : null);
                    setKnowledgeBaseId(null);
                    setCategoryId(null);
                  }}
                  options={[
                    { value: "", label: teamsLoading ? "加载中…" : teams.length > 0 ? "选择团队" : "暂无团队" },
                    ...teams.map((t) => ({ value: String(t.id), label: t.name })),
                  ]}
                />

                {teamId != null && (
                  <>
                    <span className="text-slate-300 shrink-0">/</span>
                    <ScopeSelect
                      label="知识库"
                      value={knowledgeBaseId != null ? String(knowledgeBaseId) : ""}
                      disabled={loading}
                      onChange={(v) => {
                        setKnowledgeBaseId(v ? Number(v) : null);
                        setCategoryId(null);
                      }}
                      options={[
                        { value: "", label: "全部知识库" },
                        ...knowledgeBases.map((kb) => ({ value: String(kb.id), label: kb.name })),
                      ]}
                    />
                  </>
                )}

                {knowledgeBaseId != null && categories.length > 0 && (
                  <>
                    <span className="text-slate-300 shrink-0">/</span>
                    <ScopeSelect
                      label="分类"
                      value={categoryId != null ? String(categoryId) : ""}
                      disabled={loading}
                      onChange={(v) => setCategoryId(v ? Number(v) : null)}
                      options={[
                        { value: "", label: "全部分类" },
                        ...categories.map((c) => ({ value: String(c.id), label: c.name })),
                      ]}
                    />
                  </>
                )}
              </div>

              {/* Session loading indicator */}
              {sessionLoading && (
                <span className="ml-auto flex shrink-0 items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-700">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  切换中
                </span>
              )}
            </div>

            {!teamsLoading && teams.length === 0 && (
              <p className="mt-2 text-xs text-amber-600">
                当前账号还没有加入任何团队，暂时无法发起问答。
              </p>
            )}
          </header>

          {/* ---- Chat messages ---- */}
          <section ref={messageScrollRef} className="min-h-0 overflow-y-auto px-4 py-6 sm:px-6">

            {turns.length === 0 ? (
              /* Empty state */
              <div className="mx-auto flex max-w-2xl flex-col items-center justify-center px-4 py-12 text-center sm:py-20">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-600 to-teal-600 text-white shadow-lg shadow-emerald-600/20">
                  <BookOpen className="h-6 w-6" />
                </div>

                <h1 className="mt-6 text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">
                  想了解哪个业务功能？
                </h1>
                <p className="mt-3 max-w-lg text-sm leading-relaxed text-slate-500">
                  选择团队和知识范围后，直接提问即可。系统会基于已发布的知识库内容回答你的问题。
                </p>

                <div className="mt-8 grid w-full gap-2.5 sm:grid-cols-2">
                  {hasQueryableKnowledge ? (
                    suggestedPrompts.map((item) => (
                      <button
                        key={item}
                        type="button"
                        disabled={loading || teamId == null}
                        onClick={() => {
                          setQuery(item);
                          focusInput();
                        }}
                        className="group flex items-start gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3.5 text-left text-sm text-slate-700 shadow-sm transition-colors hover:border-emerald-200 hover:text-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400 group-hover:text-emerald-500" />
                        <span className="leading-relaxed">{item}</span>
                      </button>
                    ))
                  ) : (
                    <div className="sm:col-span-2 rounded-2xl border border-dashed border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-800">
                      请先上传文档，并确保至少有一篇文档完成索引后，再使用智能示例提问。
                    </div>
                  )}
                </div>
              </div>
            ) : (
              /* Conversation turns */
              <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 pb-4">
                {turns.map((turn) => {
                  const feedbackLogId = typeof turn.logId === "number" ? turn.logId : null;
                  const isStreaming = !turn.error && !turn.answer && loading;
                  const uniqueDocCount = new Set(
                    turn.retrievedDocs.map((doc) => doc.metadata?.document_id).filter((id): id is number => id != null),
                  ).size;
                  const retrievedDocCount = uniqueDocCount > 0 ? uniqueDocCount : turn.retrievedDocs.length;
                  const answerMeta = getAnswerStatusMeta(turn.answerStatus, retrievedDocCount);

                  return (
                    <div key={turn.id} className="space-y-3">
                      {/* User message */}
                      {turn.query && (
                        <div className="flex justify-end">
                          <div className="max-w-[82%] rounded-2xl rounded-br-md bg-slate-800 px-4 py-3 text-[15px] leading-relaxed text-white shadow-sm">
                            {turn.query}
                          </div>
                        </div>
                      )}

                      {/* Assistant response */}
                      {(turn.answer || turn.error || isStreaming) && (
                        <div className="flex justify-start">
                          <div className="w-full max-w-[90%] rounded-2xl border border-slate-100 bg-white px-5 py-4 shadow-sm">
                            {/* Header */}
                            <div className="mb-3 flex items-center gap-2">
                              <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-emerald-50">
                                <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
                              </div>
                              <span className="text-xs font-medium text-slate-500">知识助手</span>
                              <AnswerStatusBadge status={turn.answerStatus} retrievedCount={retrievedDocCount} />
                            </div>

                            {/* Hint */}
                            {turn.answerStatus && answerMeta.hint && (
                              <p className="mb-3 text-xs leading-relaxed text-slate-500">{answerMeta.hint}</p>
                            )}

                            {/* Error */}
                            {turn.error && (
                              <div className="rounded-lg border border-red-100 bg-red-50 px-3 py-2.5 text-sm text-red-700">
                                {turn.error}
                              </div>
                            )}

                            {/* Streaming */}
                            {isStreaming && (
                              <div className="flex items-center gap-2.5 py-2 text-sm text-slate-500">
                                <StreamingDots />
                                <span>正在检索知识并生成回答…</span>
                              </div>
                            )}

                            {/* Answer */}
                            {turn.answer && <AnswerMarkdown text={turn.answer} />}

                            {/* Sources */}
                            <AnswerSourcesSection
                              turn={turn}
                              open={openSourceTurns.has(turn.id)}
                              expandedChunks={expandedChunks}
                              onToggleSection={() => toggleSourceSection(turn.id)}
                              onToggleChunk={toggleChunk}
                              onExpandTurn={() => expandChunksForTurn(turn.id, turn.retrievedDocs)}
                              onCollapseTurn={() => collapseChunksForTurn(turn.id, turn.retrievedDocs)}
                            />

                            {/* Feedback + copy */}
                            {turn.answer && feedbackLogId !== null && !isStreaming && (
                              <div className="mt-4 flex items-center gap-3 border-t border-slate-50 pt-3">
                                <span className="text-[11px] text-slate-400">这条回答有帮助吗？</span>
                                <div className="flex items-center gap-1">
                                  <button
                                    type="button"
                                    disabled={feedbackLoading[feedbackLogId] === true}
                                    onClick={() => void submitFeedback(feedbackLogId, "up")}
                                    className={`inline-flex h-7 items-center gap-1 rounded-md border px-2 text-[11px] transition-colors disabled:opacity-50 ${
                                      feedbackState[feedbackLogId] === "up"
                                        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                        : "border-slate-150 bg-white text-slate-500 hover:bg-slate-50"
                                    }`}
                                  >
                                    <ThumbsUp className="h-3 w-3" />
                                    有帮助
                                  </button>
                                  <button
                                    type="button"
                                    disabled={feedbackLoading[feedbackLogId] === true}
                                    onClick={() => void submitFeedback(feedbackLogId, "down")}
                                    className={`inline-flex h-7 items-center gap-1 rounded-md border px-2 text-[11px] transition-colors disabled:opacity-50 ${
                                      feedbackState[feedbackLogId] === "down"
                                        ? "border-amber-200 bg-amber-50 text-amber-700"
                                        : "border-slate-150 bg-white text-slate-500 hover:bg-slate-50"
                                    }`}
                                  >
                                    <ThumbsDown className="h-3 w-3" />
                                    需改进
                                  </button>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => void navigator.clipboard.writeText(turn.answer ?? "").then(() => toast.success("答案已复制"))}
                                  className="ml-auto inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-slate-400 transition-colors hover:bg-slate-50 hover:text-slate-600"
                                >
                                  <Copy className="h-3 w-3" />
                                  复制
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* ---- Input footer ---- */}
          <footer className="shrink-0 border-t border-slate-200/60 bg-white px-4 pb-4 pt-3 sm:px-5">
            <form onSubmit={handleSubmit}>
              <div className="mx-auto max-w-3xl">
                <div className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-white shadow-sm transition-all focus-within:border-emerald-300 focus-within:ring-2 focus-within:ring-emerald-100">
                  <Textarea
                    ref={textareaRef}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={onTextareaKeyDown}
                    disabled={loading || teamId == null}
                    rows={1}
                    placeholder={
                      teamId == null
                        ? "请先选择团队，再开始提问…"
                        : "询问业务功能、操作步骤、审批规则或异常原因…"
                    }
                    className="min-h-[52px] max-h-[180px] resize-none border-0 bg-transparent px-4 py-3 text-[15px] leading-relaxed shadow-none placeholder:text-slate-400 focus-visible:ring-0"
                  />
                  <div className="shrink-0 px-3 pb-3">
                    <Button
                      type="submit"
                      disabled={loading || !query.trim() || teamId == null}
                      className="h-9 rounded-xl bg-emerald-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-emerald-500 disabled:opacity-40"
                    >
                      {loading ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <SendHorizontal className="h-3.5 w-3.5" />
                      )}
                    </Button>
                  </div>
                </div>
                <p className="mt-1.5 text-center text-xs text-slate-400">
                  {knowledgeBaseLabel}
                  <span className="mx-1.5 text-slate-200">·</span>
                  Enter 发送，Shift+Enter 换行
                </p>
              </div>
            </form>
          </footer>
        </div>
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-[85vw] max-w-[300px] shadow-2xl">
            <div className="flex h-12 items-center justify-between border-b border-white/[0.06] bg-[#111215] px-3 text-white">
              <span className="text-sm font-medium">会话列表</span>
              <button
                type="button"
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-white/[0.06] hover:text-white"
                onClick={() => setSidebarOpen(false)}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            {sidebar}
          </div>
        </div>
      )}
    </div>
  );
}