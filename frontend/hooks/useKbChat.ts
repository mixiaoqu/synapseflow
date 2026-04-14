"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { useAskTeamScope } from "@/components/kb-chat/AskTeamScopeProvider";
import {
  listDocumentCategories,
  type DocumentCategory,
} from "@/lib/api/documentCategories";
import {
  listKnowledgeBases,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
import {
  kbChatApi,
  type KbChatRequest,
  type KbChatSessionDetail,
  type KbChatSessionMessage,
  type KbChatSessionSummary,
  type RetrievedDoc,
} from "@/lib/api/endpoints/kbChat";
import { getStoredUser } from "@/lib/auth/session";
import { consumeSseStream } from "@/lib/stream/sse";

const SESSION_LIST_LIMIT = 30;
const ACTIVE_SESSION_STORAGE_KEY = "synapseflow.kb-chat.active-session";

export interface KbChatTurn {
  id: string;
  query: string;
  answer: string;
  answerStatus?: string | null;
  logId?: number | null;
  retrievedDocs: RetrievedDoc[];
  error: string | null;
}

function buildUserScopedStorageKey(baseKey: string): string {
  const user = getStoredUser();
  return user ? `${baseKey}.${user.id}` : baseKey;
}

function readStoredValue(storageKey: string): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(storageKey);
}

function writeStoredValue(storageKey: string, value: string | null) {
  if (typeof window === "undefined") return;
  if (value) {
    window.localStorage.setItem(storageKey, value);
    return;
  }
  window.localStorage.removeItem(storageKey);
}

function buildTurnId(sessionId: string, index: number): string {
  return `${sessionId}-${index}`;
}

function buildChunkKey(turnId: string, index: number): string {
  return `${turnId}-${index}`;
}

function toTurns(sessionId: string, messages: KbChatSessionMessage[]): KbChatTurn[] {
  const turns: KbChatTurn[] = [];
  let currentTurn: KbChatTurn | null = null;

  messages.forEach((message, index) => {
    const role = message.role.trim().toLowerCase();
    const content = message.content.trim();
    if (!content) return;

    if (role === "user") {
      if (currentTurn) {
        turns.push(currentTurn);
      }
      currentTurn = {
        id: buildTurnId(sessionId, index),
        query: content,
        answer: "",
        answerStatus: null,
        logId: null,
        retrievedDocs: [],
        error: null,
      };
      return;
    }

    if (role === "assistant") {
      if (!currentTurn) {
        currentTurn = {
          id: buildTurnId(sessionId, index),
          query: "",
          answer: content,
          answerStatus: message.answer_status ?? null,
          logId: message.log_id ?? null,
          retrievedDocs: message.retrieved_docs ?? [],
          error: null,
        };
        return;
      }

      currentTurn = {
        ...currentTurn,
        answer: currentTurn.answer ? `${currentTurn.answer}\n\n${content}` : content,
        answerStatus: message.answer_status ?? currentTurn.answerStatus,
        logId: message.log_id ?? currentTurn.logId,
        retrievedDocs:
          Array.isArray(message.retrieved_docs) && message.retrieved_docs.length > 0
            ? message.retrieved_docs
            : currentTurn.retrievedDocs,
      };
    }
  });

  if (currentTurn) {
    turns.push(currentTurn);
  }

  return turns.filter((turn) => turn.query || turn.answer);
}

function mergeSessionSummary(
  current: KbChatSessionSummary | null,
  detail: KbChatSessionDetail,
): KbChatSessionSummary {
  return {
    session_id: detail.session_id,
    title: detail.title,
    preview: detail.preview ?? current?.preview ?? null,
    team_id: detail.team_id ?? current?.team_id ?? null,
    knowledge_base_id: detail.knowledge_base_id ?? current?.knowledge_base_id ?? null,
    knowledge_base_name: detail.knowledge_base_name ?? current?.knowledge_base_name ?? null,
    category_id: detail.category_id ?? current?.category_id ?? null,
    category_name: detail.category_name ?? current?.category_name ?? null,
    message_count: detail.message_count,
    created_at: detail.created_at,
    updated_at: detail.updated_at,
  };
}

