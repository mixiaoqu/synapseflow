"use client";

import { Suspense } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Bot,
  ChevronDown,
  ChevronRight,
  Loader2,
  MessageCircleMore,
  Plus,
  Quote,
  SendHorizonal,
  Sparkles,
  UserRound,
} from "lucide-react";
import { Toaster, toast } from "sonner";

import { AnswerMarkdown } from "@/components/kb-chat/AnswerMarkdown";
import {
  assistantsApi,
  type AssistantProfile,
  type AssistantSummary,
} from "@/lib/api/assistants";
import {
  listKnowledgeBases,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
import { kbChatApi, type AskTeamOption, type RetrievedDoc } from "@/lib/api/endpoints/kbChat";
import { consumeSseStream } from "@/lib/stream/sse";
import { cn } from "@/lib/utils";
import { v4 as uuidv4 } from "uuid";

interface AssistantTurn {
  id: string;
  query: string;
  answer: string;
  answerStatus?: string | null;
  logId?: number | null;
  retrievedDocs: RetrievedDoc[];
  error: string | null;
}

interface AssistantConversationState {
  turns: AssistantTurn[];
  sessionId: string | null;
  expandedChunkKeys: string[];
  openSourceTurnIds: string[];
}

interface PendingAssistantSelection {
  assistantId: number;
  teamId: number;
  knowledgeBaseId: number;
}

const EMPTY_CONVERSATION: AssistantConversationState = {
  turns: [],
  sessionId: null,
  expandedChunkKeys: [],
  openSourceTurnIds: [],
};

function createEmptyConversation(): AssistantConversationState {
  return {
    turns: [],
    sessionId: null,
    expandedChunkKeys: [],
    openSourceTurnIds: [],
  };
}

function buildChunkKey(turnId: string, index: number): string {
  return `${turnId}-${index}`;
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

function sortAssistants(items: AssistantSummary[]): AssistantSummary[] {
  return [...items].sort((left, right) => {
    const teamCompare = (left.team_name ?? "").localeCompare(right.team_name ?? "", "zh-CN");
    if (teamCompare !== 0) return teamCompare;
    const kbCompare = (left.knowledge_base_name ?? "").localeCompare(
      right.knowledge_base_name ?? "",
      "zh-CN",
    );
    if (kbCompare !== 0) return kbCompare;
    if (left.sort_order !== right.sort_order) return left.sort_order - right.sort_order;
    return left.name.localeCompare(right.name, "zh-CN");
  });
}

function mergeAssistantItems(
  items: AssistantSummary[],
  directAssistant: AssistantProfile | null,
  filters: { teamId: number | null; knowledgeBaseId: number | null },
): AssistantSummary[] {
  if (!directAssistant || filters.teamId !== directAssistant.team_id) {
    return sortAssistants(items);
  }
  if (
    filters.knowledgeBaseId != null &&
    filters.knowledgeBaseId !== directAssistant.knowledge_base_id
  ) {
    return sortAssistants(items);
  }
  if (items.some((item) => item.id === directAssistant.id)) {
    return sortAssistants(items);
  }
  return sortAssistants([directAssistant, ...items]);
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/70 bg-white/80 px-4 py-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 text-sm font-medium text-slate-700">{value}</div>
    </div>
  );
}

function AssistantReplySkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />
        正在生成回答...
      </div>
      <div className="space-y-2">
        <div className="h-3 w-11/12 animate-pulse rounded-full bg-slate-200" />
        <div className="h-3 w-full animate-pulse rounded-full bg-slate-200" />
        <div className="h-3 w-8/12 animate-pulse rounded-full bg-slate-200" />
      </div>
    </div>
  );
}

