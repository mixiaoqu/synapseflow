"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { useAskTeamScope } from "@/components/kb-chat/AskTeamScopeProvider";
import {
  assistantsApi,
  type AssistantChatRequest,
  type AssistantSummary,
} from "@/lib/api/assistants";
import {
  kbChatApi,
  type KbChatSessionDetail,
  type KbChatSessionMessage,
  type KbChatSessionSummary,
  type RetrievedDoc,
} from "@/lib/api/endpoints/kbChat";
import { getStoredUser } from "@/lib/auth/session";
import { consumeSseStream } from "@/lib/stream/sse";
import { v4 as uuidv4 } from "uuid";

const SESSION_LIST_LIMIT = 50;
const ACTIVE_SESSION_STORAGE_KEY = "synapseflow.assistant-chat.active-sessions";

export interface AssistantChatTurn {
  id: string;
  query: string;
  answer: string;
  answerStatus?: string | null;
  logId?: number | null;
  retrievedDocs: RetrievedDoc[];
  error: string | null;
}

interface AssistantConversationState {
  turns: AssistantChatTurn[];
  sessionId: string | null;
  expandedChunkKeys: string[];
  openSourceTurnIds: string[];
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

function buildUserScopedStorageKey(baseKey: string): string {
  const user = getStoredUser();
  return user ? `${baseKey}.${user.id}` : baseKey;
}

function buildScopeKey(teamId: number, assistantId: number): string {
  return `${teamId}:${assistantId}`;
}

function readStoredSessionMap(storageKey: string): Record<string, string | null> {
  if (typeof window === "undefined") return {};
  const raw = window.localStorage.getItem(storageKey);
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Record<string, string | null>;
  } catch {
    return {};
  }
}

function writeStoredSessionMap(
  storageKey: string,
  value: Record<string, string | null>,
) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(storageKey, JSON.stringify(value));
}

function buildTurnId(sessionId: string, index: number): string {
  return `${sessionId}-${index}`;
}

function buildChunkKey(turnId: string, index: number): string {
  return `${turnId}-${index}`;
}

function toTurns(sessionId: string, messages: KbChatSessionMessage[]): AssistantChatTurn[] {
  const turns: AssistantChatTurn[] = [];
  let currentTurn: AssistantChatTurn | null = null;

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
    assistant_id: detail.assistant_id ?? current?.assistant_id ?? null,
    assistant_name: detail.assistant_name ?? current?.assistant_name ?? null,
    category_id: detail.category_id ?? current?.category_id ?? null,
    category_name: detail.category_name ?? current?.category_name ?? null,
    message_count: detail.message_count,
    created_at: detail.created_at,
    updated_at: detail.updated_at,
  };
}