export function useKbChat(options?: { enableScopeFilters?: boolean }) {
  const enableScopeFilters = options?.enableScopeFilters ?? true;
  const { teamId, setTeamId, teams, teamsLoading, selectedTeam } = useAskTeamScope();

  const [query, setQuery] = useState("");
  const [knowledgeBaseId, setKnowledgeBaseId] = useState<number | null>(null);
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseWithCount[]>([]);
  const [categories, setCategories] = useState<DocumentCategory[]>([]);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [turns, setTurns] = useState<KbChatTurn[]>([]);
  const [sessions, setSessions] = useState<KbChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set());
  const [mobileTab, setMobileTab] = useState<"chat" | "sources">("chat");

  const activeTurnIdRef = useRef<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const hasRestoredSessionRef = useRef(false);
  const activeSessionStorageKeyRef = useRef<string>(
    buildUserScopedStorageKey(ACTIVE_SESSION_STORAGE_KEY),
  );
  const previousTeamIdRef = useRef<number | null>(null);
  const suppressTeamScopeResetRef = useRef(false);

  const loading = submitLoading || sessionLoading;

  const persistActiveSessionId = useCallback((sessionId: string | null) => {
    writeStoredValue(activeSessionStorageKeyRef.current, sessionId);
  }, []);

  const resetConversation = useCallback(() => {
    setTurns([]);
    setExpandedChunks(new Set());
    setMobileTab("chat");
    setActiveSessionId(null);
    sessionIdRef.current = null;
    persistActiveSessionId(null);
  }, [persistActiveSessionId]);

  const loadKnowledgeBases = useCallback(async () => {
    if (!enableScopeFilters || teamId == null) {
      setKnowledgeBases([]);
      return;
    }

    try {
      setKnowledgeBases(await listKnowledgeBases(teamId));
    } catch {
      setKnowledgeBases([]);
    }
  }, [enableScopeFilters, teamId]);

  const loadSessions = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setHistoryLoading(true);
    }

    try {
      setSessions(await kbChatApi.listSessions(SESSION_LIST_LIMIT));
    } catch {
      if (!options?.silent) {
        toast.error("加载历史会话失败");
      }
    } finally {
      if (!options?.silent) {
        setHistoryLoading(false);
      }
    }
  }, []);

  const filteredSessions = useMemo(() => {
    if (teamId == null) return sessions;
    return sessions.filter((item) => item.team_id == null || item.team_id === teamId);
  }, [sessions, teamId]);

  const openSession = useCallback(
    async (sessionId: string) => {
      if (!sessionId) return false;

      setSessionLoading(true);
      setMobileTab("chat");

      try {
        const detail = await kbChatApi.getSession(sessionId);
        const nextSummary = mergeSessionSummary(
          sessions.find((item) => item.session_id === sessionId) ?? null,
          detail,
        );

        setSessions((prev) => {
          const exists = prev.some((item) => item.session_id === sessionId);
          if (!exists) {
            return [nextSummary, ...prev];
          }
          return prev.map((item) => (item.session_id === sessionId ? nextSummary : item));
        });

        if (detail.team_id != null && detail.team_id !== teamId) {
          suppressTeamScopeResetRef.current = true;
          setTeamId(detail.team_id);
        }

        setTurns(toTurns(detail.session_id, detail.messages));
        setExpandedChunks(new Set());
        setActiveSessionId(detail.session_id);
        sessionIdRef.current = detail.session_id;
        persistActiveSessionId(detail.session_id);
        setKnowledgeBaseId(detail.knowledge_base_id ?? null);
        setCategoryId(detail.category_id ?? null);
        return true;
      } catch (error) {
        const message = error instanceof Error ? error.message : "加载会话失败";
        toast.error(message);
        return false;
      } finally {
        setSessionLoading(false);
      }
    },
    [persistActiveSessionId, sessions, setTeamId, teamId],
  );

  const deleteSession = useCallback(
    async (sessionId: string) => {
      if (!sessionId) return false;

      setDeletingSessionId(sessionId);
      try {
        await kbChatApi.deleteSession(sessionId);
        const remainingSessions = sessions.filter((item) => item.session_id !== sessionId);
        const remainingVisibleSessions =
          teamId == null
            ? remainingSessions
            : remainingSessions.filter(
                (item) => item.team_id == null || item.team_id === teamId,
              );

        setSessions(remainingSessions);

        if (activeSessionId === sessionId) {
          resetConversation();
          if (remainingVisibleSessions.length > 0) {
            await openSession(remainingVisibleSessions[0].session_id);
          }
        }

        return true;
      } catch (error) {
        const message = error instanceof Error ? error.message : "删除会话失败";
        toast.error(message);
        return false;
      } finally {
        setDeletingSessionId(null);
      }
    },
    [activeSessionId, openSession, resetConversation, sessions, teamId],
  );

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (!enableScopeFilters) {
      setKnowledgeBases([]);
      setCategories([]);
      return;
    }
    void loadKnowledgeBases();
  }, [enableScopeFilters, loadKnowledgeBases]);

  useEffect(() => {
    if (teamId === previousTeamIdRef.current) {
      return;
    }

    const previousTeamId = previousTeamIdRef.current;
    previousTeamIdRef.current = teamId;

    if (suppressTeamScopeResetRef.current) {
      suppressTeamScopeResetRef.current = false;
      return;
    }

    if (previousTeamId != null && previousTeamId !== teamId) {
      resetConversation();
      setKnowledgeBaseId(null);
      setCategoryId(null);
    }
  }, [resetConversation, teamId]);

  useEffect(() => {
    if (!knowledgeBaseId || knowledgeBaseId <= 0) {
      setCategoryId(null);
      if (!knowledgeBaseId) {
        setCategories([]);
      }
      return;
    }

    if (!knowledgeBases.some((item) => item.id === knowledgeBaseId)) {
      setKnowledgeBaseId(null);
      setCategoryId(null);
    }
  }, [knowledgeBaseId, knowledgeBases]);

  useEffect(() => {
    if (!knowledgeBaseId || knowledgeBaseId <= 0) {
      setCategories([]);
      setCategoryId(null);
      return;
    }

    let cancelled = false;

    const run = async () => {
      try {
        const items = await listDocumentCategories(knowledgeBaseId);
        if (cancelled) return;
        setCategories(items);
        setCategoryId((prev) => (prev && items.some((item) => item.id === prev) ? prev : null));
      } catch {
        if (!cancelled) {
          setCategories([]);
          setCategoryId(null);
        }
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [knowledgeBaseId]);

  useEffect(() => {
    if (historyLoading || teamsLoading || hasRestoredSessionRef.current) return;

    hasRestoredSessionRef.current = true;
    const storedSessionId = readStoredValue(activeSessionStorageKeyRef.current);
    if (
      storedSessionId &&
      filteredSessions.some((item) => item.session_id === storedSessionId)
    ) {
      void openSession(storedSessionId);
      return;
    }

    if (storedSessionId) {
      persistActiveSessionId(null);
    }

    if (filteredSessions.length > 0) {
      void openSession(filteredSessions[0].session_id);
    }
  }, [filteredSessions, historyLoading, openSession, persistActiveSessionId, teamsLoading]);

  const toggleChunk = useCallback((key: string) => {
    setExpandedChunks((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const expandChunksForTurn = useCallback((turnId: string, docs: RetrievedDoc[]) => {
    if (!docs.length) return;
    setExpandedChunks((prev) => {
      const next = new Set(prev);
      docs.forEach((_, index) => {
        next.add(buildChunkKey(turnId, index));
      });
      return next;
    });
  }, []);

  const collapseChunksForTurn = useCallback((turnId: string, docs: RetrievedDoc[]) => {
    if (!docs.length) return;
    setExpandedChunks((prev) => {
      const next = new Set(prev);
      docs.forEach((_, index) => {
        next.delete(buildChunkKey(turnId, index));
      });
      return next;
    });
  }, []);

  const lastTurn = useMemo(
    () => (turns.length > 0 ? turns[turns.length - 1] : null),
    [turns],
  );

  const sourceDocs = lastTurn?.retrievedDocs ?? [];

  const activeSession = useMemo(
    () => sessions.find((item) => item.session_id === activeSessionId) ?? null,
    [activeSessionId, sessions],
  );

  const knowledgeBaseLabel = useMemo(() => {
    if (knowledgeBaseId && knowledgeBaseId > 0) {
      const kbLabel =
        knowledgeBases.find((kb) => kb.id === knowledgeBaseId)?.name ??
        activeSession?.knowledge_base_name ??
        "所选知识库";

      if (categoryId && categoryId > 0) {
        const categoryLabel =
          categories.find((item) => item.id === categoryId)?.name ??
          activeSession?.category_name ??
          "所选分类";
        return `${kbLabel} / ${categoryLabel}`;
      }

      return kbLabel;
    }

    return selectedTeam ? `${selectedTeam.name} · 全部知识库` : "全部知识库";
  }, [activeSession, categories, categoryId, knowledgeBaseId, knowledgeBases, selectedTeam]);

  const expandAllChunks = useCallback(() => {
    if (!lastTurn?.retrievedDocs.length) return;
    setExpandedChunks(new Set(lastTurn.retrievedDocs.map((_, index) => buildChunkKey(lastTurn.id, index))));
  }, [lastTurn]);

  const collapseAllChunks = useCallback(() => {
    setExpandedChunks(new Set());
  }, []);

  const submit = useCallback(
    async (request?: Partial<KbChatRequest> & { query?: string }) => {
      const nextQuery = request?.query?.trim() ?? query.trim();
      const nextTeamId = request?.team_id !== undefined ? request.team_id : teamId;
      const nextKnowledgeBaseId =
        request?.knowledge_base_id !== undefined ? request.knowledge_base_id : knowledgeBaseId;
      const nextCategoryId =
        request?.category_id !== undefined ? request.category_id : categoryId;

      if (!nextQuery || loading) return false;

      if (!nextTeamId || nextTeamId <= 0) {
        toast.error("请先选择团队");
        return false;
      }

      const turnId = crypto.randomUUID();
      let completed = false;

      activeTurnIdRef.current = turnId;
      setSubmitLoading(true);
      setQuery("");
      setMobileTab("chat");
      setExpandedChunks(new Set());
      setTurns((prev) => [
        ...prev,
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
        const stream = await kbChatApi.stream({
          query: nextQuery,
          team_id: nextTeamId,
          knowledge_base_id:
            nextKnowledgeBaseId && nextKnowledgeBaseId > 0 ? nextKnowledgeBaseId : null,
          category_id: nextCategoryId && nextCategoryId > 0 ? nextCategoryId : null,
          session_id: sessionIdRef.current,
        });

        await consumeSseStream(stream, (event) => {
          const turnIdForUpdate = activeTurnIdRef.current;
          if (!turnIdForUpdate) return;

          switch (event.type) {
            case "retrieved": {
              const docs = event.data.retrieved_docs;
              if (Array.isArray(docs)) {
                setTurns((prev) =>
                  prev.map((turn) =>
                    turn.id === turnIdForUpdate
                      ? { ...turn, retrievedDocs: docs as RetrievedDoc[] }
                      : turn,
                  ),
                );
              }
              break;
            }
            case "complete": {
              completed = true;
              const answer = event.data.answer;
              const docs = event.data.retrieved_docs;
              const sessionId = event.data.session_id;
              const answerStatus = event.data.answer_status;
              const logId = event.data.log_id;

              if (typeof sessionId === "string" && sessionId) {
                sessionIdRef.current = sessionId;
                setActiveSessionId(sessionId);
                persistActiveSessionId(sessionId);
              }

              setTurns((prev) =>
                prev.map((turn) =>
                  turn.id === turnIdForUpdate
                    ? {
                        ...turn,
                        answer: typeof answer === "string" ? answer : turn.answer,
                        answerStatus:
                          typeof answerStatus === "string" ? answerStatus : turn.answerStatus,
                        logId: typeof logId === "number" ? logId : turn.logId,
                        retrievedDocs: Array.isArray(docs)
                          ? (docs as RetrievedDoc[])
                          : turn.retrievedDocs,
                      }
                    : turn,
                ),
              );
              break;
            }
            case "token": {
              const text = event.data.text;
              if (typeof text === "string" && text) {
                setTurns((prev) =>
                  prev.map((turn) =>
                    turn.id === turnIdForUpdate ? { ...turn, answer: turn.answer + text } : turn,
                  ),
                );
              }
              break;
            }
            case "error": {
              const message = String(event.data.message ?? "Streaming request failed");
              setTurns((prev) =>
                prev.map((turn) =>
                  turn.id === turnIdForUpdate ? { ...turn, error: message } : turn,
                ),
              );
              toast.error(message);
              break;
            }
            default:
              break;
          }
        });

        if (completed) {
          await loadSessions({ silent: true });
        }
        return true;
      } catch (error) {
        const message = error instanceof Error ? error.message : "Request failed";
        const turnIdForUpdate = activeTurnIdRef.current;
        if (turnIdForUpdate) {
          setTurns((prev) =>
            prev.map((turn) =>
              turn.id === turnIdForUpdate ? { ...turn, error: message } : turn,
            ),
          );
        }
        toast.error(message);
        return false;
      } finally {
        setSubmitLoading(false);
        activeTurnIdRef.current = null;
      }
    },
    [categoryId, knowledgeBaseId, loadSessions, loading, persistActiveSessionId, query, teamId],
  );

  return {
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
    submitLoading,
    sessionLoading,
    deletingSessionId,
    historyLoading,
    turns,
    sessions: filteredSessions,
    activeSessionId,
    expandedChunks,
    mobileTab,
    setMobileTab,
    knowledgeBaseLabel,
    lastTurn,
    sourceDocs,
    toggleChunk,
    expandChunksForTurn,
    collapseChunksForTurn,
    expandAllChunks,
    collapseAllChunks,
    resetConversation,
    openSession,
    deleteSession,
    submit,
  };
}
