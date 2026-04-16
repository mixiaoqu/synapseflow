"use client";

import type { FormEvent, KeyboardEvent as ReactKeyboardEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Bot,
  ChevronDown,
  Copy,
  Loader2,
  Menu,
  MessageCircleMore,
  MessageSquarePlus,
  Search,
  SendHorizontal,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { Toaster, toast } from "sonner";

import { AnswerMarkdown } from "@/components/kb-chat/AnswerMarkdown";
import { AnswerSourcesSection } from "@/components/kb-chat/SourcesPanel";
import { useAssistantChat } from "@/hooks/useAssistantChat";
import { kbChatApi } from "@/lib/api/endpoints/kbChat";
import { cn } from "@/lib/utils";

const INPUT_MIN_HEIGHT = 36;
const INPUT_MAX_HEIGHT = 200;
const SESSION_GROUP_ORDER = ["今天", "昨天", "本周早些时候", "更早"] as const;

function getDayBucket(dateString?: string | null): string {
  if (!dateString) return "更早";
  const value = new Date(dateString);
  if (Number.isNaN(value.getTime())) return "更早";

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfTarget = new Date(value.getFullYear(), value.getMonth(), value.getDate());
  const diffDays = Math.floor(
    (startOfToday.getTime() - startOfTarget.getTime()) / (24 * 60 * 60 * 1000),
  );

  if (diffDays <= 0) return "今天";
  if (diffDays === 1) return "昨天";
  if (diffDays <= 7) return "本周早些时候";
  return "更早";
}

function formatRelativeTime(dateString?: string | null): string {
  if (!dateString) return "";
  const value = new Date(dateString);
  if (Number.isNaN(value.getTime())) return "";

  const diffMs = Date.now() - value.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);
  if (diffMinutes < 1) return "刚刚";
  if (diffMinutes < 60) return `${diffMinutes} 分钟前`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} 小时前`;

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(value);
}

function getAnswerStatusMeta(status?: string | null, retrievedCount: number = 0) {
  switch (status) {
    case "answered":
      return {
        label: retrievedCount > 0 ? `基于 ${retrievedCount} 篇文档` : "已生成回答",
        className: "border-emerald-200 bg-emerald-50 text-emerald-700",
      };
    case "partial":
      return {
        label: "部分有依据",
        className: "border-amber-200 bg-amber-50 text-amber-700",
      };
    case "no_answer":
      return {
        label: "未找到直接依据",
        className: "border-slate-200 bg-slate-50 text-slate-600",
      };
    case "error":
      return {
        label: "回答生成异常",
        className: "border-red-200 bg-red-50 text-red-700",
      };
    default:
      return {
        label: status ?? "已生成回答",
        className: "border-slate-200 bg-slate-50 text-slate-600",
      };
  }
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
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-medium",
        meta.className,
      )}
    >
      {meta.label}
    </span>
  );
}

function AssistantReplySkeleton() {
  return (
    <div className="space-y-2.5">
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <Loader2 className="h-4 w-4 animate-spin text-emerald-500" />
        <span>正在生成回答...</span>
      </div>
      <div className="space-y-2">
        <div className="h-3.5 w-full animate-pulse rounded bg-slate-100" />
        <div className="h-3.5 w-11/12 animate-pulse rounded bg-slate-100" />
        <div className="h-3.5 w-8/12 animate-pulse rounded bg-slate-100" />
      </div>
    </div>
  );
}

export default function AskPage() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedAssistantId = useMemo(() => {
    const rawValue = searchParams.get("assistantId");
    if (!rawValue) return null;
    const parsed = Number(rawValue);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);

  const {
    teamsLoading,
    selectedTeam,
    assistants,
    assistantsLoading,
    assistantsReady,
    selectedAssistantId,
    selectedAssistant,
    setSelectedAssistantId,
    query,
    setQuery,
    loading,
    sessionLoading,
    deletingSessionId,
    historyLoading,
    turns,
    sessions,
    activeSessionId,
    expandedChunks,
    openSourceTurnIds,
    toggleChunk,
    toggleSourceTurn,
    expandChunksForTurn,
    collapseChunksForTurn,
    resetConversation,
    openSession,
    deleteSession,
    submit,
  } = useAssistantChat();

  const [feedbackState, setFeedbackState] = useState<Record<number, "up" | "down">>({});
  const [feedbackLoading, setFeedbackLoading] = useState<Record<number, boolean>>({});
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [assistantMenuOpen, setAssistantMenuOpen] = useState(false);
  const [sessionSearch, setSessionSearch] = useState("");
  const invalidDeepLinkRef = useRef<number | null>(null);
  const previousTeamIdRef = useRef<number | null>(null);
  const suppressInvalidAssistantToastRef = useRef(false);
  const messageScrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const suggestedPrompts = useMemo(
    () => (selectedAssistant?.suggested_prompts ?? []).slice(0, 3),
    [selectedAssistant?.suggested_prompts],
  );

  const filteredSessions = useMemo(() => {
    const keyword = sessionSearch.trim().toLowerCase();
    if (!keyword) return sessions;
    return sessions.filter(
      (item) =>
        item.title.toLowerCase().includes(keyword) ||
        (item.preview ?? "").toLowerCase().includes(keyword),
    );
  }, [sessionSearch, sessions]);

  const groupedSessions = useMemo(() => {
    const buckets = new Map<string, typeof filteredSessions>();
    filteredSessions.forEach((session) => {
      const label = getDayBucket(session.updated_at);
      buckets.set(label, [...(buckets.get(label) ?? []), session]);
    });

    return SESSION_GROUP_ORDER.map((label) => ({
      label,
      items: buckets.get(label) ?? [],
    })).filter((group) => group.items.length > 0);
  }, [filteredSessions]);

  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;
    element.style.height = "auto";
    const nextHeight = Math.min(
      Math.max(element.scrollHeight, INPUT_MIN_HEIGHT),
      INPUT_MAX_HEIGHT,
    );
    element.style.height = `${nextHeight}px`;
    element.style.overflowY = element.scrollHeight > INPUT_MAX_HEIGHT ? "auto" : "hidden";
  }, [query]);

  useEffect(() => {
    const element = messageScrollRef.current;
    if (!element) return;
    element.scrollTo({
      top: element.scrollHeight,
      behavior: loading ? "auto" : "smooth",
    });
  }, [loading, turns, selectedAssistantId]);

  useEffect(() => {
    const nextTeamId = selectedTeam?.id ?? null;
    if (previousTeamIdRef.current == null) {
      previousTeamIdRef.current = nextTeamId;
      return;
    }

    if (previousTeamIdRef.current !== nextTeamId) {
      suppressInvalidAssistantToastRef.current = true;
      previousTeamIdRef.current = nextTeamId;
    }
  }, [selectedTeam?.id]);

  useEffect(() => {
    if (teamsLoading || !assistantsReady || assistantsLoading) return;

    if (requestedAssistantId == null) {
      invalidDeepLinkRef.current = null;
      suppressInvalidAssistantToastRef.current = false;
      return;
    }

    if (assistants.some((item) => item.id === requestedAssistantId)) {
      setSelectedAssistantId((current) =>
        current === requestedAssistantId ? current : requestedAssistantId,
      );
      invalidDeepLinkRef.current = null;
      suppressInvalidAssistantToastRef.current = false;
      return;
    }

    if (invalidDeepLinkRef.current === requestedAssistantId) {
      return;
    }

    invalidDeepLinkRef.current = requestedAssistantId;
    if (suppressInvalidAssistantToastRef.current) {
      suppressInvalidAssistantToastRef.current = false;
    } else {
      toast.error("???????????????????????????????");
    }

    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete("assistantId");
    const nextHref = nextParams.size > 0 ? `${pathname}?${nextParams.toString()}` : pathname;
    router.replace(nextHref, { scroll: false });
  }, [
    assistants,
    assistantsLoading,
    pathname,
    requestedAssistantId,
    router,
    searchParams,
    teamsLoading,
    assistantsReady,
    setSelectedAssistantId,
  ]);

  useEffect(() => {
    if (teamsLoading || !assistantsReady || assistantsLoading) return;

    const nextParams = new URLSearchParams(searchParams.toString());
    const currentParam = nextParams.get("assistantId");
    const targetValue = selectedAssistantId != null ? String(selectedAssistantId) : null;

    if (targetValue == null) {
      if (!currentParam) return;
      nextParams.delete("assistantId");
    } else if (currentParam === targetValue) {
      return;
    } else {
      nextParams.set("assistantId", targetValue);
    }

    const nextHref = nextParams.size > 0 ? `${pathname}?${nextParams.toString()}` : pathname;
    router.replace(nextHref, { scroll: false });
  }, [assistantsLoading, assistantsReady, pathname, router, searchParams, selectedAssistantId, teamsLoading]);

  const focusInput = () => {
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const handleSubmit = async (event?: FormEvent) => {
    event?.preventDefault();
    const ok = await submit();
    if (ok) {
      focusInput();
    }
  };

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
      return;
    }
    event.preventDefault();
    void handleSubmit();
  };

  const handleDeleteSession = async (sessionId: string) => {
    if (!window.confirm("确认删除这条历史会话吗？删除后无法恢复。")) {
      return;
    }

    const ok = await deleteSession(sessionId);
    if (ok) {
      toast.success("历史会话已删除");
    }
  };

  const handleCopyText = async (text: string, successText: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(successText);
    } catch {
      toast.error("复制失败，请稍后重试");
    }
  };

  const submitFeedback = async (logId: number, feedback: "up" | "down") => {
    setFeedbackLoading((current) => ({ ...current, [logId]: true }));
    try {
      await kbChatApi.submitFeedback(logId, {
        feedback_value: feedback === "up" ? "helpful" : "not_helpful",
      });
      setFeedbackState((current) => ({ ...current, [logId]: feedback }));
      toast.success(feedback === "up" ? "已记录“有帮助”" : "已记录“需改进”");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "反馈提交失败");
    } finally {
      setFeedbackLoading((current) => ({ ...current, [logId]: false }));
    }
  };

  const sidebar = (
    <div className="flex h-full min-h-0 flex-col bg-[#111215] text-slate-200">
      <div className="shrink-0 px-3 pb-2 pt-3">
        <div className="text-xs font-medium text-slate-400">历史会话</div>
        <div className="relative mt-2">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-slate-500" />
          <input
            value={sessionSearch}
            onChange={(event) => setSessionSearch(event.target.value)}
            placeholder="搜索..."
            className="h-8 w-full rounded-lg border border-white/10 bg-white/[0.05] pl-8 pr-2 text-[11px] text-slate-200 outline-none placeholder:text-slate-500 focus:border-white/20"
          />
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-white/10 hover:[&::-webkit-scrollbar-thumb]:bg-white/20">
        {historyLoading ? (
          <div className="space-y-1.5">
            {Array.from({ length: 4 }).map((_, index) => (
              <div
                key={index}
                className="rounded-xl border border-white/5 bg-white/[0.03] px-2.5 py-2"
              >
                <div className="h-2.5 w-3/4 animate-pulse rounded-full bg-white/[0.08]" />
                <div className="mt-1.5 h-2 w-full animate-pulse rounded-full bg-white/[0.05]" />
              </div>
            ))}
          </div>
        ) : selectedAssistantId == null ? (
          <div className="rounded-xl border border-dashed border-white/10 bg-white/[0.02] mx-1 px-3 py-4 text-center text-[11px] text-slate-500">
            选择助手后展示历史会话
          </div>
        ) : groupedSessions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-white/10 bg-white/[0.02] mx-1 px-3 py-4 text-center text-[11px] text-slate-500">
            {sessionSearch ? "没有匹配的会话" : "暂无历史会话"}
          </div>
        ) : (
          <div className="space-y-2">
            {groupedSessions.map((group) => (
              <div key={group.label} className="space-y-0.5">
                <div className="px-2 text-[10px] font-medium uppercase tracking-wider text-slate-500">
                  {group.label}
                </div>
                {group.items.map((session) => {
                  const active = session.session_id === activeSessionId;
                  const deleting = deletingSessionId === session.session_id;
                  return (
                    <div
                      key={session.session_id}
                      className={cn(
                        "group rounded-lg py-1.5 px-1.5 transition-all cursor-pointer",
                        active
                          ? "bg-white/[0.08]"
                          : "hover:bg-white/[0.04]",
                      )}
                    >
                      <div className="flex items-start gap-2">
                        <button
                          type="button"
                          disabled={loading || deleting}
                          onClick={() => {
                            void openSession(session.session_id);
                            setSidebarOpen(false);
                          }}
                          className="min-w-0 flex-1 text-left"
                        >
                          <div className="min-w-0 flex-1">
                            <div
                              className={cn(
                                "truncate text-[12px] font-medium leading-snug",
                                active ? "text-white" : "text-slate-300",
                              )}
                            >
                              {session.title}
                            </div>
                            <div className="line-clamp-1 text-[11px] text-slate-500 mt-0.5">
                              {session.preview ?? "继续对话"}
                            </div>
                          </div>
                        </button>
                        <button
                          type="button"
                          disabled={loading || deleting}
                          onClick={(e) => {
                            e.stopPropagation();
                            void handleDeleteSession(session.session_id);
                          }}
                          className="opacity-0 group-hover:opacity-100 shrink-0 p-1 rounded text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                          aria-label="删除会话"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-white/5 px-3 py-2.5">
        <button
          type="button"
          disabled={selectedAssistantId == null}
          onClick={() => {
            resetConversation();
            setSidebarOpen(false);
            focusInput();
          }}
          className="flex h-9 w-full items-center justify-center gap-1.5 rounded-lg bg-emerald-600 text-xs font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <MessageSquarePlus className="h-3.5 w-3.5" />
          新建对话
        </button>
      </div>
    </div>
  );

  return (
    <div className="h-full min-h-0 overflow-hidden bg-[#f8fafc]">
      <Toaster position="top-right" richColors />

      <div className="grid h-full min-h-0 grid-cols-1 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="hidden min-h-0 border-r border-slate-200/70 lg:block">{sidebar}</aside>

        <main className="relative grid min-h-0 grid-rows-[auto_minmax(0,1fr)] overflow-hidden">
          <div className="shrink-0 border-b border-slate-200/70 bg-white px-4 py-3 sm:px-6">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setSidebarOpen(true)}
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition-colors hover:bg-slate-50 lg:hidden"
                aria-label="打开历史会话"
              >
                <Menu className="h-4 w-4" />
              </button>

              <span className="text-xs text-slate-400">
                {selectedTeam?.name ?? (teamsLoading ? "加载中..." : "未选择团队")}
              </span>

              {sessionLoading ? (
                <span className="ml-auto flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] text-emerald-600">
                  <Loader2 className="h-2.5 w-2.5 animate-spin" />
                  切换中
                </span>
              ) : null}
            </div>

            <div className="mt-2 relative">
              <button
                type="button"
                onClick={() => setAssistantMenuOpen((current) => !current)}
                className="flex w-full items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-left transition-colors hover:border-slate-300 hover:bg-white"
              >
                {selectedAssistant ? (
                  <>
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-emerald-500 text-white">
                      <Bot className="h-3.5 w-3.5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-slate-900">
                        {selectedAssistant.name}
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-slate-100 text-slate-400">
                      <Bot className="h-3.5 w-3.5" />
                    </div>
                    <div className="text-sm text-slate-500">选择助手</div>
                  </>
                )}
                <ChevronDown
                  className={cn(
                    "h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform",
                    assistantMenuOpen && "rotate-180",
                  )}
                />
              </button>

              {assistantMenuOpen ? (
                <div className="absolute left-0 right-0 top-[calc(100%+0.25rem)] z-20 rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
                  {assistantsLoading ? (
                    <div className="flex items-center justify-center py-4 text-xs text-slate-500">
                      <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
                      加载中...
                    </div>
                  ) : assistants.length === 0 ? (
                    <div className="py-4 text-center text-xs text-slate-500">
                      暂无可用助手
                    </div>
                  ) : (
                    <div className="space-y-0.5">
                      {assistants.map((assistant) => {
                        const active = assistant.id === selectedAssistantId;
                        return (
                          <button
                            key={assistant.id}
                            type="button"
                            onClick={() => {
                              setSelectedAssistantId(assistant.id);
                              setAssistantMenuOpen(false);
                            }}
                            className={cn(
                              "flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left transition-colors",
                              active
                                ? "bg-emerald-50 text-emerald-700"
                                : "text-slate-600 hover:bg-slate-50",
                            )}
                          >
                            <div
                              className={cn(
                                "flex h-6 w-6 shrink-0 items-center justify-center rounded text-[10px]",
                                active
                                  ? "bg-emerald-500 text-white"
                                  : "bg-slate-100 text-slate-500",
                              )}
                            >
                              <Bot className="h-3 w-3" />
                            </div>
                            <span className="truncate text-xs font-medium">
                              {assistant.name}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          </div>

          <section ref={messageScrollRef} className="min-h-0 overflow-y-auto px-4 pb-24 pt-3 sm:px-6 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-slate-200 hover:[&::-webkit-scrollbar-thumb]:bg-slate-300">
            {selectedAssistant == null ? (
              <div className="flex h-full min-h-[420px] items-center justify-center">
                <div className="max-w-xl text-center">
                  <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-white text-slate-400 shadow-sm">
                    <Sparkles className="h-8 w-8" />
                  </div>
                  <h2 className="mt-6 text-2xl font-semibold text-slate-900">
                    请选择一个助手开始问答
                  </h2>
                  <p className="mt-3 text-sm leading-7 text-slate-500">
                    这里不再要求你选择知识库或分类。只需要选择一个助手，就能进入对应的企业知识问答场景。
                  </p>
                </div>
              </div>
            ) : turns.length === 0 ? (
              <div className="flex h-full min-h-[420px] items-center justify-center">
                <div className="max-w-xl text-center">
                  <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-white text-slate-400 shadow-sm">
                    <MessageCircleMore className="h-8 w-8" />
                  </div>
                  <h2 className="mt-6 text-2xl font-semibold text-slate-900">
                    开始与 {selectedAssistant.name} 对话
                  </h2>
                  <p className="mt-3 text-sm leading-7 text-slate-500">
                    切换助手时会保留各自的会话历史，方便你分别验证不同助手的效果。
                  </p>
                </div>
              </div>
            ) : (
              <div className="mx-auto max-w-3xl space-y-4">
                {turns.map((turn) => {
                  const uniqueDocCount = new Set(
                    turn.retrievedDocs
                      .map((doc) => doc.metadata?.document_id)
                      .filter((id): id is number => id != null),
                  ).size;
                  const retrievedCount =
                    uniqueDocCount > 0 ? uniqueDocCount : turn.retrievedDocs.length;
                  const turnIsPending = loading && !turn.answer && !turn.error;
                  const feedbackLogId = typeof turn.logId === "number" ? turn.logId : null;

                  return (
                    <div key={turn.id} className="space-y-3">
                      <div className="flex items-start justify-end gap-2">
                        <div className="rounded-2xl bg-[#1e293b] px-4 py-2.5 text-[14px] leading-5 text-white">
                          <p className="whitespace-pre-wrap">{turn.query}</p>
                        </div>
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-600">
                          <UserRound className="h-5.5 w-5.5" />
                        </div>
                      </div>

                      <div className="flex items-start gap-2">
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
                          <Bot className="h-5.5 w-5.5" />
                        </div>
                        <div className="min-w-0 flex-1 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                          <div className="flex items-center justify-end mb-2">
                            <AnswerStatusBadge
                              status={turn.answerStatus}
                              retrievedCount={retrievedCount}
                            />
                          </div>

                          {turn.error ? (
                            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                              {turn.error}
                            </div>
                          ) : turnIsPending ? (
                            <AssistantReplySkeleton />
                          ) : (
                            <AnswerMarkdown text={turn.answer} />
                          )}

                          <AnswerSourcesSection
                            turn={turn}
                            open={openSourceTurnIds.has(turn.id)}
                            expandedChunks={expandedChunks}
                            onToggleSection={() => toggleSourceTurn(turn.id)}
                            onToggleChunk={toggleChunk}
                            onExpandTurn={() => expandChunksForTurn(turn.id, turn.retrievedDocs)}
                            onCollapseTurn={() =>
                              collapseChunksForTurn(turn.id, turn.retrievedDocs)
                            }
                          />
                          {turn.answer && feedbackLogId != null && !turnIsPending ? (
                            <div className="mt-2.5 flex items-center gap-2 border-t border-slate-100 pt-2">
                              <span className="text-[11px] text-slate-400 mr-1">
                                这条回答有帮助吗？
                              </span>
                              <button
                                type="button"
                                disabled={feedbackLoading[feedbackLogId] === true}
                                onClick={() => void submitFeedback(feedbackLogId, "up")}
                                className={cn(
                                  "inline-flex h-7 items-center gap-1 rounded-full border px-2.5 text-[11px] transition-colors disabled:opacity-50",
                                  feedbackState[feedbackLogId] === "up"
                                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                    : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50",
                                )}
                              >
                                <ThumbsUp className="h-3 w-3" />
                              </button>
                              <button
                                type="button"
                                disabled={feedbackLoading[feedbackLogId] === true}
                                onClick={() => void submitFeedback(feedbackLogId, "down")}
                                className={cn(
                                  "inline-flex h-7 items-center gap-1 rounded-full border px-2.5 text-[11px] transition-colors disabled:opacity-50",
                                  feedbackState[feedbackLogId] === "down"
                                    ? "border-amber-200 bg-amber-50 text-amber-700"
                                    : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50",
                                )}
                              >
                                <ThumbsDown className="h-3 w-3" />
                              </button>
                              <button
                                type="button"
                                onClick={() => void handleCopyText(turn.answer, "答案已复制")}
                                className="ml-auto inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] text-slate-400 transition-colors hover:bg-slate-50 hover:text-slate-600"
                              >
                                <Copy className="h-3 w-3" />
                              </button>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <footer className="fixed bottom-3 left-1/2 w-[calc(100%-2rem)] max-w-3xl -translate-x-1/2 z-10 sm:w-[calc(100%-3rem)]">
            <form onSubmit={handleSubmit}>
              <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-2 shadow-sm">
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={selectedAssistant == null || loading}
                  placeholder={
                    selectedAssistant?.placeholder_text ||
                    "输入您的问题"
                  }
                  className="flex-1 resize-none border-0 bg-transparent text-[15px] leading-7 text-slate-800 placeholder:text-slate-400 outline-none disabled:cursor-not-allowed"
                />
                <button
                  type="submit"
                  disabled={selectedAssistant == null || loading || !query.trim()}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-500 transition-colors hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin text-white" />
                  ) : (
                    <SendHorizontal className="h-4 w-4 text-white" />
                  )}
                </button>
              </div>
            </form>
          </footer>
        </main>
      </div>

      {sidebarOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-[80vw] max-w-[320px] shadow-2xl">
            <div className="flex h-12 items-center justify-between border-b border-white/5 bg-[#111215] px-3 text-white">
              <span className="text-sm font-medium">历史会话</span>
              <button
                type="button"
                onClick={() => setSidebarOpen(false)}
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-white/[0.06] hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            {sidebar}
          </div>
        </div>
      ) : null}
    </div>
  );
}