export function useAssistantChat() {
  const { teamId, setTeamId, teams, teamsLoading, selectedTeam } = useAskTeamScope();

  const [assistants, setAssistants] = useState<AssistantSummary[]>([]);
  const [assistantsLoading, setAssistantsLoading] = useState(false);
  const [assistantsReady, setAssistantsReady] = useState(false);
  const [selectedAssistantId, setSelectedAssistantId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [submitLoading, setSubmitLoading] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [sessions, setSessions] = useState<KbChatSessionSummary[]>([]);
  const [conversationByAssistant, setConversationByAssistant] = useState<
    Record<number, AssistantConversationState>
  >({});
  const [mobileTab, setMobileTab] = useState<"chat" | "sources">("chat");

  const activeTurnIdRef = useRef<string | null>(null);
  const previousTeamIdRef = useRef<number | null>(null);
  const restoredAssistantKeysRef = useRef<Set<string>>(new Set());
  const activeSessionStorageKeyRef = useRef<string>(
    buildUserScopedStorageKey(ACTIVE_SESSION_STORAGE_KEY),
  );

  const loading = submitLoading || sessionLoading;

  const selectedAssistant = useMemo(
    () => assistants.find((item) => item.id === selectedAssistantId) ?? null,
    [assistants, selectedAssistantId],
  );

  const activeConversation = useMemo(() => {
    if (selectedAssistantId == null) return EMPTY_CONVERSATION;
    return conversationByAssistant[selectedAssistantId] ?? EMPTY_CONVERSATION;
  }, [conversationByAssistant, selectedAssistantId]);

  const persistActiveSessionId = useCallback(
    (assistantId: number, sessionId: string | null) => {
      if (teamId == null) return;
      const storageKey = activeSessionStorageKeyRef.current;
      const nextMap = readStoredSessionMap(storageKey);
      nextMap[buildScopeKey(teamId, assistantId)] = sessionId;
      writeStoredSessionMap(storageKey, nextMap);
    },
    [teamId],
  );

  const updateConversation = useCallback(
    (
      assistantId: number,
      updater: (current: AssistantConversationState) => AssistantConversationState,
    ) => {
      setConversationByAssistant((current) => {
        const previous = current[assistantId] ?? createEmptyConversation();
        return {
          ...current,
          [assistantId]: updater(previous),
        };
      });
    },
    [],
  );

  const resetConversation = useCallback(() => {
    if (selectedAssistantId == null) return;
    updateConversation(selectedAssistantId, () => createEmptyConversation());
    persistActiveSessionId(selectedAssistantId, null);
    setMobileTab("chat");
  }, [persistActiveSessionId, selectedAssistantId, updateConversation]);

  const loadAssistants = useCallback(async (nextTeamId: number | null) => {
    if (nextTeamId == null) {
      setAssistants([]);
      setAssistantsReady(false);
      return;
    }

    setAssistantsLoading(true);
    setAssistantsReady(false);
    try {
      const response = await assistantsApi.listAvailable({ team_id: nextTeamId });
      setAssistants(response.items);
    } catch (error) {
      setAssistants([]);
      toast.error(error instanceof Error ? error.message : "加载助手列表失败");
    } finally {
      setAssistantsLoading(false);
      setAssistantsReady(true);
    }
  }, []);

  const loadSessions = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setHistoryLoading(true);
    }

    try {
      setSessions(await kbChatApi.listSessions(SESSION_LIST_LIMIT));
    } catch (error) {
      if (!options?.silent) {
        toast.error(error instanceof Error ? error.message : "加载历史会话失败");
      }
    } finally {
      if (!options?.silent) {
        setHistoryLoading(false);
      }
    }
  }, []);

  const filteredSessions = useMemo(() => {
    return sessions.filter((item) => {
      const matchesTeam = teamId == null || item.team_id == null || item.team_id === teamId;
      const matchesAssistant =
        selectedAssistantId == null
          ? false
          : item.assistant_id == null || item.assistant_id === selectedAssistantId;
      return matchesTeam && matchesAssistant;
    });
  }, [selectedAssistantId, sessions, teamId]);

  const openSession = useCallback(
    async (sessionId: string) => {
      if (!sessionId || selectedAssistantId == null) return false;

      setSessionLoading(true);
      setMobileTab("chat");

      try {
        const detail = await kbChatApi.getSession(sessionId);
        if (teamId != null && detail.team_id != null && detail.team_id !== teamId) {
          toast.error("该会话不属于当前团队");
          return false;
        }
        if (
          detail.assistant_id != null &&
          selectedAssistantId != null &&
          detail.assistant_id !== selectedAssistantId
        ) {
          toast.error("该会话不属于当前助手");
          return false;
        }

        const nextSummary = mergeSessionSummary(
          sessions.find((item) => item.session_id === sessionId) ?? null,
          detail,
        );

        setSessions((current) => {
          const exists = current.some((item) => item.session_id === sessionId);
          if (!exists) {
            return [nextSummary, ...current];
          }
          return current.map((item) => (item.session_id === sessionId ? nextSummary : item));
        });

        updateConversation(selectedAssistantId, () => ({
          turns: toTurns(detail.session_id, detail.messages),
          sessionId: detail.session_id,
          expandedChunkKeys: [],
          openSourceTurnIds: [],
        }));
        persistActiveSessionId(selectedAssistantId, detail.session_id);
        return true;
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "加载会话失败");
        return false;
      } finally {
        setSessionLoading(false);
      }
    },
    [persistActiveSessionId, selectedAssistantId, sessions, teamId, updateConversation],
  );

  const deleteSession = useCallback(
    async (sessionId: string) => {
      if (!sessionId || selectedAssistantId == null) return false;

      setDeletingSessionId(sessionId);
      try {
        await kbChatApi.deleteSession(sessionId);
        const remainingSessions = sessions.filter((item) => item.session_id !== sessionId);
        const remainingVisibleSessions = remainingSessions.filter(
          (item) =>
            (teamId == null || item.team_id == null || item.team_id === teamId) &&
            (item.assistant_id == null || item.assistant_id === selectedAssistantId),
        );

        setSessions(remainingSessions);

        if (activeConversation.sessionId === sessionId) {
          updateConversation(selectedAssistantId, () => createEmptyConversation());
          persistActiveSessionId(selectedAssistantId, null);

          if (remainingVisibleSessions.length > 0) {
            await openSession(remainingVisibleSessions[0].session_id);
          }
        }

        return true;
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "删除会话失败");
        return false;
      } finally {
        setDeletingSessionId(null);
      }
    },
    [
      activeConversation.sessionId,
      openSession,
      persistActiveSessionId,
      selectedAssistantId,
      sessions,
      teamId,
      updateConversation,
    ],
  );

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (teamId != null) {
      void loadAssistants(teamId);
    } else {
      setAssistants([]);
      setAssistantsReady(false);
      setSelectedAssistantId(null);
    }
  }, [teamId, loadAssistants]);

  useEffect(() => {
    if (teamId === previousTeamIdRef.current) {
      return;
    }

    const previousTeamId = previousTeamIdRef.current;
    previousTeamIdRef.current = teamId;
    restoredAssistantKeysRef.current = new Set();

    if (previousTeamId != null && previousTeamId !== teamId) {
      setSelectedAssistantId(null);
      setMobileTab("chat");
      setQuery("");
    }
  }, [teamId]);

  useEffect(() => {
    if (assistantsLoading) return;

    if (assistants.length === 0) {
      setSelectedAssistantId(null);
      return;
    }

    setSelectedAssistantId((current) => {
      if (current != null && assistants.some((item) => item.id === current)) {
        return current;
      }
      return assistants[0].id;
    });
  }, [assistants, assistantsLoading]);

  useEffect(() => {
    if (
      historyLoading ||
      assistantsLoading ||
      teamId == null ||
      selectedAssistantId == null
    ) {
      return;
    }

    const scopeKey = buildScopeKey(teamId, selectedAssistantId);
    if (restoredAssistantKeysRef.current.has(scopeKey)) {
      return;
    }

    restoredAssistantKeysRef.current.add(scopeKey);

    const currentConversation = conversationByAssistant[selectedAssistantId];
    if (currentConversation?.sessionId && currentConversation.turns.length > 0) {
      return;
    }

    const sessionMap = readStoredSessionMap(activeSessionStorageKeyRef.current);
    const storedSessionId = sessionMap[scopeKey];
    if (
      typeof storedSessionId === "string" &&
      storedSessionId &&
      filteredSessions.some((item) => item.session_id === storedSessionId)
    ) {
      void openSession(storedSessionId);
      return;
    }

    if (storedSessionId === null) {
      return;
    }

    if (filteredSessions.length > 0) {
      void openSession(filteredSessions[0].session_id);
    }
  }, [
    assistantsLoading,
    conversationByAssistant,
    filteredSessions,
    historyLoading,
    openSession,
    selectedAssistantId,
    teamId,
  ]);

  const toggleChunk = useCallback(
    (key: string) => {
      if (selectedAssistantId == null) return;
      updateConversation(selectedAssistantId, (current) => ({
        ...current,
        expandedChunkKeys: current.expandedChunkKeys.includes(key)
          ? current.expandedChunkKeys.filter((item) => item !== key)
          : [...current.expandedChunkKeys, key],
      }));
    },
    [selectedAssistantId, updateConversation],
  );

  const toggleSourceTurn = useCallback(
    (turnId: string) => {
      if (selectedAssistantId == null) return;
      updateConversation(selectedAssistantId, (current) => ({
        ...current,
        openSourceTurnIds: current.openSourceTurnIds.includes(turnId)
          ? current.openSourceTurnIds.filter((item) => item !== turnId)
          : [...current.openSourceTurnIds, turnId],
      }));
    },
    [selectedAssistantId, updateConversation],
  );

  const expandChunksForTurn = useCallback(
    (turnId: string, docs: RetrievedDoc[]) => {
      if (selectedAssistantId == null || docs.length === 0) return;
      updateConversation(selectedAssistantId, (current) => {
        const next = new Set(current.expandedChunkKeys);
        docs.forEach((_, index) => next.add(buildChunkKey(turnId, index)));
        return { ...current, expandedChunkKeys: Array.from(next) };
      });
    },
    [selectedAssistantId, updateConversation],
  );

  const collapseChunksForTurn = useCallback(
    (turnId: string, docs: RetrievedDoc[]) => {
      if (selectedAssistantId == null || docs.length === 0) return;
      updateConversation(selectedAssistantId, (current) => {
        const next = new Set(current.expandedChunkKeys);
        docs.forEach((_, index) => next.delete(buildChunkKey(turnId, index)));
        return { ...current, expandedChunkKeys: Array.from(next) };
      });
    },
    [selectedAssistantId, updateConversation],
  );

  const lastTurn = useMemo(() => {
    return activeConversation.turns.length > 0
      ? activeConversation.turns[activeConversation.turns.length - 1]
      : null;
  }, [activeConversation.turns]);

  const sourceDocs = lastTurn?.retrievedDocs ?? [];

  const expandAllChunks = useCallback(() => {
    if (selectedAssistantId == null || !lastTurn?.retrievedDocs.length) return;
    updateConversation(selectedAssistantId, (current) => ({
      ...current,
      expandedChunkKeys: lastTurn.retrievedDocs.map((_, index) =>
        buildChunkKey(lastTurn.id, index),
      ),
    }));
  }, [lastTurn, selectedAssistantId, updateConversation]);

  const collapseAllChunks = useCallback(() => {
    if (selectedAssistantId == null) return;
    updateConversation(selectedAssistantId, (current) => ({
      ...current,
      expandedChunkKeys: [],
    }));
  }, [selectedAssistantId, updateConversation]);

  const submit = useCallback(
    async (request?: Partial<AssistantChatRequest> & { query?: string }) => {
      const nextQuery = request?.query?.trim() ?? query.trim();

      if (!nextQuery || loading) return false;
      if (selectedAssistantId == null) {
        toast.error("请先选择一个助手");
        return false;
      }

      const turnId = `assistant-turn-${uuidv4()}`;
      let completed = false;

      activeTurnIdRef.current = turnId;
      setSubmitLoading(true);
      setQuery("");
      setMobileTab("chat");
      updateConversation(selectedAssistantId, (current) => ({
        ...current,
        expandedChunkKeys: [],
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
        const stream = await assistantsApi.stream(selectedAssistantId, {
          query: nextQuery,
          session_id: activeConversation.sessionId,
        });

        await consumeSseStream(stream, (event) => {
          const activeTurnId = activeTurnIdRef.current;
          if (!activeTurnId) return;

          switch (event.type) {
            case "retrieved": {
              const docs = event.data.retrieved_docs;
              if (!Array.isArray(docs)) break;
              updateConversation(selectedAssistantId, (current) => ({
                ...current,
                turns: current.turns.map((turn) =>
                  turn.id === activeTurnId
                    ? { ...turn, retrievedDocs: docs as RetrievedDoc[] }
                    : turn,
                ),
              }));
              break;
            }
            case "token": {
              const text = event.data.text;
              if (typeof text !== "string" || !text) break;
              updateConversation(selectedAssistantId, (current) => ({
                ...current,
                turns: current.turns.map((turn) =>
                  turn.id === activeTurnId
                    ? { ...turn, answer: `${turn.answer}${text}` }
                    : turn,
                ),
              }));
              break;
            }
            case "complete": {
              completed = true;
              const docs = event.data.retrieved_docs;
              const nextSessionId =
                typeof event.data.session_id === "string" ? event.data.session_id : null;
              const answerStatus =
                typeof event.data.answer_status === "string"
                  ? event.data.answer_status
                  : null;
              const logId =
                typeof event.data.log_id === "number" ? event.data.log_id : null;

              updateConversation(selectedAssistantId, (current) => ({
                ...current,
                sessionId: nextSessionId || current.sessionId,
                turns: current.turns.map((turn) =>
                  turn.id === activeTurnId
                    ? {
                        ...turn,
                        answer:
                          typeof event.data.answer === "string"
                            ? event.data.answer
                            : turn.answer,
                        answerStatus: answerStatus ?? turn.answerStatus,
                        logId: logId ?? turn.logId,
                        retrievedDocs: Array.isArray(docs)
                          ? (docs as RetrievedDoc[])
                          : turn.retrievedDocs,
                      }
                    : turn,
                ),
              }));

              if (nextSessionId) {
                persistActiveSessionId(selectedAssistantId, nextSessionId);
              }
              break;
            }
            case "error": {
              const message = String(event.data.message ?? "请求失败");
              updateConversation(selectedAssistantId, (current) => ({
                ...current,
                turns: current.turns.map((turn) =>
                  turn.id === activeTurnId ? { ...turn, error: message } : turn,
                ),
              }));
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
        const message = error instanceof Error ? error.message : "请求失败";
        const activeTurnId = activeTurnIdRef.current;
        if (activeTurnId) {
          updateConversation(selectedAssistantId, (current) => ({
            ...current,
            turns: current.turns.map((turn) =>
              turn.id === activeTurnId ? { ...turn, error: message } : turn,
            ),
          }));
        }
        toast.error(message);
        return false;
      } finally {
        setSubmitLoading(false);
        activeTurnIdRef.current = null;
      }
    },
    [
      activeConversation.sessionId,
      loadSessions,
      loading,
      persistActiveSessionId,
      query,
      selectedAssistantId,
      updateConversation,
    ],
  );

  return {
    teamId,
    setTeamId,
    teams,
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
    submitLoading,
    sessionLoading,
    deletingSessionId,
    historyLoading,
    turns: activeConversation.turns,
    sessions: filteredSessions,
    activeSessionId: activeConversation.sessionId,
    expandedChunks: new Set(activeConversation.expandedChunkKeys),
    openSourceTurnIds: new Set(activeConversation.openSourceTurnIds),
    mobileTab,
    setMobileTab,
    lastTurn,
    sourceDocs,
    toggleChunk,
    toggleSourceTurn,
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