function ReferenceDocsSection({
  turn,
  open,
  expandedChunkKeys,
  onToggleSection,
  onToggleChunk,
}: {
  turn: AssistantTurn;
  open: boolean;
  expandedChunkKeys: Set<string>;
  onToggleSection: () => void;
  onToggleChunk: (key: string) => void;
}) {
  if (turn.retrievedDocs.length === 0) return null;

  return (
    <div className="mt-4 rounded-3xl border border-slate-200 bg-slate-50/80 p-3">
      <button
        type="button"
        onClick={onToggleSection}
        className="flex w-full items-center justify-between gap-3 rounded-2xl px-2 py-1 text-left"
      >
        <div>
          <div className="text-sm font-semibold text-slate-800">参考片段</div>
          <div className="mt-1 text-xs text-slate-500">
            命中 {turn.retrievedDocs.length} 条片段，点击可展开查看原文。
          </div>
        </div>
        {open ? (
          <ChevronDown className="h-4 w-4 text-emerald-600" />
        ) : (
          <ChevronRight className="h-4 w-4 text-slate-400" />
        )}
      </button>

      {open ? (
        <div className="mt-3 space-y-2.5">
          {turn.retrievedDocs.map((doc, index) => {
            const key = buildChunkKey(turn.id, index);
            const expanded = expandedChunkKeys.has(key);
            const title = doc.metadata?.document_title?.trim() || `参考片段 ${index + 1}`;
            const category = doc.metadata?.category_name?.trim() || "未分类";
            const content = doc.content?.trim() || "暂无可展示内容";

            return (
              <button
                key={key}
                type="button"
                onClick={() => onToggleChunk(key)}
                className={cn(
                  "w-full rounded-2xl border bg-white px-4 py-3 text-left transition-all",
                  expanded
                    ? "border-emerald-300 bg-emerald-50/60 shadow-sm"
                    : "border-slate-200 hover:border-slate-300 hover:bg-slate-50",
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold text-slate-800">{title}</div>
                    <div className="mt-1 text-xs text-slate-500">{category}</div>
                  </div>
                  <span className="shrink-0 text-xs font-medium text-slate-400">
                    {expanded ? "收起" : "展开"}
                  </span>
                </div>
                <p
                  className={cn(
                    "mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-600",
                    !expanded && "line-clamp-3",
                  )}
                >
                  {content}
                </p>
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function AssistantLabPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [teams, setTeams] = useState<AskTeamOption[]>([]);
  const [teamsLoading, setTeamsLoading] = useState(true);
  const [teamId, setTeamId] = useState<number | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseWithCount[]>([]);
  const [knowledgeBasesLoading, setKnowledgeBasesLoading] = useState(false);
  const [knowledgeBaseId, setKnowledgeBaseId] = useState<number | null>(null);
  const [assistants, setAssistants] = useState<AssistantSummary[]>([]);
  const [assistantsLoading, setAssistantsLoading] = useState(false);
  const [assistantId, setAssistantId] = useState<number | null>(null);
  const [directAssistant, setDirectAssistant] = useState<AssistantProfile | null>(null);
  const [pendingSelection, setPendingSelection] = useState<PendingAssistantSelection | null>(null);
  const [query, setQuery] = useState("");
  const [conversationByAssistant, setConversationByAssistant] = useState<
    Record<number, AssistantConversationState>
  >({});
  const [streamingAssistantId, setStreamingAssistantId] = useState<number | null>(null);
  const [mobileMetaOpen, setMobileMetaOpen] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const activeRequestRef = useRef<{ assistantId: number; turnId: string } | null>(null);

  const requestedAssistantId = useMemo(() => {
    const rawValue = searchParams.get("assistantId");
    if (!rawValue) return null;
    const parsed = Number(rawValue);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);

  const selectedTeam = useMemo(
    () => teams.find((item) => item.id === teamId) ?? null,
    [teamId, teams],
  );
  const selectedKnowledgeBase = useMemo(
    () => knowledgeBases.find((item) => item.id === knowledgeBaseId) ?? null,
    [knowledgeBaseId, knowledgeBases],
  );
  const selectedAssistant = useMemo(() => {
    const fromList = assistants.find((item) => item.id === assistantId);
    if (fromList) return fromList;
    return directAssistant?.id === assistantId ? directAssistant : null;
  }, [assistantId, assistants, directAssistant]);

  const activeConversation =
    assistantId != null ? (conversationByAssistant[assistantId] ?? EMPTY_CONVERSATION) : EMPTY_CONVERSATION;
  const expandedChunkKeys = useMemo(
    () => new Set(activeConversation.expandedChunkKeys),
    [activeConversation.expandedChunkKeys],
  );
  const openSourceTurnIds = useMemo(
    () => new Set(activeConversation.openSourceTurnIds),
    [activeConversation.openSourceTurnIds],
  );
  const suggestedPrompts = selectedAssistant?.suggested_prompts ?? [];
  const isActiveAssistantStreaming =
    assistantId != null && streamingAssistantId != null && assistantId === streamingAssistantId;

  const assistantGroups = useMemo(() => {
    const groups = new Map<string, { label: string; items: AssistantSummary[] }>();
    assistants.forEach((item) => {
      const label = item.team_name ?? selectedTeam?.name ?? "未命名项目";
      const key = `${item.team_id}-${label}`;
      const current = groups.get(key);
      if (current) current.items.push(item);
      else groups.set(key, { label, items: [item] });
    });
    return Array.from(groups.values());
  }, [assistants, selectedTeam?.name]);

  const syncAssistantSearchParam = (nextAssistantId: number | null) => {
    const nextParams = new URLSearchParams(searchParams.toString());
    if (nextAssistantId == null) nextParams.delete("assistantId");
    else nextParams.set("assistantId", String(nextAssistantId));
    const nextHref = nextParams.size > 0 ? `${pathname}?${nextParams.toString()}` : pathname;
    router.replace(nextHref, { scroll: false });
  };

  const updateConversation = (
    targetAssistantId: number,
    updater: (current: AssistantConversationState) => AssistantConversationState,
  ) => {
    setConversationByAssistant((current) => {
      const previous = current[targetAssistantId] ?? createEmptyConversation();
      return { ...current, [targetAssistantId]: updater(previous) };
    });
  };

  const resetConversation = (targetAssistantId: number | null) => {
    if (targetAssistantId == null) {
      setConversationByAssistant({});
      setQuery("");
      return;
    }
    updateConversation(targetAssistantId, () => createEmptyConversation());
    setQuery("");
  };

  const selectAssistant = (nextAssistantId: number) => {
    setAssistantId(nextAssistantId);
    setPendingSelection(null);
    setMobileMetaOpen(false);
    syncAssistantSearchParam(nextAssistantId);
  };

  const handleTeamChange = (value: string) => {
    const nextTeamId = value ? Number(value) : null;
    setTeamId(nextTeamId);
    setKnowledgeBaseId(null);
    setAssistants([]);
    setAssistantId(null);
    setPendingSelection(null);
    setMobileMetaOpen(false);
    syncAssistantSearchParam(null);
  };

  const handleKnowledgeBaseChange = (value: string) => {
    const nextKnowledgeBaseId = value ? Number(value) : null;
    setKnowledgeBaseId(nextKnowledgeBaseId);
    setAssistants([]);
    setAssistantId(null);
    setPendingSelection((current) =>
      current && nextKnowledgeBaseId === current.knowledgeBaseId ? current : null,
    );
    setMobileMetaOpen(false);
    syncAssistantSearchParam(null);
  };

  const toggleChunk = (targetAssistantId: number, key: string) => {
    updateConversation(targetAssistantId, (current) => ({
      ...current,
      expandedChunkKeys: current.expandedChunkKeys.includes(key)
        ? current.expandedChunkKeys.filter((item) => item !== key)
        : [...current.expandedChunkKeys, key],
    }));
  };

  const toggleSourceTurn = (targetAssistantId: number, turnId: string) => {
    updateConversation(targetAssistantId, (current) => ({
      ...current,
      openSourceTurnIds: current.openSourceTurnIds.includes(turnId)
        ? current.openSourceTurnIds.filter((item) => item !== turnId)
        : [...current.openSourceTurnIds, turnId],
    }));
  };

  useEffect(() => {
    const run = async () => {
      setTeamsLoading(true);
      try {
        setTeams(await kbChatApi.listTeams());
      } catch (error) {
        setTeams([]);
        toast.error(error instanceof Error ? error.message : "加载项目列表失败");
      } finally {
        setTeamsLoading(false);
      }
    };
    void run();
  }, []);

  useEffect(() => {
    if (requestedAssistantId == null) {
      setDirectAssistant(null);
      return;
    }
  }, [requestedAssistantId]);

  useEffect(() => {
    if (requestedAssistantId == null) return;
    let cancelled = false;

    const run = async () => {
      try {
        const detail = await assistantsApi.get(requestedAssistantId);
        if (cancelled) return;
        setDirectAssistant(detail);
        setPendingSelection({
          assistantId: detail.id,
          teamId: detail.team_id,
          knowledgeBaseId: detail.knowledge_base_id,
        });
        setTeamId(detail.team_id);
        setKnowledgeBaseId(detail.knowledge_base_id);
        setAssistantId(detail.id);
        setMobileMetaOpen(false);
      } catch (error) {
        if (cancelled) return;
        setPendingSelection(null);
        toast.error(error instanceof Error ? error.message : "加载助手详情失败");
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [requestedAssistantId]);

  useEffect(() => {
    if (teamId == null) {
      setKnowledgeBases([]);
      setKnowledgeBaseId(null);
      setAssistants([]);
      return;
    }

    let cancelled = false;
    const run = async () => {
      setKnowledgeBasesLoading(true);
      try {
        const items = await listKnowledgeBases(teamId);
        if (cancelled) return;
        setKnowledgeBases(items);
        setKnowledgeBaseId((current) => {
          if (pendingSelection?.teamId === teamId) return pendingSelection.knowledgeBaseId;
          if (current != null && items.some((item) => item.id === current)) return current;
          return current;
        });
      } catch (error) {
        if (cancelled) return;
        setKnowledgeBases([]);
        toast.error(error instanceof Error ? error.message : "加载知识库列表失败");
      } finally {
        if (!cancelled) setKnowledgeBasesLoading(false);
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [teamId, pendingSelection]);

  useEffect(() => {
    if (teamId == null) {
      setAssistants([]);
      return;
    }

    let cancelled = false;
    const run = async () => {
      setAssistantsLoading(true);
      try {
        const response = await assistantsApi.listAvailable({
          team_id: teamId,
          knowledge_base_id: knowledgeBaseId,
        });
        if (cancelled) return;
        const merged = mergeAssistantItems(response.items, directAssistant, {
          teamId,
          knowledgeBaseId,
        });
        const pendingId =
          pendingSelection?.teamId === teamId &&
          pendingSelection.knowledgeBaseId === knowledgeBaseId
            ? pendingSelection.assistantId
            : null;

        setAssistants(merged);
        setAssistantId((current) => {
          if (current != null && merged.some((item) => item.id === current)) return current;
          if (pendingId != null && merged.some((item) => item.id === pendingId)) return pendingId;
          return null;
        });

        if (pendingId != null && merged.some((item) => item.id === pendingId)) {
          setPendingSelection(null);
        }
      } catch (error) {
        if (cancelled) return;
        setAssistants([]);
        toast.error(error instanceof Error ? error.message : "加载助手列表失败");
      } finally {
        if (!cancelled) setAssistantsLoading(false);
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [teamId, knowledgeBaseId, directAssistant, pendingSelection]);

  useEffect(() => {
    setMobileMetaOpen(false);
  }, [assistantId]);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return;
    element.scrollTo({
      top: element.scrollHeight,
      behavior: isActiveAssistantStreaming ? "auto" : "smooth",
    });
  }, [activeConversation.turns, assistantId, isActiveAssistantStreaming]);

  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;
    element.style.height = "0px";
    element.style.height = `${Math.min(element.scrollHeight, 200)}px`;
  }, [query]);

  const submit = async (prefill?: string) => {
    if (assistantId == null || selectedAssistant == null || streamingAssistantId != null) {
      if (assistantId == null) toast.error("请先选择一个助手");
      return;
    }

    const nextQuery = (prefill ?? query).trim();
    if (!nextQuery) return;

    const turnId = `assistant-lab-turn-${uuidv4()}`;
    activeRequestRef.current = { assistantId, turnId };
    setStreamingAssistantId(assistantId);
    setQuery("");

    updateConversation(assistantId, (current) => ({
      ...current,
      turns: [
        ...current.turns,
        {
          id: turnId,
          query: nextQuery,
          answer: "",
          answerStatus: null,
          logId: null,
          retrievedDocs: [],
          error: null,
        },
      ],
    }));

    try {
      const stream = await assistantsApi.stream(assistantId, {
        query: nextQuery,
        session_id: conversationByAssistant[assistantId]?.sessionId ?? null,
      });

      await consumeSseStream(stream, (event) => {
        const activeRequest = activeRequestRef.current;
        if (!activeRequest) return;

        switch (event.type) {
          case "retrieved": {
            const docs = event.data.retrieved_docs;
            if (!Array.isArray(docs)) break;
            updateConversation(activeRequest.assistantId, (current) => ({
              ...current,
              turns: current.turns.map((turn) =>
                turn.id === activeRequest.turnId ? { ...turn, retrievedDocs: docs as RetrievedDoc[] } : turn,
              ),
            }));
            break;
          }
          case "token": {
            const text = event.data.text;
            if (typeof text !== "string" || !text) break;
            updateConversation(activeRequest.assistantId, (current) => ({
              ...current,
              turns: current.turns.map((turn) =>
                turn.id === activeRequest.turnId ? { ...turn, answer: `${turn.answer}${text}` } : turn,
              ),
            }));
            break;
          }
          case "complete": {
            const docs = event.data.retrieved_docs;
            const nextSessionId = event.data.session_id;
            const answerStatus = event.data.answer_status;
            const logId = event.data.log_id;
            updateConversation(activeRequest.assistantId, (current) => ({
              ...current,
              sessionId:
                typeof nextSessionId === "string" && nextSessionId ? nextSessionId : current.sessionId,
              turns: current.turns.map((turn) =>
                turn.id === activeRequest.turnId
                  ? {
                      ...turn,
                      answer: typeof event.data.answer === "string" ? event.data.answer : turn.answer,
                      answerStatus: typeof answerStatus === "string" ? answerStatus : turn.answerStatus,
                      logId: typeof logId === "number" ? logId : turn.logId,
                      retrievedDocs: Array.isArray(docs) ? (docs as RetrievedDoc[]) : turn.retrievedDocs,
                    }
                  : turn,
              ),
            }));
            break;
          }
          case "error": {
            const message = String(event.data.message ?? "问答失败");
            updateConversation(activeRequest.assistantId, (current) => ({
              ...current,
              turns: current.turns.map((turn) =>
                turn.id === activeRequest.turnId ? { ...turn, error: message } : turn,
              ),
            }));
            toast.error(message);
            break;
          }
          default:
            break;
        }
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "问答失败";
      updateConversation(assistantId, (current) => ({
        ...current,
        turns: current.turns.map((turn) => (turn.id === turnId ? { ...turn, error: message } : turn)),
      }));
      toast.error(message);
    } finally {
      setStreamingAssistantId((current) => (current === assistantId ? null : current));
      activeRequestRef.current = null;
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-[#f6f4ee]">
      <Toaster position="top-right" richColors />

      <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-300 via-orange-400 to-orange-500 text-white shadow-lg shadow-orange-200/70">
            <Bot className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold text-slate-900">项目助手模拟</h1>
            <p className="hidden text-sm text-slate-500 md:block">
              按项目、端和助手切换验证不同配置下的真实回答效果。
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => resetConversation(assistantId)}
          disabled={streamingAssistantId != null}
          className="inline-flex h-10 items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 transition-all hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          新建对话
        </button>
      </header>

      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <aside className="shrink-0 border-b border-slate-200 bg-white md:w-60 md:border-b-0 md:border-r xl:w-72">
          <div className="overflow-x-auto md:h-full md:overflow-y-auto md:overflow-x-hidden">
            <div className="flex min-w-max gap-4 p-4 md:min-w-0 md:flex-col md:gap-5 md:p-5">
              <section className="min-w-[280px] rounded-3xl border border-slate-200 bg-white p-4 shadow-sm md:min-w-0">
                <div className="space-y-4">
                  <div>
                    <label className="mb-2 block text-xs font-medium text-slate-500">项目</label>
                    <select
                      value={teamId ?? ""}
                      disabled={teamsLoading || streamingAssistantId != null}
                      onChange={(event) => handleTeamChange(event.target.value)}
                      className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50 disabled:bg-slate-50 disabled:text-slate-400"
                    >
                      <option value="">请选择项目</option>
                      {teams.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="mb-2 block text-xs font-medium text-slate-500">端</label>
                    <select
                      value={knowledgeBaseId ?? ""}
                      disabled={teamId == null || knowledgeBasesLoading || streamingAssistantId != null}
                      onChange={(event) => handleKnowledgeBaseChange(event.target.value)}
                      className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50 disabled:bg-slate-50 disabled:text-slate-400"
                    >
                      {teamId == null ? (
                        <option value="">请先选择项目</option>
                      ) : (
                        <>
                          <option value="">全部端</option>
                          {knowledgeBases.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.name}
                            </option>
                          ))}
                        </>
                      )}
                    </select>
                  </div>
                </div>
              </section>

              <section className="min-w-[320px] flex-1 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm md:min-w-0 md:flex-none">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div className="text-xs font-semibold tracking-[0.12em] text-slate-500">
                    助手列表
                  </div>
                  {assistantsLoading ? (
                    <div className="inline-flex items-center gap-1.5 text-xs text-slate-400">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      加载中
                    </div>
                  ) : null}
                </div>

                {teamId == null ? (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                    请先选择项目
                  </div>
                ) : assistantsLoading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, index) => (
                      <div key={index} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-10 animate-pulse rounded-full bg-slate-200" />
                          <div className="flex-1 space-y-2">
                            <div className="h-3 w-1/2 animate-pulse rounded-full bg-slate-200" />
                            <div className="h-3 w-5/6 animate-pulse rounded-full bg-slate-200" />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : assistants.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                    当前项目下没有可用助手
                  </div>
                ) : (
                  <div className="space-y-4">
                    {assistantGroups.map((group) => (
                      <div key={group.label} className="space-y-2">
                        <div className="border-b border-slate-100 pb-2 text-xs font-medium text-slate-600">
                          {group.label}
                        </div>
                        <div className="space-y-2">
                          {group.items.map((assistant) => {
                            const active = assistant.id === assistantId;
                            return (
                              <button
                                key={assistant.id}
                                type="button"
                                onClick={() => selectAssistant(assistant.id)}
                                className={cn(
                                  "w-full rounded-2xl border px-4 py-3 text-left transition-all",
                                  active
                                    ? "border-amber-300 bg-amber-50 shadow-sm shadow-amber-100/70"
                                    : "border-transparent bg-white hover:border-slate-200 hover:bg-slate-50",
                                )}
                              >
                                <div className="flex items-start gap-3">
                                  <div
                                    className={cn(
                                      "mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full",
                                      active ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500",
                                    )}
                                  >
                                    <Bot className="h-4 w-4" />
                                  </div>
                                  <div className="min-w-0 flex-1">
                                    <div className={cn("truncate text-sm font-semibold", active ? "text-amber-950" : "text-slate-800")}>
                                      {assistant.name}
                                    </div>
                                    <div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
                                      {assistant.description || assistant.knowledge_base_name || "未设置描述"}
                                    </div>
                                  </div>
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </div>
        </aside>

        <main className="flex min-h-0 flex-1 flex-col bg-[#f8f7f3]">
          {selectedAssistant ? (
            <>
              <div className="border-b border-slate-200 px-4 py-4 sm:px-6">
                <section className="rounded-[28px] border border-white/70 bg-slate-100/90 p-5 shadow-sm">
                  <div className="flex flex-col gap-4 lg:gap-5">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-3">
                          <h2 className="text-xl font-semibold text-slate-900">{selectedAssistant.name}</h2>
                          <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-500">
                            {selectedAssistant.slug}
                          </span>
                        </div>
                        <p className="mt-2 text-sm text-slate-500">
                          {(selectedAssistant.team_name ?? selectedTeam?.name ?? "--") + " / "}
                          {selectedAssistant.knowledge_base_name ?? selectedKnowledgeBase?.name ?? "--"}
                        </p>
                      </div>
                      <div
                        className={cn(
                          "inline-flex w-fit items-center rounded-full px-3 py-1 text-xs font-medium",
                          selectedAssistant.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-600",
                        )}
                      >
                        {selectedAssistant.is_active ? "启用中" : "已停用"}
                      </div>
                    </div>

                    <div className="hidden gap-3 lg:grid lg:grid-cols-2">
                      <MetaItem label="创建人" value={selectedAssistant.created_by_name ?? "--"} />
                      <MetaItem label="创建时间" value={formatDateTime(selectedAssistant.created_at)} />
                      <MetaItem label="最后更新时间" value={formatDateTime(selectedAssistant.updated_at)} />
                      <MetaItem label="状态" value={selectedAssistant.is_active ? "启用" : "停用"} />
                    </div>

                    <button
                      type="button"
                      onClick={() => setMobileMetaOpen((current) => !current)}
                      className="inline-flex items-center gap-2 self-start rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 transition-colors hover:bg-slate-50 lg:hidden"
                    >
                      查看更多信息
                      {mobileMetaOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    </button>

                    {mobileMetaOpen ? (
                      <div className="grid gap-3 lg:hidden">
                        <MetaItem label="创建人" value={selectedAssistant.created_by_name ?? "--"} />
                        <MetaItem label="创建时间" value={formatDateTime(selectedAssistant.created_at)} />
                        <MetaItem label="最后更新时间" value={formatDateTime(selectedAssistant.updated_at)} />
                        <MetaItem label="状态" value={selectedAssistant.is_active ? "启用" : "停用"} />
                      </div>
                    ) : null}

                    {selectedAssistant.welcome_message ? (
                      <div className="rounded-3xl border border-slate-200 bg-white px-4 py-4">
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-700">
                            <Quote className="h-4 w-4" />
                          </div>
                          <p className="text-sm leading-6 text-slate-600">
                            {selectedAssistant.welcome_message}
                          </p>
                        </div>
                      </div>
                    ) : null}
                  </div>
                </section>
              </div>

              <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
                {activeConversation.turns.length === 0 ? (
                  <div className="flex h-full min-h-[360px] items-center justify-center">
                    <div className="max-w-lg text-center">
                      <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-white text-slate-400 shadow-sm">
                        <MessageCircleMore className="h-9 w-9" />
                      </div>
                      <h3 className="mt-6 text-xl font-semibold text-slate-900">
                        开始与 {selectedAssistant.name} 对话
                      </h3>
                      <p className="mt-3 text-sm leading-6 text-slate-500">
                        切换助手时会保留对话历史，方便你单独验证每个助手的效果。
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="mx-auto max-w-4xl space-y-6">
                    {activeConversation.turns.map((turn) => {
                      const turnIsPending = isActiveAssistantStreaming && !turn.answer && !turn.error;

                      return (
                        <div key={turn.id} className="space-y-3">
                          <div className="flex justify-end">
                            <div className="max-w-[70%] rounded-[24px] rounded-tr-md bg-gradient-to-br from-[#6a6678] via-slate-800 to-slate-900 px-5 py-4 text-sm leading-6 text-white shadow-lg shadow-slate-900/10">
                              <div className="mb-2 flex items-center justify-end gap-2 text-[11px] font-medium text-slate-200">
                                <span>你</span>
                                <UserRound className="h-3.5 w-3.5" />
                              </div>
                              <p className="whitespace-pre-wrap">{turn.query}</p>
                            </div>
                          </div>

                          <div className="flex justify-start">
                            <div className="max-w-[80%] rounded-[28px] border border-slate-200 bg-white px-5 py-4 shadow-sm">
                              <div className="mb-4 flex items-start justify-between gap-3">
                                <div className="flex items-center gap-2 text-sm font-medium text-slate-800">
                                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600">
                                    <Bot className="h-4 w-4" />
                                  </span>
                                  {selectedAssistant.name}
                                </div>
                                {turn.answerStatus ? (
                                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-500">
                                    {turn.answerStatus}
                                  </span>
                                ) : null}
                              </div>

                              {turn.error ? (
                                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                                  {turn.error}
                                </div>
                              ) : turnIsPending ? (
                                <AssistantReplySkeleton />
                              ) : (
                                <AnswerMarkdown text={turn.answer} />
                              )}

                              <ReferenceDocsSection
                                turn={turn}
                                open={openSourceTurnIds.has(turn.id)}
                                expandedChunkKeys={expandedChunkKeys}
                                onToggleSection={() => assistantId != null && toggleSourceTurn(assistantId, turn.id)}
                                onToggleChunk={(key) => assistantId != null && toggleChunk(assistantId, key)}
                              />
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="border-t border-slate-200 bg-white px-4 py-4 sm:px-6">
                <div className="mx-auto max-w-4xl">
                  <div className="rounded-[28px] border border-slate-200 bg-white p-3 shadow-sm">
                    <div className="flex items-end gap-3">
                      <div className="flex-1 rounded-3xl border border-slate-200 bg-slate-50 px-4 py-3 transition-all focus-within:border-emerald-300 focus-within:ring-4 focus-within:ring-emerald-50">
                        <textarea
                          ref={textareaRef}
                          rows={1}
                          value={query}
                          onChange={(event) => setQuery(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                              event.preventDefault();
                              void submit();
                            }
                          }}
                          disabled={isActiveAssistantStreaming}
                          placeholder={selectedAssistant.placeholder_text || "输入你想验证的问题，按 Enter 发送"}
                          className="max-h-[200px] min-h-[44px] w-full resize-none border-0 bg-transparent py-1 text-sm leading-6 text-slate-800 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed"
                        />
                      </div>

                      <div className="flex shrink-0 flex-col items-end gap-2">
                        <button
                          type="button"
                          disabled={!query.trim() || isActiveAssistantStreaming}
                          onClick={() => void submit()}
                          className="inline-flex h-11 items-center gap-2 rounded-2xl bg-gradient-to-r from-amber-400 to-orange-500 px-5 text-sm font-medium text-white shadow-lg shadow-orange-200/80 transition-all hover:-translate-y-0.5 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {isActiveAssistantStreaming ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              发送中
                            </>
                          ) : (
                            <>
                              发送
                              <SendHorizonal className="h-4 w-4" />
                            </>
                          )}
                        </button>
                        <span className="text-xs text-slate-400">Shift+Enter 换行</span>
                      </div>
                    </div>

                    {suggestedPrompts.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
                        {suggestedPrompts.map((prompt) => (
                          <button
                            key={prompt}
                            type="button"
                            disabled={isActiveAssistantStreaming}
                            onClick={() => {
                              setQuery(prompt);
                              requestAnimationFrame(() => textareaRef.current?.focus());
                            }}
                            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 transition-colors hover:border-amber-300 hover:bg-amber-50 hover:text-amber-700 disabled:opacity-50"
                          >
                            {prompt}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center px-6">
              <div className="max-w-lg text-center">
                <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-full bg-white text-slate-400 shadow-sm">
                  <Sparkles className="h-10 w-10" />
                </div>
                <h2 className="mt-6 text-2xl font-semibold text-slate-900">请完成上述配置</h2>
                <p className="mt-3 text-sm leading-7 text-slate-500">
                  先选择项目和端，再从左侧助手列表中点选目标助手。
                  {requestedAssistantId != null ? " 如果你是从管理后台跳转过来，页面会自动定位到对应助手。" : ""}
                </p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function AssistantLabPageFallback() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-500">
      <Loader2 className="h-6 w-6 animate-spin" />
    </main>
  );
}

export default function AssistantLabPage() {
  return (
    <Suspense fallback={<AssistantLabPageFallback />}>
      <AssistantLabPageContent />
    </Suspense>
  );
}
